/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bie-dark": "#0f172a",
        "bie-panel": "#1e293b",
        "bie-accent": "#3b82f6",
      },
    },
  },
  plugins: [],
};
