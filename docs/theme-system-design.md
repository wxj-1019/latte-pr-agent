# Latte PR Agent — 主题切换系统设计方案

> 文档版本：v1.0 | 日期：2026-04-19
> 
> 本文档描述前端页面整体配色切换的完整方案，包括架构设计、实施步骤和代码示例。

---

## 一、现状分析

### 1.1 当前配色架构

项目使用 **"Latte Night"** 暖棕暗色主题，配色体系分为三层：

```
:root CSS 变量 (50 个 Token)
  │
  ├─ 背景色层级 (5 个)
  │   bg-deep → bg-primary → bg-secondary → bg-tertiary → bg-hover
  │
  ├─ 文本色层级 (4 个)
  │   text-primary → text-secondary → text-tertiary → text-muted
  │
  ├─ 强调色 (7 个)
  │   accent, accent-hover, gold, gold-dim, gold-glow, rose, rose-dim, rose-glow
  │
  ├─ 语义色 (8 个)
  │   success, success-bg, warning, warning-bg, critical, critical-bg, info, info-bg
  │
  ├─ 其他 (6 个)
  │   confidence-*, severity-*, github, gitlab
  │
  ├─ 阴影 (4 个)
  │   shadow-sm, shadow-md, shadow-lg, shadow-gold
  │
  └─ 圆角 (5 个)
      radius-sm, radius-md, radius-lg, radius-xl, radius-full
         │
         ▼
  Tailwind Config (映射 20 个颜色)
  bg-latte-*, text-latte-*, border-latte-*, ring-latte-*
         │
         ▼
  @layer components (6 个组件类)
  latte-glass, latte-btn-primary/secondary, latte-badge-*, latte-input, latte-sidebar
         │
         ▼
  33 个组件文件使用
  ~227 处 Tailwind 类名 + ~45 处 var() 引用
```

### 1.2 涉及文件统计

| 类别 | 文件数 | 说明 |
|------|--------|------|
| 页面文件 | 17 | `src/app/**/*.tsx` |
| 组件文件 | 16 | `src/components/**/*.tsx` |
| 全局样式 | 1 | `globals.css` |
| Tailwind 配置 | 1 | `tailwind.config.ts` |
| **总计** | **35** | |

### 1.3 当前配色 Token 全表

以下是 `globals.css` `:root` 中定义的完整 Token 列表：

#### 背景色

| 变量名 | 当前值 (Latte Night) | 用途 |
|--------|---------------------|------|
| `--latte-bg-deep` | `#030201` | 最深层背景（滚动条轨道） |
| `--latte-bg-primary` | `#0A0806` | 主背景（页面、body） |
| `--latte-bg-secondary` | `#14110E` | 次级背景（卡片骨架屏） |
| `--latte-bg-tertiary` | `#1E1A16` | 三级背景（输入框、下拉选项） |
| `--latte-bg-hover` | `#28231E` | 悬停背景（输入框聚焦） |

#### 文本色

| 变量名 | 当前值 | 用途 |
|--------|--------|------|
| `--latte-text-primary` | `#F5E6D3` | 主文本（标题、正文） |
| `--latte-text-secondary` | `#C4B5A5` | 次级文本（描述、标签） |
| `--latte-text-tertiary` | `#8B7D6D` | 三级文本（占位符、辅助） |
| `--latte-text-muted` | `#5C5246` | 弱化文本（时间戳、提示） |

#### 强调色

| 变量名 | 当前值 | 用途 |
|--------|--------|------|
| `--latte-accent` | `#E8DCC4` | 强调色（按钮渐变） |
| `--latte-accent-hover` | `#F0E8D8` | 强调色悬停态 |
| `--latte-gold` | `#C4A77D` | 金色主强调（侧边栏激活、徽标） |
| `--latte-gold-dim` | `#8F7650` | 金色弱化态 |
| `--latte-gold-glow` | `rgba(196,167,125,0.25)` | 金色发光效果 |
| `--latte-rose` | `#D4A59A` | 玫瑰色（次要强调） |
| `--latte-rose-dim` | `#A67B72` | 玫瑰色弱化态 |
| `--latte-rose-glow` | `rgba(212,165,154,0.2)` | 玫瑰色发光效果 |

#### 语义色

| 变量名 | 当前值 | 用途 |
|--------|--------|------|
| `--latte-success` | `#7D8471` | 成功（已完成状态） |
| `--latte-success-bg` | `rgba(125,132,113,0.12)` | 成功背景 |
| `--latte-warning` | `#B85C38` | 警告 |
| `--latte-warning-bg` | `rgba(184,92,56,0.12)` | 警告背景 |
| `--latte-critical` | `#8B3A3A` | 严重/危险 |
| `--latte-critical-bg` | `rgba(139,58,58,0.12)` | 严重背景 |
| `--latte-info` | `#9A8B7A` | 信息 |
| `--latte-info-bg` | `rgba(154,139,122,0.12)` | 信息背景 |

#### 其他功能色

| 变量名 | 当前值 | 用途 |
|--------|--------|------|
| `--latte-github` | `#F5E6D3` | GitHub 平台标识色 |
| `--latte-gitlab` | `#E8C4A0` | GitLab 平台标识色 |
| `--latte-confidence-low` | `#8B7D6D` | 置信度低 |
| `--latte-confidence-med` | `#C4A77D` | 置信度中 |
| `--latte-confidence-high` | `#7D8471` | 置信度高 |
| `--latte-severity-info` | `#9A8B7A` | 严重级别-信息 |
| `--latte-severity-warning` | `#B85C38` | 严重级别-警告 |
| `--latte-severity-critical` | `#8B3A3A` | 严重级别-严重 |

#### 阴影

| 变量名 | 当前值 | 用途 |
|--------|--------|------|
| `--latte-shadow-sm` | `0 2px 8px rgba(0,0,0,0.3)` | 小阴影 |
| `--latte-shadow-md` | `0 4px 24px rgba(0,0,0,0.4)` | 中阴影（卡片） |
| `--latte-shadow-lg` | `0 12px 48px rgba(0,0,0,0.5)` | 大阴影（弹窗） |
| `--latte-shadow-gold` | `0 8px 24px rgba(196,167,125,0.15)` | 金色发光阴影 |

