"use client";

import { useState } from "react";
import { FindingCard } from "@/components/ui/finding-card";
import type { ReviewFinding } from "@/types";

interface FindingPanelProps {
  findings: ReviewFinding[];
  selectedLine?: { line: number; file: string };
}

export function FindingPanel({ findings, selectedLine }: FindingPanelProps) {
  const [expandedId, setExpandedId] = useState<number | null>(findings[0]?.id ?? null);

  const filteredFindings = selectedLine
    ? findings.filter(
        (f) => f.file_path === selectedLine.file && f.line_number === selectedLine.line
      )
    : findings;

  return (
    <div className="h-full overflow-auto pr-2">
      <h3 className="text-sm font-semibold text-latte-text-primary mb-3 px-1">
        发现 {filteredFindings.length > 0 && `(${filteredFindings.length})`}
      </h3>
      <div className="space-y-3" onMouseEnter={() => {}}>
        {filteredFindings.map((finding) => (
          <div
            key={finding.id}
            onClick={() => setExpandedId(expandedId === finding.id ? null : finding.id)}
            className="cursor-pointer"
          >
            <FindingCard finding={finding} defaultExpanded={expandedId === finding.id} />
          </div>
        ))}
        {filteredFindings.length === 0 && (
          <div className="text-sm text-latte-text-tertiary py-8 text-center">
            {selectedLine ? "此行无发现" : "暂无可用的发现"}
          </div>
        )}
      </div>
    </div>
  );
}
