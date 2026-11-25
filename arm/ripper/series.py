"""
Series discs: name the episodes the way media servers (Jellyfin, Plex, Emby) look them up, when the disc is ripped.

A disc labelled like NORTHERN_EXPOSURE_S3D2 goes into one folder per show:
    tv/Northern Exposure (1990)/Season 03/Northern Exposure S03E05.mkv
    tv/Northern Exposure (1990)/extras/Northern Exposure S02 disc 2 - 1.mkv
The "Play All" title (the episodes back to back) is skipped. Episodes are numbered in title order after the
season's highest episode on disk or planned for an earlier disc, so discs are numbered in the order they are
ripped, whatever order they are transcoded in. The plan is kept in track.new_filename (relative to job.path).
"""
import logging
import os
import re

from arm.ripper import utils
from arm.ui import db
from arm.models.job import Job, JobState
from arm.models.track import Track


def season_disc(label):
    """(season, disc) from a disc label such as SHOW_S1D2 or SHOW_SEASON_2_DISC_3, or None"""
    match = re.search(r"S(?:EASON)?_?(\d+)_?D(?:IS[CK])?_?(\d+)", (label or "").upper())
    return (int(match[1]), int(match[2])) if match else None


def title_number(filename):
    """MakeMKV's title number from a file name like C1_t04.mkv"""
    match = re.search(r"_t(\d+)\.", filename or "")
    return int(match[1]) if match else 999


def show_folder(job):
    """'Title (Year)' with the first year only: OMDb gives a series' years as 1990–1995"""
    title = job.title_manual or job.title
    year = re.match(r"\d{4}", job.year_manual or job.year or "")
    return f"{title} ({year[0]})" if year else title


def show_path(job):
    return os.path.join(job.config.COMPLETED_PATH, "tv", show_folder(job))


def planned_episodes(job, season_dir):
    """Episode numbers already used in a season: files on disk, and plans of other jobs not failed"""
    numbers = set()
    folder = os.path.join(show_path(job), season_dir)
    if os.path.isdir(folder):
        numbers |= {int(m[1]) for f in os.listdir(folder) if (m := re.search(r"S\d+E(\d+)", f))}
    others = (Track.query.join(Job, Track.job_id == Job.job_id)
              .filter(Job.job_id != job.job_id, Job.status != JobState.FAILURE.value,
                      Job.video_type == "series", Track.new_filename.like(f"{season_dir}/%")))
    for track in others:
        if show_folder(track.job) == show_folder(job) and (m := re.search(r"S\d+E(\d+)", track.new_filename)):
            numbers.add(int(m[1]))
    return numbers


def plan(job):
    """
    Plan the names of a ripped series disc's titles (track.new_filename) and mark Play All skipped.
    :return: True if the label had a season and disc (the titles are named), else False
    """
    tracks = sorted(job.tracks.filter_by(ripped=True), key=lambda t: title_number(t.filename))
    found = utils.find_play_all({t.filename: t.length or 0 for t in tracks})
    play_all, episodes = found if found else (None, {t.filename for t in tracks})
    for track in tracks:
        if track.filename == play_all:
            track.status = "skipped"
            logging.info(f"{track.filename} is a Play All title (the episodes back to back): not transcoded")
    sd = season_disc(job.label)
    if not sd:
        db.session.commit()
        return False
    season, disc = sd
    season_dir = f"Season {season:02d}"
    name = job.title_manual or job.title
    ext = job.config.DEST_EXT
    last = max(planned_episodes(job, season_dir), default=0)
    if disc > 1 and last == 0:
        logging.warning(f"Disc {disc} of season {season} ripped before disc {disc - 1}: its episodes start at E01")
    extra = 0
    for track in tracks:
        if track.filename == play_all:
            continue
        if track.filename in episodes:
            last += 1
            track.new_filename = f"{season_dir}/{name} S{season:02d}E{last:02d}.{ext}"
        else:
            extra += 1
            track.new_filename = f"extras/{name} S{season:02d} disc {disc} - {extra}.{ext}"
        logging.info(f"{track.filename} will be {track.new_filename}")
    db.session.commit()
    return True
