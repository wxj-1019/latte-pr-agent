"use client";

import { useEffect, useRef, useState } from "react";

interface Particle {
  x: number;
  y: number;
  radius: number;
  speedY: number;
  opacity: number;
  color: string;
}

export function SteamParticles() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [reducedMotion, setReducedMotion] = useState(false);
  const colorsRef = useRef<{ c1: string; c2: string }>({
    c1: "196, 167, 125",
    c2: "212, 165, 154",
  });

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  // Cache theme colors and watch for data-theme changes
  useEffect(() => {
    if (reducedMotion) return;

    const updateColors = () => {
      const root = getComputedStyle(document.documentElement);
      colorsRef.current.c1 =
        root.getPropertyValue("--latte-particle-color-1").trim() || "196, 167, 125";
      colorsRef.current.c2 =
        root.getPropertyValue("--latte-particle-color-2").trim() || "212, 165, 154";
    };

    updateColors();

    const observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        if (m.attributeName === "data-theme") {
          updateColors();
        }
      }
    });

    observer.observe(document.documentElement, { attributes: true });
    return () => observer.disconnect();
  }, [reducedMotion]);

  useEffect(() => {
    if (reducedMotion) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationId: number;
    let particles: Particle[] = [];

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    const initParticles = () => {
      particles = [];
      const count = Math.min(40, Math.floor((canvas.width * canvas.height) / 40000));
      for (let i = 0; i < count; i++) {
        particles.push({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height,
          radius: Math.random() * 60 + 20,
          speedY: Math.random() * 0.3 + 0.1,
          opacity: Math.random() * 0.04 + 0.02,
          color: Math.random() > 0.5 ? colorsRef.current.c1 : colorsRef.current.c2,
        });
      }
    };

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach((p) => {
        p.y -= p.speedY;
        if (p.y < -p.radius * 2) {
          p.y = canvas.height + p.radius * 2;
          p.x = Math.random() * canvas.width;
          // re-roll color on respawn so theme changes take effect gradually
          p.color = Math.random() > 0.5 ? colorsRef.current.c1 : colorsRef.current.c2;
        }
        const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.radius);
        gradient.addColorStop(0, `rgba(${p.color}, ${p.opacity})`);
        gradient.addColorStop(1, `rgba(${p.color}, 0)`);
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fill();
      });
      animationId = requestAnimationFrame(animate);
    };

    resize();
    initParticles();
    animate();

    window.addEventListener("resize", resize);
    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener("resize", resize);
    };
  }, [reducedMotion]);

  if (reducedMotion) return null;

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-none"
      aria-hidden="true"
    />
  );
}
