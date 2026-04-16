# Latte PR Agent 前端执行方案

> **文档定位**：将 `frontend-design-final.md` 的设计规范转化为可落地的工程任务书。  
> **适用对象**：前端开发工程师、项目经理、技术负责人。  
> **版本**：v1.0

---

## 一、项目概述与目标

### 1.1 项目定位
为 Latte PR Agent（企业级 AI 代码审查系统）构建一套与后端能力匹配的前端界面。前端不仅是数据的展示层，更是品牌理念的延伸——通过「Latte Art meets Precision Engineering」的视觉语言，将开发者工具从冰冷的工业感升华为有温度、有匠心的产品体验。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| **功能完整** | 覆盖 Landing Page（营销）+ Dashboard（Reviews / Metrics / Config / Prompts）全部页面 |
| **风格统一** | 严格遵循 Latte 配色系统，拒绝大众蓝紫渐变，所有组件视觉一致 |
| **实时响应** | Dashboard 支持 SSE 实时状态推送，反映后端 Celery 工作流 |
| **性能达标** | Lighthouse Performance ≥ 90，首屏加载时间 < 2s（4G 网络） |
| **可维护性** | 组件化开发，TypeScript 类型覆盖，文档与代码同步 |

### 1.3 技术栈（锁定）

| 层级 | 技术 | 版本要求 |
|------|------|----------|
| 框架 | Next.js (App Router) | 14.x |
| 语言 | TypeScript | 5.x |
| 样式 | Tailwind CSS | 3.4+ |
| 动画 | Framer Motion | 11.x |
| 图表 | Recharts | 2.x |
| 代码高亮 | Shiki | 1.x |
| 图标 | Lucide React | latest |
| 数据获取 | SWR | 2.x |
| 包管理 | pnpm（推荐）| 8.x |

---

## 二、阶段划分与里程碑

项目划分为 **4 个里程碑（M1 → M4）**，每个里程碑有明确的交付物和验收标准。建议采用 2 周为一个 Sprint。

```
Week  1-2 : M1 基础骨架 + 主题系统
Week  3-4 : M2 Dashboard 核心（Reviews 列表 + 详情）
Week  5-6 : M3 实时增强（SSE + Metrics + Prompts/Config）
Week  7-8 : M4 Landing Page + 性能优化 + 收尾验收
```

---

## 三、环境搭建（M1 第 1-2 天）

### 3.1 项目初始化

```bash
# 1. 创建 Next.js 14 项目（选择 App Router + Tailwind + TypeScript）
npx create-next-app@14 latte-pr-agent-web --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --use-pnpm

cd latte-pr-agent-web

# 2. 安装核心依赖
pnpm add framer-motion recharts swr lucide-react clsx tailwind-merge

# 3. 安装 Shiki（代码高亮）
pnpm add shiki

# 4. 安装开发依赖（可选但推荐）
pnpm add -D @types/node prettier prettier-plugin-tailwindcss
```

### 3.2 目录结构初始化

在项目根目录执行：

```bash
mkdir -p src/app/dashboard/reviews/\[id\]/components
mkdir -p src/app/dashboard/metrics
mkdir -p src/app/dashboard/config
mkdir -p src/app/dashboard/prompts
mkdir -p src/app/api/reviews
mkdir -p src/app/api/findings
mkdir -p src/app/api/metrics
mkdir -p src/app/api/config/\[repoId\]
mkdir -p src/app/api/prompts
mkdir -p src/app/api/sse/reviews
mkdir -p src/components/landing
mkdir -p src/components/dashboard
mkdir -p src/components/ui
mkdir -p src/components/motion
mkdir -p src/hooks
mkdir -p src/lib
mkdir -p src/types
mkdir -p public/assets/icons
```

### 3.3 Tailwind 配置扩展

将以下 Latte 主题变量扩展到 `tailwind.config.ts`：

