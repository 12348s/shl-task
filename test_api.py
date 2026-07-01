import requests
import json

BASE_URL = "http://localhost:8000"

def test(label, messages):
    print(f"\n=== {label} ===")
    resp = requests.post(f"{BASE_URL}/chat", json={"messages": messages})
    data = resp.json()
    print(f"Status: {resp.status_code}")
    print(f"Reply: {data['reply'][:200]}")
    print(f"Recommendations: {len(data['recommendations'])}")
    for r in data['recommendations']:
        print(f"  - {r['name']} | {r['test_type']}")
    print(f"End of conversation: {data['end_of_conversation']}")

# Test 1: vague query
test("Vague query", [
    {"role": "user", "content": "I need an assessment"}
])

# Test 2: clear role + seniority
test("Java developer", [
    {"role": "user", "content": "I am hiring a mid-level Java developer with 4 years experience"}
])

# Test 3: multi-turn refinement
test("Refinement", [
    {"role": "user", "content": "I am hiring a mid-level Java developer"},
    {"role": "assistant", "content": "What seniority level are you targeting?"},
    {"role": "user", "content": "Mid level. Also add a personality test"}
])

# Test 4: off-topic refusal
test("Off-topic refusal", [
    {"role": "user", "content": "What salary should I offer a Java developer?"}
])

# Test 5: detailed query - should recommend on Turn 1 (like C4)
test("Graduate financial analyst - Turn 1 recommend", [
    {"role": "user", "content": "Hiring graduate financial analysts, final year students. We need numerical reasoning and a finance knowledge test."}
])