# Latte PR Agent — AGENTS.md

> 本文档面向 AI Coding Agent，概括项目架构、技术栈、代码组织、构建测试流程及开发约定。
> 项目主要文档与代码注释使用中文，本文档同样使用中文撰写。

---

## 一、项目概述

**Latte PR Agent** 是一款企业级 AI 代码审查系统，基于 PR-Agent 理念构建。

核心能力：
- **双平台接入**：GitHub / GitLab Webhook 接收 PR/MR 事件。
- **多模型审查**：支持 DeepSeek (chat / reasoner)、Anthropic Claude、阿里云 Qwen 等模型，具备自动降级与双模型复核能力。
- **项目级上下文感知**：通过 Tree-sitter AST 解析构建文件依赖图，检测 API 契约变更，结合历史 Bug RAG 检索增强审查质量。
- **静态分析融合**：集成 Semgrep，将静态分析结果与 AI 审查结果合并、去重。
- **质量门禁与自定义规则**：支持 `.review-config.yml` 配置自定义规则、风险分级、阻塞合并。
- **反馈闭环**：开发者可对审查发现标记误报，系统据此统计指标并支持 Prompt A/B 测试与自动优化。

当前状态：Phase 1 (MVP) 已完成，Phase 2-3 的核心模块（AST、依赖图、RAG、静态分析、Celery 队列、Prompt 优化等）均已实现并通过测试。总计约 72 个自动化测试全部通过。

---

## 二、技术栈与运行时架构

### 2.1 技术栈

| 层级 | 技术 |
|------|------|
| 语言 | Python >= 3.11 |
| Web 框架 | FastAPI + Uvicorn |
| ORM / 数据库 | SQLAlchemy 2.0 (async) + asyncpg + PostgreSQL 16 + pgvector |
| 缓存 / 任务队列 | Redis + Celery |
| 静态分析 | Semgrep (通过 CLI 调用) |
| AST 解析 | tree-sitter + 各语言 grammar |
| LLM 客户端 | openai (DeepSeek), anthropic, dashscope (Qwen) |
| 部署 | Docker Compose / Kubernetes |
| 测试 | pytest + pytest-asyncio + aiosqlite + respx + testcontainers |
| 代码质量 | ruff (lint/format) + mypy (strict) |

### 2.2 运行时架构

```
GitHub/GitLab ──► Nginx / Ingress
                      │
           ┌──────────┴──────────┐
           ▼                     ▼
    webhook-server(N)      celery-worker(M)
    (FastAPI)              (Celery + Redis)
           │                     │
           └──────────┬──────────┘
                      ▼
              PostgreSQL + pgvector
                      ▼
                   Redis
```

- **webhook-server**：接收并校验 Webhook，将审查任务投递到 Celery；同时暴露 Feedback、Metrics、Prompt 管理 API。
- **celery-worker**：异步执行 `run_review_task`，完成拉取 diff → AST/依赖图分析 → LLM 审查 → 静态分析 → 结果合并 → 发布评论 → 设置 Status Check 的完整链路。
- **PostgreSQL**：主数据存储，含审查记录、发现项、Bug 知识库（向量）、文件依赖图、项目配置、Prompt 实验等。
- **Redis**：Celery Broker + Backend，以及审查缓存。

---

## 三、代码组织与模块划分

项目采用标准 Python `src/` 布局，所有业务代码位于 `src/`，测试位于 `tests/`。

