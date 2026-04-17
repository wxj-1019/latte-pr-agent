"use client";

import { useState, useCallback } from "react";
import { api, type AnalyzeResult } from "@/lib/api";

interface UseAnalyzeReturn {
  analyze: (params: { filename: string; content: string; language: string; repo_id: string }) => Promise<AnalyzeResult>;
  isLoading: boolean;
  error: Error | null;
  data: AnalyzeResult | null;
}

export function useAnalyze(): UseAnalyzeReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<AnalyzeResult | null>(null);

  const analyze = useCallback(async (params: { filename: string; content: string; language: string; repo_id: string }) => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await api.analyzeCode(params);
      setData(result);
      return result;
    } catch (err) {
      const e = err instanceof Error ? err : new Error("Analyze failed");
      setError(e);
      throw e;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { analyze, isLoading, error, data };
}
