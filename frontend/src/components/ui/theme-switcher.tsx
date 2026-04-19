"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useThemeContext } from "@/themes";
import { themeList } from "@/themes";
import { cn } from "@/lib/utils";
import { Palette, Check } from "lucide-react";

export function ThemeSwitcher() {
  const { theme, setTheme } = useThemeContext();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "inline-flex items-center justify-center w-9 h-9 rounded-latte-md",
          "text-latte-text-tertiary hover:text-latte-text-primary hover:bg-latte-bg-tertiary",
          "transition-colors duration-200"
        )}
        aria-label="切换主题"
        aria-expanded={open}
      >
        <Palette size={18} strokeWidth={1.5} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.96 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="absolute right-0 mt-2 w-56 p-2 z-50 latte-glass"
          >
            <p className="px-2 py-1.5 text-xs font-medium text-latte-text-muted uppercase tracking-wider">
              主题
            </p>
            <div className="mt-1 space-y-1">
              {themeList.map((t) => (
                <button
                  key={t.name}
                  onClick={() => {
                    setTheme(t.name);
                    setOpen(false);
                  }}
                  className={cn(
                    "w-full flex items-center gap-3 px-2 py-2 rounded-latte-md transition-colors duration-200",
                    theme === t.name
                      ? "bg-latte-gold/10 text-latte-gold"
                      : "text-latte-text-secondary hover:bg-latte-bg-tertiary hover:text-latte-text-primary"
                  )}
                >
                  <span
                    className="w-6 h-6 rounded-latte-sm border border-latte-text-primary/10 flex-shrink-0"
                    style={{
                      background: t.preview.bg,
                      boxShadow: `inset 0 0 0 2px ${t.preview.accent}`,
                    }}
                  />
                  <span className="text-sm flex-1 text-left">{t.label}</span>
                  {theme === t.name && (
                    <Check size={14} className="text-latte-gold flex-shrink-0" />
                  )}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
