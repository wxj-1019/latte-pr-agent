"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { api } from "@/lib/api";
import { RefreshCw, ZoomIn, ZoomOut, Maximize2, Copy, Check } from "lucide-react";

export default function ArchitectureDiagramPanel({ projectId }: { projectId: number }) {
  const [mermaidCode, setMermaidCode] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [scale, setScale] = useState(1);
  const [copied, setCopied] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const mermaidRef = useRef<HTMLDivElement>(null);

  const loadDiagram = useCallback(async () => {
    setLoading(true);
    setError(null);
    setRenderError(null);
    try {
      const res = await api.getArchitectureDiagram(projectId);
      setMermaidCode(res.mermaid || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadDiagram();
  }, [loadDiagram]);

  // Render mermaid diagram
  useEffect(() => {
    if (!mermaidCode || !mermaidRef.current) return;

    let cancelled = false;
    const render = async () => {
      try {
        const mermaid = await import("mermaid");
        if (cancelled) return;
        mermaid.default.initialize({
          startOnLoad: false,
          theme: "dark",
          securityLevel: "loose",
          fontFamily: "inherit",
        });
        const id = `arch-diagram-${projectId}-${Date.now()}`;
        const { svg } = await mermaid.default.render(id, mermaidCode);
        if (cancelled) return;
        if (mermaidRef.current) {
          mermaidRef.current.innerHTML = svg;
        }
      } catch (err) {
        if (!cancelled) {
          console.error("Mermaid render error:", err);
          setRenderError(err instanceof Error ? err.message : "架构图渲染失败，Mermaid 语法异常");
        }
      }
    };
    render();
    return () => {
      cancelled = true;
      if (mermaidRef.current) {
        mermaidRef.current.innerHTML = "";
      }
    };
  }, [mermaidCode, projectId]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(mermaidCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-latte-gold/30 border-t-latte-gold rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-latte-text-tertiary">
        <p className="text-sm">{error}</p>
        <button
          onClick={loadDiagram}
          className="mt-3 flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-latte-md bg-latte-bg-tertiary border border-latte-border text-latte-text-secondary hover:text-latte-text-primary transition-colors"
        >
          <RefreshCw size={12} />
          重试
        </button>
      </div>
    );
  }

  if (!mermaidCode) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-latte-text-tertiary">
        <p className="text-lg font-medium">暂无架构数据</p>
        <p className="text-sm mt-1">请先同步项目代码以生成架构图</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-latte-text-tertiary">基于项目代码结构由 AI 自动生成</p>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-latte-md bg-latte-bg-tertiary border border-latte-border text-latte-text-secondary hover:text-latte-text-primary transition-colors"
            title="复制 Mermaid 源码"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? "已复制" : "源码"}
          </button>
          <button
            onClick={() => setScale((s) => Math.min(3, s + 0.2))}
            className="w-7 h-7 rounded-latte-md bg-latte-bg-tertiary border border-latte-border text-latte-text-secondary hover:text-latte-text-primary flex items-center justify-center"
            title="放大"
          >
            <ZoomIn size={13} />
          </button>
          <button
            onClick={() => setScale((s) => Math.max(0.3, s - 0.2))}
            className="w-7 h-7 rounded-latte-md bg-latte-bg-tertiary border border-latte-border text-latte-text-secondary hover:text-latte-text-primary flex items-center justify-center"
            title="缩小"
          >
            <ZoomOut size={13} />
          </button>
          <button
            onClick={() => setScale(1)}
            className="w-7 h-7 rounded-latte-md bg-latte-bg-tertiary border border-latte-border text-latte-text-secondary hover:text-latte-text-primary flex items-center justify-center"
            title="重置"
          >
            <Maximize2 size={13} />
          </button>
          <button
            onClick={loadDiagram}
            className="w-7 h-7 rounded-latte-md bg-latte-bg-tertiary border border-latte-border text-latte-text-secondary hover:text-latte-text-primary flex items-center justify-center"
            title="重新生成"
          >
            <RefreshCw size={13} />
          </button>
        </div>
      </div>
      <div
        ref={containerRef}
        className="overflow-auto rounded-latte-xl border border-latte-border bg-latte-bg-secondary/50 min-h-[400px] flex items-center justify-center p-6"
      >
        {renderError ? (
          <div className="flex flex-col items-center text-latte-text-tertiary max-w-md">
            <p className="text-sm font-medium text-latte-text-secondary mb-1">架构图渲染异常</p>
            <p className="text-xs text-center mb-3">{renderError}</p>
            <button
              onClick={loadDiagram}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-latte-md bg-latte-bg-tertiary border border-latte-border text-latte-text-secondary hover:text-latte-text-primary transition-colors"
            >
              <RefreshCw size={12} />
              重新生成
            </button>
          </div>
        ) : (
          <div
            style={{
              transform: `scale(${scale})`,
              transformOrigin: "center center",
              transition: "transform 0.2s ease",
            }}
          >
            <div ref={mermaidRef} className="mermaid-diagram" />
          </div>
        )}
      </div>
    </div>
  );
}
