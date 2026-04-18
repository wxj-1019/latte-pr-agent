"use client";

import { useState, useEffect } from "react";
import { useReviews } from "@/hooks/use-reviews";
import { useSSE } from "@/hooks/use-sse";
import { useDebounce } from "@/hooks/use-debounce";
import { ReviewList } from "@/components/dashboard/review-list";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FadeInUp } from "@/components/motion/fade-in-up";
import type { ReviewUpdate } from "@/types";
import { ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";

const statusOptions = ["all", "pending", "running", "completed", "failed", "skipped"];
const riskOptions = ["all", "low", "medium", "high", "critical"];

const statusLabels: Record<string, string> = {
  all: "全部",
  pending: "待处理",
  running: "进行中",
  completed: "已完成",
  failed: "失败",
  skipped: "已跳过",
};

const riskLabels: Record<string, string> = {
  all: "全部",
  low: "低",
  medium: "中",
  high: "高",
  critical: "严重",
};

export default function ReviewsPage() {
  const [status, setStatus] = useState<string>("all");
  const [risk, setRisk] = useState<string>("all");
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);
  const [page, setPage] = useState(1);

  const {
    reviews,
    total,
    page: currentPage,
    pageSize,
    isLoading,
    error,
    mutate,
  } = useReviews({
    status: status === "all" ? undefined : status,
    repo: debouncedSearch || undefined,
    risk: risk === "all" ? undefined : risk,
    page,
  });

  const { subscribe } = useSSE();

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  useEffect(() => {
    setPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, risk, debouncedSearch]);

  useEffect(() => {
    const unsubscribe = subscribe((update: ReviewUpdate) => {
      mutate((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          data: prev.data.map((r) =>
            r.id === update.review_id
              ? { ...r, status: update.status, completed_at: update.status === "completed" ? new Date().toISOString() : r.completed_at }
              : r
          ),
        };
      }, false);
    });
    return unsubscribe;
  }, [subscribe, mutate]);

  return (
    <div className="max-w-6xl mx-auto">
      <FadeInUp>
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-8">
          <h1 className="text-2xl font-display font-semibold tracking-tight text-latte-text-primary">
            审查
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
                  {statusLabels[s] || s}
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
                  {riskLabels[r] || r}
                </button>
              ))}
            </div>
            <Input
              placeholder="按仓库筛选..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-48 h-9 text-sm"
            />
          </div>
        </div>
      </FadeInUp>

      {error ? (
        <FadeInUp delay={0.1}>
          <div className="flex flex-col items-center justify-center py-20 text-latte-text-tertiary">
            <p className="text-lg font-medium">加载失败</p>
            <p className="text-sm mt-1">{error.message || "无法获取审查列表"}</p>
            <Button
              variant="secondary"
              size="sm"
              className="mt-4"
              onClick={() => mutate()}
            >
              <RefreshCw size={14} className="mr-1.5" />
              重试
            </Button>
          </div>
        </FadeInUp>
      ) : isLoading ? (
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
            <p className="text-lg font-medium">未找到审查记录</p>
            <p className="text-sm mt-1">尝试调整筛选条件</p>
          </div>
        </FadeInUp>
      ) : (
        <FadeInUp delay={0.1}>
          <ReviewList reviews={reviews} />
        </FadeInUp>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <FadeInUp delay={0.15}>
          <div className="flex items-center justify-center gap-3 mt-8">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
            >
              <ChevronLeft size={16} />
              上一页
            </Button>
            <span className="text-sm text-latte-text-secondary">
              第 {currentPage} 页，共 {totalPages} 页
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages}
            >
              下一页
              <ChevronRight size={16} />
            </Button>
          </div>
        </FadeInUp>
      )}
    </div>
  );
}
