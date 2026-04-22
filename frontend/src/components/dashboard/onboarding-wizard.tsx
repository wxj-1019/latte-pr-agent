"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { FadeInUp } from "@/components/motion/fade-in-up";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import {
  Rocket,
  GitBranch,
  Settings,
  Webhook,
  ChevronRight,
  ChevronLeft,
  Check,
  Copy,
  ExternalLink,
  Sparkles,
  ShieldCheck,
  AlertTriangle,
  XCircle,
  Loader2,
  RefreshCw,
  Download,
  Play,
} from "lucide-react";

interface OnboardingWizardProps {
  onComplete: () => void;
}

const LOCAL_STORAGE_KEY = "latte_onboarding_state";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

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

const STEPS = [
  { icon: GitBranch, title: "注册仓库", desc: "添加你的仓库" },
  { icon: Settings, title: "配置审查", desc: "自定义审查设置" },
  { icon: ShieldCheck, title: "验证配置", desc: "测试配置" },
  { icon: Webhook, title: "Webhook (可选)", desc: "自动触发" },
  { icon: Sparkles, title: "全部完成！", desc: "开始审查" },
];

interface CheckItem {
  name: string;
  status: "ok" | "error" | "warning";
  message: string;
}

const CHECK_LABELS: Record<string, string> = {
  github_token: "GitHub 连接",
  gitlab_token: "GitLab 连接",
  webhook_secret: "Webhook 密钥",
  llm_api_key: "AI 模型密钥",
  database: "数据库",
  redis: "Redis 缓存",
};

function CheckIcon({ status }: { status: string }) {
  if (status === "ok")
    return (
      <div className="w-6 h-6 rounded-full bg-latte-success/20 flex items-center justify-center shrink-0">
        <Check size={14} className="text-latte-success" />
      </div>
    );
  if (status === "warning")
    return (
      <div className="w-6 h-6 rounded-full bg-latte-warning/20 flex items-center justify-center shrink-0">
        <AlertTriangle size={14} className="text-latte-warning" />
      </div>
    );
  return (
    <div className="w-6 h-6 rounded-full bg-latte-critical/20 flex items-center justify-center shrink-0">
      <XCircle size={14} className="text-latte-critical" />
    </div>
  );
}

