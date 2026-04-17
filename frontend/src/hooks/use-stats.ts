"use client";

import useSWR from "swr";
import { api } from "@/lib/api";

export interface DashboardStats {
  total_reviews: number;
  pending_reviews: number;
  running_reviews: number;
  completed_reviews: number;
  failed_reviews: number;
  skipped_reviews: number;
  high_risk_count: number;
  total_findings_today: number;
  recent_reviews: Array<{
    id: number;
    repo_id: string;
    pr_number: number;
    pr_title?: string;
    status: string;
    risk_level?: string;
    created_at: string;
  }>;
}

export function useStats() {
  const { data, error, isLoading } = useSWR<DashboardStats>("/stats", () => api.getStats());

  return {
    stats: data,
    isLoading,
    error,
  };
}
