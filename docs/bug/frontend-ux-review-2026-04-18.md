# 前端 UX 改进审查报告

> 报告日期：2026-04-18
> 审查范围：19 项前端 UX 改进实现（高 6 项 + 中 7 项 + 低 6 项）
> 审查人：Claude Code

---

## 概述

对 19 项已落地的前端 UX 改进进行代码级审查，发现 **5 项实际 Bug** 和 **2 项代码缺陷/不完整功能**。按严重程度排序如下。

---

## 🔴 Bug 1：`reviews/page.tsx` 错误状态 UI 永远无法触发（变量未解构）

### 严重程度：**高**

### 问题描述

审查列表页实现了 API 失败时的错误卡片 + 重试按钮，但 `error` 变量从未从 `useReviews` hook 中解构出来。第 128 行 `error ? (...)` 引用的 `error` 是 `undefined`，导致错误状态 UI 永远不会渲染。用户在 API 失败时只能看到无限转圈的 loading 骨架屏。

### 涉及的文件

- `frontend/src/app/dashboard/reviews/page.tsx`（第 41-53 行、第 128 行）

### 当前代码（问题所在）

```tsx
// 第 41-53 行：解构时遗漏了 error
const {
  reviews,
  total,
  page: currentPage,
  pageSize,
  isLoading,
  mutate,
} = useReviews({
  status: status === "all" ? undefined : status,
  repo: debouncedSearch || undefined,
  risk: risk === "all" ? undefined : risk,
  page,
});

// 第 128 行：使用了未声明的 error
{error ? (
  <FadeInUp delay={0.1}>
    <div className="flex flex-col items-center justify-center py-20 text-latte-text-tertiary">
      <p className="text-lg font-medium">加载失败</p>
      <p className="text-sm mt-1">{error.message || "无法获取审查列表"}</p>
      <Button variant="secondary" size="sm" className="mt-4" onClick={() => mutate()}>
        <RefreshCw size={14} className="mr-1.5" />
        重试
      </Button>
    </div>
  </FadeInUp>
) : isLoading ? (...)
```

### 影响分析

| 场景 | 后果 |
|------|------|
| API 返回 500 | 页面永远显示 loading 骨架屏，用户不知道出了错 |
| 网络断开 | 同上，无错误反馈，无重试入口 |
| 长期运行 | 用户可能认为系统卡死，直接关闭页面 |

### 修复方案

在 `useReviews` 解构中添加 `error`：

```tsx
const {
  reviews,
  total,
  page: currentPage,
  pageSize,
  isLoading,
  error,   // ← 添加此行
  mutate,
} = useReviews({...});
```

---

## 🔴 Bug 2：`useReviewDetail` 未返回 `mutate`，SSE 实时更新完全失效

### 严重程度：**高**

### 问题描述

审查详情页通过 SSE 订阅实时更新，当收到对应 `review_id` 的更新时调用 `mutateReview()` 和 `mutateFindings()` 刷新数据。但 `useReviewDetail` hook **没有返回 `mutate`**，`mutateReview` 实际是 `undefined`，调用时会抛出 `TypeError: mutateReview is not a function`。这导致 SSE 实时更新功能完全失效。

### 涉及的文件

- `frontend/src/hooks/use-reviews.ts`（第 33-44 行）
- `frontend/src/app/dashboard/reviews/[id]/page.tsx`（第 69 行、第 87 行）

### 当前代码（问题所在）

```tsx
// use-reviews.ts 第 33-44 行
export function useReviewDetail(id: number) {
  const { data, error, isLoading } = useSWR<Review>(
    id ? `/api/reviews/${id}` : null,
    () => api.getReviewDetail(id)
  );
  return {
    review: data,
    isLoading,
    error,
    // ← 缺少 mutate
  };
}

// reviews/[id]/page.tsx 第 69 行
const {
  review,
  isLoading: reviewLoading,
  error: reviewError,
  mutate: mutateReview,   // ← undefined！
} = useReviewDetail(reviewId);

// 第 87 行
if (update.review_id === reviewId) {
  mutateReview();   // ← TypeError!
  mutateFindings();
}
```

