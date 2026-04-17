"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { SteamParticles } from "./steam-particles";

export function HeroSection() {
  const router = useRouter();
  const [mouse, setMouse] = useState({ x: 0.5, y: 0.5 });
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  useEffect(() => {
    if (reducedMotion) return;
    const handleMove = (e: MouseEvent) => {
      setMouse({
        x: e.clientX / window.innerWidth,
        y: e.clientY / window.innerHeight,
      });
    };
    window.addEventListener("mousemove", handleMove);
    return () => window.removeEventListener("mousemove", handleMove);
  }, [reducedMotion]);

  return (
    <section
      className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden"
      style={{
        background: reducedMotion
          ? "var(--latte-bg-primary)"
          : `radial-gradient(ellipse 80% 50% at ${mouse.x * 100}% ${mouse.y * 100}%, rgba(196, 167, 125, 0.12), transparent),
          radial-gradient(ellipse 60% 40% at 80% 80%, rgba(212, 165, 154, 0.06), transparent),
          var(--latte-bg-primary)`,
      }}
    >
      <SteamParticles />

      {/* Decorative rotating ring */}
      {!reducedMotion && (
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 opacity-40 pointer-events-none">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 60, repeat: Infinity, ease: "linear" }}
            className="w-80 h-80 md:w-[28rem] md:h-[28rem] rounded-full border border-dashed border-latte-gold/20"
          />
          <motion.div
            animate={{ rotate: -360 }}
            transition={{ duration: 45, repeat: Infinity, ease: "linear" }}
            className="absolute inset-8 rounded-full border border-latte-rose/10"
          />
        </div>
      )}

      <div className="relative z-10 text-center max-w-5xl px-6">
        <motion.h1
          initial={reducedMotion ? {} : { opacity: 0, y: 40, filter: "blur(10px)" }}
          animate={reducedMotion ? {} : { opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
          className="font-display font-bold tracking-tight text-latte-text-primary"
          style={{ fontSize: "clamp(48px, 8vw, 96px)", lineHeight: 1.05 }}
        >
          Enterprise AI Code Review,
          <br />
          <span className="text-latte-gold">Reimagined.</span>
        </motion.h1>

        <motion.p
          initial={reducedMotion ? {} : { opacity: 0, y: 30, filter: "blur(8px)" }}
          animate={reducedMotion ? {} : { opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 0.9, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="text-lg md:text-xl text-latte-text-secondary max-w-3xl mx-auto mt-6 mb-10 leading-relaxed"
        >
          Latte PR Agent 为企业级代码审查注入智能与温度。多模型协同、上下文感知、质量门禁——
          如同一杯完美萃取的拿铁，每一个细节都恰到好处。
        </motion.p>

        <motion.div
          initial={reducedMotion ? {} : { opacity: 0, y: 20 }}
          animate={reducedMotion ? {} : { opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="flex items-center justify-center gap-4"
        >
          <Button size="lg" onClick={() => router.push("/dashboard/reviews")}>
            Get Started
          </Button>
          <Button variant="secondary" size="lg" onClick={() => router.push("/dashboard")}>
            View Dashboard
          </Button>
        </motion.div>
      </div>
    </section>
  );
}
