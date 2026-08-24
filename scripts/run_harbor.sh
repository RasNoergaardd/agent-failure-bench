#!/bin/bash
#BSUB -q gpua100
#BSUB -J afb-harbor
#BSUB -n 8
#BSUB -R "span[hosts=1]"
#BSUB -R "rusage[mem=8GB]"
#BSUB -M 9GB
#BSUB -gpu "num=1:mode=exclusive_process"
# The GPU model is selected by the queue, not by a -R selector. An
# `-R "select[gpu40gb]"` here would be ANDed with anything given on the command
# line rather than replaced by it, which silently excludes every queue whose
# cards are a different size: gpuh100 has 80 GB per GPU and far shorter waits
# than gpua100, and a 27B model in BF16 fits one of those where it needs two
# A100s. Override the queue on the command line:
#
#   bsub -q gpuh100 -gpu "num=1:mode=exclusive_process" -env "all, TP=1, ..." < <this script>
#BSUB -W 12:00
#BSUB -o logs/afb-harbor_%J.out
#BSUB -e logs/afb-harbor_%J.err
#BSUB -u s225786@dtu.dk
#BSUB -B
#BSUB -N
# -B mails when the job is dispatched and -N when it ends. Queue waits here run
# to days, so a job that starts or dies at three in the morning should say so
# rather than wait to be noticed, and the start mail is the one that says the
# wait is over. Stdout still goes to the -o file; neither flag redirects it.

# Serve an agent model with vLLM, then run Terminal-Bench tasks against it with
# Harbor. Both live inside this job, so nothing needs a tunnel.
#
#   bsub -env "all, WORK=/work3/s225786, TASKS=terminal-bench-2/sanitize-git-repo" \
#        < scripts/run_harbor.sh
#
# TASKS may also name a dataset directory, which is how subquestion 1 is run:
# every task once, for the breadth that escape-hatch evidence needs. Subquestion
# 3 wants the opposite shape, fewer tasks with N_ATTEMPTS repeats each.
#
#   bsub -env "all, WORK=/work3/s225786, TASKS=terminal-bench-2" < scripts/run_harbor.sh
#
# A model needing more than one GPU overrides the directive below on the command
# line, where it takes precedence, and sets TP to match:
#
#   bsub -gpu "num=2:mode=exclusive_process" \
#        -env "all, MODEL=Qwen/Qwen3.8-27B, TP=2, TASKS=..." < scripts/run_harbor.sh
#
# Pass configuration through `bsub -env`, not as a shell prefix: `bsub < script`
# feeds this file on stdin and drops prefix-assigned variables.
#
# The cluster has no container runtime, so Harbor runs through udocker behind
# `scripts/udocker-shim/singularity`. See the 2026-08-20 entry in
# research/experiment-log.md for why, and for the warming step this depends on.

set -euo pipefail

export VLLM_USE_FLASHINFER_SAMPLER=0   # compute nodes have no nvcc for the JIT

# --- configuration ---------------------------------------------------------
# The agent is deliberately not the strongest model available: the judge is, and
# the two must differ so that one model does not both produce and grade a
# trajectory. See research/experiment-design-rq3-rq4.md.
MODEL="${MODEL:-Qwen/Qwen3-32B-AWQ}"
TP="${TP:-1}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-40960}"
AGENT="${AGENT:-terminus-2}"
TASKS="${TASKS:-}"                     # space-separated task paths, required
N_ATTEMPTS="${N_ATTEMPTS:-1}"          # repeats per task; RQ3 needs many
N_TASKS="${N_TASKS:-}"                 # cap on tasks, empty for all
# Trials run concurrently against one vLLM server, which batches them, so the
# limit is CPU rather than GPU: every container syscall goes through PRoot.
N_CONCURRENT="${N_CONCURRENT:-4}"
# Terminus sends a temperature only when given one, so leaving this empty means
# vLLM serves the checkpoint's generation_config, which is the condition a
# benchmark result would be reported under and is what the RQ3 design asks for.
# Setting it makes the value part of the run's recorded configuration rather
# than something recovered from the checkpoint afterwards. It must never be 0
# for a subquestion-3 batch: identical repeats measure nothing.
AGENT_TEMPERATURE="${AGENT_TEMPERATURE:-}"
PORT="${PORT:-8000}"
SERVER_TIMEOUT="${SERVER_TIMEOUT:-3600}"

