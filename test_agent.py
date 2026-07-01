import sys
sys.path.insert(0, 'app')
from agent import chat

# Test 1: vague query - should ask clarifying question, no recommendations
print("=== Test 1: Vague query ===")
result = chat([{"role": "user", "content": "I need an assessment"}])
print(f"Reply: {result['reply']}")
print(f"Recommendations: {result['recommendations']}")
print()

# Test 2: clear query - should recommend
print("=== Test 2: Clear query ===")
result = chat([
    {"role": "user", "content": "I am hiring a mid-level Java developer"},
    {"role": "assistant", "content": "What seniority level are you targeting?"},
    {"role": "user", "content": "Mid level, about 4 years experience"}
])
print(f"Reply: {result['reply'][:200]}")
print(f"Recommendations count: {len(result['recommendations'])}")
for r in result['recommendations']:
    print(f"  - {r['name']} | {r['test_type']} | {r['url']}")