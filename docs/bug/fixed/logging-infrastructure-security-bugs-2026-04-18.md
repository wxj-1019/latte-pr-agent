# Bug报告：日志基础设施与安全缺陷汇总

**Bug ID**: `LOG-INFRA-001` ~ `LOG-INFRA-010`  
**发现日期**: `2026-04-18`  
**报告人**: `Claude Code (日志审计)`  
**严重程度**: `🔴 高 / 🟡 中`  
**状态**: `🟡 待修复`

---

## 基本信息

| 字段 | 内容 |
|------|------|
| **Bug标题** | `日志基础设施配置缺失、敏感信息泄露风险、核心模块静音` |
| **相关模块** | `config、main、tasks、webhooks、engine、providers、feedback、static、frontend、部署配置` |
| **影响版本** | `main分支（当前开发版本）` |
| **发现环境** | `全环境（开发/测试/生产均受影响）` |
| **复现概率** | `100%` |

## 问题描述

### 现象
1. 环境变量 `LOG_LEVEL=INFO` 已配置但业务日志级别不受控，部分 INFO 日志可能不被输出
2. `settings` 中敏感字段（API Key、Token、数据库密码）使用普通 `str` 类型，异常日志中可能明文泄露
3. 5 个核心模块（publisher、verifier、rate_limiter、deduplicator、retriever）完全无日志记录
4. 大量日志使用 f-string 格式化，存在性能损耗和潜在注入风险
5. 无 request_id / trace_id 机制，无法关联 Webhook → Celery → LLM → Git Provider 全链路日志
6. 前端生产环境仍有 `console.error/warn` 输出，无错误上报机制
7. docker-compose 生产配置未配置日志驱动和轮转，存在磁盘占满风险

### 影响范围
1. **故障排查**：审查流程中任何环节出问题都无法快速定位（评论没发出去？RAG没召回？去重漏了？）
2. **安全合规**：密钥/Token 可能通过异常日志进入 stdout → 日志系统 → 被有权限人员查看
3. **可观测性**：无法评估系统健康度（review 吞吐量、LLM 成功率、队列积压）
4. **运维稳定性**：日志文件无限增长可能导致磁盘耗尽；前端错误无法收集

### 业务影响
- 生产环境出现故障时，排查时间从分钟级延长到小时级
- 安全审计时日志脱敏不合规会直接被打回
- 无法通过日志分析系统瓶颈和优化方向

---

## 技术详情

### 相关文件
```
文件路径:行号
- `src/config/__init__.py:35`              # log_level 定义但未消费
- `src/config/__init__.py:12-31`           # 敏感字段未使用 SecretStr
- `src/main.py:21`                         # 无请求日志中间件
- `src/main.py:39`                         # f-string 日志格式化
- `src/tasks.py:35`                        # f-string 日志格式化
- `src/services/review_service.py:30,56,78,80,87,89,138,140,145,152`
                                           # 全文 f-string 日志
- `src/engine/review_engine.py:75,108,110,117,119,177,181,193`
                                           # f-string + 缓存命中无日志
- `src/llm/router.py:130,138,144`          # f-string + 无 review_id 上下文
- `src/webhooks/router.py:78-81`           # 模块内临时创建 logger + f-string
- `src/webhooks/verifier.py`               # 完全无日志
- `src/webhooks/rate_limiter.py`           # 完全无日志
- `src/feedback/publisher.py`              # 完全无日志
- `src/engine/deduplicator.py`             # 完全无日志
- `src/rag/retriever.py`                   # 完全无日志
- `src/providers/github_provider.py:33,47,60,76`
                                           # warning 丢失堆栈
- `src/providers/gitlab_provider.py:43,72,87,106`
                                           # warning 丢失堆栈
- `src/static/semgrep.py:58-65`            # 异常静默吞掉无日志
- `frontend/src/lib/env-check.ts:42,46`    # 生产环境 console 输出
- `frontend/src/app/dashboard/analyze/page.tsx:90`
                                           # 生产环境 console.error
- `docker-compose.yml`                     # 无 logging 驱动配置
- `docker-compose.prod.yml`                # 无 logging 驱动配置
- `Dockerfile`                             # 缺少 PYTHONUNBUFFERED=1
```

