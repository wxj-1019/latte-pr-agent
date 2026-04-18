"use client";

import { cn } from "@/lib/utils";

interface RealtimeIndicatorProps {
  status: "connecting" | "connected" | "disconnected";
  className?: string;
}

export function RealtimeIndicator({ status, className }: RealtimeIndicatorProps) {
  const config = {
    connecting: { label: "连接中", dotClass: "bg-amber-500 animate-pulse-slow" },
    connected: { label: "实时", dotClass: "bg-latte-success" },
    disconnected: { label: "离线", dotClass: "bg-latte-critical" },
  }[status];

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-latte-full",
        "bg-latte-bg-tertiary text-latte-text-secondary",
        className
      )}
      title={config.label}
    >
      <span className={cn("h-2 w-2 rounded-full", config.dotClass)} />
      {config.label}
    </div>
  );
}
