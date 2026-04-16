# Latte PR Agent 前端设计方案（最终版）

> **设计主题**：Latte Art meets Precision Engineering  
> **风格定位**：Apple-style 高端产品官网 + 沉浸式数据 Dashboard  
> **个性宣言**：拒绝蓝紫科技渐变的千篇一律，以「拿铁」的温润质感重新定义开发者工具的审美。

---

## 一、品牌与设计理念

### 1.1 核心概念

Latte PR Agent 的名字自带「拿铁咖啡」的意象。我们不把 Coffee 当作廉价的贴纸 Logo，而是将其升华为一套完整的设计语言：

- **Espresso（浓缩）** → 深沉、专注、高对比度的深色背景
- **Steamed Milk（奶泡）** → 柔和、流动的光效与渐变
- **Latte Art（拉花）** → 有机的、非对称的、具有艺术感的界面构图
- **Precision（精密）** → 代码审查的本质：清晰、准确、无冗余

整体视觉感受应像走进一家位于硅谷的精品咖啡店：温暖、高级、有匠心，同时每一把咖啡壶都经过精密工业设计。

### 1.2 情绪板 (Mood Board)

| 关键词 | 视觉联想 |
|--------|----------|
| 清晨咖啡吧台 | 暖光打在黑色大理石台面上，蒸汽缓缓升起 |
| 拉花旋转 | 不对称的、顺时针旋转的有机纹理 |
| 意大利建筑 | 罗马曲线的优雅，Breuer 椅子的理性 |
| 苹果 Pro Display | 极高的对比度、绝对的黑色、细腻的字体渲染 |

---

## 二、后端数据映射

前端设计必须与后端数据模型精准对应。核心实体及其前端用途如下：

### 2.1 核心实体

| 实体 | 关键字段 | 前端用途 |
|------|----------|----------|
| `Review` | `id, platform, repo_id, pr_number, pr_title, status, risk_level, ai_model, created_at, completed_at` | Reviews 列表页、详情页头部 |
| `ReviewFinding` | `id, file_path, line_number, severity, description, suggestion, confidence, ai_model` | Finding 详情面板、Diff 标注 |
| `PRFile` | `file_path, change_type, additions, deletions, diff_content` | 文件树、Diff 视图 |
| `DeveloperFeedback` | `is_false_positive, comment` | 反馈按钮、误报标记 |
| `BugKnowledge` | `bug_pattern, severity, fix_description` | RAG 知识库展示 |
| `ProjectConfig` | `config_json` | 项目配置页 |
| `PromptExperiment` | `version, is_active, ab_ratio, accuracy` | Prompt 管理页 |

### 2.2 状态工作流 (Workflow)

```
Webhook → Review (pending) → Celery Worker (running) → 
Finding 生成 → Publisher 发布评论 → Review (completed / failed / skipped)
```

前端必须实时反映这一状态流转，因此 Dashboard 需要支持 **SSE 实时推送**。

---

## 三、配色系统 (Latte Palette)

**拒绝使用**：`#6366f1` (Indigo)、`#8b5cf6` (Violet)、`#3b82f6` (Blue) 等大众科技蓝紫渐变。

### 3.1 主色板

