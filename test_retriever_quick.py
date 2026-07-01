import sys
sys.path.insert(0, 'app')
from retriever import CatalogRetriever

r = CatalogRetriever()
results = r.search('Java developer mid level', top_k=5)
for res in results:
    print(f"{res['name']} | score={res['_score']:.3f} | type={res['test_type']}")
