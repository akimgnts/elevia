import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"] ,
  theme: {
    extend: {
      colors: {
        brand: {
          cyan: "#06B6D4",
          lime: "#22C55E",
        },
        matching: {
          low: "#EF4444",
          medium: "#FACC15",
          good: "#06B6D4",
          excellent: "#22C55E",
        },
      },
      boxShadow: {
        soft: "0 8px 24px rgba(0,0,0,0.05)",
        glow: "0 0 24px rgba(6,182,212,0.25)",
        "glow-cyan": "0 0 20px rgba(6,182,212,0.2)",
        card: "0 1px 3px 0 rgba(0,0,0,0.1)",
      },
      borderRadius: {
        card: "1rem",
        button: "0.75rem",
        badge: "0.5rem",
      },
      fontFamily: {
        sans: ["InterVariable", "Inter", "ui-sans-serif", "system-ui"],
      },
    },
  },
  plugins: [require("@tailwindcss/typography"), require("@tailwindcss/forms")],
};

export default config;