REPO="${REPO:-$HOME/agent-failure-bench}"
WORK="${WORK:-$HOME/afb-work}"
VENV="${VENV:-$WORK/.venv-hpc}"                 # vLLM lives here
HARBOR_VENV="${HARBOR_VENV:-$WORK/.venv-harbor}"
UDOCKER_VENV="${UDOCKER_VENV:-$WORK/.venv-udocker}"
TASK_ROOT="${TASK_ROOT:-$WORK/harbor-test}"     # where `harbor download` put them
PYTHON_MODULE="${PYTHON_MODULE:-python3/3.12.11}"

export AFB_SHIM_PIDFILE="${AFB_SHIM_PIDFILE:-$WORK/shim-pgids-${LSB_JOBID:-local}}"
export AFB_SHIM_CONTAINERS="${AFB_SHIM_CONTAINERS:-$WORK/shim-containers-${LSB_JOBID:-local}}"

export HF_HOME="${HF_HOME:-$WORK/.cache/huggingface}"
export UDOCKER_DIR="${UDOCKER_DIR:-$WORK/.udocker}"
export UDOCKER="${UDOCKER:-$UDOCKER_VENV/bin/udocker}"

# Refuse to run a configuration nobody asked for, in the manner of
# judge_trail.sh: four jobs were lost to silent misconfiguration on 2026-07-30.
if [ -z "$TASKS" ]; then
    echo "TASKS is empty. Give one or more task paths relative to TASK_ROOT, e.g." >&2
    echo "  bsub -env \"all, TASKS=terminal-bench-2/sanitize-git-repo\" < $0" >&2
    exit 1
fi
if ! [ "$TP" -gt 0 ] 2>/dev/null; then
    echo "TP must be a positive integer, got '$TP'." >&2; exit 1
fi
if ! [ "$N_ATTEMPTS" -gt 0 ] 2>/dev/null; then
    echo "N_ATTEMPTS must be a positive integer, got '$N_ATTEMPTS'." >&2; exit 1
fi
if ! [ "$N_CONCURRENT" -gt 0 ] 2>/dev/null; then
    echo "N_CONCURRENT must be a positive integer, got '$N_CONCURRENT'." >&2; exit 1
fi
if [ -n "$N_TASKS" ] && ! [ "$N_TASKS" -gt 0 ] 2>/dev/null; then
    echo "N_TASKS must be a positive integer or empty, got '$N_TASKS'." >&2; exit 1
fi
if [ ! -f "$REPO/pyproject.toml" ]; then
    echo "REPO='$REPO' is not the checkout: no pyproject.toml there." >&2; exit 1
fi
if [ ! -d "$TASK_ROOT" ]; then
    echo "TASK_ROOT='$TASK_ROOT' does not exist. Download the dataset first:" >&2
    echo "  cd $TASK_ROOT && harbor download terminal-bench/terminal-bench-2" >&2
    exit 1
fi

cd "$REPO"
mkdir -p logs

echo "=== $(date) | job ${LSB_JOBID:-local} on $(hostname) ==="
echo "model=$MODEL tp=$TP agent=$AGENT attempts=$N_ATTEMPTS"
echo "tasks=$TASKS"
echo "CHECK THESE LINES MATCH WHAT YOU SUBMITTED before trusting the results."

if ! command -v nvidia-smi > /dev/null 2>&1; then
    echo "nvidia-smi not found, so no GPU is visible." >&2
    echo "Submit this with 'bsub < $0' rather than running it directly." >&2
    exit 1
fi
nvidia-smi --query-gpu=name,memory.total --format=csv
GPU_COUNT="$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l | tr -d ' ')"
if [ "$TP" != "$GPU_COUNT" ]; then
    echo "TP=$TP but $GPU_COUNT GPU(s) are allocated." >&2
    echo "  bsub -gpu \"num=$TP:mode=exclusive_process\" -env \"all, TP=$TP, ...\" < $0" >&2
    exit 1
fi

if [ -f "$REPO/.env" ]; then
    set -a; . "$REPO/.env"; set +a
fi

if [ -n "${PYTHON_MODULE:-}" ]; then
    [ -f /etc/profile.d/modules.sh ] && . /etc/profile.d/modules.sh
    module load "$PYTHON_MODULE"
fi

for venv in "$VENV" "$HARBOR_VENV" "$UDOCKER_VENV"; do
    if [ ! -d "$venv" ]; then
        echo "no venv at $venv (WORK=$WORK). Check the path." >&2
        exit 1
    fi
done

# The shim must precede anything else that might answer to `singularity`.
export PATH="$REPO/scripts/udocker-shim:$HARBOR_VENV/bin:$VENV/bin:$PATH"

