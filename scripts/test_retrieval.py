"""
Step 2c: Interactive test harness for the retriever -- no LLM, no
FastAPI, just raw search so you can eyeball result quality.

Usage:
    python test_retrieval.py

Type a query, see top-10 ranked results with scores. Type 'quit' to exit.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=REPO_ROOT / ".env")

# retriever.py lives in app/, this script lives in scripts/ -- add app/
# to the import path so this works regardless of where you run it from.
sys.path.insert(0, str(REPO_ROOT / "app"))

from retriever import CatalogRetriever


def main():
    print("Loading retriever...")
    retriever = CatalogRetriever()
    print(f"Ready. {len(retriever.catalog)} products indexed.\n")

    while True:
        query = input("Query (or 'quit'): ").strip()
        if query.lower() in ("quit", "exit", ""):
            break

        results = retriever.search(query, top_k=10)
        print(f"\nTop {len(results)} results for: {query!r}\n")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['name']}  (score={r['_score']:.3f}, type={r['test_type']})")
            print(f"   {r['url']}")
        print()


if __name__ == "__main__":
    main()