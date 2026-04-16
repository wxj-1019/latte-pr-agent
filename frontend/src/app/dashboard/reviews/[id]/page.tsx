"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useReviewDetail, useReviewFindings } from "@/hooks/use-reviews";
import { FileTree } from "./components/file-tree";
import { DiffViewer } from "./components/diff-viewer";
import { FindingPanel } from "./components/finding-panel";
import { GlassCard } from "@/components/ui/glass-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { Badge } from "@/components/ui/badge";
import { FadeInUp } from "@/components/motion/fade-in-up";
import { mockFiles } from "@/lib/mock-data";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function ReviewDetailPage() {
  const params = useParams();
  const reviewId = Number(params.id);
  const { review, isLoading: reviewLoading } = useReviewDetail(reviewId);
  const { findings, isLoading: findingsLoading } = useReviewFindings(reviewId);
  const [selectedFile, setSelectedFile] = useState<string>(mockFiles.find((f) => f.review_id === reviewId)?.file_path || "");
  const [selectedLine, setSelectedLine] = useState<{ line: number; file: string } | undefined>();

  const files = mockFiles.filter((f) => f.review_id === reviewId);

  const handleLineClick = (lineNum: number, filePath: string) => {
    setSelectedLine({ line: lineNum, file: filePath });
  };

  if (reviewLoading || findingsLoading || !review) {
    return (
      <div className="max-w-7xl mx-auto space-y-4">
        <div className="h-8 w-48 bg-latte-bg-secondary rounded animate-pulse" />
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-2 h-96 bg-latte-bg-secondary rounded-latte-xl animate-pulse" />
          <div className="lg:col-span-7 h-96 bg-latte-bg-secondary rounded-latte-xl animate-pulse" />
          <div className="lg:col-span-3 h-96 bg-latte-bg-secondary rounded-latte-xl animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto h-[calc(100vh-8rem)]">
      <FadeInUp>
        <div className="flex items-center gap-4 mb-6">
          <Link
            href="/dashboard/reviews"
            className="p-2 rounded-latte-md text-latte-text-tertiary hover:text-latte-text-primary hover:bg-latte-bg-tertiary transition-colors"
          >
            <ArrowLeft size={18} />
          </Link>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-display font-semibold tracking-tight text-latte-text-primary truncate">
              #{review.pr_number} {review.pr_title || "Untitled PR"}
            </h1>
            <p className="text-sm text-latte-text-tertiary">
              {review.repo_id} · {review.ai_model || "unknown"}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status={review.status} />
            {review.risk_level && review.risk_level !== "low" && (
              <Badge
                variant={
                  review.risk_level === "critical"
                    ? "critical"
                    : review.risk_level === "high"
                    ? "warning"
                    : "info"
                }
                dot
              >
                {review.risk_level}
              </Badge>
            )}
          </div>
        </div>
      </FadeInUp>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100%-5rem)]">
        <GlassCard className="lg:col-span-2 p-4 h-full overflow-hidden">
          <FileTree
            files={files}
            findings={findings}
            selectedFile={selectedFile}
            onSelectFile={setSelectedFile}
          />
        </GlassCard>

        <div className="lg:col-span-7 h-full overflow-auto pr-2 space-y-6">
          {files.length > 0 ? (
            files.map((file) => (
              <DiffViewer
                key={file.file_path}
                file={file}
                findings={findings}
                onLineClick={handleLineClick}
                selectedLine={selectedLine}
              />
            ))
          ) : (
            <div className="flex items-center justify-center h-64 text-latte-text-tertiary">
              No diff available
            </div>
          )}
        </div>

        <GlassCard className="lg:col-span-3 p-4 h-full overflow-hidden">
          <FindingPanel findings={findings} selectedLine={selectedLine} />
        </GlassCard>
      </div>
    </div>
  );
}
