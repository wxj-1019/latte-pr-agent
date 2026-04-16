# Latte PR Agent

企业级 AI 代码审查系统，基于多 LLM 架构的智能 PR 审查平台。

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

## 功能特性

- **双平台接入**：支持 GitHub / GitLab Webhook 接入
- **多模型支持**：DeepSeek、Anthropic Claude、阿里云 Qwen 等多种 LLM 提供商
- **双模型复核**：DeepSeek-V3 快速初筛 + DeepSeek-R1 深度复核高风险问题
- **智能降级**：多模型降级链，确保服务高可用
- **项目级上下文**：
  - 文件依赖图分析（支持递归 CTE 查询上下游调用链）
  - API 契约变更检测
  - 历史 Bug RAG 检索（基于 pgvector）
- **静态分析融合**：Semgrep 与 AI 审查结果智能合并
- **质量门禁**：Critical 风险自动阻塞合并
- **企业级扩展**：Celery 异步任务队列，支持水平扩展

## 快速开始

### 环境要求

- Python >= 3.11
- Docker >= 24.0
- Docker Compose >= 2.20

### 1. 克隆项目并配置环境

```bash
git clone <repository-url>
cd latte-pr-agent

# 复制环境变量模板
cp .env.example .env
# 编辑 .env 填入必要配置（见下方配置说明）
```

### 2. Docker 一键启动（推荐）

```bash
# 开发环境（带热重载）
docker-compose up -d

# 生产环境（多 worker、无热重载）
docker-compose -f docker-compose.prod.yml up -d
```

### 3. 验证服务

```bash
# 健康检查
curl http://localhost:8000/health

# 查看 Celery Worker 日志
docker-compose logs -f celery-worker
```

### 4. 配置 Webhook

#### GitHub

1. 进入仓库 **Settings > Webhooks > Add webhook**
2. Payload URL: `https://your-domain.com/webhook/github`
3. Content type: `application/json`
4. Secret: 填写 `.env` 中的 `GITHUB_WEBHOOK_SECRET`
5. 选择 **Pull requests** 事件

#### GitLab

1. 进入项目 **Settings > Webhooks**
2. URL: `https://your-domain.com/webhook/gitlab`
3. Secret Token: 填写 `.env` 中的 `GITLAB_WEBHOOK_SECRET`
4. 选择 **Merge request events**

## 配置说明

编辑 `.env` 文件，配置以下必填项：

```env
# Database（必须）
POSTGRES_PASSWORD=your_secure_password
DATABASE_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@localhost:5432/code_review
SYNC_DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@localhost:5432/code_review

# Redis（必须）
REDIS_URL=redis://localhost:6379/0

# GitHub（如使用 GitHub）
GITHUB_TOKEN=ghp_xxxxxxxx
GITHUB_WEBHOOK_SECRET=your_github_webhook_secret

# GitLab（如使用 GitLab）
GITLAB_TOKEN=glpat-xxxxxxxx
GITLAB_WEBHOOK_SECRET=your_gitlab_webhook_secret
GITLAB_URL=https://gitlab.com

# LLM API Keys（至少配置一个）
DEEPSEEK_API_KEY=sk-xxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxx
QWEN_API_KEY=sk-xxxxxxxx

# 应用配置（可选）
APP_ENV=development
LOG_LEVEL=INFO
MAX_CONCURRENT_REVIEWS=20
ENABLE_REASONER_REVIEW=false  # 是否启用双模型复核
```

### 项目级配置

在仓库根目录创建 `.review-config.yml`，自定义审查行为：

```yaml
review_config:
  # 跨服务影响分析
  cross_service:
    enabled: true
    downstream_repos:
      - repo_id: org/service-b
        platform: github

  # AI 模型覆盖
  ai_model:
    primary: "claude-3-5-sonnet"

  # 自定义规则（示例）
  custom_rules:
    - name: "禁止控制器直接调用数据库"
      pattern: "class.*Controller.*:.*\\n.*db\\.query"
      severity: "warning"
      message: "控制器层应通过 Service 访问数据库"
```

## 部署架构

```
                    ┌─────────────┐
    GitHub/GitLab ──►│   Nginx     │◄── 外部负载均衡
                     └──────┬──────┘
                            │
              ┌─────────────┴─────────────┐
              │                             │
       ┌──────▼──────┐              ┌──────▼──────┐
       │ webhook-1   │              │ webhook-2   │
       └──────┬──────┘              └──────┬──────┘
              │                             │
              └─────────────┬───────────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
       ┌──────▼──────┐ ┌────▼─────┐ ┌────▼─────┐
       │ Celery-1    │ │ Celery-2 │ │ Celery-N │
       └──────┬──────┘ └────┬─────┘ └────┬─────┘
              │             │            │
              └─────────────┴────────────┘
                            │
                   ┌────────▼────────┐
                   │  Redis (Broker) │
                   └─────────────────┘
                            │
              ┌─────────────┴─────────────┐
              │                             │
       ┌──────▼──────┐              ┌──────▼──────┐
       │ PostgreSQL  │              │  pgvector   │
       │  (主数据)    │              │  (向量检索)  │
       └─────────────┘              └─────────────┘
```

