"use client";

import { useEffect, useMemo, useState } from "react";
import { codeToHtml } from "shiki";
import { cn } from "@/lib/utils";
import { escapeHtml } from "@/lib/security";
import type { PRFile, ReviewFinding } from "@/types";

interface DiffViewerProps {
  file: PRFile;
  findings: ReviewFinding[];
  onLineClick?: (lineNum: number, filePath: string) => void;
  selectedLine?: { line: number; file: string };
}

interface DiffLine {
  oldNum?: number;
  newNum?: number;
  content: string;
  type: "context" | "add" | "remove" | "header";
}

function parseDiff(diffContent: string): DiffLine[] {
  const lines: DiffLine[] = [];
  let oldLine = 0;
  let newLine = 0;

  diffContent.split("\n").forEach((rawLine) => {
    const line = rawLine.replace(/\r/g, "");
    if (line.startsWith("@@")) {
      const match = line.match(/@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@/);
      if (match) {
        oldLine = parseInt(match[1], 10) - 1;
        newLine = parseInt(match[3], 10) - 1;
      }
      lines.push({ content: line, type: "header" });
    } else if (line.startsWith("+")) {
      newLine++;
      lines.push({ newNum: newLine, content: line.slice(1), type: "add" });
    } else if (line.startsWith("-")) {
      oldLine++;
      lines.push({ oldNum: oldLine, content: line.slice(1), type: "remove" });
    } else {
      oldLine++;
      newLine++;
      lines.push({ oldNum: oldLine, newNum: newLine, content: line, type: "context" });
    }
  });

  return lines;
}

function inferLanguage(filePath: string): string {
  const ext = filePath.split(".").pop()?.toLowerCase();
  const map: Record<string, string> = {
    py: "python",
    js: "javascript",
    ts: "typescript",
    tsx: "tsx",
    jsx: "jsx",
    java: "java",
    go: "go",
    rs: "rust",
    cpp: "cpp",
    cc: "cpp",
    hpp: "cpp",
    c: "c",
    h: "c",
    rb: "ruby",
    php: "php",
    json: "json",
    yml: "yaml",
    yaml: "yaml",
    md: "markdown",
    sh: "bash",
    dockerfile: "dockerfile",
    sql: "sql",
    html: "html",
    css: "css",
    scss: "scss",
  };
  return map[ext || ""] || "text";
}

async function highlightDiff(lines: DiffLine[], lang: string): Promise<(string | null)[]> {
  const result: (string | null)[] = new Array(lines.length).fill(null);
  const codeLines = lines.filter((l) => l.type !== "header");
  if (codeLines.length === 0) return result;

  const codeBlock = codeLines.map((l) => l.content).join("\n");
  const html = await codeToHtml(codeBlock, {
    lang,
    theme: "github-dark",
  });

  const parser = new DOMParser();
  const doc = parser.parseFromString(html, "text/html");
  const lineSpans = doc.querySelectorAll(".line");

  let hlIdx = 0;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].type !== "header" && hlIdx < lineSpans.length) {
      result[i] = lineSpans[hlIdx].innerHTML;
      hlIdx++;
    }
  }

  return result;
}

export function DiffViewer({ file, findings, onLineClick, selectedLine }: DiffViewerProps) {
  const lines = useMemo(() => parseDiff(file.diff_content || ""), [file.diff_content]);
  const fileFindings = findings.filter((f) => f.file_path === file.file_path);
  const findingMap = new Map<number, ReviewFinding>();
  fileFindings.forEach((f) => {
    if (f.line_number !== undefined) {
      findingMap.set(f.line_number, f);
    }
  });

  const [highlightedLines, setHighlightedLines] = useState<(string | null)[]>([]);
  const [highlightReady, setHighlightReady] = useState(false);

  useEffect(() => {
    let mounted = true;
    const lang = inferLanguage(file.file_path);

    highlightDiff(lines, lang)
      .then((result) => {
        if (mounted) {
          setHighlightedLines(result);
          setHighlightReady(true);
        }
      })
      .catch(() => {
        if (mounted) setHighlightReady(true);
      });

    return () => {
      mounted = false;
    };
  }, [lines, file.file_path]);

  return (
    <div className="rounded-latte-xl bg-latte-bg-deep border border-latte-text-primary/5 overflow-hidden">
      <div className="px-4 py-3 border-b border-latte-text-primary/5 flex items-center justify-between bg-latte-bg-secondary">
        <div className="text-sm font-medium text-latte-text-primary truncate">{file.file_path}</div>
        <div className="flex items-center gap-3 text-xs text-latte-text-tertiary">
          <span className="text-latte-success">+{file.additions}</span>
          <span className="text-latte-critical">-{file.deletions}</span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm font-mono">
          <tbody>
            {lines.map((line, idx) => {
              if (line.type === "header") {
                return (
                  <tr key={idx} className="bg-latte-bg-tertiary/50">
                    <td colSpan={4} className="px-4 py-1 text-latte-text-muted">
                      {line.content}
                    </td>
                  </tr>
                );
              }

              const lineNum = line.newNum || line.oldNum || 0;
              const finding = findingMap.get(lineNum);
              const hasFinding = !!finding;
              const isSelected = selectedLine?.file === file.file_path && selectedLine?.line === lineNum;

              const highlightedHtml = highlightReady ? highlightedLines[idx] : null;

              return (
                <tr
                  key={idx}
                  className={cn(
                    "group",
                    line.type === "add" && "bg-latte-success/5",
                    line.type === "remove" && "bg-latte-critical/5",
                    isSelected && "bg-latte-gold/10"
                  )}
                >
                  <td
                    className={cn(
                      "pl-4 pr-2 py-0.5 text-right text-latte-text-muted select-none w-12",
                      line.type === "remove" && "text-latte-rose/60"
                    )}
                  >
                    {line.oldNum ?? ""}
                  </td>
                  <td
                    onClick={() => onLineClick?.(lineNum, file.file_path)}
                    className={cn(
                      "relative pr-2 py-0.5 text-right text-latte-text-muted select-none cursor-pointer w-12",
                      "hover:text-latte-text-primary hover:bg-latte-bg-tertiary",
                      hasFinding && "border-r-2 border-latte-gold text-latte-gold"
                    )}
                  >
                    {line.newNum ?? ""}
                    {finding && (
                      <div className="absolute left-full top-1/2 -translate-y-1/2 ml-2 z-10 hidden group-hover:block w-56">
                        <div className="latte-glass p-3 text-left rounded-latte-md">
                          <p className="text-xs font-semibold text-latte-text-primary mb-1">
                            {finding.severity.toUpperCase()}
                          </p>
                          <p className="text-xs text-latte-text-secondary line-clamp-3">
                            {finding.description}
                          </p>
                        </div>
                      </div>
                    )}
                  </td>
                  <td className={cn(
                    "w-6 text-center text-xs select-none",
                    line.type === "add" && "text-latte-success",
                    line.type === "remove" && "text-latte-rose",
                    line.type === "context" && "text-latte-text-muted/40"
                  )}>
                    {line.type === "add" ? "+" : line.type === "remove" ? "−" : " "}
                  </td>
                  <td
                    className={cn(
                      "px-3 py-0.5 whitespace-pre",
                      line.type === "add" && "text-latte-success",
                      line.type === "remove" && "text-latte-rose",
                      line.type === "context" && "text-latte-text-secondary"
                    )}
                  >
                    {highlightedHtml !== null ? (
                      <span
                        dangerouslySetInnerHTML={{
                          __html: highlightedHtml || " ",
                        }}
                      />
                    ) : (
                      <span>{escapeHtml(line.content) || " "}</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
