"use client";

import { useState } from "react";
import {
  RadialBarChart,
  RadialBar,
  ResponsiveContainer,
  PolarAngleAxis,
  Tooltip,
} from "recharts";
import { cn } from "@/lib/utils";

interface RadialDistributionChartProps {
  data: Record<string, number>;
  colors?: Record<string, string>;
  title?: string;
  className?: string;
  height?: number;
}

const DEFAULT_COLORS: Record<string, string> = {
  architecture: "#C4A77D",
  logic: "#D4A59A",
  performance: "#81C784",
  style: "#90CAF9",
  security: "#EF9A9A",
  critical: "#EF5350",
  warning: "#FFB74D",
  info: "#64B5F6",
  low: "#81C784",
  medium: "#FFD54F",
  high: "#FF8A65",
};

const LABEL_MAP: Record<string, string> = {
  architecture: "架构",
  logic: "逻辑",
  performance: "性能",
  style: "风格",
  security: "安全",
  critical: "严重",
  warning: "警告",
  info: "信息",
  low: "低",
  medium: "中",
  high: "高",
};

export function RadialDistributionChart({
  data,
  colors = DEFAULT_COLORS,
  title,
  className,
  height = 320,
}: RadialDistributionChartProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const entries = Object.entries(data)
    .filter(([, value]) => value > 0)
    .sort(([, a], [, b]) => b - a);

  const total = entries.reduce((sum, [, v]) => sum + v, 0);
  const maxValue = Math.max(...entries.map(([, v]) => v), 1);

  // Pad data so inner radius isn't zero
  const chartData = entries.map(([key, value], index) => ({
    name: LABEL_MAP[key] || key,
    key,
    value,
    fill: colors[key] || DEFAULT_COLORS[key] || "#C4A77D",
    percent: total > 0 ? Math.round((value / total) * 100) : 0,
    index,
  }));

  // Add a dummy entry for visual center spacing
  const paddedData = [{ name: "", key: "_center", value: maxValue * 0.15, fill: "transparent" }, ...chartData];

  const handleMouseEnter = (_: unknown, index: number) => {
    if (index > 0) setHoveredIndex(index - 1);
  };

  const handleMouseLeave = () => setHoveredIndex(null);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleMouseEnterAny = handleMouseEnter as any;

  const activeItem = hoveredIndex !== null ? chartData[hoveredIndex] : null;

  return (
    <div className={cn("relative w-full", className)}>
      {title && (
        <h3 className="text-sm font-medium text-latte-text-primary mb-3">{title}</h3>
      )}
      <div className="relative" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%"
            cy="50%"
            innerRadius="18%"
            outerRadius="90%"
            data={paddedData}
            startAngle={90}
            endAngle={-270}
            onMouseEnter={handleMouseEnterAny}
            onMouseLeave={handleMouseLeave}
          >
            <PolarAngleAxis
              type="number"
              domain={[0, maxValue * 1.1]}
              tick={false}
              axisLine={false}
            />
            <RadialBar
              background={{ fill: "rgba(128,128,128,0.06)", radius: 8 }}
              dataKey="value"
              cornerRadius={6}
              animationDuration={800}
              animationEasing="ease-out"
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload[0]) return null;
                const item = payload[0].payload;
                if (item.key === "_center") return null;
                return (
                  <div className="px-3 py-2 rounded-lg bg-latte-bg-secondary border border-latte-border text-xs shadow-latte-md">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className="w-2.5 h-2.5 rounded-full"
                        style={{ backgroundColor: item.fill }}
                      />
                      <span className="font-medium text-latte-text-primary">
                        {item.name}
                      </span>
                    </div>
                    <div className="text-latte-text-secondary">
                      数量: <span className="font-medium text-latte-text-primary">{item.value}</span>
                      <span className="mx-1">·</span>
                      占比: <span className="font-medium text-latte-text-primary">{item.percent}%</span>
                    </div>
                  </div>
                );
              }}
            />
          </RadialBarChart>
        </ResponsiveContainer>

        {/* Center info */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center">
            {activeItem ? (
              <>
                <p className="text-lg font-bold" style={{ color: activeItem.fill }}>
                  {activeItem.value}
                </p>
                <p className="text-xs text-latte-text-secondary mt-0.5">
                  {activeItem.name} · {activeItem.percent}%
                </p>
              </>
            ) : (
              <>
                <p className="text-2xl font-bold text-latte-text-primary">{total}</p>
                <p className="text-xs text-latte-text-secondary mt-0.5">总计</p>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-2 justify-center mt-2">
        {chartData.map((item, i) => (
          <button
            key={item.key}
            onMouseEnter={() => setHoveredIndex(i)}
            onMouseLeave={() => setHoveredIndex(null)}
            className={cn(
              "flex items-center gap-1.5 px-2 py-1 rounded-full text-xs transition-all",
              hoveredIndex === i
                ? "bg-latte-bg-secondary/90 text-latte-text-primary scale-105"
                : "bg-latte-bg-secondary/40 text-latte-text-secondary"
            )}
          >
            <span
              className="w-2 h-2 rounded-full"
              style={{
                backgroundColor: item.fill,
                boxShadow: hoveredIndex === i ? `0 0 8px ${item.fill}` : "none",
              }}
            />
            <span>{item.name}</span>
            <span className="font-medium">{item.value}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
