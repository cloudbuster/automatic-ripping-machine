""" Main file for running DVDs/Blu-rays/CDs/data ?
It would help clear up main and make things easier to find
"""
import contextlib
import sys
import os
import logging
from importlib.util import find_spec
from pathlib import Path

# If the arm module can't be found, add the folder this file is in to PYTHONPATH
# This is a bad workaround for non-existent packaging
if find_spec("arm") is None:
    sys.path.append(str(Path(__file__).parents[2]))

from arm.ripper import utils, makemkv, handbrake, ffmpeg, series  # noqa E402
from arm.ui import app, db, constants  # noqa E402
from arm.models.job import JobState  # noqa E402


def rip_visual_media(have_dupes, job, logfile, protection):
    """
    Main ripping function for dvd and Blu-rays, movies or series
    \n
    :param have_dupes: Does this disc already exist in the database
    :param job: Current job
    :param logfile: Current logfile
    :param protection: Does the disc have 99 track protection
    :return: None
    """
    # Fix the sub-folder type - (movie|tv|unknown)
    type_sub_folder = utils.convert_job_type(job.video_type)
    # A series disc with season and disc in its label goes into the show's folder (series.py); one without
    # them can't be numbered, so a person sorts it
    episodes = job.video_type == "series" and series.season_disc(job.label)
    if job.video_type == "series" and not episodes:
        logging.info(f"No season and disc in the label {job.label}: the episodes go to unidentified/")
        type_sub_folder = "unidentified"
    # Fix the job title - Title (Year) | Title
    job_title = utils.fix_job_title(job)

    # We need to check/construct the final path, and the transcode path
    transcode_out_path = os.path.join(job.config.TRANSCODE_PATH, type_sub_folder, job_title)
    final_directory = os.path.join(job.config.COMPLETED_PATH, type_sub_folder, job_title)

    # Check folders for already ripped jobs -> creates folder
    transcode_out_path = utils.check_for_dupe_folder(have_dupes, transcode_out_path, job)
    if episodes:
        final_directory = series.show_path(job)  # shared by all discs of the show; file names are unique
        utils.make_dir(final_directory)
    elif job.video_type == "movie" and not have_dupes and (
            utils.film_disc(job.label) > 1 or not utils.has_film(final_directory, job.config.DEST_EXT)):
        # A bonus disc (label ..._D2) shares the film's folder; its titles go to extras/ (move_files_post).
        # A folder without the film (an earlier try failed) is reused, not left empty next to "Title (Year)_<n>".
        utils.make_dir(final_directory)
    else:
        # If dupes rips is disabled this might kill the run
        final_directory = utils.check_for_dupe_folder(have_dupes, final_directory, job)

    # Update the job.path with the final directory
    utils.database_updater({'path': final_directory}, job)
    # Save poster image from disc if enabled
    utils.save_disc_poster(final_directory, job)

    logging.info(f"Processing files to: {transcode_out_path}")
    makemkv_out_path = None
    transcode_in_path = str(job.devpath)
    # Do we need to use MakeMKV - Blu-rays, protected dvd's, and dvd with mainfeature off
    use_make_mkv = rip_with_mkv(job, protection)
    logging.debug(f"Using MakeMKV: [{use_make_mkv}]")
    if use_make_mkv:
        logging.info("************* Ripping disc with MakeMKV *************")
        # Run MakeMKV and get path to output
        job.status = JobState.VIDEO_RIPPING.value
        db.session.commit()
        try:
            makemkv_out_path = makemkv.makemkv(job)
        except Exception as mkv_error:  # noqa: E722
            raise utils.RipperException("Error while running MakeMKV") from mkv_error

        if job.config.NOTIFY_RIP:
            utils.notify(job, constants.NOTIFY_TITLE, f"{job.title} rip complete. Starting transcode. ")
        logging.info("************* Ripping with MakeMKV completed *************")
        # point HB/FFMPEG to the path MakeMKV ripped to
        transcode_in_path = makemkv_out_path
        if job.video_type == "series":
            series.plan(job)  # names in rip order; marks Play All skipped
    finish_visual_media(job, logfile, protection, use_make_mkv, transcode_in_path, transcode_out_path,
                        final_directory, makemkv_out_path)


