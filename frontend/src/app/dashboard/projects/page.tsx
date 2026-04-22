"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import type { ProjectRepo } from "@/types";
import {
  FolderGit2,
  Plus,
  Trash2,
  RefreshCw,
  GitBranch,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ExternalLink,
  Search as SearchIcon,
} from "lucide-react";

const statusConfig: Record<string, { color: string; label: string }> = {
  pending: { color: "bg-latte-warning/10 text-latte-warning border-latte-warning/20", label: "等待中" },
  cloning: { color: "bg-latte-info/10 text-latte-info border-latte-info/20", label: "克隆中" },
  ready: { color: "bg-latte-success/10 text-latte-success border-latte-success/20", label: "就绪" },
  error: { color: "bg-latte-critical/10 text-latte-critical border-latte-critical/20", label: "错误" },
};

export default function ProjectsPage() {
  const { showToast } = useToast();
  const [projects, setProjects] = useState<ProjectRepo[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [addForm, setAddForm] = useState({ platform: "github", repo_url: "", branch: "main" });
  const [addLoading, setAddLoading] = useState(false);
  const [error, setError] = useState("");
  const [scanLoading, setScanLoading] = useState<number | null>(null);

  const loadProjects = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.listProjects();
      setProjects(res.projects || []);
    } catch {
      setError("加载项目列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const extractRepoId = (url: string): string => {
    try {
      const u = new URL(url);
      const parts = u.pathname.replace(/^\/|\/$/g, "").split("/");
      if (parts.length >= 2) return `${parts[parts.length - 2]}/${parts[parts.length - 1]}`.replace(/\.git$/, "");
    } catch {
      // URL parse failed, return original string as fallback
    }
    return url;
  };

  const handleAdd = async () => {
    if (!addForm.repo_url.trim()) return;
    try {
      setAddLoading(true);
      setError("");
      const repo_id = extractRepoId(addForm.repo_url);
      await api.addProject({ ...addForm, repo_id });
      setShowAdd(false);
      setAddForm({ platform: "github", repo_url: "", branch: "main" });
      await loadProjects();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "添加项目失败");
    } finally {
      setAddLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("确定删除该项目及其所有分析数据？")) return;
    try {
      await api.deleteProject(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "删除失败");
    }
  };

  const handleSync = async (id: number) => {
    try {
      await api.syncProject(id);
      await loadProjects();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "同步失败");
    }
  };

  const handleScan = async (id: number) => {
    try {
      setScanLoading(id);
      setError("");
      const res = await api.scanCommits(id, 100);
      showToast(`扫描完成：共 ${res.scanned} 个提交，新增 ${res.saved} 条记录`);
      await loadProjects();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "扫描失败");
    } finally {
      setScanLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-latte-gold" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-latte-text-primary">项目管理</h1>
          <p className="text-sm text-latte-text-secondary mt-1">添加 Git 仓库，扫描提交记录进行分析</p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 px-4 py-2 bg-latte-gold text-latte-bg-primary rounded-lg hover:bg-latte-gold/90 transition-colors"
        >
          <Plus size={18} />
          添加项目
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 bg-latte-critical/5 border border-latte-critical/20 rounded-lg text-latte-critical text-sm">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {showAdd && (
        <div className="p-5 bg-latte-bg-secondary border border-latte-border rounded-xl space-y-4">
          <h3 className="font-medium text-latte-text-primary">添加新项目</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-latte-text-secondary mb-1">平台</label>
              <select
                value={addForm.platform}
                onChange={(e) => setAddForm((f) => ({ ...f, platform: e.target.value }))}
                className="w-full px-3 py-2 border border-latte-border rounded-lg text-sm bg-latte-bg-primary"
              >
                <option value="github">GitHub</option>
                <option value="gitlab">GitLab</option>
              </select>
            </div>
            <div className="md:col-span-1">
              <label className="block text-sm text-latte-text-secondary mb-1">仓库 URL</label>
              <input
                type="text"
                value={addForm.repo_url}
                onChange={(e) => setAddForm((f) => ({ ...f, repo_url: e.target.value }))}
                placeholder="https://github.com/org/repo.git"
                className="w-full px-3 py-2 border border-latte-border rounded-lg text-sm bg-latte-bg-primary text-latte-text-primary"
              />
            </div>
            <div>
              <label className="block text-sm text-latte-text-secondary mb-1">分支</label>
              <input
                type="text"
                value={addForm.branch}
                onChange={(e) => setAddForm((f) => ({ ...f, branch: e.target.value }))}
                placeholder="main"
                className="w-full px-3 py-2 border border-latte-border rounded-lg text-sm bg-latte-bg-primary text-latte-text-primary"
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleAdd}
              disabled={addLoading || !addForm.repo_url.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-latte-gold text-latte-bg-primary rounded-lg hover:bg-latte-gold/90 disabled:opacity-50 transition-colors text-sm"
            >
              {addLoading ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
              添加
            </button>
            <button
              onClick={() => { setShowAdd(false); setError(""); }}
              className="px-4 py-2 text-sm text-latte-text-secondary hover:text-latte-text-primary"
            >
              取消
            </button>
          </div>
        </div>
      )}

      {projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-latte-text-secondary">
          <FolderGit2 size={48} className="mb-4 opacity-40" />
          <p className="text-lg font-medium">暂无项目</p>
          <p className="text-sm mt-1">点击上方按钮添加你的第一个 Git 仓库</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {projects.map((project) => {
            const st = statusConfig[project.status] || statusConfig.pending;
            return (
              <div
                key={project.id}
                className="p-5 bg-latte-bg-secondary border border-latte-border rounded-xl hover:shadow-sm transition-shadow"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <Link
                        href={`/dashboard/projects/${project.id}`}
                        className="text-lg font-medium text-latte-text-primary hover:text-latte-gold transition-colors truncate"
                      >
                        {project.repo_id}
                      </Link>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${st.color}`}>
                        {st.label}
                      </span>
                      <span className="px-2 py-0.5 bg-latte-bg-tertiary rounded text-xs text-latte-text-secondary">
                        {project.platform}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-latte-text-secondary">
                      <span className="flex items-center gap-1">
                        <GitBranch size={14} />
                        {project.branch}
                      </span>
                      <span>{project.total_commits} 提交</span>
                      <span>{project.total_findings} 发现</span>
                      <span className="flex items-center gap-1">
                        {project.status === "ready" ? (
                          <CheckCircle2 size={14} className="text-latte-success" />
                        ) : project.status === "error" ? (
                          <AlertCircle size={14} className="text-latte-critical" />
                        ) : null}
                        {project.error_message && (
                          <span className="text-latte-critical truncate max-w-xs">{project.error_message}</span>
                        )}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <button
                      onClick={() => handleScan(project.id)}
                      disabled={project.status !== "ready" || scanLoading === project.id}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm border border-latte-border rounded-lg hover:bg-latte-bg-tertiary disabled:opacity-50 transition-colors"
                      title="扫描提交记录"
                    >
                      {scanLoading === project.id ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <SearchIcon size={14} />
                      )}
                      扫描
                    </button>
                    <button
                      onClick={() => handleSync(project.id)}
                      disabled={project.status !== "ready"}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm border border-latte-border rounded-lg hover:bg-latte-bg-tertiary disabled:opacity-50 transition-colors"
                      title="同步仓库"
                    >
                      <RefreshCw size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(project.id)}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm border border-latte-critical/30 text-latte-critical rounded-lg hover:bg-latte-critical/5 transition-colors"
                      title="删除项目"
                    >
                      <Trash2 size={14} />
                    </button>
                    <Link
                      href={`/dashboard/projects/${project.id}`}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm border border-latte-border rounded-lg hover:bg-latte-bg-tertiary transition-colors"
                    >
                      <ExternalLink size={14} />
                      详情
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
