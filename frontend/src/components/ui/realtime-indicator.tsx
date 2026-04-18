"use client";

import { cn } from "@/lib/utils";

interface RealtimeIndicatorProps {
  status: "connecting" | "connected" | "disconnected" | "reconnecting";
  className?: string;
  onClick?: () => void;
}

export function RealtimeIndicator({ status, className, onClick }: RealtimeIndicatorProps) {
  const config = {
    connecting: { label: "连接中", dotClass: "bg-amber-500 animate-pulse-slow" },
    connected: { label: "实时", dotClass: "bg-latte-success" },
    disconnected: { label: "离线", dotClass: "bg-latte-critical" },
    reconnecting: { label: "重连中", dotClass: "bg-amber-500 animate-pulse-slow" },
  }[status];

  const isClickable = status !== "connected" && !!onClick;

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-latte-full",
        "bg-latte-bg-tertiary text-latte-text-secondary",
        isClickable && "cursor-pointer hover:bg-latte-bg-secondary transition-colors",
        className
      )}
      title={isClickable ? `${config.label} — 点击重连` : config.label}
      onClick={isClickable ? onClick : undefined}
    >
      <span className={cn("h-2 w-2 rounded-full", config.dotClass)} />
      {config.label}
    </div>
  );
}
