# Bug记录库

本目录用于记录项目中发现的所有bug，便于追踪、分析和预防类似问题。

## 目录结构

```
docs/bug/
├── README.md              # 本文件
├── BUG_TEMPLATE.md        # Bug报告模板
├── phase1-critical-bugs-2026-04-16.md  # Phase 1严重bug记录
├── [按日期分类]
│   ├── 2026-04-*.md
│   └── ...
└── [按模块分类]
    ├── security-*.md      # 安全相关bug
    ├── database-*.md      # 数据库相关bug
    ├── logic-*.md         # 逻辑错误bug
    └── ...
```

## Bug严重程度定义

| 等级 | 图标 | 说明 |
|------|------|------|
| **高** | 🔴 | 安全漏洞、数据丢失、核心功能失效、导致系统崩溃 |
| **中** | 🟡 | 功能异常但不影响核心流程、性能问题、用户体验问题 |
| **低** | 🟢 | 界面问题、文档错误、不影响功能的代码问题 |

## Bug状态定义

| 状态 | 图标 | 说明 |
|------|------|------|
| **待修复** | 🟡 | 已确认但尚未修复 |
| **修复中** | 🔵 | 正在修复 |
| **已修复** | 🟢 | 修复完成并通过测试 |
| **无法修复** | 🔴 | 由于技术或业务原因无法修复 |
| **重复** | ⚫ | 与现有bug重复 |
| **不是bug** | ⚪ | 经确认不是bug |

## 记录规范

### 命名规范
- 按日期: `YYYY-MM-DD-简短描述.md`
- 按模块: `模块名-简短描述-YYYY-MM-DD.md`
- 按类型: `类型-简短描述-YYYY-MM-DD.md`

### 内容要求
1. 使用提供的模板格式
2. 包含完整的复现步骤
3. 提供问题代码和修复建议
4. 记录修复过程和验证结果
5. 总结经验教训

## 当前Bug统计

| 严重程度 | 待修复 | 修复中 | 已修复 | 总计 |
|----------|--------|--------|--------|------|
| 🔴 高 | 0 | 0 | 10 | 10 |
| 🟡 中 | 0 | 0 | 16 | 16 |
| 🟢 低 | 0 | 0 | 1 | 1 |
| **总计** | **0** | **0** | **27** | **27** |

## 已修复的Bug

### 🔴 高优先级（已修复）
1. **Webhook签名验证绕过** - `fixed/phase1-critical-bugs-2026-04-16.md#1`
2. **ProjectContextBuilder依赖分析缺陷** - `fixed/phase1-critical-bugs-2026-04-16.md#4`
3. **函数签名变更检测逻辑错误** - `fixed/phase1-critical-bugs-2026-04-16.md#5`
4. **数据库事务管理缺陷** - `fixed/phase1-critical-bugs-2026-04-16.md#10`
5. **AST解析模块导入错误** - `fixed/phase2-critical-bugs-2026-04-16.md#13`

### 🟡 中优先级（已修复）
6. **GitLab令牌验证逻辑错误** - `fixed/phase1-critical-bugs-2026-04-16.md#2`
7. **ReviewRouter双模型验证逻辑缺陷** - `fixed/phase1-critical-bugs-2026-04-16.md#3`
8. **服务层异常处理不完整** - `fixed/phase1-critical-bugs-2026-04-16.md#6`
9. **GitHubProvider网络请求缺少重试** - `fixed/phase1-critical-bugs-2026-04-16.md#7`
10. **数据库连接池缺失** - `fixed/phase1-critical-bugs-2026-04-16.md#8`
11. **ReviewCache Redis连接管理** - `fixed/phase1-critical-bugs-2026-04-16.md#9`
12. **唯一约束冲突处理** - `fixed/phase1-critical-bugs-2026-04-16.md#11`
13. **超大PR处理逻辑不完整** - `fixed/phase1-critical-bugs-2026-04-16.md#12`
14. **图分析模块数据库连接问题** - `fixed/phase2-critical-bugs-2026-04-16.md#14`
15. **RAG检索器Embedding维度不匹配** - `fixed/phase2-critical-bugs-2026-04-16.md#15`
16. **双模型验证配置缺失** - `fixed/phase2-critical-bugs-2026-04-16.md#16`
17. **API检测器语言支持不完整** - `fixed/phase2-critical-bugs-2026-04-16.md#17`

### 🔴 高优先级（已修复 — 自主修复复查）
18. **Redis 缓存使用 threading.Lock 阻塞事件循环** - `fixed/partial-fix-review-2026-04-18.md#问题1`
19. **review_service.py 顶层裸 except Exception 掩盖编程错误** - `fixed/partial-fix-review-2026-04-18.md#问题2`

### 🟡 中优先级（已修复 — 自主修复复查）
20. **GitLab Provider 异常未细化** - `fixed/partial-fix-review-2026-04-18.md#问题3`
21. **开发环境 Docker Compose 暴露 DB/Redis 端口** - `fixed/partial-fix-review-2026-04-18.md#问题4`