```
src/
├── main.py                 # FastAPI 入口，注册 router，/health
├── config/                 # 配置模块
│   ├── __init__.py         # Pydantic Settings（.env 读取）
│   └── project_config.py   # .review-config.yml 解析 + ProjectConfigService
├── models/                 # SQLAlchemy 2.0 异步 ORM 模型
│   ├── base.py             # Async Base, engine, sessionmaker, get_db
│   ├── review.py           # Review, PRFile, ProjectConfig
│   ├── finding.py          # ReviewFinding, DeveloperFeedback
│   ├── bug_knowledge.py    # BugKnowledge (pgvector)
│   ├── file_dependency.py  # FileDependency
│   └── prompt_experiment.py# PromptExperiment, PromptExperimentAssignment
├── repositories/           # Async Repository 模式
│   ├── review_repo.py
│   └── finding_repo.py
├── providers/              # Git 平台适配层
│   ├── base.py             # GitProvider ABC
│   ├── github_provider.py  # PyGithub 封装
│   ├── gitlab_provider.py  # python-gitlab 封装
│   └── factory.py          # GitProviderFactory
├── webhooks/               # Webhook 接收与安全
│   ├── router.py           # /webhook/github & /webhook/gitlab
│   ├── verifier.py         # HMAC-SHA256 / Secret Token 校验
│   ├── parser.py           # payload 解析
│   └── rate_limiter.py     # PR 大小熔断
├── llm/                    # LLM 适配与路由
│   ├── base.py             # LLMProvider ABC
│   ├── deepseek.py         # DeepSeek 适配
│   ├── anthropic.py        # Claude 适配
│   ├── qwen.py             # Qwen 适配
│   ├── router.py           # ReviewRouter / ResilientReviewRouter
│   └── prompts/            # Prompt 模板
├── engine/                 # 审查引擎核心
│   ├── review_engine.py    # ReviewEngine：组装 prompt、调用 LLM、融合静态分析、持久化
│   ├── deduplicator.py     # CommentDeduplicator（按 review+file+line 去重）
│   ├── cache.py            # ReviewCache（Redis 缓存）
│   ├── chunker.py          # PRChunker（大 PR 分块）
│   └── rule_engine.py      # 自定义规则引擎（正则/pattern）
├── feedback/               # 评论发布与反馈
│   ├── formatter.py        # Markdown 三段式格式化
│   ├── publisher.py        # ReviewPublisher（调用 GitProvider 发布评论 + Status Check）
│   ├── quality_gate.py     # QualityGate / RiskAggregator
│   ├── metrics.py          # 指标统计
│   └── router.py           # Feedback API (/feedback/{finding_id})
├── code_ast/               # Tree-sitter AST 解析
│   ├── parser.py
│   ├── extractors.py       # 函数/类/Import 提取
│   └── languages.py        # 语言映射
├── graph/                  # 文件依赖图
│   ├── builder.py          # DependencyGraphBuilder
│   └── repository.py       # 图查询（递归 CTE）
├── context/                # 项目上下文构建
│   ├── builder.py          # ProjectContextBuilder（依赖风险、API 变更、RAG）
│   ├── api_detector.py     # API 契约变更检测
│   └── cross_service.py    # 跨服务影响分析
├── rag/                    # 历史 Bug 检索
│   ├── embedder.py         # EmbeddingClient (DeepSeek text-embedding-v3)
│   ├── repository.py       # BugKnowledgeRepository
│   ├── retriever.py        # RAGRetriever
│   └── builder.py          # BugKnowledgeBuilder (git log 扫描)
├── static/                 # 静态分析集成
│   ├── semgrep.py          # SemgrepAnalyzer
│   └── merger.py           # FindingMerger（AI + Static 结果合并）
├── prompts/                # Prompt 管理与优化
│   ├── registry.py         # PromptRegistry（版本管理、A/B 实验）
│   ├── optimizer.py        # Auto Prompt Optimizer
│   └── router.py           # Prompt API (/prompts/*)
├── services/               # 后台任务服务
│   └── review_service.py   # run_review() 完整 pipeline
└── tasks.py                # Celery app + run_review_task
```

---

## 四、构建与运行命令

### 4.1 本地开发环境

```bash
# 1. 创建虚拟环境
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 2. 安装依赖（含 dev 依赖）
pip install -e ".[dev]"

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，至少填写：
#   POSTGRES_PASSWORD, DATABASE_URL, REDIS_URL
#   GITHUB_TOKEN / GITLAB_TOKEN
#   GITHUB_WEBHOOK_SECRET / GITLAB_WEBHOOK_SECRET
#   DEEPSEEK_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY / QWEN_API_KEY

# 4. 启动服务
uvicorn src.main:app --reload
```

### 4.2 Docker Compose 启动

```bash
# 开发环境（带热重载、单 worker）
docker-compose up -d

# 生产环境（多 replica、多 Celery worker、带 nginx）
docker-compose -f docker-compose.prod.yml up -d
```

