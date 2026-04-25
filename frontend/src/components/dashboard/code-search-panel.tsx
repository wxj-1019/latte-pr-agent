"use client";

import { useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { Search, FileCode, FunctionSquare, Box, Network, Loader2 } from "lucide-react";

interface SearchResult {
  id: number;
  name: string;
  entity_type: string;
  file_path: string;
  start_line: number;
  signature: string;
  meta_json: Record<string, unknown>;
  similarity: number;
  neighbors: Array<{
    id: number;
    name: string;
    entity_type: string;
    file_path: string;
    relation_type: string;
  }>;
}

const typeIcons: Record<string, React.ReactNode> = {
  function: <FunctionSquare size={14} className="text-latte-info" />,
  class: <Box size={14} className="text-latte-critical" />,
  interface: <FileCode size={14} className="text-latte-success" />,
  module: <Network size={14} className="text-latte-warning" />,
};

const typeColors: Record<string, string> = {
  function: "bg-latte-info/10 text-latte-info border-latte-info/20",
  class: "bg-latte-critical/10 text-latte-critical border-latte-critical/20",
  interface: "bg-latte-success/10 text-latte-success border-latte-success/20",
  module: "bg-latte-warning/10 text-latte-warning border-latte-warning/20",
};

export default function CodeSearchPanel({ projectId }: { projectId: number }) {
  const [query, setQuery] = useState("");
  const [entityType, setEntityType] = useState<string>("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const res = await api.codeSearch(
        projectId,
        query.trim(),
        entityType || undefined,
        10
      );
      setResults(res.results);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [query, entityType, projectId]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-latte-text-tertiary"
          />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="搜索代码，如：用户认证、数据库连接、API 路由..."
            className="w-full pl-9 pr-4 py-2 text-sm rounded-latte-md bg-latte-bg-tertiary border border-latte-border text-latte-text-primary placeholder:text-latte-text-tertiary focus:outline-none focus:border-latte-gold/50"
          />
        </div>
        <select
          value={entityType}
          onChange={(e) => setEntityType(e.target.value)}
          className="px-3 py-2 text-sm rounded-latte-md bg-latte-bg-tertiary border border-latte-border text-latte-text-secondary focus:outline-none focus:border-latte-gold/50"
        >
          <option value="">全部类型</option>
          <option value="function">函数</option>
          <option value="class">类</option>
          <option value="interface">接口</option>
          <option value="module">模块</option>
        </select>
        <button
          onClick={handleSearch}
          disabled={loading || !query.trim()}
          className="px-4 py-2 text-sm rounded-latte-md bg-latte-gold/10 border border-latte-gold/30 text-latte-gold hover:bg-latte-gold/20 disabled:opacity-50 disabled:hover:bg-latte-gold/10 transition-colors"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : "搜索"}
        </button>
      </div>

      {searched && !loading && results.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-latte-text-tertiary">
          <Search size={40} className="mb-3 opacity-40" />
          <p className="text-sm">未找到相关代码实体</p>
          <p className="text-xs mt-1">请先构建实体图谱并确保已生成嵌入</p>
        </div>
      )}

      <div className="space-y-2">
        {results.map((r) => (
          <div
            key={r.id}
            className="p-3 rounded-latte-lg border border-latte-border bg-latte-bg-tertiary/50 hover:bg-latte-bg-tertiary transition-colors"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2 min-w-0">
                {typeIcons[r.entity_type] || <FileCode size={14} />}
                <span className="font-medium text-sm text-latte-text-primary truncate">
                  {r.name}
                </span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded border ${
                    typeColors[r.entity_type] || "bg-latte-bg-secondary text-latte-text-secondary border-latte-border"
                  }`}
                >
                  {r.entity_type}
                </span>
              </div>
              <span className="text-[10px] text-latte-text-tertiary shrink-0">
                相似度 {(r.similarity * 100).toFixed(1)}%
              </span>
            </div>

            <div className="mt-1.5 text-xs text-latte-text-tertiary flex items-center gap-1">
              <FileCode size={11} />
              {r.file_path}:{r.start_line}
            </div>

            {r.signature && (
              <div className="mt-1 text-xs text-latte-text-secondary font-mono truncate">
                {r.signature}
              </div>
            )}

            {r.neighbors.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {r.neighbors.map((n) => (
                  <span
                    key={n.id}
                    className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded bg-latte-bg-secondary border border-latte-border text-latte-text-secondary"
                    title={`${n.file_path}`}
                  >
                    <Network size={9} />
                    {n.name}
                    <span className="text-latte-text-tertiary">({n.relation_type})</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
