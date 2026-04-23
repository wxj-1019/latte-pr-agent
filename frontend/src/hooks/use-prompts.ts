"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import type { PromptVersion } from "@/types";

export function usePrompts() {
  const { data, error, isLoading, mutate } = useSWR<PromptVersion[]>(
    typeof window === "undefined" ? null : "/api/prompts",
    () => api.getPromptVersions()
  );

  return {
    prompts: data ?? [],
    isLoading,
    error,
    mutate,
  };
}
