"""Command line entry point: `afb <command>`.

The commands follow the order the framework is built in. Validate the judge
against TRAIL first, then label real runs, then analyse them.

    afb prompt --split gaia --index 0     inspect what the judge is asked
    afb judge-trail --split gaia          label TRAIL traces, resumable
    afb agreement --judged FILE           judge validity, subquestion 2
    afb coverage --judged FILE            taxonomy revision evidence, subquestion 1
    afb judge-runs --runs DIR             label Terminal-Bench runs
    afb variance --runs DIR --judged FILE systematic vs stochastic, subquestion 3
    afb profiles --runs DIR --judged FILE failure profiles per agent, subquestion 4
"""

import argparse
import json
import re
import sys
from pathlib import Path

from afb import agreement, coverage, harbor, judge, mapping, prompt, runs, store, taxonomy, trail
from afb.annotation import AnnotationSet
from afb.trajectory import Trajectory

SPLITS = ("gaia", "swe_bench")


def _print(payload: object) -> None:
    print(json.dumps(payload, indent=2, default=str))


def _table(rows: list[tuple[str, object]]) -> None:
    width = max((len(str(name)) for name, _ in rows), default=0)
    for name, value in rows:
        print(f"  {str(name):<{width}}  {value}")


def cmd_taxonomy(args: argparse.Namespace) -> int:
    data = taxonomy.load(args.version)
    print(f"Taxonomy {data['version']} ({data['status']})")
    for function in data["cognitive_functions"]:
        print(f"\n{function['code']} - {function['name']}")
        for entry in taxonomy.error_types(args.version).values():
            if entry["function"] == function["code"]:
                addition = "  [terminal]" if entry.get("terminal_addition") else ""
                print(f"  {entry['code']:8} {entry['name']}{addition}")
    print(f"\nescape hatch: {taxonomy.escape_hatch_code(args.version)}")
    print(f"mapping from TRAIL: {mapping.coverage_report()}")
    return 0


def cmd_prompt(args: argparse.Namespace) -> int:
    trajectory = _trail_trajectories(args.split, args.index + 1)[args.index][0]
    text = prompt.build(trajectory, args.version, args.char_budget)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"{len(text)} characters written to {args.out}")
    else:
        print(text)
    return 0


def _trail_trajectories(split: str, limit: int | None = None) -> list[tuple[Trajectory, object]]:
    cases = []
    for trajectory, labels in trail.load(split):
        cases.append((trajectory, labels))
        if limit and len(cases) >= limit:
            break
    return cases


def _model_slug(model: str) -> str:
    """A filename-safe fragment of a model id: `Qwen/Qwen3-14B-AWQ` -> `qwen3-14b-awq`."""
    return re.sub(r"[^a-z0-9.]+", "-", model.rsplit("/", 1)[-1].lower()).strip("-")


def _output_guard(out: Path, model: str, resume: bool) -> int:
    """Refuse to append one judge's labels to another's, or to duplicate a run.

    Several models are run over the same split to separate judge capacity from
    guideline quality, and `--resume` is on by default. Without this check the
    second model skips every trajectory the first one judged, and the resulting
    file is attributable to neither. Nothing is deleted here: judge output costs
    GPU hours, so a collision is reported rather than resolved.
    """
    if not out.exists():
        return 0
    if not resume:
        print(
            f"{out} exists, and --no-resume appends rather than truncating, "
            "which would double every trajectory. Move or remove it, or pass --out.",
            file=sys.stderr,
        )
        return 1

    existing = store.judge_models(out)
    if foreign := existing - {None, model}:
        print(
            f"{out} already holds labels from {sorted(str(m) for m in foreign)}, not {model}. "
            "Pass --out to keep the runs separate.",
            file=sys.stderr,
        )
        return 1
    if None in existing:
        print(
            f"warning: {out} holds labels with no recorded annotator, so they "
            f"cannot be confirmed to come from {model}.",
            file=sys.stderr,
        )
    return 0


