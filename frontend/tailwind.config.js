/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
        serif: ['"Fraunces"', "Georgia", "serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        paper: "#f6f4ef",
        ink: { DEFAULT: "#1d1f1c", soft: "#4a4d47", faint: "#8a8d85" },
        line: "#e2ded4",
        accent: { DEFAULT: "#1f5c4a", soft: "#e3eee9", strong: "#164536" },
        warn: { DEFAULT: "#9a4a12", soft: "#fbeee2" },
        bad: { DEFAULT: "#a12a2a", soft: "#f9e5e5" },
      },
      boxShadow: { card: "0 1px 0 rgba(29,31,28,0.04), 0 1px 3px rgba(29,31,28,0.06)" },
    },
  },
  plugins: [],
};
