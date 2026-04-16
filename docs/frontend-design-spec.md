# Latte PR Agent 前端设计方案

> **设计主题**：Latte Art meets Precision Engineering  
> **风格定位**：Apple-style 高端产品官网 + 沉浸式 Dashboard  
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

## 二、配色系统 (Latte Palette)

**拒绝使用**：`#6366f1` (Indigo)、`#8b5cf6` (Violet)、`#3b82f6` (Blue) 等大众科技蓝紫渐变。

### 2.1 主色板

```css
:root {
  /* 背景层 - Espresso Black 家族 */
  --latte-bg-deep: #030201;          /* 纯 espresso 黑，用于最底层背景 */
  --latte-bg-primary: #0A0806;       /* 主背景，带极微弱暖调 */
  --latte-bg-secondary: #14110E;     /* 卡片、浮层面板 */
  --latte-bg-tertiary: #1E1A16;      /* hover 状态、输入框背景 */

  /* 文字层 - Milk Foam 家族 */
  --latte-text-primary: #F5E6D3;     /* 主文字：暖奶油白 */
  --latte-text-secondary: #C4B5A5;   /* 次要文字：焦糖奶泡 */
  --latte-text-tertiary: #8B7D6D;    /* 占位符、禁用状态 */

  /* 强调色 - The Latte Accent */
  --latte-accent: #E8DCC4;           /*  steamed milk 强调色 */
  --latte-accent-glow: rgba(232, 220, 196, 0.15); /* 柔和光晕 */
  --latte-gold: #C4A77D;             /* 焦糖金 */
  --latte-rose: #D4A59A;             /* 玫瑰金 */

  /* 功能色 - 有机食品色调 */
  --latte-success: #7D8471;          /* 抹茶绿：通过、低风险 */
  --latte-warning: #B85C38;          /* 肉桂橙：警告、中风险 */
  --latte-critical: #8B3A3A;         /* 深红砖：严重、高风险 */
  --latte-info: #9A8B7A;             /* 拿铁褐：信息提示 */
}
```

### 2.2 渐变规范

**Hero 背景渐变**：不使用直线彩虹渐变，而是模拟「咖啡蒸汽在黑色背景中缓缓上升」的有机光效。

```css
/* 主视觉背景：从右下角升起的暖光 */
background: radial-gradient(
  ellipse 80% 50% at 20% 40%,
  rgba(196, 167, 125, 0.15),
  transparent
),
radial-gradient(
  ellipse 60% 40% at 80% 80%,
  rgba(212, 165, 154, 0.08),
  transparent
),
var(--latte-bg-primary);
```

**玻璃拟态 (Glassmorphism)**：

```css
.glass-panel {
  background: rgba(20, 17, 14, 0.6);
  backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(245, 230, 211, 0.06);
  box-shadow: 
    0 4px 24px rgba(0, 0, 0, 0.4),
    inset 0 1px 0 rgba(245, 230, 211, 0.04);
}
```

### 2.3 光影系统

- **Ambient Glow（环境光）**：所有主要交互元素（按钮、卡片 hover）都有一层极淡的 `rgba(232, 220, 196, 0.08)` 外发光。
- **Spotlight（聚光灯）**：Dashboard 中当前活跃的 Review 卡片仿佛被吧台上方的射灯照亮，边缘有 `1px` 的 `latte-gold` 微光。
- **Steam Animation（蒸汽动效）**：在大型装饰元素上，使用 `transform: translateY()` 配合 `opacity` 模拟蒸汽缓缓上升的呼吸感。

---

## 三、字体与排版

### 3.1 字体家族

采用「西文主导 + 中文回退」的策略，保证苹果设备上的极致渲染。

```css
:root {
  --font-display: "SF Pro Display", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-text: "SF Pro Text", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-mono: "SF Mono", "JetBrains Mono", "Fira Code", "PingFang SC", monospace;
}
```

