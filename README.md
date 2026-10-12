# StudyRAG: RAG-based secure study assistant

Students upload their lecture PPTX and PDF files, organise them by subject, and chat with them.
Every answer cites the exact slide or page (for example `DBMS_Unit2.pptx · Slide 14`). Each student's
files and chats are private to them. The app runs on AWS behind an Application Load Balancer, with two
EC2 instances in two Availability Zones, RDS PostgreSQL + pgvector, S3 (SSE-KMS) and SSM Parameter Store.

- **Live app:** http://alb-studyrag-1301669676.ap-south-1.elb.amazonaws.com (API docs: `/api/docs`)
- HTTPS through CloudFront is prepared but waiting for AWS account verification; until then the ALB serves plain HTTP.
- **Demo accounts:** Student A `studenta@studyrag.app` / Student B `studentb@studyrag.app` / Admin, with passwords shared with the evaluator

## Stack
| Layer | Choice |
|---|---|
| Frontend | React 18 (Vite), Tailwind CSS, Axios, react-markdown, served by Nginx |
| Backend | FastAPI, Gunicorn + Uvicorn workers, SQLAlchemy 2 |
| RAG | PyMuPDF (PDF), python-pptx (slides + speaker notes), ~500-token chunks, Gemini `gemini-embedding-001` (768-d), pgvector cosine search, Groq `openai/gpt-oss-20b` (Gemini as backup) |
| AWS | ALB (CloudFront pending), 2× EC2 t3.micro (Docker Compose), RDS PostgreSQL 16, S3, SSM Parameter Store, KMS, CloudWatch, CloudTrail, Budgets |
| CI/CD | GitHub Actions: lint + tests (Postgres+pgvector service) → build images → GHCR → rolling deploy through SSM Run Command (OIDC, no stored keys) |

## Run locally
```bash
cp .env.example .env              # add GROQ_API_KEY and GEMINI_API_KEY
docker compose up --build         # http://localhost:8080
```
Without Docker:
```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
uvicorn app.main:app --reload     # SQLite + local file storage by default
cd ../frontend && npm install && npm run dev      # http://localhost:5173
```
To run the app with no API keys at all, set `EMBEDDINGS_PROVIDER=fake LLM_PROVIDER=fake`.

## Tests
```bash
cd backend && pytest -q && ruff check app tests
```
30 tests cover auth, RBAC, PDF/PPTX ingestion and citations, prompt injection, **Student A cannot reach Student B's data**,
upload attacks (wrong signature, zip bomb, `.ppt`, oversize, path traversal), security headers, retries, and the
Groq-outage failover.

## Repository layout
```
backend/app/        main, config, database, errors
  models/ schemas/ routers/      data model + REST API (auth, subjects, documents, chat, admin)
  rag/              loaders, chunker, embeddings, vector_store, retriever, prompts, prompt_guard, llm, pipeline, resilience
  security/         jwt, password, rbac, rate_limiter, file_validator, audit, headers
  aws/              s3_storage, ssm_config
frontend/src/       pages (Login, Register, Dashboard, Subject, Chat, AdminDashboard) + components
deploy/             docker-compose.prod.yml, nginx, scripts (setup_ec2, deploy, rolling_deploy, backup_db), aws IAM policies, loadtest
docs/               DEPLOYMENT.md, SECURITY.md, LOAD_TEST.md
```

## Docs
- [AWS deployment, step by step](docs/DEPLOYMENT.md)
- [13 cloud security aspects mapped to code](docs/SECURITY.md)
- [Before/after analysis: load balancer and error handling](docs/LOAD_TEST.md)

## API (summary)
| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth/register`, `/login`, `/refresh` · GET `/me` | JWT access + refresh |
| GET/POST/PATCH/DELETE | `/api/subjects[/{id}]` | student only |
| GET/POST | `/api/documents?subject_id=` | upload is multipart (`subject_id`, `file`) |
| GET/DELETE | `/api/documents/{id}`, `/download`, `/reprocess` | presigned S3 link (5 min) |
| POST | `/api/chat/ask` | `{subject_id, question, session_id?, doc_ids?}` → answer + citations |
| POST | `/api/chat/search` | retrieval only, no LLM |
| GET/DELETE | `/api/chat/sessions`, `/sessions/{id}/messages` | chat history |
| GET | `/api/admin/stats`, `/users`, `/audit-logs` | admin only, no document content |
| GET | `/api/health` | ALB health check, returns the instance id |