#### 圆角

| 变量名 | 当前值 | 用途 |
|--------|--------|------|
| `--latte-radius-sm` | `8px` | 徽标、小元素 |
| `--latte-radius-md` | `12px` | 输入框、下拉 |
| `--latte-radius-lg` | `20px` | 中等卡片 |
| `--latte-radius-xl` | `24px` | 大卡片、面板 |
| `--latte-radius-full` | `9999px` | 按钮、头像 |

### 1.4 硬编码颜色问题

当前存在 **~33 处硬编码颜色值**，分布在两个层面：

#### globals.css `@layer components` 中（~20 处）

| 位置 | 硬编码值 | 应替换为 |
|------|---------|---------|
| `.latte-hero-bg` | `rgba(196,167,125,0.15)` | `var(--latte-hero-gradient-1)` |
| `.latte-hero-bg` | `rgba(212,165,154,0.08)` | `var(--latte-hero-gradient-2)` |
| `.latte-glass` | `rgba(20,17,14,0.55)` | `var(--latte-glass-bg)` |
| `.latte-glass` | `rgba(245,230,211,0.06)` | `var(--latte-glass-border)` |
| `.latte-glass` | `rgba(245,230,211,0.04)` | `var(--latte-glass-inset)` |
| `.latte-glass:hover` | `rgba(196,167,125,0.2)` | `var(--latte-glass-hover-border)` |
| `.latte-glass:hover` | `rgba(245,230,211,0.08)` | `var(--latte-glass-hover-inset)` |
| `.latte-btn-primary` | `rgba(232,220,196,0.14)` / `rgba(232,220,196,0.04)` | `var(--latte-btn-gradient-*)` |
| `.latte-btn-primary` | `rgba(232,220,196,0.22)` | `var(--latte-btn-border)` |
| `.latte-btn-primary` | `rgba(0,0,0,0.2)` | `var(--latte-btn-shadow)` |
| `.latte-btn-primary:hover` | `rgba(232,220,196,0.2)` / `rgba(232,220,196,0.08)` | `var(--latte-btn-hover-gradient-*)` |
| `.latte-btn-primary:hover` | `rgba(232,220,196,0.35)` | `var(--latte-btn-hover-border)` |
| `.latte-btn-secondary` | `rgba(245,230,211,0.1)` | `var(--latte-btn-secondary-border)` |
| `.latte-btn-secondary:hover` | `rgba(245,230,211,0.18)` | `var(--latte-btn-secondary-hover-border)` |
| `.latte-badge` | `rgba(255,255,255,0.08)` | `var(--latte-badge-inset)` |
| `.latte-badge-success` | `#D4DACA` | `var(--latte-badge-success-text)` |
| `.latte-badge-warning` | `#E8C4B0` | `var(--latte-badge-warning-text)` |
| `.latte-badge-critical` | `#E8B8B8` | `var(--latte-badge-critical-text)` |
| `.latte-badge-info` | `#D8CFC4` | `var(--latte-badge-info-text)` |
| `.latte-input:focus` | `rgba(196,167,125,0.4)` / `rgba(196,167,125,0.1)` | `var(--latte-input-focus-*)` |
| `.latte-sidebar` | `rgba(10,8,6,0.8)` | `var(--latte-sidebar-bg)` |
| `.latte-sidebar` | `rgba(245,230,211,0.04)` | `var(--latte-sidebar-border)` |
| `.latte-sidebar-item:hover` | `rgba(196,167,125,0.08)` / `rgba(196,167,125,0.1)` | `var(--latte-sidebar-active-*)` |

#### TSX 组件文件中（~13 处）

| 文件 | 硬编码值 | 用途 |
|------|---------|------|
| `metrics/page.tsx` (5处) | `rgba(245,230,211,...)` | Recharts 图表网格线/坐标轴 |
| `metrics/page.tsx` (2处) | `rgba(245,230,211,...)` | Tooltip/Legend 边框 |
| `hero-section.tsx` (2处) | `rgba(196,167,125,...)` | 动态渐变背景 |
| `architecture-flow.tsx` (1处) | `rgba(196,167,125,0.6)` | 连接点发光 |
| `steam-particles.tsx` (2处) | `"196,167,125"`, `"212,165,154"` | Canvas 粒子 RGB |
| `page.tsx` (1处) | `rgba(196,167,125,0.12)` | 落地页渐变 |
| `analyze/page.tsx` (2处) | `#0d1117`, `#c9d1d9` | GitHub 编辑器主题（可保留） |

---

## 二、方案设计

### 2.1 架构选型

| 决策点 | 选择 | 理由 |
|--------|------|------|
| **切换机制** | CSS 变量 + `data-theme` 属性 | 零 JS 运行时开销，Tailwind 无需重新编译 |
| **存储方式** | `localStorage` | 用户偏好持久化，无需后端 |
| **硬编码修复** | 新增辅助 CSS 变量 | 避免依赖 `color-mix()` 浏览器兼容性 |
| **Token 结构** | 扁平 CSS 变量（与现有 `:root` 一致） | 完全兼容现有代码 |
| **切换过渡** | `transition` on `:root` | 全局丝滑切换体验 |

### 2.2 架构图

```
用户点击主题切换
      │
      ▼
ThemeProvider.setTheme("latte-light")
      │
      ├─ localStorage.setItem("latte-theme", "latte-light")
      │
      └─ document.documentElement.style.setProperty(k, v)  × 50 个变量
      │
      └─ document.documentElement.setAttribute("data-theme", "latte-light")
            │
            ▼
      CSS 变量自动生效 → 所有组件自动更新颜色
      （Tailwind 类名如 bg-latte-gold 通过 var() 间接引用，无需重新编译）
```

### 2.3 文件结构

