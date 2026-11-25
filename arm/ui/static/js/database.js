// Database page (database/templates/databaseview.html): Abandon / Fix permissions / Delete per job, each asks once inline
(function () {
    const NAMES = {abandon: "Abandon", fixperms: "Fix permissions", delete: "Delete"};
    document.getElementById("jobs").addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-act], button[data-yes], button[data-no]");
        if (!button) return;
        const row = button.closest("li[data-job]");
        const actions = row.querySelector(".actions");
        if (button.dataset.act) {
            actions.dataset.html = actions.innerHTML;
            actions.innerHTML = `<span class="text-sm">${NAMES[button.dataset.act]} job ${row.dataset.job}?</span>
                <button type="button" class="btn btn-bad" data-yes="${button.dataset.act}">Yes</button>
                <button type="button" class="btn" data-no>No</button>`;
            return;
        }
        if (button.hasAttribute("data-no")) { actions.innerHTML = actions.dataset.html; return; }
        const act = button.dataset.yes;
        let data = {};
        try {
            data = await (await fetch(`json?mode=${act}&job=${encodeURIComponent(row.dataset.job)}`)).json();
        } catch (e) { /* reported below */ }
        if (data.success && act === "delete") { row.remove(); return; }
        if (data.success && act === "abandon") { location.reload(); return; }
        actions.innerHTML = actions.dataset.html;
        const note = document.createElement("span");
        note.className = `text-sm ${data.success ? "text-ok" : "text-bad"}`;
        note.setAttribute("role", "status");
        note.textContent = data.success ? "Done" : `Failed${data.Error ? ": " + data.Error : ""}`;
        actions.append(note);
    });
}());
