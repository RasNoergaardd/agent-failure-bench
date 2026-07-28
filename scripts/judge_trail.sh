#!/bin/bash
#BSUB -q gpua100
#BSUB -J afb-judge
#BSUB -n 8
#BSUB -R "span[hosts=1]"
#BSUB -R "rusage[mem=8GB]"
#BSUB -M 10GB
#BSUB -R "select[gpu40gb]"
#BSUB -gpu "num=1:mode=exclusive_process"
#BSUB -W 08:00
#BSUB -o logs/afb-judge_%J.out
#BSUB -e logs/afb-judge_%J.err

# Serve Qwen3-14B with vLLM on one A100, then run the judge against it.
# Both the server and the client live inside this job, so nothing needs a tunnel.
#
#   bsub < scripts/judge_trail.sh                    # default: swe_bench, 5 traces
#   SPLIT=gaia LIMIT= bsub < scripts/judge_trail.sh  # full GAIA split
#
# Check the queue name against `bqueues` before the first submit; DTU renames
# them occasionally, and `gpua100` is the A100 queue at time of writing.

set -euo pipefail

# --- configuration ---------------------------------------------------------
MODEL="${MODEL:-Qwen/Qwen3-14B}"
SPLIT="${SPLIT:-swe_bench}"
LIMIT="${LIMIT:-5}"          # empty string means the whole split
PORT="${PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-40960}"
CHAR_BUDGET="${CHAR_BUDGET:-100000}"   # keeps a trajectory inside the context window
SERVER_TIMEOUT="${SERVER_TIMEOUT:-1800}"  # weights download on a cold cache is slow

REPO="${REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
WORK="${WORK:-$REPO}"
VENV="${VENV:-$WORK/.venv-hpc}"

# Model weights and datasets are large; keep them off the small home quota.
export HF_HOME="${HF_HOME:-$WORK/.cache/huggingface}"
export OUTLINES_CACHE_DIR="${OUTLINES_CACHE_DIR:-$WORK/.cache/outlines}"

cd "$REPO"
mkdir -p logs results "$HF_HOME"

echo "=== $(date) | job ${LSB_JOBID:-local} on $(hostname) ==="
echo "model=$MODEL split=$SPLIT limit=${LIMIT:-all} repo=$REPO"
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
if [ ! -d "$VENV" ]; then
    echo "--- creating $VENV (first run only, ~10 min) ---"
    python3 -m venv "$VENV"
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
LIMIT_ARG=()
[ -n "$LIMIT" ] && LIMIT_ARG=(--limit "$LIMIT")

echo "--- judging $SPLIT -> $OUT ---"
afb judge-trail \
    --split "$SPLIT" \
    --char-budget "$CHAR_BUDGET" \
    --out "$OUT" \
    --keep-going \
    "${LIMIT_ARG[@]}"

# --- analyse ---------------------------------------------------------------
echo "--- agreement (subquestion 2) ---"
afb agreement --judged "$OUT" --splits "$SPLIT" --confusion

echo "--- taxonomy coverage (subquestion 1) ---"
afb coverage --judged "$OUT"

echo "=== $(date) | done ==="
