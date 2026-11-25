// Settings page (settings/settings.html): one section at a time by the URL hash, and saving forms without leaving the page
(function () {
    const tabs = [...document.querySelectorAll("#tabs [data-tab]")];
    function show() {
        const id = (location.hash || "#general").slice(1);
        const current = tabs.some((t) => t.dataset.tab === id) ? id : "general";
        document.querySelectorAll("section.tab").forEach((s) => { s.hidden = s.id !== current; });
        tabs.forEach((t) => t.toggleAttribute("aria-current", t.dataset.tab === current));
    }
    tabs.forEach((t) => t.addEventListener("click", (event) => {  // switch without jumping down to the section
        event.preventDefault();
        history.replaceState(null, "", `#${t.dataset.tab}`);
        show();
    }));
    addEventListener("hashchange", show);
    show();

    document.querySelectorAll("form[data-save]").forEach((form) => form.addEventListener("submit", async (event) => {
        event.preventDefault();
        let ok = false;
        try {
            const response = await fetch(form.dataset.save, {method: "POST", body: new URLSearchParams(new FormData(form))});
            ok = response.ok && (await response.json()).success === true;
        } catch (e) { /* network error: reported below */ }
        const button = form.querySelector("[type=submit]");
        const note = button.nextElementSibling || button.insertAdjacentElement("afterend", document.createElement("span"));
        note.setAttribute("role", "status");
        note.className = `ml-3 text-sm ${ok ? "text-ok" : "text-bad"}`;
        note.textContent = ok ? `Saved at ${new Date().toLocaleTimeString()}` : "Not saved. Check the values, or the log.";
    }));
}());
