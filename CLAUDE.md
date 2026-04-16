# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Latte PR Agent is an Enterprise AI Code Review System that analyzes Pull/Merge Requests using multiple LLM providers. It receives webhook events from GitHub/GitLab, processes diffs through Celery workers, and publishes review comments back to the PR.

## Development Commands

### Setup
```bash
# Install dependencies
pip install -e ".[dev]"

# Setup environment
cp .env.example .env
# Edit .env with required API keys (GITHUB_TOKEN, DEEPSEEK_API_KEY, etc.)
```

### Run Services
```bash
# Start all services (Postgres with pgvector, Redis, FastAPI, Celery)
docker-compose up -d

# View logs
docker-compose logs -f webhook-server
docker-compose logs -f celery-worker

# Health check
curl http://localhost:8000/health
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_engine.py -v

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run async tests
pytest -v --asyncio-mode=auto
```

### Linting and Type Checking
```bash
# Format and lint
ruff check src tests
ruff format src tests

# Type checking
mypy src
```

### Database Migrations
```bash
# Run Alembic migrations (if using)
alembic upgrade head
```

## Architecture Overview

### Core Flow
1. **Webhook Reception** (`webhooks/router.py`): Receives GitHub/GitLab events, verifies signatures, creates review records
2. **Task Dispatch** (`tasks.py`): Celery task wrapper that calls `run_review()`
3. **Review Service** (`services/review_service.py`): Orchestrates the full pipeline:
   - Fetch PR diff from provider
   - Load project config (`.review-config.yml`)
   - Update dependency graph
   - Run `ReviewEngine`
   - Publish results via `ReviewPublisher`
4. **Review Engine** (`engine/review_engine.py`): Core logic:
   - Cache check → Context building → LLM review → Static analysis → Result merging → Persistence

### Key Modules

| Module | Purpose |
|--------|---------|
| `config/` | Pydantic-settings based configuration from env vars |
| `providers/` | GitHub/GitLab API abstraction via `GitProviderFactory` |
| `llm/` | LLM provider implementations (DeepSeek, Anthropic, Qwen) with `ResilientReviewRouter` for fallback |
| `engine/` | Core review logic: chunking, caching, deduplication, rule engine |
| `context/` | Project context building: API detection, cross-service analysis, dependency graphs |
| `rag/` | RAG retriever for similar bug lookup using pgvector |
| `graph/` | Dependency graph builder stored in PostgreSQL |
| `prompts/` | Prompt registry with A/B testing and auto-optimization |
| `feedback/` | Quality gates, metrics collection, PR comment publishing |
| `static/` | Semgrep integration for static analysis |
| `models/` | SQLAlchemy models: Review, Finding, BugKnowledge, etc. |
| `repositories/` | Data access layer |

### Dual-Model Verification
When `ENABLE_REASONER_REVIEW=true`, the system uses DeepSeek's fast model for initial review, then DeepSeek-R1 (reasoner) validates critical/warning issues automatically.

### Project Configuration
Repositories can define `.review-config.yml` at root:
```yaml
review_config:
  cross_service:
    enabled: true
    downstream_repos:
      - repo_id: org/service-b
        platform: github
  ai_model:
    primary: "claude-3-5-sonnet"  # Override default model
```

### Database Schema
- PostgreSQL with pgvector extension for embeddings
- Key tables: reviews, findings, file_dependencies, bug_knowledge, prompt_experiments
- See `sql/init.sql` for schema definition

### Environment Variables
Required: `DATABASE_URL`, `REDIS_URL`, at least one of `GITHUB_TOKEN`/`GITLAB_TOKEN`, at least one LLM API key.
See `.env.example` for full list.

### Testing Notes
- Tests use `aiosqlite` for in-memory async database
- `conftest.py` provides `client_with_db` fixture for FastAPI tests with DB override
- Mock external APIs using `respx` for HTTPX
- Integration tests use `testcontainers` for Postgres/Redis
