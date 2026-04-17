"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import type { ReviewMetrics, MetricsDataPoint } from "@/types";

export function useMetrics(range: "7d" | "30d" | "90d", repoId?: string) {
  const { data, error, isLoading } = useSWR<{
    metrics: ReviewMetrics;
    chart: MetricsDataPoint[];
    category_distribution?: Record<string, number>;
  }>(
    repoId ? [`/feedback/metrics/${repoId}`, range] : null,
    () => api.getMetrics(range, repoId || "default")
  );

  return {
    metrics: data?.metrics,
    chart: data?.chart ?? [],
    categoryDistribution: data?.category_distribution,
    isLoading,
    error,
  };
}
