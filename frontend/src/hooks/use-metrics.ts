"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import type { CombinedMetrics, MetricsDataPoint } from "@/types";

export function useMetrics(range: "7d" | "30d" | "90d", repoId?: string) {
  const key = repoId ? `stats/metrics/${repoId}/${range}` : null;

  const { data, error, isLoading } = useSWR<CombinedMetrics>(
    key,
    () => api.getCombinedMetrics(range, repoId || "default"),
    {
      revalidateOnFocus: false,
      dedupingInterval: 30_000,
    }
  );

  return {
    metrics: data?.metrics,
    commit: data?.commit,
    chart: (data?.chart ?? []) as MetricsDataPoint[],
    categoryDistribution: data?.category_distribution,
    severityDistribution: data?.severity_distribution,
    contributors: data?.contributors ?? [],
    codeChanges: data?.code_changes,
    isLoading,
    error,
  };
}