### 4.3 数据库迁移

项目使用 Alembic 做数据库迁移：

```bash
# 生成迁移脚本
alembic revision --autogenerate -m "描述"

# 执行迁移
alembic upgrade head
```

首次部署时，`sql/init.sql` 会被挂载到 PostgreSQL 容器的 `docker-entrypoint-initdb.d` 自动建表。

---

## 五、测试说明

### 5.1 运行全部测试

```bash
pytest tests/ -v
```

测试配置文件在 `pyproject.toml` 的 `[tool.pytest.ini_options]` 中：
- `asyncio_mode = "auto"`
- `testpaths = ["tests"]`
- `pythonpath = ["src"]`

### 5.2 测试策略与 fixture

- **内存数据库测试**：`tests/conftest.py` 提供 `async_db_session` fixture，使用 `sqlite+aiosqlite:///:memory:` 创建异步内存数据库，并自动建表/删表。
- **FastAPI TestClient 集成测试**：`client_with_db` fixture 通过 `app.dependency_overrides[get_db]` 注入内存 session，测试 Webhook、Feedback、Prompt API 等端点。
- **外部 API Mock**：LLM Provider、Git Provider、Redis、Semgrep 等外部依赖统一使用 `unittest.mock.AsyncMock` / `MagicMock` / `patch` 模拟，确保测试稳定、快速。
- **容器集成测试**：部分测试使用 `testcontainers` 启动真实 PostgreSQL / Redis 容器（如有需要）。

### 5.3 主要测试文件

| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_health.py` | `/health` 端点 |
| `test_models.py` | ORM 模型序列化与约束 |
| `test_repositories.py` | Repository CRUD、状态更新 |
| `test_providers.py` | GitHub/GitLab Provider Mock 测试 |
| `test_webhooks.py` | Webhook 签名校验、解析、熔断、集成 |
| `test_llm.py` | LLM Provider、ReviewRouter、ResilientReviewRouter |
| `test_engine.py` | ReviewEngine 缓存、去重、分块、静态分析融合 |
| `test_feedback.py` | Feedback API、Publisher |
| `test_context.py` | ProjectContextBuilder |
| `test_static.py` | Semgrep 解析、FindingMerger |
| `test_graph.py` | 依赖图构建与查询 |
| `test_rag.py` | RAG 检索与 Repository |
| `test_celery.py` | Celery 任务分发 |
| `test_e2e_phase2.py` | 端到端链路 |
| `test_quality_gate.py` | QualityGate 风险分级 |
| `test_rule_engine.py` | 自定义规则引擎 |
| `test_metrics.py` | 指标统计 |
| `test_project_config.py` | 项目配置解析与持久化 |

---

## 六、代码风格与开发约定

### 6.1 格式化与类型检查

- **ruff**：行宽 `100`，目标 Python 版本 `3.11`。
- **mypy**：启用 `strict = true`。

```bash
# 格式化与 lint
ruff check src tests
ruff format src tests