def finish_visual_media(job, logfile, protection, use_make_mkv, transcode_in_path, transcode_out_path,
                        final_directory, makemkv_out_path):
    """
    Everything after the rip: transcode, move to the final folder, clean up.
    Also run on its own by resume.py for a job stopped while transcoding.
    """
    type_sub_folder = utils.convert_job_type(job.video_type)
    # Begin transcoding section - only transcode if skip_transcode is false
    start_transcode(job, logfile, transcode_in_path, transcode_out_path, protection)

    # --------------- POST PROCESSING ---------------
    # If ripped with MakeMKV remove the 'out' folder and set the raw as the output
    logging.debug(f"Transcode status: [{job.config.SKIP_TRANSCODE}] and MakeMKV Status: [{use_make_mkv}]")
    if job.config.SKIP_TRANSCODE and use_make_mkv:
        utils.delete_raw_files([transcode_out_path])
        transcode_out_path = transcode_in_path

    # Update final path if user has set a custom/manual title
    logging.debug(f"Job title status: [{job.title_manual}]")
    if job.title_manual and not (job.video_type == "series" and series.season_disc(job.label)):
        # Remove the old final dir if empty: it may be the folder of a film this disc is the bonus disc of
        with contextlib.suppress(OSError):
            os.rmdir(final_directory)
        job_title = utils.fix_job_title(job)
        final_directory = os.path.join(job.config.COMPLETED_PATH, type_sub_folder, job_title)
        # Update the job.path with the final directory
        utils.database_updater({'path': final_directory}, job)

    # Move to final folder
    move_files_post(transcode_out_path, job)
    # Movie the movie poster if we have one - no longer needed, now handled by save_movie_poster
    utils.move_movie_poster(final_directory, transcode_out_path)
    # Scan Emby if arm.yaml requires it
    utils.scan_emby()
    # Set permissions if arm.yaml requires it
    utils.set_permissions(final_directory)
    # If set in the arm.yaml remove the raw files, but never with an encoded file not moved (it was lost on 26 Nov)
    left = [f for f in os.listdir(transcode_out_path) if f.endswith("." + job.config.DEST_EXT)] \
        if transcode_out_path != transcode_in_path and os.path.isdir(transcode_out_path) else []
    if left:
        logging.error(f"Not moved: {left} in {transcode_out_path}. Keeping the raw and transcoded files")
        utils.notify(job, constants.NOTIFY_TITLE, f"{job.title}: {len(left)} file(s) not moved, kept in "
                                                  f"{transcode_out_path}")
    else:
        utils.delete_raw_files([transcode_in_path, transcode_out_path, makemkv_out_path])
    # report errors if any
    notify_exit(job)
    logging.info("************* ARM processing complete *************")


def start_transcode(job, logfile, raw_in_path, transcode_out_path, protection):
    """
    This checks if transcoding is enabled for the job and then passes it off to the correct
    transcoding function, first if handbrake or ffmpegshould be used, then how it should be ripped\n
    :param raw_in_path: HandBrake in path (makeMKV_out_path|/dev/sr0)
    :param transcode_out_path: Path HandBrake should put the files (transcode_path)
    :param job: Current job
    :param logfile: Current logfile
    :param protection: If disc has 99 track protection
    :return: None
    """
    if job.config.SKIP_TRANSCODE:
        logging.info("Transcoding is disabled, skipping transcode")
        return None

    # Update db with transcoding status
    utils.database_updater({'status': "transcoding"}, job)
    # Use FFMPEG or HandBrake depending on arm.yaml setting
    if job.config.USE_FFMPEG:
        logging.info("************* Starting Transcode With FFMPEG *************")
        # If it was ripped with MakeMKV or we are doing a mkv rip then run the ffmpeg_mkv function
        if rip_with_mkv(job, protection) and job.config.RIPMETHOD == "mkv":
            logging.debug(f"ffmpeg_mkv: {raw_in_path}, {transcode_out_path}")
            ffmpeg.ffmpeg_mkv(raw_in_path, transcode_out_path, job)
        # Otherwise if it is a movie and mainfeature is enabled then run ffmpeg_main_feature
        elif job.video_type == "movie" and job.config.MAINFEATURE and job.hasnicetitle:
            logging.debug(f"ffmpeg_main_feature: {raw_in_path}, {transcode_out_path}")
            ffmpeg.ffmpeg_main_feature(raw_in_path, transcode_out_path, job)
            db.session.commit()
        # Finally if it is a series or mainfeature is disabled run ffmpeg_all to transcode all tracks
        else:
            logging.debug(f"ffmpeg_all: {raw_in_path}, {transcode_out_path}")
            ffmpeg.ffmpeg_all(raw_in_path, transcode_out_path, job)
            db.session.commit()
        logging.info("************* Finished Transcode With FFMPEG *************")
        # After transcoding update db status back to active
        utils.database_updater({'status': "active"}, job)
        return True

    elif not job.config.USE_FFMPEG:
        logging.info("************* Starting Transcode With HandBrake *************")
        # If it was ripped with MakeMKV or we are doing a mkv rip then run the handbrake_mkv function
        if rip_with_mkv(job, protection) and job.config.RIPMETHOD == "mkv":
            logging.debug(f"handbrake_mkv: {raw_in_path}, {transcode_out_path}, {logfile}")
            handbrake.handbrake_mkv(raw_in_path, transcode_out_path, logfile, job)
        # Otherwise if it is a movie and mainfeature is enabled then run handbrake_main_feature
        elif job.video_type == "movie" and job.config.MAINFEATURE and job.hasnicetitle:
            logging.debug(f"handbrake_main_feature: {raw_in_path}, {transcode_out_path}, {logfile}")
            handbrake.handbrake_main_feature(raw_in_path, transcode_out_path, logfile, job)
            db.session.commit()
        # Finally if it is a series or mainfeature is disabled run handbrake_all to transcode all tracks
        else:
            logging.debug(f"handbrake_all: {raw_in_path}, {transcode_out_path}, {logfile}")
            handbrake.handbrake_all(raw_in_path, transcode_out_path, logfile, job)
            db.session.commit()
        logging.info("************* Finished Transcode With HandBrake *************")
        # After transcoding update db status back to active
        utils.database_updater({'status': "active"}, job)
        return True
    else:
        logging.info("Invalid transcoding option selected. Skipping transcode."
                     "Set USE_FFMPEG with valid boolean value fix error")
        return None


