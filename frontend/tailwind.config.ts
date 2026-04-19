import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        latte: {
          "bg-deep": "var(--latte-bg-deep)",
          "bg-primary": "var(--latte-bg-primary)",
          "bg-secondary": "var(--latte-bg-secondary)",
          "bg-tertiary": "var(--latte-bg-tertiary)",
          "bg-hover": "var(--latte-bg-hover)",
          "text-primary": "var(--latte-text-primary)",
          "text-secondary": "var(--latte-text-secondary)",
          "text-tertiary": "var(--latte-text-tertiary)",
          "text-muted": "var(--latte-text-muted)",
          accent: "var(--latte-accent)",
          "accent-hover": "var(--latte-accent-hover)",
          gold: "var(--latte-gold)",
          "gold-dim": "var(--latte-gold-dim)",
          "gold-glow": "var(--latte-gold-glow)",
          rose: "var(--latte-rose)",
          "rose-dim": "var(--latte-rose-dim)",
          "rose-glow": "var(--latte-rose-glow)",
          success: "var(--latte-success)",
          warning: "var(--latte-warning)",
          critical: "var(--latte-critical)",
          info: "var(--latte-info)",
        },
      },
      fontFamily: {
        display: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"SF Pro Display"',
          '"Helvetica Neue"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          "sans-serif",
        ],
        text: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"SF Pro Text"',
          '"Helvetica Neue"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          "sans-serif",
        ],
        mono: ['"SF Mono"', '"JetBrains Mono"', '"Fira Code"', "monospace"],
      },
      borderRadius: {
        "latte-sm": "var(--latte-radius-sm)",
        "latte-md": "var(--latte-radius-md)",
        "latte-lg": "var(--latte-radius-lg)",
        "latte-xl": "var(--latte-radius-xl)",
      },
      boxShadow: {
        "latte-sm": "var(--latte-shadow-sm)",
        "latte-md": "var(--latte-shadow-md)",
        "latte-lg": "var(--latte-shadow-lg)",
        "latte-gold": "var(--latte-shadow-gold)",
      },
      transitionTimingFunction: {
        "apple-smooth": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
