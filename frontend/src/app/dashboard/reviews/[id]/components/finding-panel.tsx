"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { ConfidenceRing } from "@/components/ui/confidence-ring";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { ReviewFinding } from "@/types";
import { ChevronDown, ChevronUp, MessageSquare } from "lucide-react";

interface FindingPanelProps {
  findings: ReviewFinding[];
  selectedLine?: { line: number; file: string };
}

export function FindingPanel({ findings, selectedLine }: FindingPanelProps) {
  const [expandedId, setExpandedId] = useState<number | null>(findings[0]?.id ?? null);
  const [submittingId, setSubmittingId] = useState<number | null>(null);

  async function handleFeedback(findingId: number) {
    setSubmittingId(findingId);
    try {
      const res = await fetch(`/api/findings/${findingId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_false_positive: true, comment: "" }),
      });
      if (res.ok) {
        alert("Marked as false positive");
      }
    } finally {
      setSubmittingId(null);
    }
  }

  const filteredFindings = selectedLine
    ? findings.filter(
        (f) => f.file_path === selectedLine.file && f.line_number === selectedLine.line
      )
    : findings;

  return (
    <div className="h-full overflow-auto pr-2">
      <h3 className="text-sm font-semibold text-latte-text-primary mb-3 px-1">
        Findings {filteredFindings.length > 0 && `(${filteredFindings.length})`}
      </h3>
      <div className="space-y-3">
        {filteredFindings.map((finding) => {
          const isExpanded = expandedId === finding.id;
          return (
            <motion.div
              key={finding.id}
              layout
              className={cn(
                "rounded-latte-lg border transition-colors",
                isExpanded
                  ? "bg-latte-bg-secondary border-latte-gold/20"
                  : "bg-latte-bg-tertiary/50 border-transparent hover:border-latte-text-primary/5"
              )}
            >
              <button
                onClick={() => setExpandedId(isExpanded ? null : finding.id)}
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
                    {finding.description}
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
                        {finding.description}
                      </div>
                      {finding.suggestion && (
                        <div className="rounded-latte-md bg-latte-bg-tertiary p-3 text-sm text-latte-text-secondary">
                          <span className="font-medium text-latte-gold">Suggestion:</span>{" "}
                          {finding.suggestion}
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
                          disabled={submittingId === finding.id}
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
        })}
        {filteredFindings.length === 0 && (
          <div className="text-sm text-latte-text-tertiary py-8 text-center">
            {selectedLine ? "No findings for this line" : "No findings available"}
          </div>
        )}
      </div>
    </div>
  );
}
