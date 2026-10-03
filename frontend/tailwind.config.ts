import type { Config } from "tailwindcss";

/**
 * Palette mapped 1:1 from styles/tokens.css (PRD §12.2). Neutral surface
 * colors support readability; the triadic brand colors carry identity.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "ig-navy": "var(--ig-navy)",
        "ig-blue": "var(--ig-blue)",
        "ig-green": "var(--ig-green)",
        "ig-bg": "var(--ig-bg)",
        "ig-surface": "var(--ig-surface)",
        "ig-border": "var(--ig-border)",
        "ig-muted": "var(--ig-muted)",
        "ig-danger": "var(--ig-danger)",
      },
      fontFamily: {
        sans: ["Inter", "Geist", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
