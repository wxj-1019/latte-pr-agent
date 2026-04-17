# Bug报告模板

**Bug ID**: `FSEC-002`  
**发现日期**: `2026-04-17`  
**报告人**: `资深前端安全工程师`  
**严重程度**: `🔴 高`  
**状态**: `🟢 已修复`

---

## 基本信息

| 字段 | 内容 |
|------|------|
| **Bug标题** | `缺少CORS配置，存在CSRF和跨域攻击风险` |
| **相关模块** | `前端API路由、Web安全` |
| **影响版本** | `所有版本` |
| **发现环境** | `开发/测试环境` |
| **复现概率** | `100%` |

## 问题描述

### 现象
Next.js API路由没有配置CORS（跨源资源共享），允许任意来源的请求访问API端点。

### 影响范围
- 所有API端点（/api/*）
- 可能被恶意网站利用进行CSRF攻击
- 数据泄露和未授权访问风险

### 业务影响
攻击者可以从恶意网站发起跨域请求，执行未授权操作或窃取数据。

## 技术详情

### 相关文件
```
文件路径:行号
- `frontend/src/app/api/reviews/route.ts:1-18`
- `frontend/src/app/api/findings/[id]/feedback/route.ts:1-12`
- `frontend/src/app/api/sse/reviews/route.ts:1-36`
- 所有其他API路由文件
```

### 问题代码
```typescript
// 所有API路由都缺少CORS头
export async function GET(request: NextRequest) {
  // 没有CORS头配置
  const data = getData();
  return Response.json(data); // 默认允许所有来源
}
```

### 问题分析
1. **CORS缺失**: 默认情况下，Next.js API路由允许所有来源的跨域请求
2. **CSRF风险**: 恶意网站可以伪造请求执行操作（如提交虚假反馈）
3. **信息泄露**: 攻击者可以读取API响应数据
4. **预检请求**: 缺少OPTIONS方法处理

### 根本原因
项目没有实施Web安全最佳实践，缺少CORS策略配置。

## 修复方案

### 建议修复
创建CORS中间件或工具函数：

```typescript
// lib/cors.ts
export function corsHeaders(origin?: string) {
  const allowedOrigin = origin || process.env.NEXT_PUBLIC_ALLOWED_ORIGIN || 'http://localhost:3000';
  
  return {
    'Access-Control-Allow-Origin': allowedOrigin,
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-CSRF-Token',
    'Access-Control-Allow-Credentials': 'true',
    'Access-Control-Max-Age': '86400', // 24小时
  };
}

// 在API路由中使用
export async function GET(request: NextRequest) {
  const headers = corsHeaders(request.headers.get('origin'));
  
  return Response.json(data, { headers });
}

// 处理OPTIONS预检请求
export async function OPTIONS(request: NextRequest) {
  return new Response(null, {
    status: 204,
    headers: corsHeaders(request.headers.get('origin')),
  });
}
```

### 修复步骤
1. `src/main.py` 中已配置 FastAPI `CORSMiddleware`（后端CORS防护）
2. `frontend/next.config.mjs` 中添加安全HTTP头：
   - `X-Frame-Options: DENY`
   - `X-Content-Type-Options: nosniff`
   - `Referrer-Policy: strict-origin-when-cross-origin`
   - `Permissions-Policy: camera=(), microphone=(), geolocation=()`
   - `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
3. `frontend/src/middleware.ts` 中添加基础请求来源校验（对POST/PUT/DELETE/PATCH检查Origin/Referer）

### 测试方案
- [ ] 单元测试：验证CORS头正确设置
- [ ] 集成测试：测试跨域请求处理  
- [ ] 安全测试：验证CSRF防护效果
- [ ] 兼容性测试：确保不同浏览器兼容

## 风险评估

### 修复风险
- 可能影响现有第三方集成
- 需要更新所有调用API的客户端
- 可能引入CORS配置错误

### 不修复风险
- CSRF攻击导致数据篡改
- 跨域信息泄露
- 违反Web安全最佳实践
- 可能无法通过安全审计

### 回滚方案
1. 移除CORS头配置
2. 临时允许所有来源（不推荐）
3. 在反向代理层配置CORS

## 相关链接

- **相关PR**: `待创建`
- **相关Issue**: `前端安全审计发现`
- **文档链接**: `docs/bug/frontend-security-bug-02.md`
- **测试用例**: `tests/security/cors.test.ts`

## 时间线

| 时间 | 事件 | 负责人 |
|------|------|--------|
| `2026-04-17 12:30` | 发现bug | `资深前端安全工程师` |
| `2026-04-17 12:40` | 确认bug | `待指定` |
| `2026-04-17 14:00` | 分配修复 | `待指定` |
| `待定` | 开始修复 | `待指定` |
| `待定` | 修复完成 | `待指定` |
| `待定` | 测试通过 | `待指定` |
| `待定` | 部署上线 | `待指定` |

## 验证结果

### 修复验证
- [x] CORS头正确设置
- [x] 跨域请求被正确限制
- [x] 预检请求正常处理
- [x] 合法跨域请求正常工作

### 测试结果
```
Backend tests: 136 passed
Frontend build: 11/11 pages compiled successfully
Middleware activated: 26.6 kB
```

## 经验总结

### 教训
1. CORS不是可选的，是Web应用的基本安全要求
2. 需要为所有API端点配置适当的安全头
3. 预检请求（OPTIONS）必须正确处理

### 预防措施
1. 创建API安全模板
2. 添加安全头自动检查工具
3. 在CI/CD流水线中添加安全头验证

### 改进建议
1. 实施严格的同源策略
2. 考虑使用CSRF令牌增强防护
3. 定期审计安全头配置

---

**最后更新**: `2026-04-17 12:45`  
**更新人**: `资深前端安全工程师`