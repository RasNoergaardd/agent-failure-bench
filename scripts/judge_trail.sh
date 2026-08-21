#!/bin/bash
#BSUB -q gpua100
#BSUB -J afb-judge
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
#BSUB -W 08:00
#BSUB -o logs/afb-judge_%J.out
#BSUB -e logs/afb-judge_%J.err
#BSUB -u s225786@dtu.dk
#BSUB -N
# -N mails the job report on completion. Queue waits here run to days, so a
# job that finishes or dies at three in the morning should say so rather than
# wait to be noticed. Stdout still goes to the -o file; -N is separate.

# Serve an open-weight judge with vLLM on the allocated GPUs, then run the judge
# against it. Both the server and the client live inside this job, so nothing
# needs a tunnel.
#
#   bsub < scripts/judge_trail.sh                                    # swe_bench, 5 traces
#   bsub -env "all, SPLIT=gaia, LIMIT=all" < scripts/judge_trail.sh  # full GAIA split
#
# Pass configuration through `bsub -env`, not as a shell prefix. `bsub < script`
# feeds the script on stdin and does not carry prefix-assigned variables to the
# compute node, so `SPLIT=gaia bsub < ...` silently runs the defaults instead.
#
# Check the queue name against `bqueues` before the first submit; DTU renames
# them occasionally, and `gpua100` is the A100 queue at time of writing.
#
# --- the capacity ladder ---------------------------------------------------
# RQ2 needs judge capacity varied while the prompt, taxonomy and mapping are held
# fixed, so that a low agreement score can be attributed to one or the other.
# One rung per submit, each writing its own results file:
#
#   bsub -env "all, MODEL=Qwen/Qwen3-14B-AWQ, SPLIT=swe_bench, LIMIT=all" \
#        < scripts/judge_trail.sh
#
#   bsub -env "all, MODEL=Qwen/Qwen3-32B-AWQ, SPLIT=swe_bench, LIMIT=all" \
#        < scripts/judge_trail.sh
#
# A rung needing more than one GPU overrides the `#BSUB` directives below on the
# command line, where they take precedence, and sets TP to match:
#
#   bsub -gpu "num=2:mode=exclusive_process" \
#        -env "all, MODEL=..., TP=2, SPLIT=swe_bench, LIMIT=all" \
#        < scripts/judge_trail.sh
#
# TP is checked against the GPUs actually allocated before vLLM starts, because
# a mismatch either wastes half the allocation or fails deep inside startup.
#
# Qwen3 reasons by default. Reasoning and the answer share `max_tokens`, so a
# thinking rung needs a larger budget as well as the switch:
#
#   bsub -env "all, MODEL=Qwen/Qwen3-32B-AWQ, THINKING=on, MAX_TOKENS=16384, \
#              SPLIT=swe_bench, LIMIT=all" < scripts/judge_trail.sh

set -euo pipefail

# FlashInfer JIT-compiles its sampling kernel at startup, which needs nvcc.
# Compute nodes have a CUDA driver but no toolkit, so use the native sampler.
export VLLM_USE_FLASHINFER_SAMPLER=0

# vLLM honours the checkpoint's generation_config.json, and Qwen3 ships
# temperature 0.6. A sampling judge is not reproducible, so pin it.
export AFB_JUDGE_TEMPERATURE=0

# --- configuration ---------------------------------------------------------
MODEL="${MODEL:-Qwen/Qwen3-14B-AWQ}"
TP="${TP:-1}"                          # tensor-parallel size; must equal the GPUs allocated
THINKING="${THINKING:-off}"            # `on` lets the model reason before answering
MAX_TOKENS="${MAX_TOKENS:-8192}"       # shared between reasoning and the answer
SPLIT="${SPLIT:-swe_bench}"
# `LIMIT=all` judges the whole split. An empty string would be the natural
# sentinel but cannot survive job submission, so require a literal word.
LIMIT="${LIMIT:-5}"
[ "$LIMIT" = all ] && LIMIT=""
PORT="${PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-40960}"
# Optional git ref to replay a superseded version of the guidelines. The file is
# edited in place, so an earlier version exists only as a git object; extracting
# it to WORK keeps the working tree untouched, which matters because a second
# concurrent job reads its guidelines from the same checkout.
GUIDELINES_REF="${GUIDELINES_REF:-}"
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
if ! [ "$TP" -gt 0 ] 2>/dev/null; then
    echo "TP must be a positive integer, got '$TP'." >&2
    exit 1
fi
case "$THINKING" in
    on|off) ;;
    *) echo "THINKING must be 'on' or 'off', got '$THINKING'." >&2; exit 1 ;;