```css
:root {
  /* 背景层 - Espresso Black 家族 */
  --latte-bg-deep: #030201;          /* 纯 espresso 黑 */
  --latte-bg-primary: #0A0806;       /* 主背景 */
  --latte-bg-secondary: #14110E;     /* 卡片、浮层面板 */
  --latte-bg-tertiary: #1E1A16;      /* hover、输入框背景 */
  --latte-bg-hover: #28231E;         /* 更深 hover */

  /* 文字层 - Milk Foam 家族 */
  --latte-text-primary: #F5E6D3;     /* 主文字：暖奶油白 */
  --latte-text-secondary: #C4B5A5;   /* 次要文字：焦糖奶泡 */
  --latte-text-tertiary: #8B7D6D;    /* 占位符、禁用 */
  --latte-text-muted: #5C5246;       /* 极弱文字 */

  /* 强调色 - The Latte Accent */
  --latte-accent: #E8DCC4;
  --latte-accent-hover: #F0E8D8;
  --latte-gold: #C4A77D;
  --latte-gold-dim: #8F7650;
  --latte-gold-glow: rgba(196, 167, 125, 0.25);
  --latte-rose: #D4A59A;
  --latte-rose-dim: #A67B72;
  --latte-rose-glow: rgba(212, 165, 154, 0.2);

  /* 功能色 - 有机食品色调 */
  --latte-success: #7D8471;
  --latte-success-bg: rgba(125, 132, 113, 0.12);
  --latte-warning: #B85C38;
  --latte-warning-bg: rgba(184, 92, 56, 0.12);
  --latte-critical: #8B3A3A;
  --latte-critical-bg: rgba(139, 58, 58, 0.12);
  --latte-info: #9A8B7A;
  --latte-info-bg: rgba(154, 139, 122, 0.12);

  /* Severity 专用（与功能色对应，语义更清晰） */
  --latte-severity-info: #9A8B7A;
  --latte-severity-warning: #B85C38;
  --latte-severity-critical: #8B3A3A;

  /* 平台品牌色 */
  --latte-github: #F5E6D3;
  --latte-gitlab: #E8C4A0;

  /* Confidence 渐变色 */
  --latte-confidence-low: #8B7D6D;    /* < 70% */
  --latte-confidence-med: #C4A77D;    /* 70-90% */
  --latte-confidence-high: #7D8471;   /* > 90% */

  /* 阴影 */
  --latte-shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.3);
  --latte-shadow-md: 0 4px 24px rgba(0, 0, 0, 0.4);
  --latte-shadow-lg: 0 12px 48px rgba(0, 0, 0, 0.5);
  --latte-shadow-gold: 0 8px 24px rgba(196, 167, 125, 0.15);

  /* 圆角 */
  --latte-radius-sm: 8px;
  --latte-radius-md: 12px;
  --latte-radius-lg: 20px;
  --latte-radius-xl: 24px;
  --latte-radius-full: 9999px;
}
```

### 3.2 渐变规范

**Hero 背景渐变**：模拟「咖啡蒸汽在黑色背景中缓缓上升」。

```css
.latte-hero-bg {
  background:
    radial-gradient(ellipse 80% 50% at 20% 40%, rgba(196, 167, 125, 0.15), transparent),
    radial-gradient(ellipse 60% 40% at 80% 80%, rgba(212, 165, 154, 0.08), transparent),
    var(--latte-bg-primary);
}
```

**玻璃拟态 (Glassmorphism)**：

```css
.latte-glass {
  background: rgba(20, 17, 14, 0.55);
  backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(245, 230, 211, 0.06);
  border-radius: var(--latte-radius-xl);
  box-shadow: var(--latte-shadow-md), inset 0 1px 0 rgba(245, 230, 211, 0.04);
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.latte-glass:hover {
  border-color: rgba(196, 167, 125, 0.2);
  box-shadow: var(--latte-shadow-gold), inset 0 1px 0 rgba(245, 230, 211, 0.08);
}
```

### 3.3 光影系统

- **Ambient Glow**：主要交互元素 hover 时有 `rgba(232, 220, 196, 0.08)` 外发光。
- **Spotlight**：Dashboard 中当前活跃的 Review 卡片边缘有 `1px` 的 `latte-gold` 微光。
- **Steam Animation**：装饰元素使用 `translateY()` + `opacity` 模拟蒸汽缓缓上升。

---

## 四、字体与排版

### 4.1 字体家族

采用「西文主导 + 中文回退」的系统字体栈：

```css
:root {
  --font-display: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-text: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-mono: "SF Mono", "JetBrains Mono", "Fira Code", monospace;
}
```

### 4.2 字号阶梯

| 层级 | 字号 | 字重 | 行高 | 用途 |
|------|------|------|------|------|
| Display | `clamp(48px, 8vw, 96px)` | 700 | 1.05 | Hero 主标题 |
| Headline 1 | `clamp(36px, 5vw, 64px)` | 600 | 1.1 | 板块标题 |
| Headline 2 | `32px` | 600 | 1.2 | 子标题 |
| Title 3 | `24px` | 500 | 1.3 | 卡片标题 |
| Body | `16px` | 400 | 1.7 | 默认正文 |
| Caption | `14px` | 400 | 1.5 | 辅助说明 |
| Footnote | `12px` | 500 | 1.4 | 标签、元数据 |

