"use client";

import { motion } from "framer-motion";
import { GitBranch, Cpu, Database, ArrowDown } from "lucide-react";

const nodes = [
  {
    id: "ingest",
    title: "Webhook Ingest",
    desc: "GitHub / GitLab events validated and queued",
    icon: GitBranch,
    color: "text-latte-gold",
    borderColor: "border-latte-gold/20",
    glowColor: "shadow-latte-gold/10",
  },
  {
    id: "workers",
    title: "Celery Workers",
    desc: "Multi-model review, AST analysis, static checks",
    icon: Cpu,
    color: "text-latte-rose",
    borderColor: "border-latte-rose/20",
    glowColor: "shadow-latte-rose/10",
  },
  {
    id: "store",
    title: "Persistent Store",
    desc: "PostgreSQL + pgvector for embeddings",
    icon: Database,
    color: "text-latte-success",
    borderColor: "border-latte-success/20",
    glowColor: "shadow-latte-success/10",
  },
];

function DataPacket({ delay }: { delay: number }) {
  return (
    <motion.div
      className="absolute left-1/2 -translate-x-1/2 w-2.5 h-2.5 rounded-full bg-latte-gold shadow-[0_0_8px_rgba(196,167,125,0.6)] z-10"
      initial={{ top: "0%", opacity: 0 }}
      animate={{ top: "100%", opacity: [0, 1, 1, 0] }}
      transition={{
        duration: 2.5,
        repeat: Infinity,
        delay,
        ease: "linear",
      }}
    />
  );
}

export function ArchitectureFlow() {
  return (
    <div className="relative max-w-md mx-auto py-8">
      {/* Vertical connecting line */}
      <div className="absolute left-1/2 top-8 bottom-8 w-px -translate-x-1/2 border-l border-dashed border-latte-gold/20" />

      {/* Data packets flowing down */}
      <DataPacket delay={0} />
      <DataPacket delay={0.8} />
      <DataPacket delay={1.6} />

      <div className="relative space-y-12">
        {nodes.map((node, index) => {
          const Icon = node.icon;
          return (
            <motion.div
              key={node.id}
              initial={{ opacity: 0, x: index % 2 === 0 ? -30 : 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: index * 0.15 }}
              className={`relative flex items-center gap-4 ${
                index % 2 === 0 ? "flex-row" : "flex-row-reverse"
              }`}
            >
              {/* Node card */}
              <div
                className={`flex-1 latte-glass p-5 border ${node.borderColor} ${node.glowColor} hover:shadow-lg transition-shadow`}
              >
                <div className="flex items-center gap-3 mb-2">
                  <div
                    className={`w-10 h-10 rounded-latte-md bg-latte-bg-tertiary border border-latte-text-primary/5 flex items-center justify-center ${node.color}`}
                  >
                    <Icon size={20} strokeWidth={1.5} />
                  </div>
                  <h3 className="text-base font-medium text-latte-text-primary">
                    {node.title}
                  </h3>
                </div>
                <p className="text-sm text-latte-text-secondary leading-relaxed">
                  {node.desc}
                </p>
              </div>

              {/* Connector dot on the line */}
              <div className="relative z-10 flex-shrink-0">
                <motion.div
                  className={`w-4 h-4 rounded-full border-2 bg-latte-bg-primary ${node.borderColor}`}
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 2, repeat: Infinity, delay: index * 0.3 }}
                >
                  <div className={`w-full h-full rounded-full ${node.color.replace("text-", "bg-")} opacity-60`} />
                </motion.div>
              </div>

              {/* Spacer for alternating layout */}
              <div className="flex-1 hidden sm:block" />
            </motion.div>
          );
        })}
      </div>

      {/* Scale badge */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6, delay: 0.6 }}
        className="mt-10 text-center"
      >
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full latte-glass border border-latte-gold/20">
          <ArrowDown size={14} className="text-latte-gold" />
          <span className="text-sm text-latte-text-secondary">
            Horizontally scalable via Kubernetes
          </span>
        </div>
      </motion.div>
    </div>
  );
}
