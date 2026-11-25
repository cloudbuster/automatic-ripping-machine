#!/bin/bash
# Finish jobs that were stopped while transcoding (arm/ripper/resume.py). Runs in the background after the
# web UI has had time to upgrade the database.
(sleep 60 && cd /home/arm && /sbin/setuser arm python3 /opt/arm/arm/ripper/resume.py >> /home/arm/logs/arm.log 2>&1) &
