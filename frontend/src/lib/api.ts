import { Review, ReviewFinding, PromptVersion, ReviewMetrics, MetricsDataPoint, DashboardStats, AnalyzeResult, ProjectRepo, CommitAnalysis, ProjectStats } from "@/types";
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

  getSystemSettings: async () => {
    return fetchJson<{ categories: Record<string, Array<{ key: string; has_value: boolean; value?: string | null; description: string }>> }>("/settings");
  },

  batchUpdateSystemSettings: async (settingsList: Array<{ key: string; value: string }>) => {
    return fetchJson<{ results: Array<{ key: string; status: string; message?: string }> }>("/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings: settingsList }),
    });
  },

  testWebhook: async (platform: "github" | "gitlab") => {
    return fetchJson<{
      platform: string;
      passed: boolean;
      checks: Array<{ name: string; status: string; message: string; webhook_url?: string; webhook_secret?: string }>;
      webhook_secret: string;
    }>("/settings/test-webhook", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform }),
    });
  },

  fetchPullRequests: async (repoId: string, platform: string = "github") => {
    return fetchJson<{ pulls: Array<{ number: number; title: string; author: string; head_branch: string; base_branch: string; updated_at: string | null; additions: number; deletions: number; changed_files: number }>; total: number }>("/reviews/fetch-prs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_id: repoId, platform }),
    });
  },

  triggerManualReview: async (repoId: string, prNumber: number, platform: string = "github") => {
    return fetchJson<{ message: string; review_id: number; status: string }>("/reviews/trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_id: repoId, pr_number: prNumber, platform }),
    });
  },

  listProjects: async () => {
    return fetchJson<{ projects: ProjectRepo[] }>("/projects");
  },

  addProject: async (body: { platform: string; repo_url: string; branch?: string }) => {
    return fetchJson<{ project: ProjectRepo; message: string }>("/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  getProject: async (id: number) => {
    return fetchJson<ProjectRepo>(`/projects/${id}`);
  },

  deleteProject: async (id: number) => {
    return fetchJson<{ message: string }>(`/projects/${id}`, { method: "DELETE" });
  },

  syncProject: async (id: number) => {
    return fetchJson<{ message: string; pulled: number }>(`/projects/${id}/sync`, { method: "POST" });
  },

  scanCommits: async (projectId: number, maxCommits: number = 50) => {
    return fetchJson<{ project_id: number; scanned: number; saved: number }>(
      `/projects/${projectId}/scan?max_commits=${maxCommits}`,
      { method: "POST" }
    );
  },

  listCommits: async (projectId: number, page: number = 1, pageSize: number = 20, riskLevel?: string) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (riskLevel) params.set("risk_level", riskLevel);
    return fetchJson<{ commits: CommitAnalysis[]; total: number; page: number; page_size: number }>(
      `/projects/${projectId}/commits?${params.toString()}`
    );
  },

  getCommitDetail: async (projectId: number, commitHash: string) => {
    return fetchJson<CommitAnalysis>(`/projects/${projectId}/commits/${commitHash}`);
  },

  getProjectStats: async (projectId: number) => {
    return fetchJson<ProjectStats>(`/projects/${projectId}/stats`);
  },

  getProjectFindings: async (projectId: number, severity?: string, page: number = 1) => {
    const params = new URLSearchParams({ page: String(page) });
    if (severity) params.set("severity", severity);
    return fetchJson<{ findings: Array<Record<string, unknown>>; total: number; page: number }>(
      `/projects/${projectId}/findings?${params.toString()}`
    );
  },
};
