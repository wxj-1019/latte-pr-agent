# Phase 3+ 跨服务影响分析预研

**文档版本**: 1.0  
**日期**: 2026-04-16  
**状态**: 预研 / 接口预留

---

## 1. 背景与目标

当前系统（Phase 1-3）已完成**单仓库内**的文件级依赖分析（Tree-sitter + PostgreSQL 递归 CTE）。

在微服务或模块化单体架构下，一个 API 契约的变更可能影响到：
- 下游消费方服务（Consumer Services）
- 前端客户端（Mobile / Web / SDK）
- 外部合作伙伴的集成接口

**跨服务影响分析的目标**：在 PR 审查阶段，识别变更对**仓库外部**系统的潜在影响，并量化风险。

---

## 2. 技术方案对比

| 方案 | 原理 | 优点 | 缺点 | 推荐度 |
|------|------|------|------|--------|
| **A. OpenAPI / Protobuf 契约 Diff** | 对比 PR 前后 API 契约（Swagger / proto），标记 breaking changes | 精度高、语言无关、可对接 API Gateway | 需要服务先暴露标准化契约 | ⭐⭐⭐⭐⭐ |
| **B. AST + 服务注册表** | 提取各仓库的函数/类签名，建立全局调用图 | 可深入到代码级影响 | 需要维护全局代码索引，规模大时成本高 | ⭐⭐⭐ |
| **C. 调用链日志（Zipkin / Jaeger）** | 基于运行时 trace 识别真实调用关系 | 反映真实流量，不会误报 | 只能覆盖已有流量，新接口/边缘场景遗漏 | ⭐⭐⭐⭐ |
| **D. Consumer-Driven Contract (Pact)** | 基于 Pact Broker 中的消费者契约，检测 provider 变更是否破坏 consumer | 精准到字段级，消费者驱动 | 需要团队先落地契约测试文化 | ⭐⭐⭐⭐⭐ |

---

## 3. 推荐实施路径

### 3.1 短期（Phase 3 末尾 / Phase 4 初期）

**OpenAPI 契约 Diff 方案**

适用场景：已有 REST API 的服务，仓库中维护了 `openapi.yaml` 或自动生成了 Swagger 文档。

实施步骤：
1. 在 `ProjectContextBuilder` 中检测当前 PR 是否修改了 `openapi.yaml` 或控制器层的路由定义
2. 使用 `swagger-diff` 或自定义脚本对比 `base` 分支与 `head` 分支的契约
3. 标记 breaking changes：
   - 删除了 endpoint
   - 删除了请求/响应字段
   - 修改了字段类型（如 string -> int）
   - 将可选字段变为必填字段
4. 将结果写入 `cross_service_impact`

### 3.2 中期（Phase 4）

**调用链增强 + Pact 集成**

实施步骤：
1. 对接现有的 APM / Trace 系统（如 Jaeger、SkyWalking），获取服务间调用拓扑
2. 将拓扑数据写入 `cross_service_dependencies` 表（服务 -> 下游服务 -> endpoint）
3. 对接 Pact Broker，查询当前服务的消费者契约
4. 在 PR 审查时，若 API 契约变更破坏了任何消费者契约，自动提升风险等级为 `critical`

---

## 4. 数据模型预留

当前 `ProjectContextBuilder.build_context()` 已返回：

```python
{
    ...
    "cross_service_impact": None  # Phase 3+ 启用
}
```

未来扩展字段设计：

```python
{
    "cross_service_impact": {
        "has_api_contract_change": bool,
        "breaking_changes": [
            {
                "service": str,          # 当前服务名
                "endpoint": str,         # e.g. "/api/v1/users/{id}"
                "method": str,           # GET / POST / PUT / DELETE
                "change_type": str,      # "removed" | "modified" | "deprecated"
                "affected_consumers": [  # 从 Pact / Trace 获取
                    {"service": "frontend-web", "team": "platform"},
                    {"service": "mobile-app", "team": "mobile"},
                ],
            }
        ],
        "risk_score": float,  # 0.0 ~ 1.0，基于受影响消费者数量计算
    }
}
```

---

## 5. 与现有系统的集成点

| 现有模块 | 集成方式 |
|----------|----------|
| `ProjectContextBuilder` | 新增 `_detect_cross_service_impact()` 方法 |
| `QualityGate` | 若 `cross_service_impact.breaking_changes` 非空，可强制 block merge |
| `ReviewEngine._build_prompt()` | 将跨服务影响写入 Prompt 上下文 |
| `bug_knowledge` (RAG) | 检索历史上因跨服务契约变更导致的故障 |

---

## 6. 风险与挑战

1. **契约覆盖率**：如果服务没有 OpenAPI 文档，该方案完全失效。需要配套 CI 强制生成 Swagger。
2. **消费者契约维护成本**：Pact 需要消费者团队主动维护契约，推广周期较长。
3. **误报率**：调用链数据可能包含测试环境流量，需要过滤生产环境 trace。
4. **性能**：对比大型 OpenAPI 文件（>10MB）可能耗时数秒，需要异步缓存。

---

## 7. 结论

- **Phase 3 暂不实施**跨服务影响分析的具体代码，仅完成接口预留和文档预研。
- **Phase 4 推荐优先落地** OpenAPI 契约 Diff，作为低风险、高收益的第一步。
- 在团队具备契约测试文化后，逐步引入 **Pact Broker 集成**，实现消费者驱动的精准影响分析。