### 影响分析

| 场景 | 后果 |
|------|------|
| 审查状态从 running → completed | 详情页不自动刷新，用户需手动 F5 |
| 新的 finding 产生 | 右侧发现面板不更新 |
| 整个 SSE 实时更新价值 | 完全丧失，沦为摆设 |

### 修复方案

在 `useReviewDetail` 中返回 `mutate`：

```tsx
export function useReviewDetail(id: number) {
  const { data, error, isLoading, mutate } = useSWR<Review>(...);
  return {
    review: data,
    isLoading,
    error,
    mutate,   // ← 添加此行
  };
}
```

---

## 🟡 Bug 3：SSE Provider 组件卸载后残留重连定时器

### 严重程度：**中**

### 问题描述

`use-sse.tsx` 的 cleanup 函数先关闭 EventSource，再将其设为 `null`。但 `EventSource.close()` 会触发 `onerror` 回调，而 `onerror` 中设置了 `setTimeout(() => connect(), delay)`。由于 cleanup 中虽然清除了 `reconnectTimerRef`，但 `onerror` 中的 `setTimeout` 是另一个独立的定时器赋值给 `reconnectTimerRef.current`。当组件卸载时，`onerror` 执行后会把新的定时器写入 `reconnectTimerRef.current`，但此时组件已经卸载，后续 `connect()` 执行时会产生无效的状态更新（`setStatus` 在已卸载组件上）。

更精确地说：cleanup 执行顺序是 `clearTimeout(reconnectTimerRef)` → `es.close()` → `esRef.current = null`。`es.close()` 触发 `onerror`，`onerror` 中 `esRef.current = null`（已经是 null），然后 `setStatus("disconnected")` 执行（状态更新在已卸载组件上无危害但会 console warning），最后 `setTimeout(connect, delay)` 创建一个新的定时器。这个定时器在组件卸载后仍然存活，会尝试重新创建 EventSource。

### 涉及的文件

- `frontend/src/hooks/use-sse.tsx`（第 60-72 行、第 75-83 行）

### 当前代码（问题所在）

```tsx
// onerror 回调（第 60-72 行）
es.onerror = () => {
  es.close();
  esRef.current = null;
  setStatus("disconnected");

  if (retryCountRef.current < MAX_RETRIES) {
    const delay = Math.min(BASE_DELAY_MS * 2 ** retryCountRef.current, 30000);
    retryCountRef.current++;
    reconnectTimerRef.current = setTimeout(() => {
      connect();   // ← 组件卸载后仍可能执行
    }, delay);
  }
};

// cleanup（第 75-83 行）
useEffect(() => {
  connect();
  return () => {
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
  };
}, [connect]);
```

### 影响分析

| 场景 | 后果 |
|------|------|
| 用户从 Dashboard 离开到 Landing 页 | 后台仍尝试建立 SSE 连接，浪费资源 |
| 频繁路由切换 | 累积多个死掉的 EventSource 连接尝试 |
| React StrictMode 双渲染 | 更易触发，开发模式下定时器泄漏明显 |

### 修复方案

添加一个 `isMounted` 标志，阻止卸载后的状态更新和重连：

```tsx
export function SSEProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SSEStatus>("disconnected");
  const subscribersRef = useRef<Set<...>>(new Set());
  const esRef = useRef<EventSource | null>(null);
  const retryCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);   // ← 新增

  const connect = useCallback(() => {
    if (!isMountedRef.current) return;   // ← 新增
    // ...
    es.onopen = () => {
      if (!isMountedRef.current) return;   // ← 新增
      retryCountRef.current = 0;
      setStatus("connected");
    };
    es.onerror = () => {
      es.close();
      esRef.current = null;
      if (!isMountedRef.current) return;   // ← 新增
      setStatus("disconnected");
      if (retryCountRef.current < MAX_RETRIES) {
        // ...
        reconnectTimerRef.current = setTimeout(() => {
          if (isMountedRef.current) connect();   // ← 新增
        }, delay);
      }
    };
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    connect();
    return () => {
      isMountedRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [connect]);
  // ...
}
```