export function OnboardingWizard({ onComplete }: OnboardingWizardProps) {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [platform, setPlatform] = useState<"github" | "gitlab">("github");
  const [repoUrl, setRepoUrl] = useState("");
  const [language, setLanguage] = useState("python");
  const [aiModel, setAiModel] = useState("deepseek-chat");
  const [saving, setSaving] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<{
    passed: boolean;
    has_warning: boolean;
    checks: CheckItem[];
    summary: string;
  } | null>(null);
  const { showToast } = useToast();

  const repoId = parseRepoId(repoUrl);

  useEffect(() => {
    const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (saved) {
      try {
        const state = JSON.parse(saved);
        if (typeof state.step === "number") setStep(state.step);
        if (state.platform) setPlatform(state.platform);
        if (state.repoUrl) setRepoUrl(state.repoUrl);
        if (state.language) setLanguage(state.language);
        if (state.aiModel) setAiModel(state.aiModel);
      } catch {
        // ignore invalid saved state
      }
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(
      LOCAL_STORAGE_KEY,
      JSON.stringify({ step, platform, repoUrl, language, aiModel })
    );
  }, [step, platform, repoUrl, language, aiModel]);

  async function handleSaveConfig() {
    if (!repoId || repoId === repoUrl) {
      showToast("请输入有效的仓库 URL", "error");
      return;
    }
    setSaving(true);
    try {
      await api.updateProjectConfig(repoId, {
        config_json: {
          review_config: {
            language,
            context_analysis: {
              enabled: true,
              dependency_depth: 2,
              historical_bug_check: true,
              api_contract_detection: true,
            },
            ai_model: {
              primary: aiModel,
              fallback: aiModel === "deepseek-chat" ? "deepseek-reasoner" : "deepseek-chat",
            },
            dual_model_verification: {
              enabled: true,
              trigger_on: ["critical", "warning"],
            },
          },
        },
      });
      showToast("配置已保存！");
      setStep(2);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "未知错误";
      showToast("保存失败：" + message, "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleVerify() {
    if (!repoId) return;
    setVerifying(true);
    setVerifyResult(null);
    try {
      const result = await api.verifyProjectConfig(repoId, platform);
      setVerifyResult({
        ...result,
        checks: result.checks.map((c) => ({
          ...c,
          status: c.status as "ok" | "error" | "warning",
        })),
      });
      if (result.passed) {
        showToast(result.has_warning ? "通过，但存在警告" : "所有检查通过！");
      } else {
        showToast("部分检查失败。请修复以下问题。", "error");
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "未知错误";
      showToast("验证失败：" + message, "error");
    } finally {
      setVerifying(false);
    }
  }

  async function copyToClipboard(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      showToast("已复制到剪贴板");
    } catch {
      showToast("复制失败，请手动复制", "error");
    }
  }

  const [prList, setPrList] = useState<Array<{ number: number; title: string; author: string; head_branch: string; base_branch: string; updated_at: string | null; additions: number; deletions: number; changed_files: number }>>([]);
  const [fetchingPRs, setFetchingPRs] = useState(false);
  const [triggeringPR, setTriggeringPR] = useState<number | null>(null);

  async function handleFetchPRs() {
    if (!repoId) return;
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
      onComplete();
    } catch (err) {
      const message = err instanceof Error ? err.message : "未知错误";
      showToast("触发审查失败：" + message, "error");
    } finally {
      setTriggeringPR(null);
    }
  }

  const webhookUrl = `${API_BASE}/webhook/${platform}`;

  return (
    <div className="max-w-3xl mx-auto">
      <FadeInUp>
        <div className="text-center mb-8">
          <motion.div
            className="inline-flex items-center justify-center w-16 h-16 rounded-latte-2xl bg-latte-gold/10 mb-4"
            animate={{ rotate: [0, 5, -5, 0] }}
            transition={{ duration: 2, repeat: Infinity, repeatDelay: 3 }}
          >
            <Rocket className="w-8 h-8 text-latte-gold" />
          </motion.div>
          <h2 className="text-2xl font-display font-semibold text-latte-text-primary">
            欢迎使用 Latte PR Agent
          </h2>
          <p className="text-sm text-latte-text-tertiary mt-2 max-w-md mx-auto">
            只需几步即可设置你的第一个项目，开始自动化 AI 代码审查
          </p>
        </div>
      </FadeInUp>

      <div className="flex items-center justify-center gap-1.5 mb-8">
        {STEPS.map((s, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium transition-all duration-300 ${
                i < step
                  ? "bg-latte-gold text-latte-bg-primary"
                  : i === step
                  ? "bg-latte-gold/20 text-latte-gold ring-2 ring-latte-gold/30"
                  : "bg-latte-bg-tertiary text-latte-text-muted"
              }`}
            >
              {i < step ? <Check size={12} /> : i + 1}
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={`w-6 h-0.5 transition-colors duration-300 ${
                  i < step ? "bg-latte-gold" : "bg-latte-bg-tertiary"
                }`}
              />
            )}
          </div>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        >
          {step === 0 && (
            <GlassCard className="p-8" variant="elevated">
              <h3 className="text-lg font-medium text-latte-text-primary mb-1">
                注册你的仓库
              </h3>
              <p className="text-sm text-latte-text-tertiary mb-6">
                输入你的项目仓库 URL 以开始
              </p>

              <div className="space-y-5">
                <div>
                  <label className="text-xs font-medium text-latte-text-secondary mb-2 block">
                    平台
                  </label>
                  <div className="flex gap-3">
                    {(["github", "gitlab"] as const).map((p) => (
                      <button
                        key={p}
                        onClick={() => setPlatform(p)}
                        className={`flex-1 py-3 px-4 rounded-latte-lg text-sm font-medium transition-all border ${
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

                <div>
                  <label className="text-xs font-medium text-latte-text-secondary mb-2 block">
                    仓库 URL
                  </label>
                  <input
                    type="text"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    placeholder={`https://${platform}.com/owner/repository`}
                    className="w-full h-11 px-4 rounded-latte-lg bg-latte-bg-tertiary border border-transparent focus:border-latte-gold/50 focus:ring-2 focus:ring-latte-gold/20 text-sm text-latte-text-primary placeholder:text-latte-text-muted outline-none transition-all"
                  />
                  {repoId && repoId !== repoUrl && (
                    <p className="text-xs text-latte-gold mt-1.5">
                      检测到：<span className="font-medium">{repoId}</span>
                    </p>
                  )}
                </div>

                <div>
                  <label className="text-xs font-medium text-latte-text-secondary mb-2 block">
                    主要语言
                  </label>
                  <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="w-full h-11 px-4 rounded-latte-lg bg-latte-bg-tertiary border border-transparent focus:border-latte-gold/50 text-sm text-latte-text-primary outline-none transition-all appearance-none cursor-pointer"
                  >
                    <option value="python">Python</option>
                    <option value="javascript">JavaScript</option>
                    <option value="typescript">TypeScript</option>
                    <option value="go">Go</option>
                    <option value="java">Java</option>
                    <option value="rust">Rust</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end mt-8">
                <Button
                  variant="primary"
                  onClick={() => setStep(1)}
                  disabled={!repoId || repoId === repoUrl}
                >
                  继续
                  <ChevronRight size={16} />
                </Button>
              </div>
            </GlassCard>
          )}

          {step === 1 && (
            <GlassCard className="p-8" variant="elevated">
              <h3 className="text-lg font-medium text-latte-text-primary mb-1">
                配置审查设置
              </h3>
              <p className="text-sm text-latte-text-tertiary mb-6">
                自定义 Latte 如何审查你的代码
              </p>

              <div className="space-y-5">
                <div>
                  <label className="text-xs font-medium text-latte-text-secondary mb-2 block">
                    AI 审查模型
                  </label>
                  <select
                    value={aiModel}
                    onChange={(e) => setAiModel(e.target.value)}
                    className="w-full h-11 px-4 rounded-latte-lg bg-latte-bg-tertiary border border-transparent focus:border-latte-gold/50 text-sm text-latte-text-primary outline-none transition-all appearance-none cursor-pointer"
                  >
                    <option value="deepseek-chat">DeepSeek Chat（推荐）</option>
                    <option value="deepseek-reasoner">DeepSeek Reasoner（深度分析）</option>
                    <option value="claude-3-sonnet">Claude 3 Sonnet</option>
                    <option value="qwen-coder-plus">Qwen Coder Plus</option>
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {[
                    { label: "上下文分析", desc: "AST + 依赖图" },
                    { label: "静态分析", desc: "Semgrep 安全扫描" },
                    { label: "双模型审查", desc: "关键发现复核" },
                    { label: "Bug RAG", desc: "历史 Bug 模式" },
                  ].map((feature) => (
                    <div
                      key={feature.label}
                      className="p-3 rounded-latte-lg bg-latte-bg-tertiary/50 border border-latte-gold/10"
                    >
                      <div className="flex items-center gap-2">
                        <div className="w-5 h-5 rounded-full bg-latte-gold/20 flex items-center justify-center">
                          <Check size={12} className="text-latte-gold" />
                        </div>
                        <span className="text-sm font-medium text-latte-text-primary">
                          {feature.label}
                        </span>
                      </div>
                      <p className="text-xs text-latte-text-muted mt-1 ml-7">{feature.desc}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex justify-between mt-8">
                <Button variant="ghost" onClick={() => setStep(0)}>
                  <ChevronLeft size={16} />
                  返回
                </Button>
                <Button variant="primary" onClick={handleSaveConfig} disabled={saving}>
                  {saving ? "保存中..." : "保存并继续"}
                  <ChevronRight size={16} />
                </Button>
              </div>
            </GlassCard>
          )}

          {step === 2 && (
            <GlassCard className="p-8" variant="elevated">
              <h3 className="text-lg font-medium text-latte-text-primary mb-1">
                验证配置
              </h3>
              <p className="text-sm text-latte-text-tertiary mb-6">
                运行健康检查，确保所有配置正确
              </p>

              <div className="space-y-4">
                <button
                  onClick={handleVerify}
                  disabled={verifying}
                  className="w-full py-4 rounded-latte-lg bg-latte-gold/10 border border-latte-gold/20 text-latte-gold font-medium text-sm hover:bg-latte-gold/15 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {verifying ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      正在运行检查...
                    </>
                  ) : verifyResult ? (
                    <>
                      <RefreshCw size={16} />
                      重新验证
                    </>
                  ) : (
                    <>
                      <ShieldCheck size={16} />
                      开始验证
                    </>
                  )}
                </button>

                {verifyResult && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="space-y-2"
                  >
                    <div
                      className={`p-4 rounded-latte-lg border ${
                        verifyResult.passed
                          ? verifyResult.has_warning
                            ? "bg-latte-warning/5 border-latte-warning/20"
                            : "bg-latte-success/5 border-latte-success/20"
                          : "bg-latte-critical/5 border-latte-critical/20"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        {verifyResult.passed ? (
                          <Check size={16} className="text-latte-success" />
                        ) : (
                          <XCircle size={16} className="text-latte-critical" />
                        )}
                        <span className="text-sm font-medium text-latte-text-primary">
                          {verifyResult.summary}
                        </span>
                      </div>
                      {!verifyResult.passed && (
                        <p className="text-xs text-latte-text-tertiary ml-6">
                          修复以下失败的检查，然后返回更新你的配置
                        </p>
                      )}
                    </div>

                    <div className="space-y-1.5">
                      {verifyResult.checks.map((check) => (
                        <div
                          key={check.name}
                          className="flex items-start gap-3 p-3 rounded-latte-lg bg-latte-bg-tertiary/50"
                        >
                          <CheckIcon status={check.status} />
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-latte-text-primary">
                              {CHECK_LABELS[check.name] || check.name}
                            </p>
                            <p className="text-xs text-latte-text-tertiary mt-0.5">
                              {check.message}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </div>

              <div className="flex justify-between mt-8">
                <Button variant="ghost" onClick={() => setStep(1)}>
                  <ChevronLeft size={16} />
                  返回编辑配置
                </Button>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => setStep(4)}
                    disabled={!verifyResult || !verifyResult.passed}
                  >
                    跳过，稍后配置
                    <ChevronRight size={16} />
                  </Button>
                  <Button
                    variant="primary"
                    onClick={() => setStep(3)}
                    disabled={!verifyResult || !verifyResult.passed}
                  >
                    配置 Webhook
                    <ChevronRight size={16} />
                  </Button>
                </div>
              </div>
            </GlassCard>
          )}

          {step === 3 && (
            <GlassCard className="p-8" variant="elevated">
              <h3 className="text-lg font-medium text-latte-text-primary mb-1">
                设置 Webhook
              </h3>
              <p className="text-sm text-latte-text-tertiary mb-6">
                添加 Webhook 到你的 {platform === "github" ? "GitHub" : "GitLab"} 仓库
              </p>

              <div className="space-y-4">
                <div className="p-4 rounded-latte-lg bg-latte-bg-tertiary/50 border border-latte-text-primary/5">
                  <p className="text-xs text-latte-text-muted mb-2">步骤 1：复制 Webhook URL</p>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 text-sm text-latte-gold bg-latte-bg-primary/50 px-3 py-2 rounded-latte-md truncate">
                      {webhookUrl}
                    </code>
                    <button
                      onClick={() => copyToClipboard(webhookUrl)}
                      className="shrink-0 p-2 rounded-latte-md hover:bg-latte-bg-tertiary text-latte-text-tertiary hover:text-latte-text-primary transition-colors"
                      title="复制"
                    >
                      <Copy size={16} />
                    </button>
                  </div>
                </div>

                <div className="p-4 rounded-latte-lg bg-latte-bg-tertiary/50 border border-latte-text-primary/5">
                  <p className="text-xs text-latte-text-muted mb-2">
                    步骤 2：在你的仓库中配置
                  </p>
                  {platform === "github" ? (
                    <ol className="text-sm text-latte-text-secondary space-y-1.5 list-decimal list-inside">
                      <li>
                        打开仓库 → <strong>Settings</strong> → <strong>Webhooks</strong> →{" "}
                        <strong>Add webhook</strong>
                      </li>
                      <li>
                        将 URL 粘贴到 <strong>Payload URL</strong>
                      </li>
                      <li>
                        将 <strong>Content type</strong> 设置为 <code>application/json</code>
                      </li>
                      <li>
                        将 <strong>Secret</strong> 设置为你的 webhook secret
                      </li>
                      <li>
                        选择 <strong>Pull requests</strong> 事件
                      </li>
                    </ol>
                  ) : (
                    <ol className="text-sm text-latte-text-secondary space-y-1.5 list-decimal list-inside">
                      <li>
                        打开项目 → <strong>Settings</strong> → <strong>Webhooks</strong>
                      </li>
                      <li>将 URL 粘贴到 URL 字段</li>
                      <li>
                        将 <strong>Trigger</strong> 设置为 <code>Merge request events</code>
                      </li>
                      <li>输入你的 webhook secret token</li>
                    </ol>
                  )}
                </div>

                {repoId && (
                  <div className="p-4 rounded-latte-lg bg-latte-gold/5 border border-latte-gold/10">
                    <a
                      href={`https://${platform}.com/${repoId}/settings/hooks/new`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-sm text-latte-gold hover:underline"
                    >
                      打开 {platform === "github" ? "GitHub" : "GitLab"} Webhook 设置
                      <ExternalLink size={14} />
                    </a>
                  </div>
                )}
              </div>

              <div className="flex justify-between mt-8">
                <Button variant="ghost" onClick={() => setStep(2)}>
                  <ChevronLeft size={16} />
                  返回
                </Button>
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={() => setStep(4)}>
                    跳过
                    <ChevronRight size={16} />
                  </Button>
                  <Button variant="primary" onClick={() => setStep(4)}>
                    我已配置 Webhook
                    <ChevronRight size={16} />
                  </Button>
                </div>
              </div>
            </GlassCard>
          )}

          {step === 4 && (
            <GlassCard className="p-8 text-center" variant="elevated">
              <motion.div
                className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-latte-gold/10 mb-6"
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: "spring", stiffness: 200, damping: 15 }}
              >
                <Sparkles className="w-10 h-10 text-latte-gold" />
              </motion.div>

              <h3 className="text-xl font-display font-semibold text-latte-text-primary mb-2">
                一切就绪！
              </h3>
              <p className="text-sm text-latte-text-tertiary max-w-md mx-auto mb-6">
                配置完成。你可以配置 Webhook 实现自动审查，或手动获取 PR 进行审查。
              </p>

              <div className="max-w-md mx-auto mb-6">
                <button
                  onClick={handleFetchPRs}
                  disabled={fetchingPRs}
                  className="w-full py-3 px-4 rounded-latte-lg bg-latte-gold/10 border border-latte-gold/20 text-latte-gold font-medium text-sm hover:bg-latte-gold/15 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {fetchingPRs ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      正在获取 PR 列表...
                    </>
                  ) : (
                    <>
                      <Download size={16} />
                      获取仓库的 Pull Requests
                    </>
                  )}
                </button>
              </div>

              {prList.length > 0 && (
                <div className="max-w-md mx-auto mb-6 space-y-2 text-left">
                  <p className="text-xs text-latte-text-tertiary text-center mb-3">
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
                          <span className="text-xs text-latte-text-muted">{pr.author}</span>
                          <span className="text-xs text-latte-success">+{pr.additions}</span>
                          <span className="text-xs text-latte-critical">-{pr.deletions}</span>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-lg mx-auto mb-8">
                {[
                  { label: "AI 分析", desc: "多模型审查" },
                  { label: "静态扫描", desc: "Semgrep 安全" },
                  { label: "智能规则", desc: "自定义规则" },
                ].map((item) => (
                  <div key={item.label} className="p-3 rounded-latte-lg bg-latte-bg-tertiary/50">
                    <p className="text-sm font-medium text-latte-text-primary">{item.label}</p>
                    <p className="text-xs text-latte-text-muted">{item.desc}</p>
                  </div>
                ))}
              </div>

              <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                <Button variant="primary" onClick={onComplete}>
                  前往仪表盘
                  <ChevronRight size={16} />
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => router.push("/dashboard/analyze")}
                >
                  试用代码分析
                  <Sparkles size={14} />
                </Button>
              </div>
            </GlassCard>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