```
frontend/src/
├── themes/
│   ├── tokens.ts              # 所有主题的 Token 定义
│   ├── ThemeProvider.tsx       # Context + 主题切换逻辑
│   └── use-theme.ts           # Hook 导出
├── app/
│   ├── globals.css            # 修复硬编码，新增辅助变量
│   └── layout.tsx             # 包裹 ThemeProvider
├── components/
│   ├── dashboard/
│   │   └── header.tsx         # 添加主题切换按钮
│   └── ui/
│       └── theme-switcher.tsx # 主题切换器组件
└── tailwind.config.ts         # Tailwind 颜色映射改为 var() 引用
```

---

## 三、预设主题

### 3.1 🌙 Latte Night（默认 · 暖棕暗色）

当前已有配色，保持不变。

### 3.2 ☀️ Latte Light（暖棕亮色）

亮色版本，底色反转，保持暖调。

| Token | Latte Night | Latte Light | 说明 |
|-------|-------------|-------------|------|
| `--latte-bg-deep` | `#030201` | `#FAF7F2` | 最深 → 最浅 |
| `--latte-bg-primary` | `#0A0806` | `#FFFFFF` | 主背景白 |
| `--latte-bg-secondary` | `#14110E` | `#F5F0E8` | 次级背景暖米 |
| `--latte-bg-tertiary` | `#1E1A16` | `#EDE6DA` | 三级背景浅驼 |
| `--latte-bg-hover` | `#28231E` | `#E0D8CC` | 悬停态 |
| `--latte-text-primary` | `#F5E6D3` | `#2C2418` | 主文本深棕 |
| `--latte-text-secondary` | `#C4B5A5` | `#5C5246` | 次级文本 |
| `--latte-text-tertiary` | `#8B7D6D` | `#8B7D6D` | 保持不变 |
| `--latte-text-muted` | `#5C5246` | `#A89B8C` | 弱化文本 |
| `--latte-gold` | `#C4A77D` | `#A0845C` | 金色略深 |
| `--latte-gold-dim` | `#8F7650` | `#BFA47E` | 金色弱化 |
| `--latte-rose` | `#D4A59A` | `#B87B6E` | 玫瑰略深 |
| `--latte-rose-dim` | `#A67B72` | `#C49B92` | 玫瑰弱化 |
| `--latte-success` | `#7D8471` | `#5F6B52` | 成功色深 |
| `--latte-warning` | `#B85C38` | `#B85C38` | 保持不变 |
| `--latte-critical` | `#8B3A3A` | `#B94444` | 严重色略亮 |
| `--latte-info` | `#9A8B7A` | `#7A6B5A` | 信息色深 |

**辅助变量变化：**

| 辅助变量 | Latte Night | Latte Light |
|----------|-------------|-------------|
| `--latte-glass-bg` | `rgba(20,17,14,0.55)` | `rgba(255,255,255,0.7)` |
| `--latte-glass-border` | `rgba(245,230,211,0.06)` | `rgba(44,36,24,0.08)` |
| `--latte-sidebar-bg` | `rgba(10,8,6,0.8)` | `rgba(255,255,255,0.9)` |
| `--latte-btn-gradient-from` | `rgba(232,220,196,0.14)` | `rgba(44,36,24,0.06)` |
| `--latte-btn-gradient-to` | `rgba(232,220,196,0.04)` | `rgba(44,36,24,0.02)` |
| `--latte-btn-border` | `rgba(232,220,196,0.22)` | `rgba(44,36,24,0.15)` |
| `--latte-shadow-sm` | `0 2px 8px rgba(0,0,0,0.3)` | `0 2px 8px rgba(0,0,0,0.06)` |
| `--latte-shadow-md` | `0 4px 24px rgba(0,0,0,0.4)` | `0 4px 24px rgba(0,0,0,0.08)` |
| `--latte-shadow-lg` | `0 12px 48px rgba(0,0,0,0.5)` | `0 12px 48px rgba(0,0,0,0.12)` |
| `--latte-shadow-gold` | `0 8px 24px rgba(196,167,125,0.15)` | `0 8px 24px rgba(160,132,92,0.12)` |

### 3.3 🌸 Rose Latte（蜜桃粉主题）

可爱风格，基于用户偏好设计。 <mccoremem id="01KNFH1BHMW60QDGYTASPVH5J0" />

| Token | Latte Night | Rose Latte | 说明 |
|-------|-------------|------------|------|
| `--latte-bg-deep` | `#030201` | `#120810` | 深紫粉底 |
| `--latte-bg-primary` | `#0A0806` | `#1A0E16` | 玫瑰棕底 |
| `--latte-bg-secondary` | `#14110E` | `#241620` | 次级粉棕 |
| `--latte-bg-tertiary` | `#1E1A16` | `#2E1E28` | 三级 |
| `--latte-bg-hover` | `#28231E` | `#3A2832` | 悬停 |
| `--latte-text-primary` | `#F5E6D3` | `#F8E4EE` | 浅粉白 |
| `--latte-text-secondary` | `#C4B5A5` | `#D4B8C8` | 淡玫瑰 |
| `--latte-text-tertiary` | `#8B7D6D` | `#A08898` | 灰粉 |
| `--latte-text-muted` | `#5C5246` | `#6E5A66` | 暗粉灰 |
| `--latte-gold` | `#C4A77D` | `#E8A0BF` | 粉金（主强调） |
| `--latte-gold-dim` | `#8F7650` | `#B8789A` | 粉金弱化 |
| `--latte-rose` | `#D4A59A` | `#FF8FAB` | 亮粉（次要强调） |
| `--latte-rose-dim` | `#A67B72` | `#CC7090` | 粉色弱化 |
| `--latte-success` | `#7D8471` | `#8CAA7E` | 柔和绿 |
| `--latte-warning` | `#B85C38` | `#E89860` | 暖橙 |
| `--latte-critical` | `#8B3A3A` | `#CC5577` | 玫瑰红 |
| `--latte-info` | `#9A8B7A` | `#B898C0` | 薰衣草 |

---

## 四、详细实施步骤