```ts
// tailwind.config.ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        latte: {
          "bg-deep": "#030201",
          "bg-primary": "#0A0806",
          "bg-secondary": "#14110E",
          "bg-tertiary": "#1E1A16",
          "bg-hover": "#28231E",
          "text-primary": "#F5E6D3",
          "text-secondary": "#C4B5A5",
          "text-tertiary": "#8B7D6D",
          "text-muted": "#5C5246",
          accent: "#E8DCC4",
          "accent-hover": "#F0E8D8",
          gold: "#C4A77D",
          "gold-dim": "#8F7650",
          rose: "#D4A59A",
          "rose-dim": "#A67B72",
          success: "#7D8471",
          warning: "#B85C38",
          critical: "#8B3A3A",
          info: "#9A8B7A",
        },
      },
      fontFamily: {
        display: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"SF Pro Display"',
          '"Helvetica Neue"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          "sans-serif",
        ],
        text: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"SF Pro Text"',
          '"Helvetica Neue"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          "sans-serif",
        ],
        mono: ['"SF Mono"', '"JetBrains Mono"', '"Fira Code"', "monospace"],
      },
      borderRadius: {
        "latte-sm": "8px",
        "latte-md": "12px",
        "latte-lg": "20px",
        "latte-xl": "24px",
      },
      boxShadow: {
        "latte-sm": "0 2px 8px rgba(0, 0, 0, 0.3)",
        "latte-md": "0 4px 24px rgba(0, 0, 0, 0.4)",
        "latte-lg": "0 12px 48px rgba(0, 0, 0, 0.5)",
        "latte-gold": "0 8px 24px rgba(196, 167, 125, 0.15)",
      },
      transitionTimingFunction: {
        "apple-smooth": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
```

### 3.4 全局 CSS 注入

将 `docs/frontend-assets/latte-theme.css` 中的核心变量和基础样式复制到 `src/app/globals.css`，并覆盖 Next.js 默认的 light theme 样式。

---

## 四、里程碑详细任务

### M1：基础骨架 + 主题系统（Week 1-2）

#### 目标
搭建项目骨架，实现所有基础 UI 组件和动画工具，确保视觉系统可复用、可演示。

#### 任务清单

| 序号 | 任务 | 输出文件 | 验收标准 |
|------|------|----------|----------|
| M1-1 | 配置 Tailwind + 全局 CSS 主题变量 | `tailwind.config.ts`, `src/app/globals.css` | 所有 `--latte-*` 变量可用，页面背景为 `#0A0806`，文字为 `#F5E6D3` |
| M1-2 | 创建通用工具函数 | `src/lib/utils.ts` | 导出 `cn()` 函数，支持 Tailwind 类名合并 |
| M1-3 | 定义 TypeScript 类型 | `src/types/index.ts` | 定义 `Review`, `ReviewFinding`, `PRFile`, `MetricsData`, `PromptVersion` 等核心类型 |
| M1-4 | 开发 Button 组件 | `src/components/ui/button.tsx` | 支持 `primary/secondary/ghost` 三种变体，胶囊圆角，hover 有金色光晕 |
| M1-5 | 开发 Badge 组件 | `src/components/ui/badge.tsx` | 支持 `success/warning/critical/info` 四种变体，带圆点 |
| M1-6 | 开发 GlassCard 组件 | `src/components/ui/glass-card.tsx` | 支持 `default/interactive/elevated/status` 变体，status 有左侧彩色边条 |
| M1-7 | 开发 Input 组件 | `src/components/ui/input.tsx` | focus 时边框变为金色并带外发光 |
| M1-8 | 开发 StatusBadge 组件 | `src/components/ui/status-badge.tsx` | 支持 5 种状态，`pending` 有脉冲动画，`running` 有旋转动画 |
| M1-9 | 开发 ConfidenceRing 组件 | `src/components/ui/confidence-ring.tsx` | SVG 圆环进度条，颜色按低/中/高自动映射，带发光效果 |
| M1-10 | 开发 RealtimeIndicator 组件 | `src/components/ui/realtime-indicator.tsx` | 三色状态点，有 Tooltip 提示 |
| M1-11 | 开发动画包装组件 | `src/components/motion/fade-in-up.tsx`, `stagger-container.tsx` | 使用 Framer Motion，支持 `prefers-reduced-motion` |
| M1-12 | Dashboard 布局框架 | `src/app/dashboard/layout.tsx`, `src/components/dashboard/sidebar.tsx`, `src/components/dashboard/header.tsx` | 64px Sidebar + Header 布局，Sidebar hover 图标发光 |

