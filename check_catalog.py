import sys
sys.path.insert(0, 'app')
import json

with open('data/catalog_clean.json', encoding='utf-8') as f:
    data = json.load(f)

# Check Verify assessments
print("=== VERIFY ASSESSMENTS ===")
for item in data:
    if 'verify' in item['name'].lower():
        print(f"  {item['name']} | {item['test_type']}")

print("\n=== OPQ ASSESSMENTS ===")
for item in data:
    if 'opq' in item['name'].lower() or 'occupational personality' in item['name'].lower():
        print(f"  {item['name']} | {item['test_type']}")