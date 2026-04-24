"use client";

import { useState, useEffect } from "react";
import { useMetrics } from "@/hooks/use-metrics";
import { GlassCard } from "@/components/ui/glass-card";
import { FadeInUp } from "@/components/motion/fade-in-up";
import { LiquidGauge } from "@/components/ui/liquid-gauge";
import { NebulaChart } from "@/components/ui/nebula-chart";
import { api } from "@/lib/api";
import type { ProjectRepo } from "@/types";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";
import {
  FolderGit2,
  Users,
} from "lucide-react";
import Link from "next/link";

const rangeOptions: Array<"7d" | "30d" | "90d"> = ["7d", "30d", "90d"];





export default function MetricsPage() {
  const [range, setRange] = useState<"7d" | "30d" | "90d">("7d");
  const [projects, setProjects] = useState<ProjectRepo[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<string>("");
  const [projectsLoading, setProjectsLoading] = useState(true);

  useEffect(() => {
    api
      .listProjects()
      .then((res) => {
        const list = res.projects || [];
        setProjects(list);
        if (list.length > 0) {
          setSelectedRepo(list[0].repo_id);
        }
      })
      .catch(() => setProjects([]))
      .finally(() => setProjectsLoading(false));
  }, []);

  const {
    metrics,
    chart,
    commit,
    categoryDistribution,
    severityDistribution,
    contributors,
    isLoading,
    error,
  } = useMetrics(range, selectedRepo || undefined);

  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const showEmpty = !projectsLoading && projects.length === 0;

  const chartData = chart.map((d) => ({
    ...d,
    label: new Date(d.date).toLocaleDateString("zh-CN", {
      month: "short",
      day: "numeric",
    }),
  }));



  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <FadeInUp>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <h1 className="text-2xl font-display font-semibold tracking-tight text-latte-text-primary">
            指标
          </h1>
          <div className="flex flex-wrap items-center gap-2">
            {projects.length > 0 && (
              <select
                value={selectedRepo}
                onChange={(e) => setSelectedRepo(e.target.value)}
                className="h-9 px-3 rounded-latte-md bg-latte-bg-tertiary text-sm text-latte-text-secondary border border-transparent focus:border-latte-gold/40 outline-none"
              >
                {projects.map((p) => (
                  <option key={p.repo_id} value={p.repo_id}>
                    {p.repo_id}
                  </option>
                ))}
              </select>
            )}
            {rangeOptions.map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-3 py-1.5 text-xs font-medium rounded-latte-md transition-colors ${
                  range === r
                    ? "bg-latte-gold/15 text-latte-gold border border-latte-gold/30"
                    : "text-latte-text-tertiary hover:text-latte-text-primary hover:bg-latte-bg-tertiary"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </FadeInUp>

      {showEmpty ? (
        <FadeInUp delay={0.1}>
          <GlassCard className="p-12 text-center">
            <FolderGit2 size={40} className="mx-auto mb-4 text-latte-gold opacity-50" />
            <p className="text-lg font-medium text-latte-text-primary mb-2">暂无仓库数据</p>
            <p className="text-sm text-latte-text-tertiary mb-6">
              添加项目仓库后即可查看审查指标和趋势分析
            </p>
            <Link
              href="/dashboard/projects"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-latte-lg bg-latte-gold/10 text-latte-gold text-sm font-medium hover:bg-latte-gold/15 transition-colors"
            >
              添加项目仓库
            </Link>
          </GlassCard>
        </FadeInUp>
      ) : error ? (
        <FadeInUp delay={0.1}>
          <div className="flex flex-col items-center justify-center py-12 text-latte-text-tertiary">
            <p className="text-lg font-medium">加载指标失败</p>
            <p className="text-sm mt-1">{error.message || "请稍后重试"}</p>
          </div>
        </FadeInUp>
      ) : isLoading || !metrics ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-48 bg-latte-bg-secondary rounded-latte-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <>
          <FadeInUp delay={0.1}>
            <GlassCard className="p-6" variant="elevated">
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 justify-items-center">
                <LiquidGauge
                  value={commit?.analyzed_commits ?? 0}
                  max={Math.max(commit?.total_commits ?? 1, 1)}
                  label="分析覆盖率"
                  sublabel={`${commit?.analyzed_commits ?? 0} / ${commit?.total_commits ?? 0}`}
                  color="var(--latte-gold)"
                  size={130}
                />
                <LiquidGauge
                  value={metrics.total_findings}
                  max={Math.max(metrics.total_findings * 1.5, 50)}
                  label="发现项总数"
                  sublabel={`Commit ${metrics.total_commit_findings}`}
                  color="var(--latte-rose)"
                  size={130}
                />
                <LiquidGauge
                  value={Math.round((metrics.avg_confidence || 0) * 100)}
                  max={100}
                  label="平均置信度"
                  sublabel="AI 评估"
                  color="var(--latte-info)"
                  size={130}
                />
                <LiquidGauge
                  value={Math.round(metrics.false_positive_rate * 100)}
                  max={100}
                  label="误报率"
                  sublabel="越低越好"
                  color="var(--latte-warning)"
                  size={130}
                />
              </div>
            </GlassCard>
          </FadeInUp>

          <FadeInUp delay={0.15}>
            <GlassCard className="p-6">
              <h3 className="text-lg font-medium text-latte-text-primary mb-4">审查趋势</h3>
              <div className="h-80 w-full">
                {mounted ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="var(--latte-chart-grid)"
                      />
                      <XAxis
                        dataKey="label"
                        stroke="var(--latte-text-tertiary)"
                        tick={{ fill: "var(--latte-text-tertiary)", fontSize: 12 }}
                        axisLine={{ stroke: "var(--latte-chart-axis)" }}
                      />
                      <YAxis
                        stroke="var(--latte-text-tertiary)"
                        tick={{ fill: "var(--latte-text-tertiary)", fontSize: 12 }}
                        axisLine={{ stroke: "var(--latte-chart-axis)" }}
                      />
                      <Tooltip
                        contentStyle={{
                          background: "var(--latte-bg-secondary)",
                          border: "1px solid var(--latte-chart-tooltip-border)",
                          borderRadius: "12px",
                        }}
                        labelStyle={{ color: "var(--latte-text-primary)" }}
                        itemStyle={{ color: "var(--latte-text-secondary)" }}
                      />
                      <Legend
                        wrapperStyle={{ fontSize: 12, color: "var(--latte-text-secondary)" }}
                      />
                      <Line
                        type="monotone"
                        dataKey="analyses"
                        name="Commit 分析"
                        stroke="var(--latte-gold)"
                        strokeWidth={2}
                        dot={{ fill: "var(--latte-gold)", strokeWidth: 0, r: 3 }}
                        activeDot={{ r: 5, fill: "var(--latte-gold)" }}
                      />
                      <Line
                        type="monotone"
                        dataKey="commit_findings"
                        name="Commit 发现项"
                        stroke="var(--latte-rose)"
                        strokeWidth={2}
                        dot={{ fill: "var(--latte-rose)", strokeWidth: 0, r: 3 }}
                        activeDot={{ r: 5, fill: "var(--latte-rose)" }}
                      />
                      <Line
                        type="monotone"
                        dataKey="reviews"
                        name="PR 审查"
                        stroke="var(--latte-info)"
                        strokeWidth={2}
                        dot={{ fill: "var(--latte-info)", strokeWidth: 0, r: 3 }}
                        activeDot={{ r: 5, fill: "var(--latte-info)" }}
                        strokeDasharray="5 5"
                      />
                      <Line
                        type="monotone"
                        dataKey="pr_findings"
                        name="PR 发现项"
                        stroke="var(--latte-success)"
                        strokeWidth={2}
                        dot={{ fill: "var(--latte-success)", strokeWidth: 0, r: 3 }}
                        activeDot={{ r: 5, fill: "var(--latte-success)" }}
                        strokeDasharray="5 5"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : null}
              </div>
            </GlassCard>
          </FadeInUp>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <FadeInUp delay={0.2}>
              <GlassCard className="p-6">
                <NebulaChart
                  data={categoryDistribution ?? {}}
                  title="发现项类别星云"
                  height={280}
                />
              </GlassCard>
            </FadeInUp>

            <FadeInUp delay={0.25}>
              <GlassCard className="p-6">
                <NebulaChart
                  data={severityDistribution ?? {}}
                  title="严重级别星云"
                  height={280}
                />
              </GlassCard>
            </FadeInUp>
          </div>

          {contributors && contributors.length > 0 && (
            <FadeInUp delay={0.3}>
              <GlassCard className="p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Users size={18} className="text-latte-gold" />
                  <h3 className="text-lg font-medium text-latte-text-primary">
                    贡献者排行（按发现问题数）
                  </h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-latte-border-subtle">
                        <th className="text-left py-2 px-3 text-latte-text-tertiary font-medium">
                          作者
                        </th>
                        <th className="text-right py-2 px-3 text-latte-text-tertiary font-medium">
                          Commits
                        </th>
                        <th className="text-right py-2 px-3 text-latte-text-tertiary font-medium">
                          发现项
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {contributors.map((c, i) => (
                        <tr
                          key={i}
                          className="border-b border-latte-border-subtle/50 hover:bg-latte-bg-tertiary/50 transition-colors"
                        >
                          <td className="py-2.5 px-3 text-latte-text-primary font-medium">
                            {c.author}
                          </td>
                          <td className="py-2.5 px-3 text-right text-latte-text-secondary">
                            {c.commit_count}
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-latte-rose/10 text-latte-rose">
                              {c.finding_count}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </GlassCard>
            </FadeInUp>
          )}
        </>
      )}
    </div>
  );
}
