/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Matches the approved UI mockup (image.png)
        ground: '#0d0b12',
        panel: '#15121d',
        panel2: '#1c1828',
        edge: '#2a2438',
        violet: '#8b6fd4',
        violetdim: '#3a2f5c',
        risk: {
          critical: '#e5484d',
          high: '#e5901d',
          medium: '#d9b21c',
          low: '#3d9a6d',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
