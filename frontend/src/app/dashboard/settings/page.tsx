"use client";

import { useState, useEffect } from "react";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FadeInUp } from "@/components/motion/fade-in-up";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { Eye, EyeOff, Check, XCircle, Loader2, Zap, Copy, ExternalLink } from "lucide-react";

interface SettingItem {
  key: string;
  has_value: boolean;
  value?: string | null;
  description: string;
}

type SettingsCategories = Record<string, SettingItem[]>;

interface WebhookCheckResult {
  name: string;
  status: string;
  message: string;
  webhook_url?: string;
  webhook_secret?: string;
}

interface WebhookTestResult {
  platform: string;
  passed: boolean;
  checks: WebhookCheckResult[];
  webhook_secret: string;
}

const CATEGORY_LABELS: Record<string, string> = {
  platform: "平台连接",
  llm: "AI 模型密钥",
};

const KEY_LABELS: Record<string, string> = {
  github_token: "GitHub Token",
  github_webhook_secret: "GitHub Webhook Secret",
  gitlab_token: "GitLab Token",
  gitlab_webhook_secret: "GitLab Webhook Secret",
  gitlab_url: "GitLab URL",
  deepseek_api_key: "DeepSeek API Key",
  anthropic_api_key: "Anthropic API Key",
  openai_api_key: "OpenAI API Key",
  qwen_api_key: "Qwen API Key",
};

const SECRET_KEYS = new Set([
  "github_token",
  "github_webhook_secret",
  "gitlab_token",
  "gitlab_webhook_secret",
  "deepseek_api_key",
  "anthropic_api_key",
  "openai_api_key",
  "qwen_api_key",
]);

