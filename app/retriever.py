"""
Step 2b: Catalog retriever -- hybrid semantic + metadata search.

Loads the pre-built embeddings/index (from build_index.py) once, then
exposes a simple search() method your FastAPI agent code can call per
/chat request. Query embedding happens live via Gemini's embedding API
(one call per user query -- cheap and well within free-tier limits).

Import and use like:

    from retriever import CatalogRetriever

    retriever = CatalogRetriever()  # loads index once at startup
    results = retriever.search(
        "Java developer with 4 years experience, needs to work with stakeholders",
        top_k=10,
    )
"""

import json
import os
from pathlib import Path

import numpy as np
import requests

from dotenv import load_dotenv

# Repo root = parent of this file's folder (app/ -> repo root -> data/)
REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=REPO_ROOT / ".env")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
EMBED_MODEL = "gemini-embedding-001"
EMBED_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{EMBED_MODEL}:embedContent?key={GEMINI_API_KEY}"
)

DATA_DIR = REPO_ROOT / "data"
EMBEDDINGS_PATH = DATA_DIR / "catalog_embeddings.npy"
INDEX_PATH = DATA_DIR / "catalog_index.json"


class CatalogRetriever:
    def __init__(
        self,
        embeddings_path: str = EMBEDDINGS_PATH,
        index_path: str = INDEX_PATH,
    ):
        self.embeddings = np.load(embeddings_path)
        with open(index_path, encoding="utf-8") as f:
            self.catalog = json.load(f)

        if len(self.catalog) != self.embeddings.shape[0]:
            raise ValueError(
                f"Catalog has {len(self.catalog)} records but embeddings "
                f"matrix has {self.embeddings.shape[0]} rows -- rerun "
                f"build_index.py, these must stay in sync."
            )

    def _embed_query(self, query: str) -> np.ndarray:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY environment variable not set.")
        payload = {"content": {"parts": [{"text": query}]}}
        resp = requests.post(EMBED_ENDPOINT, json=payload, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini embed error {resp.status_code}: {resp.text}")
        vec = np.asarray(resp.json()["embedding"]["values"], dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 1e-10:
            vec = vec / norm
        return vec

    def _passes_filters(self, record: dict, filters: dict) -> bool:
        """filters is a dict of optional constraints:
            job_level: str -- must appear in record['job_levels']
            language: str -- must appear in record['languages']
            remote_only: bool -- if True, record['remote_testing'] must be True
            adaptive_only: bool -- if True, record['adaptive'] must be True
            max_duration_minutes: int -- record's parsed duration must be <= this
            test_types: list[str] -- record['test_type'] must intersect this list
        Any key not present in filters is not checked.
        """
        if not filters:
            return True

        if filters.get("job_level"):
            if filters["job_level"] not in record.get("job_levels", []):
                return False

        if filters.get("language"):
            if filters["language"] not in record.get("languages", []):
                return False

        if filters.get("remote_only"):
            if not record.get("remote_testing"):
                return False

        if filters.get("adaptive_only"):
            if not record.get("adaptive"):
                return False

        if filters.get("test_types"):
            wanted = set(filters["test_types"])
            if not wanted.intersection(record.get("test_type", [])):
                return False

        if filters.get("max_duration_minutes") is not None:
            minutes = _parse_duration_minutes(record.get("duration", ""))
            if minutes is not None and minutes > filters["max_duration_minutes"]:
                return False

        return True

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict | None = None,
        candidate_pool: int = 50,
    ) -> list[dict]:
        """Returns up to top_k catalog records ranked by semantic
        similarity to `query`, after applying `filters`.

        candidate_pool controls how many top semantic matches are
        considered before filtering -- kept generous (50) so that
        filters don't starve the results when the best semantic matches
        happen to fail a filter (e.g. wrong language).
        """
        query_vec = self._embed_query(query)
        scores = self.embeddings @ query_vec  # cosine similarity (both normalized)

        ranked_idx = np.argsort(-scores)[:candidate_pool]

        results = []
        for idx in ranked_idx:
            record = self.catalog[idx]
            if self._passes_filters(record, filters or {}):
                enriched = dict(record)
                enriched["_score"] = float(scores[idx])
                results.append(enriched)
            if len(results) >= top_k:
                break

        return results


def _parse_duration_minutes(duration_raw: str) -> int | None:
    """Best-effort parse of strings like '30 minutes' -> 30. Returns
    None if it can't confidently parse (caller should treat as
    'unknown, don't filter it out')."""
    if not duration_raw:
        return None
    digits = "".join(c for c in duration_raw if c.isdigit())
    return int(digits) if digits else None


if __name__ == "__main__":
    # Quick smoke test
    r = CatalogRetriever()
    print(f"Loaded {len(r.catalog)} products, embeddings shape {r.embeddings.shape}")