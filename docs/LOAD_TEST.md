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
LLM_PROVIDER=fake
EMBEDDINGS_PROVIDER=fake
EOF
bash /opt/studyrag/deploy/scripts/deploy.sh
```

Afterwards, delete those three lines, run `deploy.sh` again, and delete the "LoadTest" subject in the UI.
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

## Results template

| Metric | Before | After | Change |
|---|---:|---:|---:|
| Throughput (req/s), 50 users | | | |
| p95 latency (ms) | | | |
| Error rate under load (%) | | | |
| Errors while one instance is down | | | |
| Downtime seen by users during instance failure (s) | | | |
| Questions answered during Groq outage | 0/20 | /20 | |
| What the student sees on failure | "Internal server error" | answer (failover) or "AI service busy, retry" | |