### 4.3 排版规则

- **标题**：负字间距 `-0.02em`，营造紧致高级感。
- **正文**：中文行高 `1.6-1.8`，段间距 `1.5em`。
- **代码块**：`--font-mono`，背景 `--latte-bg-secondary`，圆角 `12px`，字号 `14px`。

---

## 五、页面结构与内容规划

前端采用 **Landing Page（营销官网）+ Dashboard（数据看板）双模式**。

### 5.1 Landing Page 结构

#### Section 1: Hero (沉浸式首屏)

- **视觉**：全屏深色背景（`latte-hero-bg`）+ Canvas 蒸汽粒子层 + 中央抽象「拉花」3D 图形。
- **文案**：
  - 主标题：`Enterprise AI Code Review, Reimagined.`
  - 副标题：`Latte PR Agent 为企业级代码审查注入智能与温度。多模型协同、上下文感知、质量门禁——如同一杯完美萃取的拿铁，每一个细节都恰到好处。`
  - CTA：`Get Started` / `View Dashboard`
- **交互**：鼠标移动时背景径向渐变中心跟随；标题有 `fade-in-up` + `blur(10px) -> blur(0)` 入场动画。

#### Section 2: Architecture Visual (架构可视化)

- **视觉**：等距视角（Isometric）的咖啡吧台式架构图。
- **文案**：`Brewed for Scale` + 异步处理与水平扩展说明。

#### Section 3: Feature Bento Grid (功能便当盒)

Apple 风格的不规则卡片拼贴布局：

| 卡片 | 尺寸 | 内容 |
|------|------|------|
| **Multi-Model Intelligence** | 2x1 | 主模型初筛，Reasoner 复核，自动降级 |
| **Context-Aware Analysis** | 1x1 | Tree-sitter + 依赖图构建 |
| **Static Analysis Fusion** | 1x1 | AI 与 Semgrep 结果智能合并 |
| **Quality Gate** | 1x1 | Critical 风险自动阻塞合并 |
| **Feedback Loop** | 1x1 | 开发者标记误报，Prompt A/B 测试 |
| **Cross-Service Impact** | 2x1 | API 契约变更，跨服务影响分析 |

#### Section 4: Live Dashboard Preview

- **视觉**：悬浮玻璃面板，含 `perspective(1000px) rotateX(5deg)` 的 3D 倾斜效果。
- **内部展示**：Metrics 概览 + Review 列表 + Finding Detail 面板。

#### Section 5: Tech Specs

MacBook 产品页风格的规格表格：

| 标签 | 数值 |
|------|------|
| Language | Python 3.11+ |
| Framework | FastAPI + Celery |
| Database | PostgreSQL 16 + pgvector |
| LLM Providers | DeepSeek, Anthropic Claude, Qwen |
| Test Coverage | 72+ Automated Tests |

#### Section 6: CTA & Footer

- **视觉**：`latte-gold` 径向渐变背景 + 磨砂玻璃胶囊按钮。
- **文案**：`Start Brewing Better Code Today`

---

### 5.2 Dashboard 页面结构

#### 布局框架

```
┌────────┬────────────────────────────────────────┐
│        │  Header: Search + Notification + Avatar │
│ Sidebar├────────────────────────────────────────┤
│ (64px) │                                        │
│  Icons │         Main Content Area              │
│        │                                        │
└────────┴────────────────────────────────────────┘
```

- **左侧 Sidebar**：窄边栏（64px），纯图标 + Tooltip，hover 时图标有 `latte-gold` 发光。
- **顶部 Header**：搜索框 + 实时连接指示器（`RealtimeIndicator`）+ 用户头像。

#### Reviews 列表页 (/dashboard/reviews)

