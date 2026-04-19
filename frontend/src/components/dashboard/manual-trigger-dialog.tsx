"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import {
  Play,
  Loader2,
  Download,
  X,
  GitBranch,
  GitPullRequest,
} from "lucide-react";

function parseRepoId(url: string): string {
  if (!url) return "";
  const clean = url.trim().replace(/\.git$/, "").replace(/\/$/, "");

  const sshMatch = clean.match(/^git@[^:]+:([^/]+\/[^/]+)$/);
  if (sshMatch) return sshMatch[1];

  try {
    const urlObj = new URL(clean);
    const path = urlObj.pathname.replace(/^\//, "");
    if (/^[^/]+\/[^/]+$/.test(path)) return path;
  } catch {
    // not a valid URL
  }

  if (/^[^/]+\/[^/]+$/.test(clean)) return clean;

  return "";
}

interface ManualTriggerDialogProps {
  open: boolean;
  onClose: () => void;
  defaultRepoId?: string;
  defaultPlatform?: "github" | "gitlab";
  onTriggered?: () => void;
}

export function ManualTriggerDialog({
  open,
  onClose,
  defaultRepoId,
  defaultPlatform = "github",
  onTriggered,
}: ManualTriggerDialogProps) {
  const { showToast } = useToast();
  const [platform, setPlatform] = useState<"github" | "gitlab">(defaultPlatform);
  const [repoUrl, setRepoUrl] = useState(defaultRepoId || "");
  const [prList, setPrList] = useState<
    Array<{
      number: number;
      title: string;
      author: string;
      head_branch: string;
      base_branch: string;
      updated_at: string | null;
      additions: number;
      deletions: number;
      changed_files: number;
    }>
  >([]);
  const [fetchingPRs, setFetchingPRs] = useState(false);
  const [triggeringPR, setTriggeringPR] = useState<number | null>(null);

  const repoId = parseRepoId(repoUrl);

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setPlatform(defaultPlatform);
      setRepoUrl(defaultRepoId || "");
      setPrList([]);
      setFetchingPRs(false);
      setTriggeringPR(null);
    }
  }, [open, defaultRepoId, defaultPlatform]);

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  async function handleFetchPRs() {
    if (!repoId) {
      showToast("请输入有效的仓库地址", "error");
      return;
    }
    setFetchingPRs(true);
    try {
      const result = await api.fetchPullRequests(repoId, platform);
      setPrList(result.pulls);
      if (result.pulls.length === 0) {
        showToast("该仓库没有打开的 Pull Request");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "未知错误";
      showToast("获取 PR 失败：" + message, "error");
    } finally {
      setFetchingPRs(false);
    }
  }

  async function handleTriggerReview(prNumber: number) {
    if (!repoId) return;
    setTriggeringPR(prNumber);
    try {
      const result = await api.triggerManualReview(repoId, prNumber, platform);
      showToast(`审查已触发！Review #${result.review_id}`);
      onTriggered?.();
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : "未知错误";
      showToast("触发审查失败：" + message, "error");
    } finally {
      setTriggeringPR(null);
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="latte-glass p-6 rounded-latte-xl max-w-lg w-full mx-4 max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <GitPullRequest size={18} className="text-latte-gold" />
                <h3 className="text-lg font-medium text-latte-text-primary">
                  手动触发审查
                </h3>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-latte-md text-latte-text-tertiary hover:text-latte-text-primary hover:bg-latte-bg-tertiary transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            {/* Platform */}
            <div className="mb-4">
              <label className="text-xs font-medium text-latte-text-secondary mb-2 block">
                平台
              </label>
              <div className="flex gap-3">
                {(["github", "gitlab"] as const).map((p) => (
                  <button
                    key={p}
                    onClick={() => setPlatform(p)}
                    className={`flex-1 py-2.5 px-4 rounded-latte-lg text-sm font-medium transition-all border ${
                      platform === p
                        ? "bg-latte-gold/10 border-latte-gold/30 text-latte-gold"
                        : "bg-latte-bg-tertiary border-transparent text-latte-text-tertiary hover:text-latte-text-secondary"
                    }`}
                  >
                    {p === "github" ? "GitHub" : "GitLab"}
                  </button>
                ))}
              </div>
            </div>

            {/* Repo input */}
            <div className="mb-4">
              <label className="text-xs font-medium text-latte-text-secondary mb-2 block">
                仓库地址
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  placeholder={`https://${platform}.com/owner/repository`}
                  className="flex-1 h-10 px-4 rounded-latte-lg bg-latte-bg-tertiary border border-transparent focus:border-latte-gold/50 focus:ring-2 focus:ring-latte-gold/20 text-sm text-latte-text-primary placeholder:text-latte-text-muted outline-none transition-all"
                />
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleFetchPRs}
                  disabled={fetchingPRs || !repoId}
                >
                  {fetchingPRs ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Download size={14} />
                  )}
                  获取 PR
                </Button>
              </div>
              {repoId && repoId !== repoUrl && (
                <p className="text-xs text-latte-gold mt-1.5">
                  检测到：<span className="font-medium">{repoId}</span>
                </p>
              )}
            </div>

            {/* PR list */}
            {prList.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-latte-text-muted mb-1">
                  点击 PR 触发审查
                </p>
                {prList.map((pr) => (
                  <button
                    key={pr.number}
                    onClick={() => handleTriggerReview(pr.number)}
                    disabled={triggeringPR === pr.number}
                    className="w-full p-3 rounded-latte-lg bg-latte-bg-tertiary/50 border border-latte-text-primary/5 hover:border-latte-gold/20 hover:bg-latte-bg-tertiary transition-all text-left flex items-center gap-3 disabled:opacity-50"
                  >
                    <div className="shrink-0 w-8 h-8 rounded-full bg-latte-gold/10 flex items-center justify-center">
                      {triggeringPR === pr.number ? (
                        <Loader2 size={14} className="animate-spin text-latte-gold" />
                      ) : (
                        <Play size={14} className="text-latte-gold" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-latte-text-primary truncate">
                        #{pr.number} {pr.title}
                      </p>
                      <div className="flex items-center gap-3 mt-0.5">
                        <span className="text-xs text-latte-text-muted">
                          {pr.author}
                        </span>
                        <span className="text-xs text-latte-success">
                          +{pr.additions}
                        </span>
                        <span className="text-xs text-latte-critical">
                          -{pr.deletions}
                        </span>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}

            {prList.length === 0 && !fetchingPRs && (
              <div className="text-center py-8 text-latte-text-muted text-sm">
                <GitBranch size={32} className="mx-auto mb-3 opacity-30" />
                <p>输入仓库地址并点击「获取 PR」</p>
                <p className="text-xs mt-1 opacity-60">
                  无需配置 Webhook 即可手动触发审查
                </p>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