esac
if ! [ "$MAX_TOKENS" -gt 0 ] 2>/dev/null; then
    echo "MAX_TOKENS must be a positive integer, got '$MAX_TOKENS'." >&2
    exit 1
fi
if [ ! -f "$REPO/pyproject.toml" ]; then
    echo "REPO='$REPO' is not the checkout: no pyproject.toml there." >&2
    exit 1
fi

cd "$REPO"
mkdir -p logs results "$HF_HOME"

echo "=== $(date) | job ${LSB_JOBID:-local} on $(hostname) ==="
echo "model=$MODEL tp=$TP thinking=$THINKING max_tokens=$MAX_TOKENS"
echo "split=$SPLIT limit=${LIMIT:-all} char_budget=$CHAR_BUDGET repo=$REPO"
echo "CHECK THESE LINES MATCH WHAT YOU SUBMITTED before trusting the results."
nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv || true

# A TP that does not match the allocation either strands half the GPUs or fails
# deep inside vLLM startup, after the weights download. Catch it here.
#
# Check for the tool separately: under `pipefail` a missing nvidia-smi would kill
# the script with a bare 127, and the usual reason it is missing is that this was
# run on the login node instead of submitted.
if ! command -v nvidia-smi > /dev/null 2>&1; then
    echo "nvidia-smi not found, so no GPU is visible." >&2
    echo "Submit this with 'bsub < $0' rather than running it directly." >&2
    exit 1
fi
GPU_COUNT="$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l | tr -d ' ')"
if [ "$TP" != "$GPU_COUNT" ]; then
    echo "TP=$TP but $GPU_COUNT GPU(s) are allocated." >&2
    echo "Override the #BSUB directive on the command line to match, e.g." >&2
    echo "  bsub -gpu \"num=$TP:mode=exclusive_process\" -env \"all, TP=$TP, ...\" < $0" >&2
    exit 1
fi

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

if [ -n "$GUIDELINES_REF" ]; then
    GUIDELINES_FILE="$WORK/guidelines-${GUIDELINES_REF}.md"
    if ! git -C "$REPO" show "${GUIDELINES_REF}:research/annotation-guidelines.md" \
         > "$GUIDELINES_FILE" 2>/dev/null; then
        echo "GUIDELINES_REF='$GUIDELINES_REF' does not name a commit holding" >&2
        echo "research/annotation-guidelines.md. Check 'git log -- <that path>'." >&2
        exit 1
    fi
    export AFB_GUIDELINES_PATH="$GUIDELINES_FILE"
    echo "guidelines replayed from $GUIDELINES_REF -> $GUIDELINES_FILE"
fi

# Principle 4 requires the serving stack version. Runs A and B did not record it,
# which is why this is echoed rather than left to be recovered from the venv.
echo "--- pinning info (principle 4) ---"
python -c "import vllm; print('vllm', vllm.__version__)"
python -c "import torch; print('torch', torch.__version__, 'cuda', torch.version.cuda)"
python -c "from afb import prompt; print('guidelines sha256', prompt.guidelines_digest())"
git -C "$REPO" rev-parse --short HEAD 2>/dev/null | sed 's/^/afb commit /' || true

# --- serve the model -------------------------------------------------------
SERVER_LOG="logs/vllm_${LSB_JOBID:-local}.log"
echo "--- starting vLLM, log: $SERVER_LOG ---"
vllm serve "$MODEL" \
    --port "$PORT" \
    --max-model-len "$MAX_MODEL_LEN" \
    --tensor-parallel-size "$TP" \
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
export AFB_JUDGE_MAX_TOKENS="$MAX_TOKENS"

# vLLM takes the reasoning switch through the chat template, which the OpenAI
# schema has no field for. Setting it explicitly in both directions means the
# rung records what it did instead of inheriting the checkpoint's default.
if [ "$THINKING" = on ]; then
    export AFB_JUDGE_EXTRA_BODY='{"chat_template_kwargs": {"enable_thinking": true}}'
else
    export AFB_JUDGE_EXTRA_BODY='{"chat_template_kwargs": {"enable_thinking": false}}'
fi

# One file per rung. The judge model is part of the name because `--resume` is on
# by default: a shared name would make rung two skip everything rung one judged.
MODEL_SLUG="$(printf '%s' "${MODEL##*/}" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9.' '-' \
              | sed 's/-\{2,\}/-/g; s/^-//; s/-$//')"
[ "$THINKING" = on ] && MODEL_SLUG="${MODEL_SLUG}-thinking"
[ -n "$GUIDELINES_REF" ] && MODEL_SLUG="${MODEL_SLUG}-guidelines-${GUIDELINES_REF}"
OUT="${OUT:-results/judged-trail-${SPLIT}-${MODEL_SLUG}.jsonl}"

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
