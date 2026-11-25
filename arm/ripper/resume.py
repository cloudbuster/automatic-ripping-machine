"""
Resume DVD/Blu-ray jobs that were stopped while transcoding (ARM's container or Docker restarted, e.g. by an
unattended upgrade). The rip is done and its files are in the raw folder, so the disc isn't needed: the job is
transcoded again from there and finishes as usual.

    resume.py           at container start: start one resume.py <job_id> per interrupted job
    resume.py <job_id>  finish that job
"""
import logging
import os
import signal
import subprocess
import sys
import datetime
from importlib.util import find_spec
from pathlib import Path

import psutil

# If the arm module can't be found, add the folder this file is in to PYTHONPATH
# This is a bad workaround for non-existent packaging
if find_spec("arm") is None:
    sys.path.append(str(Path(__file__).parents[2]))

from arm.models.job import Job, JobState  # noqa: E402

RESUMABLE = (JobState.TRANSCODE_WAITING.value, JobState.TRANSCODE_ACTIVE.value)


def running(job):
    """Is the job's own process still alive (same pid and start time)"""
    try:
        return job.pid is not None and job.pid_hash == hash(psutil.Process(job.pid))
    except psutil.NoSuchProcess:
        return False


def interrupted_jobs():
    return [job for job in Job.query.filter(Job.status.in_(RESUMABLE)).order_by(Job.job_id)
            if job.disctype in ("dvd", "bluray") and not running(job)]


def resume(job_id):
    from arm.ripper import arm_ripper, logger, makemkv, utils
    from arm.ui import db
    import arm.config.config as cfg

    def stop(_signal, _frame):
        raise utils.RipperException("Received SIGTERM")
    signal.signal(signal.SIGTERM, stop)

    job = Job.query.get(job_id)
    root = logging.getLogger()
    for handler in [h for h in root.handlers if isinstance(h, logging.FileHandler)]:
        root.removeHandler(handler)
    root.addHandler(logger._create_file_handler(job.logfile))
    root.setLevel(cfg.arm_config["LOGLEVEL"])
    logging.info("************* Resuming the transcode after ARM was stopped *************")
    job.get_pid()
    db.session.commit()

    raw = makemkv.raw_path_for(job)
    try:
        if not os.path.isdir(raw) or not os.listdir(raw):
            raise utils.RipperException(f"Raw files not found in {raw}: insert the disc again")
        # ponytail: transcodes every title again, also ones finished before the stop; skip those if it matters
        transcode_out = os.path.join(job.config.TRANSCODE_PATH, utils.convert_job_type(job.video_type),
                                     os.path.basename(job.path))
        os.makedirs(transcode_out, exist_ok=True)
        # protection=True: there are raw files, so MakeMKV ripped it (has_track_99 isn't kept in the database)
        arm_ripper.finish_visual_media(job, os.path.join(cfg.arm_config["LOGPATH"], job.logfile), True,
                                       True, raw, transcode_out, job.path, raw)
        job.status = JobState.SUCCESS.value
    except Exception as error:
        if str(error) == "Received SIGTERM" and job.status in RESUMABLE:
            logging.info(f"Stopped again; job left as '{job.status}' to be resumed when ARM starts again")
            return
        logging.critical(f"Resume failed: {error}", exc_info=True)
        job.status = JobState.FAILURE.value
        job.errors = str(error)
    finally:
        job.stop_time = datetime.datetime.now()
        db.session.commit()


def main():
    if sys.argv[1:]:
        resume(int(sys.argv[1]))
        return
    jobs = interrupted_jobs()
    for job in jobs:
        print(f"Resuming job {job.job_id} ({job.label})")
        subprocess.Popen([sys.executable, __file__, str(job.job_id)], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if jobs:
        from arm.models.notifications import Notifications
        from arm.ui import db
        titles = ", ".join(sorted({j.title or j.label for j in jobs}))
        message = (f"ARM was stopped while encoding {len(jobs)} disc(s) ({titles}). "
                   "It is finishing them from their raw rips; no need to insert them again.")
        db.session.add(Notifications("Resumed", message))
        db.session.commit()


if __name__ == "__main__":
    main()
