# Latte PR Agent 前端组件大纲

本文档提供从设计规范到代码落地的组件层级、文件结构与接口设计建议。基于 Next.js 14 (App Router) + React + TypeScript + Tailwind CSS 架构。

---

## 一、项目文件结构

```
frontend/
├── app/
│   ├── layout.tsx              # 根布局，注入 latte-theme.css
│   ├── page.tsx                # Landing Page（营销官网）
│   ├── dashboard/
│   │   ├── layout.tsx          # Dashboard 布局（Sidebar + Header）
│   │   ├── page.tsx            # Dashboard 首页（重定向到 /dashboard/reviews）
│   │   ├── reviews/
│   │   │   ├── page.tsx        # Review 列表页
│   │   │   └── [id]/
│   │   │       └── page.tsx    # Review 详情页
│   │   ├── metrics/
│   │   │   └── page.tsx        # 指标统计页
│   │   ├── config/
│   │   │   └── page.tsx        # 项目配置页
│   │   └── prompts/
│   │       └── page.tsx        # Prompt 管理页
│   ├── api/                    # Next.js API routes（可选代理）
│   └── globals.css             # Tailwind 导入 + 主题变量覆盖
├── components/
│   ├── landing/                # Landing Page 专用组件
│   ├── dashboard/              # Dashboard 专用组件
│   ├── ui/                     # 通用原子组件
│   └── motion/                 # 动画包装组件
├── hooks/                      # 自定义 Hooks
├── lib/                        # 工具函数、API 客户端
├── types/                      # TypeScript 类型定义
└── public/
    └── assets/                 # 静态资源（3D、图片、图标）
```

---

## 二、通用 UI 组件 (components/ui/)

### 2.1 Button

```tsx
// components/ui/button.tsx
import { ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center font-medium transition-all",
          "duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
          variant === "primary" && [
            "latte-btn-primary",
            size === "sm" && "px-5 py-2.5 text-sm",
            size === "md" && "px-7 py-3.5 text-[15px]",
            size === "lg" && "px-9 py-4 text-base",
          ],
          variant === "secondary" && [
            "latte-btn-secondary",
            size === "sm" && "px-5 py-2.5 text-sm",
            size === "md" && "px-7 py-3.5 text-[15px]",
            size === "lg" && "px-9 py-4 text-base",
          ],
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
```

### 2.2 Badge

```tsx
// components/ui/badge.tsx
import { cn } from "@/lib/utils";

type BadgeVariant = "success" | "warning" | "critical" | "info";

interface BadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
  dot?: boolean;
  className?: string;
}

export function Badge({ variant, children, dot = true, className }: BadgeProps) {
  return (
    <span className={cn("latte-badge", `latte-badge-${variant}`, className)}>
      {dot && <span className="latte-badge-dot" />}
      {children}
    </span>
  );
}
```

### 2.3 GlassCard

```tsx
// components/ui/glass-card.tsx
import { cn } from "@/lib/utils";

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
}

export function GlassCard({ children, className, hover = true }: GlassCardProps) {
  return (
    <div
      className={cn(
        "latte-glass p-8",
        hover && "cursor-pointer",
        className
      )}
    >
      {children}
    </div>
  );
}
```

### 2.4 Input

```tsx
// components/ui/input.tsx
import { InputHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn("latte-input", className)}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";
```

---

## 三、Landing Page 组件 (components/landing/)

### 3.1 HeroSection

```tsx
// components/landing/hero-section.tsx
"use client";

import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";

export function HeroSection() {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden latte-hero-bg">
      {/* 蒸汽粒子背景层（Canvas 或简单 CSS 动画） */}
      <SteamParticles />

      {/* 3D 拉花装饰（Spline 嵌入或 CSS 3D） */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 opacity-60">
        <LatteArt3D />
      </div>

      <div className="relative z-10 text-center max-w-5xl px-6">
        <motion.h1
          initial={{ opacity: 0, y: 40, filter: "blur(10px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
          className="latte-display mb-6"
        >
          Enterprise AI Code Review,
          <br />
          <span className="text-[var(--latte-gold)]">Reimagined.</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 30, filter: "blur(8px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 0.9, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="latte-body text-xl max-w-3xl mx-auto mb-10"
        >
          Latte PR Agent 为企业级代码审查注入智能与温度。
          多模型协同、上下文感知、质量门禁——
          如同一杯完美萃取的拿铁，每一个细节都恰到好处。
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="flex items-center justify-center gap-4"
        >
          <Button size="lg">Get Started</Button>
          <Button variant="secondary" size="lg">View Dashboard</Button>
        </motion.div>
      </div>
    </section>
  );
}
```

### 3.2 SteamParticles

```tsx
// components/landing/steam-particles.tsx
"use client";

import { useEffect, useRef } from "react";

export function SteamParticles() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    // 轻量级 Canvas 粒子动画，模拟金色和玫瑰色的蒸汽缓慢上升
    // 粒子数量控制在 30-50 个，保证性能
    // 颜色：rgba(196, 167, 125, 0.08) 和 rgba(212, 165, 154, 0.05)
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-none"
    />
  );
}
```

