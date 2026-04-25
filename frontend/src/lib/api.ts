import { Review, ReviewFinding, PromptVersion, ReviewMetrics, CombinedMetrics, MetricsDataPoint, DashboardStats, AnalyzeResult, ProjectRepo, CommitAnalysis, ProjectStats, ContributorInfo, ContributorDetail } from "@/types";
import { csrfHeaders } from "./csrf";
import { notifyError } from "@/components/ui/notification";

const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";

function getAdminApiKey(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("latte_admin_api_key") || "";
  }
  return "";
}

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
    let message = `API 错误: ${res.status} ${res.statusText}`;
    try {
      const errBody = await res.json();
      if (errBody.detail) message = errBody.detail;
      else if (errBody.message) message = errBody.message;
    } catch {
      // response is not JSON, keep default message
    }
    /* also push to notification panel */
    if (typeof window !== "undefined") {
      notifyError("请求失败", message, { category: "system" });
    }
    throw new Error(message);
  }
  const contentType = res.headers.get("content-type");
  if (!contentType || !contentType.includes("application/json")) {
    const msg = `API 返回了非 JSON 响应 (${contentType || "unknown"})`;
    if (typeof window !== "undefined") {
      notifyError("请求失败", msg, { category: "system" });
    }
    throw new Error(msg);
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

  getCombinedMetrics: async (range: "7d" | "30d" | "90d", repoId: string) => {
    return fetchJson<CombinedMetrics>(
      `/stats/metrics?repo_id=${encodeURIComponent(repoId)}&range=${range}`
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

  deletePromptVersion: async (version: string) => {
    return fetchJson<{ message: string; version: string }>(`/prompts/versions/${encodeURIComponent(version)}`, {
      method: "DELETE",
    });
  },

  generateProjectPrompt: async (projectId: number) => {
    return fetchJson<{ message: string; version: string }>(`/prompts/generate-for-project/${projectId}`, {
      method: "POST",
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
      body: JSON.stringify({ config_json: body }),
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
    return fetchJson<{ categories: Record<string, Array<{ key: string; has_value: boolean; value?: string | null; description: string }>> }>("/settings", {
      headers: { "X-API-Key": getAdminApiKey() },
    });
  },

  batchUpdateSystemSettings: async (settingsList: Array<{ key: string; value: string }>) => {
    return fetchJson<{ results: Array<{ key: string; status: string; message?: string }> }>("/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json", "X-API-Key": getAdminApiKey() },
      body: JSON.stringify({ settings: settingsList }),
    });
  },

  revealSettings: async (keys: string[]) => {
    return fetchJson<{ values: Record<string, string> }>("/settings/reveal", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": getAdminApiKey() },
      body: JSON.stringify({ keys }),
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
      headers: { "Content-Type": "application/json", "X-API-Key": getAdminApiKey() },
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

  addProject: async (body: { platform: string; repo_url: string; repo_id: string; branch?: string }) => {
    return fetchJson<ProjectRepo>("/projects", {
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
    return fetchJson<{ id: number; status: string; new_commits: number }>(`/projects/${id}/sync`, { method: "POST" });
  },

  scanCommits: async (projectId: number, maxCommits: number = 50) => {
    return fetchJson<{ project_id: number; status?: string; operation?: string; scanned?: number; saved?: number }>(
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

  getContributors: async (projectId: number) => {
    return fetchJson<{ contributors: ContributorInfo[]; total: number }>(
      `/projects/${projectId}/contributors`
    );
  },

  getContributorDetail: async (projectId: number, authorEmail: string) => {
    return fetchJson<ContributorDetail>(
      `/projects/${projectId}/contributors/${encodeURIComponent(authorEmail)}`
    );
  },

  getKnowledgeGraph: async (projectId: number) => {
    return fetchJson<{ file_graph: { nodes: Array<{ id: string; group: string }>; edges: Array<{ source: string; target: string; type: string }> }; module_graph: { nodes: Array<{ id: string; group: string }>; edges: Array<{ source: string; target: string; count: number }> } }>(
      `/projects/${projectId}/knowledge-graph`
    );
  },

  getEntityGraph: async (projectId: number) => {
    return fetchJson<{
      nodes: Array<{
        id: string;
        name: string;
        type: string;
        file: string;
        group: string;
        start_line: number;
        end_line: number;
      }>;
      edges: Array<{
        source: string;
        target: string | null;
        type: string;
        source_file: string;
        target_file: string | null;
      }>;
    }>(`/projects/${projectId}/entity-graph`);
  },

  buildEntityGraph: async (projectId: number) => {
    return fetchJson<{ entities: number; relationships: number; skipped?: boolean }>(
      `/projects/${projectId}/entity-graph/build`,
      { method: "POST" }
    );
  },

  getEntityNeighbors: async (projectId: number, entityId: number) => {
    return fetchJson<{
      entity: {
        id: number;
        name: string;
        type: string;
        file: string;
        signature: string;
        start_line: number;
        end_line: number;
        meta: Record<string, unknown>;
      } | null;
      incoming: Array<{
        relation_id: number;
        relation_type: string;
        source_entity: { id: number; name: string; type: string; file: string };
        meta: Record<string, unknown>;
      }>;
      outgoing: Array<{
        relation_id: number;
        relation_type: string;
        target_entity: { id: number; name: string; type: string; file: string };
        meta: Record<string, unknown>;
      }>;
    }>(`/projects/${projectId}/entity-graph/entities/${entityId}/neighbors`);
  },

  codeSearch: async (projectId: number, query: string, entityType?: string, topK: number = 10) => {
    const params = new URLSearchParams({ q: query, top_k: String(topK) });
    if (entityType) params.set("entity_type", entityType);
    return fetchJson<{
      query: string;
      results: Array<{
        id: number;
        name: string;
        entity_type: string;
        file_path: string;
        start_line: number;
        signature: string;
        meta_json: Record<string, unknown>;
        similarity: number;
        neighbors: Array<{ id: number; name: string; entity_type: string; file_path: string; relation_type: string }>;
      }>;
    }>(`/projects/${projectId}/code-search?${params.toString()}`);
  },

  getCodeComplexity: async (projectId: number) => {
    return fetchJson<{
      total_entities: number;
      total_functions: number;
      total_classes: number;
      god_class_count: number;
      god_classes: Array<{ name: string; incoming: number }>;
      cycle_dependencies: number;
      isolated_functions: number;
      isolated_ratio: number;
    }>(`/projects/${projectId}/code-complexity`);
  },

  graphRagRetrieve: async (projectId: number, body: { query: string; changed_files?: string[]; depth?: number; top_k?: number }) => {
    return fetchJson<{
      query: string;
      results: Array<{
        id: number;
        name: string;
        entity_type: string;
        file_path: string;
        signature: string;
        start_line: number;
        meta_json: Record<string, unknown>;
        depth: number;
      }>;
    }>(`/projects/${projectId}/graph-rag/retrieve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  getArchitectureDiagram: async (projectId: number) => {
    return fetchJson<{ mermaid: string }>(
      `/projects/${projectId}/architecture`
    );
  },

  analyzeCommit: async (projectId: number, commitHash: string) => {
    return fetchJson<{ commit_hash: string; status: string; message?: string }>(
      `/projects/${projectId}/commits/${commitHash}/analyze`,
      { method: "POST" }
    );
  },

  analyzeProject: async (projectId: number, maxCommits?: number) => {
    const params = new URLSearchParams();
    if (maxCommits !== undefined && maxCommits > 0) params.set("max_commits", String(maxCommits));
    const query = params.toString();
    return fetchJson<{ project_id: number; status: string; operation: string }>(
      `/projects/${projectId}/analyze${query ? `?${query}` : ""}`,
      { method: "POST" }
    );
  },
};