**字体加载策略**：使用系统字体栈，无需额外加载外部字体，确保首屏速度。

### 3.2 字号阶梯

| 层级 | 字号 | 字重 | 行高 | 用途 |
|------|------|------|------|------|
| Display | `clamp(48px, 8vw, 96px)` | 700 | 1.05 | Hero 主标题 |
| Headline 1 | `clamp(36px, 5vw, 64px)` | 600 | 1.1 | 板块标题 |
| Headline 2 | `32px` | 600 | 1.2 | 子标题 |
| Title 3 | `24px` | 500 | 1.3 | 卡片标题 |
| Body Large | `18px` | 400 | 1.6 | 大段正文 |
| Body | `16px` | 400 | 1.6 | 默认正文 |
| Caption | `14px` | 400 | 1.5 | 辅助说明 |
| Footnote | `12px` | 500 | 1.4 | 标签、元数据 |

### 3.3 排版规则

- **标题**：使用 `-0.02em` 的负字间距（Tracking），营造紧致、高级的感觉。
- **正文**：中文行高 `1.6-1.8`，段间距 `1.5em`。
- **代码块**：使用 `--font-mono`，背景 `--latte-bg-secondary`，圆角 `12px`，字号 `14px`。

---

## 四、页面结构与内容规划

前端采用 **Landing Page（营销官网）+ Dashboard（数据看板）双模式**。用户首次访问进入 Landing Page，登录后进入 Dashboard。

### 4.1 Landing Page 结构

#### Section 1: Hero (沉浸式首屏)

**视觉**：
- 全屏深色背景，带动态蒸汽光效（Canvas/WebGL 轻量级粒子，颜色为 `latte-gold` 和 `latte-rose` 的极低透明度）。
- 中央偏上放置一个抽象的「拉花」3D 图形（可用 Spline 或 CSS 3D 实现一个旋转的奶泡纹理环）。

**文案**：
- 主标题：`Enterprise AI Code Review, Reimagined.`（英文，字体更大，Apple 风格）
- 副标题：`Latte PR Agent 为企业级代码审查注入智能与温度。多模型协同、上下文感知、质量门禁——如同一杯完美萃取的拿铁，每一个细节都恰到好处。`
- CTA 按钮：`Get Started` / `View Dashboard`

**交互**：
- 鼠标移动时，背景的径向渐变中心跟随鼠标，产生「灯光扫过咖啡吧台」的效果。
- 标题文字有 `fade-in-up` + `blur(10px) -> blur(0)` 的入场动画。

#### Section 2: Architecture Visual (架构可视化)

**视觉**：
- 不是普通的流程图，而是一个 **等距视角（Isometric）的咖啡吧台式架构图**。
- GitHub/GitLab 像是「咖啡豆入口」。
- Celery Workers 像是「一组并行的意式咖啡机」。
- PostgreSQL + pgvector 像是「深色的储豆罐」。
- 连接线用发光的粒子流动画表示数据流动。

**文案**：
- 标题：`Brewed for Scale`
- 副标题：从 Webhook 接收到评论发布，全链路异步处理，支持 Kubernetes 水平扩展。

#### Section 3: Feature Bento Grid (功能便当盒)

**视觉**：采用 Apple 官网常见的 Bento Grid 布局（不规则大小的卡片拼贴）。

6 张功能卡片的布局与内容：

