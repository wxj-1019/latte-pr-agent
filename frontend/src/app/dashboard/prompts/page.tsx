"use client";

import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FadeInUp } from "@/components/motion/fade-in-up";
import { usePrompts } from "@/hooks/use-prompts";
import { Check, FlaskConical } from "lucide-react";

export default function PromptsPage() {
  const { prompts, isLoading } = usePrompts();

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <FadeInUp>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-display font-semibold tracking-tight text-latte-text-primary">
              Prompt Registry
            </h1>
            <p className="text-sm text-latte-text-tertiary mt-1">
              Manage prompt versions and A/B experiments
            </p>
          </div>
          <Button variant="secondary">
            <Check size={16} />
            New Version
          </Button>
        </div>
      </FadeInUp>

      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="h-32 bg-latte-bg-secondary rounded-latte-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {prompts.map((prompt, index) => (
            <FadeInUp key={prompt.id} delay={index * 0.1}>
              <GlassCard className="p-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-medium text-latte-text-primary">
                        {prompt.version}
                      </h3>
                      {prompt.is_active && (
                        <Badge variant="success" dot>
                          active
                        </Badge>
                      )}
                      {prompt.is_baseline && (
                        <Badge variant="info" dot>
                          baseline
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-4 mt-2 text-sm text-latte-text-tertiary">
                      <span>Used in {prompt.repo_count} repos</span>
                      <span>·</span>
                      <span>Accuracy {Math.round((prompt.accuracy || 0) * 100)}%</span>
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
                    <Button variant="ghost" size="sm">
                      Edit
                    </Button>
                    <Button variant="secondary" size="sm">
                      Test
                    </Button>
                  </div>
                </div>
              </GlassCard>
            </FadeInUp>
          ))}
        </div>
      )}
    </div>
  );
}
