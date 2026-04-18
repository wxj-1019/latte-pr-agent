"use client";

import { motion } from "framer-motion";
import { GlassCard } from "@/components/ui/glass-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { Badge } from "@/components/ui/badge";

export function DashboardPreview() {
  return (
    <section className="py-24 px-6 overflow-hidden">
      <div className="max-w-7xl mx-auto text-center mb-14">
        <motion.h2
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="font-display font-semibold tracking-tight text-latte-text-primary"
          style={{ fontSize: "clamp(36px, 5vw, 64px)", lineHeight: 1.1 }}
        >
          每次审查，一目了然
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, delay: 0.1 }}
          className="text-lg text-latte-text-secondary mt-4 max-w-2xl mx-auto"
        >
          从 PR 概览到单条发现的置信度，所有数据一目了然。
        </motion.p>
      </div>

      <motion.div
        initial={{ opacity: 0, rotateX: 15, y: 60 }}
        whileInView={{ opacity: 1, rotateX: 5, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
        whileHover={{ rotateX: 0, scale: 1.01 }}
        className="max-w-6xl mx-auto"
        style={{ perspective: "1000px" }}
      >
        <GlassCard className="p-2 rounded-[32px]">
          <div className="bg-latte-bg-deep rounded-[24px] overflow-hidden min-h-[420px] p-6">
            {/* Mock Dashboard Header */}
            <div className="flex items-center justify-between mb-6">
              <div className="flex gap-6">
                <div>
                  <p className="text-xs text-latte-text-muted">审查</p>
                  <p className="text-2xl font-display font-semibold text-latte-text-primary">1,284</p>
                </div>
                <div>
                  <p className="text-xs text-latte-text-muted">发现</p>
                  <p className="text-2xl font-display font-semibold text-latte-text-primary">3,402</p>
                </div>
                <div>
                  <p className="text-xs text-latte-text-muted">准确率</p>
                  <p className="text-2xl font-display font-semibold text-latte-gold">94.2%</p>
                </div>
              </div>
              <div className="px-3 py-1.5 rounded-latte-md bg-latte-bg-tertiary text-xs text-latte-text-secondary">
                最近 7 天
              </div>
            </div>

            {/* Mock Review Cards */}
            <div className="space-y-3">
              <div className="flex items-center justify-between p-4 rounded-latte-xl bg-latte-bg-secondary border-l-4 border-latte-success">
                <div className="flex items-center gap-3">
                  <StatusBadge status="completed" />
                  <span className="text-sm text-latte-text-primary">#127 fix: memory leak</span>
                </div>
                <Badge variant="critical" dot>
                  严重
                </Badge>
              </div>
              <div className="flex items-center justify-between p-4 rounded-latte-xl bg-latte-bg-secondary border-l-4 border-amber-500">
                <div className="flex items-center gap-3">
                  <StatusBadge status="pending" />
                  <span className="text-sm text-latte-text-primary">#128 feat: add user auth</span>
                </div>
                <span className="text-xs text-latte-text-muted">2 分钟前</span>
              </div>
              <div className="flex items-center justify-between p-4 rounded-latte-xl bg-latte-bg-secondary border-l-4 border-blue-500">
                <div className="flex items-center gap-3">
                  <StatusBadge status="running" />
                  <span className="text-sm text-latte-text-primary">#45 refactor: migrate to app router</span>
                </div>
                <span className="text-xs text-latte-text-muted">运行中</span>
              </div>
            </div>
          </div>
        </GlassCard>
      </motion.div>
    </section>
  );
}