| 卡片 | 尺寸 | 视觉元素 | 文案 |
|------|------|----------|------|
| **Multi-Model Intelligence** | 2x1 大卡片 | 三个旋转的「奶泡环」代表 DeepSeek/Claude/Qwen | 主模型初筛，Reasoner 复核，自动降级永不掉线。 |
| **Context-Aware Analysis** | 1x1 | 抽象的 AST 树状图，节点发光 | Tree-sitter 解析 + 依赖图构建，审查不再是盲人摸象。 |
| **Static Analysis Fusion** | 1x1 | Semgrep 的盾牌标志融入咖啡杯轮廓 | AI 与 Semgrep 结果智能合并，去重、互补。 |
| **Quality Gate** | 1x1 | 一个类似 iOS 控制中心的开关动画 | Critical 风险自动阻塞合并，为代码质量守门。 |
| **Feedback Loop** | 1x1 | 螺旋上升的曲线，象征持续优化 | 开发者标记误报，Prompt A/B 测试，越用越聪明。 |
| **Cross-Service Impact** | 2x1 大卡片 | 多个咖啡杯通过蒸汽连接 | 检测 API 契约变更，分析跨服务影响范围。 |

**交互**：
- 卡片 hover 时有 `scale(1.02)` + 边缘光效亮起的微动效。
- 内部的小图形有独立的持续旋转或呼吸动画。

#### Section 4: Live Dashboard Preview (实时仪表盘预览)

**视觉**：
- 一个巨大的「悬浮玻璃面板」，展示模拟的 Dashboard 界面。
- 面板有 `perspective(1000px) rotateX(5deg)` 的 3D 倾斜效果，像 floating display。
- 内部包含：
  - 顶部的 Metrics 概览（Reviews: 1,284 | Findings: 3,402 | Accuracy: 94.2%）
  - 中间的 Review 列表（带 status badge: pending/completed/skipped）
  - 右侧的 Finding Detail 面板（展示 severity、category、ai_model）

**文案**：
- 标题：`Every Review, Visualized`
- 副标题：从 PR 概览到单条发现的置信度，所有数据一目了然。

#### Section 5: Tech Specs (技术规格)

**视觉**：
- 类似 MacBook 产品页底部的 Tech Specs 表格风格。
- 左侧大标签，右侧数值。

**内容**：

| 标签 | 数值 |
|------|------|
| Language | Python 3.11+ |
| Framework | FastAPI + Celery |
| Database | PostgreSQL 16 + pgvector |
| LLM Providers | DeepSeek, Anthropic Claude, Qwen |
| Static Analysis | Semgrep |
| Test Coverage | 72+ Automated Tests |
| Deployment | Docker Compose / Kubernetes |

#### Section 6: CTA & Footer

**视觉**：
- 背景变为一个巨大的 `latte-gold` 到 `transparent` 的径向渐变。
- 中央巨大的 CTA 按钮，采用「胶囊按钮」设计，背景是磨砂玻璃 + 金色边框发光。

**文案**：
- `Start Brewing Better Code Today`
- 按钮：`Deploy on GitHub` / `Read the Docs`

---

### 4.2 Dashboard 页面结构

Dashboard 是面向实际使用者的管理界面，风格保持一致的 Latte 主题，但信息密度更高。

#### 布局

- **左侧 Sidebar**：窄边栏（64px），纯图标 + Tooltip。hover 时图标有 `latte-gold` 发光效果。
- **顶部 Header**：搜索框 + 通知铃铛 + 用户头像。
- **主内容区**：可切换的视图（Reviews / Metrics / Config / Prompts）。

#### Reviews 列表页

- 表格行不是普通的横线分割，而是每张 Review 是一个独立的 `glass-panel` 卡片。
- 列：PR Title | Repo | Status Badge | Risk Level | Model | Completed At
- Status Badge 的颜色：
  - `pending` → 半透明琥珀色圆点
  - `completed` → 抹茶绿圆点
  - `skipped` → 灰色圆点

#### Review Detail 页

三栏布局：
- **左栏（20%）**：PR 基本信息、文件列表（File Tree）
- **中栏（50%）**：Diff 视图（暗色代码高亮，语法高亮配色与 Latte 主题统一）
- **右栏（30%）**：Finding 列表，点击后展开详情，含 `Mark as False Positive` 按钮

#### Metrics 页

- 顶部 4 个 KPI 卡片（Glassmorphism 大数字）
- 中部：折线图（Review Volume over Time），线条颜色为 `latte-gold`
- 底部：饼图（Findings by Category），用 Latte 色系的不同饱和度区分