### 步骤 1：创建主题 Token 定义

**文件**: `frontend/src/themes/tokens.ts`

```typescript
export type ThemeName = "latte-night" | "latte-light" | "rose-latte";

export interface ThemeMeta {
  name: ThemeName;
  label: string;
  emoji: string;
  preview: { bg: string; accent: string; text: string };
}

export const themeList: ThemeMeta[] = [
  {
    name: "latte-night",
    label: "暖棕暗色",
    emoji: "🌙",
    preview: { bg: "#0A0806", accent: "#C4A77D", text: "#F5E6D3" },
  },
  {
    name: "latte-light",
    label: "暖棕亮色",
    emoji: "☀️",
    preview: { bg: "#FFFFFF", accent: "#A0845C", text: "#2C2418" },
  },
  {
    name: "rose-latte",
    label: "蜜桃粉",
    emoji: "🌸",
    preview: { bg: "#1A0E16", accent: "#E8A0BF", text: "#F8E4EE" },
  },
];

export type ThemeTokens = Record<string, string>;

const latteNight: ThemeTokens = {
  // 背景色
  "--latte-bg-deep": "#030201",
  "--latte-bg-primary": "#0A0806",
  "--latte-bg-secondary": "#14110E",
  "--latte-bg-tertiary": "#1E1A16",
  "--latte-bg-hover": "#28231E",

  // 文本色
  "--latte-text-primary": "#F5E6D3",
  "--latte-text-secondary": "#C4B5A5",
  "--latte-text-tertiary": "#8B7D6D",
  "--latte-text-muted": "#5C5246",

  // 强调色
  "--latte-accent": "#E8DCC4",
  "--latte-accent-hover": "#F0E8D8",
  "--latte-gold": "#C4A77D",
  "--latte-gold-dim": "#8F7650",
  "--latte-rose": "#D4A59A",
  "--latte-rose-dim": "#A67B72",

  // 语义色
  "--latte-success": "#7D8471",
  "--latte-warning": "#B85C38",
  "--latte-critical": "#8B3A3A",
  "--latte-info": "#9A8B7A",

  // 功能色
  "--latte-github": "#F5E6D3",
  "--latte-gitlab": "#E8C4A0",
  "--latte-confidence-low": "#8B7D6D",
  "--latte-confidence-med": "#C4A77D",
  "--latte-confidence-high": "#7D8471",

  // 辅助变量 — 半透明层
  "--latte-gold-glow": "rgba(196, 167, 125, 0.25)",
  "--latte-rose-glow": "rgba(212, 165, 154, 0.2)",
  "--latte-success-bg": "rgba(125, 132, 113, 0.12)",
  "--latte-warning-bg": "rgba(184, 92, 56, 0.12)",
  "--latte-critical-bg": "rgba(139, 58, 58, 0.12)",
  "--latte-info-bg": "rgba(154, 139, 122, 0.12)",

  // 辅助变量 — 组件
  "--latte-hero-gradient-1": "rgba(196, 167, 125, 0.15)",
  "--latte-hero-gradient-2": "rgba(212, 165, 154, 0.08)",
  "--latte-glass-bg": "rgba(20, 17, 14, 0.55)",
  "--latte-glass-border": "rgba(245, 230, 211, 0.06)",
  "--latte-glass-inset": "rgba(245, 230, 211, 0.04)",
  "--latte-glass-hover-border": "rgba(196, 167, 125, 0.2)",
  "--latte-glass-hover-inset": "rgba(245, 230, 211, 0.08)",
  "--latte-btn-gradient-from": "rgba(232, 220, 196, 0.14)",
  "--latte-btn-gradient-to": "rgba(232, 220, 196, 0.04)",
  "--latte-btn-border": "rgba(232, 220, 196, 0.22)",
  "--latte-btn-shadow": "0 1px 2px rgba(0, 0, 0, 0.2)",
  "--latte-btn-hover-gradient-from": "rgba(232, 220, 196, 0.2)",
  "--latte-btn-hover-gradient-to": "rgba(232, 220, 196, 0.08)",
  "--latte-btn-hover-border": "rgba(232, 220, 196, 0.35)",
  "--latte-btn-secondary-border": "rgba(245, 230, 211, 0.1)",
  "--latte-btn-secondary-hover-border": "rgba(245, 230, 211, 0.18)",
  "--latte-badge-inset": "rgba(255, 255, 255, 0.08)",
  "--latte-badge-success-text": "#D4DACA",
  "--latte-badge-warning-text": "#E8C4B0",
  "--latte-badge-critical-text": "#E8B8B8",
  "--latte-badge-info-text": "#D8CFC4",
  "--latte-input-focus-border": "rgba(196, 167, 125, 0.4)",
  "--latte-input-focus-ring": "rgba(196, 167, 125, 0.1)",
  "--latte-sidebar-bg": "rgba(10, 8, 6, 0.8)",
  "--latte-sidebar-border": "rgba(245, 230, 211, 0.04)",
  "--latte-sidebar-active-bg": "rgba(196, 167, 125, 0.08)",
  "--latte-sidebar-active-shadow": "rgba(196, 167, 125, 0.1)",
  "--latte-particle-color-1": "196, 167, 125",
  "--latte-particle-color-2": "212, 165, 154",

  // 阴影
  "--latte-shadow-sm": "0 2px 8px rgba(0, 0, 0, 0.3)",
  "--latte-shadow-md": "0 4px 24px rgba(0, 0, 0, 0.4)",
  "--latte-shadow-lg": "0 12px 48px rgba(0, 0, 0, 0.5)",
  "--latte-shadow-gold": "0 8px 24px rgba(196, 167, 125, 0.15)",

  // 圆角（不变）
  "--latte-radius-sm": "8px",
  "--latte-radius-md": "12px",
  "--latte-radius-lg": "20px",
  "--latte-radius-xl": "24px",
  "--latte-radius-full": "9999px",
};

const latteLight: ThemeTokens = {
  "--latte-bg-deep": "#FAF7F2",
  "--latte-bg-primary": "#FFFFFF",
  "--latte-bg-secondary": "#F5F0E8",
  "--latte-bg-tertiary": "#EDE6DA",
  "--latte-bg-hover": "#E0D8CC",

  "--latte-text-primary": "#2C2418",
  "--latte-text-secondary": "#5C5246",
  "--latte-text-tertiary": "#8B7D6D",
  "--latte-text-muted": "#A89B8C",

  "--latte-accent": "#3C3428",
  "--latte-accent-hover": "#2C2418",
  "--latte-gold": "#A0845C",
  "--latte-gold-dim": "#BFA47E",
  "--latte-rose": "#B87B6E",
  "--latte-rose-dim": "#C49B92",

  "--latte-success": "#5F6B52",
  "--latte-warning": "#B85C38",
  "--latte-critical": "#B94444",
  "--latte-info": "#7A6B5A",

  "--latte-github": "#2C2418",
  "--latte-gitlab": "#A07850",
  "--latte-confidence-low": "#8B7D6D",
  "--latte-confidence-med": "#A0845C",
  "--latte-confidence-high": "#5F6B52",

  "--latte-gold-glow": "rgba(160, 132, 92, 0.2)",
  "--latte-rose-glow": "rgba(184, 123, 110, 0.15)",
  "--latte-success-bg": "rgba(95, 107, 82, 0.1)",
  "--latte-warning-bg": "rgba(184, 92, 56, 0.1)",
  "--latte-critical-bg": "rgba(185, 68, 68, 0.1)",
  "--latte-info-bg": "rgba(122, 107, 90, 0.1)",

  "--latte-hero-gradient-1": "rgba(160, 132, 92, 0.12)",
  "--latte-hero-gradient-2": "rgba(184, 123, 110, 0.06)",
  "--latte-glass-bg": "rgba(255, 255, 255, 0.7)",
  "--latte-glass-border": "rgba(44, 36, 24, 0.08)",
  "--latte-glass-inset": "rgba(255, 255, 255, 0.5)",
  "--latte-glass-hover-border": "rgba(160, 132, 92, 0.2)",
  "--latte-glass-hover-inset": "rgba(255, 255, 255, 0.6)",
  "--latte-btn-gradient-from": "rgba(44, 36, 24, 0.06)",
  "--latte-btn-gradient-to": "rgba(44, 36, 24, 0.02)",
  "--latte-btn-border": "rgba(44, 36, 24, 0.15)",
  "--latte-btn-shadow": "0 1px 2px rgba(0, 0, 0, 0.06)",
  "--latte-btn-hover-gradient-from": "rgba(44, 36, 24, 0.1)",
  "--latte-btn-hover-gradient-to": "rgba(44, 36, 24, 0.04)",
  "--latte-btn-hover-border": "rgba(44, 36, 24, 0.25)",
  "--latte-btn-secondary-border": "rgba(44, 36, 24, 0.1)",
  "--latte-btn-secondary-hover-border": "rgba(44, 36, 24, 0.18)",
  "--latte-badge-inset": "rgba(255, 255, 255, 0.4)",
  "--latte-badge-success-text": "#4A5C40",
  "--latte-badge-warning-text": "#8B4428",
  "--latte-badge-critical-text": "#8B2E2E",
  "--latte-badge-info-text": "#5C4A38",
  "--latte-input-focus-border": "rgba(160, 132, 92, 0.5)",
  "--latte-input-focus-ring": "rgba(160, 132, 92, 0.1)",
  "--latte-sidebar-bg": "rgba(255, 255, 255, 0.9)",
  "--latte-sidebar-border": "rgba(44, 36, 24, 0.06)",
  "--latte-sidebar-active-bg": "rgba(160, 132, 92, 0.08)",
  "--latte-sidebar-active-shadow": "rgba(160, 132, 92, 0.08)",
  "--latte-particle-color-1": "160, 132, 92",
  "--latte-particle-color-2": "184, 123, 110",

  "--latte-shadow-sm": "0 2px 8px rgba(0, 0, 0, 0.06)",
  "--latte-shadow-md": "0 4px 24px rgba(0, 0, 0, 0.08)",
  "--latte-shadow-lg": "0 12px 48px rgba(0, 0, 0, 0.12)",
  "--latte-shadow-gold": "0 8px 24px rgba(160, 132, 92, 0.12)",

  "--latte-radius-sm": "8px",
  "--latte-radius-md": "12px",
  "--latte-radius-lg": "20px",
  "--latte-radius-xl": "24px",
  "--latte-radius-full": "9999px",
};

const roseLatte: ThemeTokens = {
  "--latte-bg-deep": "#120810",
  "--latte-bg-primary": "#1A0E16",
  "--latte-bg-secondary": "#241620",
  "--latte-bg-tertiary": "#2E1E28",
  "--latte-bg-hover": "#3A2832",

  "--latte-text-primary": "#F8E4EE",
  "--latte-text-secondary": "#D4B8C8",
  "--latte-text-tertiary": "#A08898",
  "--latte-text-muted": "#6E5A66",

  "--latte-accent": "#F0D0E0",
  "--latte-accent-hover": "#F8E0EE",
  "--latte-gold": "#E8A0BF",
  "--latte-gold-dim": "#B8789A",
  "--latte-rose": "#FF8FAB",
  "--latte-rose-dim": "#CC7090",

  "--latte-success": "#8CAA7E",
  "--latte-warning": "#E89860",
  "--latte-critical": "#CC5577",
  "--latte-info": "#B898C0",

  "--latte-github": "#F8E4EE",
  "--latte-gitlab": "#F0C8D8",
  "--latte-confidence-low": "#A08898",
  "--latte-confidence-med": "#E8A0BF",
  "--latte-confidence-high": "#8CAA7E",

  "--latte-gold-glow": "rgba(232, 160, 191, 0.25)",
  "--latte-rose-glow": "rgba(255, 143, 171, 0.2)",
  "--latte-success-bg": "rgba(140, 170, 126, 0.12)",
  "--latte-warning-bg": "rgba(232, 152, 96, 0.12)",
  "--latte-critical-bg": "rgba(204, 85, 119, 0.12)",
  "--latte-info-bg": "rgba(184, 152, 192, 0.12)",

  "--latte-hero-gradient-1": "rgba(232, 160, 191, 0.15)",
  "--latte-hero-gradient-2": "rgba(255, 143, 171, 0.08)",
  "--latte-glass-bg": "rgba(36, 22, 32, 0.55)",
  "--latte-glass-border": "rgba(248, 228, 238, 0.06)",
  "--latte-glass-inset": "rgba(248, 228, 238, 0.04)",
  "--latte-glass-hover-border": "rgba(232, 160, 191, 0.2)",
  "--latte-glass-hover-inset": "rgba(248, 228, 238, 0.08)",
  "--latte-btn-gradient-from": "rgba(240, 208, 224, 0.14)",
  "--latte-btn-gradient-to": "rgba(240, 208, 224, 0.04)",
  "--latte-btn-border": "rgba(240, 208, 224, 0.22)",
  "--latte-btn-shadow": "0 1px 2px rgba(0, 0, 0, 0.2)",
  "--latte-btn-hover-gradient-from": "rgba(240, 208, 224, 0.2)",
  "--latte-btn-hover-gradient-to": "rgba(240, 208, 224, 0.08)",
  "--latte-btn-hover-border": "rgba(240, 208, 224, 0.35)",
  "--latte-btn-secondary-border": "rgba(248, 228, 238, 0.1)",
  "--latte-btn-secondary-hover-border": "rgba(248, 228, 238, 0.18)",
  "--latte-badge-inset": "rgba(255, 255, 255, 0.08)",
  "--latte-badge-success-text": "#B8D8AE",
  "--latte-badge-warning-text": "#F0C8A0",
  "--latte-badge-critical-text": "#F0A0B8",
  "--latte-badge-info-text": "#D8C0E0",
  "--latte-input-focus-border": "rgba(232, 160, 191, 0.4)",
  "--latte-input-focus-ring": "rgba(232, 160, 191, 0.1)",
  "--latte-sidebar-bg": "rgba(26, 14, 22, 0.8)",
  "--latte-sidebar-border": "rgba(248, 228, 238, 0.04)",
  "--latte-sidebar-active-bg": "rgba(232, 160, 191, 0.08)",
  "--latte-sidebar-active-shadow": "rgba(232, 160, 191, 0.1)",
  "--latte-particle-color-1": "232, 160, 191",
  "--latte-particle-color-2": "255, 143, 171",

  "--latte-shadow-sm": "0 2px 8px rgba(0, 0, 0, 0.3)",
  "--latte-shadow-md": "0 4px 24px rgba(0, 0, 0, 0.4)",
  "--latte-shadow-lg": "0 12px 48px rgba(0, 0, 0, 0.5)",
  "--latte-shadow-gold": "0 8px 24px rgba(232, 160, 191, 0.15)",

  "--latte-radius-sm": "8px",
  "--latte-radius-md": "12px",
  "--latte-radius-lg": "20px",
  "--latte-radius-xl": "24px",
  "--latte-radius-full": "9999px",
};

export const themes: Record<ThemeName, ThemeTokens> = {
  "latte-night": latteNight,
  "latte-light": latteLight,
  "rose-latte": roseLatte,
};
```

