"use client";

import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import {
  Network,
  Box,
  LayoutGrid,
  Cpu,
  RefreshCw,
  Search,
  X,
  GitBranch,
  Route,
} from "lucide-react";
import EntityDetailCard from "./entity-detail-card";

interface GraphNode {
  id: string;
  group: string;
  name?: string;
  type?: string;
}

interface GraphData {
  nodes: GraphNode[];
  edges: Array<{ source: string; target: string; type?: string; count?: number }>;
}

interface KnowledgeGraphResponse {
  file_graph: GraphData;
  module_graph: GraphData;
}

interface EntityGraphResponse {
  nodes: Array<{
    id: string;
    name: string;
    type: string;
    file: string;
    group: string;
    start_line: number;
    end_line: number;
  }>;
  edges: Array<{
    source: string;
    target: string | null;
    type: string;
    source_file: string;
    target_file: string | null;
  }>;
}

const colorPalette = [
  "#E8B86D", "#C75B5B", "#5B8DBE", "#7ABF5E", "#B085C7",
  "#5BC0BE", "#D4A373", "#8FB996", "#C9ADA7", "#A8DADC",
];

const entityTypeColors: Record<string, string> = {
  function: "#5B8DBE",
  class: "#C75B5B",
  interface: "#7ABF5E",
  module: "#B085C7",
};

