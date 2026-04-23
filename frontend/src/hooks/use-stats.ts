"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import type { DashboardStats } from "@/types";

export function useStats() {
  const { data, error, isLoading, mutate } = useSWR<DashboardStats>(
    typeof window === "undefined" ? null : "/stats",
    () => api.getStats(),
    {
      onErrorRetry: (err) => {
        if (err.message?.includes("API")) return;
      },
    }
  );

  return {
    stats: data,
    isLoading,
    error,
    mutate,
  };
}
