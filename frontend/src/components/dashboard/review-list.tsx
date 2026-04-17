"use client";

import Link from "next/link";
import { GlassCard } from "@/components/ui/glass-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { Badge } from "@/components/ui/badge";
import type { Review } from "@/types";
import { motion } from "framer-motion";
import { AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ReviewListProps {
  reviews: Review[];
}

function formatTimeAgo(isoString: string) {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

export function ReviewList({ reviews }: ReviewListProps) {
  return (
    <div className="space-y-4">
      {reviews.map((review, index) => (
        <motion.div
          key={review.id}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: index * 0.05, ease: [0.16, 1, 0.3, 1] }}
        >
          <Link href={`/dashboard/reviews/${review.id}`}>
            <GlassCard
              variant="status"
              status={review.status}
              className={cn(
                "p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 relative overflow-hidden",
                review.status === "running" && "before:absolute before:inset-y-0 before:left-0 before:w-1 before:bg-gradient-to-b before:from-blue-400 before:via-blue-500 before:to-blue-400 before:animate-pulse",
                review.status === "failed" && "animate-shake"
              )}
            >
              <div className="flex items-start gap-4 min-w-0">
                <StatusBadge status={review.status} />
                <div className="min-w-0">
                  <h4 className="font-medium text-latte-text-primary truncate">
                    {review.platform === "direct" ? (
                      <>
                        <span className="text-latte-gold">#ANALYZE</span>{" "}
                        {review.pr_title?.replace("Direct analysis: ", "") || "Untitled"}
                      </>
                    ) : (
                      <>
                        #{review.pr_number} {review.pr_title || "Untitled PR"}
                      </>
                    )}
                  </h4>
                  <p className="text-sm text-latte-text-tertiary mt-0.5">
                    {review.platform === "direct" ? (
                      <>
                        Direct analysis {review.ai_model ? `· ${review.ai_model}` : ""}
                      </>
                    ) : (
                      <>
                        {review.repo_id} · {review.ai_model || "unknown model"}
                      </>
                    )}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 sm:text-right">
                {review.status === "failed" && (
                  <div className="flex items-center gap-1.5 text-latte-critical">
                    <AlertCircle size={14} />
                    <span className="text-xs font-medium">Error</span>
                  </div>
                )}
                {review.status === "completed" && review.risk_level && review.risk_level !== "low" && (
                  <Badge
                    variant={
                      review.risk_level === "critical"
                        ? "critical"
                        : review.risk_level === "high"
                        ? "warning"
                        : "info"
                    }
                    dot
                  >
                    {review.risk_level}
                  </Badge>
                )}
                <span className="text-xs text-latte-text-muted whitespace-nowrap">
                  {formatTimeAgo(review.created_at)}
                </span>
              </div>
            </GlassCard>
          </Link>
        </motion.div>
      ))}
    </div>
  );
}
