/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#f8f9fa",
        editorial: {
          bg: "#fbfbfb",
          card: "#ffffff",
          border: "#000000",
          muted: "#71717a",
          red: "#ff3b30",
          'red-dark': "#e63946",
          blue: "#4a8b9f",
          'blue-muted': "#3d7a8d",
          accent: "#f4f4f5",
          dark: "#09090b",
        },
      },
      fontFamily: {
        sans: [
          '"Space Grotesk"',
          '"Plus Jakarta Sans"',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          'sans-serif',
        ],
        mono: [
          '"JetBrains Mono"',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Monaco',
          'Consolas',
          'monospace',
        ],
      },
      boxShadow: {
        'brutal-sm': '2px 2px 0px 0px #000000',
        'brutal': '3px 3px 0px 0px #000000',
        'brutal-lg': '5px 5px 0px 0px #000000',
      },
    },
  },
  plugins: [],
}
