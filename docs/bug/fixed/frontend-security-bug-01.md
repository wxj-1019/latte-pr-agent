# Bug报告模板

**Bug ID**: `FSEC-001`  
**发现日期**: `2026-04-17`  
**报告人**: `资深前端安全工程师`  
**严重程度**: `🔴 高`  
**状态**: `🟡 待修复`

---

## 基本信息

| 字段 | 内容 |
|------|------|
| **Bug标题** | `API路由缺少输入验证，存在正则表达式注入风险` |
| **相关模块** | `前端API路由` |
| **影响版本** | `所有版本` |
| **发现环境** | `开发/测试环境` |
| **复现概率** | `100%` |

## 问题描述

### 现象
API路由直接使用用户输入的`repo`参数进行`includes()`检查，没有进行任何输入验证或清理。

### 影响范围
- 所有使用`/api/reviews`接口的页面
- 可能影响所有仓库筛选功能
- 潜在的数据泄露风险

### 业务影响
攻击者可以通过注入恶意字符串导致API返回错误数据或执行未预期的操作。

## 技术详情

### 相关文件
```
文件路径:行号
- `frontend/src/app/api/reviews/route.ts:10-18`
```

### 问题代码
```typescript
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const status = searchParams.get("status");
  const repo = searchParams.get("repo"); // 用户输入，未验证

  let data = [...mockReviews];
  if (status) {
    data = data.filter((r) => r.status === status);
  }
  if (repo) {
    data = data.filter((r) => r.repo_id.includes(repo)); // 危险：直接使用用户输入
  }

  return Response.json(data);
}
```

### 问题分析
1. **输入验证缺失**: 直接使用`searchParams.get("repo")`获取的用户输入
2. **正则表达式注入**: 如果用户输入包含特殊正则字符，可能导致`includes()`方法行为异常
3. **数据泄露风险**: 恶意输入可能绕过筛选逻辑，返回不应访问的数据

### 根本原因
缺少前端API路由的输入验证层，直接信任用户输入。

## 修复方案

### 建议修复
```typescript
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const status = searchParams.get("status");
  const repo = searchParams.get("repo");

  let data = [...mockReviews];
  
  // 验证status参数
  if (status) {
    const validStatuses = ["pending", "running", "completed", "failed", "skipped"];
    if (validStatuses.includes(status)) {
      data = data.filter((r) => r.status === status);
    }
  }
  
  // 清理和验证repo参数
  if (repo) {
    // 只允许字母、数字、斜杠、连字符、点号
    const safeRepo = repo.replace(/[^\w\/\-\.]/g, '');
    if (safeRepo.length > 0 && safeRepo.length <= 100) {
      data = data.filter((r) => r.repo_id.includes(safeRepo));
    }
  }

  return Response.json(data);
}
```

### 修复步骤
1. 在`frontend/src/app/api/reviews/route.ts`中添加输入验证逻辑
2. 创建通用的输入验证工具函数
3. 添加单元测试验证输入清理效果
4. 更新API文档说明参数验证规则

### 测试方案
- [ ] 单元测试：测试各种恶意输入场景
- [ ] 集成测试：验证API端点安全性  
- [ ] 回归测试：确保原有功能不受影响
- [ ] 安全测试：进行渗透测试验证修复效果

## 风险评估

### 修复风险
- 可能影响现有使用特殊字符的合法查询
- 需要更新客户端代码以适配新的验证规则

### 不修复风险
- 数据泄露风险
- 正则表达式注入攻击
- 可能被用于信息收集攻击

### 回滚方案
1. 恢复原始代码
2. 临时禁用仓库筛选功能
3. 在负载均衡器层面添加输入过滤

## 相关链接

- **相关PR**: `待创建`
- **相关Issue**: `前端安全审计发现`
- **文档链接**: `docs/bug/frontend-security-bug-01.md`
- **测试用例**: `tests/api/reviews-input-validation.test.ts`

## 时间线

| 时间 | 事件 | 负责人 |
|------|------|--------|
| `2026-04-17 12:30` | 发现bug | `资深前端安全工程师` |
| `2026-04-17 12:35` | 确认bug | `待指定` |
| `2026-04-17 13:00` | 分配修复 | `待指定` |
| `待定` | 开始修复 | `待指定` |
| `待定` | 修复完成 | `待指定` |
| `待定` | 测试通过 | `待指定` |
| `待定` | 部署上线 | `待指定` |

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
1. 永远不要信任用户输入
2. 所有API端点都需要输入验证
3. 前端也需要安全防护，不仅仅是后端

### 预防措施
1. 建立前端API路由安全编码规范
2. 添加自动化的输入验证检查工具
3. 定期进行前端安全审计

### 改进建议
1. 创建统一的输入验证中间件
2. 添加API安全测试套件
3. 实施安全代码审查流程

---

**最后更新**: `2026-04-17 12:40`  
**更新人**: `资深前端安全工程师`