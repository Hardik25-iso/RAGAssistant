# Before / after analysis (load balancer + error handling)

Three experiments, each run on the "before" and "after" setup with the same workload. Paste the
tables and the chart into the report's Testing and Results chapter.

| | Before | After |
|---|---|---|
| Infrastructure | 1 EC2 (t3.micro), reached directly on its Elastic IP | CloudFront → ALB → 2 EC2 in two AZs |
| Error handling | `ENABLE_RESILIENCE=false`: one attempt, 120 s timeout, raw 500s | retries with backoff + jitter, 15 s timeouts, 20 s budget, Groq → Gemini failover, clean 503 + `Retry-After` |

## Setup on your laptop

```bash
pip install locust==2.32.4 requests pymupdf matplotlib
export LT_EMAIL=loadtest@studyrag.app LT_PASSWORD=LoadTest123
mkdir -p results
```

## Test mode on the instances (switch it on before, off after)

Locust would burn the Groq/Gemini free-tier quotas in seconds and hit the per-user rate limits,
which would hide what we are measuring (the infrastructure). So during experiments 1 and 2, on **every**
instance (SSM Session Manager → `sudo -i`):

```bash
cat >> /opt/studyrag/.env <<'EOF'
RATE_LIMIT_ENABLED=false
MAX_QUERIES_PER_DAY=1000000
LLM_PROVIDER=fake
EMBEDDINGS_PROVIDER=fake
EOF
bash /opt/studyrag/deploy/scripts/deploy.sh
```

Afterwards, delete those four lines, run `deploy.sh` again, and delete the "LoadTest" subject in the UI.
Locust gives each simulated user its own `X-Forwarded-For` IP, so the Nginx per-IP edge limit
(20 req/s) behaves as it would for 50 real students instead of throttling one laptop.
Say this in the report: the AI calls were stubbed so the numbers measure the cloud setup (database, compute,
load balancing), not Groq's latency.

## Experiment 1: throughput and latency

```bash
# BEFORE: single instance (studyrag-ec2 temporarily allows port 80 from your IP)
locust -f deploy/loadtest/locustfile.py --host http://<ELASTIC-IP> --headless -u 50 -r 5 -t 5m \
       --csv results/before_50 --only-summary

# AFTER: the same, through the ALB (header needed because the ALB only accepts CloudFront traffic)
export LT_HEADER="X-Origin-Verify: <your-secret>"
locust -f deploy/loadtest/locustfile.py --host http://<ALB-DNS-NAME> --headless -u 50 -r 5 -t 5m \
       --csv results/after_50 --only-summary

python deploy/loadtest/compare.py results/before_50 results/after_50   # table + results/before_vs_after.png
```

Repeat with `-u 100` if 50 users doesn't stress the single t3.micro. The `[instances]` block at the end of
each run shows how requests were split across instances: about 50/50 after, 100% before.

## Experiment 2: instance failure (availability)

Start the same Locust command with `-t 4m`. At about 1:30, stop the app on one instance:

```bash
docker compose -f /opt/studyrag/deploy/docker-compose.prod.yml stop backend   # wait 60 s, then:
docker compose -f /opt/studyrag/deploy/docker-compose.prod.yml start backend
```

- Before: every request fails for the whole minute (the only instance is down).
- After: Nginx answers 503 for a few seconds until the ALB health check (every 10 s, 2 failures) marks the
  target unhealthy. Then all traffic goes to the healthy instance with no errors, and the instance rejoins
  automatically after 2 passing checks.

Plot `results/*_stats_history.csv` (columns `Timestamp`, `Failures/s`) for both runs, or screenshot the
ALB target group's "Healthy hosts" graph and the Locust failures.

## Experiment 3: error handling when the LLM provider fails

Fault injection: `CHAOS_FAIL_PRIMARY_LLM=true` makes every Groq call return HTTP 503.

