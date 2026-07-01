"""
Step 1: Fetch and prepare the SHL product catalog for the recommender agent.

Usage:
    python prepare_catalog.py

Downloads the raw catalog JSON, filters out Pre-packaged Job Solutions
(keeping only Individual Test Solutions), normalizes each record into a
consistent schema, and writes the result to catalog_clean.json.
"""

import json
import re
import urllib.request

CATALOG_URL = "https://tcp-us-prod-rnd.shl.com/voiceRater/shl-ai-hiring/shl_product_catalog.json"

# Map SHL's full category names to the single-letter test type codes
# used on the live product pages / in the assignment's example schema.
CATEGORY_TO_CODE = {
    "Ability & Aptitude": "A",
    "Biodata & Situational Judgment": "B",
    "Competencies": "C",
    "Development & 360": "D",
    "Assessment Exercises": "E",
    "Knowledge & Skills": "K",
    "Personality & Behavior": "P",
    "Simulations": "S",
}


def fetch_raw_catalog():
    req = urllib.request.Request(CATALOG_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw_text = resp.read().decode("utf-8")
    # strict=False tolerates raw/unescaped control characters (e.g. literal
    # newlines or tabs inside description strings) that the source JSON
    # contains but that Python's default strict parser rejects.
    return json.loads(raw_text, strict=False)


def is_packaged_solution(record: dict) -> bool:
    """Heuristic for identifying Pre-packaged Job Solutions (out of scope
    per the assignment), so they can be excluded, keeping only Individual
    Test Solutions.

    Two name-pattern signals, either of which is sufficient:
    1. Name ends in 'Solution' (e.g. 'Entry Level Cashier Solution',
       'Customer Service Phone Solution').
    2. Name starts with 'Entry Level' (catches bundles that follow the
       same family naming convention but don't happen to end in the word
       'Solution', e.g. 'Entry Level Customer Serv-Retail & Contact
       Center').

    NOTE: An earlier version of this heuristic also excluded any record
    with 'Competencies' in its `keys`. That was WRONG -- it swept out
    genuine standalone products like 'Global Skills Assessment',
    'RemoteWorkQ', and the HiPo/PJM/UCF reports, which are tagged
    Competencies but are not job-role bundles. Verified against raw
    `keys` data before removing that signal. Confirmed via
    diagnose_exclusions.py: the two name-pattern signals above account
    for all 8 genuine bundles in the current catalog with no known false
    positives, restoring the 13 wrongly-excluded standalone products.

    This is still a heuristic inferred from patterns in the data, not a
    field SHL explicitly provides -- spot-check the printed exclusion
    sample after running this script and adjust if the catalog changes.
    """
    name = record.get("name", "").strip()
    ends_in_solution = bool(re.search(r"\bSolutions?\s*$", name, re.IGNORECASE))
    starts_entry_level = name.lower().startswith("entry level")
    return ends_in_solution or starts_entry_level


def normalize(record: dict) -> dict:
    keys = record.get("keys", [])
    test_types = [CATEGORY_TO_CODE.get(k, k) for k in keys]
    return {
        "id": record.get("entity_id"),
        "name": record.get("name", "").strip(),
        "url": record.get("link"),
        "description": (record.get("description") or "").strip(),
        "job_levels": record.get("job_levels", []),
        "languages": record.get("languages", []),
        "duration": record.get("duration", ""),
        "remote_testing": record.get("remote") == "yes",
        "adaptive": record.get("adaptive") == "yes",
        "keys": keys,
        "test_type": test_types,
    }


def main():
    print(f"Fetching catalog from {CATALOG_URL} ...")
    raw = fetch_raw_catalog()
    print(f"Total raw records: {len(raw)}")

    individual = [r for r in raw if not is_packaged_solution(r)]
    packaged = [r for r in raw if is_packaged_solution(r)]

    print(f"Individual Test Solutions: {len(individual)}")
    print(f"Pre-packaged Job Solutions (excluded): {len(packaged)}")

    cleaned = [normalize(r) for r in individual]

    with open("catalog_clean.json", "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    print("Wrote catalog_clean.json")

    # Quick sanity check: print a few excluded names so you can eyeball
    # whether the "Solution" heuristic is catching the right things.
    print("\nSample of excluded (packaged) product names:")
    for r in packaged[:10]:
        print(" -", r.get("name"))


if __name__ == "__main__":
    main()