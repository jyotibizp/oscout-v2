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
        // Upstox-style dark theme: charcoal surfaces, white text, purple accent (all text >= 7:1)
        canvas: "#121212",    // app background
        panel: "#1e1e1e",     // surfaces
        raise: "#2a2a2a",     // raised rows / inputs
        line: "#3a3a3a",      // borders / grid
        ink: { DEFAULT: "#ffffff", soft: "#dedede", faint: "#b8b8b8" },  // ≥ 7.5:1 on every surface
        accent: { DEFAULT: "#a99bff", strong: "#6b4ef6", deep: "#5b3fe0", soft: "#2d2546" },  // text / buttons
        good: "#3ecf8e",
        warn: "#f5b14c",
        bad: "#ff6b6b",
      },
      fontFamily: {
        sans: ['Inter', "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