#### M1 验收 Demo
运行 `pnpm dev`，访问 `/dashboard/reviews`，应能看到：
- 正确的深色背景和暖色文字
- Sidebar 和 Header 布局正常
- 页面上放置若干 GlassCard、Button、Badge 的展示样例

---

### M2：Dashboard 核心（Week 3-4）

#### 目标
完成 Reviews 列表页和 Review 详情页（含 DiffViewer），实现前后端数据打通。

#### 后端依赖（需同步开发或 Mock）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/reviews` | GET | 支持 `status`, `repo`, `page` 查询参数 |
| `/api/reviews/:id` | GET | 返回 Review 详情 |
| `/api/reviews/:id/findings` | GET | 返回该 Review 的所有 Findings |
| `/api/findings/:id/feedback` | POST | 提交误报反馈 |

> **说明**：以上接口若后端暂未实现，M2 阶段先用 Next.js API Routes 写 Mock 数据（见 M2-1），不阻塞前端进度。

#### 任务清单

| 序号 | 任务 | 输出文件 | 验收标准 |
|------|------|----------|----------|
| M2-1 | 创建 API 客户端 + Mock 数据 | `src/lib/api.ts`, `src/lib/mock-data.ts` | 所有接口有 TypeScript 类型，Mock 数据覆盖常见状态 |
| M2-2 | 开发 useReviews Hook | `src/hooks/use-reviews.ts` | 使用 SWR，支持分页、过滤、刷新 |
| M2-3 | 开发 ReviewList 组件 | `src/components/dashboard/review-list.tsx` | 卡片式列表，hover 发光，StatusBadge 和风险徽章正确显示 |
| M2-4 | Reviews 列表页 | `src/app/dashboard/reviews/page.tsx` | 集成 Filter、Search、Pagination，数据来自 Hook |
| M2-5 | 开发 FileTree 组件 | `src/app/dashboard/reviews/[id]/components/file-tree.tsx` | 树形展开/折叠，文件名右侧显示 finding 数量徽章（颜色映射最高 severity） |
| M2-6 | 集成 Shiki 开发 DiffViewer | `src/app/dashboard/reviews/[id]/components/diff-viewer.tsx` | 正确渲染 diff，新增行绿底、删除行红底， finding 行右侧有金色竖线 |
| M2-7 | 开发 FindingPanel 组件 | `src/app/dashboard/reviews/[id]/components/finding-panel.tsx` | 展开显示描述、建议、ConfidenceRing、模型标签、False Positive 按钮 |
| M2-8 | Review 详情页组装 | `src/app/dashboard/reviews/[id]/page.tsx` | 三栏布局（20% / 50% / 30%），点击 Diff 行号可高亮对应 Finding |
| M2-9 | 页面切换动画 | `src/app/dashboard/reviews/[id]/page.tsx` | 使用 Framer Motion 的 `layoutId` 实现 Shared Element Transition（标题 + StatusBadge） |

#### M2 验收 Demo
- `/dashboard/reviews` 能滚动加载 Mock 数据，Filter 可用
- 点击 Review 卡片进入详情页，有平滑过渡动画
- Diff 视图能正确渲染多文件 diff，文件树可交互
- 点击 Finding 卡片的 False Positive 按钮，前端能调用 API（Mock 返回成功即可）

---

### M3：实时增强 + 完整 Dashboard（Week 5-6）

#### 目标
接入 SSE 实现实时状态更新，完成 Metrics、Config、Prompts 页面。

