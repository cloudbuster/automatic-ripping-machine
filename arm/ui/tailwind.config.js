// Tailwind for the glass pages (home, job details); the Dockerfile builds static/css/home.css.
// Colors are CSS variables (static/css/home.src.css) so light and dark come from one set of class names.
module.exports = {
  content: ['templates/home.html', 'templates/glass_toggle.html', 'jobs/templates/jobdetail.html', 'static/js/home.js']
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
