// Tailwind for every page of the UI (all templates are glass pages now); the Dockerfile builds static/css/home.css.
// Colors are CSS variables (static/css/home.src.css) so light and dark come from one set of class names.
module.exports = {
  content: ['templates/*.html', '*/templates/**/*.html', 'static/js/*.js']
    .map((f) => __dirname + '/' + f),
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