#### 后端依赖

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/sse/reviews` | SSE | 推送 Review 状态变更事件 |
| `/api/metrics` | GET | 支持 `range=7d\|30d\|90d` |
| `/api/config/:repoId` | GET/PUT | 项目配置读写 |
| `/api/prompts/versions` | GET/POST | Prompt 版本列表/创建 |
| `/api/prompts/optimize` | POST | 自动优化 Prompt |

#### 任务清单

| 序号 | 任务 | 输出文件 | 验收标准 |
|------|------|----------|----------|
| M3-1 | 开发 useSSE Hook | `src/hooks/use-sse.ts` | 封装 EventSource，支持自动重连（断线 3s 内重连） |
| M3-2 | 在 ReviewList 接入 SSE | `src/components/dashboard/review-list.tsx` | 收到状态变更后，对应卡片有状态流转动画（ pending→running 蓝色流动 / running→completed 绿色扫光 / failed 抖动） |
| M3-3 | Header 接入 RealtimeIndicator | `src/components/dashboard/header.tsx` | 显示 SSE 连接状态 |
| M3-4 | 开发 Metrics 图表组件 | `src/app/dashboard/metrics/page.tsx` | 顶部 4 个 KPI 卡片，中部 Recharts 折线图，底部饼图，配色全为 Latte 色系 |
| M3-5 | 开发 useMetrics Hook | `src/hooks/use-metrics.ts` | SWR 获取，支持 range 切换 |
| M3-6 | 开发 Config 页面 | `src/app/dashboard/config/page.tsx` | 可视化表单编辑 `.review-config.yml`（开关、列表、模型选择器） |
| M3-7 | 开发 Prompts 页面 | `src/app/dashboard/prompts/page.tsx` | Prompt 版本卡片列表，显示 active/baseline 状态、A/B 比例、准确率 |
| M3-8 | Dashboard 首页重定向 | `src/app/dashboard/page.tsx` | 默认重定向到 `/dashboard/reviews` |

#### M3 验收 Demo
- 模拟后端 SSE 推送，Dashboard 中 Review 卡片状态实时变化且动画正确
- `/dashboard/metrics` 能展示折线图和饼图，range 切换有加载态
- `/dashboard/config` 和 `/dashboard/prompts` 页面结构完整，表单可交互

---

### M4：Landing Page + 性能优化 + 收尾（Week 7-8）

#### 目标
完成营销官网，进行性能调优和最终验收。

#### 任务清单

| 序号 | 任务 | 输出文件 | 验收标准 |
|------|------|----------|----------|
| M4-1 | 开发 SteamParticles 背景 | `src/components/landing/steam-particles.tsx` | Canvas 粒子层，30-50 个金色/玫瑰色粒子缓慢上升，CPU 占用 < 5% |
| M4-2 | 开发 HeroSection | `src/components/landing/hero-section.tsx` | 主标题和副标题有 fade-in-up + blur 动画，背景渐变跟随鼠标移动 |
| M4-3 | 开发 BentoGrid | `src/components/landing/bento-grid.tsx` | 6 张功能卡片，桌面端不规则布局，移动端单列，hover 有发光 |
| M4-4 | 开发 DashboardPreview | `src/components/landing/dashboard-preview.tsx` | 3D 倾斜玻璃面板，hover 回正，内部展示 Mock Dashboard UI |
| M4-5 | 开发 TechSpecs + Footer | `src/app/page.tsx` | MacBook 风格的规格表，CTA 胶囊按钮有磨砂玻璃效果 |
| M4-6 | Landing Page 组装 | `src/app/page.tsx` | 完整 6 个 Section，滚动有视差效果 |
| M4-7 | 性能优化 | 全局 | 图片转 WebP/AVIF，组件懒加载，减少 JS Bundle |
| M4-8 | 可访问性检查 | 全局 | `prefers-reduced-motion` 下禁用粒子和位移动画，所有图片有 alt |
| M4-9 | Lighthouse 跑分 | 报告 | Performance ≥ 90，Accessibility ≥ 95，Best Practices ≥ 95 |

#### M4 验收标准
- 访问 `/` 能看到完整的 Landing Page，动画流畅
- 移动端（iPhone 14 Pro 尺寸）布局正常，Bento Grid 变为单列
- Lighthouse 报告截图存档

---

## 五、后端接口开发依赖清单

前端开发不等待后端，但以下接口需要在产品上线前由后端提供真实实现。M2-M3 阶段前端使用 Mock 数据过渡。

### 5.1 需要后端新增/确认的接口

| 接口路径 | 方法 | 前端用途 | 优先级 |
|----------|------|----------|--------|
| `/api/reviews` | GET | Reviews 列表 | P0 |
| `/api/reviews/:id` | GET | Review 详情 | P0 |
| `/api/reviews/:id/findings` | GET | Finding 列表 | P0 |
| `/api/findings/:id/feedback` | POST | 提交反馈 | P0 |
| `/api/sse/reviews` | SSE | 实时状态推送 | P1 |
| `/api/metrics` | GET | 指标统计 | P1 |
| `/api/config/:repoId` | GET, PUT | 项目配置 | P1 |
| `/api/prompts/versions` | GET, POST | Prompt 版本 | P2 |
| `/api/prompts/optimize` | POST | Prompt 优化 | P2 |

### 5.2 后端接口字段确认

后端需确保以下字段在前端使用的 JSON 响应中存在且命名一致：

```ts
// /api/reviews 返回的 Review 对象
interface Review {
  id: number;
  platform: "github" | "gitlab";
  repo_id: string;
  pr_number: number;
  pr_title?: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  risk_level?: "low" | "medium" | "high" | "critical";
  ai_model?: string;
  created_at: string; // ISO 8601
  completed_at?: string;
}

