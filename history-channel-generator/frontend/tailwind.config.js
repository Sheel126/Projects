/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  theme: {
    extend: {
      colors: {
        documentary: {
          bg: '#0f1117',
          card: '#1a1d27',
          border: '#2a2f3d',
          accent: '#f59e0b',
          muted: '#94a3b8',
        },
      },
    },
  },
  plugins: [],
};
