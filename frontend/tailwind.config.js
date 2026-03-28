/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        hacker: {
          green: "#00FF41",
          dark: "#0D0208",
          muted: "#003B00",
        }
      },
      fontFamily: {
        mono: ["Space Mono", "monospace"],
      }
    },
  },
  plugins: [],
}
