#!/bin/bash
# Bake Harbor's container prerequisites into a udocker image.
#
# Harbor's bootstrap installs tmux, asciinema and a uvicorn/fastapi venv into the
# container on every start. Under udocker's PRoot that takes about ten minutes,
# and Harbor's health check waits sixty seconds and then kills the container, a
# limit that no --timeout-multiplier reaches because it is a hardcoded loop of
# sixty one-second polls. Installing the same things once, ahead of time, turns a
# guaranteed timeout into a start of a few seconds.
#
#   scripts/harbor_warm_image.sh python:3.12-slim afb/harbor-warm:latest
#
# Then set `docker_image` in the task's task.toml to the warmed name.

set -euo pipefail

BASE="${1:-python:3.12-slim}"
TARGET="${2:-afb/harbor-warm:latest}"
: "${UDOCKER_DIR:?set UDOCKER_DIR to a directory off the home quota, e.g. /work3/\$USER/.udocker}"
UDOCKER="${UDOCKER:-udocker}"

WORK="$(dirname "$UDOCKER_DIR")"
CONTAINER="hbwarm-$$"
TARBALL="$WORK/${CONTAINER}.tar"
cleanup() { rm -f "$TARBALL"; "$UDOCKER" rm "$CONTAINER" > /dev/null 2>&1 || true; }
trap cleanup EXIT

echo "--- base $BASE -> $TARGET ---"
"$UDOCKER" pull "$BASE"
"$UDOCKER" create --name="$CONTAINER" "$BASE"

# Kept in step with harbor/environments/singularity/bootstrap.sh: it skips each
# install when the thing is already present, so these four are what it looks for.
"$UDOCKER" run --user=root "$CONTAINER" bash -c '
  set -e
  export DEBIAN_FRONTEND=noninteractive
  if ! command -v apt-get > /dev/null 2>&1; then
    echo "no apt-get in this image; warming supports Debian-family images only" >&2
    exit 1
  fi
  apt-get update -qq
  # python3-venv carries ensurepip, without which `python3 -m venv` fails on
  # Debian and Ubuntu. The versioned name is what actually provides it once
  # python3 is installed, so try both and let the unversioned one be enough
  # where the versioned one does not exist.
  apt-get install -y -qq tmux asciinema python3 python3-venv || true
  if ! python3 -c "import ensurepip" 2>/dev/null; then
    version="$(python3 -c "import sys; print(\"%d.%d\" % sys.version_info[:2])")"
    apt-get install -y -qq "python${version}-venv" || true
  fi
  python3 -m venv /opt/harbor-server
  /opt/harbor-server/bin/pip install -q uvicorn fastapi
  command -v tmux && command -v asciinema
  /opt/harbor-server/bin/python3 -c "import uvicorn, fastapi"
'

"$UDOCKER" export -o "$TARBALL" "$CONTAINER"
"$UDOCKER" import "$TARBALL" "$TARGET"
echo "--- $TARGET ready ---"
"$UDOCKER" images | grep -F "${TARGET%%:*}" || true
