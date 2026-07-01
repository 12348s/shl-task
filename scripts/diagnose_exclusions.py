"""
Diagnostic: print full raw records for items the filter excluded,
so we can check whether the 'packaged Job Solution' heuristic is
correctly classifying them.
"""

import json
import re
import urllib.request

CATALOG_URL = "https://tcp-us-prod-rnd.shl.com/voiceRater/shl-ai-hiring/shl_product_catalog.json"


def fetch_raw_catalog():
    req = urllib.request.Request(CATALOG_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw_text = resp.read().decode("utf-8")
    return json.loads(raw_text, strict=False)


def is_packaged_solution(record: dict) -> bool:
    name = record.get("name", "").strip()
    keys = record.get("keys", [])
    ends_in_solution = bool(re.search(r"\bSolutions?\s*$", name, re.IGNORECASE))
    has_competencies = "Competencies" in keys
    return ends_in_solution or has_competencies


def main():
    raw = fetch_raw_catalog()
    packaged = [r for r in raw if is_packaged_solution(r)]

    print(f"Total excluded: {len(packaged)}\n")
    for r in packaged:
        name = r.get("name")
        keys = r.get("keys", [])
        ends_in_solution = bool(re.search(r"\bSolutions?\s*$", name.strip(), re.IGNORECASE))
        has_competencies = "Competencies" in keys
        reason = []
        if ends_in_solution:
            reason.append("name ends in 'Solution'")
        if has_competencies:
            reason.append("has 'Competencies' key")
        print(f"- {name}")
        print(f"    keys: {keys}")
        print(f"    excluded because: {', '.join(reason)}")
        print()


if __name__ == "__main__":
    main()