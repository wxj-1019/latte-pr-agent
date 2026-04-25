"use client";

import { cn } from "@/lib/utils";

interface HorizontalBarChartProps {
  data: Record<string, number>;
  colors?: Record<string, string>;
  title?: string;
  className?: string;
  height?: number;
}

const DEFAULT_COLORS: Record<string, string> = {
  critical: "#EF5350",
  high: "#FF8A65",
  medium: "#FFD54F",
  low: "#81C784",
  warning: "#FFB74D",
  info: "#64B5F6",
};

const LABEL_MAP: Record<string, string> = {
  critical: "严重",
  high: "高",
  medium: "中",
  low: "低",
  warning: "警告",
  info: "信息",
};

const ICON_DOT: Record<string, string> = {
  critical: "🔴",
  high: "🟠",
  medium: "🟡",
  low: "🟢",
  warning: "⚠️",
  info: "ℹ️",
};

export function HorizontalBarChart({
  data,
  colors = DEFAULT_COLORS,
  title,
  className,
  height = 260,
}: HorizontalBarChartProps) {
  const entries = Object.entries(data)
    .filter(([, v]) => v > 0)
    .sort(([, a], [, b]) => b - a);

  const total = entries.reduce((sum, [, v]) => sum + v, 0);
  const maxValue = Math.max(...entries.map(([, v]) => v), 1);

  if (entries.length === 0) {
    return (
      <div className={cn("relative w-full", className)}>
        {title && <h3 className="text-sm font-medium text-latte-text-primary mb-3">{title}</h3>}
        <div className="flex items-center justify-center text-latte-text-tertiary text-sm" style={{ height }}>
          暂无数据
        </div>
      </div>
    );
  }

  return (
    <div className={cn("relative w-full", className)}>
      {title && <h3 className="text-sm font-medium text-latte-text-primary mb-3">{title}</h3>}
      <div className="space-y-3" style={{ height }}>
        {entries.map(([key, value]) => {
          const percent = total > 0 ? Math.round((value / total) * 100) : 0;
          const widthPercent = Math.max((value / maxValue) * 100, 4);
          const color = colors[key] || DEFAULT_COLORS[key] || "#C4A77D";
          const label = LABEL_MAP[key] || key;
          const icon = ICON_DOT[key] || "●";

          return (
            <div key={key} className="group">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-sm">{icon}</span>
                  <span className="text-sm font-medium text-latte-text-primary">{label}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-latte-text-primary">{value}</span>
                  <span className="text-xs text-latte-text-tertiary">{percent}%</span>
                </div>
              </div>
              <div className="h-2.5 bg-latte-bg-tertiary rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700 ease-out group-hover:brightness-110"
                  style={{
                    width: `${widthPercent}%`,
                    backgroundColor: color,
                    boxShadow: `0 0 8px ${color}40`,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