### 问题代码

#### Bug-1：log_level 配置未生效
```python
# src/config/__init__.py:35
class Settings(BaseSettings):
    ...
    log_level: str = "INFO"    # 定义了，但 src/ 中没有任何代码读取它

# 后果：业务代码的 logger.info() 可能不被输出
```

#### Bug-2：敏感字段未使用 SecretStr
```python
# src/config/__init__.py:12-31
class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/code_review"
    github_token: str = ""
    deepseek_api_key: str = ""
    anthropic_api_key: str = ""
    # 全部使用 str，异常消息中可能包含这些值
```

#### Bug-3：f-string 格式化日志
```python
# src/services/review_service.py:56
logger.info(f"Review {review_id}: fetched diff ({len(diff_content)} chars)")

# src/tasks.py:35
logger.exception(f"Celery task failed for review {review_id}: {exc}")

# src/llm/router.py:130
logger.info(f"Trying model {model}, attempt {attempt + 1}")
```

#### Bug-4：核心模块完全无日志
```python
# src/feedback/publisher.py
# 无任何 import logging 或 logger 使用
# 向 GitHub/GitLab 发布评论的完整流程完全静默
```

#### Bug-5：前端生产环境 console 输出
```typescript
// frontend/src/lib/env-check.ts:42
console.error("[Latte PR Agent] Environment validation failed:", errors);
// 生产构建后仍会执行，用户可在 DevTools 中查看
```

#### Bug-6：docker-compose 无日志驱动
```yaml
# docker-compose.prod.yml (片段)
services:
  webhook-server:
    # 缺少 logging 块
    # 默认 json-file 驱动会无限增长
```

### 问题分析

1. **配置层面**：项目虽然定义了 `log_level` 环境变量，但缺少一个统一的日志初始化入口（如 `setup_logging()` 函数在 `main.py` 启动时调用）。Python 的默认根 logger 级别为 WARNING，如果 uvicorn 未正确传递级别，大量 INFO 日志会被静默丢弃。

2. **安全层面**：Pydantic `SecretStr` 的作用是当字段被打印或拼接进字符串时自动脱敏为 `**********`。当前使用普通 `str`，加上多处 `logger.warning(f"...{exc}...")` 的异常记录方式，Celery 连接失败时可能将包含密码的 Broker URL 完整写入日志。

3. **工程规范层面**：Python logging 标准推荐 `%s` 延迟格式化（lazy formatting），原因是：
   - f-string 在日志级别被过滤时仍会执行字符串拼接，浪费 CPU
   - 若变量值中包含 `%s` 等特殊字符，可能被二次解析（尤其在自定义 Handler 中）

4. **可观测性层面**：没有 request_id 中间件意味着同一次 Webhook 请求在 FastAPI 进程、Celery Worker、外部 API 调用中的日志无法关联。生产环境中排查"某条 PR 评论没发"需要人工跨容器匹配时间戳。

5. **部署层面**：Docker 默认 `json-file` 日志驱动不限制大小，长期运行下单个容器的日志文件可能达到数十 GB，导致宿主机磁盘耗尽和 Pod 驱逐。

### 根本原因
- **日志被视为“附属功能”而非“基础设施”**：在项目初期未投入设计，各模块自行决定是否打日志，导致覆盖极不均匀
- **缺乏日志规范和 Code Review 检查清单**：没有团队级的日志标准（何时用 info/warning/error、必须携带什么上下文、禁止 f-string 等）
- **安全左移缺失**：在配置设计阶段未将敏感字段脱敏纳入考虑，异常处理时也未评估日志泄露风险

---

## 修复方案

### 建议修复