// /api/reviews/:id/findings 返回的 Finding 对象
interface ReviewFinding {
  id: number;
  review_id: number;
  file_path: string;
  line_number?: number;
  severity: "info" | "warning" | "critical";
  description: string;
  suggestion?: string;
  confidence?: number; // 0 ~ 1
  ai_model?: string;
  created_at: string;
}

// SSE 推送消息格式
interface ReviewUpdate {
  review_id: number;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  timestamp: string;
  findings_count?: number;
}
```

---

## 六、代码规范与质量门禁

### 6.1 代码提交规范

```
<type>(<scope>): <subject>

type: feat | fix | docs | style | refactor | test | chore
scope: ui | dashboard | landing | api | hook | lib

示例：
feat(dashboard): add ReviewList with status filter
fix(ui): correct GlassCard hover shadow color
```

### 6.2 静态检查

```bash
# ESLint
pnpm lint

# TypeScript 类型检查
pnpm tsc --noEmit

# Prettier 格式化检查
pnpm prettier --check "src/**/*.{ts,tsx,css}"
```

**门禁要求**：每次 PR 必须通过 `lint` 和 `tsc --noEmit`。

### 6.3 组件开发规范

1. **文件命名**：PascalCase（如 `review-list.tsx` 用于组件文件，`use-reviews.ts` 用于 Hook）
2. **样式优先使用 Tailwind**：禁止直接写裸 CSS，特殊效果（如玻璃拟态的复杂 backdrop-filter）可写为工具类或放在 globals.css
3. **动画降级**：所有 Framer Motion 组件必须包裹 `prefers-reduced-motion` 判断
4. **类型安全**：所有 API 返回数据必须定义 Zod Schema 或 TypeScript Interface，禁止用 `any`

### 6.4 性能规范

- **图片**：使用 Next.js `<Image>`，格式优先 WebP/AVIF
- **字体**：使用系统字体栈，不加载外部字体文件
- **Bundle**：单个页面首屏 JS Bundle < 200KB（gzip）
- **动画**：粒子效果使用 `requestAnimationFrame`，避免 `setInterval`

---

## 七、风险点与应对策略

| 风险 | 影响 | 应对策略 |
|------|------|----------|
| **Shiki SSR 兼容性问题** | DiffViewer 在服务端渲染时可能报错或体积过大 | 使用 `shiki` 的 `getHighlighter` 在 `useEffect` 中异步加载，服务端回退到纯文本展示 |
| **玻璃拟态性能下降** | 大量 `backdrop-filter: blur()` 在低配设备上卡顿 | Dashboard 列表超过 50 条时，非视口内卡片降级为纯色背景（`--latte-bg-secondary`） |
| **SSE 连接不稳定** | 网络波动导致 Dashboard 状态不同步 | Hook 内实现指数退避重连（1s → 3s → 5s），最大重试 10 次，失败后显示 `disconnected` 状态并允许手动刷新 |
| **Next.js 14 App Router 学习成本** | 新特性（Server Component、Parallel Routes）可能拖慢进度 | 约定：UI 组件和页面用 Client Component（`"use client"`），数据获取优先用 Server Component，降低心智负担 |
| **设计还原度不足** | 开发过程中细节丢失，偏离 Apple 风格 | 每完成一个里程碑，由设计负责人（或 AI Agent）进行视觉走查，使用 Figma 或设计文档作为单一事实来源 |

---

## 八、Mock 数据规范（M2-M3 过渡期）

在真实后端接口就绪前，使用以下 Mock 数据标准：

### 8.1 Reviews Mock

```ts
// src/lib/mock-data.ts
export const mockReviews: Review[] = [
  {
    id: 42,
    platform: "github",
    repo_id: "org/latte-backend",
    pr_number: 128,
    pr_title: "feat: add user auth",
    status: "pending",
    ai_model: "deepseek-chat",
    created_at: "2026-04-16T10:00:00Z",
  },
  {
    id: 41,
    platform: "github",
    repo_id: "org/latte-backend",
    pr_number: 127,
    pr_title: "fix: memory leak",
    status: "completed",
    risk_level: "critical",
    ai_model: "claude-3-5-sonnet",
    created_at: "2026-04-16T08:30:00Z",
    completed_at: "2026-04-16T09:00:00Z",
  },
];
```

### 8.2 SSE Mock Server（本地开发）

在 `src/app/api/sse/reviews/route.ts` 中实现一个简易 SSE 端点，每 5 秒随机推送一条状态更新：

```ts
import { NextRequest } from "next/server";

