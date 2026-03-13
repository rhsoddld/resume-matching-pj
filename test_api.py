import requests

BASE_URL = "http://127.0.0.1:8000"

def test_api():
    print("Testing /api/health...")
    r = requests.get(f"{BASE_URL}/api/health")
    print(r.status_code, r.text)
    
    # We need a candidate ID. Let's use the one we saw earlier: sneha-16852973
    candidate_id = "sneha-16852973"
    print(f"\nTesting /api/candidates/{candidate_id}...")
    r = requests.get(f"{BASE_URL}/api/candidates/{candidate_id}")
    print(f"Status: {r.status_code}")
    print("Response keys:", list(r.json().keys()) if r.status_code == 200 else r.text)
    
    print("\nTesting /api/jobs/match...")
    payload = {
        "job_description": "Looking for a seasoned HR professional with marketing experience.",
        "top_k": 3,
        "category": "HR"
    }
    r = requests.post(f"{BASE_URL}/api/jobs/match", json=payload)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        matches = r.json().get("matches", [])
        print(f"Found {len(matches)} matches.")
        if matches:
            print("Top match:", matches[0])
    else:
        print(r.text)

if __name__ == "__main__":
    test_api()
