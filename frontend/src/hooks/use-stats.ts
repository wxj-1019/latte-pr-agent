"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import type { DashboardStats } from "@/types";

export function useStats() {
  const { data, error, isLoading, mutate } = useSWR<DashboardStats>(
    typeof window === "undefined" ? null : "/stats",
    () => api.getStats(),
    {
      onErrorRetry: (err, _key, _config, revalidate, { retryCount }) => {
        if (retryCount >= 3) return;
        if (err.message?.includes("API")) return;
        setTimeout(() => revalidate({ retryCount }), 3000);
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
