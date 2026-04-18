"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { ChevronRight, ChevronDown, FileCode } from "lucide-react";
import type { PRFile, ReviewFinding } from "@/types";

interface FileTreeProps {
  files: PRFile[];
  findings: ReviewFinding[];
  selectedFile?: string;
  onSelectFile: (path: string) => void;
}

interface TreeNodeData {
  __isFile?: boolean;
  __path?: string;
  [key: string]: TreeNodeData | boolean | string | undefined;
}

function buildTree(paths: string[]): TreeNodeData {
  const root: TreeNodeData = {};
  paths.forEach((path) => {
    const parts = path.split("/");
    let current = root;
    parts.forEach((part, idx) => {
      if (!current[part]) {
        current[part] = { __isFile: idx === parts.length - 1, __path: path };
      }
      current = current[part] as TreeNodeData;
    });
  });
  return root;
}

function getFileSeverity(findings: ReviewFinding[], filePath: string) {
  const fileFindings = findings.filter((f) => f.file_path === filePath);
  if (fileFindings.some((f) => f.severity === "critical")) return "critical";
  if (fileFindings.some((f) => f.severity === "warning")) return "warning";
  if (fileFindings.some((f) => f.severity === "info")) return "info";
  return null;
}

function getFileFindingCount(findings: ReviewFinding[], filePath: string) {
  return findings.filter((f) => f.file_path === filePath).length;
}

function TreeNode({
  name,
  node,
  findings,
  selectedFile,
  onSelectFile,
  depth = 0,
}: {
  name: string;
  node: TreeNodeData;
  findings: ReviewFinding[];
  selectedFile?: string;
  onSelectFile: (path: string) => void;
  depth?: number;
}) {
  const isFile = node.__isFile;
  const path = node.__path;
  const [expanded, setExpanded] = useState(true);
  const children = Object.entries(node).filter(([k]) => !k.startsWith("__"));

  if (isFile && path) {
    const severity = getFileSeverity(findings, path);
    const count = getFileFindingCount(findings, path);
    const isSelected = selectedFile === path;

    return (
      <button
        onClick={() => onSelectFile(path)}
        className={cn(
          "w-full flex items-center justify-between py-1.5 px-2 rounded-latte-md text-sm transition-colors",
          isSelected
            ? "bg-latte-gold/10 text-latte-gold"
            : "text-latte-text-secondary hover:bg-latte-bg-tertiary hover:text-latte-text-primary"
        )}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <FileCode size={14} className="shrink-0 text-latte-text-tertiary" />
          <span className="truncate">{name}</span>
        </div>
        {count > 0 && (
          <div className="flex items-center gap-1.5 shrink-0">
            {severity && (
              <span
                className={cn("h-1.5 w-1.5 rounded-full", {
                  "bg-latte-critical": severity === "critical",
                  "bg-latte-warning": severity === "warning",
                  "bg-latte-info": severity === "info",
                })}
              />
            )}
            <span className="text-xs text-latte-text-muted">{count}</span>
          </div>
        )}
      </button>
    );
  }

  return (
    <div>
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-1 py-1.5 px-2 text-sm text-latte-text-secondary hover:text-latte-text-primary transition-colors"
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span>{name}</span>
      </button>
      {expanded && (
        <div>
          {children.map(([childName, childNode]) => (
            <TreeNode
              key={childName}
              name={childName}
              node={childNode as TreeNodeData}
              findings={findings}
              selectedFile={selectedFile}
              onSelectFile={onSelectFile}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function FileTree({ files, findings, selectedFile, onSelectFile }: FileTreeProps) {
  const paths = files.map((f) => f.file_path);
  const tree = buildTree(paths);

  return (
    <div className="h-full overflow-auto pr-2">
      <h3 className="text-sm font-semibold text-latte-text-primary mb-3 px-2">文件</h3>
      <div className="space-y-0.5">
        {Object.entries(tree).map(([name, node]) => (
          <TreeNode
            key={name}
            name={name}
            node={node as TreeNodeData}
            findings={findings}
            selectedFile={selectedFile}
            onSelectFile={onSelectFile}
          />
        ))}
      </div>
    </div>
  );
}