function getGroupColor(group: string) {
  const fixed = entityTypeColors[group];
  if (fixed) return fixed;
  let hash = 0;
  for (let i = 0; i < group.length; i++) {
    hash = group.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colorPalette[Math.abs(hash) % colorPalette.length];
}

function computeShortestPath(graph: GraphData, start: string, end: string): string[] {
  if (start === end) return [start];
  const adj = new Map<string, string[]>();
  graph.edges.forEach((e) => {
    if (!adj.has(e.source)) adj.set(e.source, []);
    if (!adj.has(e.target)) adj.set(e.target, []);
    adj.get(e.source)!.push(e.target);
    adj.get(e.target)!.push(e.source);
  });
  const queue: Array<[string, string[]]> = [[start, [start]]];
  const visited = new Set<string>([start]);
  while (queue.length) {
    const [node, path] = queue.shift()!;
    for (const neighbor of adj.get(node) || []) {
      if (visited.has(neighbor)) continue;
      const newPath = [...path, neighbor];
      if (neighbor === end) return newPath;
      visited.add(neighbor);
      queue.push([neighbor, newPath]);
    }
  }
  return [];
}

function ForceGraphCanvas({
  data,
  highlightedNodes,
  highlightedEdges,
  onNodeClick,
  selectedNode,
}: {
  data: GraphData;
  highlightedNodes?: Set<string>;
  highlightedEdges?: Set<string>;
  onNodeClick?: (id: string) => void;
  selectedNode?: string | null;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);

  const nodes = useMemo(() => {
    const map = new Map<string, { x: number; y: number; vx: number; vy: number }>();
    const width = 800;
    const height = 500;
    data.nodes.forEach((n) => {
      map.set(n.id, {
        x: Math.random() * width,
        y: Math.random() * height,
        vx: 0,
        vy: 0,
      });
    });
    for (let iter = 0; iter < 200; iter++) {
      const ids = Array.from(map.keys());
      for (let i = 0; i < ids.length; i++) {
        for (let j = i + 1; j < ids.length; j++) {
          const a = map.get(ids[i])!;
          const b = map.get(ids[j])!;
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const force = 2000 / (dist * dist);
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          a.vx += fx;
          a.vy += fy;
          b.vx -= fx;
          b.vy -= fy;
        }
      }
      data.edges.forEach((e) => {
        const a = map.get(e.source);
        const b = map.get(e.target);
        if (!a || !b) return;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = dist * 0.001;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        a.vx += fx;
        a.vy += fy;
        b.vx -= fx;
        b.vy -= fy;
      });
      ids.forEach((id) => {
        const n = map.get(id)!;
        n.vx += (width / 2 - n.x) * 0.0005;
        n.vy += (height / 2 - n.y) * 0.0005;
        n.vx *= 0.9;
        n.vy *= 0.9;
        n.x += n.vx;
        n.y += n.vy;
        n.x = Math.max(20, Math.min(width - 20, n.x));
        n.y = Math.max(20, Math.min(height - 20, n.y));
      });
    }
    return map;
  }, [data]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const width = 800;
    const height = 500;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);

    data.edges.forEach((e) => {
      const a = nodes.get(e.source);
      const b = nodes.get(e.target);
      if (!a || !b) return;
      const edgeKey = `${e.source}|${e.target}`;
      const isHighlighted = highlightedEdges?.has(edgeKey);
      ctx.beginPath();
      ctx.moveTo(a.x * scale + offset.x, a.y * scale + offset.y);
      ctx.lineTo(b.x * scale + offset.x, b.y * scale + offset.y);
      ctx.strokeStyle = isHighlighted
        ? "rgba(232, 184, 109, 0.8)"
        : "rgba(200, 200, 200, 0.25)";
      ctx.lineWidth = isHighlighted ? 2.5 : 1;
      ctx.stroke();
    });

    data.nodes.forEach((n) => {
      const pos = nodes.get(n.id);
      if (!pos) return;
      const x = pos.x * scale + offset.x;
      const y = pos.y * scale + offset.y;
      const isHovered = hoveredNode === n.id;
      const isSelected = selectedNode === n.id;
      const isHighlighted = highlightedNodes?.has(n.id);
      const radius = isSelected ? 12 : isHovered ? 10 : 6;
      const color = getGroupColor(n.group);

      if (isHighlighted || isSelected) {
        ctx.beginPath();
        ctx.arc(x, y, radius + 4, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(232, 184, 109, 0.2)";
        ctx.fill();
      }

      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = isSelected ? "#E8B86D" : isHovered ? "#fff" : "rgba(255,255,255,0.3)";
      ctx.lineWidth = isSelected ? 3 : isHovered ? 2 : 1;
      ctx.stroke();

      if (isHovered || isSelected || data.nodes.length < 30 || isHighlighted) {
        ctx.fillStyle = "#e2e8f0";
        ctx.font = isHovered || isSelected ? "12px sans-serif" : "10px sans-serif";
        ctx.textAlign = "center";
        const label = n.name || n.id.split("/").pop() || n.id;
        ctx.fillText(label, x, y + radius + 14);
      }
    });
  }, [nodes, data, scale, offset, hoveredNode, selectedNode, highlightedNodes, highlightedEdges]);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (isDragging) {
        setOffset((prev) => ({
          x: prev.x + e.movementX,
          y: prev.y + e.movementY,
        }));
        return;
      }
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const mx = (e.clientX - rect.left - offset.x) / scale;
      const my = (e.clientY - rect.top - offset.y) / scale;

      let closest: string | null = null;
      let minDist = Infinity;
      data.nodes.forEach((n) => {
        const pos = nodes.get(n.id);
        if (!pos) return;
        const d = Math.sqrt((pos.x - mx) ** 2 + (pos.y - my) ** 2);
        if (d < minDist && d < 15) {
          minDist = d;
          closest = n.id;
        }
      });
      setHoveredNode(closest);
    },
    [nodes, data, scale, offset, isDragging]
  );

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    setScale((prev) => Math.max(0.3, Math.min(3, prev - e.deltaY * 0.001)));
  }, []);

  const handleClick = useCallback(() => {
    if (hoveredNode && onNodeClick) {
      onNodeClick(hoveredNode);
    }
  }, [hoveredNode, onNodeClick]);

  const hoveredNodeData = useMemo(() => {
    if (!hoveredNode) return null;
    return data.nodes.find((n) => n.id === hoveredNode) || null;
  }, [hoveredNode, data]);

  return (
    <div className="relative">
      <canvas
        ref={canvasRef}
        width={800}
        height={500}
        className="rounded-latte-lg cursor-grab active:cursor-grabbing"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => { setHoveredNode(null); setIsDragging(false); }}
        onWheel={handleWheel}
        onMouseDown={() => setIsDragging(true)}
        onMouseUp={() => setIsDragging(false)}
        onClick={handleClick}
      />
      {hoveredNodeData && (
        <div className="absolute top-2 left-2 px-3 py-1.5 rounded-latte-md bg-latte-bg-tertiary/90 border border-latte-border text-xs text-latte-text-secondary max-w-xs">
          <div className="font-medium text-latte-text-primary">
            {hoveredNodeData.name || hoveredNodeData.id}
          </div>
          {hoveredNodeData.type && (
            <div className="text-latte-text-tertiary mt-0.5">{hoveredNodeData.type}</div>
          )}
        </div>
      )}
      <div className="absolute bottom-2 right-2 flex items-center gap-2">
        <button
          onClick={() => setScale((s) => Math.min(3, s + 0.2))}
          className="w-7 h-7 rounded-latte-md bg-latte-bg-tertiary/80 border border-latte-border text-latte-text-secondary hover:text-latte-text-primary text-sm"
        >
          +
        </button>
        <button
          onClick={() => setScale((s) => Math.max(0.3, s - 0.2))}
          className="w-7 h-7 rounded-latte-md bg-latte-bg-tertiary/80 border border-latte-border text-latte-text-secondary hover:text-latte-text-primary text-sm"
        >
          −
        </button>
      </div>
    </div>
  );
}

