/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: 'rgb(var(--surface) / <alpha-value>)',
        'surface-container': 'rgb(var(--surface-container) / <alpha-value>)',
        primary: 'rgb(var(--primary) / <alpha-value>)',
        secondary: 'rgb(var(--secondary) / <alpha-value>)',
        tertiary: 'rgb(var(--tertiary) / <alpha-value>)',
        error: 'rgb(var(--error) / <alpha-value>)',
        'on-surface': 'rgb(var(--on-surface) / <alpha-value>)',
        'on-surface-variant': 'rgb(var(--on-surface-variant) / <alpha-value>)',
        outline: 'rgb(var(--outline) / <alpha-value>)',
      },
      fontFamily: {
        display: ['Sora', 'system-ui', 'sans-serif'],
        body: ['Manrope', 'system-ui', 'sans-serif'],
        mono: ['IBM Plex Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        glass: '0 8px 26px rgba(3, 7, 18, 0.45)',
        'glass-lg': '0 16px 42px rgba(3, 7, 18, 0.55)',
        depth: '0 12px 30px rgba(12, 74, 110, 0.2)',
      },
      backgroundImage: {
        'hero-gradient':
          'radial-gradient(circle at 10% 10%, rgba(56, 189, 248, 0.2), transparent 34%), radial-gradient(circle at 85% 20%, rgba(16, 185, 129, 0.12), transparent 36%), linear-gradient(160deg, rgba(8, 15, 31, 0.98), rgba(6, 11, 23, 0.96))',
      },
      transitionTimingFunction: {
        premium: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
    },
  },
  plugins: [],
};
