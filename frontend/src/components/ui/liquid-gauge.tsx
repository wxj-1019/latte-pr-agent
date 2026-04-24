"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface LiquidGaugeProps {
  value: number;
  max?: number;
  label: string;
  sublabel?: string;
  color?: string;
  size?: number;
  className?: string;
}

export function LiquidGauge({
  value,
  max = 100,
  label,
  sublabel,
  color = "var(--latte-gold)",
  size = 140,
  className,
}: LiquidGaugeProps) {
  const percent = Math.min(Math.max((value / max) * 100, 0), 100);
  const [displayValue, setDisplayValue] = useState(0);
  const [waveOffset, setWaveOffset] = useState(0);
  const rafRef = useRef<number>(0);
  const startTimeRef = useRef<number>(0);

  // Count-up animation
  useEffect(() => {
    const duration = 1200;
    const start = performance.now();
    const from = displayValue;
    const to = value;

    const tick = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(Math.round(from + (to - from) * eased));
      if (progress < 1) {
        requestAnimationFrame(tick);
      }
    };
    requestAnimationFrame(tick);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  // Wave animation
  useEffect(() => {
    startTimeRef.current = performance.now();
    const animate = (now: number) => {
      const t = (now - startTimeRef.current) / 1000;
      setWaveOffset(t);
      rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  const cx = size / 2;
  const cy = size / 2;
  const radius = size * 0.42;
  const waveHeight = size * 0.04;
  const fillY = cy + radius - (percent / 100) * (radius * 2);

  const buildWavePath = (phase: number, amplitude: number, freq: number) => {
    let d = `M ${cx - radius} ${fillY}`;
    const steps = 40;
    for (let i = 0; i <= steps; i++) {
      const x = cx - radius + (i / steps) * (radius * 2);
      const y =
        fillY +
        Math.sin((i / steps) * Math.PI * freq + phase + waveOffset * 2) * amplitude;
      d += ` L ${x} ${y}`;
    }
    d += ` L ${cx + radius} ${cy + radius + 10}`;
    d += ` L ${cx - radius} ${cy + radius + 10} Z`;
    return d;
  };

  return (
    <div className={cn("flex flex-col items-center", className)}>
      <div style={{ width: size, height: size, position: "relative" }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <defs>
            <clipPath id={`liquid-clip-${label}`}>
              <circle cx={cx} cy={cy} r={radius} />
            </clipPath>
            <linearGradient id={`liquid-grad-${label}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.9} />
              <stop offset="100%" stopColor={color} stopOpacity={0.5} />
            </linearGradient>
          </defs>

          {/* Background circle */}
          <circle
            cx={cx}
            cy={cy}
            r={radius}
            fill="var(--latte-bg-tertiary)"
            stroke="var(--latte-border)"
            strokeWidth={2}
          />

          {/* Liquid */}
          <g clipPath={`url(#liquid-clip-${label})`}>
            {/* Back wave */}
            <path
              d={buildWavePath(0, waveHeight * 0.8, 2.5)}
              fill={color}
              opacity={0.35}
            />
            {/* Front wave */}
            <path
              d={buildWavePath(Math.PI / 3, waveHeight, 2)}
              fill={`url(#liquid-grad-${label})`}
            />
            {/* Highlight line on wave surface */}
            <path
              d={buildWavePath(Math.PI / 3, waveHeight, 2)}
              fill="none"
              stroke="rgba(255,255,255,0.25)"
              strokeWidth={1.5}
            />
          </g>

          {/* Glass rim glow */}
          <circle
            cx={cx}
            cy={cy}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={2}
            opacity={0.3}
            style={{ filter: `drop-shadow(0 0 6px ${color})` }}
          />

          {/* Center text */}
          <text
            x={cx}
            y={cy - 2}
            textAnchor="middle"
            dominantBaseline="middle"
            fill="var(--latte-text-primary)"
            fontSize={size * 0.22}
            fontWeight={700}
            fontFamily="var(--font-display)"
          >
            {displayValue.toLocaleString()}
          </text>
          <text
            x={cx}
            y={cy + size * 0.16}
            textAnchor="middle"
            dominantBaseline="middle"
            fill="var(--latte-text-secondary)"
            fontSize={size * 0.1}
          >
            {sublabel || `${Math.round(percent)}%`}
          </text>
        </svg>
      </div>
      <p className="mt-2 text-sm font-medium text-latte-text-secondary">{label}</p>
    </div>
  );
}
