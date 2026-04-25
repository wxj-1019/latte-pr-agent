"use client";

import { X, FileCode, FunctionSquare, Box, Network, GitCommit } from "lucide-react";

interface EntityDetail {
  id: number;
  name: string;
  type: string;
  file: string;
  start_line: number;
  end_line: number;
  signature?: string;
  meta?: Record<string, unknown>;
}

interface Neighbor {
  relation_id: number;
  relation_type: string;
  source_entity?: { id: number; name: string; type: string; file: string };
  target_entity?: { id: number; name: string; type: string; file: string };
  meta?: Record<string, unknown>;
}

interface EntityDetailCardProps {
  entity: EntityDetail;
  incoming: Neighbor[];
  outgoing: Neighbor[];
  onClose: () => void;
}

const typeIcons: Record<string, React.ReactNode> = {
  function: <FunctionSquare size={14} className="text-latte-info" />,
  class: <Box size={14} className="text-latte-critical" />,
  interface: <FileCode size={14} className="text-latte-success" />,
  module: <Network size={14} className="text-latte-warning" />,
};

const typeLabels: Record<string, string> = {
  function: "函数",
  class: "类",
  interface: "接口",
  module: "模块",
};

export default function EntityDetailCard({ entity, incoming, outgoing, onClose }: EntityDetailCardProps) {
  return (
    <div className="w-80 shrink-0 rounded-latte-xl border border-latte-border bg-latte-bg-tertiary/95 backdrop-blur p-4 space-y-3 max-h-[600px] overflow-auto">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {typeIcons[entity.type] || <FileCode size={14} />}
          <h4 className="font-semibold text-sm text-latte-text-primary truncate">{entity.name}</h4>
        </div>
        <button
          onClick={onClose}
          className="shrink-0 text-latte-text-tertiary hover:text-latte-text-primary transition-colors"
        >
          <X size={14} />
        </button>
      </div>

      <div className="text-[11px] text-latte-text-tertiary flex items-center gap-1">
        <GitCommit size={11} />
        {entity.file}:{entity.start_line}-{entity.end_line}
      </div>

      {entity.signature && (
        <div className="text-xs font-mono text-latte-text-secondary bg-latte-bg-secondary p-2 rounded-latte-md border border-latte-border truncate">
          {entity.signature}
        </div>
      )}

      {entity.meta && Object.keys(entity.meta).length > 0 && (
        <div className="space-y-1">
          <p className="text-[11px] font-medium text-latte-text-secondary">元数据</p>
          {Object.entries(entity.meta).map(([k, v]) => (
            <div key={k} className="text-[11px] text-latte-text-tertiary">
              {k}: {Array.isArray(v) ? v.join(", ") : String(v)}
            </div>
          ))}
        </div>
      )}

      {outgoing.length > 0 && (
        <div className="space-y-1">
          <p className="text-[11px] font-medium text-latte-text-secondary">调用/ outgoing ({outgoing.length})</p>
          <div className="space-y-1">
            {outgoing.map((o) => (
              <div key={o.relation_id} className="text-[11px] text-latte-text-tertiary flex items-center gap-1">
                <Network size={9} />
                <span className="text-latte-text-secondary">{o.target_entity?.name}</span>
                <span>({o.relation_type})</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {incoming.length > 0 && (
        <div className="space-y-1">
          <p className="text-[11px] font-medium text-latte-text-secondary">被调用 / incoming ({incoming.length})</p>
          <div className="space-y-1">
            {incoming.map((i) => (
              <div key={i.relation_id} className="text-[11px] text-latte-text-tertiary flex items-center gap-1">
                <Network size={9} />
                <span className="text-latte-text-secondary">{i.source_entity?.name}</span>
                <span>({i.relation_type})</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
