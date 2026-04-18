"use client";

import { useState, useEffect } from "react";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FadeInUp } from "@/components/motion/fade-in-up";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api } from "@/lib/api";
import { X, Plus } from "lucide-react";

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="flex items-center justify-between py-3 cursor-pointer">
      <span className="text-sm text-latte-text-secondary">{label}</span>
      <button
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
          checked ? "bg-latte-gold" : "bg-latte-bg-tertiary"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-latte-text-primary transition-transform ${
            checked ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </label>
  );
}

interface CustomRule {
  name: string;
  pattern: string;
  message: string;
  severity: "warning" | "critical";
}

interface ReviewConfigShape {
  context_analysis?: {
    enabled?: boolean;
    historical_bug_check?: boolean;
    api_contract_detection?: boolean;
    dependency_depth?: number;
  };
  critical_paths?: string[];
  custom_rules?: CustomRule[];
  ai_model?: {
    primary?: string;
    fallback?: string;
  };
}

export default function ConfigPage() {
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [newPath, setNewPath] = useState("");
  const [newRule, setNewRule] = useState({ name: "", pattern: "", message: "", severity: "warning" as "warning" | "critical" });
  const { showToast } = useToast();

  const [repos, setRepos] = useState<string[]>([]);
  const [selectedRepo, setSelectedRepo] = useState("default");

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmTitle, setConfirmTitle] = useState("");
  const [confirmDesc, setConfirmDesc] = useState("");
  const [confirmAction, setConfirmAction] = useState<(() => void) | null>(null);

  useEffect(() => {
    api.getRepos()
      .then((res) => {
        const list = res.repos || [];
        setRepos(list);
        if (list.length > 0 && !list.includes(selectedRepo)) {
          setSelectedRepo(list[0]);
        }
      })
      .catch(() => setRepos([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedRepo) return;
    setLoading(true);
    api.getProjectConfig(selectedRepo)
      .then((data: unknown) => {
        const d = data as Record<string, unknown>;
        setConfig((d.config_json as Record<string, unknown>) || {});
      })
      .catch((err) => {
        setError(err.message || "加载配置失败");
      })
      .finally(() => setLoading(false));
  }, [selectedRepo]);

  const reviewConfig = (config.review_config as ReviewConfigShape) || {};

  function requestConfirm(title: string, desc: string, action: () => void) {
    setConfirmTitle(title);
    setConfirmDesc(desc);
    setConfirmAction(() => action);
    setConfirmOpen(true);
  }

  async function handleSave() {
    setSaving(true);
    try {
      await api.updateProjectConfig(selectedRepo, config);
      showToast("配置已保存");
    } catch (err) {
      showToast("保存失败：" + (err instanceof Error ? err.message : "未知错误"), "error");
    } finally {
      setSaving(false);
    }
  }

  function addPath() {
    if (!newPath.trim()) return;
    setConfig({
      ...config,
      review_config: {
        ...reviewConfig,
        critical_paths: [...(reviewConfig.critical_paths || []), newPath.trim()],
      },
    });
    setNewPath("");
  }

  function removePath(index: number) {
    const paths = [...(reviewConfig.critical_paths || [])];
    paths.splice(index, 1);
    setConfig({
      ...config,
      review_config: { ...reviewConfig, critical_paths: paths },
    });
  }

  function addRule() {
    if (!newRule.name.trim() || !newRule.pattern.trim() || !newRule.message.trim()) return;
    setConfig({
      ...config,
      review_config: {
        ...reviewConfig,
        custom_rules: [...(reviewConfig.custom_rules || []), { ...newRule }],
      },
    });
    setNewRule({ name: "", pattern: "", message: "", severity: "warning" });
  }

  function removeRule(index: number) {
    const rules = [...(reviewConfig.custom_rules || [])];
    rules.splice(index, 1);
    setConfig({
      ...config,
      review_config: { ...reviewConfig, custom_rules: rules },
    });
  }

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="h-8 w-48 bg-latte-bg-secondary rounded animate-pulse" />
        <div className="h-64 bg-latte-bg-secondary rounded-latte-xl animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto flex flex-col items-center justify-center py-20 text-latte-text-tertiary">
        <p className="text-lg font-medium">加载配置失败</p>
        <p className="text-sm mt-1">{error}</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <FadeInUp>
        <h1 className="text-2xl font-display font-semibold tracking-tight text-latte-text-primary">
          项目配置
        </h1>
        <div className="flex items-center gap-3 mt-2">
          <select
            value={selectedRepo}
            onChange={(e) => { setError(null); setSelectedRepo(e.target.value); }}
            className="h-9 px-3 rounded-latte-md bg-latte-bg-tertiary text-sm text-latte-text-secondary border border-transparent focus:border-latte-gold/40 outline-none appearance-none"
            style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%23C4A77D' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`,
              backgroundRepeat: "no-repeat",
              backgroundPosition: "right 0.5rem center",
              backgroundSize: "1rem",
            }}
          >
            {repos.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
      </FadeInUp>

      <FadeInUp delay={0.1}>
        <GlassCard className="p-6">
          <h3 className="text-lg font-medium text-latte-text-primary mb-4">上下文分析</h3>
          <div className="divide-y divide-latte-text-primary/5">
            <Toggle
              label="启用上下文分析"
              checked={reviewConfig.context_analysis?.enabled ?? false}
              onChange={(v) =>
                setConfig({
                  ...config,
                  review_config: {
                    ...reviewConfig,
                    context_analysis: { ...reviewConfig.context_analysis, enabled: v },
                  },
                })
              }
            />
            <Toggle
              label="历史 Bug 检查"
              checked={reviewConfig.context_analysis?.historical_bug_check ?? false}
              onChange={(v) =>
                setConfig({
                  ...config,
                  review_config: {
                    ...reviewConfig,
                    context_analysis: { ...reviewConfig.context_analysis, historical_bug_check: v },
                  },
                })
              }
            />
            <Toggle
              label="API 契约检测"
              checked={reviewConfig.context_analysis?.api_contract_detection ?? false}
              onChange={(v) =>
                setConfig({
                  ...config,
                  review_config: {
                    ...reviewConfig,
                    context_analysis: { ...reviewConfig.context_analysis, api_contract_detection: v },
                  },
                })
              }
            />
          </div>
          <div className="mt-4">
            <label className="text-sm text-latte-text-secondary">依赖深度</label>
            <Input
              type="number"
              value={reviewConfig.context_analysis?.dependency_depth || 2}
              onChange={(e) =>
                setConfig({
                  ...config,
                  review_config: {
                    ...reviewConfig,
                    context_analysis: {
                      ...reviewConfig.context_analysis,
                      dependency_depth: parseInt(e.target.value, 10),
                    },
                  },
                })
              }
              className="mt-2 w-32"
            />
          </div>
        </GlassCard>
      </FadeInUp>

      <FadeInUp delay={0.15}>
        <GlassCard className="p-6">
          <h3 className="text-lg font-medium text-latte-text-primary mb-4">关键路径</h3>
          <div className="space-y-2 mb-4">
            {(reviewConfig.critical_paths || []).map((path: string, idx: number) => (
              <div key={idx} className="flex items-center justify-between px-3 py-2 rounded-latte-md bg-latte-bg-tertiary text-sm text-latte-text-secondary">
                <span>{path}</span>
                <button
                  onClick={() => requestConfirm(
                    "删除关键路径",
                    `确定要删除 "${path}" 吗？此操作无法撤销。`,
                    () => removePath(idx)
                  )}
                  className="text-latte-text-muted hover:text-latte-critical transition-colors"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
            {!(reviewConfig.critical_paths || []).length && (
              <p className="text-sm text-latte-text-muted">未定义关键路径</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Input
              placeholder="例如 src/payment/"
              value={newPath}
              onChange={(e) => setNewPath(e.target.value)}
              className="flex-1 h-9 text-sm"
              onKeyDown={(e) => e.key === "Enter" && addPath()}
            />
            <Button variant="secondary" size="sm" onClick={addPath}>
              <Plus size={14} />
              添加
            </Button>
          </div>
        </GlassCard>
      </FadeInUp>

      <FadeInUp delay={0.2}>
        <GlassCard className="p-6">
          <h3 className="text-lg font-medium text-latte-text-primary mb-4">自定义规则</h3>
          <div className="space-y-3 mb-4">
            {(reviewConfig.custom_rules || []).map((rule: CustomRule, idx: number) => (
              <div key={idx} className="p-3 rounded-latte-md bg-latte-bg-tertiary text-sm">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-latte-text-primary">{rule.name}</span>
                  <button
                    onClick={() => requestConfirm(
                      "删除自定义规则",
                      `确定要删除规则 "${rule.name}" 吗？此操作无法撤销。`,
                      () => removeRule(idx)
                    )}
                    className="text-latte-text-muted hover:text-latte-critical transition-colors"
                  >
                    <X size={14} />
                  </button>
                </div>
                <p className="text-latte-text-secondary">Pattern: {rule.pattern}</p>
                <p className="text-latte-text-muted text-xs mt-1">{rule.message}</p>
              </div>
            ))}
            {!(reviewConfig.custom_rules || []).length && (
              <p className="text-sm text-latte-text-muted">未定义自定义规则</p>
            )}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <Input
              placeholder="规则名称"
              value={newRule.name}
              onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
              className="h-9 text-sm"
            />
            <Input
              placeholder="匹配模式"
              value={newRule.pattern}
              onChange={(e) => setNewRule({ ...newRule, pattern: e.target.value })}
              className="h-9 text-sm"
            />
            <Input
              placeholder="提示信息"
              value={newRule.message}
              onChange={(e) => setNewRule({ ...newRule, message: e.target.value })}
              className="h-9 text-sm sm:col-span-2"
            />
            <div className="flex items-center gap-2">
              <select
                value={newRule.severity}
                onChange={(e) => setNewRule({ ...newRule, severity: e.target.value as "warning" | "critical" })}
                className="h-9 px-2 pr-8 rounded-latte-md bg-latte-bg-tertiary text-sm text-latte-text-secondary border border-transparent focus:border-latte-gold/40 outline-none appearance-none"
                style={{
                  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%23C4A77D' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`,
                  backgroundRepeat: "no-repeat",
                  backgroundPosition: "right 0.5rem center",
                  backgroundSize: "1rem",
                }}
              >
                <option value="warning">警告</option>
                <option value="critical">严重</option>
              </select>
              <Button variant="secondary" size="sm" onClick={addRule}>
                <Plus size={14} />
                添加规则
              </Button>
            </div>
          </div>
        </GlassCard>
      </FadeInUp>

      <FadeInUp delay={0.25}>
        <GlassCard className="p-6">
          <h3 className="text-lg font-medium text-latte-text-primary mb-4">AI 模型</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-latte-text-secondary">主模型</label>
              <Input
                value={reviewConfig.ai_model?.primary || ""}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    review_config: {
                      ...reviewConfig,
                      ai_model: { ...reviewConfig.ai_model, primary: e.target.value },
                    },
                  })
                }
                className="mt-2"
              />
            </div>
            <div>
              <label className="text-sm text-latte-text-secondary">备用模型</label>
              <Input
                value={reviewConfig.ai_model?.fallback || ""}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    review_config: {
                      ...reviewConfig,
                      ai_model: { ...reviewConfig.ai_model, fallback: e.target.value },
                    },
                  })
                }
                className="mt-2"
              />
            </div>
          </div>
        </GlassCard>
      </FadeInUp>

      <FadeInUp delay={0.3}>
        <div className="flex justify-end">
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "保存中..." : "保存更改"}
          </Button>
        </div>
      </FadeInUp>

      <ConfirmDialog
        open={confirmOpen}
        title={confirmTitle}
        description={confirmDesc}
        onConfirm={() => { confirmAction?.(); setConfirmOpen(false); }}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