export default function KnowledgeGraphPanel({ projectId }: { projectId: number }) {
  const [data, setData] = useState<KnowledgeGraphResponse | null>(null);
  const [entityData, setEntityData] = useState<EntityGraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [entityLoading, setEntityLoading] = useState(false);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"module" | "file" | "entity">("module");

  // Filters
  const [entityTypeFilter, setEntityTypeFilter] = useState<string>("all");
  const [relationTypeFilter, setRelationTypeFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Interaction
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [nodeDetail, setNodeDetail] = useState<any>(null);
  const [pathMode, setPathMode] = useState(false);
  const [pathNodes, setPathNodes] = useState<string[]>([]);
  const [highlightedPath, setHighlightedPath] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getKnowledgeGraph(projectId)
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "加载失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    if (viewMode !== "entity") return;
    if (entityData) return;
    let cancelled = false;
    setEntityLoading(true);
    api
      .getEntityGraph(projectId)
      .then((res) => {
        if (!cancelled) setEntityData(res);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setEntityLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [viewMode, projectId, entityData]);

  const rawGraph = useMemo<GraphData | null>(() => {
    if (!data) return null;
    if (viewMode === "module") return data.module_graph;
    if (viewMode === "file") return data.file_graph;
    if (!entityData) return null;
    return {
      nodes: entityData.nodes.map((n) => ({
        id: n.id,
        group: n.type,
        name: n.name,
        type: n.type,
      })),
      edges: entityData.edges
        .filter((e) => e.target !== null)
        .map((e) => ({
          source: e.source,
          target: e.target as string,
          type: e.type,
        })),
    };
  }, [data, viewMode, entityData]);

  const currentGraph = useMemo<GraphData | null>(() => {
    if (!rawGraph) return null;
    let nodes = rawGraph.nodes;
    let edges = rawGraph.edges;

    if (viewMode === "entity") {
      if (entityTypeFilter !== "all") {
        nodes = nodes.filter((n) => n.type === entityTypeFilter);
        const nodeIds = new Set(nodes.map((n) => n.id));
        edges = edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));
      }
      if (relationTypeFilter !== "all") {
        edges = edges.filter((e) => e.type === relationTypeFilter);
        const connectedIds = new Set<string>();
        edges.forEach((e) => {
          connectedIds.add(e.source);
          connectedIds.add(e.target);
        });
        nodes = nodes.filter((n) => connectedIds.has(n.id));
      }
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matched = new Set(nodes.filter((n) => (n.name || n.id).toLowerCase().includes(q)).map((n) => n.id));
      // Include direct neighbors of matched nodes
      edges.forEach((e) => {
        if (matched.has(e.source)) matched.add(e.target);
        if (matched.has(e.target)) matched.add(e.source);
      });
      nodes = nodes.filter((n) => matched.has(n.id));
      edges = edges.filter((e) => matched.has(e.source) && matched.has(e.target));
    }

    return { nodes, edges };
  }, [rawGraph, viewMode, entityTypeFilter, relationTypeFilter, searchQuery]);

  const highlightedNodes = useMemo(() => {
    if (!highlightedPath.length) return undefined;
    return new Set(highlightedPath);
  }, [highlightedPath]);

  const highlightedEdges = useMemo(() => {
    if (!highlightedPath.length) return undefined;
    const set = new Set<string>();
    for (let i = 0; i < highlightedPath.length - 1; i++) {
      set.add(`${highlightedPath[i]}|${highlightedPath[i + 1]}`);
      set.add(`${highlightedPath[i + 1]}|${highlightedPath[i]}`);
    }
    return set;
  }, [highlightedPath]);

  const handleNodeClick = useCallback(
    async (nodeId: string) => {
      if (pathMode) {
        const newPath = [...pathNodes, nodeId];
        if (newPath.length === 2) {
          const path = computeShortestPath(currentGraph || { nodes: [], edges: [] }, newPath[0], newPath[1]);
          setHighlightedPath(path);
          setPathNodes([]);
        } else {
          setPathNodes(newPath);
        }
        return;
      }

      setSelectedNode(nodeId);
      if (viewMode === "entity" && entityData) {
        try {
          const detail = await api.getEntityNeighbors(projectId, parseInt(nodeId));
          setNodeDetail(detail);
        } catch {
          setNodeDetail(null);
        }
      } else {
        setNodeDetail(null);
      }
    },
    [pathMode, pathNodes, currentGraph, viewMode, entityData, projectId]
  );

  const handleBuild = async () => {
    setBuilding(true);
    try {
      await api.buildEntityGraph(projectId);
      const graph = await api.getEntityGraph(projectId);
      setEntityData(graph);
    } catch (err) {
      setError(err instanceof Error ? err.message : "构建失败");
    } finally {
      setBuilding(false);
    }
  };

  const clearPath = () => {
    setPathMode(false);
    setPathNodes([]);
    setHighlightedPath([]);
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
        <Network size={40} className="mb-3 opacity-40" />
        <p className="text-sm">{error}</p>
      </div>
    );
  }

  const isEntityEmpty = viewMode === "entity" && (!entityData || entityData.nodes.length === 0) && !entityLoading;
  const isGraphEmpty = !currentGraph || currentGraph.nodes.length === 0;

  if (isGraphEmpty && !isEntityEmpty) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-latte-text-tertiary">
        <Network size={48} className="mb-4 opacity-40" />
        <p className="text-lg font-medium">暂无图谱数据</p>
        <p className="text-sm mt-1">请先同步项目代码以生成依赖图</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode("module")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-latte-md border transition-colors ${
              viewMode === "module"
                ? "bg-latte-gold/10 border-latte-gold/30 text-latte-gold"
                : "bg-latte-bg-tertiary border-latte-border text-latte-text-secondary hover:text-latte-text-primary"
            }`}
          >
            <LayoutGrid size={13} />
            模块视图
          </button>
          <button
            onClick={() => setViewMode("file")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-latte-md border transition-colors ${
              viewMode === "file"
                ? "bg-latte-gold/10 border-latte-gold/30 text-latte-gold"
                : "bg-latte-bg-tertiary border-latte-border text-latte-text-secondary hover:text-latte-text-primary"
            }`}
          >
            <Box size={13} />
            文件视图
          </button>
          <button
            onClick={() => setViewMode("entity")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-latte-md border transition-colors ${
              viewMode === "entity"
                ? "bg-latte-gold/10 border-latte-gold/30 text-latte-gold"
                : "bg-latte-bg-tertiary border-latte-border text-latte-text-secondary hover:text-latte-text-primary"
            }`}
          >
            <Cpu size={13} />
            实体视图
          </button>
        </div>

        {viewMode === "entity" && (
          <>
            <div className="h-4 w-px bg-latte-border mx-1" />
            <select
              value={entityTypeFilter}
              onChange={(e) => setEntityTypeFilter(e.target.value)}
              className="px-2 py-1.5 text-xs rounded-latte-md bg-latte-bg-tertiary border border-latte-border text-latte-text-secondary focus:outline-none"
            >
              <option value="all">全部类型</option>
              <option value="function">函数</option>
              <option value="class">类</option>
            </select>
            <select
              value={relationTypeFilter}
              onChange={(e) => setRelationTypeFilter(e.target.value)}
              className="px-2 py-1.5 text-xs rounded-latte-md bg-latte-bg-tertiary border border-latte-border text-latte-text-secondary focus:outline-none"
            >
              <option value="all">全部关系</option>
              <option value="calls">调用</option>
              <option value="inherits">继承</option>
              <option value="decorates">装饰器</option>
            </select>
            <div className="relative">
              <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-latte-text-tertiary" />
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索实体..."
                className="pl-7 pr-2 py-1.5 text-xs rounded-latte-md bg-latte-bg-tertiary border border-latte-border text-latte-text-primary placeholder:text-latte-text-tertiary focus:outline-none w-40"
              />
              {searchQuery && (
                <button onClick={() => setSearchQuery("")} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-latte-text-tertiary">
                  <X size={10} />
                </button>
              )}
            </div>
            <button
              onClick={() => {
                if (pathMode) clearPath();
                else { setPathMode(true); setSelectedNode(null); setNodeDetail(null); }
              }}
              className={`flex items-center gap-1 px-2 py-1.5 text-xs rounded-latte-md border transition-colors ${
                pathMode
                  ? "bg-latte-gold/10 border-latte-gold/30 text-latte-gold"
                  : "bg-latte-bg-tertiary border-latte-border text-latte-text-secondary hover:text-latte-text-primary"
              }`}
              title="点击两个节点查看最短路径"
            >
              <Route size={12} />
              {pathMode ? "选择节点中..." : "路径"}
            </button>
            {pathMode && (
              <button onClick={clearPath} className="text-[10px] text-latte-text-tertiary hover:text-latte-text-primary">
                取消
              </button>
            )}
          </>
        )}

        <div className="flex-1" />

        {viewMode === "entity" && (
          <button
            onClick={handleBuild}
            disabled={building}
            className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-latte-md border border-latte-border bg-latte-bg-tertiary text-latte-text-secondary hover:text-latte-text-primary disabled:opacity-50 transition-colors"
          >
            {building ? <RefreshCw size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            {building ? "构建中..." : "构建实体图谱"}
          </button>
        )}
        <p className="text-xs text-latte-text-tertiary">
          {currentGraph ? `${currentGraph.nodes.length} 节点 · ${currentGraph.edges.length} 边` : "—"}
        </p>
      </div>

      {isEntityEmpty ? (
        <div className="flex flex-col items-center justify-center py-16 text-latte-text-tertiary">
          <Cpu size={48} className="mb-4 opacity-40" />
          <p className="text-lg font-medium">暂无实体图谱数据</p>
          <p className="text-sm mt-1 mb-4">点击上方「构建实体图谱」按钮开始扫描代码实体</p>
          <button
            onClick={handleBuild}
            disabled={building}
            className="flex items-center gap-2 px-4 py-2 text-sm rounded-latte-md bg-latte-gold/10 border border-latte-gold/30 text-latte-gold hover:bg-latte-gold/20 disabled:opacity-50 transition-colors"
          >
            {building ? <RefreshCw size={14} className="animate-spin" /> : <Cpu size={14} />}
            {building ? "构建中..." : "构建实体图谱"}
          </button>
        </div>
      ) : (
        <div className="flex gap-4">
          <div className="flex-1 overflow-auto rounded-latte-xl border border-latte-border bg-latte-bg-secondary/50">
            {currentGraph && (
              <ForceGraphCanvas
                data={currentGraph}
                highlightedNodes={highlightedNodes}
                highlightedEdges={highlightedEdges}
                onNodeClick={handleNodeClick}
                selectedNode={selectedNode}
              />
            )}
          </div>
          {nodeDetail && nodeDetail.entity && (
            <EntityDetailCard
              entity={nodeDetail.entity}
              incoming={nodeDetail.incoming || []}
              outgoing={nodeDetail.outgoing || []}
              onClose={() => {
                setSelectedNode(null);
                setNodeDetail(null);
              }}
            />
          )}
        </div>
      )}

      {highlightedPath.length > 0 && (
        <div className="flex items-center gap-2 text-xs text-latte-text-secondary">
          <GitBranch size={12} className="text-latte-gold" />
          <span>最短路径: {highlightedPath.length} 个节点</span>
          <button onClick={clearPath} className="text-latte-text-tertiary hover:text-latte-text-primary">
            清除
          </button>
        </div>
      )}
    </div>
  );
}