def notify_exit(job):
    """
    Notify post transcoding - ARM finished\n
    Includes any errors
    :param job: current job
    :return: None
    """
    if job.config.NOTIFY_TRANSCODE:
        if job.errors:
            errlist = ', '.join(job.errors)
            utils.notify(job, constants.NOTIFY_TITLE,
                         f" {job.title} processing completed with errors. "
                         f"Title(s) {errlist} failed to complete. ")
            logging.info(f"Transcoding completed with errors.  Title(s) {errlist} failed to complete. ")
        else:
            utils.notify(job, constants.NOTIFY_TITLE, f"{job.title} {constants.PROCESS_COMPLETE}")


def move_files_post(transcode_out_path, job):
    """
    Logic for moving files post transcoding\n
    if series move all to 1 folder\n
    if movie check what source we got them from, for MakeMKV use skip_transcode_movie, so we can check filesize\n
    :param transcode_out_path: This should either be the RAW_PATH from MakeMKV, /dev/srX or TRANSCODE_PATH
    :param job: current job
    :return: None
    """
    tracks = job.tracks.filter_by(ripped=True)  # .order_by(job.tracks.length.desc())
    if job.video_type == "series":
        for track in tracks:
            if track.status == "skipped":  # Play All, not transcoded (series.plan)
                continue
            if track.new_filename:  # Season 03/Show S03E05.mkv or extras/... (series.plan)
                new_file = os.path.join(job.path, track.new_filename)
                utils.make_dir(os.path.dirname(new_file))
                logging.info(f"Moving {track.filename} to {new_file}")
                utils.move_files_main(os.path.join(transcode_out_path, track.filename), new_file,
                                      os.path.dirname(new_file))
            else:
                utils.move_files(transcode_out_path, track.filename, job, False)
    elif job.video_type == "movie" and utils.film_disc(job.label) > 1 and utils.has_film(job.path, job.config.DEST_EXT):
        move_bonus_disc(transcode_out_path, job)
    else:
        for track in tracks:
            if tracks.count() == 1:
                utils.move_files(transcode_out_path, track.filename, job, True)
            else:
                # If source is MakeMKV we know the mainfeature will be wrong let skip_transcode_movie handle it
                if track.source == "MakeMKV":
                    skip_transcode_movie(os.listdir(transcode_out_path), job, transcode_out_path)
                    break
                # If HandBrake was used we can pass track.main_feature
                utils.move_files(transcode_out_path, track.filename, job, track.main_feature)


FILM_PART_MIN = 3600  # seconds: a title this long on a later disc is the film's next part, not an extra