```
┌─────────────────────────────────────────────────────────┐
│ [Status ▼] [Repo ▼] [Risk ▼]              [Search 🔍]  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │ ● pending    #42  feat: add user auth   org/repo  │  │
│  │              "Add OAuth2 integration"   DeepSeek  │  │
│  │                              2 minutes ago        │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │ ● completed  #41  fix: memory leak      org/repo  │  │
│  │              "Fix connection pool..."   [critical]│  │
│  │              Claude-3.5  |  3 findings   1h ago   │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**设计决策**：
1. **卡片列表替代表格**，更符合玻璃拟态风格。
2. **状态指示**：
   - `pending` → 琥珀色脉冲动画
   - `running` → 蓝色旋转指示器
   - `completed` → 抹茶绿
   - `failed` → 深红
   - `skipped` → 灰色
3. **风险等级徽章**：仅在 `completed` 且非 `low` 时显示。

#### Review 详情页 (/dashboard/reviews/[id])

**三栏布局**：

```
┌──────────┬─────────────────────────────┬───────────────────┐
│ 文件树   │      Diff 视图               │  Finding 列表面板  │
├──────────┼─────────────────────────────┼───────────────────┤
│ ▼ src/   │ @@ -45,7 +45,7 @@           │ ┌───────────────┐ │
│   auth/  │  - const timeout = 5000;    │ │ ⚠️ Warning    │ │
│   ▶ api.ts│ + const timeout = 30000;   │ │ Line 47       │ │
│    [3]   │                             │ │ confidence 92%│ │
│ ▼ utils/ │  [高亮显示变更]              │ └───────────────┘ │
│   db.ts  │                             │ ┌───────────────┐ │
│    [1]   │  点击行号关联 finding        │ │ 🔴 Critical   │ │
│          │                             │ │ Line 52       │ │
│          │                             │ │ [展开详情...] │ │
│          │                             │ └───────────────┘ │
└──────────┴─────────────────────────────┴───────────────────┘
```

- **左栏（20%）**：文件列表，文件名右侧显示该文件的 finding 数量徽章（颜色表示最高 severity）。
- **中栏（50%）**：Diff 视图，新增行深绿背景（`--latte-success/10%`），删除行深红背景（`--latte-critical/10%`）。点击行号可高亮对应 Finding。
- **右栏（30%）**：Finding 卡片列表，展开后显示：
  - AI 描述与修复建议
  - `ConfidenceRing` 置信度圆环（金色 Apple Watch 风格）
  - 应用模型标签
  - `Mark as False Positive` 按钮

#### Metrics 页 (/dashboard/metrics)

- **顶部**：4 个 `latte-glass` KPI 大数字卡片（Reviews / Findings / Accuracy / False Positive Rate）。
- **中部**：`Recharts` 折线图（`reviews` 为 `latte-gold` 线，`findings` 为 `latte-rose` 线）。
- **底部**：饼图（Findings by Category / Severity）。

#### Prompt 管理页 (/dashboard/prompts)

```
┌─────────────────────────────────────────────────────────────┐
│  Prompt Registry                                [+ New]     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ v1.2.0-system  (active)                    [Edit][Test]│  │
│  │ 使用于: 3 个仓库  |  准确率: 94.2%                      │  │
│  │ A/B 测试: 50% / 50% (vs v1.1.9)                        │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ v1.1.9-system  (baseline)                  [Edit][Test]│  │
│  │ 使用于: 5 个仓库  |  准确率: 91.8%                      │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 项目配置页 (/dashboard/config)

可视化编辑 `.review-config.yml`：
- 开关：跨服务影响分析、依赖图深度、历史 Bug 检查
- 列表：Critical Paths、Custom Rules
- 模型选择器：Primary / Fallback

---

## 六、API 接口设计

前端通过统一的 API 客户端与后端通信。部分接口需要新增后端路由支持。

