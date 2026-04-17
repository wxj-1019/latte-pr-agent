# Bug报告模板

**Bug ID**: `FSEC-003`  
**发现日期**: `2026-04-17`  
**报告人**: `资深前端安全工程师`  
**严重程度**: `🔴 高`  
**状态**: `🟡 待修复`

---

## 基本信息

| 字段 | 内容 |
|------|------|
| **Bug标题** | `SSE端点缺少认证和速率限制，存在DDoS和信息泄露风险` |
| **相关模块** | `前端SSE（Server-Sent Events）` |
| **影响版本** | `所有版本` |
| **发现环境** | `开发/测试环境` |
| **复现概率** | `100%` |

## 问题描述

### 现象
Server-Sent Events端点完全开放，没有认证机制和速率限制，任何人都可以连接并接收实时更新。

### 影响范围
- `/api/sse/reviews` SSE流端点
- 实时审查状态更新功能
- 服务器资源消耗
- 潜在的信息泄露

### 业务影响
攻击者可以：
1. 发起大量SSE连接导致DDoS攻击
2. 监听实时审查状态，获取敏感信息
3. 消耗服务器资源，影响正常用户

## 技术详情

### 相关文件
```
文件路径:行号
- `frontend/src/app/api/sse/reviews/route.ts:1-36`
- `frontend/src/hooks/use-sse.ts:1-50`
```

### 问题代码
```typescript
export async function GET(request: NextRequest) {
  // 没有认证检查
  // 没有速率限制
  // 任何人都可以连接
  
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      // 每8秒发送一次模拟数据
      const interval = setInterval(() => {
        const data = JSON.stringify({
          review_id: 42,
          status: "running",
          timestamp: new Date().toISOString(),
        });
        controller.enqueue(encoder.encode(`data: ${data}\n\n`));
      }, 8000);
      
      request.signal.addEventListener("abort", () => {
        clearInterval(interval);
        controller.close();
      });
    },
  });
  
  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
```

### 问题分析
1. **认证缺失**: 没有验证用户身份，任何人都可以连接SSE流
2. **速率限制缺失**: 没有限制单个IP或用户的连接数
3. **资源消耗**: 每个SSE连接保持长连接，消耗服务器资源
4. **信息泄露**: 审查状态可能包含敏感信息

### 根本原因
SSE端点被视为内部使用，没有考虑安全防护措施。

## 修复方案

### 建议修复
```typescript
import { rateLimiter } from "@/lib/rate-limiter";
import { authenticateRequest } from "@/lib/auth";

export async function GET(request: NextRequest) {
  // 1. 认证检查
  const user = await authenticateRequest(request);
  if (!user) {
    return new Response('Unauthorized', { status: 401 });
  }
  
  // 2. 速率限制检查
  const clientId = user.id || request.ip;
  if (!rateLimiter.check(clientId, 'sse')) {
    return new Response('Too Many Requests', { 
      status: 429,
      headers: { 'Retry-After': '60' }
    });
  }
  
  // 3. 只返回用户有权访问的数据
  const reviewId = request.nextUrl.searchParams.get('review_id');
  if (reviewId && !user.canAccessReview(parseInt(reviewId))) {
    return new Response('Forbidden', { status: 403 });
  }
  
  // 4. 添加连接超时
  const timeout = setTimeout(() => {
    // 30分钟后自动关闭连接
  }, 30 * 60 * 1000);
  
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      // 只发送用户相关的更新
      const interval = setInterval(() => {
        const updates = getRelevantUpdates(user.id, reviewId);
        updates.forEach(update => {
          const data = JSON.stringify(update);
          controller.enqueue(encoder.encode(`data: ${data}\n\n`));
        });
      }, 5000); // 降低频率
      
      request.signal.addEventListener("abort", () => {
        clearInterval(interval);
        clearTimeout(timeout);
        controller.close();
      });
    },
  });
  
  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no", // 禁用代理缓冲
    },
  });
}
```

### 修复步骤
1. 创建认证中间件`lib/auth.ts`
2. 实现速率限制器`lib/rate-limiter.ts`
3. 更新SSE端点添加安全防护
4. 添加连接管理和超时机制
5. 实现基于权限的数据过滤

### 测试方案
- [ ] 单元测试：验证认证和速率限制
- [ ] 集成测试：测试SSE连接安全性  
- [ ] 压力测试：验证DDoS防护效果
- [ ] 安全测试：进行SSE端点渗透测试

## 风险评估

### 修复风险
- 可能影响现有客户端的连接
- 需要实现用户认证系统
- 可能增加服务器复杂度

### 不修复风险
- DDoS攻击导致服务不可用
- 敏感信息泄露
- 服务器资源被恶意消耗
- 违反数据隐私法规

### 回滚方案
1. 移除认证和速率限制
2. 临时禁用SSE功能
3. 在负载均衡器层面添加防护

## 相关链接

- **相关PR**: `待创建`
- **相关Issue**: `前端安全审计发现`
- **文档链接**: `docs/bug/frontend-security-bug-03.md`
- **测试用例**: `tests/security/sse-security.test.ts`

## 时间线

| 时间 | 事件 | 负责人 |
|------|------|--------|
| `2026-04-17 12:30` | 发现bug | `资深前端安全工程师` |
| `2026-04-17 12:50` | 确认bug | `待指定` |
| `2026-04-17 15:00` | 分配修复 | `待指定` |
| `待定` | 开始修复 | `待指定` |
| `待定` | 修复完成 | `待指定` |
| `待定` | 测试通过 | `待指定` |
| `待定` | 部署上线 | `待指定` |

## 验证结果

### 修复验证
- [ ] 未认证用户无法连接SSE
- [ ] 速率限制有效防止滥用
- [ ] 只返回用户有权访问的数据
- [ ] 连接超时机制正常工作

### 测试结果
```
待测试完成后填写
```

## 经验总结

### 教训
1. 实时通信端点需要更强的安全防护
2. 长连接服务容易成为DDoS攻击目标
3. 需要基于权限过滤实时数据

### 预防措施
1. 为所有实时通信端点制定安全规范
2. 实施统一的认证和授权中间件
3. 添加监控和告警机制

### 改进建议
1. 考虑使用WebSocket替代SSE以获得更好控制
2. 实现连接池管理
3. 添加实时通信审计日志

---

**最后更新**: `2026-04-17 12:55`  
**更新人**: `资深前端安全工程师`