### 步骤 2：创建 ThemeProvider

**文件**: `frontend/src/themes/ThemeProvider.tsx`

```tsx
"use client";

import { createContext, useEffect, useState, useCallback } from "react";
import { themes, ThemeName, ThemeTokens } from "./tokens";

interface ThemeContextValue {
  theme: ThemeName;
  setTheme: (name: ThemeName) => void;
}

export const ThemeContext = createContext<ThemeContextValue>({
  theme: "latte-night",
  setTheme: () => {},
});

const STORAGE_KEY = "latte-theme";
const DEFAULT_THEME: ThemeName = "latte-night";

function applyTokens(tokens: ThemeTokens) {
  const root = document.documentElement;
  Object.entries(tokens).forEach(([key, value]) => {
    root.style.setProperty(key, value);
  });
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemeName>(DEFAULT_THEME);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY) as ThemeName | null;
    const initial = saved && themes[saved] ? saved : DEFAULT_THEME;
    setThemeState(initial);
    applyTokens(themes[initial]);
    document.documentElement.setAttribute("data-theme", initial);
    setMounted(true);
  }, []);

  const setTheme = useCallback((name: ThemeName) => {
    if (!themes[name]) return;
    setThemeState(name);
    localStorage.setItem(STORAGE_KEY, name);
    applyTokens(themes[name]);
    document.documentElement.setAttribute("data-theme", name);
  }, []);

  // 防止 SSR 闪烁
  if (!mounted) {
    return <>{children}</>;
  }

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
```

