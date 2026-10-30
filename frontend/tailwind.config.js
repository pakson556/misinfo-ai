// Tailwind CSS = styling with small utility classes in the JSX
// (e.g. className="text-sm text-ink"). This file defines the project's design
// tokens: the colour palette and fonts. "ink" is the text colour, "paper" the
// background, and refuted / mixed / supported / unverified are the verdict colours.
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F7F8FA",
        sheet: "#FFFFFF",
        ink: { DEFAULT: "#18202E", soft: "#4A5468", faint: "#8A93A6" },
        rule: "#DDE1E8",
        cobalt: { DEFAULT: "#2F4BD8", deep: "#2238A8", wash: "#E9EDFC" },
        refuted: { DEFAULT: "#B4232C", wash: "#FBEAEB" },
        mixed: { DEFAULT: "#A86A12", wash: "#FBF1DF" },
        supported: { DEFAULT: "#1D7352", wash: "#E4F3EC" },
        unverified: { DEFAULT: "#667085", wash: "#EEF0F3" },
      },
      fontFamily: {
        serif: ['"Literata Variable"', "Georgia", "serif"],
        sans: ['"Instrument Sans Variable"', "system-ui", "sans-serif"],
      },
      maxWidth: { measure: "68ch" },
    },
  },
  plugins: [],
};