export default function SystemSettingsPage() {
  const [categories, setCategories] = useState<SettingsCategories>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [showValues, setShowValues] = useState<Record<string, boolean>>({});
  const [changedKeys, setChangedKeys] = useState<Set<string>>(new Set());
  const [testingWebhook, setTestingWebhook] = useState<"github" | "gitlab" | null>(null);
  const [webhookResults, setWebhookResults] = useState<Record<string, WebhookTestResult>>({});
  const { showToast } = useToast();

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getSystemSettings();
      setCategories(data.categories);
      const initValues: Record<string, string> = {};
      Object.values(data.categories as SettingsCategories).flat().forEach((item) => {
        initValues[item.key] = item.value || "";
      });
      setEditValues(initValues);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载设置失败");
    } finally {
      setLoading(false);
    }
  }

  function handleChange(key: string, value: string) {
    setEditValues((prev) => ({ ...prev, [key]: value }));
    setChangedKeys((prev) => new Set(prev).add(key));
  }

  function toggleShow(key: string) {
    setShowValues((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  async function handleSave() {
    if (changedKeys.size === 0) {
      showToast("没有需要保存的更改");
      return;
    }
    setSaving(true);
    try {
      const settingsList = Array.from(changedKeys).map((key) => ({
        key,
        value: editValues[key] || "",
      }));
      const res = await api.batchUpdateSystemSettings(settingsList);
      const errors = res.results.filter((r) => r.status === "error");
      if (errors.length > 0) {
        showToast(
          `保存失败：${errors.map((e) => `${e.key}: ${e.message}`).join(", ")}`,
          "error"
        );
      } else {
        showToast("设置已保存");
        setChangedKeys(new Set());
        await loadSettings();
      }
    } catch (err) {
      showToast("保存失败：" + (err instanceof Error ? err.message : "未知错误"), "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleTestWebhook(platform: "github" | "gitlab") {
    setTestingWebhook(platform);
    try {
      const result = await api.testWebhook(platform);
      setWebhookResults((prev) => ({ ...prev, [platform]: result }));

      if (result.passed) {
        showToast(`${platform === "github" ? "GitHub" : "GitLab"} Webhook 测试通过`, "success");
        await loadSettings();
      } else {
        showToast(`${platform === "github" ? "GitHub" : "GitLab"} Webhook 测试未通过，请检查配置`, "error");
      }
    } catch (err) {
      showToast("测试失败：" + (err instanceof Error ? err.message : "未知错误"), "error");
    } finally {
      setTestingWebhook(null);
    }
  }

  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text);
    showToast("已复制到剪贴板");
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
        <XCircle size={40} className="mb-4 text-latte-critical" />
        <p className="text-lg font-medium">加载设置失败</p>
        <p className="text-sm mt-1">{error}</p>
        <Button variant="secondary" size="sm" className="mt-4" onClick={loadSettings}>
          重试
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <FadeInUp>
        <h1 className="text-2xl font-display font-semibold tracking-tight text-latte-text-primary">
          系统设置
        </h1>
        <p className="text-sm text-latte-text-tertiary mt-1">
          配置平台 Token、AI 模型密钥等敏感信息，存储在数据库中加密保存
        </p>
      </FadeInUp>

      {Object.entries(categories).map(([catKey, items], catIdx) => (
        <FadeInUp key={catKey} delay={0.1 * (catIdx + 1)}>
          <GlassCard className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-latte-text-primary">
                {CATEGORY_LABELS[catKey] || catKey}
              </h3>
              {catKey === "platform" && (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleTestWebhook("github")}
                    disabled={testingWebhook === "github"}
                  >
                    {testingWebhook === "github" ? (
                      <><Loader2 size={14} className="animate-spin" /> 测试中...</>
                    ) : (
                      <><Zap size={14} /> 测试 GitHub</>
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleTestWebhook("gitlab")}
                    disabled={testingWebhook === "gitlab"}
                  >
                    {testingWebhook === "gitlab" ? (
                      <><Loader2 size={14} className="animate-spin" /> 测试中...</>
                    ) : (
                      <><Zap size={14} /> 测试 GitLab</>
                    )}
                  </Button>
                </div>
              )}
            </div>

            <div className="space-y-4">
              {items.map((item) => {
                const isSecret = SECRET_KEYS.has(item.key);
                const isVisible = showValues[item.key];
                const hasChanged = changedKeys.has(item.key);
                const rawValue = editValues[item.key] ?? "";
                const currentValue =
                  isSecret && item.has_value && !hasChanged && !rawValue
                    ? "••••••"
                    : rawValue;

                return (
                  <div key={item.key}>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="text-sm font-medium text-latte-text-secondary">
                        {KEY_LABELS[item.key] || item.key}
                      </label>
                      <div className="flex items-center gap-2">
                        {item.has_value && !hasChanged && (
                          <span className="inline-flex items-center gap-1 text-xs text-latte-success">
                            <Check size={12} />
                            已配置
                          </span>
                        )}
                        {hasChanged && (
                          <span className="text-xs text-latte-warning">未保存</span>
                        )}
                      </div>
                    </div>
                    <p className="text-xs text-latte-text-muted mb-2">{item.description}</p>
                    <div className="relative">
                      <Input
                        type={isSecret && !isVisible && !currentValue.startsWith("•") ? "password" : "text"}
                        value={currentValue}
                        onChange={(e) => handleChange(item.key, e.target.value)}
                        placeholder={item.has_value && !hasChanged ? "已配置，输入新值可覆盖" : "请输入..."}
                        className="pr-10"
                      />
                      {isSecret && (
                        <button
                          type="button"
                          onClick={() => toggleShow(item.key)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-latte-text-muted hover:text-latte-text-secondary transition-colors"
                        >
                          {isVisible ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {catKey === "platform" && webhookResults.github && (
              <WebhookTestResultCard result={webhookResults.github} onCopy={copyToClipboard} />
            )}
            {catKey === "platform" && webhookResults.gitlab && (
              <WebhookTestResultCard result={webhookResults.gitlab} onCopy={copyToClipboard} />
            )}
          </GlassCard>
        </FadeInUp>
      ))}

      <FadeInUp delay={0.3}>
        <div className="flex items-center justify-between">
          <p className="text-xs text-latte-text-muted">
            {changedKeys.size > 0
              ? `${changedKeys.size} 项设置已修改`
              : "所有设置均为最新"}
          </p>
          <Button onClick={handleSave} disabled={saving || changedKeys.size === 0}>
            {saving ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                保存中...
              </>
            ) : (
              "保存更改"
            )}
          </Button>
        </div>
      </FadeInUp>
    </div>
  );
}

function WebhookTestResultCard({
  result,
  onCopy,
}: {
  result: WebhookTestResult;
  onCopy: (text: string) => void;
}) {
  const platformLabel = result.platform === "github" ? "GitHub" : "GitLab";

  return (
    <div className="mt-6 pt-4 border-t border-latte-bg-tertiary">
      <h4 className="text-sm font-medium text-latte-text-primary mb-3 flex items-center gap-2">
        <Zap size={14} className={result.passed ? "text-latte-success" : "text-latte-warning"} />
        {platformLabel} Webhook 测试结果
      </h4>
      <div className="space-y-2">
        {result.checks.map((check) => (
          <div
            key={check.name}
            className={`text-xs px-3 py-2 rounded-lg flex items-start gap-2 ${
              check.status === "ok" || check.status === "generated"
                ? "bg-latte-success/10 text-latte-success"
                : check.status === "error"
                ? "bg-latte-critical/10 text-latte-critical"
                : "bg-blue-500/10 text-blue-400"
            }`}
          >
            <span className="mt-0.5">
              {check.status === "ok" || check.status === "generated" ? (
                <Check size={12} />
              ) : check.status === "error" ? (
                <XCircle size={12} />
              ) : (
                <ExternalLink size={12} />
              )}
            </span>
            <div className="flex-1">
              <span className="font-medium">{check.name}</span>: {check.message}
              {check.webhook_url && (
                <div className="mt-1 flex items-center gap-2">
                  <code className="bg-latte-bg-secondary px-2 py-0.5 rounded text-[11px] break-all">
                    {check.webhook_url}
                  </code>
                  <button
                    onClick={() => onCopy(check.webhook_url!)}
                    className="text-latte-text-muted hover:text-latte-text-secondary transition-colors shrink-0"
                  >
                    <Copy size={11} />
                  </button>
                </div>
              )}
              {check.webhook_secret && (
                <div className="mt-1 flex items-center gap-2">
                  <code className="bg-latte-bg-secondary px-2 py-0.5 rounded text-[11px] break-all">
                    {check.webhook_secret}
                  </code>
                  <button
                    onClick={() => onCopy(check.webhook_secret!)}
                    className="text-latte-text-muted hover:text-latte-text-secondary transition-colors shrink-0"
                  >
                    <Copy size={11} />
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
