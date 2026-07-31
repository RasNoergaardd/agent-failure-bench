#!/bin/bash
#BSUB -q gpua100
#BSUB -J afb-judge
#BSUB -n 8
#BSUB -R "span[hosts=1]"
#BSUB -R "rusage[mem=8GB]"
#BSUB -M 9GB
#BSUB -R "select[gpu40gb]"
#BSUB -gpu "num=1:mode=exclusive_process"
#BSUB -W 08:00
#BSUB -o logs/afb-judge_%J.out
#BSUB -e logs/afb-judge_%J.err

# Serve Qwen3-14B with vLLM on one A100, then run the judge against it.
# Both the server and the client live inside this job, so nothing needs a tunnel.
#
#   bsub < scripts/judge_trail.sh                                  # swe_bench, 5 traces
#   bsub -env "all, SPLIT=gaia, LIMIT=all" < scripts/judge_trail.sh  # full GAIA split
#
# Pass configuration through `bsub -env`, not as a shell prefix. `bsub < script`
# feeds the script on stdin and does not carry prefix-assigned variables to the
# compute node, so `SPLIT=gaia bsub < ...` silently runs the defaults instead.
#
# Check the queue name against `bqueues` before the first submit; DTU renames
# them occasionally, and `gpua100` is the A100 queue at time of writing.

set -euo pipefail

# FlashInfer JIT-compiles its sampling kernel at startup, which needs nvcc.
# Compute nodes have a CUDA driver but no toolkit, so use the native sampler.
export VLLM_USE_FLASHINFER_SAMPLER=0

# vLLM honours the checkpoint's generation_config.json, and Qwen3 ships
# temperature 0.6. A sampling judge is not reproducible, so pin it.
export AFB_JUDGE_TEMPERATURE=0

# --- configuration ---------------------------------------------------------
MODEL="${MODEL:-Qwen/Qwen3-14B-AWQ}"
SPLIT="${SPLIT:-swe_bench}"
# `LIMIT=all` judges the whole split. An empty string would be the natural
# sentinel but cannot survive job submission, so require a literal word.
LIMIT="${LIMIT:-5}"
[ "$LIMIT" = all ] && LIMIT=""
PORT="${PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-40960}"
CHAR_BUDGET="${CHAR_BUDGET:-100000}"   # keeps a trajectory inside the context window
SERVER_TIMEOUT="${SERVER_TIMEOUT:-1800}"  # weights download on a cold cache is slow

# `bsub < script` feeds this file on stdin, so BASH_SOURCE is not a path and
# cannot locate the checkout. These must be defaults inside the script, not
# inherited from an interactive shell: `bsub -env` bypasses ~/.bashrc, and a
# wrong REPO silently relocates the venv, the caches and the results file.
REPO="${REPO:-$HOME/agent-failure-bench}"
WORK="${WORK:-$HOME/afb-work}"
VENV="${VENV:-$WORK/.venv-hpc}"
PYTHON_MODULE="${PYTHON_MODULE:-python3/3.12.11}"

# Model weights and datasets are large; keep them off the small home quota.
export HF_HOME="${HF_HOME:-$WORK/.cache/huggingface}"
export OUTLINES_CACHE_DIR="${OUTLINES_CACHE_DIR:-$WORK/.cache/outlines}"

# Refuse to run on a configuration that is not what was asked for. A job that
# silently judges the wrong split wastes GPU hours and, worse, can put the wrong
# numbers in a results table.
case "$SPLIT" in
    gaia|swe_bench) ;;
    *) echo "unknown SPLIT '$SPLIT': expected gaia or swe_bench." >&2; exit 1 ;;
esac
if [ -n "$LIMIT" ] && ! [ "$LIMIT" -gt 0 ] 2>/dev/null; then
    echo "LIMIT must be a positive integer or the word 'all', got '$LIMIT'." >&2
    exit 1
