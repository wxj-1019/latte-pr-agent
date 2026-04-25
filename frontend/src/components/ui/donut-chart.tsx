"use client";

import { useState, useCallback } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Sector } from "recharts";
import { cn } from "@/lib/utils";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const PieAny = Pie as any;

interface DonutChartProps {
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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const renderActiveShape = (props: any) => {
  const {
    cx, cy, innerRadius, outerRadius, startAngle, endAngle,
    fill, payload, percent, value,
  } = props;

  return (
    <g>
      <text x={cx} y={cy - 4} dy={0} textAnchor="middle" fill="var(--latte-text-primary)" className="text-xl font-bold">
        {value}
      </text>
      <text x={cx} y={cy + 16} dy={0} textAnchor="middle" fill="var(--latte-text-secondary)" className="text-xs">
        {LABEL_MAP[payload.key] || payload.key} · {Math.round((percent || 0) * 100)}%
      </text>
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={innerRadius}
        outerRadius={outerRadius + 6}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        cornerRadius={6}
      />
      <Sector
        cx={cx}
        cy={cy}
        startAngle={startAngle}
        endAngle={endAngle}
        innerRadius={outerRadius + 10}
        outerRadius={outerRadius + 14}
        fill={fill}
        opacity={0.3}
      />
    </g>
  );
};

export function DonutChart({
  data,
  colors = DEFAULT_COLORS,
  title,
  className,
  height = 280,
}: DonutChartProps) {
  const [activeIndex, setActiveIndex] = useState(0);

  const entries = Object.entries(data).filter(([, v]) => v > 0);
  const total = entries.reduce((sum, [, v]) => sum + v, 0);

  const chartData = entries.map(([key, value]) => ({
    key,
    name: LABEL_MAP[key] || key,
    value,
    fill: colors[key] || DEFAULT_COLORS[key] || "#C4A77D",
  }));

  const onPieEnter = useCallback((_: unknown, index: number) => {
    setActiveIndex(index);
  }, []);

  if (chartData.length === 0) {
    return (
      <div className={cn("relative w-full", className)}>
        {title && <h3 className="text-sm font-medium text-latte-text-primary mb-3">{title}</h3>}
        <div className="flex items-center justify-center h-64 text-latte-text-tertiary text-sm">
          暂无数据
        </div>
      </div>
    );
  }

  return (
    <div className={cn("relative w-full", className)}>
      {title && <h3 className="text-sm font-medium text-latte-text-primary mb-3">{title}</h3>}
      <div className="flex flex-col sm:flex-row items-center gap-4">
        <div className="w-full sm:w-1/2" style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <PieAny
                activeIndex={activeIndex}
                activeShape={renderActiveShape}
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius="60%"
                outerRadius="85%"
                dataKey="value"
                onMouseEnter={onPieEnter}
                stroke="none"
                cornerRadius={6}
                paddingAngle={3}
                animationBegin={0}
                animationDuration={600}
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </PieAny>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="w-full sm:w-1/2 space-y-2">
          {chartData.map((item, i) => {
            const percent = total > 0 ? Math.round((item.value / total) * 100) : 0;
            const isActive = activeIndex === i;
            return (
              <button
                key={item.key}
                onMouseEnter={() => setActiveIndex(i)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all text-left",
                  isActive
                    ? "bg-latte-bg-tertiary scale-[1.02]"
                    : "hover:bg-latte-bg-tertiary/50"
                )}
              >
                <span
                  className="w-3 h-3 rounded-full shrink-0"
                  style={{ backgroundColor: item.fill }}
                />
                <span className="flex-1 text-latte-text-primary">{item.name}</span>
                <span className="font-medium text-latte-text-primary">{item.value}</span>
                <span
                  className={cn(
                    "text-xs px-1.5 py-0.5 rounded-full transition-colors",
                    isActive ? "bg-latte-bg-secondary text-latte-text-primary" : "text-latte-text-tertiary"
                  )}
                >
                  {percent}%
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
