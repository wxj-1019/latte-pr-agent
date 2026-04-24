import type { Review, ReviewFinding, PRFile, ReviewMetrics, MetricsDataPoint, PromptVersion, ProjectConfig } from "@/types";

export const mockReviews: Review[] = [
  {
    id: 42,
    org_id: "default",
    platform: "github",
    repo_id: "org/latte-backend",
    pr_number: 128,
    pr_title: "feat: add user auth",
    pr_author: "alice",
    status: "pending",
    review_mode: "incremental",
    ai_model: "deepseek-chat",
    created_at: "2026-04-16T10:00:00Z",
  },
  {
    id: 41,
    org_id: "default",
    platform: "github",
    repo_id: "org/latte-backend",
    pr_number: 127,
    pr_title: "fix: memory leak in connection pool",
    pr_author: "bob",
    status: "completed",
    risk_level: "critical",
    review_mode: "incremental",
    ai_model: "claude-3-5-sonnet",
    created_at: "2026-04-16T08:30:00Z",
    completed_at: "2026-04-16T09:00:00Z",
  },
  {
    id: 40,
    org_id: "default",
    platform: "gitlab",
    repo_id: "org/latte-frontend",
    pr_number: 45,
    pr_title: "refactor: migrate to app router",
    pr_author: "charlie",
    status: "running",
    review_mode: "incremental",
    ai_model: "deepseek-reasoner",
    created_at: "2026-04-16T07:00:00Z",
  },
  {
    id: 39,
    org_id: "default",
    platform: "github",
    repo_id: "org/latte-backend",
    pr_number: 126,
    pr_title: "chore: update dependencies",
    pr_author: "dave",
    status: "skipped",
    review_mode: "incremental",
    created_at: "2026-04-15T16:00:00Z",
  },
  {
    id: 38,
    org_id: "default",
    platform: "github",
    repo_id: "org/latte-backend",
    pr_number: 125,
    pr_title: "feat: add sse endpoint for realtime updates",
    pr_author: "eve",
    status: "failed",
    review_mode: "incremental",
    ai_model: "qwen-max",
    created_at: "2026-04-15T14:00:00Z",
  },
];

export const mockFindings: ReviewFinding[] = [
  {
    id: 101,
    review_id: 41,
    file_path: "src/db/pool.ts",
    line_number: 47,
    category: "resource-leak",
    severity: "warning",
    description: "Connection timeout increased from 5s to 30s without retry logic. This may mask transient failures.",
    suggestion: "Add exponential backoff retry or circuit breaker pattern.",
    confidence: 0.92,
    ai_model: "claude-3-5-sonnet",
    created_at: "2026-04-16T09:00:00Z",
  },
  {
    id: 102,
    review_id: 41,
    file_path: "src/db/pool.ts",
    line_number: 52,
    category: "resource-leak",
    severity: "critical",
    description: "Connections are not released on unhandled exceptions, leading to pool exhaustion.",
    suggestion: "Wrap connection usage in try/finally blocks to ensure release.",
    confidence: 0.96,
    ai_model: "claude-3-5-sonnet",
    created_at: "2026-04-16T09:00:00Z",
  },
  {
    id: 103,
    review_id: 41,
    file_path: "src/auth/oauth.ts",
    line_number: 12,
    category: "security",
    severity: "info",
    description: "Consider adding state parameter validation for CSRF protection.",
    suggestion: "Validate the state parameter against the session store.",
    confidence: 0.85,
    ai_model: "claude-3-5-sonnet",
    created_at: "2026-04-16T09:00:00Z",
  },
];

export const mockFiles: PRFile[] = [
  {
    id: 201,
    review_id: 41,
    file_path: "src/db/pool.ts",
    change_type: "modified",
    additions: 8,
    deletions: 3,
    diff_content: `@@ -45,7 +45,7 @@
- const timeout = 5000;
+ const timeout = 30000;
 
 export function createPool() {
   const pool = new Pool({
@@ -52,6 +52,11 @@
     max: 20,
   });
 
+  pool.on('error', (err) => {
+    console.error(err);
+  });
+
   return pool;
 }`,
  },
  {
    id: 202,
    review_id: 41,
    file_path: "src/auth/oauth.ts",
    change_type: "added",
    additions: 45,
    deletions: 0,
    diff_content: `@@ -0,0 +1,45 @@
+import { OAuth2Client } from 'google-auth-library';
+
+export const oauthClient = new OAuth2Client({
+  clientId: process.env.GOOGLE_CLIENT_ID,
+  clientSecret: process.env.GOOGLE_CLIENT_SECRET,
+  redirectUri: '/auth/callback',
+});`,
  },
  {
    id: 203,
    review_id: 41,
    file_path: "src/utils/logger.ts",
    change_type: "modified",
    additions: 2,
    deletions: 2,
    diff_content: `@@ -1,4 +1,4 @@
- import { createLogger } from 'pino';
+ import { createLogger } from 'winston';
 
 export const logger = createLogger({ level: 'info' });`,
  },
];

export const mockMetrics: ReviewMetrics = {
  total_reviews: 1284,
  total_findings: 3402,
  false_positive_rate: 0.058,
  avg_confidence: 0.91,
};

export const mockMetricsChart: MetricsDataPoint[] = [
  { date: "04-10", reviews: 12, pr_findings: 28, analyses: 8, commit_findings: 15 },
  { date: "04-11", reviews: 18, pr_findings: 42, analyses: 12, commit_findings: 22 },
  { date: "04-12", reviews: 15, pr_findings: 35, analyses: 10, commit_findings: 18 },
  { date: "04-13", reviews: 22, pr_findings: 51, analyses: 15, commit_findings: 28 },
  { date: "04-14", reviews: 19, pr_findings: 38, analyses: 11, commit_findings: 20 },
  { date: "04-15", reviews: 24, pr_findings: 56, analyses: 16, commit_findings: 32 },
  { date: "04-16", reviews: 20, pr_findings: 48, analyses: 14, commit_findings: 26 },
];

export const mockPromptVersions: PromptVersion[] = [
  {
    id: 1,
    version: "v1.2.0-system",
    is_active: true,
    is_baseline: false,
    ab_ratio: 0.5,
    accuracy: 0.942,
    repo_count: 3,
    created_at: "2026-04-10T00:00:00Z",
  },
  {
    id: 2,
    version: "v1.1.9-system",
    is_active: false,
    is_baseline: true,
    ab_ratio: 0.5,
    accuracy: 0.918,
    repo_count: 5,
    created_at: "2026-03-20T00:00:00Z",
  },
];

export const mockProjectConfig: ProjectConfig = {
  id: 1,
  org_id: "default",
  platform: "github",
  repo_id: "org/latte-backend",
  config_json: {
    review_config: {
      language: "python",
      context_analysis: {
        enabled: true,
        dependency_depth: 2,
        historical_bug_check: true,
        api_contract_detection: true,
      },
      critical_paths: ["src/payment/", "src/auth/"],
      custom_rules: [
        {
          name: "禁止控制器直接调用 DB",
          pattern: "*/controllers/*",
          forbidden: "*/db/*",
          message: "控制器层不应直接访问数据库",
          severity: "warning",
        },
      ],
      ai_model: {
        primary: "deepseek-chat",
        fallback: "deepseek-reasoner",
      },
      dual_model_verification: {
        enabled: true,
        trigger_on: ["critical", "warning"],
      },
      cross_service: {
        enabled: true,
        downstream_repos: [{ repo_id: "org/service-b", platform: "github" }],
      },
    },
  },
  updated_at: "2026-04-16T00:00:00Z",
};
