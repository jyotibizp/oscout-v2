/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // dark blue + grey terminal palette
        canvas: "#0b1220",    // app background
        panel: "#111a2b",     // surfaces
        raise: "#16213a",     // raised rows / inputs
        line: "#22304a",      // borders / grid
        ink: { DEFAULT: "#e6ebf3", soft: "#a9b4c6", faint: "#71809a" },
        accent: { DEFAULT: "#3b82f6", strong: "#2563eb", soft: "#1e3a6b" },
        good: "#22c55e",
        warn: "#f59e0b",
        bad: "#ef4444",
      },
      fontFamily: {
        sans: ['Inter', "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