### 🟢 低优先级（已修复 — 自主修复复查）
22. **ResilientReviewRouter 兼容旧配置键 "primary"** - `fixed/partial-fix-review-2026-04-18.md#问题5`

### 🟡 中优先级（已修复 — 接口对齐）
23. **API-INT-001: 前端后端接口不匹配** - `fixed/api-integration-bugs-2026-04-17.md`

## 已修复的前端安全Bug

### 🔴 高优先级
18. **FSEC-001: API路由缺少输入验证** - `fixed/frontend-security-bug-01.md`
19. **FSEC-002: 缺少CORS配置** - `fixed/frontend-security-bug-02.md`
20. **FSEC-003: SSE端点缺少认证和速率限制** - `fixed/frontend-security-bug-03.md`

### 🟡 中优先级
21. **FSEC-004: XSS漏洞风险** - `fixed/frontend-security-bug-04.md`

### 📋 汇总报告（已修复）
- **前端安全Bug汇总** - `fixed/frontend-security-bugs-summary.md`
- **日志基础设施与安全缺陷汇总** - `fixed/logging-infrastructure-security-bugs-2026-04-18.md`
- **自主修复项复查报告（5项未完全修复→已修复）** - `fixed/partial-fix-review-2026-04-18.md`

## 修复进度跟踪

### 本周修复目标（2026-04-16 至 2026-04-23）
- [x] 修复后端所有🔴高优先级bug
- [x] 修复后端所有🟡中优先级bug
- [x] 修复前端安全bug（FSEC-001至004）
- [x] 添加React错误边界
- [x] 添加环境变量安全检查
- [x] 添加安全依赖扫描
- [x] 修复日志基础设施缺陷（LOG-INFRA-001~010）
- [x] 修复自主修复复查残留问题（5项）
- [x] 修复前端后端接口不匹配问题
- [ ] 建立bug预防机制

### 修复完成情况
- **后端完成时间**: 2026-04-16
- **后端修复数量**: 17个bug全部修复
- **前端修复时间**: 2026-04-17
- **前端修复数量**: 4个安全bug + 3个安全改进全部完成
- **接口对齐修复时间**: 2026-04-18
- **安全漏洞**: 全部修复
- **逻辑缺陷**: 全部修复
- **性能问题**: 全部修复
- **日志基础设施**: 全部修复
- **接口兼容性**: 全部修复

### 负责人
- **安全相关bug**: 待分配
- **数据库相关bug**: 待分配  
- **逻辑错误bug**: 待分配
- **性能问题bug**: 待分配

## 如何使用

### 报告新bug
1. 复制`BUG_TEMPLATE.md`为新文件
2. 按模板填写bug信息
3. 更新本README中的统计信息
4. 提交到版本控制系统

### 查找bug
1. 按日期查找: 查看最近日期的文件
2. 按模块查找: 查看模块前缀的文件
3. 按状态查找: 查看文件中的状态标记

### 更新bug状态
1. 打开对应的bug文件
2. 更新状态、时间线和验证结果
3. 更新本README中的统计信息

## 最佳实践

### 预防措施
1. **代码审查**: 所有修改必须经过代码审查
2. **自动化测试**: 核心功能必须有自动化测试
3. **静态分析**: 使用工具进行代码质量检查
4. **安全扫描**: 定期进行安全漏洞扫描

### 处理流程
1. **发现**: 发现bug后立即记录
2. **评估**: 评估严重程度和影响范围
3. **分配**: 分配给合适的开发人员
4. **修复**: 按照修复方案进行修复
5. **验证**: 验证修复效果
6. **关闭**: 更新状态并总结经验

### 经验分享
- 每月进行bug分析会议
- 分享典型bug案例
- 更新开发规范和检查清单

---

**最后更新**: 2026-04-17  
**更新人**: Claude Code  
**下次统计更新**: 2026-04-24

## 已关闭Bug详情

### API-INT-001: 前端后端接口不匹配（已修复）
- **发现日期**: 2026-04-17
- **修复日期**: 2026-04-18
- **严重程度**: 🟡 中
- **状态**: 🟢 已修复
- **影响**: 指标页面、提示词页面功能异常
- **根本原因**: 前后端接口格式不一致，缺少统一接口契约
- **修复内容**:
  1. ✅ `/feedback/metrics/{repo_id}` — `ReviewMetricsService.get_repo_metrics()` 返回 `{ metrics, chart, severity_distribution, ... }` 格式，与前端 `ReviewMetrics` + `MetricsDataPoint[]` 对齐
  2. ✅ `/prompts/versions` — 后端直接返回数组 `PromptVersion[]`，与前端类型一致
  3. ✅ `/prompts` POST — 后端新增 `@router.post("")` 别名路由 `save_version_alias`，与前端调用路径匹配
  4. ✅ 时间序列数据 — `ReviewMetricsService._review_volume_chart()` 已实现，返回最近 N 天 reviews/findings 数量
  5. ✅ 平均置信度 — `ReviewMetricsService._avg_confidence()` 已实现，基于 `ReviewFinding.confidence` 平均值计算
- **文档**: `fixed/api-integration-bugs-2026-04-17.md`