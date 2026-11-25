"""
What the home page shows (templates/home.html, static/js/home.js), as one JSON answer: the drives, the jobs in
progress with how far they are, the finished discs grouped by show/season or film, unread notifications, free space.
"""
import os
import re

import psutil

import arm.config.config as cfg
from arm.models.job import Job, JobState
from arm.models.system_drives import SystemDrives, CDS
from arm.ui import json_api

FINISHED = (JobState.SUCCESS.value, JobState.FAILURE.value)


def _episodes(tracks):
    return sorted(int(m[1]) for t in tracks if t.new_filename and (m := re.search(r"S\d+E(\d+)", t.new_filename)))


def job_summary(job):
    from arm.ripper.series import first_year, season_disc
    tracks = [t for t in job.tracks if t.ripped]
    kept = [t for t in tracks if t.status != "skipped"]
    season, disc = season_disc(job.label) or (None, None)
    return {
        "id": job.job_id, "title": job.title_manual or job.title or job.label or "Unknown disc", "year": first_year(job),
        "label": job.label, "disctype": job.disctype, "video_type": job.video_type, "status": job.status,
        "poster": job.poster_url_manual or job.poster_url or "", "season": season, "disc": disc,
        "episodes": _episodes(tracks),
        "extras": sum(1 for t in tracks if (t.new_filename or "").startswith("extras/")),
        "files": len(kept), "errors": job.errors or "", "path": job.path or "",
        "stop": job.stop_time.strftime("%d %b %H:%M") if job.stop_time else "",
    }


def _progress(job, summary):
    """Percent, ETA and speed from ARM's log parsing, plus which file of the disc HandBrake is on"""
    results = {}
    json_api.process_logfile(os.path.join(cfg.arm_config["LOGPATH"], str(job.logfile)), job, results)
    summary.update(progress=float(getattr(job, "progress", 0) or 0), eta=getattr(job, "eta", "") or "",
                   fps=getattr(job, "cur_fps", "") or "")
    if job.status == JobState.TRANSCODE_ACTIVE.value and summary["files"]:
        log = os.path.join(cfg.arm_config["LOGPATH"], str(job.logfile))
        try:
            with open(log, errors="replace") as file:
                started = sum(1 for line in file if "Transcoding file " in line)
        except OSError:
            started = 0
        current = max(1, min(started, summary["files"]))
        summary.update(file=current, disc_progress=round(((current - 1) + summary["progress"] / 100)
                                                         / summary["files"] * 100, 1))
    return summary


def _drive(drive):
    try:
        tray = drive.tray_status()
    except Exception:  # noqa: B902 - no device in this container, permissions
        tray = None
    state = {CDS.TRAY_OPEN: "open", CDS.NO_DISC: "empty", CDS.DISC_OK: "disc"}.get(tray, "unknown")
    if drive.job_current is not None and not drive.job_current.finished:
        state = "busy"
    previous = drive.job_previous
    return {
        "name": drive.name or drive.model or drive.mount, "model": " ".join(filter(None, [drive.maker, drive.model])),
        "mount": drive.mount, "state": state,
        "current": job_summary(drive.job_current) if state == "busy" else None,
        "previous": job_summary(previous) if previous is not None else None,
    }


def _group(jobs):
    """Finished discs of the same show and season (or the same film) together, newest first"""
    groups = {}
    for job in jobs:
        s = job_summary(job)
        key = (s["title"], s["year"], s["season"], s["status"])
        g = groups.setdefault(key, {**s, "discs": [], "episodes": [], "extras": 0, "jobs": []})
        g["discs"].append(s["disc"] or len(g["discs"]) + 1)
        g["episodes"] += s["episodes"]
        g["extras"] += s["extras"]
        g["jobs"].append(s["id"])
        g["poster"] = g["poster"] or s["poster"]
    for g in groups.values():
        g["discs"].sort()
        g["episodes"].sort()
    return list(groups.values())


def home_status():
    drives = [_drive(d) for d in SystemDrives.query.filter(SystemDrives.stale.isnot(True)).all()]
    active = [_progress(j, job_summary(j))
              for j in Job.query.filter(~Job.finished).order_by(Job.job_id).all()]
    finished = Job.query.filter(Job.status.in_(FINISHED)).order_by(Job.job_id.desc()).limit(40).all()
    try:
        free = psutil.disk_usage(cfg.arm_config["COMPLETED_PATH"]).free
    except OSError:
        free = None
    try:
        with open(os.path.join(cfg.arm_config["INSTALLPATH"], "VERSION")) as file:
            version = file.read().strip()
    except OSError:
        version = ""
    return {
        "success": True, "mode": "home", "name": cfg.arm_config.get("ARM_NAME") or "ARM", "version": version,
        "drives": drives, "active": active, "finished": _group(finished)[:8],
        "notes": json_api.get_notifications(), "free_bytes": free,
    }
