import { Review, ReviewFinding, PromptVersion, ReviewMetrics, MetricsDataPoint, DashboardStats, AnalyzeResult } from "@/types";
import { csrfHeaders } from "./csrf";

const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const isMutating = !!options?.method && options.method !== "GET" && options.method !== "HEAD";
  const res = await fetch(`${baseUrl}${url}`, {
    ...options,
    headers: {
      ...(options?.headers || {}),
      ...(isMutating ? csrfHeaders() : {}),
    },
  });
  if (!res.ok) {
    throw new Error(`API 错误: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getReviews: async (options?: { status?: string; repo?: string; risk?: string; page?: number }) => {
    const params = new URLSearchParams();
    if (options?.status) params.set("status", options.status);
    if (options?.repo) params.set("repo", options.repo);
    if (options?.risk) params.set("risk", options.risk);
    if (options?.page) params.set("page", String(options.page));
    return fetchJson<{ data: Review[]; total: number; page: number; page_size: number }>(
      `/reviews?${params.toString()}`
    );
  },

  getReviewDetail: async (id: number) => {
    return fetchJson<Review>(`/reviews/${id}`);
  },

  getReviewFindings: async (reviewId: number) => {
    return fetchJson<ReviewFinding[]>(`/reviews/${reviewId}/findings`);
  },

  getMetrics: async (range: "7d" | "30d" | "90d", repoId: string) => {
    return fetchJson<{ metrics: ReviewMetrics; chart: MetricsDataPoint[] }>(
      `/feedback/metrics/${repoId}?range=${range}`
    );
  },

  getPromptVersions: async () => {
    return fetchJson<PromptVersion[]>("/prompts/versions");
  },

  savePromptVersion: async (body: { version: string; text: string; metadata?: object }) => {
    return fetchJson<PromptVersion>("/prompts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  optimizePrompt: async (body: { base_version?: string; new_version?: string; min_samples?: number }) => {
    return fetchJson<{ optimized: boolean; new_version?: string; stats?: object }>("/prompts/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  getStats: async () => {
    return fetchJson<DashboardStats>("/stats");
  },

  getProjectConfig: async (repoId: string) => {
    return fetchJson<object>(`/configs/${repoId}`);
  },

  updateProjectConfig: async (repoId: string, body: object) => {
    return fetchJson<object>(`/configs/${repoId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  submitFeedback: async (findingId: number, isFalsePositive: boolean, comment?: string) => {
    const params = new URLSearchParams();
    params.set("is_false_positive", String(isFalsePositive));
    if (comment) params.set("comment", comment);
    return fetchJson<object>(`/feedback/${findingId}?${params.toString()}`, {
      method: "POST",
    });
  },

  analyzeCode: async (body: { filename: string; content: string; language: string; repo_id: string }) => {
    return fetchJson<AnalyzeResult>("/reviews/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  getRepos: async () => {
    return fetchJson<{ repos: string[] }>("/repos");
  },

  verifyProjectConfig: async (repoId: string, platform: string = "github") => {
    return fetchJson<{
      passed: boolean;
      has_warning: boolean;
      checks: { name: string; status: string; message: string }[];
      summary: string;
    }>("/configs/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_id: repoId, platform }),
    });
  },
};
