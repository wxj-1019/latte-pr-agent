"use client";

import { cn } from "@/lib/utils";

interface ConfidenceRingProps {
  value: number;
  size?: number;
  strokeWidth?: number;
  className?: string;
}

export function ConfidenceRing({
  value,
  size = 40,
  strokeWidth = 4,
  className,
}: ConfidenceRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const progress = Math.min(Math.max(value, 0), 1);
  const offset = circumference - progress * circumference;

  let color = "var(--latte-confidence-low)";
  if (progress >= 0.9) color = "var(--latte-confidence-high)";
  else if (progress >= 0.7) color = "var(--latte-confidence-med)";

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--latte-bg-tertiary)"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{
            filter: `drop-shadow(0 0 4px ${color})`,
            transition: "stroke-dashoffset 0.8s cubic-bezier(0.16, 1, 0.3, 1)",
          }}
        />
      </svg>
      <span className="absolute text-[10px] font-semibold text-latte-text-secondary">
        {Math.round(progress * 100)}
      </span>
    </div>
  );
}
