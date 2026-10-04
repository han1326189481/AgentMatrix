import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          primary: '#0a0e1a',
          secondary: '#0d1220',
          tertiary: '#131a2b',
          card: '#161d2f',
          'card-hover': '#1a2338',
          elevated: '#1e2842',
        },
        border: {
          default: '#1e2942',
          light: '#253352',
          glow: 'rgba(56, 189, 248, 0.15)',
        },
        text: {
          primary: '#e8edf5',
          secondary: '#94a3b8',
          tertiary: '#64748b',
          muted: '#475569',
        },
        accent: {
          cyan: '#38bdf8',
          blue: '#3b82f6',
          green: '#10b981',
          emerald: '#34d399',
          amber: '#f59e0b',
          orange: '#f97316',
          red: '#ef4444',
          purple: '#a78bfa',
        },
      },
      fontFamily: {
        sans: ['Noto Sans SC', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        sm: '8px',
        md: '12px',
        lg: '16px',
      },
      boxShadow: {
        card: '0 1px 3px rgba(0, 0, 0, 0.3)',
        elevated: '0 4px 12px rgba(0, 0, 0, 0.4)',
        glow: '0 0 20px rgba(56, 189, 248, 0.15)',
        'glow-lg': '0 0 40px rgba(56, 189, 248, 0.2)',
        'glow-green': '0 0 20px rgba(16, 185, 129, 0.2)',
        'glow-amber': '0 0 20px rgba(245, 158, 11, 0.2)',
      },
    },
  },
  plugins: [],
};

export default config;
