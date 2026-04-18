"use client";

import { motion } from "framer-motion";
import { GlassCard } from "@/components/ui/glass-card";
import { Brain, Network, ShieldCheck, Gauge, RefreshCw, Share2 } from "lucide-react";

const features = [
  {
    id: "multi-model",
    title: "多模型智能",
    description: "主模型初筛，Reasoner 复核，自动降级永不掉线。",
    size: "large",
    icon: Brain,
  },
  {
    id: "context",
    title: "上下文感知分析",
    description: "Tree-sitter 解析 + 依赖图构建，审查不再是盲人摸象。",
    size: "small",
    icon: Network,
  },
  {
    id: "static",
    title: "静态分析融合",
    description: "AI 与 Semgrep 结果智能合并，去重、互补。",
    size: "small",
    icon: ShieldCheck,
  },
  {
    id: "quality",
    title: "质量门禁",
    description: "Critical 风险自动阻塞合并，为代码质量守门。",
    size: "small",
    icon: Gauge,
  },
  {
    id: "feedback",
    title: "反馈闭环",
    description: "开发者标记误报，Prompt A/B 测试，越用越聪明。",
    size: "small",
    icon: RefreshCw,
  },
  {
    id: "cross",
    title: "跨服务影响",
    description: "检测 API 契约变更，分析跨服务影响范围。",
    size: "large",
    icon: Share2,
  },
];

export function BentoGrid() {
  return (
    <section className="py-24 px-6 max-w-7xl mx-auto">
      <motion.h2
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.8 }}
        className="font-display font-semibold tracking-tight text-latte-text-primary text-center mb-16"
        style={{ fontSize: "clamp(36px, 5vw, 64px)", lineHeight: 1.1 }}
      >
        为精准而生
      </motion.h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 auto-rows-[260px]">
        {features.map((feature, i) => {
          const Icon = feature.icon;
          return (
            <motion.div
              key={feature.id}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: i * 0.08 }}
              className={
                feature.size === "large" ? "md:col-span-2" : ""
              }
            >
              <GlassCard className="h-full flex flex-col justify-between p-7 hover:border-latte-gold/30">
                <div className="w-12 h-12 rounded-latte-lg bg-latte-bg-tertiary border border-latte-text-primary/5 flex items-center justify-center text-latte-gold">
                  <Icon size={22} strokeWidth={1.5} />
                </div>
                <div>
                  <h3 className="text-xl font-display font-medium text-latte-text-primary mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-sm text-latte-text-secondary leading-relaxed">
                    {feature.description}
                  </p>
                </div>
              </GlassCard>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
