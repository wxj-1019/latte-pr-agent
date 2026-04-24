# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Latte PR Agent is an Enterprise AI Code Review System that analyzes Pull/Merge Requests using multiple LLM providers. It receives webhook events from GitHub/GitLab, processes diffs through Celery workers, publishes review comments back to the PR, and provides a Next.js dashboard for management. It also supports standalone Git project analysis (commit scanning + per-commit AI review).

## Development Commands

### Setup
```bash
# Backend
pip install -e ".[dev]"
cp .env.example .env  # Edit with required API keys

# Frontend
cd frontend && npm install
```

### Run Services
```bash
# Start all services (Postgres with pgvector, Redis, FastAPI, Celery)
docker-compose up -d

# Or run locally:
uvicorn src.main:app --reload                # Backend on :8000
celery -A tasks worker --loglevel=info       # Celery worker
cd frontend && npm run dev                   # Frontend on :3000

# Health check
curl http://localhost:8000/health
```

### Testing
```bash
pytest                          # All tests (asyncio_mode=auto in pyproject.toml)
pytest tests/test_engine.py -v  # Single file
pytest --cov=src --cov-report=term-missing

# Frontend
cd frontend && npm run lint
```

### Linting and Type Checking
```bash
ruff check src tests
ruff format src tests
mypy src                      # strict=true in pyproject.toml
```

### Database Migrations
```bash
alembic upgrade head
alembic revision --autogenerate -m "description"
```

## Architecture Overview

### Core Flow (PR Review)
1. **Webhook Reception** (`webhooks/router.py`): Receives GitHub/GitLab events, verifies signatures, creates review records
2. **Task Dispatch** (`tasks.py`): `run_review_task` Celery task calls `run_review()`
3. **Review Service** (`services/review_service.py`): Orchestrates full pipeline — fetch diff → load config → dependency graph → ReviewEngine → publish
4. **Review Engine** (`engine/review_engine.py`): Cache check → Context building → LLM review → Static analysis → Result merging → Persistence

### Core Flow (Project Analysis)
1. **Project Management** (`projects/router.py`): Add GitHub/GitLab repos, triggers background clone → git log scan → commit analysis
2. **Clone Task** (`tasks.py:clone_project_task`): Celery task that clones repo, scans git log, saves commits to DB
3. **Commit Analysis** (`commits/router.py`): Per-commit LLM review (`_do_analyze_commit`), batch analysis (`/analyze`), contributors stats
4. **SSE Progress** (`projects/router.py:/{id}/stream`): Server-Sent Events endpoint for real-time clone/sync/scan/analyze progress via `AnalysisProgressTracker`

### Key Modules

| Module | Purpose |
|--------|---------|
| `config/` | Pydantic-settings based configuration from env vars |
| `configs/` | Per-project config API (`/configs/*`) |
| `providers/` | GitHub/GitLab API abstraction via `GitProviderFactory` |
| `llm/` | LLM providers (DeepSeek, Anthropic, Qwen) with `ResilientReviewRouter` for fallback |
| `engine/` | Core review logic: chunking, caching, deduplication, rule engine |
| `context/` | Project context: API detection, cross-service analysis, dependency graphs |
| `rag/` | RAG retriever for similar bug lookup using pgvector |
| `graph/` | Dependency graph builder stored in PostgreSQL |
| `prompts/` | Prompt registry with A/B testing and auto-optimization |
| `feedback/` | Quality gates, metrics collection, PR comment publishing |
| `static/` | Semgrep integration for static analysis |
| `projects/` | Git repo management: add, clone, sync, delete, SSE progress streaming |
| `commits/` | Git log scanning, commit analysis via LLM, batch analysis, contributor stats |
| `settings/` | Admin settings management with API key auth, webhook configuration test endpoint |
| `reviews/` | Review API endpoints (`/reviews/*`) |
| `stats/` | Dashboard statistics API |
| `models/` | SQLAlchemy models: Review, Finding, BugKnowledge, ProjectRepo, CommitAnalysis, CommitFinding, etc. |
| `repositories/` | Data access layer |

### Frontend (`frontend/`)

Next.js 14 App Router dashboard with Tailwind CSS + Framer Motion. Key libraries: SWR (data fetching), Recharts (charts), Shiki (syntax highlighting).

Dashboard pages:
- `/dashboard` — Overview with stats
- `/dashboard/reviews` — PR review list, `/dashboard/reviews/[id]` — detail with diff viewer + findings
- `/dashboard/projects` — Project list, `/dashboard/projects/[id]` — project detail with commits & findings
- `/dashboard/analyze` — Code snippet analysis
- `/dashboard/metrics` — Review metrics charts
- `/dashboard/prompts` — Prompt version management
- `/dashboard/settings` — System settings (API keys, webhook config)
- `/dashboard/config` — Per-project `.review-config.yml` editor

API client at `frontend/src/lib/api.ts` wraps all backend endpoints. Admin-protected endpoints pass `X-API-Key` header from localStorage.

### Dual-Model Verification
When `ENABLE_REASONER_REVIEW=true`, the system uses DeepSeek's fast model for initial review, then DeepSeek-R1 (reasoner) validates critical/warning issues automatically.

### Admin API Key Pattern
The `/settings` endpoints require `X-API-Key` header matching `ADMIN_API_KEY` env var. Frontend stores this in `localStorage` under key `latte_admin_api_key` and sends it via `api.ts:getAdminApiKey()`.

### Project Configuration
Repositories can define `.review-config.yml` at root. See README.md for full schema including `cross_service`, `ai_model`, `custom_rules`, `dual_model_verification`.

### Database Schema
- PostgreSQL with pgvector extension for embeddings
- Key tables: `reviews`, `findings`, `file_dependencies`, `bug_knowledge`, `prompt_experiments`, `project_repos`, `commit_analyses`, `commit_findings`, `system_settings`
- See `sql/init.sql` for schema definition

### Environment Variables
Required: `DATABASE_URL`, `REDIS_URL`, at least one of `GITHUB_TOKEN`/`GITLAB_TOKEN`, at least one LLM API key.
See `.env.example` for full list.

### Testing Notes
- Tests use `aiosqlite` for in-memory async database
- `conftest.py` provides `client_with_db` fixture for FastAPI tests with DB override
- Mock external APIs using `respx` for HTTPX, `unittest.mock` for LLM/Git/Redis/Semgrep
- Integration tests use `testcontainers` for Postgres/Redis
