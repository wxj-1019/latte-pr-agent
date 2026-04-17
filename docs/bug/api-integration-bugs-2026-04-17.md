# Bug报告模板

**Bug ID**: `API-INT-001`  
**发现日期**: `2026-04-17`  
**报告人**: `Claude Code (前端后端接口分析)`  
**严重程度**: `🟡 中`  
**状态**: `🟡 待修复`

---

## 基本信息

| 字段 | 内容 |
|------|------|
| **Bug标题** | `前端后端接口不匹配导致功能异常` |
| **相关模块** | `前端API客户端、后端路由层、指标服务、提示词服务` |
| **影响版本** | `main分支（当前开发版本）` |
| **发现环境** | `开发环境` |
| **复现概率** | `100%` |

## 问题描述

### 现象
前端页面（指标页面、提示词页面）无法正常显示数据，控制台出现API响应格式错误。

### 影响范围
1. 指标页面：无法显示审查指标数据
2. 提示词页面：无法显示提示词版本列表
3. 配置页面：可能影响配置保存功能

### 业务影响
- 用户无法查看项目审查指标
- 无法管理提示词版本
- 影响系统监控和配置管理功能

## 技术详情

### 相关文件
```
文件路径:行号
- frontend/src/lib/api.ts:40-44 (指标API调用)
- frontend/src/lib/api.ts:46-48 (提示词API调用)
- frontend/src/lib/api.ts:50-56 (保存提示词API调用)
- src/feedback/router.py:11-17 (指标接口)
- src/feedback/metrics.py:15-36 (指标服务)
- src/prompts/router.py:24-28 (提示词版本接口)
- src/prompts/router.py:45-52 (保存提示词接口)
- frontend/src/types/index.ts:109-114 (ReviewMetrics类型定义)
```

### 问题代码
```typescript
// 前端期望的API响应格式
// api.ts 第40-44行
export const api = {
  getMetrics: async (_range: "7d" | "30d" | "90d", repoId: string) => {
    return fetchJson<{ metrics: ReviewMetrics; chart: MetricsDataPoint[] }>(
      `/feedback/metrics/${repoId}`
    );
  },
```

```python
# 后端实际的API响应格式
# feedback/router.py 第11-17行
@router.get("/metrics/{repo_id}")
async def get_metrics(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ReviewMetricsService(db)
    return await service.get_repo_metrics(repo_id)
```

### 问题分析
经过详细分析，发现以下接口不匹配问题：

#### 1. `/feedback/metrics/{repo_id}` 接口不匹配
- **前端期望**：`{ metrics: ReviewMetrics; chart: MetricsDataPoint[] }`
- **后端返回**：直接返回metrics对象，没有`metrics`包装层，也没有`chart`字段
- **缺失字段**：`avg_confidence`（前端需要但后端未计算）

#### 2. `/prompts/versions` 接口不匹配
- **前端期望**：`PromptVersion[]`（数组）
- **后端返回**：`{ "versions": [...] }`（对象包含versions字段）

#### 3. `/prompts` POST接口路径不匹配
- **前端调用**：`/prompts` (POST)
- **后端实现**：`/prompts/versions` (POST)

#### 4. 时间序列数据缺失
前端指标页面需要时间序列图表数据（`chart`字段），但后端没有提供相关接口。

### 根本原因
1. **前后端开发不同步**：前端和后端开发时没有统一的接口规范
2. **缺少接口契约**：没有使用OpenAPI/Swagger等工具定义接口契约
3. **测试覆盖不足**：缺少端到端集成测试来验证接口兼容性
4. **类型定义不一致**：TypeScript类型定义与Python实现不匹配

## 修复方案

### 建议修复

#### 方案一：修改后端接口（推荐）
```python
# 修改 feedback/router.py
@router.get("/metrics/{repo_id}")
async def get_metrics(
    repo_id: str,
    range: str = "7d",  # 新增range参数
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ReviewMetricsService(db)
    metrics = await service.get_repo_metrics(repo_id)
    chart_data = await service.get_time_series_data(repo_id, range)
    
    # 计算平均置信度
    avg_confidence = await service.calculate_avg_confidence(repo_id)
    metrics["avg_confidence"] = avg_confidence
    
    return {
        "metrics": metrics,
        "chart": chart_data
    }
```

