"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { escapeHtml } from "@/lib/security";
import { ConfidenceRing } from "@/components/ui/confidence-ring";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { ReviewFinding } from "@/types";
import { ChevronDown, ChevronUp, MessageSquare } from "lucide-react";

interface FindingCardProps {
  finding: ReviewFinding;
  defaultExpanded?: boolean;
}

export function FindingCard({ finding, defaultExpanded = false }: FindingCardProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [submitting, setSubmitting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const { showToast } = useToast();

  async function doSubmitFeedback() {
    setConfirmOpen(false);
    setSubmitting(true);
    try {
      await api.submitFeedback(finding.id, true, "");
      showToast("已标记为误报");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "未知错误";
      showToast("提交反馈失败: " + message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <motion.div
      layout
      className={cn(
        "rounded-latte-lg border transition-colors",
        isExpanded
          ? "bg-latte-bg-secondary border-latte-gold/20"
          : "bg-latte-bg-tertiary/50 border-transparent hover:border-latte-text-primary/5"
      )}
    >
      <button
        onClick={() => setIsExpanded((v) => !v)}
        className="w-full p-4 text-left flex items-start justify-between gap-3"
      >
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge
              variant={
                finding.severity === "critical"
                  ? "critical"
                  : finding.severity === "warning"
                  ? "warning"
                  : "info"
              }
              dot
            >
              {finding.severity}
            </Badge>
            <span className="text-xs text-latte-text-muted">
              第 {finding.line_number ?? "-"} 行
            </span>
          </div>
          <p className="text-sm text-latte-text-secondary mt-2 truncate">
            {escapeHtml(finding.description)}
          </p>
        </div>
        <div className="shrink-0 pt-0.5">
          {isExpanded ? (
            <ChevronUp size={16} className="text-latte-text-tertiary" />
          ) : (
            <ChevronDown size={16} className="text-latte-text-tertiary" />
          )}
        </div>
      </button>
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-4">
              <div className="text-sm text-latte-text-primary leading-relaxed">
                {escapeHtml(finding.description)}
              </div>
              {finding.suggestion && (
                <div className="rounded-latte-md bg-latte-bg-tertiary p-3 text-sm text-latte-text-secondary">
                  <span className="font-medium text-latte-gold">建议:</span>{" "}
                  {escapeHtml(finding.suggestion)}
                </div>
              )}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <ConfidenceRing value={finding.confidence ?? 0} size={40} />
                  <div className="text-xs text-latte-text-muted">
                    <p>置信度</p>
                    <p className="text-latte-text-secondary">
                      {finding.ai_model || "未知"}
                    </p>
                  </div>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setConfirmOpen(true)}
                  disabled={submitting}
                >
                  <MessageSquare size={14} />
                  误报
                </Button>

                <ConfirmDialog
                  open={confirmOpen}
                  title="标记为误报"
                  description={`确定将第 ${finding.line_number ?? "-"} 行的发现标记为误报吗？此操作将帮助改进审查质量。`}
                  onConfirm={doSubmitFeedback}
                  onCancel={() => setConfirmOpen(false)}
                  confirmText="确认标记"
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