### 步骤 3：创建 use-theme Hook

**文件**: `frontend/src/themes/use-theme.ts`

```ts
import { useContext } from "react";
import { ThemeContext } from "./ThemeProvider";

export function useTheme() {
  return useContext(ThemeContext);
}
```

### 步骤 4：创建主题切换器组件

**文件**: `frontend/src/components/ui/theme-switcher.tsx`

```tsx
"use client";

import { useState, useRef, useEffect } from "react";
import { useTheme } from "@/themes/use-theme";
import { themeList } from "@/themes/tokens";

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const current = themeList.find((t) => t.name === theme) || themeList[0];

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-latte-md
                   text-latte-text-tertiary hover:text-latte-text-primary
                   hover:bg-latte-bg-tertiary transition-colors text-sm"
        title="切换主题"
      >
        <span>{current.emoji}</span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-48 rounded-latte-xl
                        bg-latte-bg-secondary border border-latte-text-primary/10
                        shadow-latte-lg py-2 z-50">
          {themeList.map((t) => (
            <button
              key={t.name}
              onClick={() => { setTheme(t.name); setOpen(false); }}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm
                         transition-colors ${
                           theme === t.name
                             ? "text-latte-gold bg-latte-sidebar-active-bg"
                             : "text-latte-text-secondary hover:text-latte-text-primary hover:bg-latte-bg-tertiary"
                         }`}
            >
              <span className="text-base">{t.emoji}</span>
              <span>{t.label}</span>
              {theme === t.name && (
                <span className="ml-auto w-2 h-2 rounded-full bg-latte-gold" />
              )}
              <span className="ml-auto flex gap-0.5">
                <span
                  className="w-3 h-3 rounded-full border border-latte-text-primary/10"
                  style={{ backgroundColor: t.preview.bg }}
                />
                <span
                  className="w-3 h-3 rounded-full border border-latte-text-primary/10"
                  style={{ backgroundColor: t.preview.accent }}
                />
                <span
                  className="w-3 h-3 rounded-full border border-latte-text-primary/10"
                  style={{ backgroundColor: t.preview.text }}
                />
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