### 3.3 BentoGrid

```tsx
// components/landing/bento-grid.tsx
"use client";

import { motion } from "framer-motion";
import { GlassCard } from "@/components/ui/glass-card";

const features = [
  {
    id: "multi-model",
    title: "Multi-Model Intelligence",
    description: "主模型初筛，Reasoner 复核，自动降级永不掉线。",
    size: "large", // spans 2 cols
    icon: "RingsIcon",
  },
  {
    id: "context",
    title: "Context-Aware Analysis",
    description: "Tree-sitter 解析 + 依赖图构建，审查不再是盲人摸象。",
    size: "small",
    icon: "TreeIcon",
  },
  // ... 更多卡片
];

export function BentoGrid() {
  return (
    <section className="py-32 px-6 max-w-7xl mx-auto">
      <motion.h2
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.8 }}
        className="latte-headline text-center mb-20"
      >
        Brewed for Precision
      </motion.h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 auto-rows-[280px]">
        {features.map((feature, i) => (
          <motion.div
            key={feature.id}
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: i * 0.1 }}
            className={cn(
              feature.size === "large" && "md:col-span-2",
              feature.size === "tall" && "md:row-span-2"
            )}
          >
            <GlassCard className="h-full flex flex-col justify-between">
              <div>{/* 图标 */}</div>
              <div>
                <h3 className="latte-title mb-2">{feature.title}</h3>
                <p className="latte-caption">{feature.description}</p>
              </div>
            </GlassCard>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
```

### 3.4 DashboardPreview

```tsx
// components/landing/dashboard-preview.tsx
"use client";

import { motion } from "framer-motion";

export function DashboardPreview() {
  return (
    <section className="py-32 px-6 overflow-hidden">
      <div className="max-w-7xl mx-auto text-center mb-16">
        <h2 className="latte-headline mb-4">Every Review, Visualized</h2>
        <p className="latte-body text-lg">
          从 PR 概览到单条发现的置信度，所有数据一目了然。
        </p>
      </div>

      <motion.div
        initial={{ opacity: 0, rotateX: 15, y: 60 }}
        whileInView={{ opacity: 1, rotateX: 5, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
        whileHover={{ rotateX: 0, scale: 1.02 }}
        className="max-w-6xl mx-auto perspective-[1000px]"
      >
        <div className="latte-glass p-2 rounded-[32px]">
          <div className="bg-[var(--latte-bg-deep)] rounded-[24px] overflow-hidden min-h-[500px]">
            {/* 模拟 Dashboard UI */}
            <MockDashboardUI />
          </div>
        </div>
      </motion.div>
    </section>
  );
}
```

---

## 四、Dashboard 组件 (components/dashboard/)

### 4.1 DashboardLayout

```tsx
// app/dashboard/layout.tsx
import { Sidebar } from "@/components/dashboard/sidebar";
import { Header } from "@/components/dashboard/header";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-[var(--latte-bg-primary)]">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Header />
        <main className="flex-1 p-8 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
```

### 4.2 Sidebar

```tsx
// components/dashboard/sidebar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { GitPullRequest, BarChart3, Settings, FileText } from "lucide-react";

const navItems = [
  { href: "/dashboard/reviews", icon: GitPullRequest, label: "Reviews" },
  { href: "/dashboard/metrics", icon: BarChart3, label: "Metrics" },
  { href: "/dashboard/config", icon: Settings, label: "Config" },
  { href: "/dashboard/prompts", icon: FileText, label: "Prompts" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="latte-sidebar">
      <div className="mb-8">
        <span className="text-xl font-bold text-[var(--latte-gold)]">L</span>
      </div>
      <nav className="flex flex-col gap-2">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "latte-sidebar-item",
              pathname.startsWith(item.href) && "active"
            )}
            title={item.label}
          >
            <item.icon size={20} strokeWidth={1.5} />
          </Link>
        ))}
      </nav>
    </aside>
  );
}
```

### 4.3 ReviewList

```tsx
// components/dashboard/review-list.tsx
import { Review } from "@/types/review";
import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";

interface ReviewListProps {
  reviews: Review[];
}

export function ReviewList({ reviews }: ReviewListProps) {
  return (
    <div className="space-y-4">
      {reviews.map((review) => (
        <Link key={review.id} href={`/dashboard/reviews/${review.id}`}>
          <GlassCard className="flex items-center justify-between py-5 px-6">
            <div className="flex items-center gap-4">
              <Badge
                variant={
                  review.status === "completed"
                    ? "success"
                    : review.status === "pending"
                    ? "warning"
                    : "info"
                }
              >
                {review.status}
              </Badge>
              <div>
                <h4 className="font-medium text-[var(--latte-text-primary)]">
                  {review.pr_title || `PR #${review.pr_number}`}
                </h4>
                <p className="text-sm text-[var(--latte-text-tertiary)]">
                  {review.repo_id}
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm text-[var(--latte-text-secondary)]">
                {review.ai_model || "deepseek-chat"}
              </p>
              <p className="text-xs text-[var(--latte-text-muted)]">
                {new Date(review.created_at).toLocaleDateString()}
              </p>
            </div>
          </GlassCard>
        </Link>
      ))}
    </div>
  );
}
```

### 4.4 MetricsChart

```tsx
// components/dashboard/metrics-chart.tsx
"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

