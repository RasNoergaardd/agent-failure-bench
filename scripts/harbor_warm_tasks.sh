#!/bin/bash
# Warm the images of one or more Harbor tasks, and repoint the tasks at them.
#
# Harbor's bootstrap installs tmux, asciinema and a uvicorn/fastapi venv on every
# container start, and its health check gives that sixty seconds. Under udocker's
# PRoot the install takes minutes, so a task whose image lacks any of them times
# out however generous --timeout-multiplier is. Terminal-Bench images ship tmux
# but not asciinema, so every one of them needs this.
#
#   scripts/harbor_warm_tasks.sh terminal-bench-2/sanitize-git-repo
#   scripts/harbor_warm_tasks.sh terminal-bench-2/*/
#
# Idempotent: a task already pointing at a warmed image is skipped, so this can
# be re-run over a directory as tasks are added.

set -euo pipefail

: "${UDOCKER_DIR:?set UDOCKER_DIR to a directory off the home quota, e.g. /work3/\$USER/.udocker}"
UDOCKER="${UDOCKER:-udocker}"
SUFFIX="${SUFFIX:-hbwarm}"

if [ "$#" -eq 0 ]; then
    echo "usage: $0 <task-dir> [task-dir...]" >&2
    exit 1
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for task in "$@"; do
    toml="${task%/}/task.toml"
    if [ ! -f "$toml" ]; then
        echo "skip ${task}: no task.toml" >&2
        continue
    fi

    image="$(sed -n 's/^docker_image *= *"\(.*\)"/\1/p' "$toml" | head -1)"
    if [ -z "$image" ]; then
        echo "skip ${task}: no docker_image, the singularity backend cannot build a Dockerfile" >&2
        continue
    fi
    case "$image" in
        *"-${SUFFIX}"*) echo "skip ${task}: already warmed ($image)"; continue ;;
    esac

    # One warmed image per base image, shared by every task that uses it.
    warm="${image%:*}-${SUFFIX}:${image##*:}"
    if "$UDOCKER" images 2>/dev/null | awk '{print $1}' | grep -qxF "$warm"; then
        echo "reuse $warm"
    else
        echo "--- warming $image -> $warm ---"
        UDOCKER="$UDOCKER" "$here/harbor_warm_image.sh" "$image" "$warm"
    fi

    # Keep the original recorded: principle 4 needs the image a run actually used
    # to be traceable back to the one the benchmark published.
    grep -q '^# afb: original docker_image' "$toml" \
        || sed -i "s|^docker_image *= *\"${image}\"|# afb: original docker_image = \"${image}\"\ndocker_image = \"${warm}\"|" "$toml"
    echo "${task}: -> $warm"
done