```python
# 修改 prompts/router.py
@router.get("/versions")
async def list_versions(db: AsyncSession = Depends(get_db)) -> list:
    registry = PromptRegistry(db)
    await registry.load_from_db()
    return registry.list_versions()  # 直接返回数组

@router.post("/")
async def save_version(
    req: SavePromptRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    registry = PromptRegistry(db)
    await registry.save_version(req.version, req.text, req.metadata)
    return {"message": "Saved", "version": req.version}
```

#### 方案二：修改前端适配
```typescript
// 修改前端api.ts
export const api = {
  getMetrics: async (_range: "7d" | "30d" | "90d", repoId: string) => {
    const data = await fetchJson<any>(`/feedback/metrics/${repoId}`);
    // 适配后端格式
    return {
      metrics: {
        total_reviews: data.total_reviews,
        total_findings: data.total_findings,
        false_positive_rate: data.false_positive_rate,
        avg_confidence: data.avg_confidence || 0.85, // 默认值或计算
      },
      chart: [] // 需要新增时间序列接口
    };
  },
```

### 修复步骤
1. **评估影响**：确定采用方案一还是方案二
2. **修改后端接口**（如果采用方案一）：
   - 修改`/feedback/metrics/{repo_id}`接口格式
   - 添加平均置信度计算
   - 添加时间序列数据接口
   - 修改`/prompts/versions`接口返回格式
   - 添加`/prompts` POST接口或修改前端调用路径
3. **更新前端**（如果采用方案二）：
   - 修改api.ts适配后端格式
   - 更新类型定义
   - 添加缺失数据的处理逻辑
4. **测试验证**：
   - 单元测试
   - 集成测试
   - 端到端测试

### 测试方案
- [ ] 单元测试：验证修改后的接口逻辑
- [ ] 集成测试：验证前后端接口兼容性  
- [ ] 回归测试：确保现有功能不受影响
- [ ] 性能测试：验证新增计算不影响性能

## 风险评估

### 修复风险
1. **向后兼容性**：修改接口可能影响现有客户端
2. **数据一致性**：新增计算可能影响数据准确性
3. **性能影响**：新增的时间序列查询可能影响性能

### 不修复风险
1. **功能异常**：指标页面和提示词页面无法使用
2. **用户体验**：用户无法查看重要数据
3. **系统监控**：无法监控审查质量和效果

### 回滚方案
1. 保留原有接口，新增兼容接口
2. 使用API版本控制（如`/v1/feedback/metrics`）
3. 提供迁移期，逐步切换

## 相关链接

- **相关PR**: `待创建`
- **相关Issue**: `前端后端接口配合需求分析`
- **文档链接**: `docs/bug/api-integration-bugs-2026-04-17.md`
- **测试用例**: `tests/test_api_integration.py`

## 时间线

| 时间 | 事件 | 负责人 |
|------|------|--------|
| `2026-04-17 13:30` | 发现bug | `Claude Code` |
| `2026-04-17 13:45` | 确认bug | `Claude Code` |
| `2026-04-17 14:00` | 分配修复 | `待分配` |
| `2026-04-17 14:00` | 开始修复 | `待分配` |
| `2026-04-17 16:00` | 修复完成 | `待分配` |
| `2026-04-17 16:30` | 测试通过 | `待分配` |
| `2026-04-17 17:00` | 部署上线 | `待分配` |

## 验证结果

### 修复验证
- [ ] 问题现象消失
- [ ] 相关功能正常
- [ ] 性能无退化
- [ ] 无新bug引入

### 测试结果
```
待测试完成后填写
```

## 经验总结

### 教训
1. **接口契约重要性**：前后端开发必须基于明确的接口契约
2. **集成测试必要性**：需要端到端集成测试验证接口兼容性
3. **类型系统一致性**：TypeScript和Python类型定义应该同步
4. **开发流程规范**：需要建立前后端协同开发流程

### 预防措施
1. **使用OpenAPI/Swagger**：定义统一的接口规范
2. **建立接口测试套件**：自动化验证接口兼容性
3. **代码生成工具**：从接口定义生成客户端和服务端代码
4. **契约测试**：使用Pact等工具进行契约测试

### 改进建议
1. **引入API版本控制**：支持接口演进和向后兼容
2. **建立接口文档**：维护完整的接口文档
3. **自动化集成测试**：CI/CD中增加接口集成测试
4. **前后端协同工作流**：建立前后端协同开发流程

---

**最后更新**: `2026-04-17 13:45`  
**更新人**: `Claude Code`