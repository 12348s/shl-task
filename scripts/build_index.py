"""
Step 2a: Build a semantic search index over catalog_clean.json using
Gemini's embedding API (no local ML dependency, no torch, lightweight
for free-tier deployment).

Usage:
    pip install numpy requests
    set GEMINI_API_KEY=your_key_here   (Windows)
    export GEMINI_API_KEY=your_key_here (Mac/Linux)
    python build_index.py

This is a ONE-TIME offline step. It reads catalog_clean.json (from
Step 1), embeds a text representation of each product via Gemini, and
saves:
    - catalog_embeddings.npy  (float32 matrix, one row per product)
    - catalog_index.json      (the catalog records, same row order as
                                the embeddings matrix)

Commit both output files to your repo -- the deployed FastAPI service
loads them at startup and does NOT re-embed the catalog on every boot.
Only per-query embedding happens live (see retriever.py).
"""

import json
import os
import time
from pathlib import Path

import numpy as np
import requests

from dotenv import load_dotenv

# Repo root = parent of this file's folder (scripts/ -> repo root -> data/)
REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=REPO_ROOT / ".env")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
EMBED_MODEL = "gemini-embedding-001"
BATCH_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{EMBED_MODEL}:batchEmbedContents?key={GEMINI_API_KEY}"
)
BATCH_SIZE = 50  # Gemini's batchEmbedContents caps around 100 requests/call

DATA_DIR = REPO_ROOT / "data"
CATALOG_PATH = DATA_DIR / "catalog_clean.json"
EMBEDDINGS_OUT = DATA_DIR / "catalog_embeddings.npy"
INDEX_OUT = DATA_DIR / "catalog_index.json"


def build_text_blob(record: dict) -> str:
    """Concatenate the fields that matter for semantic matching into one
    string per product. Name and description carry the most signal;
    job_levels and keys/test_type help match role-seniority and
    category-flavored queries (e.g. 'personality test for managers').
    """
    parts = [
        record.get("name", ""),
        record.get("description", ""),
        " ".join(record.get("job_levels", [])),
        " ".join(record.get("keys", [])),
    ]
    return " | ".join(p for p in parts if p)


def embed_batch(texts: list[str], retries: int = 6) -> list[list[float]]:
    payload = {
        "requests": [
            {
                "model": f"models/{EMBED_MODEL}",
                "content": {"parts": [{"text": t}]},
            }
            for t in texts
        ]
    }
    for attempt in range(retries):
        resp = requests.post(BATCH_ENDPOINT, json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            return [e["values"] for e in data["embeddings"]]
        if resp.status_code == 429:
            wait = 30 * (attempt + 1)  # 30s, 60s, 90s, 120s, 150s, 180s
            print(f"Rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        raise RuntimeError(f"Gemini embed error {resp.status_code}: {resp.text}")
    raise RuntimeError("Exceeded retries embedding batch")


def main():
    if not GEMINI_API_KEY:
        raise SystemExit(
            "GEMINI_API_KEY environment variable not set. "
            "Get a free key at https://aistudio.google.com/apikey"
        )

    with open(CATALOG_PATH, encoding="utf-8") as f:
        catalog = json.load(f)

    print(f"Loaded {len(catalog)} products from {CATALOG_PATH}")

    texts = [build_text_blob(r) for r in catalog]

    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        print(f"Embedding {i + 1}-{i + len(batch)} of {len(texts)}...")
        all_embeddings.extend(embed_batch(batch))
        if i + BATCH_SIZE < len(texts):  # don't sleep after last batch
            print("Sleeping 30s to respect rate limits...")
            time.sleep(30)

    embeddings = np.asarray(all_embeddings, dtype=np.float32)
    # Normalize so a plain dot product at query time equals cosine similarity.
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / np.clip(norms, 1e-10, None)

    np.save(EMBEDDINGS_OUT, embeddings)
    with open(INDEX_OUT, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print(f"Saved {embeddings.shape} embeddings to {EMBEDDINGS_OUT}")
    print(f"Saved catalog index to {INDEX_OUT}")

    


if __name__ == "__main__":
    main()