---

## 🟡 Bug 4：侧边栏"首页"链接在所有子页面都高亮

### 严重程度：**低**

### 问题描述

`sidebar.tsx` 使用 `pathname.startsWith(item.href)` 判断 active 状态。由于 `/dashboard` 是 `/dashboard/reviews` 等所有子路径的前缀，`pathname.startsWith("/dashboard")` 对所有 Dashboard 页面都返回 `true`，导致"首页"链接一直处于高亮状态。

### 涉及的文件

- `frontend/src/components/dashboard/sidebar.tsx`（第 34 行）

### 当前代码（问题所在）

```tsx
<Link
  key={item.href}
  href={item.href}
  className={cn(
    "latte-sidebar-item",
    pathname.startsWith(item.href) && "active"   // ← "/dashboard/reviews".startsWith("/dashboard") === true
  )}
>
```

### 修复方案

对 `/dashboard` 做精确匹配，其他路径保持前缀匹配：

```tsx
className={cn(
  "latte-sidebar-item",
  (item.href === "/dashboard" ? pathname === item.href : pathname.startsWith(item.href)) && "active"
)}
```

---

## 🟡 Bug 5：搜索词变化时不重置页码

### 严重程度：**低**

### 问题描述

审查列表页的 `useEffect` 只在 `status` 和 `risk` 变化时重置页码到第 1 页，但没有监听 `debouncedSearch` 的变化。如果用户在第 3 页时输入新的搜索关键词，页码仍停留在第 3 页，而新关键词的结果可能不足 3 页，导致显示"未找到审查记录"的空状态，用户需要手动点回第 1 页。

### 涉及的文件

- `frontend/src/app/dashboard/reviews/page.tsx`（第 59-61 行）

### 当前代码（问题所在）

```tsx
useEffect(() => {
  setPage(1);
}, [status, risk]);
// ↑ 缺少 debouncedSearch
```

### 修复方案

将 `debouncedSearch` 加入依赖数组：

```tsx
useEffect(() => {
  setPage(1);
}, [status, risk, debouncedSearch]);
```

---

## 🟢 缺陷 6：`layout.tsx` 向 `Header` 传递了未使用的 prop

### 严重程度：**低**（代码异味，TypeScript 严格模式下会编译失败）

### 问题描述

`dashboard/layout.tsx` 通过 `<Header sseStatus={status} />` 向 `Header` 传递 `sseStatus` prop，但 `Header` 组件的签名是 `export function Header()`（无参数），内部自己调用了 `useSSE()` 获取状态。`sseStatus` prop 被完全忽略。在 TypeScript `strict` 模式下，这会编译报错：`Property 'sseStatus' does not exist on type 'IntrinsicAttributes & { children?: ReactNode; }'`。

### 涉及的文件

- `frontend/src/app/dashboard/layout.tsx`（第 14 行）
- `frontend/src/components/dashboard/header.tsx`（第 10 行）

### 修复方案

**方案 A**：移除 `layout.tsx` 中的 `sseStatus` prop，让 `Header` 自己获取状态：

```tsx
// layout.tsx
<Header />
```

**方案 B**：修改 `Header` 接收 `sseStatus` prop 并移除内部的 `useSSE()` 调用（避免在 `DashboardInner` 和 `Header` 中重复调用 `useSSE`，虽然 Context 本身开销不大）：

```tsx
// header.tsx
export function Header({ sseStatus }: { sseStatus: SSEStatus }) {
  // 移除 const { status, reconnect } = useSSE();
  // 使用 sseStatus 替代 status
}
```

> 推荐方案 A，保持简单。

---

## 🟢 缺陷 7：全局加载进度条（NProgress）组件缺失

### 严重程度：**低**（功能不完整）

### 问题描述

`globals.css` 中已定义了 NProgress 的样式覆盖（第 201-207 行），但 `frontend/src/components/dashboard/progress-bar.tsx` 文件不存在，`layout.tsx` 也未导入或挂载任何进度条组件。低优先级改进 #15 "全局加载进度条" 实际上只完成了 CSS 样式，组件逻辑和路由集成均未实现。