---

## 五、组件设计规范

### 5.1 按钮 (Button)

**Primary Button（主按钮）**：
- 背景：`linear-gradient(180deg, rgba(232, 220, 196, 0.12), rgba(232, 220, 196, 0.04))`
- 边框：`1px solid rgba(232, 220, 196, 0.2)`
- 文字：`--latte-text-primary`
- 圆角：`9999px`（胶囊形）
- Hover：背景亮度提升，底部出现 `0 8px 24px rgba(196, 167, 125, 0.2)` 投影

**Secondary Button（次按钮）**：
- 背景：透明
- 边框：`1px solid rgba(245, 230, 211, 0.1)`
- Hover：背景填充 `--latte-bg-tertiary`

### 5.2 卡片 (Card)

所有卡片统一使用 `glass-panel` 风格：
- 背景：`rgba(20, 17, 14, 0.5)`
- 圆角：`24px`
- 内边距：`32px`
- Hover：边框颜色从 `rgba(245, 230, 211, 0.06)` 过渡到 `rgba(196, 167, 125, 0.2)`，时长 `400ms`

### 5.3 Badge / Tag

- **Critical**：深红背景 + 浅红文字，圆角 `6px`，字重 600
- **Warning**：肉桂背景 + 浅文字
- **Success**：抹茶绿背景 + 浅文字
- **Info**：灰褐背景 + 浅文字

所有 badge 都有 `inset 0 1px 0 rgba(255,255,255,0.1)` 的内高光，增加立体感。

### 5.4 表单输入框

- 背景：`--latte-bg-tertiary`
- 边框：`1px solid transparent`，focus 时变为 `rgba(196, 167, 125, 0.4)`
- 圆角：`12px`
- Focus 时有柔和的金色外发光

---

## 六、动效与交互规范

### 6.1 入场动画

所有页面元素采用 **Staggered Reveal（交错显现）**：
- 初始状态：`opacity: 0; transform: translateY(40px); filter: blur(8px);`
- 结束状态：`opacity: 1; transform: translateY(0); filter: blur(0);`
- 时长：`800ms`
- 缓动：`cubic-bezier(0.16, 1, 0.3, 1)`（Apple 风格：快起慢收）
- 交错间隔：`100ms`

### 6.2 滚动交互

- **Parallax（视差）**：Hero 背景的蒸汽粒子层以 `0.3x` 速度跟随滚动，装饰图形以 `0.5x` 速度移动。
- **Scroll Snap**：Landing Page 的长滚动不做 Snap，保持自然；Dashboard 的列表区可以有轻微的 Snap。

### 6.3 微交互

- **Magnetic Button**：按钮在 `50px` 范围内对鼠标有轻微吸引（使用 Framer Motion 或 GSAP）。
- **Cursor Spotlight**：在 Dashboard 的卡片区域，鼠标下方有一个 `200px` 的径向渐变跟随移动，照亮当前的卡片。
- **Number Counter**：KPI 数字从 0 滚动到目标值，时长 `1.5s`，使用 `cubic-bezier(0.33, 1, 0.68, 1)`。

### 6.4 页面切换

使用 **Shared Element Transition（共享元素过渡）**：
- 从 Review 列表点击进入详情时，该 Review 卡片的标题和 Status Badge 平滑飞到详情页的对应位置，其余内容淡入。

---

## 七、技术栈建议

### 7.1 推荐方案

