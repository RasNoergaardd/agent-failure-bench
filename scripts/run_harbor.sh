#!/bin/bash
#BSUB -q gpua100
#BSUB -J afb-harbor
#BSUB -n 8
#BSUB -R "span[hosts=1]"
#BSUB -R "rusage[mem=8GB]"
#BSUB -M 9GB
#BSUB -R "select[gpu40gb]"
#BSUB -gpu "num=1:mode=exclusive_process"
#BSUB -W 12:00
#BSUB -o logs/afb-harbor_%J.out
#BSUB -e logs/afb-harbor_%J.err

# Serve an agent model with vLLM, then run Terminal-Bench tasks against it with
# Harbor. Both live inside this job, so nothing needs a tunnel.
#
#   bsub -env "all, WORK=/work3/s225786, TASKS=terminal-bench-2/sanitize-git-repo" \
#        < scripts/run_harbor.sh
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
PORT="${PORT:-8000}"
SERVER_TIMEOUT="${SERVER_TIMEOUT:-3600}"

REPO="${REPO:-$HOME/agent-failure-bench}"
WORK="${WORK:-$HOME/afb-work}"
VENV="${VENV:-$WORK/.venv-hpc}"                 # vLLM lives here
HARBOR_VENV="${HARBOR_VENV:-$WORK/.venv-harbor}"
UDOCKER_VENV="${UDOCKER_VENV:-$WORK/.venv-udocker}"
TASK_ROOT="${TASK_ROOT:-$WORK/harbor-test}"     # where `harbor download` put them
PYTHON_MODULE="${PYTHON_MODULE:-python3/3.12.11}"

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

cleanup() {
    echo "--- stopping vLLM (pid $SERVER_PID) ---"
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
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
# shellcheck disable=SC2086
"$REPO/scripts/harbor_warm_tasks.sh" $TASKS

# --- run the tasks ---------------------------------------------------------
# terminus-2 runs on the host and drives the container over HTTP, so it reaches
# vLLM directly and the container needs no outward network for the model.
export OPENAI_API_KEY="${OPENAI_API_KEY:-dummy}"   # vLLM ignores it, litellm requires one

PATH_ARGS=()
for task in $TASKS; do
    PATH_ARGS+=(-p "$task")
done

# Subquestion 3 measures variation across repeats, so the sampling settings are
# the experiment rather than a detail. vLLM serves the checkpoint's
# generation_config unless overridden, and this records what that resolved to.
echo "--- agent sampling (subquestion 3 needs this to be nonzero) ---"
find "$HF_HOME/hub" -name generation_config.json -path "*$(printf %s "$MODEL" | tr / -)*" \
    -exec head -c 400 {} \; -quit 2>/dev/null || echo "no generation_config.json found"
echo

echo "--- running $AGENT against $MODEL ---"
harbor run \
    "${PATH_ARGS[@]}" \
    --agent "$AGENT" \
    --model "openai/$MODEL" \
    --ak "api_base=http://127.0.0.1:$PORT/v1" \
    --n-attempts "$N_ATTEMPTS" \
    -e singularity \
    --environment-kwarg "singularity_image_cache_dir=$WORK/.sif-cache"

echo "=== $(date) | done ==="
