import type { Config } from "tailwindcss";

// FinMind design tokens — "Deep Void" theme.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: "#070A11",        // app background
        card: "#0E1424",        // primary surfaces
        elevated: "#151F36",    // dropdowns, modals, drawers
        ink: { 1: "#EAF0FA", 2: "#9AA8C4", 3: "#5C6B8A", 4: "#3A4663" },
        signal: "#22D3EE",      // cyan accent
        gain: "#34D399",
        warn: "#FBBF24",
        danger: "#F43F5E",
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans Variable"', "Inter", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono Variable"', "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        glass: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 20px 40px -24px rgba(0,0,0,0.6)",
        glow: "0 0 0 1px rgba(34,211,238,0.25), 0 0 32px -4px rgba(34,211,238,0.35)",
      },
      keyframes: {
        sweep: { "0%": { backgroundPosition: "0% 0" }, "100%": { backgroundPosition: "200% 0" } },
        glow: { "0%,100%": { opacity: "0.35", transform: "scale(1)" }, "50%": { opacity: "0.75", transform: "scale(1.08)" } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
        blink: { "0%,49%": { opacity: "1" }, "50%,100%": { opacity: "0" } },
        float: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-6px)" } },
      },
      animation: {
        sweep: "sweep 5s linear infinite",
        glow: "glow 2.4s ease-in-out infinite",
        shimmer: "shimmer 1.6s infinite",
        blink: "blink 1s steps(1) infinite",
        float: "float 6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