echo "--- pinning info (principle 4) ---"
"$VENV/bin/python" -c "import vllm; print('vllm', vllm.__version__)"
"$VENV/bin/python" -c "import torch; print('torch', torch.__version__, 'cuda', torch.version.cuda)"
harbor --version | sed 's/^/harbor /'
"$UDOCKER" --version 2>/dev/null | head -1 | sed 's/^/udocker /' || true
git -C "$REPO" rev-parse --short HEAD 2>/dev/null | sed 's/^/afb commit /' || true

# --- serve the agent model -------------------------------------------------
SERVER_LOG="logs/vllm_harbor_${LSB_JOBID:-local}.log"
echo "--- starting vLLM, log: $SERVER_LOG ---"
"$VENV/bin/vllm" serve "$MODEL" \
    --port "$PORT" \
    --max-model-len "$MAX_MODEL_LEN" \
    --tensor-parallel-size "$TP" \
    --gpu-memory-utilization 0.92 \
    > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!

: > "$AFB_SHIM_PIDFILE"        # a stale file from an earlier job names other processes
: > "$AFB_SHIM_CONTAINERS"

cleanup() {
    echo "--- stopping vLLM (pid $SERVER_PID) ---"
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    reap_containers
    # Whatever the shims did not manage to remove themselves. Each rootfs is
    # roughly three gigabytes, so a job that leaves its containers behind fills
    # the quota for the next one.
    singularity sweep || true
}

# Containers must not outlive the job. On 2026-08-22 a trial that Harbor
# force-killed left its udocker and PRoot processes running on the compute node
# after the job had finished, holding a GPU it was not using until cluster
# support wrote to ask what it was doing. The shim records the process group of
# every container it starts in $AFB_SHIM_PIDFILE, and this stops all of them.
reap_containers() {
    [ -s "$AFB_SHIM_PIDFILE" ] || return 0
    echo "--- stopping leftover containers ---"
    while read -r group; do
        [ -n "$group" ] || continue
        kill -0 -- "-$group" 2>/dev/null || continue
        echo "  terminating process group $group"
        kill -TERM -- "-$group" 2>/dev/null || true
    done < "$AFB_SHIM_PIDFILE"
    sleep 10
    while read -r group; do
        [ -n "$group" ] || continue
        if kill -0 -- "-$group" 2>/dev/null; then
            echo "  killing process group $group"
            kill -KILL -- "-$group" 2>/dev/null || true
        fi
    done < "$AFB_SHIM_PIDFILE"
    rm -f "$AFB_SHIM_PIDFILE"
}
trap cleanup EXIT INT TERM

echo "--- waiting for the server (up to ${SERVER_TIMEOUT}s) ---"
deadline=$((SECONDS + SERVER_TIMEOUT))
until curl -sf "http://127.0.0.1:$PORT/v1/models" > /dev/null; do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "vLLM died during startup. Last 40 lines:" >&2
        tail -40 "$SERVER_LOG" >&2
        exit 1
    fi
    if [ "$SECONDS" -ge "$deadline" ]; then
        echo "vLLM did not become ready within ${SERVER_TIMEOUT}s." >&2
        tail -40 "$SERVER_LOG" >&2
        exit 1
    fi
    sleep 10
done
echo "server ready after ${SECONDS}s"

