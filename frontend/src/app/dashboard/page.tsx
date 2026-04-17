"use client";

import { useStats } from "@/hooks/use-stats";
import { GlassCard } from "@/components/ui/glass-card";
import { FadeInUp } from "@/components/motion/fade-in-up";
import { StatusBadge } from "@/components/ui/status-badge";
import { CountUp } from "@/components/ui/count-up";
import Link from "next/link";

export default function DashboardPage() {
  const { stats, isLoading, error } = useStats();

  if (error) {
    return (
      <div className="max-w-6xl mx-auto flex flex-col items-center justify-center py-20 text-latte-text-tertiary">
        <p className="text-lg font-medium">Failed to load dashboard stats</p>
        <p className="text-sm mt-1">{error.message || "Please try again later"}</p>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <FadeInUp>
        <h1 className="text-2xl font-display font-semibold tracking-tight text-latte-text-primary">
          Dashboard
        </h1>
        <p className="text-sm text-latte-text-tertiary mt-1">
          Overview of your code review activity
        </p>
      </FadeInUp>

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
              <p className="text-sm text-latte-text-tertiary">Total Reviews</p>
              <p className="text-3xl font-display font-semibold text-latte-text-primary mt-2">
                <CountUp value={stats.total_reviews} />
              </p>
            </GlassCard>
            <GlassCard className="p-6" variant="elevated">
              <p className="text-sm text-latte-text-tertiary">Pending</p>
              <p className="text-3xl font-display font-semibold text-latte-text-primary mt-2">
                <CountUp value={stats.pending_reviews} />
              </p>
            </GlassCard>
            <GlassCard className="p-6" variant="elevated">
              <p className="text-sm text-latte-text-tertiary">Completed</p>
              <p className="text-3xl font-display font-semibold text-latte-text-primary mt-2">
                <CountUp value={stats.completed_reviews} />
              </p>
            </GlassCard>
            <GlassCard className="p-6" variant="elevated">
              <p className="text-sm text-latte-text-tertiary">High Risk</p>
              <p className="text-3xl font-display font-semibold text-latte-rose mt-2">
                <CountUp value={stats.high_risk_count} />
              </p>
            </GlassCard>
          </div>
        </FadeInUp>
      )}

      <FadeInUp delay={0.2}>
        <GlassCard className="p-6">
          <h3 className="text-lg font-medium text-latte-text-primary mb-4">Recent Reviews</h3>
          {isLoading || !stats ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-14 bg-latte-bg-secondary rounded-latte-lg animate-pulse" />
              ))}
            </div>
          ) : stats.recent_reviews.length === 0 ? (
            <div className="text-sm text-latte-text-tertiary py-8 text-center">
              No reviews yet
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
                      #{review.pr_number} {review.pr_title || "Untitled PR"}
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
    </div>
  );
}
