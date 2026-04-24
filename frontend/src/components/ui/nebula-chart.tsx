"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { cn } from "@/lib/utils";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  baseRadius: number;
  color: string;
  category: string;
  alpha: number;
  pulsePhase: number;
  pulseSpeed: number;
}

interface NebulaChartProps {
  data: Record<string, number>;
  colors?: Record<string, string>;
  title?: string;
  className?: string;
  height?: number;
}

const DEFAULT_COLORS: Record<string, string> = {
  architecture: "196, 167, 125",
  logic: "212, 165, 154",
  performance: "129, 199, 132",
  style: "144, 202, 249",
  security: "239, 154, 154",
  critical: "239, 83, 80",
  warning: "255, 183, 77",
  info: "100, 181, 246",
  low: "129, 199, 132",
  medium: "255, 213, 79",
  high: "255, 138, 101",
};

export function NebulaChart({
  data,
  colors = DEFAULT_COLORS,
  title,
  className,
  height = 320,
}: NebulaChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const mouseRef = useRef({ x: -1000, y: -1000 });
  const [hoveredCategory, setHoveredCategory] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; text: string } | null>(null);
  const rafRef = useRef<number>(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const initParticles = useCallback(
    (w: number, h: number) => {
      const particles: Particle[] = [];
      const categories = Object.keys(data);
      const total = Object.values(data).reduce((a, b) => a + b, 0);
      const cx = w / 2;
      const cy = h / 2;
      const maxRadius = Math.min(w, h) * 0.38;

      categories.forEach((cat, ci) => {
        const count = data[cat];
        const ratio = count / Math.max(total, 1);
        const particleCount = Math.max(3, Math.min(30, Math.round(ratio * 80)));
        const angleBase = (ci / categories.length) * Math.PI * 2;
        const angleSpread = ((Math.PI * 2) / categories.length) * 0.7;
        const rgb =
          colors[cat] ||
          colors[Object.keys(colors)[ci % Object.keys(colors).length]] ||
          "196, 167, 125";

        for (let i = 0; i < particleCount; i++) {
          const angle = angleBase + (Math.random() - 0.5) * angleSpread;
          const dist = Math.random() * maxRadius * (0.3 + Math.random() * 0.7);
          const x = cx + Math.cos(angle) * dist;
          const y = cy + Math.sin(angle) * dist;
          particles.push({
            x,
            y,
            vx: (Math.random() - 0.5) * 0.15,
            vy: (Math.random() - 0.5) * 0.15,
            radius: 2 + Math.random() * 3,
            baseRadius: 2 + Math.random() * 3,
            color: rgb,
            category: cat,
            alpha: 0.5 + Math.random() * 0.5,
            pulsePhase: Math.random() * Math.PI * 2,
            pulseSpeed: 0.02 + Math.random() * 0.03,
          });
        }
      });

      particlesRef.current = particles;
    },
    [data, colors]
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      const rect = container.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      initParticles(rect.width, height);
    };

    resize();
    window.addEventListener("resize", resize);

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      };
      const px = mouseRef.current.x;
      const py = mouseRef.current.y;
      let nearestCat: string | null = null;
      let nearestDist = Infinity;
      particlesRef.current.forEach((p) => {
        const dx = px - p.x;
        const dy = py - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 60 && dist < nearestDist) {
          nearestDist = dist;
          nearestCat = p.category;
        }
      });
      setHoveredCategory(nearestCat);
      if (nearestCat && data[nearestCat] !== undefined) {
        setTooltip({
          x: px + 12,
          y: py - 12,
          text: `${nearestCat}: ${data[nearestCat]}`,
        });
      } else {
        setTooltip(null);
      }
    };

    const handleMouseLeave = () => {
      mouseRef.current = { x: -1000, y: -1000 };
      setHoveredCategory(null);
      setTooltip(null);
    };

    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("mouseleave", handleMouseLeave);

    const animate = () => {
      const rect = container.getBoundingClientRect();
      const w = rect.width;
      const h = height;
      ctx.clearRect(0, 0, w, h);

      const particles = particlesRef.current;
      const isHovering = hoveredCategory !== null;

      // Update and draw particles
      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        p.pulsePhase += p.pulseSpeed;

        // Boundary bounce
        const margin = 20;
        if (p.x < margin || p.x > w - margin) p.vx *= -1;
        if (p.y < margin || p.y > h - margin) p.vy *= -1;

        const pulse = Math.sin(p.pulsePhase) * 0.3 + 1;
        p.radius = p.baseRadius * pulse;

        const isHovered = p.category === hoveredCategory;
        const alpha = isHovering ? (isHovered ? 1 : 0.12) : p.alpha;
        const r = isHovered ? p.radius * 1.6 : p.radius;

        // Glow
        const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 4);
        glow.addColorStop(0, `rgba(${p.color}, ${alpha * 0.8})`);
        glow.addColorStop(0.4, `rgba(${p.color}, ${alpha * 0.25})`);
        glow.addColorStop(1, `rgba(${p.color}, 0)`);
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r * 4, 0, Math.PI * 2);
        ctx.fill();

        // Core
        ctx.fillStyle = `rgba(${p.color}, ${alpha})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fill();
      });

      // Draw constellation lines between nearby same-category particles
      ctx.lineWidth = 0.6;
      for (let i = 0; i < particles.length; i++) {
        const p1 = particles[i];
        if (isHovering && p1.category !== hoveredCategory) continue;
        const lineAlpha = isHovering ? 0.5 : 0.15;

        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          if (p1.category !== p2.category) continue;
          const dx = p1.x - p2.x;
          const dy = p1.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 50) {
            ctx.strokeStyle = `rgba(${p1.color}, ${lineAlpha * (1 - dist / 50)})`;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
      }

      // Center hub glow
      const cx = w / 2;
      const cy = h / 2;
      const hubGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 60);
      hubGlow.addColorStop(0, "rgba(196, 167, 125, 0.08)");
      hubGlow.addColorStop(1, "rgba(196, 167, 125, 0)");
      ctx.fillStyle = hubGlow;
      ctx.beginPath();
      ctx.arc(cx, cy, 60, 0, Math.PI * 2);
      ctx.fill();

      rafRef.current = requestAnimationFrame(animate);
    };

    rafRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", resize);
      canvas.removeEventListener("mousemove", handleMouseMove);
      canvas.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, [initParticles, height, hoveredCategory, data]);

  const categories = Object.keys(data);

  return (
    <div ref={containerRef} className={cn("relative w-full", className)}>
      {title && (
        <h3 className="text-sm font-medium text-latte-text-primary mb-3">{title}</h3>
      )}
      <div className="relative">
        <canvas
          ref={canvasRef}
          className="w-full rounded-xl cursor-crosshair"
          style={{ height }}
        />
        {/* Category legend */}
        <div className="absolute bottom-2 left-2 right-2 flex flex-wrap gap-2 justify-center">
          {categories.map((cat) => {
            const rgb = colors[cat] || "196, 167, 125";
            const isActive = hoveredCategory === cat;
            return (
              <button
                key={cat}
                onMouseEnter={() => setHoveredCategory(cat)}
                onMouseLeave={() => setHoveredCategory(null)}
                className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs transition-all ${
                  isActive
                    ? "bg-latte-bg-secondary/90 text-latte-text-primary scale-105"
                    : "bg-latte-bg-secondary/60 text-latte-text-secondary"
                }`}
              >
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: `rgb(${rgb})`, boxShadow: `0 0 6px rgb(${rgb})` }}
                />
                <span>{cat}</span>
                <span className="font-medium">{data[cat]}</span>
              </button>
            );
          })}
        </div>
        {/* Tooltip */}
        {tooltip && (
          <div
            className="absolute pointer-events-none px-2 py-1 rounded-lg bg-latte-bg-secondary border border-latte-border text-xs text-latte-text-primary shadow-latte-md"
            style={{ left: tooltip.x, top: tooltip.y }}
          >
            {tooltip.text}
          </div>
        )}
      </div>
    </div>
  );
}
