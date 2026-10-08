import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// absolute paths so styles build no matter which folder the dev server is started from
const here = dirname(fileURLToPath(import.meta.url));

/** @type {import('tailwindcss').Config} */
export default {
  content: [join(here, "index.html"), join(here, "src/**/*.{ts,tsx}")],
  theme: {
    extend: {
      colors: {
        // dark blue + grey terminal palette
        canvas: "#0b1220",    // app background
        panel: "#111a2b",     // surfaces
        raise: "#16213a",     // raised rows / inputs
        line: "#2a3a58",      // borders / grid
        ink: { DEFAULT: "#f1f5fb", soft: "#d0d8e4", faint: "#a8b4c7" },  // ≥ 7.5:1 on every surface
        accent: { DEFAULT: "#60a5fa", strong: "#2563eb", deep: "#1d4ed8", soft: "#1e3a6b" },  // text / buttons
        good: "#4ade80",
        warn: "#f59e0b",
        bad: "#f87171",
      },
      fontFamily: {
        sans: ['Inter', "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
