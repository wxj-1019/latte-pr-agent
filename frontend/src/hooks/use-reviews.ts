"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import type { Review, ReviewFinding } from "@/types";

interface UseReviewsOptions {
  status?: string;
  repo?: string;
  page?: number;
}

export function useReviews(options?: UseReviewsOptions) {
  const key = ["/api/reviews", options?.status, options?.repo, options?.page];
  const { data, error, isLoading, mutate } = useSWR<Review[]>(
    key,
    () => api.getReviews(options),
    { refreshInterval: 30000 }
  );

  return {
    reviews: data ?? [],
    isLoading,
    error,
    mutate,
  };
}

export function useReviewDetail(id: number) {
  const { data, error, isLoading } = useSWR<Review>(
    id ? `/api/reviews/${id}` : null,
    () => api.getReviewDetail(id)
  );

  return {
    review: data,
    isLoading,
    error,
  };
}

export function useReviewFindings(reviewId: number) {
  const { data, error, isLoading, mutate } = useSWR<ReviewFinding[]>(
    reviewId ? `/api/reviews/${reviewId}/findings` : null,
    () => api.getReviewFindings(reviewId)
  );

  return {
    findings: data ?? [],
    isLoading,
    error,
    mutate,
  };
}