def cmd_judge_trail(args: argparse.Namespace) -> int:
    """Label TRAIL traces so the judge can be scored against expert annotations."""
    config = judge.JudgeConfig(char_budget=args.char_budget, taxonomy_version=args.version)
    if args.model:
        config.model = args.model

    # The model is part of the default name: one split judged by several models
    # must not land in one file.
    out = Path(
        args.out
        or f"results/judged-trail-{args.split}-{_model_slug(config.model)}.jsonl"
    )
    if _output_guard(out, config.model, args.resume):
        return 1
    done = store.judged_ids(out) if args.resume else set()

    cases = _trail_trajectories(args.split, args.limit)
    failures = 0
    for position, (trajectory, _) in enumerate(cases, start=1):
        if trajectory.trajectory_id in done:
            continue
        try:
            annotations = judge.judge(trajectory, config)
        except judge.JudgeError as error:
            failures += 1
            print(f"[{position}/{len(cases)}] FAILED {trajectory.trajectory_id}: {error}",
                  file=sys.stderr)
            continue
        store.append(out, annotations)
        print(f"[{position}/{len(cases)}] {trajectory.trajectory_id}: "
              f"{len(annotations.annotations)} annotations")

    print(f"\nwrote {out}, {failures} failures")
    return 1 if failures and not args.keep_going else 0


def cmd_agreement(args: argparse.Namespace) -> int:
    """Subquestion 2: how well the judge agrees with TRAIL's experts."""
    judged = {s.trajectory_id: s for s in store.load(Path(args.judged))}
    reports = []
    for split in args.splits:
        cases = [
            (trajectory, labels, judged[trajectory.trajectory_id])
            for trajectory, labels in trail.load(split)
            if trajectory.trajectory_id in judged
        ]
        if not cases:
            continue
        reports.append(
            agreement.score(
                cases, label=split, tolerance=args.tolerance, version=args.mapping
            )
        )

    if not reports:
        print("no judged trajectories matched the TRAIL splits", file=sys.stderr)
        return 1

    for report in reports:
        print(f"\n=== {report.label} ===")
        _table(list(report.summary().items()))
        if args.confusion:
            print("\n  expert function -> judge function")
            for (expert, judge_function), count in report.confusion().most_common():
                mark = "" if expert == judge_function else "   <-"
                print(f"    {expert:12} -> {judge_function:12} {count:4}{mark}")
        if args.by_category:
            print("\n  TRAIL category -> judge functions (pairs, agreeing/decidable)")
            for category, row in report.by_category().items():
                labels = ", ".join(f"{f} {n}" for f, n in row["judge_functions"])
                print(
                    f"    {category[:34]:34} n={row['pairs']:3}  "
                    f"expert={str(row['expert_function'] or '-'):10} "
                    f"agree {row['function_agreeing']}/{row['function_decidable']}  {labels}"
                )
    return 0


def cmd_coverage(args: argparse.Namespace) -> int:
    """Subquestion 1: evidence for revising the taxonomy."""
    sets: list[AnnotationSet] = []
    for path in args.judged:
        sets += store.load(Path(path))
    report = coverage.analyse(sets, args.version)
    print(coverage.revision_report(report))
    if args.json:
        _print(report.summary())
    return 0


def cmd_judge_runs(args: argparse.Namespace) -> int:
    """Label Terminal-Bench runs with the validated judge."""
    trajectories = harbor.load_dir(Path(args.runs))
    if not trajectories:
        print(f"no run files found under {args.runs}", file=sys.stderr)
        return 1

    config = judge.JudgeConfig(char_budget=args.char_budget, taxonomy_version=args.version)
    if args.model:
        config.model = args.model

    out = Path(args.out or f"results/judged-runs-{_model_slug(config.model)}.jsonl")
    if _output_guard(out, config.model, args.resume):
        return 1
    done = store.judged_ids(out) if args.resume else set()

    failures = 0
    for position, trajectory in enumerate(trajectories, start=1):
        if trajectory.trajectory_id in done:
            continue
        try:
            annotations = judge.judge(trajectory, config)
        except judge.JudgeError as error:
            failures += 1
            print(f"[{position}] FAILED {trajectory.trajectory_id}: {error}", file=sys.stderr)
            continue
        store.append(out, annotations)
        print(f"[{position}/{len(trajectories)}] {trajectory.trajectory_id}: "
              f"{len(annotations.annotations)} annotations")

    print(f"\nwrote {out}, {failures} failures")
    return 1 if failures and not args.keep_going else 0


def _run_cases(runs_dir: str, judged_path: str) -> list[tuple[Trajectory, AnnotationSet]]:
    judged = {s.trajectory_id: s for s in store.load(Path(judged_path))}
    return [
        (trajectory, judged[trajectory.trajectory_id])
        for trajectory in harbor.load_dir(Path(runs_dir))
        if trajectory.trajectory_id in judged
    ]