# 类型检查
mypy src
```

### 6.2 编码约定

1. **异步优先**：所有 I/O 操作（数据库、HTTP、Git 平台 API）均使用 `async/await`。SQLAlchemy 使用 `AsyncSession` + `create_async_engine`。
2. **Repository 模式**：数据库访问统一封装到 `repositories/` 目录，Service/Engine 层不直接写 SQL。
3. **抽象基类**：可替换组件（`GitProvider`、`LLMProvider`）必须继承 ABC，便于 Mock 测试和后续扩展。
4. **结构化日志**：统一使用 `logging.getLogger(__name__)`，避免 `print`。
5. **配置管理**：运行时配置统一通过 `config.settings`（Pydantic Settings）读取，支持 `.env` 文件；项目级配置通过 `.review-config.yml` 定义，由 `ProjectConfigLoader` 解析。
6. **异常处理**：对外部依赖（LLM、Git 平台、Semgrep）的调用必须包裹异常捕获，并记录 `logger.warning` 或 `logger.exception`，避免单点故障拖垮整个审查流程。
7. **安全**：
   - Webhook 签名比较使用 `secrets.compare_digest`（已替换 `hmac.compare_digest` 的过时写法，消除时序攻击）。
   - 所有 Token、Secret 通过环境变量注入，不硬编码。

### 6.3 模块导入风格

- 在 `src/` 内部使用绝对导入（如 `from models import get_db`、`from engine import ReviewEngine`），因为 `PYTHONPATH` 已设置为 `src/`。
- 模型层在 `models/__init__.py` 统一导出，方便外部使用。

---

## 七、安全注意事项

1. **Webhook Secret**：GitHub 使用 `X-Hub-Signature-256` (HMAC-SHA256)，GitLab 使用 `X-Gitlab-Token` 明文比对。校验逻辑在 `src/webhooks/verifier.py`，务必使用 `secrets.compare_digest`。
2. **环境变量**：生产环境 `.env` 文件不可提交到仓库（已在 `.gitignore` 中排除）。
3. **数据库连接池**：`models/base.py` 已显式配置连接池参数（`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`, `pool_recycle=3600`）。
4. **降级与熔断**：
   - `ResilientReviewRouter` 在模型全部不可用时返回 `degraded=True`，仅展示静态分析结果，避免审查流程完全中断。
   - `RateLimiter` 对超大 PR（>500 文件）自动熔断并标记 `skipped`。
5. **SQL 注入防范**：所有数据库查询通过 SQLAlchemy ORM / 参数化 SQL 完成，不拼接用户输入到 SQL 字符串。

---

## 八、部署与扩展

### 8.1 Docker Compose 部署

- `docker-compose.yml`：开发环境，单 webhook-server + postgres + redis + celery-worker。
- `docker-compose.prod.yml`：生产环境，webhook-server 和 celery-worker 均配置 `deploy.replicas` 与资源限制，并前置 `nginx` 负载均衡。

### 8.2 Kubernetes 部署

`k8s/` 目录包含完整 manifests：

```
k8s/
├── namespace.yaml
├── secret.yaml          # 存放各类 Token/Secret
├── configmap.yaml
├── postgres.yaml
├── redis.yaml
├── webhook-server.yaml  # FastAPI Deployment + Service
├── celery-worker.yaml   # Celery Deployment
└── ingress.yaml         # Nginx Ingress
```

水平扩展命令：

```bash
kubectl scale deployment webhook-server --replicas=4 -n latte-pr-agent
kubectl scale deployment celery-worker --replicas=6 -n latte-pr-agent
```

### 8.3 仓库级配置

在目标仓库根目录放置 `.review-config.yml`，可启用跨服务影响分析、自定义规则、指定模型等：

```yaml
review_config:
  language: python
  context_analysis:
    enabled: true
    dependency_depth: 2
    historical_bug_check: true
    api_contract_detection: true
  critical_paths:
    - src/payment/
    - src/auth/
  custom_rules:
    - name: "禁止控制器直接调用 DB"
      pattern: "*/controllers/*"
      forbidden: "*/db/*"
      message: "控制器层不应直接访问数据库"
      severity: warning
  ai_model:
    primary: deepseek-chat
    fallback: deepseek-reasoner
  dual_model_verification:
    enabled: true
    trigger_on: [critical, warning]
  cross_service:
    enabled: true
    downstream_repos:
      - repo_id: org/service-b
        platform: github
```

---

## 九、常用参考路径

| 文件/目录 | 说明 |
|-----------|------|
| `pyproject.toml` | Python 依赖、pytest/ruff/mypy 配置 |
| `.env.example` | 环境变量模板 |
| `sql/init.sql` | PostgreSQL 初始化脚本（含 pgvector 扩展、索引） |
| `docs/implementation-guide.md` | Phase 1~3 完整实现指南与测试方案 |
| `DEPLOYMENT.md` | 私有化部署详细指南 |
| `src/main.py` | FastAPI 入口 |
| `src/tasks.py` | Celery 配置与任务定义 |
| `src/services/review_service.py` | 审查完整 pipeline 入口 |

---

*文档生成时间：2026-04-16*  
*基于项目实际代码与配置编写，供 AI Agent 快速理解项目使用。*
