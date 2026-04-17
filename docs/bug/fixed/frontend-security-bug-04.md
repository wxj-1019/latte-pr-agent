# Bug报告模板

**Bug ID**: `FSEC-004`  
**发现日期**: `2026-04-17`  
**报告人**: `资深前端安全工程师`  
**严重程度**: `🟡 中`  
**状态**: `🟡 待修复`

---

## 基本信息

| 字段 | 内容 |
|------|------|
| **Bug标题** | `XSS漏洞风险：直接渲染用户内容未转义` |
| **相关模块** | `Diff查看器、代码显示组件` |
| **影响版本** | `所有版本` |
| **发现环境** | `开发/测试环境` |
| **复现概率** | `高（如果恶意内容存在）` |

## 问题描述

### 现象
Diff查看器直接渲染diff内容，没有对HTML特殊字符进行转义，存在跨站脚本（XSS）攻击风险。

### 影响范围
- 代码diff显示功能
- 审查详情页面
- 任何显示代码变更的组件
- 可能影响所有查看代码diff的用户

### 业务影响
如果攻击者能够提交包含恶意脚本的代码变更，其他用户在查看diff时可能执行恶意脚本。

## 技术详情

### 相关文件
```
文件路径:行号
- `frontend/src/app/dashboard/reviews/[id]/components/diff-viewer.tsx:49-137`
- 第127行：直接渲染line.content
```

### 问题代码
```typescript
export function DiffViewer({ file, findings, onLineClick, selectedLine }: DiffViewerProps) {
  // ... 解析diff内容
  
  return (
    <div className="rounded-latte-xl bg-latte-bg-deep border border-latte-text-primary/5 overflow-hidden">
      {/* ... */}
      <tbody>
        {lines.map((line, idx) => {
          return (
            <tr key={idx}>
              {/* ... */}
              <td className={cn("px-3 py-0.5 whitespace-pre")}>
                {line.content || " "} {/* 危险：直接渲染，未转义HTML */}
              </td>
            </tr>
          );
        })}
      </tbody>
    </div>
  );
}
```

### 问题分析
1. **直接渲染**: 使用`{line.content}`直接渲染，React默认不转义JSX中的变量
2. **HTML注入**: 如果`line.content`包含`<script>alert('xss')</script>`，脚本会被执行
3. **攻击场景**: 攻击者提交包含恶意脚本的代码，其他用户查看时触发
4. **影响严重**: XSS可以窃取会话cookie、重定向用户、执行未授权操作

### 根本原因
假设diff内容只包含纯文本，没有考虑恶意内容注入的可能性。

## 修复方案

### 建议修复
```typescript
import DOMPurify from 'dompurify';

// 方法1：使用DOMPurify清理HTML
function sanitizeHtml(content: string): string {
  return DOMPurify.sanitize(content, {
    ALLOWED_TAGS: [], // 不允许任何HTML标签
    ALLOWED_ATTR: [], // 不允许任何属性
    KEEP_CONTENT: true, // 保留文本内容
  });
}

// 方法2：手动转义HTML特殊字符
function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// 方法3：使用React的dangerouslySetInnerHTML（不推荐）
// 方法4：使用专门的代码高亮库（如shiki、prism）

// 在组件中使用
export function DiffViewer({ file, findings, onLineClick, selectedLine }: DiffViewerProps) {
  // ... 解析diff内容
  
  return (
    // ...
    <td className={cn("px-3 py-0.5 whitespace-pre font-mono")}>
      <code className="text-sm">
        {escapeHtml(line.content) || " "} {/* 安全：转义HTML */}
      </code>
    </td>
    // ...
  );
}
```

### 修复步骤
1. 创建HTML转义工具函数`lib/security.ts`
2. 更新DiffViewer组件使用转义后的内容
3. 检查其他可能渲染用户内容的组件
4. 添加XSS防护测试
5. 考虑使用代码高亮库增强安全性

### 测试方案
- [ ] 单元测试：验证HTML转义功能
- [ ] 安全测试：注入XSS payload验证防护效果  
- [ ] 集成测试：确保diff显示功能正常
- [ ] 回归测试：验证性能无影响

## 风险评估

### 修复风险
- 可能影响代码高亮或特殊字符显示
- 需要更新所有渲染用户内容的组件
- 可能增加包大小（如果引入DOMPurify）

### 不修复风险
- XSS攻击导致用户数据泄露
- 会话劫持风险
- 违反Web安全最佳实践
- 可能无法通过安全合规审计

### 回滚方案
1. 恢复直接渲染
2. 在显示前添加内容过滤
3. 使用iframe沙箱隔离

## 相关链接

- **相关PR**: `待创建`
- **相关Issue**: `前端安全审计发现`
- **文档链接**: `docs/bug/frontend-security-bug-04.md`
- **测试用例**: `tests/security/xss-protection.test.ts`

## 时间线

| 时间 | 事件 | 负责人 |
|------|------|--------|
| `2026-04-17 12:30` | 发现bug | `资深前端安全工程师` |
| `2026-04-17 13:00` | 确认bug | `待指定` |
| `2026-04-17 16:00` | 分配修复 | `待指定` |
| `待定` | 开始修复 | `待指定` |
| `待定` | 修复完成 | `待指定` |
| `待定` | 测试通过 | `待指定` |
| `待定` | 部署上线 | `待指定` |

## 验证结果

### 修复验证
- [ ] XSS payload被正确转义
- [ ] 代码显示功能正常
- [ ] 特殊字符正确显示
- [ ] 性能无显著下降

### 测试结果
```
待测试完成后填写
```

## 经验总结

### 教训
1. 永远不要信任用户提供的内容
2. 所有渲染用户内容的场景都需要XSS防护
3. React的JSX插值不提供完整的XSS防护

### 预防措施
1. 建立内容安全渲染规范
2. 添加自动XSS检测工具
3. 定期进行安全代码审查

### 改进建议
1. 实施CSP（Content Security Policy）
2. 使用专门的代码高亮和安全显示库
3. 添加输入内容的安全扫描

---

**最后更新**: `2026-04-17 13:05`  
**更新人**: `资深前端安全工程师`