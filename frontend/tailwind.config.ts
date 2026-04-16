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
          "bg-deep": "#030201",
          "bg-primary": "#0A0806",
          "bg-secondary": "#14110E",
          "bg-tertiary": "#1E1A16",
          "bg-hover": "#28231E",
          "text-primary": "#F5E6D3",
          "text-secondary": "#C4B5A5",
          "text-tertiary": "#8B7D6D",
          "text-muted": "#5C5246",
          accent: "#E8DCC4",
          "accent-hover": "#F0E8D8",
          gold: "#C4A77D",
          "gold-dim": "#8F7650",
          "gold-glow": "rgba(196, 167, 125, 0.25)",
          rose: "#D4A59A",
          "rose-dim": "#A67B72",
          "rose-glow": "rgba(212, 165, 154, 0.2)",
          success: "#7D8471",
          warning: "#B85C38",
          critical: "#8B3A3A",
          info: "#9A8B7A",
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
        "latte-sm": "8px",
        "latte-md": "12px",
        "latte-lg": "20px",
        "latte-xl": "24px",
      },
      boxShadow: {
        "latte-sm": "0 2px 8px rgba(0, 0, 0, 0.3)",
        "latte-md": "0 4px 24px rgba(0, 0, 0, 0.4)",
        "latte-lg": "0 12px 48px rgba(0, 0, 0, 0.5)",
        "latte-gold": "0 8px 24px rgba(196, 167, 125, 0.15)",
      },
      transitionTimingFunction: {
        "apple-smooth": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
