# AWS deployment guide

Region: **ap-south-1 (Mumbai)**. Follow the steps in order, and take the screenshots marked 📸 for the report.

```
Browser ──HTTPS──▶ CloudFront ──HTTP + secret header──▶ ALB ──▶ EC2 #1 (Nginx → FastAPI)  ─┐
 (TLS, *.cloudfront.net cert)   (SG: CloudFront IPs only)   └──▶ EC2 #2 (Nginx → FastAPI)  ─┤
                                                                                           ├─▶ RDS PostgreSQL + pgvector (private)
                                                                                           ├─▶ S3 (private, SSE-KMS)
                                                                                           ├─▶ SSM Parameter Store (secrets)
                                                                                           └─▶ Groq / Gemini APIs
GitHub Actions ──OIDC──▶ IAM role ──SSM Run Command──▶ EC2 (rolling deploy, no SSH)
```

**Why CloudFront instead of DuckDNS + certbot:** DuckDNS can only create A records, and an ALB has no fixed IP,
so a DuckDNS name can't point at it. CloudFront gives a free HTTPS URL (`https://dxxxx.cloudfront.net`) with
an AWS-managed certificate, and you don't need to buy a domain.

---

## 1. Account security
1. Turn on MFA for the root user, then stop using root.
2. IAM → Users: create one user per teammate with MFA and the `AdministratorAccess` policy (project only).
3. Billing → Budgets → create a **$5 monthly cost budget** with an email alert. 📸

## 2. API keys
- Groq: console.groq.com → API Keys (the model is `openai/gpt-oss-20b`).
- Gemini: aistudio.google.com → Get API key (used for embeddings and as the backup LLM).

## 3. Security groups (EC2 → Security Groups, default VPC)
| Name | Inbound rule | Why |
|---|---|---|
| `sg-alb` | HTTP 80 from **prefix list** `com.amazonaws.global.cloudfront.origin-facing` | Only CloudFront can reach the ALB |
| `sg-ec2` | HTTP 80 from `sg-alb` (+ **temporarily** HTTP 80 from *My IP* for the "before" test) | Instances aren't reachable from the internet |
| `sg-rds` | PostgreSQL 5432 from `sg-ec2` | Only the app can reach the database |

There is no SSH (port 22) rule anywhere. Use **Session Manager** for shell access. 📸

## 4. S3 bucket `studyrag-docs-<team>`
1. Block *all* public access: on.
2. Default encryption: **SSE-KMS** with the `aws/s3` key, Bucket Key enabled.
3. Permissions → Bucket policy: paste `deploy/aws/s3_bucket_policy.json` (replace `TEAM`). It denies non-HTTPS
   requests and unencrypted uploads. 📸

## 5. RDS PostgreSQL
Create database → Standard create → PostgreSQL **16** → template *Free tier*.
- `db.t4g.micro`, 20 GB gp3, **storage encryption on**, initial database name `studyrag`.
- Master username `studyrag`, a strong password (Secrets Manager option: off; we use Parameter Store).
- Public access **No**, security group **sg-rds**, automated backups 7 days.
- The app runs `CREATE EXTENSION vector` itself on first start. RDS for PostgreSQL 16 forces SSL by default. 📸

## 6. Secrets in Parameter Store (Systems Manager → Parameter Store)
Create each one as **SecureString** (KMS key `alias/aws/ssm`):

| Name | Value |
|---|---|
| `/studyrag/DATABASE_URL` | `postgresql+psycopg://studyrag:<password>@<rds-endpoint>:5432/studyrag?sslmode=require` |
| `/studyrag/JWT_SECRET` | output of `openssl rand -hex 32` |
| `/studyrag/GROQ_API_KEY` | your Groq key |
| `/studyrag/GEMINI_API_KEY` | your Gemini key |
| `/studyrag/ADMIN_EMAIL` | e.g. `admin@studyrag.app` |
| `/studyrag/ADMIN_PASSWORD` | a strong password (the admin account is created on first start) |

📸 Take the screenshot with values hidden.

## 7. IAM role for EC2: `StudyRagEc2Role`
IAM → Roles → Create → trusted entity **EC2**. Attach:
- `AmazonSSMManagedInstanceCore` (Session Manager + Run Command)
- An inline policy from `deploy/aws/iam_ec2_policy.json`, replacing `TEAM` and `ACCOUNT_ID`. It allows S3 access
  only under `users/*` (plus `backups/*` write), `/studyrag/*` parameters only, KMS only via S3/SSM, and its own
  log group only. 📸

## 8. GitHub repository
1. Push the code to `github.com/<you>/RAGAssistant` and add teammates as collaborators.
2. Settings → Code security: turn on **secret scanning** and **push protection**.
3. Settings → Branches → protect `main`: require a PR, 1 approval, and passing status checks (CI).
4. Actions → run **Deploy** once by hand (*Run workflow*). It builds both images and pushes them to GHCR.
   The deploy step only warns, because no instances exist yet.
5. Your profile → Packages → `studyrag-backend` and `studyrag-web` → Package settings → **Change visibility → Public**
   (the images contain no secrets; this lets EC2 pull them without a token).

## 9. EC2 instance #1 (this is the "before" setup)
Launch instance:
- Name `studyrag-1`, tag **`App = studyrag`**. Ubuntu Server 24.04, `t3.micro`, no key pair.
- Network: default VPC, subnet in **ap-south-1a**, auto-assign public IP on (needed for outbound calls to Groq,
  Gemini and GHCR), security group **sg-ec2**.
