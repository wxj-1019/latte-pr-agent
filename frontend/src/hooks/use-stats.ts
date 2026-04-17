"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import type { DashboardStats } from "@/types";

export function useStats() {
  const { data, error, isLoading } = useSWR<DashboardStats>("/stats", () => api.getStats());

  return {
    stats: data,
    isLoading,
    error,
  };
}
