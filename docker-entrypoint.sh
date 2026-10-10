#!/bin/sh
set -e

# The persistent volume is mounted over $DATA_DIR at runtime, so its ownership
# comes from the host (often root). Fix it before dropping privileges.
mkdir -p "$DATA_DIR/media/atestados" "$DATA_DIR/media/employees"

if [ "$(id -u)" = "0" ]; then
    find "$DATA_DIR" \! -user appuser -exec chown appuser:appuser {} +
    exec gosu appuser "$@"
fi

exec "$@"
