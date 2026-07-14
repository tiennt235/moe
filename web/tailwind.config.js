/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#0D1216", 2: "#141B21", 3: "#1B242B" },
        line: { DEFAULT: "#232E35", 2: "#33414A" },
        fg: { DEFAULT: "#E5EDF1", muted: "#9AA7AF", faint: "#74828B" },
        accent: { DEFAULT: "#2DD4C4", ink: "#5FE6D9", deep: "#0E7C7B" },
        good: "#5CC77E",
        warn: "#E0A64B",
        bad: "#E48774",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["ui-monospace", "SF Mono", "JetBrains Mono", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
