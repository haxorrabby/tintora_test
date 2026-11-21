/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './templates/**/*.html',
    './apps/**/templates/**/*.html',
    './apps/**/forms.py',
    './static/src/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        // Brand Primary Tokens
        ink: {
          DEFAULT: '#24272B',
          50: '#F7F8F9',
          100: '#EEF0F2',
          200: '#DDE0E3',
          300: '#C4C8CD',
          400: '#8B9198',
          500: '#697078',
          600: '#4F555C',
          700: '#383D43',
          800: '#2D3237',
          900: '#24272B',
          950: '#181B1E',
        },
        paper: {
          DEFAULT: '#F7F8F6',
          50: '#FFFFFF',
          100: '#FBFCFA',
          200: '#F7F8F6',
          300: '#E9ECE8',
          400: '#D7DCD7',
          500: '#BCC3BD',
          600: '#929A93',
          700: '#717A73',
          800: '#555E57',
          900: '#3A423C',
        },
        vermilion: {
          DEFAULT: '#C4322A',
          light: '#E4584F',
          dark: '#A92721',
          soft: 'rgba(196, 50, 42, 0.08)',
        },
        gold: {
          DEFAULT: '#C9A96A',
          light: '#DEC187',
          dark: '#7A6234',
          soft: 'rgba(201, 169, 106, 0.12)',
        },
        // Surfaces for light/dark editorial contrast
        surface: {
          light: '#F5F6F4',
          cardLight: '#FFFFFF',
          dark: '#181B1E',
          cardDark: '#22262A',
          subtleDark: '#2B3035',
        }
      },
      fontFamily: {
        serif: ['"DM Sans"', 'system-ui', '-apple-system', 'sans-serif'],
        sans: ['"DM Sans"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"DM Sans"', 'system-ui', '-apple-system', 'sans-serif'],
      },
      fontSize: {
        'display-2xl': ['clamp(4.5rem, 12vw, 13rem)', { lineHeight: '0.88', letterSpacing: '-0.04em' }],
        'display-xl': ['clamp(3.5rem, 8vw, 8rem)', { lineHeight: '0.92', letterSpacing: '-0.035em' }],
        'display-lg': ['clamp(2.5rem, 5vw, 5.5rem)', { lineHeight: '0.98', letterSpacing: '-0.03em' }],
        'display-md': ['clamp(2rem, 3.5vw, 3.75rem)', { lineHeight: '1.05', letterSpacing: '-0.025em' }],
        'heading-1': ['clamp(1.75rem, 2.5vw, 2.75rem)', { lineHeight: '1.15', letterSpacing: '-0.02em' }],
        'heading-2': ['clamp(1.35rem, 1.8vw, 2rem)', { lineHeight: '1.25', letterSpacing: '-0.015em' }],
        'heading-3': ['1.25rem', { lineHeight: '1.35', letterSpacing: '-0.01em' }],
        'body-lg': ['1.125rem', { lineHeight: '1.6' }],
        'body-base': ['1rem', { lineHeight: '1.6' }],
        'body-sm': ['0.875rem', { lineHeight: '1.5' }],
        'caption': ['0.75rem', { lineHeight: '1.4', letterSpacing: '0.08em' }],
      },
      letterSpacing: {
        editorial: '-0.035em',
        caps: '0.12em',
      },
      borderWidth: {
        'hairline': '0.5px',
        '1': '1px',
      },
      boxShadow: {
        'editorial': '0 20px 40px -15px rgba(13, 15, 20, 0.07)',
        'editorial-hover': '0 30px 60px -15px rgba(13, 15, 20, 0.12)',
        'dark-card': '0 20px 40px -15px rgba(0, 0, 0, 0.4)',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-subtle': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        }
      },
      animation: {
        'fade-in': 'fade-in 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'pulse-subtle': 'pulse-subtle 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
    require('@tailwindcss/aspect-ratio'),
  ],
}
