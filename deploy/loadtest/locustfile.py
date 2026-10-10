"""Load test for the before/after (single EC2 vs ALB + 2 EC2) comparison.

    pip install locust==2.32.4 requests
    export LT_EMAIL=loadtest@studyrag.app LT_PASSWORD='LoadTest123'
    locust -f deploy/loadtest/locustfile.py --host http://<EIP-or-ALB-or-CloudFront> \
           --headless -u 50 -r 5 -t 5m --csv results/after_50users

The test_start hook registers/logs in the load-test account, creates a
"LoadTest" subject and uploads a sample PDF once, so every run starts the same.
Each response's X-Instance-ID header is counted to show how the ALB spreads load.
"""
import io
import os
import random
import time
from collections import Counter

import requests
from locust import HttpUser, between, events, task

EMAIL = os.getenv("LT_EMAIL", "loadtest@studyrag.app")
PASSWORD = os.getenv("LT_PASSWORD", "LoadTest123")
# For hitting the ALB directly (it only forwards requests carrying the CloudFront secret header):
#   export LT_HEADER="X-Origin-Verify: <secret>"
EXTRA = dict([h.split(": ", 1)]) if os.getenv("LT_HEADER") else {}
QUESTIONS = [
    "What is normalization?",
    "Explain first normal form",
    "difference between paging and segmentation",
    "what is a deadlock",
    "explain the TCP three way handshake",
    "summarize the main topics",
]
SHARED: dict = {}
instances: Counter = Counter()


def _sample_pdf() -> bytes:
    import fitz  # PyMuPDF (pip install pymupdf)

    doc = fitz.open()
    pages = [
        "Normalization organises a relational database to reduce redundancy. 1NF requires atomic values. "
        "2NF removes partial dependency. 3NF removes transitive dependency.",
        "Paging divides memory into fixed-size frames. Segmentation divides memory into variable-size "
        "logical segments. Paging avoids external fragmentation.",
        "A deadlock happens when processes wait on each other forever. Conditions: mutual exclusion, "
        "hold and wait, no preemption, circular wait.",
        "TCP opens a connection with a three-way handshake: SYN, SYN-ACK, ACK.",
    ]
    for text in pages:
        doc.new_page().insert_textbox(fitz.Rect(50, 50, 550, 800), text, fontsize=11)
    return doc.tobytes()


@events.test_start.add_listener
def prepare(environment, **_):
    host = environment.host.rstrip("/")
    s = requests.Session()
    s.headers.update(EXTRA)
    r = s.post(f"{host}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    if r.status_code == 401:
        r = s.post(f"{host}/api/auth/register",
                   json={"name": "Load Test", "email": EMAIL, "password": PASSWORD}, timeout=30)
    r.raise_for_status()
    token = r.json()["access_token"]
    s.headers["Authorization"] = f"Bearer {token}"

    subjects = s.get(f"{host}/api/subjects", timeout=30).json()
    subject = next((x for x in subjects if x["name"] == "LoadTest"), None)
    if subject is None:
        subject = s.post(f"{host}/api/subjects", json={"name": "LoadTest"}, timeout=30).json()
    docs = s.get(f"{host}/api/documents", params={"subject_id": subject["id"]}, timeout=30).json()
    if not any(d["status"] == "ready" for d in docs):
        s.post(f"{host}/api/documents", data={"subject_id": subject["id"]},
               files={"file": ("loadtest_notes.pdf", io.BytesIO(_sample_pdf()), "application/pdf")}, timeout=120)
        for _ in range(40):
            docs = s.get(f"{host}/api/documents", params={"subject_id": subject["id"]}, timeout=30).json()
            if any(d["status"] == "ready" for d in docs):
                break
            time.sleep(3)
    SHARED.update(token=token, subject_id=subject["id"])
    print(f"[prepare] subject={subject['id']} docs={[d['status'] for d in docs]}")


@events.request.add_listener
def count_instance(response=None, **_):
    if response is not None and getattr(response, "headers", None):
        instances[response.headers.get("X-Instance-ID", "none")] += 1


@events.test_stop.add_listener
def report(**_):
    total = sum(instances.values()) or 1
    print("\n[instances] requests served per backend instance:")
    for name, n in instances.most_common():
        print(f"  {name:<20} {n:>7}  ({n / total:.0%})")


class Student(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.client.headers.update(EXTRA)
        # All simulated users run from one laptop. Give each its own client IP so the
        # Nginx per-IP edge limit sees 50 students on 50 IPs (like real traffic)
        # instead of one IP. Nginx takes the first X-Forwarded-For entry; CloudFront
        # and the ALB append theirs after it.
        self.client.headers["X-Forwarded-For"] = f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
        self.client.headers["Authorization"] = f"Bearer {SHARED['token']}"
        self.sid = SHARED["subject_id"]
        self.session_id = None

    @task(3)
    def list_subjects(self):
        self.client.get("/api/subjects", name="GET /api/subjects")

    @task(3)
    def list_documents(self):
        self.client.get(f"/api/documents?subject_id={self.sid}", name="GET /api/documents")

    @task(4)
    def search(self):
        self.client.post("/api/chat/search", json={"subject_id": self.sid, "query": random.choice(QUESTIONS)},
                         name="POST /api/chat/search")

    @task(2)
    def ask(self):
        body = {"subject_id": self.sid, "question": random.choice(QUESTIONS)}
        if self.session_id:
            body["session_id"] = self.session_id
        with self.client.post("/api/chat/ask", json=body, name="POST /api/chat/ask", catch_response=True) as r:
            if r.status_code == 200:
                self.session_id = r.json()["session_id"]
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(1)
    def health(self):
        self.client.get("/api/health", name="GET /api/health")
