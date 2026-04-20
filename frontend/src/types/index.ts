export interface Review {
  id: number;
  org_id: string;
  platform: "github" | "gitlab" | "direct";
  repo_id: string;
  pr_number: number;
  pr_title?: string;
  pr_author?: string;
  base_branch?: string;
  head_branch?: string;
  head_sha?: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  risk_level?: "low" | "medium" | "high" | "critical";
  trigger_type?: string;
  review_mode: string;
  prompt_version?: string;
  ai_model?: string;
  diff_stats?: Record<string, number>;
  pr_files?: PRFile[];
  created_at: string;
  completed_at?: string;
}

export interface ReviewFinding {
  id: number;
  review_id: number;
  file_path: string;
  line_number?: number;
  category?: string;
  severity: "info" | "warning" | "critical";
  description: string;
  suggestion?: string;
  confidence?: number;
  affected_files?: string[];
  ai_model?: string;
  raw_response?: Record<string, unknown>;
  created_at: string;
}

export interface PRFile {
  id: number;
  review_id: number;
  file_path: string;
  change_type?: "added" | "removed" | "modified" | "renamed";
  additions: number;
  deletions: number;
  diff_content?: string;
}

export interface DeveloperFeedback {
  id: number;
  finding_id: number;
  is_false_positive: boolean;
  comment?: string;
  created_at: string;
}

export interface ProjectConfig {
  id: number;
  org_id: string;
  platform: "github" | "gitlab";
  repo_id: string;
  config_json: {
    review_config?: {
      language?: string;
      context_analysis?: {
        enabled?: boolean;
        dependency_depth?: number;
        historical_bug_check?: boolean;
        api_contract_detection?: boolean;
      };
      critical_paths?: string[];
      custom_rules?: Array<{
        name: string;
        pattern: string;
        forbidden?: string;
        message: string;
        severity: "warning" | "critical";
      }>;
      ai_model?: {
        primary?: string;
        fallback?: string;
      };
      dual_model_verification?: {
        enabled?: boolean;
        trigger_on?: string[];
      };
      cross_service?: {
        enabled?: boolean;
        downstream_repos?: Array<{ repo_id: string; platform: string }>;
      };
    };
  };
  updated_at: string;
}

export interface PromptVersion {
  id: number;
  version: string;
  is_active: boolean;
  is_baseline: boolean;
  ab_ratio?: number;
  accuracy?: number;
  repo_count: number;
  content?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface ReviewMetrics {
  total_reviews: number;
  total_findings: number;
  false_positive_rate: number;
  avg_confidence: number;
}

export interface MetricsDataPoint {
  date: string;
  reviews: number;
  findings: number;
}

export interface ReviewUpdate {
  review_id: number;
  status: Review["status"];
  timestamp: string;
  findings_count?: number;
}

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
    status: "pending" | "running" | "completed" | "failed" | "skipped";
    risk_level?: string;
    created_at: string;
  }>;
}

export interface AnalyzeResult {
  review_id: number;
  status: string;
  summary: string;
  risk_level: "low" | "medium" | "high" | "critical";
  findings: ReviewFinding[];
}

export interface ProjectRepo {
  id: number;
  org_id: string;
  platform: "github" | "gitlab";
  repo_id: string;
  repo_url: string;
  branch: string;
  local_path?: string;
  status: "pending" | "cloning" | "ready" | "error";
  error_message?: string;
  last_analyzed_sha?: string;
  total_commits: number;
  total_findings: number;
  config_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CommitAnalysis {
  commit_hash: string;
  parent_hash?: string;
  author_name: string;
  author_email: string;
  message: string;
  commit_ts: string;
  additions: number;
  deletions: number;
  changed_files: number;
  diff_content?: string;
  summary?: string;
  risk_level?: "low" | "medium" | "high" | "critical";
  ai_model?: string;
  status: "pending" | "analyzing" | "completed" | "failed";
  findings: CommitFindingItem[];
}

export interface CommitFindingItem {
  id: number;
  file_path: string;
  line_number?: number;
  severity: "info" | "warning" | "critical";
  category: string;
  description: string;
  suggestion?: string;
  confidence?: number;
  evidence?: string;
  reasoning?: string;
}

export interface ProjectStats {
  total_commits: number;
  analyzed_commits: number;
  total_findings: number;
  severity_distribution: Record<string, number>;
  category_distribution: Record<string, number>;
}
