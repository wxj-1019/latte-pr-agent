"use client";

import { useState, useEffect } from "react";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FadeInUp } from "@/components/motion/fade-in-up";
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

const DEFAULT_REPO = "default";

export default function ConfigPage() {
  const [config, setConfig] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [newPath, setNewPath] = useState("");
  const [newRule, setNewRule] = useState({ name: "", pattern: "", message: "", severity: "warning" as "warning" | "critical" });

  useEffect(() => {
    api.getProjectConfig(DEFAULT_REPO)
      .then((data: any) => {
        setConfig(data.config_json || {});
      })
      .catch((err) => {
        setError(err.message || "Failed to load config");
      })
      .finally(() => setLoading(false));
  }, []);

  const reviewConfig = config.review_config || {};

  async function handleSave() {
    setSaving(true);
    try {
      await api.updateProjectConfig(DEFAULT_REPO, config);
      alert("Config saved");
    } catch (err: any) {
      alert("Failed to save: " + (err.message || "Unknown error"));
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
        <p className="text-lg font-medium">Failed to load config</p>
        <p className="text-sm mt-1">{error}</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <FadeInUp>
        <h1 className="text-2xl font-display font-semibold tracking-tight text-latte-text-primary">
          Project Config
        </h1>
        <p className="text-sm text-latte-text-tertiary mt-1">
          Customize review behavior for {DEFAULT_REPO}
        </p>
      </FadeInUp>

      <FadeInUp delay={0.1}>
        <GlassCard className="p-6">
          <h3 className="text-lg font-medium text-latte-text-primary mb-4">Context Analysis</h3>
          <div className="divide-y divide-latte-text-primary/5">
            <Toggle
              label="Enable context analysis"
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
              label="Historical bug check"
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
              label="API contract detection"
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
            <label className="text-sm text-latte-text-secondary">Dependency depth</label>
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
          <h3 className="text-lg font-medium text-latte-text-primary mb-4">Critical Paths</h3>
          <div className="space-y-2 mb-4">
            {(reviewConfig.critical_paths || []).map((path: string, idx: number) => (
              <div key={idx} className="flex items-center justify-between px-3 py-2 rounded-latte-md bg-latte-bg-tertiary text-sm text-latte-text-secondary">
                <span>{path}</span>
                <button onClick={() => removePath(idx)} className="text-latte-text-muted hover:text-latte-critical transition-colors">
                  <X size={14} />
                </button>
              </div>
            ))}
            {!(reviewConfig.critical_paths || []).length && (
              <p className="text-sm text-latte-text-muted">No critical paths defined</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Input
              placeholder="e.g. src/payment/"
              value={newPath}
              onChange={(e) => setNewPath(e.target.value)}
              className="flex-1 h-9 text-sm"
              onKeyDown={(e) => e.key === "Enter" && addPath()}
            />
            <Button variant="secondary" size="sm" onClick={addPath}>
              <Plus size={14} />
              Add
            </Button>
          </div>
        </GlassCard>
      </FadeInUp>

      <FadeInUp delay={0.2}>
        <GlassCard className="p-6">
          <h3 className="text-lg font-medium text-latte-text-primary mb-4">Custom Rules</h3>
          <div className="space-y-3 mb-4">
            {(reviewConfig.custom_rules || []).map((rule: any, idx: number) => (
              <div key={idx} className="p-3 rounded-latte-md bg-latte-bg-tertiary text-sm">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-latte-text-primary">{rule.name}</span>
                  <button onClick={() => removeRule(idx)} className="text-latte-text-muted hover:text-latte-critical transition-colors">
                    <X size={14} />
                  </button>
                </div>
                <p className="text-latte-text-secondary">Pattern: {rule.pattern}</p>
                <p className="text-latte-text-muted text-xs mt-1">{rule.message}</p>
              </div>
            ))}
            {!(reviewConfig.custom_rules || []).length && (
              <p className="text-sm text-latte-text-muted">No custom rules defined</p>
            )}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <Input
              placeholder="Rule name"
              value={newRule.name}
              onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
              className="h-9 text-sm"
            />
            <Input
              placeholder="Pattern"
              value={newRule.pattern}
              onChange={(e) => setNewRule({ ...newRule, pattern: e.target.value })}
              className="h-9 text-sm"
            />
            <Input
              placeholder="Message"
              value={newRule.message}
              onChange={(e) => setNewRule({ ...newRule, message: e.target.value })}
              className="h-9 text-sm sm:col-span-2"
            />
            <div className="flex items-center gap-2">
              <select
                value={newRule.severity}
                onChange={(e) => setNewRule({ ...newRule, severity: e.target.value as "warning" | "critical" })}
                className="h-9 px-2 rounded-latte-md bg-latte-bg-tertiary text-sm text-latte-text-secondary border border-transparent focus:border-latte-gold/40 outline-none"
              >
                <option value="warning">warning</option>
                <option value="critical">critical</option>
              </select>
              <Button variant="secondary" size="sm" onClick={addRule}>
                <Plus size={14} />
                Add Rule
              </Button>
            </div>
          </div>
        </GlassCard>
      </FadeInUp>

      <FadeInUp delay={0.25}>
        <GlassCard className="p-6">
          <h3 className="text-lg font-medium text-latte-text-primary mb-4">AI Models</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-latte-text-secondary">Primary</label>
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
              <label className="text-sm text-latte-text-secondary">Fallback</label>
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
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </FadeInUp>
    </div>
  );
}
