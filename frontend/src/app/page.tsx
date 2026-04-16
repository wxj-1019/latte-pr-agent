"use client";

import { HeroSection } from "@/components/landing/hero-section";
import { BentoGrid } from "@/components/landing/bento-grid";
import { DashboardPreview } from "@/components/landing/dashboard-preview";
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
  { label: "Language", value: "Python 3.11+", icon: Server },
  { label: "Framework", value: "FastAPI + Celery", icon: Cpu },
  { label: "Database", value: "PostgreSQL 16 + pgvector", icon: Database },
  { label: "LLM Providers", value: "DeepSeek, Claude, Qwen", icon: GitBranch },
  { label: "Static Analysis", value: "Semgrep", icon: Box },
  { label: "Test Coverage", value: "72+ Automated Tests", icon: CheckCircle },
];

export default function HomePage() {
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
            Brewed for Scale
          </h2>
          <p className="text-lg text-latte-text-secondary text-center max-w-2xl mx-auto mb-16">
            从 Webhook 接收到评论发布，全链路异步处理，支持 Kubernetes 水平扩展。
          </p>
        </FadeInUp>

        <FadeInUp delay={0.1}>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="latte-glass p-8 text-center">
              <div className="w-14 h-14 mx-auto rounded-full bg-latte-bg-tertiary border border-latte-text-primary/5 flex items-center justify-center text-latte-gold mb-4">
                <GitBranch size={24} strokeWidth={1.5} />
              </div>
              <h3 className="text-lg font-medium text-latte-text-primary mb-2">Webhook Ingest</h3>
              <p className="text-sm text-latte-text-secondary">GitHub / GitLab events validated and queued</p>
            </div>
            <div className="latte-glass p-8 text-center">
              <div className="w-14 h-14 mx-auto rounded-full bg-latte-bg-tertiary border border-latte-text-primary/5 flex items-center justify-center text-latte-rose mb-4">
                <Cpu size={24} strokeWidth={1.5} />
              </div>
              <h3 className="text-lg font-medium text-latte-text-primary mb-2">Celery Workers</h3>
              <p className="text-sm text-latte-text-secondary">Multi-model review, AST analysis, static checks</p>
            </div>
            <div className="latte-glass p-8 text-center">
              <div className="w-14 h-14 mx-auto rounded-full bg-latte-bg-tertiary border border-latte-text-primary/5 flex items-center justify-center text-latte-success mb-4">
                <Database size={24} strokeWidth={1.5} />
              </div>
              <h3 className="text-lg font-medium text-latte-text-primary mb-2">Persistent Store</h3>
              <p className="text-sm text-latte-text-secondary">PostgreSQL + pgvector for embeddings</p>
            </div>
          </div>
        </FadeInUp>
      </section>

      <BentoGrid />
      <DashboardPreview />

      {/* Tech Specs */}
      <section className="py-24 px-6 max-w-5xl mx-auto">
        <FadeInUp>
          <h2
            className="font-display font-semibold tracking-tight text-latte-text-primary text-center mb-14"
            style={{ fontSize: "clamp(36px, 5vw, 64px)", lineHeight: 1.1 }}
          >
            Tech Specs
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
            Start Brewing Better Code Today
          </h2>
          <p className="text-lg text-latte-text-secondary max-w-xl mx-auto mb-10">
            让 Latte PR Agent 成为你团队的代码审查专家。
          </p>
          <div className="flex items-center justify-center gap-4">
            <Button size="lg">Get Started</Button>
            <Button variant="secondary" size="lg">
              Read the Docs
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