export async function GET(req: NextRequest) {
  const stream = new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder();
      const interval = setInterval(() => {
        const data = JSON.stringify({
          review_id: 42,
          status: "running",
          timestamp: new Date().toISOString(),
        });
        controller.enqueue(encoder.encode(`data: ${data}\n\n`));
      }, 5000);

      req.signal.addEventListener("abort", () => {
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

---

## 九、附录：关键设计参数速查表

### 9.1 颜色

| 用途 | 色值 |
|------|------|
| 主背景 | `#0A0806` |
| 卡片背景 | `#14110E` |
| 主文字 | `#F5E6D3` |
| 次要文字 | `#C4B5A5` |
| 强调金 | `#C4A77D` |
| 强调玫瑰 | `#D4A59A` |
| 成功/抹茶 | `#7D8471` |
| 警告/肉桂 | `#B85C38` |
| 严重/深红 | `#8B3A3A` |

### 9.2 动画参数

| 动画 | 时长 | 缓动函数 |
|------|------|----------|
| 入场动画 | 800ms | `cubic-bezier(0.16, 1, 0.3, 1)` |
| 卡片 hover | 400ms | `cubic-bezier(0.16, 1, 0.3, 1)` |
| 按钮 hover | 300ms | `cubic-bezier(0.16, 1, 0.3, 1)` |
| 状态流转 | 600ms | `ease-in-out` |
| 数字计数 | 1500ms | `cubic-bezier(0.33, 1, 0.68, 1)` |
| 交错延迟 | 100ms | — |

### 9.3 布局参数

| 元素 | 尺寸 |
|------|------|
| Sidebar 宽度 | 64px |
| Dashboard 主内容内边距 | 32px (p-8) |
| GlassCard 圆角 | 24px |
| Button 圆角 | 9999px（胶囊） |
| Badge 圆角 | 6px |
| Input 圆角 | 12px |

---

## 十、任务总览图

```
M1 (Week 1-2)        M2 (Week 3-4)         M3 (Week 5-6)         M4 (Week 7-8)
├─ 环境搭建           ├─ API 客户端+Mock      ├─ SSE 实时更新         ├─ Landing Page
├─ 主题系统配置        ├─ Reviews 列表页       ├─ Metrics 图表页       ├─ 性能优化
├─ 基础 UI 组件        ├─ Review 详情页        ├─ Config/Prompts 页    ├─ Lighthouse 验收
├─ 动画工具           ├─ DiffViewer           ├─ 状态流转动画          ├─ 可访问性检查
└─ Dashboard 骨架      └─ FileTree/FindingPanel └─ Dashboard 完整闭环   └─ 文档归档
```

---

*执行方案版本：v1.0*  
*生成时间：2026-04-16*
