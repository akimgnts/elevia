import type { Config } from "tailwindcss";

/**
 * Tailwind Design Tokens
 * Systematic scale for spacing, shadows, and radii
 * Intent: calm, minimal, professional (Apple-clean)
 */
const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Brand: cyan → lime gradient
        brand: {
          cyan: "#06B6D4",
          lime: "#22C55E",
        },
        // Matching score feedback
        matching: {
          low: "#EF4444",
          medium: "#FACC15",
          good: "#06B6D4",
          excellent: "#22C55E",
        },
        // Neutral palette (slate-based)
        surface: {
          DEFAULT: "#FFFFFF",
          muted: "#F8FAFC",
          subtle: "#F1F5F9",
        },
      },
      // Shadow scale: subtle elevation hierarchy
      boxShadow: {
        xs: "0 1px 2px rgba(0,0,0,0.04)",
        sm: "0 2px 4px rgba(0,0,0,0.05)",
        DEFAULT: "0 4px 12px rgba(0,0,0,0.06)",
        md: "0 8px 24px rgba(0,0,0,0.08)",
        lg: "0 16px 48px rgba(0,0,0,0.10)",
        soft: "0 8px 24px rgba(0,0,0,0.05)",
        glow: "0 0 24px rgba(6,182,212,0.20)",
        card: "0 1px 3px rgba(0,0,0,0.06)",
      },
      // Border radius scale: consistent curves
      borderRadius: {
        sm: "0.375rem",
        DEFAULT: "0.5rem",
        md: "0.75rem",
        lg: "1rem",
        xl: "1.25rem",
        "2xl": "1.5rem",
        card: "1rem",
        button: "0.75rem",
        badge: "0.5rem",
      },
      fontFamily: {
        sans: ["InterVariable", "Inter", "ui-sans-serif", "system-ui"],
      },
      // Spacing rhythm (4px base)
      spacing: {
        "18": "4.5rem",
        "22": "5.5rem",
      },
    },
  },
  plugins: [require("@tailwindcss/typography"), require("@tailwindcss/forms")],
};

export default config;
