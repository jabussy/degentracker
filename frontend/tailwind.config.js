/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        surface: {
          0: "#0a0a0b",
          1: "#111113",
          2: "#18181b",
          3: "#222226",
          4: "#2a2a30",
        },
        border: "#2e2e35",
        value: "#22c55e",
        loss: "#ef4444",
        warn: "#f59e0b",
        dim: "#71717a",
      },
    },
  },
  plugins: [],
};
