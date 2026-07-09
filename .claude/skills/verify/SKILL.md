---
name: verify
description: How to launch and drive this project's surfaces (afb CLI + annotation TUI) for end-to-end verification.
---

# Verifying afb

## CLI surface

```sh
uv run afb schema --out <dir>        # writes Trajectory/FailureAnnotation JSON Schemas
uv run afb ingest <harbor-job-dir> --out <dir> [--tasks-dir <dir>]   # Harbor run → trajectories
uv run afb annotate <trajectory.json> --annotator human:<id> --annotations-dir <dir>
```

Real Harbor output for ingest testing: `data/raw/smoke-oracle/smoke-oracle` (2 oracle
trials, gitignored). A fresh one costs ~4 min: `harbor run -d terminal-bench/terminal-bench-2
-a oracle -l 2 -n 1 -o data/raw/<name> -y -q` (needs Docker running; harbor is a uv tool,
`export PATH="$HOME/.local/bin:$PATH"`). Task definitions: `harbor tasks download
terminal-bench/<task> -o <dir>`.

Fixture trajectory for TUI work: `tests/fixtures/sample_trajectory.json` (15 events,
failure chain: ACT-1 at event 8 → RFL-1 at event 12). Always point `--annotations-dir`
at a scratch dir — never at `data/annotations/` during verification.

## Driving the TUI (tmux)

```sh
tmux -L afb new-session -d -s v -x 170 -y 45 "uv run afb annotate tests/fixtures/sample_trajectory.json --annotator human:rasmus --annotations-dir /tmp/anns"
sleep 4
tmux -L afb capture-pane -t v -p          # screen dump
tmux -L afb send-keys -t v <keys>         # drive; use -l for literal text
tmux -L afb kill-server                   # cleanup
```

Gotchas learned the hard way:

- **Do not redirect stderr** of the app command — Textual renders the UI via stderr;
  redirecting it leaves a blank pane.
- **The annotation form modal does not auto-focus**: the first Tab focuses the first
  field (span-start). Traversal from open: Tab×3 → function select; then Tab order is
  type select → proposed-category → severity → confidence → root-cause checkbox →
  cascade select → rationale TextArea → Save → Cancel. Backwards is `BTab`.
- Selects: Enter opens the overlay (highlight starts on the current value; blank counts
  as an entry when allow_blank), Down/Up move, Enter picks. Send keys in *small batches
  with sleeps and capture-pane between* — long blind key blasts desync.
- In zsh, `$T` holding a command string won't word-split; define a function:
  `t() { tmux -L afb send-keys -t v "$@"; }`.
- This Textual version uses `Select.NULL` as the no-selection sentinel (`Select.BLANK`
  resolves to something bogus — never use it).

## What to check after a TUI session

- Annotation JSON in the annotations dir validates and contains what was entered.
- The trajectory file is byte-identical (sha256 before/after) — the tool must never
  write to it.
- Reopen the app with the same args: annotations must resume into the bottom table.
- Hash guard: modify a copy of the trajectory (same trajectory_id), point at the same
  annotations dir → app must refuse with "hash mismatch".