def move_bonus_disc(transcode_out_path, job):
    """
    A film's later disc (label ..._D2, ripped after the film's first disc). A title of an hour or more is the film's
    next part (Spartacus: 3 h 17 min on two discs): Title (Year) - part2.mkv, and the first disc's file becomes
    - part1.mkv, the names Jellyfin, Plex and Emby play as one film. Every other title goes into the extras
    folder, Title (Year)/extras/Title (Year) - disc 2 - 1.mkv, in title order.
    """
    # ponytail: length alone decides; a feature-length documentary on a bonus disc would count as a part
    base = os.path.basename(job.path)
    ext = "." + job.config.DEST_EXT
    disc = utils.film_disc(job.label)
    lengths = {t.filename: t.length or 0 for t in job.tracks}
    files = sorted((f for f in os.listdir(transcode_out_path) if f.endswith(ext)),
                   key=lambda f: (series.title_number(f), f))
    part = max(files, key=lambda f: lengths.get(f, 0), default=None)
    if part and lengths.get(part, 0) >= FILM_PART_MIN:
        film = os.path.join(job.path, base + ext)
        if os.path.isfile(film):
            logging.info(f"Disc {disc} continues the film: {film} becomes part 1")
            os.rename(film, os.path.join(job.path, f"{base} - part1{ext}"))
        new_file = os.path.join(job.path, f"{base} - part{disc}{ext}")
        logging.info(f"Disc {disc}: moving {part} ({lengths[part] // 60} min) to {new_file}")
        utils.move_files_main(os.path.join(transcode_out_path, part), new_file, job.path)
        files.remove(part)
    extras = os.path.join(job.path, job.config.EXTRAS_SUB)
    for number, file in enumerate(files, 1):
        utils.make_dir(extras)
        new_file = os.path.join(extras, f"{base} - disc {disc} - {number}{ext}")
        logging.info(f"Bonus disc {disc}: moving {file} to {new_file}")
        utils.move_files_main(os.path.join(transcode_out_path, file), new_file, extras)


def rip_with_mkv(current_job, protection=0):
    """
    Test to check if title was or should be ripped by MakeMKV\n
    :param current_job: current job
    :param protection: If the disc have 99 track protection
    :return: Bool
    """
    mkv_ripped = False
    # Rip bluray
    if current_job.disctype == "bluray":
        mkv_ripped = True
    # Rip dvd with mode: mkv and mainfeature: false
    if current_job.disctype == "dvd" and (not current_job.config.MAINFEATURE and current_job.config.RIPMETHOD == "mkv"):
        mkv_ripped = True
    # Rip dvds with skip transcode
    if current_job.disctype == "dvd" and current_job.config.SKIP_TRANSCODE:
        mkv_ripped = True
    # If dvd has 99 protection force MakeMKV to be used
    if protection and current_job.disctype == "dvd":
        mkv_ripped = True
    # if backup_dvd, always use mkv
    if current_job.config.RIPMETHOD == "backup_dvd":
        mkv_ripped = True
    return mkv_ripped


def skip_transcode_movie(files, job, raw_path):
    """
    Only ran if job is a movie - find the largest file use it as mainfeature\n
    Move everything else to extras folder\n
    If mainfeature is enabled skip moving everything but the main file\n
    :param files: os.listdir(RAW_PATH)
    :param job: Current job
    :param raw_path: RAW_PATH of ripped mkv files (mkvoutpath)
    :return: None
    """
    logging.debug(f"Videotype: {job.video_type}")
    # if video_type is movie, then move the biggest title to media_dir
    # move the rest of the files to the extras' folder
    # find largest filesize
    logging.debug("Finding largest file")
    largest_file_name = utils.find_largest_file(files, raw_path)
    # largest_file_name should be the largest file
    logging.debug(f"Largest file is: {largest_file_name}")
    temp_path = os.path.join(raw_path, largest_file_name)
    if os.stat(temp_path).st_size <= 1:  # sanity check for filesize
        logging.info(f"{raw_path} is empty or very small size. - Folder size: {os.stat(temp_path).st_size}")
    for file in files:
        # move main into main folder
        # move others into extras folder
        if file == largest_file_name:
            # largest movie
            utils.move_files(raw_path, file, job, True)
        else:
            # If mainfeature is enabled - skip to the next file
            if job.config.MAINFEATURE:
                logging.info(f"MAINFEATURE IS {job.config.MAINFEATURE} - Skipping move of {file}")
                continue
            # Other/extras
            if str(job.config.EXTRAS_SUB).lower() != "none":
                utils.move_files(raw_path, file, job, False)
            else:
                logging.info(f"Not moving extra: \"{file}\" - Sub folder is not set or named incorrectly")
