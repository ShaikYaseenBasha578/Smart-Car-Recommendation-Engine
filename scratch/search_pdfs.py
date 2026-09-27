from googlesearch import search
import time

def find_pdf(query):
    try:
        results = list(search(f"{query}", num_results=10))
        # Filter for .pdf
        return [r for r in results if r.endswith('.pdf')]
    except Exception as e:
        return [str(e)]

print("Thar ROXX:", find_pdf("Mahindra Thar ROXX brochure pdf site:mahindra.com OR site:auto.mahindra.com"))
print("Punch:", find_pdf("Tata Punch brochure pdf site:tatamotors.com"))
print("Aura:", find_pdf("Hyundai Aura brochure pdf site:hyundai.com"))
print("Dzire:", find_pdf("Maruti Dzire brochure pdf site:marutisuzuki.com OR site:nexaexperience.com"))