### 涉及的文件

- `frontend/src/app/globals.css`（第 201-207 行）
- `frontend/src/components/dashboard/progress-bar.tsx`（**不存在**）
- `frontend/src/app/dashboard/layout.tsx`

### 缺失的实现内容

1. `progress-bar.tsx` 组件（包装 NProgress 的 start/done 调用）
2. 在 `layout.tsx` 中集成（或利用 Next.js App Router 的 `loading.tsx`）
3. 路由变化时自动触发 NProgress

---

## 验证方式

| Bug | 验证方式 |
|-----|----------|
| Bug 1（error 未解构） | 在 DevTools Network 中 block `/reviews` API 请求，确认是否显示错误卡片 |
| Bug 2（mutate 未返回） | 打开审查详情页，触发一次 SSE 更新，观察控制台是否抛出 TypeError |
| Bug 3（SSE 定时器泄漏） | React DevTools Profiler 中观察组件卸载后是否仍有 EventSource 连接尝试 |
| Bug 4（侧边栏高亮） | 进入 `/dashboard/reviews`，观察"首页"是否同时高亮 |
| Bug 5（搜索不重置页码） | 翻到第 2 页，输入搜索词，确认页码是否回到第 1 页 |
| 缺陷 6（Header prop） | 运行 `tsc --noEmit`，确认是否报错 |
| 缺陷 7（NProgress） | 检查 `frontend/src/components/dashboard/` 目录下是否存在 `progress-bar.tsx` |

---

## 修复优先级建议

| 优先级 | 问题 | 原因 |
|:------:|------|------|
| **P0** | Bug 1：`error` 未解构 | API 失败时用户无感知，核心功能体验断裂 |
| **P0** | Bug 2：`mutate` 未返回 | SSE 实时更新完全失效，功能退化 |
| **P1** | Bug 3：SSE 定时器泄漏 | 路由切换后资源泄漏，长期运行性能影响 |
| **P2** | Bug 4：侧边栏高亮 | UI 误导，纯体验问题 |
| **P2** | Bug 5：搜索不重置页码 | 用户体验问题，操作路径不自然 |
| **P2** | 缺陷 6：Header prop 不一致 | TypeScript 严格模式下编译失败 |
| **P3** | 缺陷 7：NProgress 缺失 | 功能不完整，不影响现有功能 |

---

## 其他实现良好的改进（无需修复）

以下改进实现正确，未发现明显问题：

| # | 改进项 | 评价 |
|---|--------|------|
| 3 | 配置页破坏性操作确认 | `ConfirmDialog` + `requestConfirm` 实现正确，Escape 关闭工作正常 |
| 4 | alert() → Toast | Config/Prompts 页已全部使用 `useToast`，无残留 `alert()` |
| 5 | 饼图假数据 → 空状态 | `categoryDistribution` 为空时正确显示"暂无分类数据" |
| 6 | FindingCard 误报确认 | 二次确认弹窗实现正确，反馈 API 调用完整 |
| 10 | Prompt 内容预览 | 展开/收起状态管理正确，无性能问题 |
| 11 | 配置页仓库选择器 | 从 `/repos` API 获取列表，切换时正确加载对应配置 |
| 12 | 分析页语言/文件名同步 | `languageDefaults` 映射正确，切换时自动更新 filename |
| 13 | 审查详情虚拟滚动 | `LazyDiffViewer` 的 `IntersectionObserver` 实现正确，`rootMargin: 200px` 预加载合理 |
| 14 | 自定义 404 页面 | `not-found.tsx` 简洁有效，主题一致 |
| 16 | 侧边栏文字标签 | 宽度 180px，图标+文字显示正确 |
| 17 | 文件树默认折叠 | `depth === 0` 默认展开，更深层级默认折叠，符合要求 |
| 18 | DiffViewer 双列行号 | 旧行号 + 新行号 + 标记列（+/−/空格）实现完整 |
| 19 | 键盘快捷键 | `/` 聚焦搜索、`Escape` 关闭弹窗均正常工作 |

---

*报告生成时间：2026-04-18*
