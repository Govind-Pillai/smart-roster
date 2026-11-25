export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#3B82F6', dark: '#1D4ED8', light: '#93C5FD' },
        success: '#22C55E',
        warning: '#F59E0B',
        danger: '#EF4444',
      }
    }
  },
  plugins: []
}
