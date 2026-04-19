"use client";

import { useState, useEffect } from "react";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FadeInUp } from "@/components/motion/fade-in-up";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { Eye, EyeOff, Check, XCircle, Loader2 } from "lucide-react";

interface SettingItem {
  key: string;
  has_value: boolean;
  value?: string | null;
  description: string;
}

type SettingsCategories = Record<string, SettingItem[]>;

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
      await api.batchUpdateSystemSettings(settingsList);
      showToast("设置已保存");
      setChangedKeys(new Set());
      await loadSettings();
    } catch (err) {
      showToast("保存失败：" + (err instanceof Error ? err.message : "未知错误"), "error");
    } finally {
      setSaving(false);
    }
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
            <h3 className="text-lg font-medium text-latte-text-primary mb-4">
              {CATEGORY_LABELS[catKey] || catKey}
            </h3>
            <div className="space-y-4">
              {items.map((item) => {
                const isSecret = SECRET_KEYS.has(item.key);
                const isVisible = showValues[item.key];
                const hasChanged = changedKeys.has(item.key);
                const currentValue = editValues[item.key] ?? "";

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
                        type={isSecret && !isVisible ? "password" : "text"}
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
