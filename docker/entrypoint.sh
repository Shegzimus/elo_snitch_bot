#!/bin/sh
# Container entrypoint: prepare the volume, start the pipeline timer, hand over
# to the bot.
set -eu

# The volume is empty on first deploy, and these are the targets of the
# symlinks Dockerfile.fly created.
mkdir -p /data/snapshots /data/wwebjs_auth

# The Google service-account JSON is a Fly secret. Secrets are single-line, so
# it travels base64-encoded. config.py expects it at <project root>/.google/.
if [ -n "${GOOGLE_CREDENTIALS_B64:-}" ]; then
    mkdir -p /app/.google
    echo "$GOOGLE_CREDENTIALS_B64" | base64 -d > /app/.google/credentials.json
    chmod 600 /app/.google/credentials.json
else
    echo "[entrypoint] GOOGLE_CREDENTIALS_B64 unset -- the pipeline cannot read the sheet." >&2
fi

# The pipeline runs on a sleep loop rather than under cron: one less daemon in a
# 512MB machine, and its output lands in `fly logs` alongside the bot's.
#
# Failures are logged and swallowed on purpose. A Riot dev key expires every 24
# hours, and a dead pipeline must not take the bot down with it -- yesterday's
# snapshot still answers !topelo, an offline bot answers nothing.
if [ "${RUN_PIPELINE:-true}" = "true" ]; then
    (
        while true; do
            echo "[pipeline] starting run"
            if python -m src.python.run_pipeline; then
                echo "[pipeline] run complete"
            else
                echo "[pipeline] run FAILED -- serving the previous snapshot" >&2
            fi
            sleep "${PIPELINE_INTERVAL_SECONDS:-3600}"
        done
    ) &
fi

# exec, so the bot is the process Fly supervises: when it exits, the machine
# restarts, which is the recovery path bot.js's uncaughtException handler
# assumes.
exec node src/js/bot.js
