"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { ProjectRepo, CommitAnalysis, ProjectStats } from "@/types";
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
} from "lucide-react";

const riskColors: Record<string, string> = {
  critical: "bg-red-100 text-red-700 border-red-200",
  high: "bg-orange-100 text-orange-700 border-orange-200",
  medium: "bg-yellow-100 text-yellow-700 border-yellow-200",
  low: "bg-green-100 text-green-700 border-green-200",
};

const sevColors: Record<string, string> = {
  critical: "text-red-600",
  warning: "text-yellow-600",
  info: "text-blue-600",
};

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = Number(params.id);

  const [project, setProject] = useState<ProjectRepo | null>(null);
  const [stats, setStats] = useState<ProjectStats | null>(null);
  const [commits, setCommits] = useState<CommitAnalysis[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [scanLoading, setScanLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"commits" | "stats">("commits");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [proj, stat, commitRes] = await Promise.all([
        api.getProject(projectId),
        api.getProjectStats(projectId).catch(() => null),
        api.listCommits(projectId, page, 20),
      ]);
      setProject(proj);
      setStats(stat);
      setCommits(commitRes.commits || []);
      setTotal(commitRes.total || 0);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [projectId, page]);

  useEffect(() => {
    load();
  }, [load]);

  const handleScan = async () => {
    try {
      setScanLoading(true);
      setError("");
      const res = await api.scanCommits(projectId, 200);
      alert(`扫描完成：${res.scanned} 个提交，新增 ${res.saved} 条`);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "扫描失败");
    } finally {
      setScanLoading(false);
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
          onClick={handleScan}
          disabled={project.status !== "ready" || scanLoading}
          className="flex items-center gap-2 px-4 py-2 bg-latte-gold text-white rounded-lg hover:bg-latte-gold/90 disabled:opacity-50 transition-colors text-sm"
        >
          {scanLoading ? <Loader2 size={16} className="animate-spin" /> : <SearchIcon size={16} />}
          扫描提交
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <div className="flex gap-2 border-b border-latte-border pb-0">
        {(["commits", "stats"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? "border-latte-gold text-latte-gold"
                : "border-transparent text-latte-text-secondary hover:text-latte-text-primary"
            }`}
          >
            {tab === "commits" ? "提交记录" : "统计概览"}
          </button>
        ))}
      </div>

      {activeTab === "stats" && stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-5 bg-white border border-latte-border rounded-xl">
            <div className="flex items-center gap-2 text-latte-text-secondary text-sm mb-2">
              <GitCommitHorizontal size={16} />
              总提交数
            </div>
            <p className="text-3xl font-semibold text-latte-text-primary">{stats.total_commits}</p>
            <p className="text-xs text-latte-text-secondary mt-1">已分析 {stats.analyzed_commits}</p>
          </div>
          <div className="p-5 bg-white border border-latte-border rounded-xl">
            <div className="flex items-center gap-2 text-latte-text-secondary text-sm mb-2">
              <AlertTriangle size={16} />
              发现总数
            </div>
            <p className="text-3xl font-semibold text-latte-text-primary">{stats.total_findings}</p>
          </div>
          <div className="p-5 bg-white border border-latte-border rounded-xl">
            <div className="flex items-center gap-2 text-latte-text-secondary text-sm mb-2">
              <BarChart3 size={16} />
              严重程度分布
            </div>
            <div className="space-y-1">
              {Object.entries(stats.severity_distribution).map(([sev, count]) => (
                <div key={sev} className="flex items-center justify-between text-sm">
                  <span className={sevColors[sev] || "text-gray-600"}>{sev}</span>
                  <span className="font-medium">{count}</span>
                </div>
              ))}
              {Object.keys(stats.severity_distribution).length === 0 && (
                <p className="text-xs text-latte-text-secondary">暂无数据</p>
              )}
            </div>
          </div>
          {Object.keys(stats.category_distribution).length > 0 && (
            <div className="md:col-span-3 p-5 bg-white border border-latte-border rounded-xl">
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
                className="p-4 bg-white border border-latte-border rounded-xl hover:shadow-sm transition-shadow"
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
                        c.status === "completed" ? "bg-green-50 text-green-600" :
                        c.status === "pending" ? "bg-yellow-50 text-yellow-600" :
                        c.status === "analyzing" ? "bg-blue-50 text-blue-600" :
                        "bg-red-50 text-red-600"
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
                      <span className="text-green-600">+{c.additions}</span>
                      <span className="text-red-500">-{c.deletions}</span>
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
