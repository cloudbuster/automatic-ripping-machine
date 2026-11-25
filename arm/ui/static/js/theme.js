// Light / dark toggle for the glass pages (templates/glass_toggle.html): follows the system until used, then remembers
(function () {
    const $ = (id) => document.getElementById(id);
    // Light / dark: follows the system until the button is used, then remembers the choice
    const root = document.documentElement;
    const isDark = () => root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    function showIcon() { const d = isDark(); $("icon-moon").hidden = d; $("icon-sun").hidden = !d; }
    $("theme-toggle").addEventListener("click", () => {
        root.dataset.theme = isDark() ? "light" : "dark";
        try { localStorage.setItem("arm-theme", root.dataset.theme); } catch (e) { /* private window */ }
        showIcon();
    });
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", showIcon);
    showIcon();

}());