# --- warm the task images --------------------------------------------------
# Harbor's health check allows sixty seconds, hardcoded, and its bootstrap
# installs asciinema on every start, which takes minutes under udocker's PRoot.
# Warming is idempotent, so an already-warmed task costs one `udocker images`.
cd "$TASK_ROOT"
# TASKS may name a dataset directory rather than individual tasks, which is how
# subquestion 1 is run: every task once, for breadth. Expand such a directory
# into the tasks beneath it, so that one list drives both the warming below and
# the job configuration further down and the two cannot disagree.
TASK_LIST="$(
    for entry in $TASKS; do
        if [ -d "$entry" ] && [ ! -f "$entry/task.toml" ]; then
            for task in "$entry"/*/; do
                [ -f "$task/task.toml" ] && printf '%s\n' "${task%/}"
            done
        else
            printf '%s\n' "$entry"
        fi
    done | sort -u
)"
# The cap is applied here rather than by Harbor, so that the tasks named in the
# configuration are exactly the tasks that run. Dataset order, per
# research/experiment-design-rq3-rq4.md.
[ -n "$N_TASKS" ] && TASK_LIST="$(printf '%s\n' "$TASK_LIST" | head -n "$N_TASKS")"
TASK_COUNT="$(printf '%s\n' "$TASK_LIST" | grep -c .)"
if [ "$TASK_COUNT" -eq 0 ]; then
    echo "TASKS='$TASKS' matched no task.toml under $TASK_ROOT." >&2
    exit 1
fi
echo "--- $TASK_COUNT task(s) resolved ---"

# shellcheck disable=SC2086
"$REPO/scripts/harbor_warm_tasks.sh" $TASK_LIST

# --- run the tasks ---------------------------------------------------------
# terminus-2 runs on the host and drives the container over HTTP, so it reaches
# vLLM directly and the container needs no outward network for the model.
export OPENAI_API_KEY="${OPENAI_API_KEY:-dummy}"   # vLLM ignores it, litellm requires one

# Subquestion 3 measures variation across repeats, so the sampling settings are
# the experiment rather than a detail. vLLM serves the checkpoint's
# generation_config unless overridden, and this records what that resolved to.
echo "--- agent sampling (subquestion 3 needs this to be nonzero) ---"
# HuggingFace names cache directories models--<org>--<name>, with a doubled
# separator, so the model id's slash becomes two dashes and not one.
MODEL_CACHE="$HF_HOME/hub/models--$(printf %s "$MODEL" | sed 's|/|--|g')"
SAMPLING="$(find "$MODEL_CACHE" -name generation_config.json -print -quit 2>/dev/null)"
if [ -n "$SAMPLING" ]; then
    echo "generation_config $SAMPLING"
    cat "$SAMPLING"
else
    # Not fatal for a single-attempt run, but subquestion 3 measures variation
    # across repeats and cannot be interpreted without knowing what was sampled.
    echo "WARNING: no generation_config.json under $MODEL_CACHE." >&2
    echo "The sampling settings are unrecorded, which subquestion 3 requires." >&2
fi
echo

if [ -n "$AGENT_TEMPERATURE" ] && [ "$N_ATTEMPTS" -gt 1 ] && [ "$AGENT_TEMPERATURE" = 0 ]; then
    echo "AGENT_TEMPERATURE=0 with N_ATTEMPTS=$N_ATTEMPTS reproduces the same" >&2
    echo "run $N_ATTEMPTS times and measures no variance. Refusing." >&2
    exit 1
fi
if [ -n "$AGENT_TEMPERATURE" ]; then
    echo "agent temperature pinned to $AGENT_TEMPERATURE"
else
    echo "agent temperature unset: vLLM serves the checkpoint default above"
fi

# The task list goes in a job configuration file rather than on the command
# line. Harbor's repeated task-path flag does not accumulate: a run submitted on
# 2026-08-22 named all 22 tasks, logged all 22, and wrote a config.json holding
# only the last one, so 21 tasks were silently dropped and the job reported a
# clean single-trial result. A configuration file is the documented granular
# form, and --print-config below checks it before anything is scheduled.
JOB_CONFIG="$TASK_ROOT/job-config-${LSB_JOBID:-local}.json"
TASK_LIST="$TASK_LIST" MODEL="$MODEL" AGENT="$AGENT" PORT="$PORT" \
AGENT_TEMPERATURE="$AGENT_TEMPERATURE" WORK="$WORK" \
python3 - "$JOB_CONFIG" <<'PYCONF'
import json, os, sys

kwargs = {"api_base": f"http://127.0.0.1:{os.environ['PORT']}/v1"}
if temperature := os.environ.get("AGENT_TEMPERATURE", ""):
    kwargs["temperature"] = float(temperature)

config = {
    "environment": {
        "type": "singularity",
        "kwargs": {"singularity_image_cache_dir": f"{os.environ['WORK']}/.sif-cache"},
    },
    "agents": [
        {
            "name": os.environ["AGENT"],
            "model_name": f"openai/{os.environ['MODEL']}",
            "kwargs": kwargs,
        }
    ],
    "tasks": [
        {"path": line} for line in os.environ["TASK_LIST"].split("\n") if line.strip()
    ],
}
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(config, handle, indent=2)
print(f"wrote {sys.argv[1]} with {len(config['tasks'])} task(s)")
PYCONF

# Verify the resolved configuration still holds every task before running it,
# so that a silent drop fails the job rather than producing a smaller result.
RESOLVED="$(harbor run -c "$JOB_CONFIG" --print-config)"
RESOLVED_COUNT="$(printf '%s' "$RESOLVED" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["tasks"]))')"
if [ "$RESOLVED_COUNT" != "$TASK_COUNT" ]; then
    echo "Harbor resolved $RESOLVED_COUNT tasks from a configuration naming $TASK_COUNT." >&2
    printf '%s\n' "$RESOLVED" >&2
    exit 1
fi
echo "--- harbor resolved $RESOLVED_COUNT task(s), running $AGENT against $MODEL ---"

harbor run \
    -c "$JOB_CONFIG" \
    --n-attempts "$N_ATTEMPTS" \
    --n-concurrent "$N_CONCURRENT"

echo "=== $(date) | done ==="