### 步骤 5：修复 globals.css 硬编码

将所有硬编码 `rgba()` 替换为新增的辅助 CSS 变量：

```css
/* 修复前 */
.latte-glass {
  background: rgba(20, 17, 14, 0.55);
  border: 1px solid rgba(245, 230, 211, 0.06);
}

/* 修复后 */
.latte-glass {
  background: var(--latte-glass-bg);
  border: 1px solid var(--latte-glass-border);
}
```

完整的替换映射关系：

| 组件类 | 原硬编码 | 替换为 |
|--------|---------|--------|
| `.latte-hero-bg` | `rgba(196,167,125,0.15)` | `var(--latte-hero-gradient-1)` |
| `.latte-hero-bg` | `rgba(212,165,154,0.08)` | `var(--latte-hero-gradient-2)` |
| `.latte-glass` | `rgba(20,17,14,0.55)` | `var(--latte-glass-bg)` |
| `.latte-glass` | `rgba(245,230,211,0.06)` | `var(--latte-glass-border)` |
| `.latte-glass` | `inset 0 1px 0 rgba(245,230,211,0.04)` | `inset 0 1px 0 var(--latte-glass-inset)` |
| `.latte-glass:hover` | `rgba(196,167,125,0.2)` | `var(--latte-glass-hover-border)` |
| `.latte-glass:hover` | `inset 0 1px 0 rgba(245,230,211,0.08)` | `inset 0 1px 0 var(--latte-glass-hover-inset)` |
| `.latte-btn-primary` | `linear-gradient(...0.14, ...0.04)` | `linear-gradient(180deg, var(--latte-btn-gradient-from), var(--latte-btn-gradient-to))` |
| `.latte-btn-primary` | `rgba(232,220,196,0.22)` | `var(--latte-btn-border)` |
| `.latte-btn-primary` | `0 1px 2px rgba(0,0,0,0.2)` | `var(--latte-btn-shadow)` |
| `.latte-btn-primary:hover` | `linear-gradient(...0.2, ...0.08)` | `linear-gradient(180deg, var(--latte-btn-hover-gradient-from), var(--latte-btn-hover-gradient-to))` |
| `.latte-btn-primary:hover` | `rgba(232,220,196,0.35)` | `var(--latte-btn-hover-border)` |
| `.latte-btn-secondary` | `rgba(245,230,211,0.1)` | `var(--latte-btn-secondary-border)` |
| `.latte-btn-secondary:hover` | `rgba(245,230,211,0.18)` | `var(--latte-btn-secondary-hover-border)` |
| `.latte-badge` | `rgba(255,255,255,0.08)` | `var(--latte-badge-inset)` |
| `.latte-badge-success` | `color: #D4DACA` | `color: var(--latte-badge-success-text)` |
| `.latte-badge-warning` | `color: #E8C4B0` | `color: var(--latte-badge-warning-text)` |
| `.latte-badge-critical` | `color: #E8B8B8` | `color: var(--latte-badge-critical-text)` |
| `.latte-badge-info` | `color: #D8CFC4` | `color: var(--latte-badge-info-text)` |
| `.latte-input:focus` | `rgba(196,167,125,0.4)` | `var(--latte-input-focus-border)` |
| `.latte-input:focus` | `0 0 0 3px rgba(196,167,125,0.1)` | `0 0 0 3px var(--latte-input-focus-ring)` |
| `.latte-sidebar` | `rgba(10,8,6,0.8)` | `var(--latte-sidebar-bg)` |
| `.latte-sidebar` | `rgba(245,230,211,0.04)` | `var(--latte-sidebar-border)` |
| `.latte-sidebar-item:hover` | `rgba(196,167,125,0.08)` | `var(--latte-sidebar-active-bg)` |
| `.latte-sidebar-item:hover` | `0 0 16px rgba(196,167,125,0.1)` | `0 0 16px var(--latte-sidebar-active-shadow)` |

### 步骤 6：修复 Tailwind Config

将硬编码颜色值改为 `var()` 引用，使其跟随 CSS 变量动态变化：

```typescript
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
          "bg-deep": "var(--latte-bg-deep)",
          "bg-primary": "var(--latte-bg-primary)",
          "bg-secondary": "var(--latte-bg-secondary)",
          "bg-tertiary": "var(--latte-bg-tertiary)",
          "bg-hover": "var(--latte-bg-hover)",
          "text-primary": "var(--latte-text-primary)",
          "text-secondary": "var(--latte-text-secondary)",
          "text-tertiary": "var(--latte-text-tertiary)",
          "text-muted": "var(--latte-text-muted)",
          accent: "var(--latte-accent)",
          "accent-hover": "var(--latte-accent-hover)",
          gold: "var(--latte-gold)",
          "gold-dim": "var(--latte-gold-dim)",
          "gold-glow": "var(--latte-gold-glow)",
          rose: "var(--latte-rose)",
          "rose-dim": "var(--latte-rose-dim)",
          "rose-glow": "var(--latte-rose-glow)",
          success: "var(--latte-success)",
          "success-bg": "var(--latte-success-bg)",
          warning: "var(--latte-warning)",
          "warning-bg": "var(--latte-warning-bg)",
          critical: "var(--latte-critical)",
          "critical-bg": "var(--latte-critical-bg)",
          info: "var(--latte-info)",
          "info-bg": "var(--latte-info-bg)",
        },
      },
      // fontFamily、borderRadius、boxShadow、transitionTimingFunction 保持不变
    },
  },
  plugins: [],
};

export default config;
```

