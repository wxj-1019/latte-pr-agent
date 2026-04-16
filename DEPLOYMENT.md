# Latte PR Agent 私有化部署指南

## 一、环境要求

- Docker Engine >= 24.0
- Docker Compose >= 2.20
- （可选）Kubernetes >= 1.28

## 二、快速启动（Docker Compose）

### 1. 配置环境变量

复制示例并填写真实密钥：

```bash
cp .env.example .env
# 编辑 .env，填入以下必填项：
# POSTGRES_PASSWORD
# GITHUB_TOKEN / GITLAB_TOKEN
# GITHUB_WEBHOOK_SECRET / GITLAB_WEBHOOK_SECRET
# DEEPSEEK_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY / QWEN_API_KEY
```

### 2. 启动服务

```bash
# 开发环境（带热重载）
docker-compose up -d

# 生产环境（多 worker、无热重载）
docker-compose -f docker-compose.prod.yml up -d
```

### 3. 验证健康检查

```bash
curl http://localhost:8000/health
```

### 4. 查看 Celery Worker 日志

```bash
docker-compose logs -f celery-worker
```

## 三、生产环境架构

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

## 四、Kubernetes 部署

### 1. 构建镜像并推送到仓库

```bash
docker build -t your-registry/latte-pr-agent:latest .
docker push your-registry/latte-pr-agent:latest
```

### 2. 修改镜像地址和密钥

```bash
# 编辑 k8s/secret.yaml，填入真实密钥
# 编辑 k8s/webhook-server.yaml 和 k8s/celery-worker.yaml 中的 image 字段
# 编辑 k8s/ingress.yaml 中的 host 字段
```

### 3. 应用资源

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/webhook-server.yaml
kubectl apply -f k8s/celery-worker.yaml
kubectl apply -f k8s/ingress.yaml
```

### 4. 水平扩展

```bash
# 扩展 Webhook 服务
kubectl scale deployment webhook-server --replicas=4 -n latte-pr-agent

# 扩展 Celery Worker
kubectl scale deployment celery-worker --replicas=6 -n latte-pr-agent
```

## 五、数据库初始化

首次部署时，PostgreSQL 会通过 `sql/init.sql` 自动建表。若需手动迁移：

```bash
# 进入 postgres 容器
kubectl exec -it deployment/postgres -n latte-pr-agent -- psql -U postgres -d code_review
```

## 六、Webhook 配置

### GitHub

1. 进入仓库 Settings > Webhooks > Add webhook
2. Payload URL: `https://latte.yourdomain.com/webhook/github`
3. Content type: `application/json`
4. Secret: 填写 `GITHUB_WEBHOOK_SECRET`
5. 选择 `Pull requests` 事件

### GitLab

1. 进入项目 Settings > Webhooks
2. URL: `https://latte.yourdomain.com/webhook/gitlab`
3. Secret Token: 填写 `GITLAB_WEBHOOK_SECRET`
4. 选择 `Merge request events`

## 七、Prompt A/B 测试与自动优化

系统已内置 Prompt Registry 和 Auto Prompt Optimizer：

- 查看 Prompt 版本：`GET /prompts/versions`
- 创建新版本：`POST /prompts/versions`
- 自动优化 Prompt：`POST /prompts/optimize`
- 查看按版本分组的指标：`GET /feedback/metrics/{repo_id}`

## 八、跨服务影响分析配置

在仓库根目录创建 `.review-config.yml`：

```yaml
review_config:
  cross_service:
    enabled: true
    downstream_repos:
      - repo_id: org/service-b
        platform: github
      - repo_id: org/service-c
        platform: github
```

## 九、监控与日志

- 健康检查：`GET /health`
- 反馈指标：`GET /feedback/metrics/{repo_id}`
- 建议接入 Prometheus + Grafana 监控 Celery Worker 队列深度和 Webhook 响应延迟。

## 十、环境变量清单

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `DATABASE_URL` | 是 | PostgreSQL async 连接串 |
| `SYNC_DATABASE_URL` | 是 | PostgreSQL sync 连接串 |
| `REDIS_URL` | 是 | Redis 连接串 |
| `GITHUB_TOKEN` | 否* | GitHub Personal Access Token |
| `GITLAB_TOKEN` | 否* | GitLab Access Token |
| `GITHUB_WEBHOOK_SECRET` | 否* | GitHub Webhook 签名密钥 |
| `GITLAB_WEBHOOK_SECRET` | 否* | GitLab Webhook 签名密钥 |
| `DEEPSEEK_API_KEY` | 否* | DeepSeek API Key |
| `ANTHROPIC_API_KEY` | 否* | Anthropic API Key |
| `OPENAI_API_KEY` | 否* | OpenAI API Key（用于 Embedding）|
| `QWEN_API_KEY` | 否* | 阿里云 DashScope API Key |
| `APP_ENV` | 否 | `development` / `production` |
| `LOG_LEVEL` | 否 | 日志级别 |
| `MAX_CONCURRENT_REVIEWS` | 否 | 最大并发审查数 |
| `ENABLE_REASONER_REVIEW` | 否 | 是否启用双模型复核 |

> *根据实际接入的平台和模型至少配置一组。
