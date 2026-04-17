# Latte PR Agent — 安全与代码质量审查报告

> **审查日期**：2026-04-18  
> **审查范围**：全栈（后端 Python/FastAPI、前端 Next.js、K8s 部署、Docker 配置、测试与 CI）  
> **审查结论**：功能框架已成型，但存在**高危安全漏洞**和**关键代码缺陷**，不建议直接投入生产。  
> **涉及文件**：~40 个源文件  
> **发现问题**：共 45+ 项（含高危 10 项、中危 15+ 项、低危/改进 20 项）

---

## 一、执行摘要

| 维度 | 评分 | 状态说明 |
|------|:----:|----------|
| 功能完整性 | ⭐⭐⭐⭐ | Phase 1~3 核心能力均已实现，136 个自动化测试通过 |
| 代码健壮性 | ⭐⭐⭐ | 竞态条件、事务原子性破坏、子进程泄漏、异常处理缺失 |
| 安全性 | ⭐⭐ | 存在高危配置漏洞、API 无认证、部署暴露敏感端口 |
| 可运维性 | ⭐⭐ | 无监控指标、无审计日志、健康检查不完整、K8s 安全加固缺失 |

**核心风险**：
1. **CORS 默认配置极度危险**：`allow_origins=["*"]` + `allow_credentials=True`，任何恶意网站均可跨域伪造请求。
2. **数据库/Redis 端口直接暴露宿主机**：配合默认弱密码，可被外部扫描破解。
3. **全站无 HTTPS**：所有 Token、Secret、Webhook 凭证明文传输。
4. **管理后台 API 完全无认证**：任何人可访问/修改审查记录、Prompt、项目配置。
5. **关键代码缺陷**：竞态条件导致重复数据、事务边界混乱、子进程泄漏、路径遍历漏洞。

---

## 二、高危漏洞（P0 — 立即修复）

### P0-1：CORS 配置允许任意来源且携带凭证

- **风险等级**：🔴 **高危**  
- **涉及文件**：
  - `src/config/__init__.py` — `cors_origins: str = "*"`
  - `src/main.py` — `allow_credentials=True`, `allow_origins=["*"]`
- **问题描述**：默认配置下，FastAPI 允许任意跨域来源访问，且允许携带 Cookie/凭证。这违反了 CORS 安全规范，使系统完全暴露在跨域请求伪造（CSRF 绕过）风险下。
- **攻击场景**：攻击者构造恶意网页，诱导已登录管理员访问，即可通过浏览器自动携带的 Cookie 调用 `/prompts/*`、`/configs/*` 等管理接口。
- **修复建议**：
  - 生产环境 `CORS_ORIGINS` 必须配置为明确的域名白名单（如 `https://dashboard.example.com`）
  - 禁止 `*` 与 `allow_credentials=True` 共存
  - 增加启动时断言：若 `app_env == "production"` 且 `cors_origins == "*"`，直接拒绝启动

---

### P0-2：Docker Compose 直接暴露数据库/Redis 端口

- **风险等级**：🔴 **高危**  
- **涉及文件**：
  - `docker-compose.yml` — `5432:5432`, `6379:6379`
  - `docker-compose.prod.yml` — `5432:5432`, `6379:6379`
- **问题描述**：开发环境和生产环境编排文件均将 PostgreSQL 和 Redis 映射到宿主机所有接口。配合默认弱密码 `postgres`，外部扫描工具可在数分钟内完成暴力破解。
- **修复建议**：
  - 删除 `docker-compose.prod.yml` 中的端口映射，服务通过 Docker 内部网络通信
  - 开发环境若必须映射，应绑定 `127.0.0.1`（如 `127.0.0.1:5432:5432`）
  - 移除默认密码回退（`${POSTGRES_PASSWORD:-postgres}`），强制要求环境变量

---

### P0-3：生产环境无 HTTPS，全站明文传输

- **风险等级**：🔴 **高危**  
- **涉及文件**：
  - `nginx.conf`
  - `docker-compose.prod.yml` — 仅暴露 `80:80`
  - `k8s/ingress.yaml`
