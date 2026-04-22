"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import type { ProjectRepo, CommitAnalysis, ProjectStats, ContributorInfo, ContributorDetail, AnalysisProgress } from "@/types";
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  GitCommitHorizontal,
  Search as SearchIcon,
  BarChart3,
  AlertTriangle,
  FileCode,
  User,
  Clock,
  ChevronLeft,
  ChevronRight,
  Users,
  ChevronDown,
  ChevronUp,
  TrendingUp,
  Shield,
  RefreshCw,
} from "lucide-react";
import { AnalysisProgressPanel } from "@/components/dashboard/analysis-progress";

const riskColors: Record<string, string> = {
  critical: "bg-latte-critical/10 text-latte-critical border-latte-critical/20",
  high: "bg-latte-warning/10 text-latte-warning border-latte-warning/20",
  medium: "bg-latte-gold/10 text-latte-gold border-latte-gold/20",
  low: "bg-latte-success/10 text-latte-success border-latte-success/20",
};

const sevColors: Record<string, string> = {
  critical: "text-latte-critical",
  warning: "text-latte-warning",
  info: "text-latte-info",
};

const gradeColors: Record<string, string> = {
  A: "bg-latte-success",
  B: "bg-latte-info",
  C: "bg-latte-gold",
  D: "bg-latte-warning",
  F: "bg-latte-critical",
};

