"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useStats } from "@/hooks/use-stats";
import { GlassCard } from "@/components/ui/glass-card";
import { FadeInUp } from "@/components/motion/fade-in-up";
import { StatusBadge } from "@/components/ui/status-badge";
import { CountUp } from "@/components/ui/count-up";
import { useToast } from "@/components/ui/toast";
import { notifySuccess, notifyError } from "@/components/ui/notification";
import { OnboardingWizard } from "@/components/dashboard/onboarding-wizard";
import { ManualTriggerDialog } from "@/components/dashboard/manual-trigger-dialog";
import { Button } from "@/components/ui/button";
import {
  Rocket,
  GitPullRequest,
  FolderGit2,
  Search,
  Loader2,
  CheckCircle2,
  AlertCircle,
  ChevronRight,
  GitBranch,
  Plus,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { ProjectRepo } from "@/types";

export default function DashboardPage() {
  const router = useRouter();
  const { stats, isLoading, error, mutate } = useStats();
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showTriggerDialog, setShowTriggerDialog] = useState(false);
  const [projects, setProjects] = useState<ProjectRepo[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [scanningId, setScanningId] = useState<number | null>(null);
  const { showToast } = useToast();

  const loadProjects = useCallback(async () => {
    try {
      setProjectsLoading(true);
      const res = await api.listProjects();
      setProjects(res.projects || []);
    } catch (err) {
      console.error("Failed to load projects:", err);
      setProjects([]);
    } finally {
      setProjectsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleQuickScan = async (e: React.MouseEvent, projectId: number) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      setScanningId(projectId);
      await api.scanCommits(projectId, 100);
      await loadProjects();
      notifySuccess("扫描完成", `项目 #${projectId} 的提交扫描已成功触发`, { category: "sync", action_url: `/dashboard/projects/${projectId}` });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "未知错误";
      showToast("扫描失败：" + msg, "error");
      notifyError("扫描失败", msg, { category: "sync" });
    } finally {
      setScanningId(null);
    }
  };

  if (error) {
    return (
      <div className="max-w-6xl mx-auto flex flex-col items-center justify-center py-20 text-latte-text-tertiary">
        <p className="text-lg font-medium">加载仪表盘数据失败</p>
        <p className="text-sm mt-1">{error.message || "请稍后重试"}</p>
      </div>
    );
  }

  const isEmpty = !isLoading && stats && stats.total_reviews === 0 && projects.length === 0;

  if (isEmpty && showOnboarding) {
    return (
      <div className="py-8">
        <OnboardingWizard onComplete={() => setShowOnboarding(false)} />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <FadeInUp>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-display font-semibold tracking-tight text-latte-text-primary">
              仪表盘
            </h1>
            <p className="text-sm text-latte-text-tertiary mt-1">
              代码审查活动总览
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => setShowTriggerDialog(true)}>
            <GitPullRequest size={14} />
            手动审查
          </Button>
        </div>
      </FadeInUp>

      <ManualTriggerDialog
        open={showTriggerDialog}
        onClose={() => setShowTriggerDialog(false)}
        onTriggered={() => mutate()}
      />

      {isEmpty && (
        <FadeInUp delay={0.1}>
          <GlassCard className="p-12 text-center" variant="elevated">
            <div className="max-w-md mx-auto">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-latte-2xl bg-latte-gold/10 mb-5">
                <Rocket className="w-7 h-7 text-latte-gold" />
              </div>
              <h3 className="text-lg font-display font-semibold text-latte-text-primary mb-2">
                暂无项目
              </h3>
              <p className="text-sm text-latte-text-tertiary mb-6">
                注册你的第一个仓库即可开始使用。Latte 将自动审查每个拉取请求，检查安全性、代码质量和最佳实践。
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                <Button variant="primary" onClick={() => setShowOnboarding(true)}>
                  <Rocket size={16} />
                  配置你的第一个项目
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => router.push("/dashboard/projects")}
                >
                  添加项目仓库
                </Button>
              </div>
            </div>
          </GlassCard>
        </FadeInUp>
      )}

      {!isEmpty && (
        <>
          <FadeInUp delay={0.1}>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {isLoading || !stats ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-32 bg-latte-bg-secondary rounded-latte-xl animate-pulse" />
                ))
              ) : (
                <>
                  <GlassCard className="p-6" variant="elevated">
                    <p className="text-sm text-latte-text-tertiary">审查总数</p>
                    <p className="text-3xl font-display font-semibold text-latte-text-primary mt-2">
                      <CountUp value={stats.total_reviews} />
                    </p>
                  </GlassCard>
                  <GlassCard className="p-6" variant="elevated">
                    <p className="text-sm text-latte-text-tertiary">待处理</p>
                    <p className="text-3xl font-display font-semibold text-latte-text-primary mt-2">
                      <CountUp value={stats.pending_reviews} />
                    </p>
                  </GlassCard>
                  <GlassCard className="p-6" variant="elevated">
                    <p className="text-sm text-latte-text-tertiary">已完成</p>
                    <p className="text-3xl font-display font-semibold text-latte-text-primary mt-2">
                      <CountUp value={stats.completed_reviews} />
                    </p>
                  </GlassCard>
                  <GlassCard className="p-6" variant="elevated">
                    <p className="text-sm text-latte-text-tertiary">高风险</p>
                    <p className="text-3xl font-display font-semibold text-latte-rose mt-2">
                      <CountUp value={stats.high_risk_count} />
                    </p>
                  </GlassCard>
                </>
              )}
            </div>
          </FadeInUp>

          <FadeInUp delay={0.2}>
            <GlassCard className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-latte-text-primary">已接入项目</h3>
                <Link href="/dashboard/projects">
                  <Button variant="ghost" size="sm">
                    <Plus size={14} />
                    添加项目
                  </Button>
                </Link>
              </div>
              {projectsLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 2 }).map((_, i) => (
                    <div key={i} className="h-16 bg-latte-bg-secondary rounded-latte-lg animate-pulse" />
                  ))}
                </div>
              ) : projects.length === 0 ? (
                <div className="text-sm text-latte-text-tertiary py-8 text-center">
                  暂未接入任何项目 —{" "}
                  <Link href="/dashboard/projects" className="text-latte-gold hover:underline">
                    添加项目仓库
                  </Link>{" "}
                  开始分析
                </div>
              ) : (
                <div className="space-y-2">
                  {projects.map((project) => (
                    <Link
                      key={project.id}
                      href={`/dashboard/projects/${project.id}`}
                      className="flex items-center gap-4 p-4 rounded-latte-lg border border-latte-border hover:border-latte-gold/30 hover:bg-latte-bg-tertiary/20 transition-all group"
                    >
                      <div className="flex items-center justify-center w-10 h-10 rounded-latte-md bg-latte-bg-tertiary shrink-0">
                        <FolderGit2 size={20} className="text-latte-gold" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium text-latte-text-primary truncate">
                            {project.repo_id}
                          </p>
                          <span className="text-xs px-1.5 py-0.5 rounded bg-latte-bg-tertiary text-latte-text-tertiary">
                            {project.platform}
                          </span>
                          {project.status === "ready" ? (
                            <CheckCircle2 size={14} className="text-green-500 shrink-0" />
                          ) : project.status === "error" ? (
                            <AlertCircle size={14} className="text-latte-critical shrink-0" />
                          ) : null}
                        </div>
                        <div className="flex items-center gap-3 mt-1 text-xs text-latte-text-tertiary">
                          <span className="flex items-center gap-1">
                            <GitBranch size={12} />
                            {project.branch}
                          </span>
                          <span>{project.total_commits} 提交</span>
                          <span>{project.total_findings} 发现</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={(e) => handleQuickScan(e, project.id)}
                          disabled={project.status !== "ready" || scanningId === project.id}
                          className="flex items-center gap-1 px-3 py-1.5 text-xs border border-latte-border rounded-latte-md hover:bg-latte-gold/10 hover:border-latte-gold/30 disabled:opacity-50 transition-colors"
                          title="扫描提交记录"
                        >
                          {scanningId === project.id ? (
                            <Loader2 size={12} className="animate-spin" />
                          ) : (
                            <Search size={12} />
                          )}
                          分析
                        </button>
                        <ChevronRight size={16} className="text-latte-text-tertiary group-hover:text-latte-gold transition-colors" />
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </GlassCard>
          </FadeInUp>

          <FadeInUp delay={0.3}>
            <GlassCard className="p-6">
              <h3 className="text-lg font-medium text-latte-text-primary mb-4">最近审查</h3>
              {isLoading || !stats ? (
                <div className="space-y-3">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="h-14 bg-latte-bg-secondary rounded-latte-lg animate-pulse" />
                  ))}
                </div>
              ) : stats.recent_reviews.length === 0 ? (
                <div className="text-sm text-latte-text-tertiary py-8 text-center">
                  暂无审查记录 — 向已配置的仓库提交 PR 即可开始
                </div>
              ) : (
                <div className="divide-y divide-latte-text-primary/5">
                  {stats.recent_reviews.map((review) => (
                    <Link
                      key={review.id}
                      href={`/dashboard/reviews/${review.id}`}
                      className="flex items-center justify-between py-4 hover:bg-latte-bg-tertiary/30 px-2 rounded-latte-md transition-colors"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-latte-text-primary truncate">
                          #{review.pr_number} {review.pr_title || "未命名 PR"}
                        </p>
                        <p className="text-xs text-latte-text-tertiary mt-0.5">
                          {review.repo_id} · {new Date(review.created_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <StatusBadge status={review.status} />
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </GlassCard>
          </FadeInUp>
        </>
      )}
    </div>
  );
}