- **问题描述**：Nginx 和 Ingress 仅配置 HTTP（80 端口），未配置 443 及 SSL/TLS 证书。所有 Webhook Secret、GitHub/GitLab Token、用户凭证、AI 生成的代码审查内容均在公网明文传输，完全丧失机密性和完整性保护。
- **修复建议**：
  - `nginx.conf` 增加 443 监听和 SSL 证书配置
  - 80 端口配置强制 301 跳转至 HTTPS
  - 增加 `ssl_protocols TLSv1.2 TLSv1.3; ssl_prefer_server_ciphers on;`
  - K8s Ingress 增加证书 Secret 引用和 HSTS 注解

---

### P0-4：管理后台 API 完全无认证/授权

- **风险等级**：🔴 **高危**  
- **涉及文件**：
  - `src/main.py` — 所有 router 注册
  - `src/reviews/router.py`
  - `src/prompts/router.py`
  - `src/configs/router.py`
  - `src/feedback/router.py`
  - `src/stats/router.py`
- **问题描述**：除 Webhook 端点外，所有 REST API（包括审查记录查询、Prompt 管理、配置修改、统计报表、Feedback 提交）均未设置任何身份校验依赖。任何人只需知道 URL 即可访问和修改全部数据。
- **修复建议**：
  - 为管理后台 API 增加 API Key（`X-API-Key` Header）或 OAuth2/JWT 认证依赖
  - 在 FastAPI 路由分组层面统一挂载 `Depends(verify_api_key)`
  - 区分只读和读写权限，防止低权限 Key 修改 Prompt/配置

---

### P0-5：Webhook 端点无限流，存在 DoS 风险

- **风险等级**：🔴 **高危**  
- **涉及文件**：
  - `src/webhooks/router.py` — `/webhook/github`, `/webhook/gitlab`
  - `src/main.py` — `slowapi` 引入但未覆盖 Webhook
- **问题描述**：Webhook 接收端点未配置任何速率限制。攻击者即使不知道 Secret，也可以发送海量伪造请求，触发 HMAC 计算、签名验证、PR 解析等逻辑，迅速耗尽：
  - FastAPI Worker 连接池
  - Celery Broker 队列积压
  - LLM API 调用配额与费用
  - 数据库连接资源
- **修复建议**：
  - 为 Webhook 端点增加基于 IP 的限速（如 `60/minute` per IP）
  - 增加基于仓库的限速（如 `30/minute` per repo）
  - Nginx 层面增加 `limit_req_zone` 作为第二层防护
  - 超大 Payload 直接拒绝（已在 `rate_limiter.py` 中实现 PR 大小熔断，但请求频率层面缺失）

---

### P0-6：Semgrep 路径拼接存在路径遍历漏洞

