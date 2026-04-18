"use client";

import { useRouter } from "next/navigation";
import { HeroSection } from "@/components/landing/hero-section";
import { BentoGrid } from "@/components/landing/bento-grid";
import { DashboardPreview } from "@/components/landing/dashboard-preview";
import { ArchitectureFlow } from "@/components/landing/architecture-flow";
import { Button } from "@/components/ui/button";
import { FadeInUp } from "@/components/motion/fade-in-up";
import {
  Server,
  Database,
  Cpu,
  GitBranch,
  Box,
  CheckCircle,
} from "lucide-react";

const specs = [
  { label: "语言", value: "Python 3.11+", icon: Server },
  { label: "框架", value: "FastAPI + Celery", icon: Cpu },
  { label: "数据库", value: "PostgreSQL 16 + pgvector", icon: Database },
  { label: "LLM 提供商", value: "DeepSeek, Claude, Qwen", icon: GitBranch },
  { label: "静态分析", value: "Semgrep", icon: Box },
  { label: "测试覆盖", value: "72+ 自动化测试", icon: CheckCircle },
];

export default function HomePage() {
  const router = useRouter();
  return (
    <main className="bg-latte-bg-primary">
      <HeroSection />

      {/* Architecture Visual */}
      <section className="py-24 px-6 max-w-7xl mx-auto">
        <FadeInUp>
          <h2
            className="font-display font-semibold tracking-tight text-latte-text-primary text-center mb-6"
            style={{ fontSize: "clamp(36px, 5vw, 64px)", lineHeight: 1.1 }}
          >
            为规模化而生
          </h2>
          <p className="text-lg text-latte-text-secondary text-center max-w-2xl mx-auto mb-16">
            从 Webhook 接收到评论发布，全链路异步处理，支持 Kubernetes 水平扩展。
          </p>
        </FadeInUp>

        <ArchitectureFlow />
      </section>

      <BentoGrid />
      <DashboardPreview />

      {/* 技术规格 */}
      <section className="py-24 px-6 max-w-5xl mx-auto">
        <FadeInUp>
          <h2
            className="font-display font-semibold tracking-tight text-latte-text-primary text-center mb-14"
            style={{ fontSize: "clamp(36px, 5vw, 64px)", lineHeight: 1.1 }}
          >
            技术规格
          </h2>
        </FadeInUp>
        <div className="space-y-4">
          {specs.map((spec, i) => {
            const Icon = spec.icon;
            return (
              <FadeInUp key={spec.label} delay={i * 0.05}>
                <div className="latte-glass p-5 flex items-center justify-between hover:border-latte-gold/20">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-latte-md bg-latte-bg-tertiary flex items-center justify-center text-latte-gold">
                      <Icon size={18} strokeWidth={1.5} />
                    </div>
                    <span className="text-sm text-latte-text-tertiary">{spec.label}</span>
                  </div>
                  <span className="text-base font-medium text-latte-text-primary">{spec.value}</span>
                </div>
              </FadeInUp>
            );
          })}
        </div>
      </section>

      {/* CTA & Footer */}
      <section
        className="py-32 px-6 text-center"
        style={{
          background: `radial-gradient(ellipse 60% 40% at 50% 100%, rgba(196, 167, 125, 0.12), transparent), var(--latte-bg-primary)`,
        }}
      >
        <FadeInUp>
          <h2
            className="font-display font-semibold tracking-tight text-latte-text-primary mb-6"
            style={{ fontSize: "clamp(36px, 5vw, 64px)", lineHeight: 1.1 }}
          >
            从今天开始，酿造更优质的代码
          </h2>
          <p className="text-lg text-latte-text-secondary max-w-xl mx-auto mb-10">
            让 Latte PR Agent 成为你团队的代码审查专家。
          </p>
          <div className="flex items-center justify-center gap-4">
            <Button size="lg" onClick={() => router.push("/dashboard/reviews")}>
              开始使用
            </Button>
            <Button variant="secondary" size="lg" onClick={() => router.push("/dashboard")}>
              仪表盘
            </Button>
          </div>
        </FadeInUp>

        <footer className="mt-24 pt-8 border-t border-latte-text-primary/5 text-sm text-latte-text-muted">
          <p>© 2026 Latte PR Agent. MIT License.</p>
        </footer>
      </section>
    </main>
  );
}
