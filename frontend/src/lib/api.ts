import { Review, ReviewFinding, PromptVersion, ReviewMetrics, MetricsDataPoint } from "@/types";

const baseUrl = typeof window !== "undefined" ? "" : process.env.NEXT_PUBLIC_API_URL || "";

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${baseUrl}${url}`, options);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getReviews: async (options?: { status?: string; repo?: string; page?: number }) => {
    const params = new URLSearchParams();
    if (options?.status) params.set("status", options.status);
    if (options?.repo) params.set("repo", options.repo);
    if (options?.page) params.set("page", String(options.page));
    return fetchJson<Review[]>(`/api/reviews?${params.toString()}`);
  },

  getReviewDetail: async (id: number) => {
    return fetchJson<Review>(`/api/reviews/${id}`);
  },

  getReviewFindings: async (reviewId: number) => {
    return fetchJson<ReviewFinding[]>(`/api/reviews/${reviewId}/findings`);
  },

  getMetrics: async (range: "7d" | "30d" | "90d") => {
    return fetchJson<{ metrics: ReviewMetrics; chart: MetricsDataPoint[]; range: string }>(
      `/api/metrics?range=${range}`
    );
  },

  getPromptVersions: async () => {
    return fetchJson<PromptVersion[]>("/api/prompts");
  },

  savePromptVersion: async (body: { version: string; text: string; metadata?: object }) => {
    return fetchJson<PromptVersion>("/api/prompts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  optimizePrompt: async (body: { base_version?: string; new_version?: string; min_samples?: number }) => {
    return fetchJson<{ optimized: boolean; new_version?: string; stats?: object }>("/api/prompts/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  getProjectConfig: async (repoId: string) => {
    return fetchJson<object>(`/api/config/${repoId}`);
  },

  updateProjectConfig: async (repoId: string, body: object) => {
    return fetchJson<object>(`/api/config/${repoId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  submitFeedback: async (findingId: number, isFalsePositive: boolean, comment?: string) => {
    const params = new URLSearchParams();
    params.set("is_false_positive", String(isFalsePositive));
    if (comment) params.set("comment", comment);
    return fetchJson<object>(`/api/findings/${findingId}/feedback?${params.toString()}`, {
      method: "POST",
    });
  },
};
