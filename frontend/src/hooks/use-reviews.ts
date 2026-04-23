"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import type { Review, ReviewFinding } from "@/types";

interface UseReviewsOptions {
  status?: string;
  repo?: string;
  risk?: string;
  page?: number;
}

export function useReviews(options?: UseReviewsOptions) {
  const key = typeof window === "undefined" ? null : ["/api/reviews", options?.status, options?.repo, options?.risk, options?.page];
  const { data, error, isLoading, mutate } = useSWR<{ data: Review[]; total: number; page: number; page_size: number }>(
    key,
    () => api.getReviews(options),
    { refreshInterval: 30000 }
  );

  return {
    reviews: data?.data ?? [],
    total: data?.total ?? 0,
    page: data?.page ?? 1,
    pageSize: data?.page_size ?? 20,
    isLoading,
    error,
    mutate,
  };
}

export function useReviewDetail(id: number) {
  const { data, error, isLoading, mutate } = useSWR<Review>(
    typeof window === "undefined" || !id ? null : `/api/reviews/${id}`,
    () => api.getReviewDetail(id)
  );

  return {
    review: data,
    isLoading,
    error,
    mutate,
  };
}

export function useReviewFindings(reviewId: number) {
  const { data, error, isLoading, mutate } = useSWR<ReviewFinding[]>(
    typeof window === "undefined" || !reviewId ? null : `/api/reviews/${reviewId}/findings`,
    () => api.getReviewFindings(reviewId)
  );

  return {
    findings: data ?? [],
    isLoading,
    error,
    mutate,
  };
}