- **风险等级**：🔴 **高危**  
- **涉及文件**：`src/static/semgrep.py` — 第 16 行
- **问题描述**：代码直接拼接路径：`f"{repo_path}/{f}"`，其中 `f` 来自外部传入的 `changed_files` 列表，未做校验。恶意 payload（如 `../../../etc/passwd`）可导致 semgrep 扫描任意系统文件。
- **修复建议**：
  - 使用 `pathlib.Path(repo_path) / f` 拼接后，通过 `path.resolve()` 校验是否在 repo 目录内
  - 拒绝包含 `..` 或绝对路径（`/` 或 `C:\`）的文件名
  - 使用 `os.path.commonpath` 做最终校验

---

### P0-7：生产环境以开发模式运行

- **风险等级**：🔴 **高危**  
- **涉及文件**：`docker-compose.yml` — `command: uvicorn main:app ... --reload`
- **问题描述**：Docker Compose 开发文件使用 `--reload`，且未在 `docker-compose.prod.yml` 中覆盖。若误用开发文件部署生产，文件监控器会增加攻击面（可被利用触发未预期代码重载）。
- **修复建议**：
  - `docker-compose.yml` 删除 `--reload`，仅保留 `uvicorn main:app --host 0.0.0.0 --port 8000`
  - 开发热重载通过单独 `docker-compose.override.yml` 或 `docker-compose.dev.yml` 实现

---

### P0-8：GitLab Provider 完全无异常处理

- **风险等级**：🔴 **高危**  
- **涉及文件**：`src/providers/gitlab_provider.py`
- **问题描述**：所有方法（`__init__`、`get_diff_content`、`publish_review_comment`、`set_status_check`）均未 try-except。任何网络抖动、GitLab API 变更、权限不足、MR 关闭等情况都会导致整个审查 pipeline 崩溃，且无任何日志记录。
- **修复建议**：
  - 参照 `github_provider.py` 的结构，为所有外部调用增加异常捕获和日志
  - 网络类异常应触发降级（仅展示静态分析结果），而非直接失败

---

### P0-9：子进程泄漏（Semgrep 超时未清理）

- **风险等级**：🔴 **高危**  
- **涉及文件**：`src/static/semgrep.py` — 第 19~30 行
- **问题描述**：`asyncio.wait_for(proc.communicate(), timeout=120)` 超时后仅返回 `[]`，未调用 `proc.kill()`。semgrep 进程可能继续后台运行成为僵尸进程，长期运行会耗尽系统 PID 和内存资源。
- **修复建议**：
  ```python
  try:
      stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
  except asyncio.TimeoutError:
      proc.kill()
      await proc.wait()
      logger.warning("Semgrep 超时，进程已强制终止")
      return []
  ```

---

### P0-10：缺少 CI/CD 流水线与安全扫描

- **风险等级**：🔴 **高危**  
- **涉及文件**：项目根目录（`.github/workflows/` 不存在）
- **问题描述**：项目完全缺失 CI/CD 工作流。没有自动化测试、Lint、类型检查、构建验证、依赖漏洞扫描。代码合并无法保证质量基线。
- **修复建议**：
  - 创建 `.github/workflows/ci.yml`，包含：`pytest`、`ruff check`、`mypy`、`docker build`
  - 引入 `pip-audit` / `safety` / `snyk` 扫描 Python 依赖漏洞
  - 前端增加 `npm audit` 和 `npm run build` 校验
  - CI 中运行 Semgrep 规则集扫描项目自身源代码（SAST）

---

## 三、关键代码缺陷（P1 — 1~2周内修复）

### P1-1：竞态条件导致重复数据（TOCTOU）

- **风险等级**：🟠 **关键**  
- **涉及文件**：`src/engine/review_engine.py` — `CommentDeduplicator.should_comment()`
- **问题描述**：先 `SELECT` 查询是否已存在，再决定是否 `INSERT`。多个 Celery Worker 并发处理同一 review 时，查询窗口期内可能同时返回 `True`，导致相同位置的 finding 被重复持久化。
- **修复建议**：
  - 数据库层面增加唯一约束/索引：`UNIQUE(review_id, file_path, line_number, message_hash)`
  - 插入逻辑改为 `INSERT ... ON CONFLICT DO NOTHING`，用数据库原子性保证去重

---

### P1-2：事务边界混乱，破坏原子性

- **风险等级**：🟠 **关键**  
- **涉及文件**：
  - `src/services/review_service.py` — 多处 commit
  - `src/repositories/finding_repo.py` — 内部自行 commit
  - `src/repositories/review_repo.py` — 内部自行 commit
- **问题描述**：`FindingRepository.create()` 和 `ReviewRepository.update_status()` 在方法内部自行调用 `session.commit()`。当它们在 `session.begin()` 事务块内被调用时，会导致**嵌套提交**，破坏事务原子性。若后续步骤失败，已持久化的 finding 无法回滚。
- **修复建议**：
  - **Repository 层禁止自行 commit**，所有数据库写操作仅执行 SQL/ORM 语句
  - 由 Service/Engine 层通过上下文管理器统一控制事务边界
  - 需要独立提交的状态更新，应在 Service 层显式控制，而非隐藏在 Repository 内部

---

### P1-3：异常日志泄露敏感连接信息

- **风险等级**：🟠 **关键**  
- **涉及文件**：`src/webhooks/router.py` — `_dispatch_review()`
- **问题描述**：`except Exception as exc` 后直接 `logging.warning(f"...{exc}...")`。如果 Celery/Redis 连接异常信息中包含 Broker URL（含密码）或其他敏感配置，将被写入日志系统，导致凭证泄露。
- **修复建议**：
  - 实现 `SensitiveDataFilter(logging.Filter)`，用正则脱敏日志中的 API Key、Token、密码、数据库连接串
  - 对 `settings` 中的敏感字段使用 Pydantic `SecretStr` 类型，防止意外序列化

---

### P1-4：GitHub Provider 发布方法零异常保护

- **风险等级**：🟠 **关键**  
- **涉及文件**：`src/providers/github_provider.py` — `publish_review_comment`, `set_status_check`
- **问题描述**：向 GitHub API 发布评论和状态检查的方法完全未 try-except。权限不足、行号越界、PR 已关闭等情况都会导致整个审查流程中断。
- **修复建议**：为所有外部 API 调用增加异常捕获，记录 warning 日志后继续流程（不可因评论发布失败而丢弃审查结果）。

---

### P1-5：缓存空值误判

- **风险等级**：🟠 **关键**  
- **涉及文件**：`src/engine/review_engine.py` — 第 74 行
- **问题描述**：`if cached:` 会把空字典 `{}`、空列表 `[]`、空字符串 `""` 误判为无缓存，导致缓存失效。
- **修复建议**：改为 `if cached is not None:`

---

### P1-6：LLM 路由修改入参字典

- **风险等级**：🟠 **关键**  
- **涉及文件**：`src/llm/router.py` — `_merge_results()`
- **问题描述**：`primary["issues"] = merged_issues` 直接修改传入的 `primary` 字典，调用方若复用该对象会被意外污染。
- **修复建议**：先 `copy.deepcopy(primary)` 再修改，或返回新字典

---

### P1-7：GitHub Provider 未捕获 HTTPStatusError

- **风险等级**：🟠 **关键**  
- **涉及文件**：`src/providers/github_provider.py` — `get_diff_content()`
- **问题描述**：只捕获了 `TimeoutException` 和 `NetworkError`，但 `httpx.raise_for_status()` 抛出的 `HTTPStatusError`（4xx/5xx）未被捕获。
- **修复建议**：增加 `except httpx.HTTPStatusError` 分支处理

---

### P1-8：`reviews/analyze` 端点文件名净化可绕过

- **风险等级**：🟠 **关键**  
- **涉及文件**：`src/reviews/router.py`
- **问题描述**：`req.filename.replace("..", "")` 可被绕过。例如 `....//` → 第一次替换为 `../` → 仍包含路径遍历。
- **修复建议**：使用 `pathlib.Path(req.filename).name` 提取纯文件名，或拒绝任何包含 `/` 或 `\` 的输入

---

### P1-9：Redis 未认证暴露（生产环境）

- **风险等级**：🟠 **关键**  
- **涉及文件**：`docker-compose.prod.yml`, `k8s/redis.yaml`
- **问题描述**：Redis 默认无密码或弱密码，且端口被映射/暴露，可被利用写入恶意数据、作为跳板或触发 RCE（历史版本 Redis 存在相关漏洞）。
- **修复建议**：
  - 配置 `requirepass` 或启用 Redis ACL
  - 生产环境 Redis 不暴露宿主机端口，仅通过 ClusterIP Service 访问
  - K8s 中增加 NetworkPolicy 限制仅 webhook-server 和 celery-worker 可访问 Redis

---

### P1-10：Celery 回退机制引入 DoS 风险

- **风险等级**：🟠 **关键**  
- **涉及文件**：`src/webhooks/router.py` — `_dispatch_review()`
- **问题描述**：当 Celery 不可用时，回退到 `background_tasks.add_task(run_review, review_id)`。若攻击者持续发送请求且 Celery 持续不可用，所有审查任务将在 FastAPI 工作进程内同步执行，迅速耗尽资源导致服务瘫痪。
- **修复建议**：
  - 回退模式增加熔断开关和并发限制（如最多同时执行 2 个回退任务）
  - 或干脆拒绝服务（返回 503），提示"队列繁忙，请稍后重试"

---

## 四、架构与运维缺陷（P2 — 1个月内修复）

### P2-1：健康检查端点未检查下游依赖

- **风险等级**：🟡 **中危**  
- **涉及文件**：`src/main.py` — `/health`
- **问题描述**：`/health` 仅返回 `{"status": "ok", "env": "production"}`，未检查 PostgreSQL、Redis、Celery Broker、pgvector 扩展是否可用。
- **修复建议**：
  - 拆分探针：
    - `/live` — 纯进程存活（200/204）
    - `/ready` — 检查 `SELECT 1`、Redis `PING`、pgvector 扩展存在性
  - K8s 中 `livenessProbe` → `/live`，`readinessProbe` → `/ready`
  - Celery Worker 增加 readinessProbe（检查 worker 是否已注册到 broker）

---

### P2-2：完全缺失监控与可观测性

- **风险等级**：🟡 **中危**  
- **涉及文件**：全局
- **问题描述**：
  - 无 Prometheus `/metrics` 端点
  - 无分布式 Tracing（OpenTelemetry/Jaeger）
  - 无结构化日志（JSON Formatter），不利于 Loki/ELK 解析
  - 日志中无 `trace_id`、`review_id` 等关联字段
  - 无业务指标（review 吞吐量、P99 延迟、LLM 成功率、feedback 误报率）
- **修复建议**：
  - 引入 `prometheus-fastapi-instrumentator`，暴露 RED 指标
  - 自定义业务指标：`review_total`、`review_duration_seconds`、`llm_calls_total`、`llm_fallback_total`
  - 使用 `structlog` 或自定义 JSON Formatter，统一注入 `request_id`
  - Celery 配置 Prometheus exporter 或 Flower

---

### P2-3：完全缺失审计日志

- **风险等级**：🟡 **中危**  
- **涉及文件**：全局（Webhook、Feedback、Prompt、Config API）
- **问题描述**：关键操作均未记录审计轨迹：
  - Webhook 接收（来源 IP、User-Agent、事件类型、签名验证结果）
  - Feedback 提交（提交者身份、IP、时间、变更内容）
  - Prompt/Config 更新（谁在什么时间修改了什么）
  - Review 状态流转（缺少状态变更日志表）
- **修复建议**：
  - 新增 `audit_logs` 表（`id`, `action`, `resource_type`, `resource_id`, `actor_ip`, `actor_identity`, `payload`, `timestamp`）
  - 开发 `AuditLogMiddleware` 自动记录所有 POST/PUT/DELETE 请求（去除敏感 payload）

---

### P2-4：Pydantic 模型缺少输入长度限制

- **风险等级**：🟡 **中危**  
- **涉及文件**：
  - `src/reviews/router.py` — `AnalyzeRequest`
  - `src/prompts/router.py` — `SavePromptRequest`
  - `src/configs/router.py` — `ConfigUpdateRequest`
  - `src/feedback/router.py` — Feedback 请求体
- **问题描述**：多个关键字段无 `max_length` 限制，超大输入可导致：
  - 内存溢出（数 MB 的 `content` 字符串）
  - LLM Token 超限/费用激增
  - 数据库 `Text` 字段虽然无上限，但网络传输和序列化超时
- **修复建议**：
  - `content`：`max_length=500_000`（约 500KB 代码）
  - `filename`：`max_length=260`
  - `comment`：`max_length=5000`
  - `repo_id`：`max_length=200`
  - `dict` 类型输入增加自定义 validator，限制嵌套深度（如 `max_depth=5`）

---

### P2-5：K8s Manifests 安全加固严重缺失

- **风险等级**：🟡 **中危**  
- **涉及文件**：`k8s/` 全部 YAML
- **问题描述**：
  - 所有 Pod 使用默认 `default` ServiceAccount，无最小权限 RBAC
  - **完全缺失 `securityContext`**：`runAsNonRoot`、`readOnlyRootFilesystem`、`allowPrivilegeEscalation: false`、`capabilities: drop: ["ALL"]`、`seccompProfile`
  - `secret.yaml` 使用 `stringData` 明文占位符，且所有凭证集中在一个 Secret 中
  - 缺少默认 deny-all NetworkPolicy
  - 缺少 PodDisruptionBudget
  - 缺少 ResourceQuota / LimitRange
  - HPA 仅基于 CPU，Celery Worker 瓶颈通常是队列长度而非 CPU
- **修复建议**：
  - 所有容器添加 `securityContext`（见上）
  - Secret 按用途拆分（`latte-db-secret`、`latte-vcs-secret`、`latte-llm-secret`）
  - 添加默认 deny-all NetworkPolicy + 白名单放行
  - Celery Worker HPA 改用 KEDA（基于 Redis queue length）
  - `postgres-pvc` 显式声明 `storageClassName`

---

### P2-6：前端 CSRF 校验存在绕过风险

- **风险等级**：🟡 **中危**  
- **涉及文件**：`frontend/src/lib/csrf.ts` 或 `middleware.ts`
- **问题描述**：`origin.includes(host)` 和 `referer.includes(host)` 可被子域名或部分匹配绕过（如 `host=example.com`，`origin=attacker-example.com` 也会匹配成功）。
- **修复建议**：使用严格相等或 `endsWith(`.${host}`)` 校验

---

### P2-7：前端缺少 Content-Security-Policy (CSP)

- **风险等级**：🟡 **中危**  
- **涉及文件**：`frontend/next.config.mjs`
- **问题描述**：虽然配置了部分安全头，但缺失 CSP。前端展示用户代码 diff 和 AI 生成的 Markdown 描述，缺少 CSP 会增大 XSS 攻击面。
- **修复建议**：增加 CSP 头，限制 `script-src`、`style-src`、`connect-src`，对 AI 生成的 HTML 使用 DOMPurify 净化

---

### P2-8：OpenAPI 文档未保护

- **风险等级**：🟡 **中危**  
- **涉及文件**：`src/main.py`
- **问题描述**：FastAPI 默认暴露 `/docs`（Swagger UI）和 `/redoc`，生产环境下会泄露完整的 API 结构、路由、Pydantic 模型 schema。
- **修复建议**：生产环境配置 `docs_url=None, redoc_url=None, openapi_url=None`，或挂载到带认证的后台路径

---

### P2-9：数据库连接池缺少监控与超时配置

- **风险等级**：🟡 **中危**  
- **涉及文件**：`src/models/base.py`
- **问题描述**：虽配置了 `pool_size=10`、`max_overflow=20`、`pool_pre_ping=True`、`pool_recycle=3600`，但：
  - 未配置 `pool_timeout`（默认无限等待，级联阻塞风险）
  - 未暴露连接池状态指标
  - 未监听慢查询和连接泄漏事件
- **修复建议**：
  - 配置 `pool_timeout=30`
  - 使用 `sqlalchemy.event.listen` 监听 `checkout`/`checkin`，记录慢查询和连接持有时间
  - 暴露 Prometheus 指标：`sqlalchemy_pool_available`、`sqlalchemy_pool_checked_out`

---

### P2-10：缺少 API 版本化

- **风险等级**：🟡 **中危**  
- **涉及文件**：`src/main.py`
- **问题描述**：所有路由无前缀（如 `/v1/`），未来接口变更无法平滑升级。
- **修复建议**：所有 API 路由增加 `/api/v1` 前缀，或按 router 分组挂载到 `/api/v1/*`

---

## 五、代码风格与工程实践（P3 — 持续优化）

### P3-1：裸 `except Exception` 泛滥
- **涉及文件**：`review_engine.py`、`llm/router.py`、`semgrep.py` 等
- **问题**：会捕获 `asyncio.CancelledError`，干扰 Celery 任务的优雅取消流程
- **修复**：改为捕获具体异常（如 `OSError`、`ConnectionError`、`httpx.HTTPError`），或显式 `except Exception as e: if isinstance(e, asyncio.CancelledError): raise`

### P3-2：重试机制缺少 Jitter
- **涉及文件**：`src/llm/router.py`
- **问题**：`await asyncio.sleep(2 ** attempt)` 在并发场景下可能引发"惊群效应"
- **修复**：加入随机抖动：`await asyncio.sleep(min(2 ** attempt + random.random(), max_backoff))`

### P3-3：日志上下文缺失
- **涉及文件**：全局
- **问题**：所有日志都是裸字符串，未绑定 `review_id`、`repo_id` 等结构化字段
- **修复**：使用 `logging.LoggerAdapter` 或 `structlog` 绑定上下文

### P3-4：时区处理不一致
- **涉及文件**：`reviews/router.py` 等
- **问题**：混用 `datetime.utcnow()`（无感知）和自定义 `beijing_now()`
- **修复**：统一使用 `datetime.now(timezone.utc)` 或带明确时区的方法

### P3-5：MD5 用于内容哈希
- **涉及文件**：`src/engine/` 等
- **问题**：`hashlib.md5` 用于生成 `content_hash`，虽然非安全场景，但统一使用 SHA-256 可避免审计噪音
- **修复**：替换为 `hashlib.sha256`

### P3-6：缺少前端测试
- **涉及文件**：`frontend/`
- **问题**：无任何测试文件（Jest/Vitest/Playwright）
- **修复**：添加组件测试和 E2E 测试，覆盖 XSS 防护、ErrorBoundary、关键交互

### P3-7：缺少测试覆盖率工具
- **涉及文件**：`pyproject.toml`
- **问题**：未配置 `pytest-cov`，无法量化覆盖程度
- **修复**：添加 `pytest-cov` 到 dev 依赖，配置 `fail_under=80`

### P3-8：Alembic 缺少初始迁移
- **涉及文件**：`alembic/versions/`
- **问题**：`sql/init.sql` 直接建表，但 Alembic 只有修改时区的迁移。首次运行 `alembic upgrade head` 可能报错
- **修复**：创建基线迁移脚本，或使用 `alembic stamp head` 标记当前状态

### P3-9：`.gitignore` 规则不完善
- **涉及文件**：`.gitignore`
- **问题**：未忽略 `frontend/.next/`、`frontend/out/`、`.env.*.local`、`*.pem`、`*.key`
- **修复**：补充上述规则，防止敏感文件和构建产物误提交

### P3-10：Dockerfile COPY 未设置文件属主
- **涉及文件**：`Dockerfile`
- **问题**：`COPY src/ ./src/` 未使用 `--chown=appuser`，文件默认属主为 root
- **修复**：改为 `COPY --chown=appuser:appuser src/ ./src/`

---

## 六、修复优先级路线图

### 第一阶段：安全基线（1~2周）
1. 修复 CORS 配置（禁止 `*` + `credentials=True`）
2. 关闭 Docker Compose 数据库/Redis 端口映射
3. 配置 Nginx HTTPS（443 + SSL + HSTS + 80 跳转）
4. 为管理后台 API 增加 API Key 认证
5. 为 Webhook 端点增加速率限制
6. 修复 Semgrep 路径遍历漏洞
7. 修复 GitLab Provider 异常处理
8. 修复子进程泄漏（超时 kill）

### 第二阶段：代码健壮性（2~3周）
1. 修复竞态条件（数据库唯一约束 + `ON CONFLICT`）
2. 重构 Repository 层事务边界（禁止内部 commit）
3. 修复缓存空值误判
4. 修复 LLM 路由修改入参字典
5. 增加异常日志脱敏过滤器
6. 修复 GitHub Provider HTTPStatusError 捕获
7. 修复 `reviews/analyze` 文件名净化绕过

### 第三阶段：可运维性（3~4周）
1. 拆分健康检查端点（`/live` + `/ready`）
2. 增加 Prometheus 指标和结构化日志
3. 增加审计日志表和中间件
4. 为 Pydantic 模型增加输入长度限制
5. 加固 K8s manifests（securityContext、RBAC、NetworkPolicy）
6. 修复前端 CSRF 和 CSP

### 第四阶段：工程化（持续）
1. 建立 CI/CD 流水线（GitHub Actions）
2. 引入依赖漏洞扫描（Dependabot、pip-audit）
3. 补充前端测试和覆盖率阈值
4. 补齐 Alembic 初始迁移
5. 增加 API 版本化前缀

---

## 附录：快速检查清单

在部署到生产环境前，请确认以下检查项：

- [ ] `CORS_ORIGINS` 配置为明确域名，非 `*`
- [ ] PostgreSQL 和 Redis 端口未映射到宿主机
- [ ] Nginx 已配置 443 和 SSL 证书
- [ ] 管理后台 API 需要认证
- [ ] Webhook 端点已限速
- [ ] `.env` 中所有密码/密钥均为强随机字符串
- [ ] `APP_ENV=production` 时 SQL echo 已关闭
- [ ] `/docs` 和 `/redoc` 已禁用或已保护
- [ ] K8s 容器配置了 `securityContext` 和 `readOnlyRootFilesystem`
- [ ] CI/CD 流水线中包含安全扫描步骤

---

*报告生成时间：2026-04-18*  
*基于项目实际代码审查编写，供开发团队参考和跟踪修复进度。*
