"use client";

import { useState } from "react";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { FadeInUp } from "@/components/motion/fade-in-up";
import { usePrompts } from "@/hooks/use-prompts";
import { api } from "@/lib/api";
import { Check, FlaskConical, Loader2, ChevronDown, ChevronUp } from "lucide-react";

interface TestState {
  loading: boolean;
  result: string | null;
  error: string | null;
}

export default function PromptsPage() {
  const { prompts, isLoading, mutate } = usePrompts();

  const [isCreating, setIsCreating] = useState(false);
  const [newVersion, setNewVersion] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newMetadata, setNewMetadata] = useState("");
  const [createLoading, setCreateLoading] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editVersion, setEditVersion] = useState("");
  const [editContent, setEditContent] = useState("");
  const [editMetadata, setEditMetadata] = useState("");
  const [editLoading, setEditLoading] = useState(false);

  const [testStates, setTestStates] = useState<Record<number, TestState>>({});
  const [expandedTests, setExpandedTests] = useState<Set<number>>(new Set());

  async function handleCreate() {
    if (!newVersion.trim() || !newContent.trim()) return;
    setCreateLoading(true);
    try {
      let metadata: object | undefined;
      if (newMetadata.trim()) {
        try {
          metadata = JSON.parse(newMetadata);
        } catch {
          alert("元数据必须是有效的 JSON");
          setCreateLoading(false);
          return;
        }
      }
      await api.savePromptVersion({
        version: newVersion.trim(),
        text: newContent.trim(),
        metadata,
      });
      setIsCreating(false);
      setNewVersion("");
      setNewContent("");
      setNewMetadata("");
      mutate();
    } catch (err) {
      alert("创建失败：" + (err instanceof Error ? err.message : "未知错误"));
    } finally {
      setCreateLoading(false);
    }
  }

  function startEdit(prompt: (typeof prompts)[0]) {
    setEditingId(prompt.id);
    setEditVersion(prompt.version);
    setEditContent(prompt.content || "");
    setEditMetadata(prompt.metadata ? JSON.stringify(prompt.metadata, null, 2) : "");
  }

  async function handleSaveEdit() {
    if (!editVersion.trim() || !editContent.trim()) return;
    setEditLoading(true);
    try {
      let metadata: object | undefined;
      if (editMetadata.trim()) {
        try {
          metadata = JSON.parse(editMetadata);
        } catch {
          alert("元数据必须是有效的 JSON");
          setEditLoading(false);
          return;
        }
      }
      await api.savePromptVersion({
        version: editVersion.trim(),
        text: editContent.trim(),
        metadata,
      });
      setEditingId(null);
      mutate();
    } catch (err) {
      alert("保存失败：" + (err instanceof Error ? err.message : "未知错误"));
    } finally {
      setEditLoading(false);
    }
  }

  async function handleTest(prompt: (typeof prompts)[0]) {
    setTestStates((prev) => ({
      ...prev,
      [prompt.id]: { loading: true, result: null, error: null },
    }));
    setExpandedTests((prev) => {
      const next = new Set(prev);
      next.add(prompt.id);
      return next;
    });
    try {
      const result = await api.optimizePrompt({
        base_version: prompt.version,
        new_version: `${prompt.version}-test`,
        min_samples: 10,
      });
      setTestStates((prev) => ({
        ...prev,
        [prompt.id]: { loading: false, result: JSON.stringify(result, null, 2), error: null },
      }));
    } catch (err) {
      setTestStates((prev) => ({
        ...prev,
        [prompt.id]: { loading: false, result: null, error: err instanceof Error ? err.message : "测试失败" },
      }));
    }
  }

  function toggleTestExpand(id: number) {
    setExpandedTests((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <FadeInUp>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-display font-semibold tracking-tight text-latte-text-primary">
              Prompt 注册表
            </h1>
            <p className="text-sm text-latte-text-tertiary mt-1">
              管理 Prompt 版本和 A/B 实验
            </p>
          </div>
          <Button
            variant="secondary"
            onClick={() => setIsCreating((v) => !v)}
            disabled={isCreating}
          >
            <Check size={16} />
            {isCreating ? "创建中..." : "新版本"}
          </Button>
        </div>
      </FadeInUp>

      {isCreating && (
        <FadeInUp>
          <GlassCard className="p-6 space-y-4">
            <h3 className="text-lg font-medium text-latte-text-primary">创建新 Prompt 版本</h3>
            <div>
              <label className="text-sm text-latte-text-secondary block mb-1.5">版本</label>
              <Input
                placeholder="例如 v1.3.0"
                value={newVersion}
                onChange={(e) => setNewVersion(e.target.value)}
              />
            </div>
            <div>
              <label className="text-sm text-latte-text-secondary block mb-1.5">内容</label>
              <textarea
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
                rows={6}
                className="w-full rounded-latte-md bg-latte-bg-tertiary border border-transparent focus:border-latte-gold/40 outline-none px-3 py-2 text-sm text-latte-text-primary font-mono resize-none"
                placeholder="输入 Prompt 文本..."
              />
            </div>
            <div>
              <label className="text-sm text-latte-text-secondary block mb-1.5">元数据（JSON，可选）</label>
              <textarea
                value={newMetadata}
                onChange={(e) => setNewMetadata(e.target.value)}
                rows={3}
                className="w-full rounded-latte-md bg-latte-bg-tertiary border border-transparent focus:border-latte-gold/40 outline-none px-3 py-2 text-sm text-latte-text-primary font-mono resize-none"
                placeholder='{"author": "team", "tags": ["security"]}'
              />
            </div>
            <div className="flex items-center gap-2">
              <Button onClick={handleCreate} disabled={createLoading || !newVersion.trim() || !newContent.trim()}>
                {createLoading ? <Loader2 size={16} className="animate-spin" /> : "保存"}
              </Button>
              <Button variant="ghost" onClick={() => setIsCreating(false)}>
                取消
              </Button>
            </div>
          </GlassCard>
        </FadeInUp>
      )}

      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="h-32 bg-latte-bg-secondary rounded-latte-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {prompts.map((prompt, index) => {
            const isEditing = editingId === prompt.id;
            const testState = testStates[prompt.id];
            const isTestExpanded = expandedTests.has(prompt.id);

            return (
              <FadeInUp key={prompt.id} delay={index * 0.1}>
                <GlassCard className="p-6">
                  {isEditing ? (
                    <div className="space-y-4">
                      <div>
                        <label className="text-sm text-latte-text-secondary block mb-1.5">版本</label>
                        <Input
                          value={editVersion}
                          onChange={(e) => setEditVersion(e.target.value)}
                        />
                      </div>
                      <div>
                        <label className="text-sm text-latte-text-secondary block mb-1.5">内容</label>
                        <textarea
                          value={editContent}
                          onChange={(e) => setEditContent(e.target.value)}
                          rows={6}
                          className="w-full rounded-latte-md bg-latte-bg-tertiary border border-transparent focus:border-latte-gold/40 outline-none px-3 py-2 text-sm text-latte-text-primary font-mono resize-none"
                        />
                      </div>
                      <div>
                        <label className="text-sm text-latte-text-secondary block mb-1.5">元数据（JSON，可选）</label>
                        <textarea
                          value={editMetadata}
                          onChange={(e) => setEditMetadata(e.target.value)}
                          rows={3}
                          className="w-full rounded-latte-md bg-latte-bg-tertiary border border-transparent focus:border-latte-gold/40 outline-none px-3 py-2 text-sm text-latte-text-primary font-mono resize-none"
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          onClick={handleSaveEdit}
                          disabled={editLoading || !editVersion.trim() || !editContent.trim()}
                        >
                          {editLoading ? <Loader2 size={16} className="animate-spin" /> : "保存"}
                        </Button>
                        <Button variant="ghost" onClick={() => setEditingId(null)}>
                          取消
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                        <div>
                          <div className="flex items-center gap-3">
                            <h3 className="text-lg font-medium text-latte-text-primary">
                              {prompt.version}
                            </h3>
                            {prompt.is_active && (
                              <Badge variant="success" dot>
                                活跃
                              </Badge>
                            )}
                            {prompt.is_baseline && (
                              <Badge variant="info" dot>
                                基线
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-4 mt-2 text-sm text-latte-text-tertiary">
                            <span>用于 {prompt.repo_count} 个仓库</span>
                            <span>·</span>
                            <span>准确率 {Math.round((prompt.accuracy || 0) * 100)}%</span>
                            {prompt.ab_ratio !== undefined && (
                              <>
                                <span>·</span>
                                <span className="inline-flex items-center gap-1">
                                  <FlaskConical size={14} />
                                  A/B {Math.round(prompt.ab_ratio * 100)}%
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button variant="ghost" size="sm" onClick={() => startEdit(prompt)}>
                            编辑
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleTest(prompt)}
                            disabled={testState?.loading}
                          >
                            {testState?.loading ? (
                              <Loader2 size={14} className="animate-spin" />
                            ) : (
                              <FlaskConical size={14} />
                            )}
                            测试
                          </Button>
                        </div>
                      </div>

                      {testState && (
                        <div className="mt-4 pt-4 border-t border-latte-text-primary/5">
                          <button
                            onClick={() => toggleTestExpand(prompt.id)}
                            className="flex items-center gap-2 text-sm text-latte-text-secondary hover:text-latte-text-primary transition-colors"
                          >
                            {isTestExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            测试结果
                          </button>
                          {isTestExpanded && (
                            <div className="mt-3">
                              {testState.error ? (
                                <p className="text-sm text-latte-critical">{testState.error}</p>
                              ) : testState.result ? (
                                <pre className="text-xs font-mono text-latte-text-secondary bg-latte-bg-tertiary rounded-latte-md p-3 overflow-auto max-h-64">
                                  {testState.result}
                                </pre>
                              ) : null}
                            </div>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </GlassCard>
              </FadeInUp>
            );
          })}
        </div>
      )}
    </div>
  );
}
