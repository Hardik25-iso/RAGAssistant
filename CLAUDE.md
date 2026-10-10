# CLAUDE.md: project context for Claude Code

## What this is
StudyRAG: a secure, RAG-based study assistant. It is the CA3 mini-project for Cloud Computing (SIT Pune, AIML), and evaluation starts **14 Oct 2026**.
Students upload PPTX/PDF files per subject and chat with them. Answers cite the slide or page. Data is isolated per student.
The plan follows `RAG-Based Secure Study Assistant — Project Roadmap` (by Dakshesh Chauhan), with the changes below.

## Grading (10 marks)
- Project design, setup and config (2): modular code
- Implementation and cloud deployment (3): fully deployed, no errors
- Report (5): project, cloud setup, CI/CD, GitHub link
- Also required by the faculty: a load balancer and error handling, with a **before/after analysis** in the report. Report naming: `ICC01/ICC02_Group Number`.

## Decisions taken (and why)
- AWS ap-south-1. LLM: Groq `openai/gpt-oss-20b` (Groq dropped its Llama models on free tiers in Aug 2026), with Gemini as a failover. Embeddings: Gemini `gemini-embedding-001` at 768 dimensions (Groq has no embedding API).
- **CloudFront → ALB → 2× EC2** instead of DuckDNS + certbot. DuckDNS can't point at an ALB (A records only), and CloudFront gives a free HTTPS URL.
- No HNSW index: searches are always filtered by `owner_id` and `subject_id`, so an exact scan is correct and fast enough.
- Tables are created at startup (`init_db`, with a Postgres advisory lock), not through Alembic, to save time.
- CI/CD: GitHub Actions → GHCR images → rolling deploy through SSM Run Command, with GitHub OIDC (no SSH and no stored AWS keys).
- `ENABLE_RESILIENCE` and `CHAOS_FAIL_PRIMARY_LLM` flags exist only for the before/after error-handling experiment.

## Status (as of 10 Oct 2026)
DONE and verified in a sandbox:
- Backend: all routers, the RAG pipeline and the security layer. **30 pytest tests pass** on both SQLite and real Postgres 16 + pgvector. `ruff` is clean.
- Frontend builds. A browser end-to-end run passed through the real Nginx config (register → subject → upload PPTX → ask → citation → prompt-injection block).
- Nginx config passes `nginx -t`. A Locust smoke test ran against Gunicorn + Postgres with 0 errors.
- Deploy scripts, IAM policies, workflows and docs are written.

NOT DONE (next steps, in order):
1. `git remote add origin` and push to GitHub (public repo). Fill in `.github/CODEOWNERS` handles.
2. ~~Docker build~~ DONE 10 Oct: images build; fixed an init_db race between Gunicorn workers on a fresh DB.
3. ~~Real keys~~ DONE 10 Oct: real DBMS deck (157 slides) ingested, answers cite correct slides. Gemini free tier rate-limits embeddings (~100 texts/min), so ingestion now uses small batches and waits out 429s (`EMBED_BATCH_SIZE`, `EMBED_INGEST_BUDGET_SECONDS`). A large deck can take 1-2 min to reach `ready`.
4. AWS deployment: follow `docs/DEPLOYMENT.md` step by step. Run the "before" tests after step 9 and the "after" tests after step 12 (`docs/LOAD_TEST.md`).
5. Fill the results table in `docs/LOAD_TEST.md` and generate the chart with `deploy/loadtest/compare.py`.
6. Write the report in the college format (outline is in the roadmap §11; security table in `docs/SECURITY.md`). Collect AWS console screenshots (marked 📸 in DEPLOYMENT.md).

## Commands
```bash
cd backend && pip install -r requirements-dev.txt && pytest -q && ruff check app tests
cd backend && EMBEDDINGS_PROVIDER=fake LLM_PROVIDER=fake uvicorn app.main:app --reload   # no keys needed
cd frontend && npm install && npm run dev        # proxies /api to :8000
docker compose up --build                        # full stack at http://localhost:8080
```
On Windows, use Git Bash or WSL for the `.sh` scripts. The Python and Node steps work in PowerShell too.

## Layout
- `backend/app/{routers,models,schemas}`: API and data model
- `backend/app/rag`: RAG pipeline
- `backend/app/security`: security layer
- `backend/app/aws`: S3 and SSM helpers
- `frontend/src/{pages,components}`: React (Vite + Tailwind)
- `deploy/`: prod compose, nginx, scripts, IAM JSON and load tests
- `docs/`: DEPLOYMENT, SECURITY, LOAD_TEST

## Conventions
- Every data query is filtered by `owner_id`. Another user's resource returns 404, not 403. Keep this in any new endpoint.
- Admins see statistics and audit logs only, never document content.
- Commit prefixes: `feat(rag):`, `feat(aws):`, `fix(api):`, and so on. Each member commits only the files they own (CODEOWNERS).
