"use client";

import { cn } from "@/lib/utils";

type StatusType = "pending" | "running" | "completed" | "failed" | "skipped";

interface StatusBadgeProps {
  status: StatusType;
  className?: string;
}

const statusConfig: Record<StatusType, { label: string; dotClass: string }> = {
  pending: {
    label: "pending",
    dotClass: "bg-amber-500 animate-pulse-slow",
  },
  running: {
    label: "running",
    dotClass: "bg-blue-500",
  },
  completed: {
    label: "completed",
    dotClass: "bg-latte-success",
  },
  failed: {
    label: "failed",
    dotClass: "bg-latte-critical",
  },
  skipped: {
    label: "skipped",
    dotClass: "bg-latte-text-muted",
  },
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 px-2.5 py-1 text-xs font-semibold rounded-latte-sm",
        "bg-latte-bg-tertiary text-latte-text-secondary",
        className
      )}
    >
      {status === "running" ? (
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
        </span>
      ) : (
        <span className={cn("h-1.5 w-1.5 rounded-full", config.dotClass)} />
      )}
      {config.label}
    </span>
  );
}