def cmd_variance(args: argparse.Namespace) -> int:
    """Subquestion 3: systematic versus stochastic failures."""
    cases = _run_cases(args.runs, args.judged)
    if not cases:
        print("no judged runs found", file=sys.stderr)
        return 1

    entries = runs.variance(cases, args.threshold)
    print("=== per task ===")
    for entry in entries:
        summary = entry.summary(args.threshold)
        print(f"\n{summary['agent']} / {summary['task_id']}  "
              f"runs={summary['runs']} success={summary['success_rate']}")
        for code, rate in summary["systematic"]:
            print(f"    systematic  {code:8} {rate:.0%} of runs")
        for code, rate in summary["stochastic"]:
            print(f"    stochastic  {code:8} {rate:.0%} of runs")
    print("\n=== overall ===")
    _table(list(runs.variance_summary(entries, args.threshold).items()))
    return 0


def cmd_profiles(args: argparse.Namespace) -> int:
    """Subquestion 4: whether failure profiles differ across agents."""
    cases = _run_cases(args.runs, args.judged)
    if not cases:
        print("no judged runs found", file=sys.stderr)
        return 1

    entries = runs.profiles(cases)
    for entry in entries:
        print(f"\n=== {entry.agent} ===")
        _table(list(entry.summary().items()))
    if len(entries) > 1:
        print("\n=== pairwise divergence ===")
        for row in runs.compare(entries, args.level):
            print(f"  {row['agents'][0]} vs {row['agents'][1]}: "
                  f"{row['divergence']} over {row['shared_tasks']} shared tasks")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="afb", description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add(name: str, handler, help_text: str) -> argparse.ArgumentParser:
        sub = subparsers.add_parser(name, help=help_text)
        sub.set_defaults(handler=handler)
        sub.add_argument("--version", default=taxonomy.DEFAULT_VERSION, help="taxonomy version")
        return sub

    add("taxonomy", cmd_taxonomy, "print the taxonomy and its TRAIL mapping status")

    p = add("prompt", cmd_prompt, "print the judge prompt for one TRAIL trace")
    p.add_argument("--split", choices=SPLITS, default="gaia")
    p.add_argument("--index", type=int, default=0)
    p.add_argument("--char-budget", type=int, default=prompt.DEFAULT_CHAR_BUDGET)
    p.add_argument("--out")

    p = add("judge-trail", cmd_judge_trail, "run the judge over TRAIL traces")
    p.add_argument("--split", choices=SPLITS, default="gaia")
    p.add_argument("--limit", type=int)
    p.add_argument("--model")
    p.add_argument("--char-budget", type=int, default=prompt.DEFAULT_CHAR_BUDGET)
    p.add_argument("--out")
    p.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="skip trajectories already in the output file (default)",
    )
    p.add_argument("--keep-going", action="store_true")

    p = add("agreement", cmd_agreement, "score judge labels against TRAIL experts")
    p.add_argument("--judged", required=True)
    p.add_argument("--splits", nargs="+", choices=SPLITS, default=list(SPLITS))
    p.add_argument("--tolerance", type=int, default=0, help="event window for a match")
    p.add_argument(
        "--mapping",
        default=mapping.DEFAULT_VERSION,
        help="TRAIL mapping version; v1 and v2 are sensitivity variants of v0",
    )
    p.add_argument("--confusion", action="store_true")
    p.add_argument(
        "--by-category",
        action="store_true",
        help="break matched pairs down by TRAIL expert category, to separate a "
        "judge disagreement from an artifact of how that category was mapped",
    )

    p = add("coverage", cmd_coverage, "taxonomy usage and revision candidates")
    p.add_argument("--judged", nargs="+", required=True)
    p.add_argument("--json", action="store_true")

    p = add("judge-runs", cmd_judge_runs, "run the judge over Terminal-Bench runs")
    p.add_argument("--runs", required=True)
    p.add_argument("--model")
    p.add_argument("--char-budget", type=int, default=prompt.DEFAULT_CHAR_BUDGET)
    p.add_argument("--out")
    p.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="skip trajectories already in the output file (default)",
    )
    p.add_argument("--keep-going", action="store_true")

    p = add("variance", cmd_variance, "systematic versus stochastic failures")
    p.add_argument("--runs", required=True)
    p.add_argument("--judged", required=True)
    p.add_argument("--threshold", type=float, default=runs.SYSTEMATIC_THRESHOLD)

    p = add("profiles", cmd_profiles, "compare failure profiles across agents")
    p.add_argument("--runs", required=True)
    p.add_argument("--judged", required=True)
    p.add_argument("--level", choices=("function", "code"), default="function")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