### Kubernetes 部署

```bash
# 构建镜像
docker build -t your-registry/latte-pr-agent:latest .
docker push your-registry/latte-pr-agent:latest

# 修改配置后应用
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/webhook-server.yaml
kubectl apply -f k8s/celery-worker.yaml
kubectl apply -f k8s/ingress.yaml

# 水平扩展
kubectl scale deployment webhook-server --replicas=4 -n latte-pr-agent
kubectl scale deployment celery-worker --replicas=6 -n latte-pr-agent
```

## API 端点

### Webhook 接收

| 端点 | 方法 | 描述 |
|------|------|------|
| `/webhook/github` | POST | GitHub Webhook 接收 |
| `/webhook/gitlab` | POST | GitLab Webhook 接收 |

### 反馈与指标

| 端点 | 方法 | 描述 |
|------|------|------|
| `/feedback/{finding_id}` | POST | 标记误报 |
| `/feedback/metrics/{repo_id}` | GET | 获取仓库审查指标 |

### Prompt 管理

| 端点 | 方法 | 描述 |
|------|------|------|
| `/prompts/versions` | GET | 列出 Prompt 版本 |
| `/prompts/versions` | POST | 创建新 Prompt 版本 |
| `/prompts/optimize` | POST | 自动优化 Prompt |

### 健康检查

| 端点 | 方法 | 描述 |
|------|------|------|
| `/health` | GET | 服务健康状态 |

## 开发指南

### 本地开发环境

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/ -v

# 运行单个测试文件
pytest tests/test_engine.py -v

# 代码检查
ruff check src tests
ruff format src tests

# 类型检查
mypy src

# 启动开发服务器
uvicorn src.main:app --reload
```

### 数据库迁移

```bash
# 创建迁移
alembic revision --autogenerate -m "描述"

# 应用迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

### 项目结构

```
latte-pr-agent/
├── src/
│   ├── main.py              # FastAPI 入口
│   ├── tasks.py             # Celery 任务
│   ├── config/              # 配置管理
│   ├── engine/              # 审查引擎核心
│   ├── llm/                 # LLM 适配层
│   ├── providers/           # Git 平台适配
│   ├── webhooks/            # Webhook 接收
│   ├── context/             # 项目上下文构建
│   ├── graph/               # 依赖图构建
│   ├── rag/                 # RAG 检索
│   ├── static/              # 静态分析
│   ├── feedback/            # 反馈与发布
│   ├── prompts/             # Prompt 管理
│   ├── models/              # ORM 模型
│   └── repositories/        # 数据访问层
├── tests/                   # 测试目录
├── sql/                     # 数据库初始化
├── k8s/                     # Kubernetes 配置
├── docs/                    # 项目文档
└── prompts/                 # Prompt 模板
```

## 项目状态

| 阶段 | 功能 | 状态 |
|------|------|------|
| **Phase 1** | MVP 基础功能 | ✅ 已完成 (57 测试通过) |
| | - Webhook 接收与安全校验 | ✅ |
| | - GitHub/GitLab Provider | ✅ |
| | - DeepSeek/Claude/Qwen LLM | ✅ |
| | - Review Engine + Cache | ✅ |
| | - 评论发布与反馈闭环 | ✅ |
| **Phase 2** | 智能增强 | ✅ 已完成 |
| | - Tree-sitter AST 解析 | ✅ |
| | - 文件依赖图构建 | ✅ |
| | - 项目上下文构建器 | ✅ |
| | - pgvector RAG 系统 | ✅ |
| | - Semgrep 静态分析 | ✅ |
| **Phase 3** | 企业级扩展 | ✅ 已完成 |
| | - 风险分级与质量门禁 | ✅ |
| | - 自定义规则引擎 | ✅ |
| | - Celery 异步队列 | ✅ |
| | - Prompt A/B 测试 | ✅ |

**当前测试覆盖**：72+ 个测试全部通过

## 文档

- [部署指南](DEPLOYMENT.md) - 详细部署配置与架构说明
- [实现指南](docs/implementation-guide.md) - 完整实现方案与测试策略
- [CLAUDE.md](CLAUDE.md) - Claude Code 开发指南

## 许可证

[MIT License](LICENSE)

---

*Latte PR Agent - 让 AI 成为每个团队的代码审查专家*
