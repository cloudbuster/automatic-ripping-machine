/* Home page: renders json?mode=home (arm/ui/home_api.py) and refreshes it. Plain JS, no libraries. */
(function () {
    "use strict";
    const body = document.body;
    const AUTH = body.dataset.auth === "1";
    const REFRESH = Math.max(1000, parseInt(body.dataset.refresh, 10) || 2000);
    const $ = (id) => document.getElementById(id);
    const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g,
        (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"}[c]));
    const pad = (n) => String(n).padStart(2, "0");
    let confirmStop = null;  // job id whose Stop button asks "are you sure"

    const STATES = {
        active: ["Starting", "p-acc", true], info: ["Reading disc", "p-acc", true],
        waiting: ["Waiting", "p-wait", false], ripping: ["Ripping", "p-acc", true],
        waiting_transcode: ["Waiting", "p-wait", false], transcoding: ["Encoding", "p-acc", true],
        success: ["Done", "p-ok", false], fail: ["Failed", "p-bad", false],
    };
    function pill(status) {
        const [text, cls, live] = STATES[status] || [status || "Unknown", "p-wait", false];
        return `<span class="pill ${cls}"><span class="dot${live ? " pulse" : ""}"></span>${esc(text)}</span>`;
    }

    function cover(job) {
        if (job.poster && /^https?:\/\//.test(job.poster)) {
            return `<img class="cover" src="${esc(job.poster)}" alt="" loading="lazy">`;
        }
        let hue = 0;
        for (const ch of job.title || "") hue = (hue * 31 + ch.charCodeAt(0)) % 360;
        const short = job.disctype === "bluray" ? "BD" : job.disctype === "music" ? "CD"
            : (job.title || "?").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
        return `<div class="cover" aria-hidden="true" style="background: linear-gradient(160deg, hsl(${hue} 55% 38%), hsl(${(hue + 40) % 360} 60% 24%))">${esc(short)}</div>`;
    }

    function range(eps) {
        if (!eps.length) return "";
        return eps.length === 1 ? `E${pad(eps[0])}` : `E${pad(eps[0])}–E${pad(eps[eps.length - 1])}`;
    }
    function plural(n, word) { return `${n} ${word}${n === 1 ? "" : "s"}`; }

    /** Where a job's files go, e.g. "4 episodes → Season 01, E05–E08" */
    function target(job) {
        if (job.video_type === "series" && job.episodes.length) {
            const extras = job.extras ? ` + ${plural(job.extras, "extra")}` : "";
            return `${plural(job.episodes.length, "episode")}${extras} → Season ${pad(job.season)}, ${range(job.episodes)}`;
        }
        if (job.video_type === "series") return job.files ? plural(job.files, "title") : "Series";
        if (job.disctype === "music") return "Music";
        if (job.video_type === "movie") return "Movies";
        return job.label || "";
    }
    function name(job) {
        const year = job.year && job.video_type !== "series" ? ` <span class="font-normal text-muted">(${esc(job.year)})</span>` : "";
        const disc = job.season ? ` <span class="font-normal text-muted">S${job.season} · disc ${job.disc}</span>` : "";
        return `${esc(job.title)}${year}${disc}`;
    }
    function stopButton(job) {
        if (!AUTH) return "";
        if (confirmStop === job.id) {
            return `<span class="flex items-center gap-2 text-sm text-muted">Stop this job?
                <button type="button" class="btn btn-bad" data-stop-yes="${job.id}">Stop</button>
                <button type="button" class="btn" data-stop-no>Keep</button></span>`;
        }
        return `<button type="button" class="btn" data-stop="${job.id}">Stop</button>`;
    }

    function driveCard(drive) {
        const states = {
            empty: ["Ready", "p-ok", "Empty", "Insert the next disc. ARM names it, rips it and opens the tray."],
            open: ["Tray open", "p-wait", "Tray open", "Put a disc in and close the tray."],
            disc: ["Disc in", "p-acc", "Disc in the drive", "ARM starts on its own within a few seconds."],
            unknown: ["Unknown", "p-wait", "Can't read the drive", "Check that the drive is plugged in, then restart ARM."],
        };
        let head, title, text;
        if (drive.state === "busy" && drive.current) {
            head = pill(drive.current.status);
            title = name(drive.current);
            text = esc(drive.current.status === "ripping" ? "Copying the disc; the tray opens when it's done."
                : "Identifying the disc.");
        } else {
            const s = states[drive.state] || states.unknown;
            head = `<span class="pill ${s[1]}"><span class="dot"></span>${s[0]}</span>`;
            title = esc(s[2]);
            text = esc(s[3]);
        }
        const last = drive.previous && drive.state !== "busy"
            ? `<p class="divider pt-4 text-sm text-muted">Last disc: <span class="font-medium text-ink">${esc(drive.previous.title)}${drive.previous.season ? ` S${drive.previous.season}D${drive.previous.disc}` : ""}</span>${drive.previous.stop ? `, ${esc(drive.previous.stop)}` : ""}</p>`
            : "";
        return `<article class="glass flex flex-col gap-4 rounded-2xl p-6 md:col-span-2">
            <div class="flex items-center justify-between gap-3"><span class="label">Drive · ${esc(drive.mount)}</span>${head}</div>
            <div class="flex items-center gap-4">
                <svg width="56" height="56" viewBox="0 0 56 56" fill="none" aria-hidden="true">
                    <rect x="3" y="18" width="50" height="20" rx="5" fill="var(--track)" stroke="var(--accent)" stroke-width="1.5"/>
                    <rect x="9" y="27" width="22" height="3" rx="1.5" fill="var(--accent)" opacity=".5"/>
                    <circle cx="45" cy="28.5" r="2.2" fill="${drive.state === "busy" ? "var(--accent)" : "var(--ok)"}"/>
                </svg>
                <div class="min-w-0"><h2 class="text-lg font-bold">${title}</h2><p class="text-sm text-muted">${text}</p></div>
            </div>${last}</article>`;
    }

    function nowCard(job) {
        if (!job) {
            return `<article class="glass flex flex-col justify-center gap-2 rounded-2xl p-6 md:col-span-3">
                <span class="label">Encoding now</span><h2 class="text-lg font-bold">Nothing to encode</h2>
                <p class="text-sm text-muted">Finished discs are in your library.</p></article>`;
        }
        const encoding = job.status === "transcoding";
        const pct = encoding && job.disc_progress != null ? job.disc_progress : job.progress;
        const step = encoding && job.file ? `${job.video_type === "series" ? "Episode" : "Title"} ${job.file} of ${job.files}` : STATES[job.status] ? STATES[job.status][0] : "";
        const eta = job.eta && job.eta !== "Unknown" ? `${esc(job.eta)} left for this file` : "";
        return `<article class="glass flex flex-col gap-4 rounded-2xl p-6 md:col-span-3">
            <div class="flex items-center justify-between gap-3"><span class="label">${encoding ? "Encoding now" : "Working on"}</span>${pill(job.status)}</div>
            <div class="flex items-start gap-4">${cover(job)}
                <div class="min-w-0 flex-1"><h2 class="text-lg font-bold leading-snug">${name(job)}</h2>
                <p class="text-sm text-muted">${esc(step)}${step ? " · " : ""}<span class="text-ink">${esc(target(job))}</span></p></div>
                ${stopButton(job)}
            </div>
            <div><div class="bar" role="progressbar" aria-valuenow="${Math.round(pct)}" aria-valuemin="0" aria-valuemax="100" aria-label="Progress"><i style="width: ${Math.min(100, pct)}%"></i></div>
            <div class="mt-2 flex justify-between gap-3 text-sm text-muted"><span><span class="font-semibold text-ink">${Math.round(pct)}%</span>${encoding && job.files > 1 ? " of the disc" : ""}${job.fps ? ` · ${esc(Math.round(job.fps))} fps` : ""}</span><span>${eta}</span></div></div>
            </article>`;
    }

    function queueItem(job) {
        return `<li class="glass lift flex items-center gap-4 rounded-2xl p-4">${cover(job)}
            <div class="min-w-0 flex-1"><p class="truncate font-semibold">${name(job)}</p>
            <p class="truncate text-sm text-muted">${esc(target(job))}</p></div>${pill(job.status)}${stopButton(job)}</li>`;
    }

    function finishedCard(g) {
        let title = `${esc(g.title)}${g.year && g.video_type !== "series" ? ` <span class="font-normal text-muted">(${esc(g.year)})</span>` : ""}`;
        const meta = [];
        if (g.season) {
            title = `${esc(g.title)}, Season ${g.season}`;
            const discs = g.discs.length > 1 && g.discs.every((d, i) => i === 0 || d === g.discs[i - 1] + 1)
                ? `Discs ${g.discs[0]}–${g.discs[g.discs.length - 1]}` : `${g.discs.length > 1 ? "Discs" : "Disc"} ${g.discs.join(", ")}`;
            meta.push(discs);
            if (g.episodes.length) meta.push(range(g.episodes));
            if (g.extras) meta.push(plural(g.extras, "extra"));
        } else if (g.discs.length > 1) {
            meta.push(`${g.discs.length} discs`);
        }
        if (g.status === "fail") meta.push(/SIGTERM/.test(g.errors) ? "Stopped by a restart" : g.errors || "See the log");
        else if (g.stop) meta.push(g.stop);
        const kind = {bluray: "Blu-ray", dvd: "DVD", music: "CD", data: "Data"}[g.disctype] || "";
        const link = AUTH ? `href="jobdetail?job_id=${g.jobs[0]}"` : "";
        return `<a ${link} class="glass lift flex gap-4 rounded-2xl p-4">${cover(g)}
            <div class="min-w-0"><div class="flex items-center gap-2">${pill(g.status)}<span class="label">${esc(kind)}</span></div>
            <p class="mt-1 font-semibold">${title}</p><p class="text-sm text-muted">${esc(meta.join(" · "))}</p></div></a>`;
    }

    function noteCard(note) {
        const close = AUTH ? `<button type="button" class="btn ml-auto" data-note="${esc(note.id)}">Dismiss</button>` : "";
        return `<aside class="glass flex items-start gap-3 rounded-2xl px-5 py-4">
            <span class="pill p-acc mt-0.5">${esc(note.title || "Notice")}</span>
            <p class="min-w-0 text-sm text-muted">${esc(note.message)}</p>${close}</aside>`;
    }

    function gb(bytes) { return bytes == null ? "" : `${Math.round(bytes / 1e9)} GB free`; }

    function render(data) {
        const drives = data.drives || [];
        const active = data.active || [];
        const now = active.find((j) => j.status === "transcoding") || null;
        const inDrive = new Set(drives.filter((d) => d.current).map((d) => d.current.id));
        const queue = active.filter((j) => j !== now && !inDrive.has(j.id));
        const model = drives.map((d) => d.model).filter(Boolean)[0];
        $("badge-text").textContent = [data.name, model].filter(Boolean).join(" · ");
        $("now").innerHTML = (drives.length ? drives.map(driveCard).join("")
            : `<article class="glass rounded-2xl p-6 md:col-span-2"><span class="label">Drive</span><h2 class="mt-2 text-lg font-bold">No drive found</h2><p class="text-sm text-muted">Plug in the drive, then restart ARM.</p></article>`)
            + nowCard(now);
        $("notes").innerHTML = (data.notes || []).slice(0, 3).map(noteCard).join("");
        $("queue-section").hidden = !queue.length;
        $("queue").innerHTML = queue.map(queueItem).join("");
        $("queue-count").textContent = queue.length ? plural(queue.length, "disc") : "";
        $("finished-section").hidden = !(data.finished || []).length;
        $("finished").innerHTML = (data.finished || []).map(finishedCard).join("");
        $("free").textContent = gb(data.free_bytes);
        $("version").textContent = data.version ? `ARM ${data.version}` : "";
    }

    let last = null;
    async function load() {
        if (document.hidden) return;
        try {
            const response = await fetch("json?mode=home", {cache: "no-store"});
            if (!response.ok) throw new Error(`the server answered ${response.status}`);
            last = await response.json();
            render(last);
            $("error").hidden = true;
        } catch (error) {
            $("error").textContent = `Can't reach ARM (${error.message}). Retrying…`;
            $("error").hidden = false;
        }
    }

    document.addEventListener("click", async (event) => {
        const t = event.target.closest("button");
        if (!t) return;
        if (t.dataset.stop) { confirmStop = Number(t.dataset.stop); if (last) render(last); }
        else if (t.hasAttribute("data-stop-no")) { confirmStop = null; if (last) render(last); }
        else if (t.dataset.stopYes) {
            confirmStop = null;
            await fetch(`json?mode=abandon&job=${encodeURIComponent(t.dataset.stopYes)}`);
            load();
        } else if (t.dataset.note) {
            await fetch(`json?mode=read_notification&notify_id=${encodeURIComponent(t.dataset.note)}`);
            load();
        }
    });

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

    document.addEventListener("visibilitychange", load);
    load();
    setInterval(load, REFRESH);
}());
