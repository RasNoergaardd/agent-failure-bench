#!/bin/bash
#BSUB -q gpua100
#BSUB -J afb-smoke
#BSUB -n 4
#BSUB -R "span[hosts=1]"
#BSUB -R "rusage[mem=8GB]"
#BSUB -M 9GB
#BSUB -R "select[gpu40gb]"
#BSUB -gpu "num=1:mode=exclusive_process"
#BSUB -W 00:30
#BSUB -o logs/afb-smoke_%J.out
#BSUB -e logs/afb-smoke_%J.err

# Does the setup work at all? Checks, in order:
#   1. the GPU is visible
#   2. the python module and venv load
#   3. afb imports and the taxonomy parses
#   4. TRAIL data is readable
#   5. vLLM serves the model
#   6. the model answers one request
#   7. afb can parse a judge response into valid annotations
#
# No judging, no dataset pass, 30 minutes. Run this before judge_trail.sh.
#
#   bsub < scripts/smoke_test.sh

set -euo pipefail

# FlashInfer JIT-compiles its sampling kernel at startup, which needs nvcc.
# Compute nodes have a CUDA driver but no toolkit, so use the native sampler.
export VLLM_USE_FLASHINFER_SAMPLER=0

# vLLM honours the checkpoint's generation_config.json, and Qwen3 ships
# temperature 0.6. A sampling judge is not reproducible, so pin it.
export AFB_JUDGE_TEMPERATURE=0

MODEL="${MODEL:-Qwen/Qwen3-14B-AWQ}"
PORT="${PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-40960}"
SERVER_TIMEOUT="${SERVER_TIMEOUT:-900}"

REPO="${REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
WORK="${WORK:-$REPO}"
VENV="${VENV:-$WORK/.venv-hpc}"
export HF_HOME="${HF_HOME:-$WORK/.cache/huggingface}"

cd "$REPO"
mkdir -p logs results

pass() { echo "  [PASS] $1"; }
fail() { echo "  [FAIL] $1" >&2; exit 1; }

echo "=== $(date) | job ${LSB_JOBID:-local} on $(hostname) ==="
echo "model=$MODEL work=$WORK"

echo "--- 1. GPU ---"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || fail "no GPU visible"
pass "GPU visible"

echo "--- 2. python and venv ---"
if [ -n "${PYTHON_MODULE:-}" ]; then
    [ -f /etc/profile.d/modules.sh ] && . /etc/profile.d/modules.sh
    module load "$PYTHON_MODULE"
fi
[ -d "$VENV" ] || fail "no venv at $VENV"
export PATH="$VENV/bin:$PATH"
python --version
python -c "import afb, vllm" || fail "afb or vllm will not import"
pass "venv usable"

echo "--- 3. taxonomy ---"
python - <<'PY' || exit 1
from afb import taxonomy, mapping
codes = taxonomy.error_types()
assert len(codes) == 24, f"expected 24 codes, got {len(codes)}"
print(f"  {len(codes)} error codes, mapping {mapping.coverage_report()}")
PY
pass "taxonomy and mapping load"

echo "--- 4. TRAIL data ---"
python - <<'PY' || exit 1
from afb import trail
traj, labels = next(trail.load("swe_bench"))
print(f"  {traj.trajectory_id}: {len(traj.events)} events, {len(labels.errors)} expert errors")
PY
pass "TRAIL readable"

echo "--- 5. serving $MODEL ---"
SERVER_LOG="logs/smoke-vllm_${LSB_JOBID:-local}.log"
vllm serve "$MODEL" --port "$PORT" --max-model-len "$MAX_MODEL_LEN" \
    --gpu-memory-utilization 0.92 > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

deadline=$((SECONDS + SERVER_TIMEOUT))
until curl -sf "http://127.0.0.1:$PORT/v1/models" > /dev/null; do
    kill -0 "$SERVER_PID" 2>/dev/null || { tail -30 "$SERVER_LOG" >&2; fail "vLLM died, see $SERVER_LOG"; }
    [ "$SECONDS" -lt "$deadline" ] || { tail -30 "$SERVER_LOG" >&2; fail "vLLM not ready in ${SERVER_TIMEOUT}s"; }
    sleep 10
done
pass "server ready after ${SECONDS}s"

echo "--- 6. one request ---"
curl -sf "http://127.0.0.1:$PORT/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{\"model\": \"$MODEL\", \"max_tokens\": 32, \"messages\":
         [{\"role\": \"user\", \"content\": \"Reply with the single word: ready\"}]}" \
    | python -c "import json,sys; print('  model said:', json.load(sys.stdin)['choices'][0]['message']['content'][:200])" \
    || fail "the model did not answer"
pass "model answers"

echo "--- 7. judge round trip on one trajectory ---"
export AFB_JUDGE_BASE_URL="http://127.0.0.1:$PORT/v1"
export AFB_JUDGE_MODEL="$MODEL"
export AFB_JUDGE_API_KEY="dummy"
python - <<'PY' || exit 1
from afb import judge, trail
trajectory, _ = next(trail.load("swe_bench"))
result = judge.judge(trajectory, judge.JudgeConfig(char_budget=100_000))
print(f"  {len(result.annotations)} annotations on {trajectory.trajectory_id}")
for annotation in result.annotations[:5]:
    print(f"    events {annotation.event_span} {annotation.error_type:7} "
          f"{annotation.severity:6} {annotation.rationale[:70]}")
PY
pass "judge produced valid annotations"

echo "=== $(date) | setup works ==="