```bash
# on every instance: put real providers back (remove the test-mode lines), then
echo "CHAOS_FAIL_PRIMARY_LLM=true" >> /opt/studyrag/.env
sed -i "s/^ENABLE_RESILIENCE=.*/ENABLE_RESILIENCE=false/" /opt/studyrag/.env   # BEFORE
bash /opt/studyrag/deploy/scripts/deploy.sh
python deploy/loadtest/error_handling_test.py https://<cloudfront-domain> --label before -n 20

sed -i 's/ENABLE_RESILIENCE=false/ENABLE_RESILIENCE=true/' /opt/studyrag/.env   # AFTER
bash /opt/studyrag/deploy/scripts/deploy.sh
python deploy/loadtest/error_handling_test.py https://<cloudfront-domain> --label after -n 20
```

Expected: before, 0/20 answered, each one a generic "Internal server error" (500). After, 20/20 answered
via the Gemini failover, a little slower because of the retries. Finally, remove both lines and redeploy.

## Results (measured 10 Oct 2026, ap-south-1)

Before = 1 × t3.micro reached directly. After = ALB → 2 × t3.micro in ap-south-1a and 1b (hit on the ALB
with the origin header, since CloudFront was pending account verification). Same app version (`1b84126`),
same RDS db.t4g.micro, AI calls stubbed for experiments 1–2. Locust: 1–3 s think time per user.

### Experiment 1: throughput and latency

| Metric | Before, 50 users | After, 50 users | Before, 150 users | After, 150 users |
|---|---:|---:|---:|---:|
| Throughput (req/s) | 23.9 | 23.7 | 69.1 | 69.2 |
| Median latency (ms) | 28 | 38 | 50 | **34** (−32%) |
| p95 latency (ms) | 130 | 230 | 330 | **270** (−18%) |
| p99 latency (ms) | 640 | 420 | 960 | 1100 |
| Error rate (%) | 0.00 | 0.00 | 0.01 | **0.00** |
| Requests per instance | 100% | 50% / 50% | 100% | 50% / 50% |

Throughput is the same in both setups because it is bounded by the users' think time, not by the servers.
At 50 users the extra ALB hop adds ~10 ms. At 150 users each instance carries half the load, so median and
p95 latency drop and the single instance's 503s disappear. Charts: `results/before_vs_after_50.png`,
`results/before_vs_after_150.png`.

Found and fixed during the "after" run: under 150 users the first version deadlocked (SQLAlchemy pool
exhausted while FastAPI threads waited, 112 errors, 62 s requests). Fix in `app/security/rbac.py`
(release the connection after authentication); rerun gave 0 errors.

### Experiment 2: instance failure (backend stopped for 60 s, 50 users, 4 min)

| Metric | Before | After |
|---|---:|---:|
| Failed requests | 780 / 4622 (16.9%) | **157 / 5320 (2.95%)** |
| Time users saw errors (s) | 79 | **40** |
| Where the traffic went | nowhere (only instance down) | healthy instance (65% / 33% split over the run) |

After: errors only until the ALB health check (10 s interval, 2 failures) took the target out, then all
traffic went to the healthy instance; the stopped one rejoined automatically.

### Experiment 3: Groq outage (`CHAOS_FAIL_PRIMARY_LLM=true`, 20 questions, real providers)

| Metric | Before (`ENABLE_RESILIENCE=false`) | After (`true`) |
|---|---:|---:|
| Questions answered | 0 / 20 | **13 / 20** (via Gemini failover) |
| Status codes | 500 × 20 | 200 × 13, 503 × 7 |
| What the student saw | "Internal server error" | the answer, or "The AI service is busy right now. Please try again in a few seconds." |
| Median latency | 0.6 s | 6.8 s (retries + failover) |

The 7 unanswered questions hit Gemini's free-tier rate limit (6 × 429, 1 × 503) because the test fires 20
questions within a minute. Both providers down at once still gives the student a clear retry message
instead of a crash.
