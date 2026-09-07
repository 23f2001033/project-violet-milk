/** @type {import('tailwindcss').Config} */

/*
 * Every surface and text colour resolves through a CSS variable, so the light
 * theme is a palette swap in index.css rather than an edit to 215 class names
 * spread across eleven organs.
 *
 * `slate` is deliberately OVERRIDDEN rather than extended. The components were
 * written against slate-100..700 as a neutral ramp, and remapping the ramp is
 * what lets the whole interface invert without touching a single component.
 * The unused shades still resolve, so nothing breaks if one is added later.
 */
const ramp = Object.fromEntries(
  [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950].map((n) => [
    n,
    `var(--t${n})`,
  ])
)

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Matches the approved UI mockup (image.png) in the dark palette.
        ground: 'var(--c-ground)',
        panel: 'var(--c-panel)',
        panel2: 'var(--c-panel2)',
        edge: 'var(--c-edge)',
        violet: 'var(--c-violet)',
        violetdim: 'var(--c-violetdim)',
        slate: ramp,
        risk: {
          critical: 'var(--c-critical)',
          high: 'var(--c-high)',
          medium: 'var(--c-medium)',
          low: 'var(--c-low)',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
