"use client";

import { useState } from "react";
import { useStats } from "@/hooks/use-stats";
import { GlassCard } from "@/components/ui/glass-card";
import { FadeInUp } from "@/components/motion/fade-in-up";
import { StatusBadge } from "@/components/ui/status-badge";
import { CountUp } from "@/components/ui/count-up";
import { OnboardingWizard } from "@/components/dashboard/onboarding-wizard";
import { Button } from "@/components/ui/button";
import { Rocket } from "lucide-react";
import Link from "next/link";

export default function DashboardPage() {
  const { stats, isLoading, error } = useStats();
  const [showOnboarding, setShowOnboarding] = useState(false);

  if (error) {
    return (
      <div className="max-w-6xl mx-auto flex flex-col items-center justify-center py-20 text-latte-text-tertiary">
        <p className="text-lg font-medium">加载仪表盘数据失败</p>
        <p className="text-sm mt-1">{error.message || "请稍后重试"}</p>
      </div>
    );
  }

  const isEmpty = !isLoading && stats && stats.total_reviews === 0;

  if (isEmpty && showOnboarding) {
    return (
      <div className="py-8">
        <OnboardingWizard onComplete={() => setShowOnboarding(false)} />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <FadeInUp>
        <h1 className="text-2xl font-display font-semibold tracking-tight text-latte-text-primary">
          仪表盘
        </h1>
        <p className="text-sm text-latte-text-tertiary mt-1">
          代码审查活动总览
        </p>
      </FadeInUp>

      {isEmpty && (
        <FadeInUp delay={0.1}>
          <GlassCard className="p-12 text-center" variant="elevated">
            <div className="max-w-md mx-auto">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-latte-2xl bg-latte-gold/10 mb-5">
                <Rocket className="w-7 h-7 text-latte-gold" />
              </div>
              <h3 className="text-lg font-display font-semibold text-latte-text-primary mb-2">
                暂无项目
              </h3>
              <p className="text-sm text-latte-text-tertiary mb-6">
                注册你的第一个仓库即可开始使用。Latte 将自动审查每个拉取请求，检查安全性、代码质量和最佳实践。
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                <Button variant="primary" onClick={() => setShowOnboarding(true)}>
                  <Rocket size={16} />
                  配置你的第一个项目
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => (window.location.href = "/dashboard/analyze")}
                >
                  先试试代码分析
                </Button>
              </div>
            </div>
          </GlassCard>
        </FadeInUp>
      )}

      {!isEmpty && (
        <>
          {isLoading || !stats ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-32 bg-latte-bg-secondary rounded-latte-xl animate-pulse" />
              ))}
            </div>
          ) : (
            <FadeInUp delay={0.1}>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <GlassCard className="p-6" variant="elevated">
                  <p className="text-sm text-latte-text-tertiary">审查总数</p>
                  <p className="text-3xl font-display font-semibold text-latte-text-primary mt-2">
                    <CountUp value={stats.total_reviews} />
                  </p>
                </GlassCard>
                <GlassCard className="p-6" variant="elevated">
                  <p className="text-sm text-latte-text-tertiary">待处理</p>
                  <p className="text-3xl font-display font-semibold text-latte-text-primary mt-2">
                    <CountUp value={stats.pending_reviews} />
                  </p>
                </GlassCard>
                <GlassCard className="p-6" variant="elevated">
                  <p className="text-sm text-latte-text-tertiary">已完成</p>
                  <p className="text-3xl font-display font-semibold text-latte-text-primary mt-2">
                    <CountUp value={stats.completed_reviews} />
                  </p>
                </GlassCard>
                <GlassCard className="p-6" variant="elevated">
                  <p className="text-sm text-latte-text-tertiary">高风险</p>
                  <p className="text-3xl font-display font-semibold text-latte-rose mt-2">
                    <CountUp value={stats.high_risk_count} />
                  </p>
                </GlassCard>
              </div>
            </FadeInUp>
          )}

          <FadeInUp delay={0.2}>
            <GlassCard className="p-6">
              <h3 className="text-lg font-medium text-latte-text-primary mb-4">最近审查</h3>
              {isLoading || !stats ? (
                <div className="space-y-3">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="h-14 bg-latte-bg-secondary rounded-latte-lg animate-pulse" />
                  ))}
                </div>
              ) : stats.recent_reviews.length === 0 ? (
                <div className="text-sm text-latte-text-tertiary py-8 text-center">
                  暂无审查记录 — 向已配置的仓库提交 PR 即可开始
                </div>
              ) : (
                <div className="divide-y divide-latte-text-primary/5">
                  {stats.recent_reviews.map((review) => (
                    <Link
                      key={review.id}
                      href={`/dashboard/reviews/${review.id}`}
                      className="flex items-center justify-between py-4 hover:bg-latte-bg-tertiary/30 px-2 rounded-latte-md transition-colors"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-latte-text-primary truncate">
                          #{review.pr_number} {review.pr_title || "未命名 PR"}
                        </p>
                        <p className="text-xs text-latte-text-tertiary mt-0.5">
                          {review.repo_id} · {new Date(review.created_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <StatusBadge status={review.status} />
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </GlassCard>
          </FadeInUp>
        </>
      )}
    </div>
  );
}
