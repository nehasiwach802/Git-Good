#!/bin/sh
set -eu
# A newly mounted persistent volume can be root-owned. Change only its directory,
# then drop privileges before Python starts; existing database files stay intact.
if [ "$(id -u)" = "0" ]; then
    mkdir -p -- "${DATA_DIR:-/app/data}"
    chown appuser:appuser -- "${DATA_DIR:-/app/data}"
    exec gosu appuser "$@"
fi
exec "$@"