### 步骤 7：修复 TSX 文件中的硬编码

需要修改的文件：

| 文件 | 修复方式 |
|------|---------|
| `metrics/page.tsx` | 将 `rgba(245,230,211,...)` 替换为 `var(--latte-text-primary)` 的半透明版本，或新增辅助变量 |
| `hero-section.tsx` | 使用 `var(--latte-hero-gradient-1)` / `var(--latte-hero-gradient-2)` |
| `architecture-flow.tsx` | 使用 `var(--latte-gold-glow)` |
| `steam-particles.tsx` | 读取 `var(--latte-particle-color-1)` / `var(--latte-particle-color-2)` |
| `page.tsx` (落地页) | 使用 `var(--latte-hero-gradient-1)` |

**steam-particles.tsx 特殊处理**（Canvas 需要 RGB 值）：

```tsx
// 之前
const color1 = "196, 167, 125";
const color2 = "212, 165, 154";

// 之后
const color1 = getComputedStyle(document.documentElement)
  .getPropertyValue("--latte-particle-color-1").trim();
const color2 = getComputedStyle(document.documentElement)
  .getPropertyValue("--latte-particle-color-2").trim();
```

### 步骤 8：集成到应用

#### 8.1 修改 `layout.tsx`

```tsx
import { ThemeProvider } from "@/themes/ThemeProvider";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">
        <ThemeProvider>
          <ProgressBar />
          <EnvCheck />
          <ToastProvider>
            <ErrorBoundary>{children}</ErrorBoundary>
          </ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
```

#### 8.2 修改 `header.tsx`，添加 ThemeSwitcher

```tsx
import { ThemeSwitcher } from "@/components/ui/theme-switcher";

// 在 Header 组件的右侧区域添加：
<div className="flex items-center gap-4">
  <ThemeSwitcher />
  <RealtimeIndicator ... />
  {/* ... 其他按钮 */}
</div>
```

### 步骤 9：添加全局过渡动画

在 `globals.css` 中添加：

```css
html {
  transition: background-color 0.3s ease, color 0.3s ease;
}

html * {
  transition: background-color 0.3s ease,
              color 0.3s ease,
              border-color 0.3s ease,
              box-shadow 0.3s ease;
}
```

> **注意**：全局 `*` 选择器的 transition 可能影响动画性能。如遇到性能问题，可缩小范围至 `.latte-glass, .latte-btn-primary, .latte-sidebar` 等具体组件类。

---

## 五、扩展指南

### 5.1 新增自定义主题

1. 在 `tokens.ts` 中新增一套 `ThemeTokens` 定义
2. 在 `themeList` 数组中添加元信息
3. 在 `themes` 对象中注册

```ts
const oceanBreeze: ThemeTokens = {
  "--latte-bg-primary": "#0B1622",
  "--latte-gold": "#4ECDC4",
  // ... 定义所有 50+ 变量
};

export const themes = {
  "latte-night": latteNight,
  "latte-light": latteLight,
  "rose-latte": roseLatte,
  "ocean-breeze": oceanBreeze,  // 新增
};
```

### 5.2 支持用户自定义配色

可在「系统设置」页面中增加颜色选择器，让用户微调特定 Token 值，存入 localStorage：

```ts
// 用户自定义覆盖
const customOverrides = JSON.parse(localStorage.getItem("latte-custom-theme") || "{}");
Object.entries(customOverrides).forEach(([k, v]) => {
  document.documentElement.style.setProperty(k, v as string);
});
```

### 5.3 跟随系统主题

```ts
// 在 ThemeProvider 中
useEffect(() => {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  if (!localStorage.getItem(STORAGE_KEY)) {
    setTheme(mq.matches ? "latte-night" : "latte-light");
  }
  mq.addEventListener("change", (e) => {
    if (!localStorage.getItem(STORAGE_KEY)) {
      setTheme(e.matches ? "latte-night" : "latte-light");
    }
  });
}, []);
```

---

## 六、实施计划

| 阶段 | 内容 | 涉及文件 | 预计工作量 |
|------|------|---------|-----------|
| **Phase 1** | 修复硬编码 + 新增辅助 CSS 变量 | `globals.css` | 核心步骤 |
| **Phase 2** | Tailwind Config 改为 var() | `tailwind.config.ts` | 核心步骤 |
| **Phase 3** | 创建 ThemeProvider + tokens | 3 个新文件 | 核心步骤 |
| **Phase 4** | 创建 ThemeSwitcher 组件 | 1 个新文件 | 核心步骤 |
| **Phase 5** | 集成到 layout + header | 2 个文件 | 核心步骤 |
| **Phase 6** | 修复 TSX 硬编码 | 5 个文件 | 优化步骤 |
| **Phase 7** | 添加过渡动画 | `globals.css` | 优化步骤 |
| **Phase 8** | 全面测试 + 微调颜色 | 所有页面 | 验证步骤 |

---

## 七、兼容性说明

| 特性 | Chrome | Firefox | Safari | Edge |
|------|--------|---------|--------|------|
| CSS 自定义属性 | ✅ 49+ | ✅ 31+ | ✅ 9.1+ | ✅ 15+ |
| `data-*` 属性选择器 | ✅ 全版本 | ✅ 全版本 | ✅ 全版本 | ✅ 全版本 |
| `backdrop-filter` | ✅ 76+ | ✅ 103+ | ✅ 9+ | ✅ 79+ |
| `localStorage` | ✅ 4+ | ✅ 3.5+ | ✐ 4+ | ✅ 12+ |

本方案不使用 `color-mix()` 等新特性，兼容性极佳。
