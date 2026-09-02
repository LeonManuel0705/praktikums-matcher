import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
COOKIE = {}


def call(path, payload=None, method=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(BASE + path, data=data, method=method or ("POST" if data else "GET"))
    request.add_header("Content-Type", "application/json")
    if COOKIE:
        request.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in COOKIE.items()))
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            for header in response.headers.get_all("Set-Cookie") or []:
                name, _, rest = header.partition("=")
                COOKIE[name] = rest.split(";")[0]
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        print(f"  HTTP {exc.code}: {exc.read().decode()[:200]}")
        raise


call("/api/auth/register", {"email": "e2e@example.com", "password": "geheim12345",
                            "name": "Leon", "school": "EHG Werder", "grade_level": "12"})
print("Konto angelegt und angemeldet")

call("/api/profile", {"interests": ["ai_tech"], "location": "Potsdam", "radius_km": 35,
                      "start_date": "2027-01-11", "end_date": "2027-01-29",
                      "compensation": "any", "free_text": "möchte was mit LLMs und Machine Learning machen"},
     method="PUT")
print("Profil gespeichert: KI/Tech, Potsdam 35 km, Januar 2027, LLM-Wunsch\n")

started = call("/api/searches", {})
search_id = started["search_id"]
print(f"Suche {search_id} gestartet über {started['provider']}\n")

last_event = 0
begin = time.time()
while time.time() - begin < 900:
    state = call(f"/api/searches/{search_id}?after_event={last_event}")
    for event in state["events"]:
        last_event = event["id"]
        print(f"  [{time.time() - begin:6.1f}s] {event['kind']:11} {event['message'][:110]}")
    if state["status"] != "running":
        break
    time.sleep(2)

final = call(f"/api/searches/{search_id}")
print(f"\nStatus: {final['status']}  Dauer: {time.time() - begin:.0f}s  Treffer: {len(final['results'])}\n")
for offer in final["results"][:8]:
    print(f"  {offer['score']:3d}%  {offer['title'][:52]:52} | {offer['company'][:20]:20} | {offer['city'][:18]}")
    for criterion in offer["breakdown"]["criteria"]:
        print(f"          {criterion['label']:11} {criterion['percent']:3d}%  {criterion['detail'][:62]}")
    print(f"          {offer['url'][:100]}")
sys.exit(0 if final["status"] == "done" else 1)
