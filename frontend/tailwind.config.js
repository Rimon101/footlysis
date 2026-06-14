/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  safelist: [
    /^col-span-(1|2|3|4|5|6|7|8|9|10|11|12)$/,
    /^sm:col-span-(1|2|3|4|5|6|7|8|9|10|11|12)$/,
    /^md:col-span-(1|2|3|4|5|6|7|8|9|10|11|12)$/,
    /^lg:col-span-(1|2|3|4|5|6|7|8|9|10|11|12)$/,
  ],
  theme: {
    extend: {
      colors: {
        // Insight Elite — primary (Neon Cyan)
        brand: {
          50:  '#e6fdff',
          100: '#b8f7ff',
          200: '#7aeeff',
          300: '#3be5ff',
          400: '#16d8f5',
          500: '#00f5ff',
          600: '#00bccc',
          700: '#008f99',
          800: '#003739',
          900: '#001f20',
        },
        // Insight Elite — secondary (Neon Lime)
        lime: {
          50:  '#f5ffe0',
          100: '#e8ffb0',
          200: '#d4ff7a',
          300: '#c0ff4d',
          400: '#b6ff36',
          500: '#adff2f',
          600: '#8ed400',
          700: '#6ea300',
          800: '#4e7300',
          900: '#2e4400',
        },
        // Insight Elite — tertiary / AI (Electric Violet)
        violet: {
          50:  '#f0e8ff',
          100: '#d6b8ff',
          200: '#b27bff',
          300: '#8a3dff',
          400: '#7a17ff',
          500: '#7000ff',
          600: '#5800cc',
          700: '#400099',
          800: '#2c0073',
          900: '#1a004a',
        },
        // Insight Elite — surface tones
        surface: {
          base:    '#131313',
          deep:    '#0A0A0F',
          low:     '#1c1b1b',
          DEFAULT: '#201f1f',
          high:    '#2a2a2a',
          highest: '#353534',
        },
        // Data-critical signal
        data: {
          critical: '#FF3B30',
        },
        // Backwards-compat alias for existing accent utility references
        accent: {
          400: '#22d3ee',
          500: '#06b6d4',
          600: '#0891b2',
        },
        // Backwards-compat pitch aliases (used by some legacy classes)
        pitch: {
          dark:  '#020617',
          mid:   '#0f172a',
          light: '#1e293b',
        },
      },
      fontFamily: {
        display: ['Geist', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        sans:    ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        data:    ['JetBrains Mono', 'ui-monospace', 'Fira Code', 'monospace'],
        mono:    ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        bento: '16px',
        tile:  '12px',
      },
      spacing: {
        bento:   '24px',
        card:    '24px',
        section: '40px',
        touch:   '48px',
      },
      backdropBlur: {
        glass:    '12px',
        'glass-lg': '20px',
      },
      boxShadow: {
        'glow-cyan':   '0 0 24px rgba(0, 245, 255, 0.25)',
        'glow-cyan-sm':'0 2px 12px rgba(0, 245, 255, 0.20)',
        'glow-lime':   '0 0 24px rgba(173, 255, 47, 0.25)',
        'glow-violet': '0 0 24px rgba(112, 0, 255, 0.35)',
      },
      animation: {
        'shimmer':    'shimmer 2s ease-in-out infinite',
        'slide-up':   'slideUp 0.35s ease-out',
        'fade-in':    'fadeIn 0.3s ease-out',
        'pulse-soft': 'pulseSoft 2.5s ease-in-out infinite',
        'bento-in':   'bentoIn 0.35s ease-out',
      },
      keyframes: {
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        slideUp: {
          '0%':   { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0.6' },
        },
        bentoIn: {
          '0%':   { opacity: '0', transform: 'scale(0.98)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
      },
    },
  },
  plugins: [],
}
