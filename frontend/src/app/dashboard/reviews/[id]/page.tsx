"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { useReviewDetail, useReviewFindings } from "@/hooks/use-reviews";
import { useSSE } from "@/hooks/use-sse";
import { FileTree } from "./components/file-tree";
import { DiffViewer } from "./components/diff-viewer";
import { FindingPanel } from "./components/finding-panel";
import { GlassCard } from "@/components/ui/glass-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import type { PRFile, ReviewFinding } from "@/types";

function LazyDiffViewer({
  file,
  findings,
  onLineClick,
  selectedLine,
}: {
  file: PRFile;
  findings: ReviewFinding[];
  onLineClick: (lineNum: number, filePath: string) => void;
  selectedLine?: { line: number; file: string };
}) {
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className="min-h-[100px]">
      {isVisible ? (
        <DiffViewer
          file={file}
          findings={findings}
          onLineClick={onLineClick}
          selectedLine={selectedLine}
        />
      ) : (
        <div className="h-32 rounded-latte-xl bg-latte-bg-secondary animate-pulse" />
      )}
    </div>
  );
}

export default function ReviewDetailPage() {
  const params = useParams();
  const reviewId = Number(params.id);
  const {
    review,
    isLoading: reviewLoading,
    error: reviewError,
    mutate: mutateReview,
  } = useReviewDetail(reviewId);
  const { findings, isLoading: findingsLoading, mutate: mutateFindings } = useReviewFindings(reviewId);
  const { subscribe } = useSSE();
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [selectedLine, setSelectedLine] = useState<{ line: number; file: string } | undefined>();

  const files = useMemo(() => review?.pr_files || [], [review?.pr_files]);

  useEffect(() => {
    if (files.length > 0 && !selectedFile) {
      setSelectedFile(files[0].file_path);
    }
  }, [files, selectedFile]);

  useEffect(() => {
    const unsubscribe = subscribe((update) => {
      if (update.review_id === reviewId) {
        mutateReview();
        mutateFindings();
      }
    });
    return unsubscribe;
  }, [subscribe, reviewId, mutateReview, mutateFindings]);

  const handleLineClick = (lineNum: number, filePath: string) => {
    setSelectedLine({ line: lineNum, file: filePath });
  };

  if (reviewLoading || findingsLoading) {
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

  if (reviewError || !review) {
    return (
      <div className="max-w-7xl mx-auto flex flex-col items-center justify-center h-[calc(100vh-8rem)] text-latte-text-tertiary">
        <p className="text-lg font-medium">加载审查失败</p>
        <p className="text-sm mt-1">{reviewError?.message || "审查记录未找到"}</p>
        <Link
          href="/dashboard/reviews"
          className="mt-4 text-latte-gold hover:underline text-sm"
        >
          返回审查列表
        </Link>
      </div>
    );
  }

  return (
    <motion.div
      className="max-w-7xl mx-auto h-[calc(100vh-8rem)]"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      <motion.div
        className="flex items-center gap-4 mb-6"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <Link
          href="/dashboard/reviews"
          className="p-2 rounded-latte-md text-latte-text-tertiary hover:text-latte-text-primary hover:bg-latte-bg-tertiary transition-colors"
        >
          <ArrowLeft size={18} />
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-display font-semibold tracking-tight text-latte-text-primary truncate">
            #{review.pr_number} {review.pr_title || "未命名 PR"}
            </h1>
          <p className="text-sm text-latte-text-tertiary">
            {review.repo_id} · {review.ai_model || "未知"}
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
              {({ low: "低", medium: "中", high: "高", critical: "严重" } as Record<string, string>)[review.risk_level] || review.risk_level}
            </Badge>
          )}
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100%-5rem)]">
        <motion.div
          className="lg:col-span-2 h-full"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
        >
          <GlassCard className="p-4 h-full overflow-hidden">
            <FileTree
              files={files}
              findings={findings}
              selectedFile={selectedFile}
              onSelectFile={setSelectedFile}
            />
          </GlassCard>
        </motion.div>

        <motion.div
          className="lg:col-span-7 h-full overflow-auto pr-2 space-y-6"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
        >
          {files.length > 0 ? (
            files.map((file) => (
              <LazyDiffViewer
                key={file.file_path}
                file={file}
                findings={findings}
                onLineClick={handleLineClick}
                selectedLine={selectedLine}
              />
            ))
          ) : (
            <div className="flex items-center justify-center h-64 text-latte-text-tertiary">
              暂无 diff 数据
            </div>
          )}
        </motion.div>

        <motion.div
          className="lg:col-span-3 h-full"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
        >
          <GlassCard className="p-4 h-full overflow-hidden">
            <FindingPanel findings={findings} selectedLine={selectedLine} />
          </GlassCard>
        </motion.div>
      </div>
    </motion.div>
  );
}
