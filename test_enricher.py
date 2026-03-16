import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from backend.services.candidate_enricher import enrich_hits
from backend.core.database import get_collection

async def main():
    print("Testing candidate enrichment with new ontology options...")
    hits = [
        {"candidate_id": "C-123", "experience_years": 5},
        {"candidate_id": "C-124", "experience_years": 8},
        {"candidate_id": "C-125", "experience_years": 10},
    ]

    print("--- Testing region filters ---")
    uk_results = enrich_hits(hits, min_experience_years=None, region="United Kingdom")
    remote_results = enrich_hits(hits, min_experience_years=None, region="Remote")
    print(f"UK Candidates Found: {len(uk_results)}")
    print(f"Remote Candidates Found: {len(remote_results)}")

    print("--- Testing industry filters ---")
    tech_results = enrich_hits(hits, min_experience_years=None, industry="Technology")
    finance_results = enrich_hits(hits, min_experience_years=None, industry="Finance")
    ecommerce_results = enrich_hits(hits, min_experience_years=None, industry="E-commerce")
    print(f"Technology Candidates Found: {len(tech_results)}")
    print(f"Finance Candidates Found: {len(finance_results)}")
    print(f"E-commerce Candidates Found: {len(ecommerce_results)}")

if __name__ == "__main__":
    asyncio.run(main())
