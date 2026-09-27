from knowledge_base.ingestion.common.resolver import compute_similarity

s1 = "VXi Manual"
c1 = "VXi Petrol Manual"
c2 = "VXi (O) Petrol Manual"

print("c1:", max(compute_similarity(s1, c1), compute_similarity(s1.replace('-',' '), c1)))
print("c2:", max(compute_similarity(s1, c2), compute_similarity(s1.replace('-',' '), c2)))
