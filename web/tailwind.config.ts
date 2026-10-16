import type { Config } from "tailwindcss";

// FinMind AI Design System — Precision Institutional Fintech (Swiss Minimalist / Stripe / Ramp inspired)
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: "#080C14",        // Deep architectural obsidian
        card: "#0E1422",        // Primary surface
        surface: "#121A2C",     // Secondary surface / table headers
        elevated: "#182238",    // Modals, popovers, dropdowns
        border: {
          subtle: "#161F33",
          DEFAULT: "#1E2942",
          strong: "#2B3A5C",
        },
        ink: {
          1: "#F8FAFC",         // Primary text
          2: "#94A3B8",         // Secondary text
          3: "#64748B",         // Muted metadata
          4: "#475569",         // Dim timestamps / icons
        },
        brand: {
          DEFAULT: "#38BDF8",   // Precision Sky Blue
          hover: "#0284C7",
          subtle: "rgba(56, 189, 248, 0.08)",
        },
        emerald: {
          DEFAULT: "#10B981",
          hover: "#059669",
          subtle: "rgba(16, 185, 129, 0.08)",
        },
        gain: "#10B981",        // Income / savings
        warn: "#F59E0B",        // Medium risk / warnings
        danger: "#EF4444",      // Fraud / critical risk
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans Variable"', "Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ['"JetBrains Mono Variable"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        card: "inset 0 1px 0 0 rgba(255, 255, 255, 0.05), 0 1px 3px 0 rgba(0, 0, 0, 0.35)",
        cardHover: "inset 0 1px 0 0 rgba(255, 255, 255, 0.08), 0 4px 16px -2px rgba(0, 0, 0, 0.5)",
        modal: "inset 0 1px 0 0 rgba(255, 255, 255, 0.08), 0 24px 48px -12px rgba(0, 0, 0, 0.75)",
      },
      keyframes: {
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: {
        shimmer: "shimmer 1.8s infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
