// Tailwind for the home page (templates/home.html, static/js/home.js); the Dockerfile builds static/css/home.css.
// Colors are CSS variables (static/css/home.src.css) so light and dark come from one set of class names.
module.exports = {
  content: [__dirname + '/templates/home.html', __dirname + '/static/js/home.js'],
  theme: {
    extend: {
      fontFamily: { sans: ['Outfit', 'ui-sans-serif', 'system-ui', 'sans-serif'] },
      colors: {
        ink: 'var(--ink)', muted: 'var(--muted)', faint: 'var(--faint)', accent: 'var(--accent)',
        ok: 'var(--ok)', bad: 'var(--bad)', wait: 'var(--wait)',
      },
    },
  },
};
