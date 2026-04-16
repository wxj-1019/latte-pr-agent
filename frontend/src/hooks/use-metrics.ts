"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import type { ReviewMetrics, MetricsDataPoint } from "@/types";

export function useMetrics(range: "7d" | "30d" | "90d") {
  const { data, error, isLoading } = useSWR<{ metrics: ReviewMetrics; chart: MetricsDataPoint[] }>(
    `/api/metrics?range=${range}`,
    () => api.getMetrics(range)
  );

  return {
    metrics: data?.metrics,
    chart: data?.chart ?? [],
    isLoading,
    error,
  };
}
