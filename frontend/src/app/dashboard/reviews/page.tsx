"use client";

import { useState, useCallback } from "react";
import { useReviews } from "@/hooks/use-reviews";
import { useSSE } from "@/hooks/use-sse";
import { ReviewList } from "@/components/dashboard/review-list";
import { Input } from "@/components/ui/input";
import { FadeInUp } from "@/components/motion/fade-in-up";
import type { ReviewUpdate } from "@/types";

const statusOptions = ["all", "pending", "running", "completed", "failed", "skipped"];
const riskOptions = ["all", "low", "medium", "high", "critical"];

export default function ReviewsPage() {
  const [status, setStatus] = useState<string>("all");
  const [risk, setRisk] = useState<string>("all");
  const [search, setSearch] = useState("");
  const { reviews: rawReviews, isLoading, mutate } = useReviews({
    status: status === "all" ? undefined : status,
    repo: search || undefined,
  });

  const reviews = rawReviews.filter((r) => {
    if (risk === "all") return true;
    return r.risk_level === risk;
  });

  const handleSSE = useCallback(
    (update: ReviewUpdate) => {
      mutate((prev) => {
        if (!prev) return prev;
        return prev.map((r) =>
          r.id === update.review_id
            ? { ...r, status: update.status, completed_at: update.status === "completed" ? new Date().toISOString() : r.completed_at }
            : r
        );
      }, false);
    },
    [mutate]
  );

  useSSE(handleSSE);

  return (
    <div className="max-w-6xl mx-auto">
      <FadeInUp>
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-8">
          <h1 className="text-2xl font-display font-semibold tracking-tight text-latte-text-primary">
            Reviews
          </h1>
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
            <div className="flex flex-wrap gap-1.5">
              {statusOptions.map((s) => (
                <button
                  key={s}
                  onClick={() => setStatus(s)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-latte-md transition-colors ${
                    status === s
                      ? "bg-latte-gold/15 text-latte-gold border border-latte-gold/30"
                      : "text-latte-text-tertiary hover:text-latte-text-primary hover:bg-latte-bg-tertiary"
                  }`}
                >
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {riskOptions.map((r) => (
                <button
                  key={r}
                  onClick={() => setRisk(r)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-latte-md transition-colors ${
                    risk === r
                      ? "bg-latte-rose/15 text-latte-rose border border-latte-rose/30"
                      : "text-latte-text-tertiary hover:text-latte-text-primary hover:bg-latte-bg-tertiary"
                  }`}
                >
                  {r.charAt(0).toUpperCase() + r.slice(1)}
                </button>
              ))}
            </div>
            <Input
              placeholder="Filter by repo..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-48 h-9 text-sm"
            />
          </div>
        </div>
      </FadeInUp>

      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-24 rounded-latte-xl bg-latte-bg-secondary animate-pulse"
            />
          ))}
        </div>
      ) : reviews.length === 0 ? (
        <FadeInUp delay={0.1}>
          <div className="flex flex-col items-center justify-center py-20 text-latte-text-tertiary">
            <p className="text-lg font-medium">No reviews found</p>
            <p className="text-sm mt-1">Try adjusting your filters</p>
          </div>
        </FadeInUp>
      ) : (
        <FadeInUp delay={0.1}>
          <ReviewList reviews={reviews} />
        </FadeInUp>
      )}
    </div>
  );
}
