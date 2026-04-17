"use client";

import { useState, useEffect } from "react";
import { useMetrics } from "@/hooks/use-metrics";
import { GlassCard } from "@/components/ui/glass-card";
import { FadeInUp } from "@/components/motion/fade-in-up";
import { CountUp } from "@/components/ui/count-up";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
} from "recharts";

const rangeOptions: Array<"7d" | "30d" | "90d"> = ["7d", "30d", "90d"];

const pieColors = [
  "var(--latte-gold)",
  "var(--latte-rose)",
  "var(--latte-success)",
  "var(--latte-info)",
  "var(--latte-warning)",
  "var(--latte-critical)",
];

const defaultPieData = [
  { name: "Security", value: 35 },
  { name: "Performance", value: 25 },
  { name: "Style", value: 20 },
  { name: "Logic", value: 20 },
];

export default function MetricsPage() {
  const [range, setRange] = useState<"7d" | "30d" | "90d">("7d");
  const { metrics, chart, categoryDistribution, isLoading, error } = useMetrics(range, "default");
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <FadeInUp>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <h1 className="text-2xl font-display font-semibold tracking-tight text-latte-text-primary">
            Metrics
          </h1>
          <div className="flex gap-2">
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

      {error ? (
        <FadeInUp delay={0.1}>
          <div className="flex flex-col items-center justify-center py-12 text-latte-text-tertiary">
            <p className="text-lg font-medium">Failed to load metrics</p>
            <p className="text-sm mt-1">{error.message || "Please try again later"}</p>
          </div>
        </FadeInUp>
      ) : isLoading || !metrics ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 bg-latte-bg-secondary rounded-latte-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <FadeInUp delay={0.1}>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <GlassCard className="p-6" variant="elevated">
              <p className="text-sm text-latte-text-tertiary">Total Reviews</p>
              <p className="text-3xl font-display font-semibold text-latte-text-primary mt-2">
                <CountUp value={metrics.total_reviews} />
              </p>
            </GlassCard>
            <GlassCard className="p-6" variant="elevated">
              <p className="text-sm text-latte-text-tertiary">Total Findings</p>
              <p className="text-3xl font-display font-semibold text-latte-text-primary mt-2">
                <CountUp value={metrics.total_findings} />
              </p>
            </GlassCard>
            <GlassCard className="p-6" variant="elevated">
              <p className="text-sm text-latte-text-tertiary">Avg Confidence</p>
              <p className="text-3xl font-display font-semibold text-latte-text-primary mt-2">
                <CountUp value={Math.round(metrics.avg_confidence * 100)} suffix="%" />
              </p>
            </GlassCard>
            <GlassCard className="p-6" variant="elevated">
              <p className="text-sm text-latte-text-tertiary">False Positive Rate</p>
              <p className="text-3xl font-display font-semibold text-latte-text-primary mt-2">
                <CountUp value={Math.round(metrics.false_positive_rate * 100)} suffix="%" />
              </p>
            </GlassCard>
          </div>
        </FadeInUp>
      )}

      <FadeInUp delay={0.2}>
        <GlassCard className="p-6">
          <h3 className="text-lg font-medium text-latte-text-primary mb-4">Review Volume</h3>
          <div className="h-72 w-full">
            {mounted ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chart}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(245, 230, 211, 0.06)" />
                <XAxis
                  dataKey="date"
                  stroke="var(--latte-text-tertiary)"
                  tick={{ fill: "var(--latte-text-tertiary)", fontSize: 12 }}
                  axisLine={{ stroke: "rgba(245, 230, 211, 0.1)" }}
                />
                <YAxis
                  stroke="var(--latte-text-tertiary)"
                  tick={{ fill: "var(--latte-text-tertiary)", fontSize: 12 }}
                  axisLine={{ stroke: "rgba(245, 230, 211, 0.1)" }}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--latte-bg-secondary)",
                    border: "1px solid rgba(245, 230, 211, 0.1)",
                    borderRadius: "12px",
                  }}
                  labelStyle={{ color: "var(--latte-text-primary)" }}
                  itemStyle={{ color: "var(--latte-text-secondary)" }}
                />
                <Line
                  type="monotone"
                  dataKey="reviews"
                  stroke="var(--latte-gold)"
                  strokeWidth={2}
                  dot={{ fill: "var(--latte-gold)", strokeWidth: 0, r: 3 }}
                  activeDot={{ r: 5, fill: "var(--latte-accent)" }}
                />
                <Line
                  type="monotone"
                  dataKey="findings"
                  stroke="var(--latte-rose)"
                  strokeWidth={2}
                  dot={{ fill: "var(--latte-rose)", strokeWidth: 0, r: 3 }}
                  activeDot={{ r: 5, fill: "var(--latte-rose)" }}
                />
              </LineChart>
            </ResponsiveContainer>
            ) : null}
          </div>
        </GlassCard>
      </FadeInUp>

      <FadeInUp delay={0.3}>
        <GlassCard className="p-6">
          <h3 className="text-lg font-medium text-latte-text-primary mb-4">Findings by Category</h3>
          <div className="h-64 w-full">
            {mounted ? (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={categoryDistribution && Object.keys(categoryDistribution).length > 0
                    ? Object.entries(categoryDistribution).map(([name, value]) => ({ name, value }))
                    : defaultPieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {(categoryDistribution && Object.keys(categoryDistribution).length > 0
                    ? Object.entries(categoryDistribution).map(([name, value]) => ({ name, value }))
                    : defaultPieData
                  ).map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={pieColors[index % pieColors.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "var(--latte-bg-secondary)",
                    border: "1px solid rgba(245, 230, 211, 0.1)",
                    borderRadius: "12px",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
            ) : null}
          </div>
        </GlassCard>
      </FadeInUp>
    </div>
  );
}
