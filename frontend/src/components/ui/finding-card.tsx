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
import type { ReviewFinding } from "@/types";
import { ChevronDown, ChevronUp, MessageSquare } from "lucide-react";

interface FindingCardProps {
  finding: ReviewFinding;
  defaultExpanded?: boolean;
}

export function FindingCard({ finding, defaultExpanded = false }: FindingCardProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [submitting, setSubmitting] = useState(false);
  const { showToast } = useToast();

  async function handleFeedback(findingId: number) {
    setSubmitting(true);
    try {
      await api.submitFeedback(findingId, true, "");
      showToast("Marked as false positive");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unknown error";
      showToast("Failed to submit feedback: " + message, "error");
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
              Line {finding.line_number ?? "-"}
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
                  <span className="font-medium text-latte-gold">Suggestion:</span>{" "}
                  {escapeHtml(finding.suggestion)}
                </div>
              )}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <ConfidenceRing value={finding.confidence ?? 0} size={40} />
                  <div className="text-xs text-latte-text-muted">
                    <p>Confidence</p>
                    <p className="text-latte-text-secondary">
                      {finding.ai_model || "unknown"}
                    </p>
                  </div>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handleFeedback(finding.id)}
                  disabled={submitting}
                >
                  <MessageSquare size={14} />
                  False Positive
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
