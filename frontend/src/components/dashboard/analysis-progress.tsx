"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Loader2, CheckCircle2, XCircle, GitCommit, RefreshCw, Database } from "lucide-react";
import { GlassCard } from "@/components/ui/glass-card";
import type { AnalysisProgress } from "@/types";

interface AnalysisProgressPanelProps {
  progress: AnalysisProgress | null;
}

const operationLabels: Record<string, string> = {
  clone: "克隆仓库",
  sync: "同步仓库",
  scan: "扫描提交",
};

const stepIcons: Record<string, React.ReactNode> = {
  started: <Loader2 size={14} className="animate-spin" />,
  fetching_git_log: <GitCommit size={14} />,
  parsing_git_log: <GitCommit size={14} />,
  saving_commits: <Database size={14} />,
  fetching: <RefreshCw size={14} className="animate-spin" />,
  checking_updates: <RefreshCw size={14} />,
  pulling: <RefreshCw size={14} className="animate-spin" />,
  cloning: <Loader2 size={14} className="animate-spin" />,
  clone_done: <CheckCircle2 size={14} />,
  skip_clone: <CheckCircle2 size={14} />,
  scanning: <GitCommit size={14} />,
  saving: <Database size={14} />,
  finished: <CheckCircle2 size={14} />,
  error: <XCircle size={14} />,
};

export function AnalysisProgressPanel({ progress }: AnalysisProgressPanelProps) {
  if (!progress) return null;

  const { operation, status, step, progress: current, total, message, result, error } = progress;
  const pct = total > 0 ? Math.min(100, Math.round((current / total) * 100)) : 0;

  const isRunning = status === "running";
  const isCompleted = status === "completed";
  const isFailed = status === "failed";

  const statusColor = isRunning
    ? "text-latte-info"
    : isCompleted
    ? "text-latte-success"
    : "text-latte-critical";

  const statusBg = isRunning
    ? "bg-latte-info/10 border-latte-info/30"
    : isCompleted
    ? "bg-latte-success/10 border-latte-success/30"
    : "bg-latte-critical/10 border-latte-critical/30";

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.25 }}
      >
        <GlassCard variant="status" status={status as "running" | "completed" | "failed"} className="p-4 mb-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className={statusColor}>
                {stepIcons[step] || <Loader2 size={14} className="animate-spin" />}
              </span>
              <span className="text-sm font-medium text-latte-text-primary">
                {operationLabels[operation] || operation}
              </span>
              <span
                className={cn(
                  "text-xs px-2 py-0.5 rounded-full border",
                  statusBg,
                  statusColor
                )}
              >
                {isRunning ? "进行中" : isCompleted ? "已完成" : "失败"}
              </span>
            </div>
            <span className="text-xs text-latte-text-tertiary tabular-nums">
              {pct}%
            </span>
          </div>

          {/* Progress bar */}
          <div className="h-1.5 bg-latte-bg-tertiary rounded-full overflow-hidden mb-3">
            <motion.div
              className={cn(
                "h-full rounded-full",
                isRunning && "bg-latte-info",
                isCompleted && "bg-latte-success",
                isFailed && "bg-latte-critical"
              )}
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 0.4, ease: "easeOut" }}
            />
          </div>

          {/* Message */}
          <p className="text-sm text-latte-text-secondary leading-relaxed">{message}</p>

          {/* Result summary */}
          {isCompleted && result && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="mt-3 pt-3 border-t border-latte-border/30 text-xs text-latte-text-tertiary space-y-1"
            >
              {result.scanned !== undefined && (
                <p>扫描提交: {result.scanned} 条</p>
              )}
              {result.saved !== undefined && (
                <p>新增入库: {result.saved} 条</p>
              )}
              {result.new_commits !== undefined && (
                <p>新提交: {result.new_commits} 个</p>
              )}
            </motion.div>
          )}

          {/* Error detail */}
          {isFailed && error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="mt-3 pt-3 border-t border-latte-border/30"
            >
              <p className="text-xs text-latte-critical">{error}</p>
            </motion.div>
          )}
        </GlassCard>
      </motion.div>
    </AnimatePresence>
  );
}

function cn(...classes: (string | false | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}