- Storage: 30 GB gp3, **Encrypted**.
- Advanced → IAM instance profile **StudyRagEc2Role**.
- Advanced → Metadata: **IMDSv2 required**, **hop limit 2** (containers need the extra hop to get role credentials).
- Advanced → User data:
  ```bash
  #!/bin/bash
  export GHCR_OWNER=<github-username-lowercase>
  export REPO_URL=https://github.com/<you>/RAGAssistant.git
  export S3_BUCKET=studyrag-docs-<team>
  curl -fsSL https://raw.githubusercontent.com/<you>/RAGAssistant/main/deploy/scripts/setup_ec2.sh | bash
  ```
After about 5 minutes, allocate an **Elastic IP**, associate it, and open `http://<EIP>` (your IP is allowed by the
temporary rule). Register, upload a PPTX, and ask a question. 📸

If something fails: Systems Manager → Session Manager → start a session → `sudo tail -100 /var/log/cloud-init-output.log`,
then `cd /opt/studyrag && sudo docker compose -f deploy/docker-compose.prod.yml logs backend`.

➡️ Now run the **"before"** measurements in `docs/LOAD_TEST.md`.

## 10. EC2 instance #2
Select `studyrag-1` → Actions → Image and templates → **Launch more like this**. Rename it `studyrag-2` and
choose subnet **ap-south-1b**. Check that the role, metadata settings, tag and user data were copied.

## 11. Target group + Application Load Balancer
1. Target group `tg-studyrag`: type Instances, HTTP 80. Health check `/api/health`, interval **10 s**, timeout 5 s,
   healthy 2, unhealthy 2, success code 200. Register both instances. Under Attributes, set deregistration delay to 30 s.
2. Load balancer `alb-studyrag`: internet-facing, subnets in 1a and 1b, security group **sg-alb**.
   - Listener HTTP:80, **default action: fixed response 403**.
   - Add a listener rule: *HTTP header* `X-Origin-Verify` equals `<long random secret>` → forward to `tg-studyrag`.
   - Attributes → idle timeout **120 s**.
3. Wait until both targets show **healthy**. 📸

## 12. CloudFront distribution (HTTPS + deployment link)
- Origin: the ALB DNS name, protocol **HTTP only**, port 80, response timeout **60 s**.
  Add a custom header `X-Origin-Verify: <same secret>`.
- Default behavior: viewer protocol **Redirect HTTP to HTTPS**; allowed methods **GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE**;
  cache policy **CachingDisabled**; origin request policy **AllViewerExceptHostHeader**.
- Add a behavior for `/assets/*` with cache policy **CachingOptimized** (the React build is cached at the edge).
- Price class: *Use North America, Europe, Asia, Middle East, and Africa* (includes India).
- WAF: optional. The "Enable security protections" option is a paid service.

Your deployment link is `https://dxxxxxxxx.cloudfront.net` (API docs at `/api/docs`). 📸

Then lock everything down:
- `sg-ec2`: delete the temporary *My IP* rule.
- Release the Elastic IP (idle Elastic IPs cost money).
- Set the allowed origin on both instances, then redeploy:
  `sudo sed -i 's#^CORS_ORIGINS=.*#CORS_ORIGINS=https://dxxxx.cloudfront.net#' /opt/studyrag/.env && sudo bash /opt/studyrag/deploy/scripts/deploy.sh`

➡️ Run the **"after"** measurements in `docs/LOAD_TEST.md`.

## 13. CI/CD with GitHub OIDC (no AWS keys in GitHub)
1. IAM → Identity providers → Add → OpenID Connect: URL `https://token.actions.githubusercontent.com`,
   audience `sts.amazonaws.com`.
2. IAM → Roles → Create → Custom trust policy: `deploy/aws/github_oidc_trust.json` (replace `ACCOUNT_ID`, `GITHUB_USER`). The deploy job runs in the `production` environment, so GitHub signs its token with `sub = repo:<you>/RAGAssistant:environment:production`; the trust policy matches exactly that.
   Inline policy: `deploy/aws/github_deploy_policy.json`. Name it `StudyRagGithubDeploy`.
3. GitHub → Settings → Environments → create `production`. Settings → Secrets → Actions → add
   `AWS_DEPLOY_ROLE_ARN` = the role's ARN.
4. Merge a PR into `main`. CI runs (ruff, pytest on Postgres+pgvector, frontend build, npm audit, Docker builds),
   then Deploy builds the images, pushes them to GHCR, and updates the instances **one at a time** through SSM
   Run Command. Each instance must pass its health check before the next one is updated, so the ALB always has a
   healthy target. 📸 the Actions run and the SSM Run Command history.

## 14. Monitoring
- CloudWatch → Log groups → `/studyrag/app`: container logs from both instances (one stream per instance). 📸
- Alarms (send to an SNS email topic):
  - `CPUUtilization > 80%` for 5 minutes, one per instance
  - ALB target group `UnHealthyHostCount > 0`
  - ALB `HTTPCode_Target_5XX_Count > 10` in 5 minutes
- CloudTrail → Event history: shows who changed what in the account. 📸
- The app's own audit log is on the Admin dashboard. 📸

## 15. Demo accounts (put them in the README for the evaluator)
- The admin is created from `/studyrag/ADMIN_EMAIL` and `/studyrag/ADMIN_PASSWORD`.
- Register `studenta@studyrag.app` and `studentb@studyrag.app`. Upload different files as each, and show that
  A sees nothing of B's (`pytest -k isolation` proves the same thing in CI).

## 16. After evaluation (avoid charges)
Delete, in this order: the CloudFront distribution (disable it first), ALB, target group, both EC2 instances,
the RDS instance (skip the final snapshot), the S3 bucket, the Parameter Store entries, the IAM roles, the OIDC
provider, and any unused Elastic IP.