#### 1. 统一日志配置模块（新增 `src/logging_config.py`）
```python
import logging
import sys
from config import settings


def setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = [handler]
    
    # 添加敏感信息过滤器
    class SensitiveDataFilter(logging.Filter):
        _patterns = [
            r'(token|api_key|apikey|password|secret|auth)=[^&\s\'"]+',
            r'(postgresql\+asyncpg://|redis://)[^\s\'"]+',
            r'sk-[a-zA-Z0-9]{20,}',
            r'ghp_[a-zA-Z0-9]{36}',
            r'glpat-[a-zA-Z0-9\-]{20}',
        ]
        
        def filter(self, record: logging.LogRecord) -> bool:
            import re
            msg = str(record.getMessage())
            for pattern in self._patterns:
                msg = re.sub(pattern, r'\1=***', msg, flags=re.IGNORECASE)
            record.msg = msg
            record.args = ()
            return True
    
    handler.addFilter(SensitiveDataFilter())
```

#### 2. 敏感字段改为 SecretStr
```python
# src/config/__init__.py
from pydantic import SecretStr

class Settings(BaseSettings):
    database_url: SecretStr = SecretStr("postgresql+asyncpg://postgres:postgres@localhost:5432/code_review")
    github_token: SecretStr = SecretStr("")
    deepseek_api_key: SecretStr = SecretStr("")
    # ... 其他敏感字段同理
    
    # 使用方式：settings.github_token.get_secret_value() 获取真实值
    # str(settings.github_token) → "**********"
```

#### 3. 在 `src/main.py` 启动时初始化日志
```python
# src/main.py
from logging_config import setup_logging

setup_logging()  # 放在 app 实例化之前
```

#### 4. 将 f-string 全部改为 % 风格
```python
# 修复前
logger.info(f"Review {review_id}: fetched diff ({len(diff_content)} chars)")

# 修复后
logger.info("Review %s: fetched diff (%s chars)", review_id, len(diff_content))
```

#### 5. 为核心静音模块补充日志
```python
# src/feedback/publisher.py
import logging

logger = logging.getLogger(__name__)

class ReviewPublisher:
    async def publish(self, review_id: int, findings: list) -> None:
        logger.info("Publishing review %s: %d findings", review_id, len(findings))
        success = 0
        for finding in findings:
            try:
                await self._publish_single(finding)
                success += 1
            except Exception:
                logger.exception("Failed to publish comment on %s:%s", finding.file_path, finding.line_number)
        logger.info("Review %s: published %d/%d comments", review_id, success, len(findings))
```

#### 6. 增加 request_id 中间件
```python
# src/main.py
import uuid
from fastapi import Request

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    # 可结合 contextvars 注入 logger 上下文
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

#### 7. 前端生产环境屏蔽 console
```typescript
// frontend/src/lib/logger.ts
const isProd = process.env.NODE_ENV === 'production';