export default function ProjectDetailPage() {
  const { showToast } = useToast();
  const params = useParams();
  const router = useRouter();
  const projectId = Number(params.id);

  const [project, setProject] = useState<ProjectRepo | null>(null);
  const [stats, setStats] = useState<ProjectStats | null>(null);
  const [commits, setCommits] = useState<CommitAnalysis[]>([]);
  const [contributors, setContributors] = useState<ContributorInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [scanLoading, setScanLoading] = useState(false);
  const [syncLoading, setSyncLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"commits" | "contributors" | "stats">("contributors");
  const [error, setError] = useState("");
  const [expandedContributor, setExpandedContributor] = useState<string | null>(null);
  const [contributorCommits, setContributorCommits] = useState<Record<string, ContributorDetail>>({});
  const [analysisProgress, setAnalysisProgress] = useState<AnalysisProgress | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [proj, stat, commitRes, contribRes] = await Promise.all([
        api.getProject(projectId),
        api.getProjectStats(projectId).catch(() => null),
        api.listCommits(projectId, page, 20),
        api.getContributors(projectId).catch(() => ({ contributors: [], total: 0 })),
      ]);
      setProject(proj);
      setStats(stat);
      setCommits(commitRes.commits || []);
      setTotal(commitRes.total || 0);
      setContributors(contribRes.contributors || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [projectId, page]);

  useEffect(() => {
    load();
  }, [load]);

  const closeSSE = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
  }, []);

  const connectSSE = useCallback(() => {
    closeSSE();
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
    const url = `${baseUrl}/projects/${projectId}/stream`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as AnalysisProgress;
        setAnalysisProgress(data);
        if (data.status === "completed") {
          showToast(`${data.message}：扫描 ${data.result?.scanned ?? 0} 条，新增 ${data.result?.saved ?? data.result?.new_commits ?? 0} 条`);
          closeSSE();
          load();
          setScanLoading(false);
          setSyncLoading(false);
        } else if (data.status === "failed") {
          showToast(`分析失败：${data.error || data.message}`, "error");
          closeSSE();
          setScanLoading(false);
          setSyncLoading(false);
        }
      } catch {
        // ignore malformed events
      }
    };

    es.onerror = () => {
      es.close();
      esRef.current = null;
    };
  }, [projectId, closeSSE, load, showToast]);

  useEffect(() => {
    return () => {
      closeSSE();
    };
  }, [closeSSE]);

  const handleScan = async () => {
    try {
      setScanLoading(true);
      setError("");
      setAnalysisProgress(null);
      const res = await api.scanCommits(projectId, 200);
      if (res.status === "started") {
        connectSSE();
      } else {
        // fallback for old sync behavior
        showToast(`扫描完成：${res.scanned} 个提交，新增 ${res.saved} 条`);
        await load();
        setScanLoading(false);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "扫描失败");
      setScanLoading(false);
    }
  };

  const handleSync = async () => {
    try {
      setSyncLoading(true);
      setError("");
      setAnalysisProgress(null);
      const res = await api.syncProject(projectId);
      if (res.status === "syncing") {
        connectSSE();
      } else {
        showToast(`同步完成：${res.status}，新增 ${res.new_commits} 个提交`);
        await load();
        setSyncLoading(false);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "同步失败");
      setSyncLoading(false);
    }
  };

  const toggleContributor = async (email: string) => {
    if (expandedContributor === email) {
      setExpandedContributor(null);
      return;
    }
    setExpandedContributor(email);
    if (!contributorCommits[email]) {
      try {
        const detail = await api.getContributorDetail(projectId, email);
        setContributorCommits((prev) => ({ ...prev, [email]: detail }));
      } catch (err) {
        console.error("Failed to load contributor detail:", err);
        setContributorCommits((prev) => ({ ...prev, [email]: { commits: [], total: 0 } }));
      }
    }
  };

  if (loading && !project) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-latte-gold" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="text-center py-16 text-latte-text-secondary">
        <AlertCircle size={48} className="mx-auto mb-4 opacity-40" />
        <p>项目不存在</p>
      </div>
    );
  }

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.push("/dashboard/projects")}
          className="p-2 hover:bg-latte-bg-tertiary rounded-lg transition-colors"
        >
          <ArrowLeft size={20} />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-semibold text-latte-text-primary">{project.repo_id}</h1>
          <p className="text-sm text-latte-text-secondary mt-1">
            {project.platform} · {project.branch} · {project.total_commits} 提交 · {project.total_findings} 发现
          </p>
        </div>
        <button
          onClick={handleSync}
          disabled={syncLoading}
          className="flex items-center gap-2 px-4 py-2 bg-latte-info text-latte-bg-primary rounded-lg hover:bg-latte-info/90 disabled:opacity-50 transition-colors text-sm"
        >
          {syncLoading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          同步仓库
        </button>
        <button
          onClick={handleScan}
          disabled={project.status !== "ready" || scanLoading}
          className="flex items-center gap-2 px-4 py-2 bg-latte-gold text-latte-bg-primary rounded-lg hover:bg-latte-gold/90 disabled:opacity-50 transition-colors text-sm"
        >
          {scanLoading ? <Loader2 size={16} className="animate-spin" /> : <SearchIcon size={16} />}
          扫描提交
        </button>
      </div>

      <AnalysisProgressPanel progress={analysisProgress} />

      {error && (
        <div className="flex items-center gap-2 p-3 bg-latte-critical/5 border border-latte-critical/20 rounded-lg text-latte-critical text-sm">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <div className="flex gap-2 border-b border-latte-border pb-0">
        {(["contributors", "commits", "stats"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? "border-latte-gold text-latte-gold"
                : "border-transparent text-latte-text-secondary hover:text-latte-text-primary"
            }`}
          >
            {tab === "contributors" ? "贡献者分析" : tab === "commits" ? "提交记录" : "统计概览"}
          </button>
        ))}
      </div>

      {activeTab === "contributors" && (
        <div className="space-y-4">
          {contributors.length === 0 ? (
            <div className="text-center py-12 text-latte-text-secondary">
              <Users size={36} className="mx-auto mb-3 opacity-40" />
              <p>暂无贡献者数据</p>
              <p className="text-sm mt-1">请先扫描提交记录</p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-4 bg-latte-bg-secondary border border-latte-border rounded-xl text-center">
                  <p className="text-2xl font-bold text-latte-text-primary">{contributors.length}</p>
                  <p className="text-xs text-latte-text-secondary mt-1">贡献者</p>
                </div>
                <div className="p-4 bg-latte-bg-secondary border border-latte-border rounded-xl text-center">
                  <p className="text-2xl font-bold text-latte-success">
                    {contributors.filter((c) => c.grade === "A" || c.grade === "B").length}
                  </p>
                  <p className="text-xs text-latte-text-secondary mt-1">高质量开发者</p>
                </div>
                <div className="p-4 bg-latte-bg-secondary border border-latte-border rounded-xl text-center">
                  <p className="text-2xl font-bold text-latte-text-primary">
                    {contributors.length > 0
                      ? Math.round(contributors.reduce((s, c) => s + c.quality_score, 0) / contributors.length)
                      : 0}
                  </p>
                  <p className="text-xs text-latte-text-secondary mt-1">平均质量分</p>
                </div>
                <div className="p-4 bg-latte-bg-secondary border border-latte-border rounded-xl text-center">
                  <p className="text-2xl font-bold text-latte-critical">
                    {contributors.reduce((s, c) => s + c.findings.critical, 0)}
                  </p>
                  <p className="text-xs text-latte-text-secondary mt-1">严重发现</p>
                </div>
              </div>

              {contributors.map((contributor) => {
                const isExpanded = expandedContributor === contributor.author_email;
                const detailCommits = contributorCommits[contributor.author_email]?.commits || [];

                return (
                  <div key={contributor.author_email} className="bg-latte-bg-secondary border border-latte-border rounded-xl overflow-hidden">
                    <button
                      onClick={() => toggleContributor(contributor.author_email)}
                      className="w-full flex items-center gap-4 p-5 hover:bg-latte-bg-tertiary/20 transition-colors text-left"
                    >
                      <div className="flex items-center justify-center w-12 h-12 rounded-full bg-latte-bg-tertiary shrink-0">
                        <span className="text-lg font-bold text-latte-gold">
                          {contributor.author_name.charAt(0).toUpperCase()}
                        </span>
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold text-latte-text-primary">{contributor.author_name}</p>
                          <span className="text-xs text-latte-text-secondary">{contributor.author_email}</span>
                        </div>
                        <div className="flex items-center gap-4 mt-1 text-xs text-latte-text-secondary">
                          <span>{contributor.commit_count} 提交</span>
                          <span className="text-latte-success">+{contributor.total_additions}</span>
                          <span className="text-latte-critical">-{contributor.total_deletions}</span>
                          <span>{contributor.total_files_changed} 文件</span>
                          {contributor.findings.total > 0 && (
                            <span className="text-latte-text-secondary">
                              {contributor.findings.total} 发现 (密度 {contributor.finding_density})
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-4 shrink-0">
                        <div className="text-center">
                          <div className={`inline-flex items-center justify-center w-10 h-10 rounded-full text-latte-bg-primary font-bold text-sm ${gradeColors[contributor.grade] || "bg-latte-text-muted"}`}>
                            {contributor.grade}
                          </div>
                          <p className="text-xs text-latte-text-secondary mt-1">{contributor.quality_score}分</p>
                        </div>

                        <div className="flex gap-1.5">
                          {contributor.findings.critical > 0 && (
                            <span className="px-2 py-0.5 rounded-full text-xs bg-latte-critical/10 text-latte-critical">
                              {contributor.findings.critical} 严重
                            </span>
                          )}
                          {contributor.findings.warning > 0 && (
                            <span className="px-2 py-0.5 rounded-full text-xs bg-latte-warning/10 text-latte-warning">
                              {contributor.findings.warning} 警告
                            </span>
                          )}
                          {contributor.findings.info > 0 && (
                            <span className="px-2 py-0.5 rounded-full text-xs bg-latte-info/10 text-latte-info">
                              {contributor.findings.info} 信息
                            </span>
                          )}
                          {contributor.findings.total === 0 && (
                            <span className="px-2 py-0.5 rounded-full text-xs bg-latte-success/10 text-latte-success">
                              无问题
                            </span>
                          )}
                        </div>

                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="border-t border-latte-border bg-latte-bg-primary/30">
                        <div className="p-5 space-y-3">
                          <div className="grid grid-cols-3 gap-3 mb-4">
                            <div className="p-3 bg-latte-bg-secondary rounded-lg border border-latte-border">
                              <div className="flex items-center gap-1.5 text-xs text-latte-text-secondary mb-1">
                                <Shield size={12} />
                                代码质量
                              </div>
                              <div className="flex items-center gap-2">
                                <div className="flex-1 h-2 bg-latte-bg-tertiary rounded-full overflow-hidden">
                                  <div
                                    className={`h-full rounded-full ${contributor.quality_score >= 75 ? "bg-latte-success" : contributor.quality_score >= 50 ? "bg-latte-gold" : "bg-latte-critical"}`}
                                    style={{ width: `${contributor.quality_score}%` }}
                                  />
                                </div>
                                <span className="text-sm font-medium">{contributor.quality_score}</span>
                              </div>
                            </div>
                            <div className="p-3 bg-latte-bg-secondary rounded-lg border border-latte-border">
                              <div className="flex items-center gap-1.5 text-xs text-latte-text-secondary mb-1">
                                <TrendingUp size={12} />
                                发现密度
                              </div>
                              <p className="text-lg font-semibold">
                                {contributor.finding_density}
                                <span className="text-xs font-normal text-latte-text-secondary ml-1">/ 提交</span>
                              </p>
                            </div>
                            <div className="p-3 bg-latte-bg-secondary rounded-lg border border-latte-border">
                              <div className="flex items-center gap-1.5 text-xs text-latte-text-secondary mb-1">
                                <BarChart3 size={12} />
                                已分析
                              </div>
                              <p className="text-lg font-semibold">
                                {contributor.analyzed_commits}
                                <span className="text-xs font-normal text-latte-text-secondary ml-1">/ {contributor.commit_count}</span>
                              </p>
                            </div>
                          </div>

                          <h4 className="text-sm font-medium text-latte-text-primary">提交历史</h4>
                          {detailCommits.length === 0 ? (
                            <p className="text-xs text-latte-text-secondary py-4 text-center">加载中...</p>
                          ) : (
                            detailCommits.map((c) => (
                              <div key={c.commit_hash} className="p-3 bg-latte-bg-secondary rounded-lg border border-latte-border">
                                <div className="flex items-start justify-between gap-2">
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                      <code className="text-xs font-mono bg-latte-bg-tertiary px-1 py-0.5 rounded">
                                        {c.commit_hash.slice(0, 8)}
                                      </code>
                                      {c.risk_level && (
                                        <span className={`px-1.5 py-0.5 rounded text-xs ${riskColors[c.risk_level] || ""}`}>
                                          {c.risk_level}
                                        </span>
                                      )}
                                      {c.findings_count > 0 && (
                                        <span className="text-xs text-latte-text-secondary">{c.findings_count} 发现</span>
                                      )}
                                    </div>
                                    <p className="text-sm text-latte-text-primary mt-1 truncate">{c.message}</p>
                                    <div className="flex items-center gap-3 mt-1 text-xs text-latte-text-secondary">
                                      <span className="text-latte-success">+{c.additions}</span>
                                      <span className="text-latte-critical">-{c.deletions}</span>
                                      <span>{c.changed_files} 文件</span>
                                      {c.commit_ts != null && <span>{new Date(c.commit_ts).toLocaleString("zh-CN")}</span>}
                                    </div>
                                    {c.findings.length > 0 && (
                            <div className="mt-2 space-y-1">
                              {c.findings.map((f, fi) => (
                                <div key={fi} className="flex items-start gap-2 text-xs p-2 bg-latte-bg-tertiary rounded">
                                  <span className={`shrink-0 font-medium ${sevColors[f.severity] || ""}`}>
                                    [{f.severity}]
                                  </span>
                                  <div className="min-w-0">
                                    <p className="text-latte-text-primary">{f.description}</p>
                                    {f.file_path && (
                                      <p className="text-latte-text-secondary mt-0.5">
                                        {f.file_path}{f.line_number ? `:${f.line_number}` : ""}
                                      </p>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                                  </div>
                                </div>
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </>
          )}
        </div>
      )}

      {activeTab === "stats" && stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-5 bg-latte-bg-secondary border border-latte-border rounded-xl">
            <div className="flex items-center gap-2 text-latte-text-secondary text-sm mb-2">
              <GitCommitHorizontal size={16} />
              总提交数
            </div>
            <p className="text-3xl font-semibold text-latte-text-primary">{stats.total_commits}</p>
            <p className="text-xs text-latte-text-secondary mt-1">已分析 {stats.analyzed_commits}</p>
          </div>
          <div className="p-5 bg-latte-bg-secondary border border-latte-border rounded-xl">
            <div className="flex items-center gap-2 text-latte-text-secondary text-sm mb-2">
              <AlertTriangle size={16} />
              发现总数
            </div>
            <p className="text-3xl font-semibold text-latte-text-primary">{stats.total_findings}</p>
          </div>
          <div className="p-5 bg-latte-bg-secondary border border-latte-border rounded-xl">
            <div className="flex items-center gap-2 text-latte-text-secondary text-sm mb-2">
              <BarChart3 size={16} />
              严重程度分布
            </div>
            <div className="space-y-1">
              {Object.entries(stats.severity_distribution).map(([sev, count]) => (
                <div key={sev} className="flex items-center justify-between text-sm">
                  <span className={sevColors[sev] || "text-latte-text-muted"}>{sev}</span>
                  <span className="font-medium">{count}</span>
                </div>
              ))}
              {Object.keys(stats.severity_distribution).length === 0 && (
                <p className="text-xs text-latte-text-secondary">暂无数据</p>
              )}
            </div>
          </div>
          {Object.keys(stats.category_distribution).length > 0 && (
            <div className="md:col-span-3 p-5 bg-latte-bg-secondary border border-latte-border rounded-xl">
              <h3 className="text-sm text-latte-text-secondary mb-3">类别分布</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(stats.category_distribution).map(([cat, count]) => (
                  <div key={cat} className="flex items-center justify-between p-3 bg-latte-bg-tertiary rounded-lg">
                    <span className="text-sm truncate">{cat}</span>
                    <span className="text-sm font-medium ml-2">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === "commits" && (
        <div className="space-y-3">
          {commits.length === 0 ? (
            <div className="text-center py-12 text-latte-text-secondary">
              <GitCommitHorizontal size={36} className="mx-auto mb-3 opacity-40" />
              <p>暂无提交记录</p>
              <p className="text-sm mt-1">点击 &quot;扫描提交&quot; 按钮开始扫描</p>
            </div>
          ) : (
            commits.map((c) => (
              <div
                key={c.commit_hash}
                className="p-4 bg-latte-bg-secondary border border-latte-border rounded-xl hover:shadow-sm transition-shadow"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <code className="text-xs font-mono bg-latte-bg-tertiary px-1.5 py-0.5 rounded">
                        {c.commit_hash.slice(0, 8)}
                      </code>
                      {c.risk_level && (
                        <span className={`px-2 py-0.5 rounded-full text-xs border ${riskColors[c.risk_level] || ""}`}>
                          {c.risk_level}
                        </span>
                      )}
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        c.status === "completed" ? "bg-latte-success/10 text-latte-success" :
                        c.status === "pending" ? "bg-latte-gold/10 text-latte-gold" :
                        c.status === "analyzing" ? "bg-latte-info/10 text-latte-info" :
                        "bg-latte-critical/10 text-latte-critical"
                      }`}>
                        {c.status === "completed" ? "已分析" : c.status === "pending" ? "待分析" : c.status === "analyzing" ? "分析中" : "失败"}
                      </span>
                    </div>
                    <p className="text-sm font-medium text-latte-text-primary truncate">{c.message}</p>
                    <div className="flex items-center gap-4 mt-2 text-xs text-latte-text-secondary">
                      <span className="flex items-center gap-1">
                        <User size={12} />
                        {c.author_name}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock size={12} />
                        {new Date(c.commit_ts).toLocaleString("zh-CN")}
                      </span>
                      <span className="text-latte-success">+{c.additions}</span>
                      <span className="text-latte-critical">-{c.deletions}</span>
                      <span className="flex items-center gap-1">
                        <FileCode size={12} />
                        {c.changed_files} 文件
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 pt-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="p-2 border border-latte-border rounded-lg hover:bg-latte-bg-tertiary disabled:opacity-50"
              >
                <ChevronLeft size={16} />
              </button>
              <span className="text-sm text-latte-text-secondary">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="p-2 border border-latte-border rounded-lg hover:bg-latte-bg-tertiary disabled:opacity-50"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
