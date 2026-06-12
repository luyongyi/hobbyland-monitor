/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        gundam: {
          red: '#dc2626',
          blue: '#1e40af',
          yellow: '#fbbf24',
        },
      },
    },
  },
  plugins: [],
}