fi
if [ ! -f "$REPO/pyproject.toml" ]; then
    echo "REPO='$REPO' is not the checkout: no pyproject.toml there." >&2
    exit 1
fi

cd "$REPO"
mkdir -p logs results "$HF_HOME"

echo "=== $(date) | job ${LSB_JOBID:-local} on $(hostname) ==="
echo "model=$MODEL split=$SPLIT limit=${LIMIT:-all} repo=$REPO"
echo "CHECK THIS LINE MATCHES WHAT YOU SUBMITTED before trusting the results."
nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv || true

# --- secrets ---------------------------------------------------------------
# HF_TOKEN is needed only to download the gated TRAIL dataset the first time.
if [ -f "$REPO/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$REPO/.env"
    set +a
fi

# --- environment -----------------------------------------------------------
# The cluster's default python3 predates this package's 3.12 requirement, so a
# module must supply a newer one. `module` is a shell function, not a binary,
# and is not defined in a non-interactive shell until this file is sourced.
if [ -n "${PYTHON_MODULE:-}" ]; then
    [ -f /etc/profile.d/modules.sh ] && . /etc/profile.d/modules.sh
    module load "$PYTHON_MODULE"
fi

PYTHON="${PYTHON:-python3}"
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
    echo "need python >= 3.12, found $("$PYTHON" --version 2>&1)." >&2
    echo "run 'module avail python3' and set PYTHON_MODULE to a 3.12+ module." >&2
    exit 1
fi

# Building this venv pulls several GB of vLLM wheels. Home quota is 40 GB, so a
# missing venv is far more likely to be a wrong VENV path than a genuine first
# run: say so instead of silently filling the quota in the wrong directory.
if [ ! -d "$VENV" ]; then
    if [ "${AFB_CREATE_VENV:-0}" != 1 ]; then
        echo "no venv at $VENV (WORK=$WORK)." >&2
        echo "check the path, or pass AFB_CREATE_VENV=1 to build it (~10 min, several GB)." >&2
        exit 1
    fi
    echo "--- creating $VENV (~10 min) ---"
    "$PYTHON" -m venv "$VENV"
    "$VENV/bin/pip" install --upgrade pip
    "$VENV/bin/pip" install vllm
    "$VENV/bin/pip" install -e "$REPO"
fi
export PATH="$VENV/bin:$PATH"
python -c "import afb, vllm; print('afb + vllm import OK')"

# --- serve the model -------------------------------------------------------
SERVER_LOG="logs/vllm_${LSB_JOBID:-local}.log"
echo "--- starting vLLM, log: $SERVER_LOG ---"
vllm serve "$MODEL" \
    --port "$PORT" \
    --max-model-len "$MAX_MODEL_LEN" \
    --gpu-memory-utilization 0.92 \
    > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!

# Always take the server down, including on bkill or an error mid-script.
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

# --- run the judge ---------------------------------------------------------
export AFB_JUDGE_BASE_URL="http://127.0.0.1:$PORT/v1"
export AFB_JUDGE_MODEL="$MODEL"
export AFB_JUDGE_API_KEY="dummy"   # vLLM ignores it; afb requires one to be set

OUT="results/judged-trail-${SPLIT}.jsonl"

echo "--- judging $SPLIT -> $OUT ---"
# Branching rather than expanding a possibly-empty array, which trips `set -u`.
if [ -n "$LIMIT" ]; then
    afb judge-trail --split "$SPLIT" --char-budget "$CHAR_BUDGET" \
        --out "$OUT" --keep-going --limit "$LIMIT"
else
    afb judge-trail --split "$SPLIT" --char-budget "$CHAR_BUDGET" \
        --out "$OUT" --keep-going
fi

# --- analyse ---------------------------------------------------------------
echo "--- agreement (subquestion 2) ---"
afb agreement --judged "$OUT" --splits "$SPLIT" --confusion

echo "--- taxonomy coverage (subquestion 1) ---"
afb coverage --judged "$OUT"

echo "=== $(date) | done ==="
