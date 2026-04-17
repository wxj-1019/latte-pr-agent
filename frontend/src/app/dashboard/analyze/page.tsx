"use client";

import { useEffect, useRef, useState } from "react";
import { codeToHtml } from "shiki";
import { useAnalyze } from "@/hooks/use-analyze";
import { api } from "@/lib/api";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { FadeInUp } from "@/components/motion/fade-in-up";
import { FindingCard } from "@/components/ui/finding-card";
import { Sparkles } from "lucide-react";

const languages = [
  { value: "python", label: "Python" },
  { value: "javascript", label: "JavaScript" },
  { value: "typescript", label: "TypeScript" },
  { value: "java", label: "Java" },
  { value: "go", label: "Go" },
  { value: "rust", label: "Rust" },
  { value: "cpp", label: "C++" },
];

function ShikiEditor({
  code,
  onChange,
  language,
}: {
  code: string;
  onChange: (val: string) => void;
  language: string;
}) {
  const [highlighted, setHighlighted] = useState<string>("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    let mounted = true;
    codeToHtml(code, {
      lang: language,
      theme: "github-dark",
    }).then((html) => {
      if (mounted) setHighlighted(html);
    });
    return () => {
      mounted = false;
    };
  }, [code, language]);

  const handleScroll = () => {
    const pre = textareaRef.current?.nextElementSibling as HTMLPreElement | null;
    if (pre && textareaRef.current) {
      pre.scrollTop = textareaRef.current.scrollTop;
      pre.scrollLeft = textareaRef.current.scrollLeft;
    }
  };

  return (
    <div className="relative w-full h-full rounded-latte-md overflow-hidden bg-[#0d1117]">
      <textarea
        ref={textareaRef}
        value={code}
        onChange={(e) => onChange(e.target.value)}
        onScroll={handleScroll}
        spellCheck={false}
        className="absolute inset-0 z-10 w-full h-full p-4 font-mono text-sm text-transparent bg-transparent resize-none outline-none whitespace-pre"
        style={{ caretColor: "#c9d1d9", lineHeight: 1.5 }}
      />
      <pre
        className="absolute inset-0 z-0 w-full h-full p-4 m-0 font-mono text-sm overflow-auto pointer-events-none"
        style={{ lineHeight: 1.5 }}
        dangerouslySetInnerHTML={{ __html: highlighted }}
      />
    </div>
  );
}

export default function AnalyzePage() {
  const [code, setCode] = useState<string>("");
  const [language, setLanguage] = useState("python");
  const [filename, setFilename] = useState("example.py");
  const [repoId, setRepoId] = useState("direct/default");
  const [repos, setRepos] = useState<string[]>([]);
  const { analyze, isLoading, error, data } = useAnalyze();

  useEffect(() => {
    api.getRepos()
      .then((res) => setRepos(res.repos))
      .catch((err) => {
        console.error("Failed to load repos:", err);
        setRepos([]);
      });
  }, []);

  async function handleAnalyze() {
    if (!code.trim()) return;
    await analyze({ filename, content: code, language, repo_id: repoId });
  }

  return (
    <div className="max-w-7xl mx-auto h-[calc(100vh-8rem)]">
      <FadeInUp>
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-display font-semibold tracking-tight text-latte-text-primary flex items-center gap-2">
              <Sparkles size={22} className="text-latte-gold" />
              Code Analyze
            </h1>
            <p className="text-sm text-latte-text-tertiary mt-1">Paste code and get an instant AI review</p>
          </div>
          {data && (
            <Button variant="secondary" onClick={handleAnalyze} disabled={isLoading || !code.trim()}>
              {isLoading ? "Analyzing..." : "Re-analyze"}
            </Button>
          )}
        </div>
      </FadeInUp>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[calc(100%-5rem)]">
        <GlassCard className="p-0 h-full flex flex-col overflow-hidden" variant="elevated">
          <div className="flex items-center gap-3 p-4 border-b border-latte-text-primary/5 bg-latte-bg-secondary/50">
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="h-9 px-3 rounded-latte-md bg-latte-bg-tertiary text-sm text-latte-text-secondary border border-transparent focus:border-latte-gold/40 outline-none"
            >
              {languages.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </select>
            <Input
              value={filename}
              onChange={(e) => setFilename(e.target.value)}
              placeholder="filename"
              className="w-40 h-9 text-sm"
            />
            <select
              value={repoId}
              onChange={(e) => setRepoId(e.target.value)}
              className="h-9 px-3 rounded-latte-md bg-latte-bg-tertiary text-sm text-latte-text-secondary border border-transparent focus:border-latte-gold/40 outline-none flex-1 min-w-0"
            >
              <option value="direct/default">Default (no project config)</option>
              {repos.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-h-0 p-4">
            <ShikiEditor code={code} onChange={setCode} language={language} />
          </div>
          <div className="p-4 border-t border-latte-text-primary/5 bg-latte-bg-secondary/50">
            <Button onClick={handleAnalyze} disabled={isLoading || !code.trim()} className="w-full">
              {isLoading ? "Analyzing..." : "Start Analysis"}
            </Button>
          </div>
        </GlassCard>

        <GlassCard className="p-4 h-full overflow-hidden flex flex-col" variant="elevated">
          {!data && !isLoading && !error && (
            <div className="flex-1 flex flex-col items-center justify-center text-latte-text-tertiary">
              <Sparkles size={40} className="mb-3 opacity-50" />
              <p className="text-sm">Your review results will appear here</p>
            </div>
          )}

          {isLoading && !data && (
            <div className="flex-1 flex flex-col items-center justify-center text-latte-text-tertiary space-y-3">
              <div className="h-8 w-8 rounded-full border-2 border-latte-gold/30 border-t-latte-gold animate-spin" />
              <p className="text-sm">AI is reviewing your code...</p>
            </div>
          )}

          {error && !data && (
            <div className="flex-1 flex flex-col items-center justify-center text-latte-rose">
              <p className="text-sm font-medium">Analysis failed</p>
              <p className="text-xs mt-1 opacity-80">{error.message}</p>
            </div>
          )}

          {data && (
            <div className="h-full flex flex-col min-h-0">
              <div className="flex items-center justify-between mb-4 shrink-0">
                <div className="flex items-center gap-3">
                  <Badge
                    variant={
                      data.risk_level === "critical"
                        ? "critical"
                        : data.risk_level === "high"
                        ? "warning"
                        : data.risk_level === "medium"
                        ? "info"
                        : "success"
                    }
                    dot
                  >
                    {data.risk_level}
                  </Badge>
                  <span className="text-sm text-latte-text-secondary">
                    {data.findings.length} finding{data.findings.length !== 1 ? "s" : ""}
                  </span>
                </div>
              </div>
              {data.summary && (
                <p className="text-sm text-latte-text-secondary mb-4 shrink-0">{data.summary}</p>
              )}
              <div className="flex-1 overflow-auto pr-2 space-y-3 min-h-0">
                {data.findings.map((finding) => (
                  <FindingCard key={finding.id} finding={finding} />
                ))}
                {data.findings.length === 0 && (
                  <div className="text-sm text-latte-text-tertiary py-8 text-center">No issues found 🎉</div>
                )}
              </div>
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );
}