interface MetricsData {
  date: string;
  reviews: number;
  findings: number;
}

interface MetricsChartProps {
  data: MetricsData[];
}

export function MetricsChart({ data }: MetricsChartProps) {
  return (
    <div className="h-[300px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="rgba(245, 230, 211, 0.06)"
          />
          <XAxis
            dataKey="date"
            stroke="var(--latte-text-tertiary)"
            tick={{ fill: "var(--latte-text-tertiary)", fontSize: 12 }}
            axisLine={{ stroke: "rgba(245, 230, 211, 0.1)" }}
          />
          <YAxis
            stroke="var(--latte-text-tertiary)"
            tick={{ fill: "var(--latte-text-tertiary)", fontSize: 12 }}
            axisLine={{ stroke: "rgba(245, 230, 211, 0.1)" }}
          />
          <Tooltip
            contentStyle={{
              background: "var(--latte-bg-secondary)",
              border: "1px solid rgba(245, 230, 211, 0.1)",
              borderRadius: "12px",
            }}
            labelStyle={{ color: "var(--latte-text-primary)" }}
            itemStyle={{ color: "var(--latte-text-secondary)" }}
          />
          <Line
            type="monotone"
            dataKey="reviews"
            stroke="var(--latte-gold)"
            strokeWidth={2}
            dot={{ fill: "var(--latte-gold)", strokeWidth: 0, r: 3 }}
            activeDot={{ r: 5, fill: "var(--latte-accent)" }}
          />
          <Line
            type="monotone"
            dataKey="findings"
            stroke="var(--latte-rose)"
            strokeWidth={2}
            dot={{ fill: "var(--latte-rose)", strokeWidth: 0, r: 3 }}
            activeDot={{ r: 5, fill: "var(--latte-rose)" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

---

## 五、类型定义 (types/)

```ts
// types/review.ts
export interface Review {
  id: number;
  org_id: string;
  platform: "github" | "gitlab";
  repo_id: string;
  pr_number: number;
  pr_title?: string;
  pr_author?: string;
  base_branch?: string;
  head_branch?: string;
  head_sha?: string;
  status: "pending" | "completed" | "skipped" | "failed";
  risk_level?: "low" | "medium" | "high" | "critical";
  trigger_type?: string;
  review_mode: string;
  prompt_version?: string;
  diff_stats?: Record<string, number>;
  created_at: string;
  completed_at?: string;
}

export interface ReviewFinding {
  id: number;
  review_id: number;
  file_path: string;
  line_number?: number;
  category?: string;
  severity: "info" | "warning" | "critical";
  description: string;
  suggestion?: string;
  confidence?: number;
  ai_model?: string;
  created_at: string;
}

export interface ReviewMetrics {
  total_reviews: number;
  total_findings: number;
  false_positive_rate: number;
  avg_confidence: number;
}
```

---

## 六、动画包装组件 (components/motion/)

### 6.1 FadeInUp

```tsx
// components/motion/fade-in-up.tsx
"use client";

import { motion } from "framer-motion";

interface FadeInUpProps {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}

export function FadeInUp({ children, delay = 0, className }: FadeInUpProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 40, filter: "blur(8px)" }}
      whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{
        duration: 0.8,
        delay,
        ease: [0.16, 1, 0.3, 1],
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
```

### 6.2 StaggerContainer

```tsx
// components/motion/stagger-container.tsx
"use client";

import { motion } from "framer-motion";

const containerVariants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.1,
    },
  },
};

export function StaggerContainer({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
```

---

## 七、关键开发提示

1. **3D 图形**：Hero 中的 `LatteArt3D` 建议用 **Spline** 制作一个轻量级的循环动画，导出为 public URL 用 iframe 嵌入；或直接用 CSS `@keyframes rotate` 做一个多层圆环的 3D 效果。
2. **代码高亮**：Dashboard 的 Diff 视图推荐使用 **PrismJS** 或 **Shiki**，将背景色设为 `var(--latte-bg-deep)`，关键字用 `var(--latte-rose)`，字符串用 `var(--latte-gold)`，注释用 `var(--latte-text-muted)`。
3. **响应式策略**：Landing Page 的 Bento Grid 在移动端降级为单列；Dashboard 的 Sidebar 在 `md` 以下变为底部固定导航栏。
4. **性能优化**：
   - Canvas 蒸汽粒子在 `prefers-reduced-motion` 时完全禁用。
   - Recharts 图表使用 `ResponsiveContainer` 避免布局抖动。
   - 3D 元素仅在 `lg` 以上屏幕加载，移动端用静态 SVG 替代。
