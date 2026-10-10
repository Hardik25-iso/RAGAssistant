"""Error-handling experiment: what does a student see when the primary LLM (Groq) is down?

Run it twice against the same deployment:
  before: ENABLE_RESILIENCE=false  CHAOS_FAIL_PRIMARY_LLM=true
  after:  ENABLE_RESILIENCE=true   CHAOS_FAIL_PRIMARY_LLM=true
(set both in /opt/studyrag/.env on every instance, then run deploy.sh)

    python deploy/loadtest/error_handling_test.py https://<host> --label before -n 20
Needs the "LoadTest" subject with a ready document (created by the locust test_start hook).
"""
import argparse
import os
import statistics
import time
from collections import Counter

import requests

ap = argparse.ArgumentParser()
ap.add_argument("host")
ap.add_argument("--label", default="run")
ap.add_argument("-n", type=int, default=20)
args = ap.parse_args()

host = args.host.rstrip("/")
s = requests.Session()
if os.getenv("LT_HEADER"):
    k, v = os.environ["LT_HEADER"].split(": ", 1)
    s.headers[k] = v
r = s.post(f"{host}/api/auth/login", json={"email": os.getenv("LT_EMAIL", "loadtest@studyrag.app"),
                                          "password": os.getenv("LT_PASSWORD", "LoadTest123")}, timeout=30)
r.raise_for_status()
s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
subject = next(x for x in s.get(f"{host}/api/subjects", timeout=30).json() if x["name"] == "LoadTest")

codes, latencies, bodies = Counter(), [], Counter()
for i in range(args.n):
    t = time.perf_counter()
    try:
        resp = s.post(f"{host}/api/chat/ask", json={"subject_id": subject["id"], "question": "What is normalization?"},
                      timeout=90)
        code = resp.status_code
        detail = resp.json().get("detail", "answered") if code != 200 else "answered"
    except requests.RequestException as exc:
        code, detail = "timeout/conn", type(exc).__name__
    latencies.append((time.perf_counter() - t) * 1000)
    codes[code] += 1
    bodies[str(detail)[:70]] += 1
    print(f"{i + 1:>3} {code} {latencies[-1]:7.0f} ms  {str(detail)[:60]}")

ok = codes.get(200, 0)
print(f"\n== {args.label}: {ok}/{args.n} answered ({100 * ok / args.n:.0f}%), "
      f"median {statistics.median(latencies):.0f} ms, max {max(latencies):.0f} ms")
print("status codes:", dict(codes))
print("what the user saw:", dict(bodies))