| 层级 | 技术 | 理由 |
|------|------|------|
| 框架 | **Next.js 14 (App Router)** | SSR 利于 SEO，Landing Page 可被搜索引擎索引 |
| 语言 | **TypeScript** | 与后端 Python 类型对接更清晰 |
| 样式 | **Tailwind CSS** | 快速实现复杂的玻璃拟态和响应式布局 |
| 动画 | **Framer Motion** | React 生态最强大的声明式动画库，完美实现 Apple 风格的入场和页面过渡 |
| 3D/图形 | **Spline** 或 **React Three Fiber** | Hero 的拉花 3D 图形 |
| 图表 | **Recharts** 或 **Tremor** | Dashboard 数据可视化，自定义 Latte 主题配色 |
| 图标 | **Lucide React** | 线条简洁，与 Apple 风格匹配 |
| 代码高亮 | **Prism.js / Shiki** | Diff 视图语法高亮，可自定义主题为 Latte 色系 |

### 7.2 响应式断点

```css
/* Mobile First */
sm: 640px
md: 768px
lg: 1024px
xl: 1280px
2xl: 1536px
```

- **Mobile**：Bento Grid 变为单列堆叠，Dashboard Sidebar 变为底部 Tab Bar。
- **Tablet**：Bento Grid 变为 2 列，Dashboard 保持 Sidebar。
- **Desktop**：完整的多列布局和 3D 效果。

---

## 八、 assets 资源清单

### 8.1 需要制作的视觉资产

1. **Hero Latte Art 3D** (`assets/hero-latte-art.spline`)
   - 一个抽象的、缓缓旋转的奶泡环，颜色为 `latte-gold` 和 `latte-rose`。
   - 材质：Subsurface Scattering（次表面散射），营造类似牛奶的温润透光感。

2. **Architecture Illustration** (`assets/architecture-iso.png` 或 `.svg`)
   - 等距视角的咖啡吧台式架构图。
   - 可用 Figma 的 Oblique 插件或 Blender 渲染。

3. **Feature Icons** (`assets/icons/`)
   - 6 个简洁的线性图标，带 `1.5px` 描边，圆角端点。

4. **Dashboard Mock Screenshot** (`assets/dashboard-preview.png`)
   - 可直接用前端代码渲染后截图，作为 Landing Page 的展示图。

### 8.2 无需制作的资产

- **字体**：完全使用系统字体栈，无需加载任何外部字体文件。
- **背景纹理**：全部通过 CSS 渐变和 Canvas 粒子实现，无需图片。

---

## 九、开发检查清单

### Landing Page
- [ ] Hero 背景有随鼠标移动的聚光灯效果
- [ ] 主标题使用 `-0.02em` 字间距和 `clamp` 响应式字号
- [ ] Bento Grid 在桌面端为不规则布局，移动端自动堆叠
- [ ] Dashboard Preview 有 `perspective` 3D 倾斜和悬停回正效果
- [ ] 所有按钮和卡片 hover 时有金色光晕
- [ ] 页面滚动时有视差效果

### Dashboard
- [ ] Sidebar 为纯图标窄边栏，hover 有发光
- [ ] Review 列表使用卡片式布局而非传统表格
- [ ] Status Badge 使用圆点 + 文字，颜色符合功能色规范
- [ ] Diff 视图语法高亮配色与 Latte 主题一致
- [ ] Metrics 图表使用 `latte-gold` 作为主线条/扇区颜色
- [ ] 数字变化时有 CountUp 动画

### 性能与可访问性
- [ ] Lighthouse Performance >= 90
- [ ] 支持 `prefers-reduced-motion`（减弱动画模式）
- [ ] 所有文字对比度 >= WCAG AA 标准
- [ ] 图片使用 WebP/AVIF 格式

---

## 十、结语

这套方案的核心竞争力在于：**它不是又一个蓝紫渐变的 SaaS 模板，而是将「Latte」的品牌基因深度融入到了每一个像素和每一次交互中**。从 Espresso 黑到 Steamed Milk 白的色彩系统，从缓缓上升的蒸汽粒子到精密排列的 Bento Grid，都在传递同一个信息：

> **Latte PR Agent 是温暖的，也是专业的；是有机的，也是精确的。**

---

*设计文档版本：v1.0*  
*创建时间：2026-04-16*