export const logger = {
  log: isProd ? () => {} : console.log,
  warn: isProd ? () => {} : console.warn,
  error: isProd ? () => {} : console.error, // 或接入 Sentry
};
```

#### 8. docker-compose 增加日志轮转
```yaml
# docker-compose.prod.yml
services:
  webhook-server:
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"
  celery-worker:
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"
```

#### 9. Dockerfile 增加 PYTHONUNBUFFERED
```dockerfile
# Dockerfile
ENV PYTHONUNBUFFERED=1
```

### 修复步骤
1. **第一步**：创建 `src/logging_config.py`，实现 `setup_logging()` + `SensitiveDataFilter`
2. **第二步**：`src/config/__init__.py` 敏感字段改为 `SecretStr`，修改所有引用点（`get_secret_value()`）
3. **第三步**：`src/main.py` 启动时调用 `setup_logging()`，增加 request_id 中间件
4. **第四步**：全局搜索替换 f-string 日志为 `%` 风格（可使用 ruff / regex 批量处理）
5. **第五步**：为 5 个静音模块（publisher、verifier、rate_limiter、deduplicator、retriever）补充日志
6. **第六步**：前端封装 logger，替换所有 `console.*` 调用
7. **第七步**：docker-compose 增加 logging 驱动配置，Dockerfile 增加 `PYTHONUNBUFFERED=1`
8. **第八步**：运行全部 155 个测试，确认无回归

### 测试方案
- [ ] 单元测试：验证 `SensitiveDataFilter` 能正确脱敏 Token、数据库 URL
- [ ] 单元测试：验证 `setup_logging()` 能正确应用 `LOG_LEVEL` 环境变量
- [ ] 单元测试：验证 `SecretStr` 字段 `str()` 输出为脱敏值
- [ ] 集成测试：验证 request_id 能从 FastAPI 传递到响应头
- [ ] 回归测试：全部 155 个现有测试通过
- [ ] 手工测试：构造 Celery 连接异常，确认日志中不出现 Redis 密码

---

## 风险评估

### 修复风险
| 风险 | 说明 | 缓解措施 |
|------|------|----------|
| SecretStr 引入导致调用点报错 | 大量代码直接 `settings.github_token` 传参，改为 SecretStr 后类型不匹配 | 全局搜索替换，加上 `get_secret_value()`；mypy 严格模式会捕获 |
| 日志级别生效后日志量激增 | DEBUG/INFO 级别打开后可能输出大量日志，影响性能 | 生产环境默认保持 INFO；关键路径避免在循环中打 info |
| 前端 logger 封装遗漏 | 可能有 `console.*` 调用未被发现 | 使用 ESLint `no-console` 规则全局检查 |

### 不修复风险
- **生产故障无法排查**：评论没发、RAG 没召回、去重失效等问题全靠猜测
- **安全审计不通过**：密钥明文出现在日志中，违反绝大多数企业的安全基线
- **磁盘耗尽**：日志无限增长可能导致服务宕机
- **合规风险**：GDPR/等保/ISO27001 等要求对敏感操作留痕和脱敏

### 回滚方案
- 日志配置变更：删除 `setup_logging()` 调用，恢复 Python 默认行为
- SecretStr 变更：回滚 `src/config/__init__.py`，恢复 `str` 类型
- docker-compose 变更：删除 `logging:` 块
- 全部变更可在 5 分钟内通过 `git revert` 回滚

---

## 相关链接

- **相关文档**: `docs/security-code-review-report.md`（P0-3、P1-3、P2-2、P2-3）
- **测试用例**: `tests/test_webhooks.py`、`tests/test_engine.py`、`tests/test_llm.py`

## 时间线

| 时间 | 事件 | 负责人 |
|------|------|--------|
| `2026-04-18` | 发现bug | `Claude Code (日志审计)` |
| `2026-04-18` | 确认bug | `Claude Code (日志审计)` |
| | 分配修复 | `待分配` |
| | 开始修复 | `待分配` |
| | 修复完成 | `待分配` |
| | 测试通过 | `待分配` |
| | 部署上线 | `待分配` |

## 验证结果

### 修复验证
- [ ] `LOG_LEVEL` 环境变量能正确控制业务日志级别
- [ ] 异常日志中不出现 API Key、Token、数据库密码明文
- [ ] 5 个静音模块（publisher、verifier、rate_limiter、deduplicator、retriever）有日志输出
- [ ] 全链路 request_id 能关联 FastAPI → Celery → Provider 日志
- [ ] 前端生产构建后无 console 输出
- [ ] docker-compose 日志文件大小受控

### 测试结果
```
[待修复后补充]
```

## 经验总结

### 教训
- 日志不应被视为"开发调试工具"，而是生产系统的**核心基础设施**，必须在项目初期统一设计
- 配置类中的敏感字段从第一天就应该使用 `SecretStr`，后期改造成本高
- f-string 虽然写起来方便，但在日志场景下是**反模式**，团队应通过 lint 规则禁止

### 预防措施
- 在 Code Review 检查清单中增加日志相关条目：
  - [ ] 新增模块是否引入了 `logger = logging.getLogger(__name__)`
  - [ ] 日志是否使用 `%s` 延迟格式化
  - [ ] 异常处理是否使用 `logger.exception()`
  - [ ] 是否携带了 `review_id` / `request_id` 等上下文
  - [ ] 是否泄露了敏感信息
- CI 中增加 `ruff` 规则禁止 `logging-fstring`（如启用 `G` 规则集）

### 改进建议
- 引入 `structlog` 实现结构化 JSON 日志，便于接入 ELK/Loki
- 接入 Sentry 进行前端+后端错误上报
- 为 Celery 增加 Flower 监控面板
- 增加 Prometheus `/metrics` 端点，暴露业务指标（与日志互补）

---

**最后更新**: `2026-04-18`  
**更新人**: `Claude Code`
