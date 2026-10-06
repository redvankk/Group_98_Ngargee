"""Send a few questions to the running API and print the answers.

Start the API first (uvicorn main:app --port 8000), then:  python smoke_test.py
"""
import json
import sys
import urllib.request

API = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

QUESTIONS = [
    "I like to learn coding",
    "Are there any clubs for women in technology?",
    "I want to play chess",
    "I am interested in cybersecurity",
    "What is the capital of France?",  # should be declined
]


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.load(resp)


with urllib.request.urlopen(f"{API}/health", timeout=10) as resp:
    print("HEALTH:", json.dumps(json.load(resp), indent=2))

for question in QUESTIONS:
    data = post("/chat", {"question": question, "history": [], "top_k": 4})
    print("\n" + "=" * 80)
    print(f"Q: {question}")
    print(f"mode={data['mode']} retriever={data['retriever']} total={data['timings']['total_ms']} ms")
    print(data["answer"])
    for s in data["sources"]:
        print(f"  [{s['number']}] {s['name']} (score {s['score']}) {s['url']}")