```ts
// lib/api.ts
export const api = {
  // Reviews
  getReviews: (params?: { status?: string; repo?: string; page?: number }) =>
    fetch(`/api/reviews?${new URLSearchParams(params as any)}`),

  getReviewDetail: (id: number) =>
    fetch(`/api/reviews/${id}`),

  // Findings
  getReviewFindings: (reviewId: number) =>
    fetch(`/api/reviews/${reviewId}/findings`),

  submitFeedback: (findingId: number, data: { is_false_positive: boolean; comment?: string }) =>
    fetch(`/api/findings/${findingId}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  // Metrics
  getMetrics: (range: "7d" | "30d" | "90d") =>
    fetch(`/api/metrics?range=${range}`),

  // Config
  getProjectConfig: (repoId: string) =>
    fetch(`/api/config/${repoId}`),
  updateProjectConfig: (repoId: string, config: object) =>
    fetch(`/api/config/${repoId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    }),

  // Prompts
  getPromptVersions: () => fetch("/api/prompts/versions"),
  createPromptVersion: (data: object) =>
    fetch("/api/prompts/versions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }),
  optimizePrompt: (data: object) =>
    fetch("/api/prompts/optimize", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }),

  // SSE 实时更新
  subscribeReviewUpdates: (callback: (update: ReviewUpdate) => void) => {
    const es = new EventSource("/api/sse/reviews");
    es.onmessage = (e) => callback(JSON.parse(e.data));
    return () => es.close();
  },
};
```

**备注**：SSE 路由 `/api/sse/reviews` 需要后端新增支持，用于向前端推送 Review 状态变更事件。

---

## 七、组件设计规范

### 7.1 按钮 (Button)

```tsx
interface ButtonProps {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
}
```

**Primary**：
- 背景：`linear-gradient(180deg, rgba(232, 220, 196, 0.14), rgba(232, 220, 196, 0.04))`
- 边框：`1px solid rgba(232, 220, 196, 0.22)`
- 圆角：`9999px`（胶囊形）
- Hover：亮度提升 + `latte-shadow-gold` + `translateY(-1px)`

**Secondary**：
- 背景：透明
- 边框：`1px solid rgba(245, 230, 211, 0.1)`
- Hover：填充 `--latte-bg-tertiary`

### 7.2 GlassCard（玻璃卡片）

```tsx
interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "interactive" | "elevated" | "status";
  status?: "pending" | "running" | "completed" | "failed" | "skipped";
}
```

- **default**：标准玻璃面板。
- **interactive**：hover 时边框发光 + scale(1.01)。
- **elevated**：更强的阴影，用于 KPI 卡片。
- **status**：左侧带有 `4px` 彩色状态边条：
  - `pending` → 琥珀脉冲
  - `running` → 蓝色渐变流动
  - `completed` → 抹茶绿
  - `failed` → 深红
  - `skipped` → 灰色

### 7.3 Badge / Tag

```tsx
type BadgeVariant = "success" | "warning" | "critical" | "info";
interface BadgeProps {
  variant: BadgeVariant;
  dot?: boolean;
}
```

- 圆角 `6px`，字重 600，字号 12px
- 所有 badge 带 `inset 0 1px 0 rgba(255,255,255,0.08)` 内高光

### 7.4 StatusBadge（状态徽章）

```tsx
interface StatusBadgeProps {
  status: "pending" | "running" | "completed" | "failed" | "skipped";
}
```

- `pending`：琥珀色圆点 + 呼吸动画
- `running`：蓝色旋转圆环
- `completed`：抹茶绿圆点
- `failed`：深红圆点
- `skipped`：灰色圆点

### 7.5 DiffViewer（Diff 查看器）

```tsx
interface DiffViewerProps {
  files: PRFile[];
  findings: ReviewFinding[];
  selectedFile?: string;
  onLineClick?: (lineNum: number, filePath: string) => void;
}
```

- 使用 **Shiki** 语法高亮，Latte 主题配色：
  - 关键字：`var(--latte-rose)`
  - 字符串：`var(--latte-gold)`
  - 注释：`var(--latte-text-muted)`
- 新增行背景：`rgba(125, 132, 113, 0.1)`
- 删除行背景：`rgba(139, 58, 58, 0.1)`
- Finding 标注：对应行右侧有 `2px` 金色竖线，hover 显示 finding 摘要 tooltip

### 7.6 ConfidenceRing（置信度圆环）

```tsx
interface ConfidenceRingProps {
  value: number; // 0 ~ 1
  size?: number;
}
```

- Apple Watch 风格圆环进度条
- 颜色根据值自动映射：
  - `< 0.7` → `--latte-confidence-low`
  - `0.7 ~ 0.9` → `--latte-confidence-med`
  - `> 0.9` → `--latte-confidence-high`
- 圆环末尾有柔和发光效果

### 7.7 RealtimeIndicator（实时连接指示器）

```tsx
interface RealtimeIndicatorProps {
  status: "connecting" | "connected" | "disconnected";
}
```

- 显示在 Dashboard Header 右侧
- `connecting` → 琥珀脉冲点
- `connected` → 抹茶绿稳定点
- `disconnected` → 深红点

### 7.8 表单输入框

- 背景：`--latte-bg-tertiary`
- 边框：`1px solid transparent`，focus 时变为 `rgba(196, 167, 125, 0.4)`
- 圆角：`12px`
- Focus 外发光：`0 0 0 3px rgba(196, 167, 125, 0.1)`

---

## 八、动效与交互规范

### 8.1 入场动画 (Staggered Reveal)

```css
/* 初始状态 */
opacity: 0;
transform: translateY(40px);
filter: blur(8px);

/* 结束状态 */
opacity: 1;
transform: translateY(0);
filter: blur(0);

/* 参数 */
duration: 800ms;
easing: cubic-bezier(0.16, 1, 0.3, 1);
stagger: 100ms;
```

### 8.2 滚动交互

- **Parallax**：Hero 粒子层 `0.3x` 滚动速度，装饰图形 `0.5x`。
- **Scroll Snap**：Dashboard 列表区可配置轻微 Snap，Landing Page 保持自然滚动。

### 8.3 微交互

- **Magnetic Button**：按钮在 `50px` 范围内对鼠标有轻微吸引（Framer Motion）。
- **Cursor Spotlight**：Dashboard 卡片区鼠标下方有 `200px` 径向渐变跟随。
- **Number Counter**：KPI 数字从 0 滚动到目标值，时长 `1.5s`。

### 8.4 Review 状态流转动画

| 流转 | 动画效果 |
|------|----------|
| `pending → running` | 卡片左侧出现蓝色渐变流动光效 |
| `running → completed` | 绿色光效从左侧扫过，findings 数字 CountUp |
| `any → failed` | 卡片轻微抖动（`shake`），红色错误图标浮现 |
| `pending → completed` | 状态边条颜色渐变过渡，时长 `600ms` |

### 8.5 页面切换

- 使用 **Shared Element Transition**：
  - 从 Review 列表点击进入详情时，该 Review 卡片的标题和 StatusBadge 平滑飞到详情页对应位置。

### 8.6 无障碍与性能

- 支持 `prefers-reduced-motion`：所有位移动画和粒子效果在该模式下禁用。
- 所有文字对比度满足 WCAG AA。
- Canvas 粒子数量控制在 30-50 个。

---

## 九、技术栈与项目结构

### 9.1 技术栈

| 层级 | 技术 | 理由 |
|------|------|------|
| 框架 | **Next.js 14 (App Router)** | SSR 利于 SEO，支持 API Routes |
| 语言 | **TypeScript** | 与后端类型对接清晰 |
| 样式 | **Tailwind CSS** | 快速实现玻璃拟态和响应式 |
| 动画 | **Framer Motion** | Apple 风格的声明式动画与页面过渡 |
| 3D/图形 | **Spline / React Three Fiber** | Hero 拉花 3D 图形 |
| 图表 | **Recharts** | Dashboard 数据可视化，易自定义主题色 |
| 图标 | **Lucide React** | 线条简洁，Apple 风格 |
| 代码高亮 | **Shiki** | Diff 语法高亮，可自定义主题为 Latte 色系 |
| 数据获取 | **SWR / React Query** | 缓存、重试、实时更新管理 |

### 9.2 响应式断点

```css
sm: 640px
md: 768px
lg: 1024px
xl: 1280px
2xl: 1536px
```

- **Mobile**：Bento Grid 单列，Dashboard Sidebar 变为底部 Tab Bar。
- **Tablet**：Bento Grid 2 列，Dashboard 保持 Sidebar。
- **Desktop**：完整多列布局和 3D 效果。

### 9.3 推荐文件结构

```
frontend/
├── app/
│   ├── layout.tsx                    # 根布局，注入主题 CSS
│   ├── page.tsx                      # Landing Page
│   ├── globals.css                   # Tailwind + Latte 变量
│   ├── dashboard/
│   │   ├── layout.tsx                # Sidebar + Header 布局
│   │   ├── page.tsx                  # 重定向到 /dashboard/reviews
│   │   ├── reviews/
│   │   │   ├── page.tsx              # Review 列表
│   │   │   └── [id]/
│   │   │       ├── page.tsx          # Review 详情
│   │   │       └── components/
│   │   │           ├── diff-viewer.tsx
│   │   │           ├── finding-panel.tsx
│   │   │           └── file-tree.tsx
│   │   ├── metrics/
│   │   │   └── page.tsx              # 指标统计
│   │   ├── config/
│   │   │   └── page.tsx              # 项目配置
│   │   └── prompts/
│   │       └── page.tsx              # Prompt 管理
│   └── api/                          # Next.js API Routes（代理/聚合）
│       ├── reviews/route.ts
│       ├── findings/route.ts
│       ├── metrics/route.ts
│       ├── config/[repoId]/route.ts
│       ├── prompts/route.ts
│       └── sse/reviews/route.ts
├── components/
│   ├── landing/                      # Landing Page 专用
│   │   ├── hero-section.tsx
│   │   ├── steam-particles.tsx
│   │   ├── bento-grid.tsx
│   │   └── dashboard-preview.tsx
│   ├── dashboard/                    # Dashboard 专用
│   │   ├── sidebar.tsx
│   │   ├── header.tsx
│   │   ├── review-list.tsx
│   │   ├── diff-viewer.tsx
│   │   ├── file-tree.tsx
│   │   └── finding-panel.tsx
│   ├── ui/                           # 通用原子组件
│   │   ├── button.tsx
│   │   ├── badge.tsx
│   │   ├── glass-card.tsx
│   │   ├── input.tsx
│   │   ├── status-badge.tsx
│   │   ├── confidence-ring.tsx
│   │   └── realtime-indicator.tsx
│   └── motion/                       # 动画包装
│       ├── fade-in-up.tsx
│       └── stagger-container.tsx
├── hooks/
│   ├── use-reviews.ts                # SWR 获取 reviews
│   ├── use-review-detail.ts
│   ├── use-sse.ts                    # SSE 订阅
│   ├── use-metrics.ts
│   └── use-prompts.ts
├── lib/
│   ├── api.ts                        # API 客户端
│   ├── utils.ts                      # cn() 等工具
│   └── theme.ts                      # 主题工具
├── types/
│   └── index.ts                      # TypeScript 类型定义
└── public/
    └── assets/
        ├── hero-latte-art.spline     # Spline 3D 文件
        └── icons/                    # 自定义图标
```

---

## 十、实施优先级建议

| 优先级 | 任务 | 原因 |
|--------|------|------|
| **P0** | Reviews 列表页 + API 连接 | 核心功能，数据驱动 |
| **P0** | Review 详情页（三栏布局 + DiffViewer） | 核心价值展示 |
| **P1** | SSE 实时更新 + RealtimeIndicator | 提升用户体验，反映后端状态流 |
| **P1** | Metrics 图表页 | 数据可视化需求 |
| **P2** | Prompt Management 页面 | 高级功能，面向管理员 |
| **P2** | Landing Page 动画/微交互完善 | 品牌体验优化 |

---

## 十一、开发检查清单

### Landing Page
- [ ] Hero 背景有随鼠标移动的聚光灯效果
- [ ] 主标题使用 `-0.02em` 字间距和 `clamp` 响应式字号
- [ ] Bento Grid 桌面端不规则布局，移动端自动堆叠
- [ ] Dashboard Preview 有 `perspective` 3D 倾斜和悬停回正
- [ ] 所有按钮和卡片 hover 时有金色光晕

### Dashboard
- [ ] Sidebar 为纯图标窄边栏，hover 有发光
- [ ] Review 列表使用卡片式布局，带有 `status` 变体左边条
- [ ] StatusBadge 正确显示 pending/running/completed/failed/skipped
- [ ] Diff 视图语法高亮配色与 Latte 主题一致
- [ ] 文件树显示每个文件的 finding 数量徽章
- [ ] Finding 卡片包含 ConfidenceRing 和 False Positive 按钮
- [ ] Metrics 图表使用 `latte-gold` 主线条
- [ ] Header 包含 RealtimeIndicator 实时连接状态

### 性能与可访问性
- [ ] Lighthouse Performance >= 90
- [ ] 支持 `prefers-reduced-motion`
- [ ] 文字对比度 >= WCAG AA
- [ ] SSE 断线后 3s 内自动重连

---

*文档版本：v2.0 (Final)*  
*整合时间：2026-04-16*
