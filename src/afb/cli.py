"""afb command-line entry point."""

import argparse
import json
import sys
from pathlib import Path

from afb.models import FailureAnnotation, Trajectory


def _cmd_schema(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for model in (Trajectory, FailureAnnotation):
        path = out_dir / f"{model.__name__}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n")
        print(f"wrote {path}")
    return 0


def _cmd_ingest(args: argparse.Namespace) -> int:
    from afb.ingest.harbor import HarborParseError, parse_job

    out_dir = Path(args.out)
    try:
        trajectories = parse_job(
            Path(args.job_dir),
            tasks_dir=Path(args.tasks_dir) if args.tasks_dir else None,
        )
    except HarborParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    for t in trajectories:
        path = out_dir / f"{t.trajectory_id}.json"
        path.write_text(t.model_dump_json(indent=2) + "\n")
        print(f"wrote {path} ({t.task_id}, outcome: {t.outcome.value}, {len(t.events)} events)")
    return 0


def _cmd_annotate(args: argparse.Namespace) -> int:
    if not args.annotator or not args.annotator.startswith("human:"):
        print("error: --annotator must be of the form human:<id> (spec 003 R5)", file=sys.stderr)
        return 2
    trajectory = Trajectory.model_validate_json(Path(args.trajectory).read_text())

    from afb.annotate import AnnotateApp, AnnotationStore, TrajectoryMismatch

    store = AnnotationStore(Path(args.annotations_dir), trajectory, args.annotator)
    try:
        AnnotateApp(trajectory, store).run()
    except TrajectoryMismatch as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="afb", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    schema = sub.add_parser("schema", help="export JSON Schemas for the public models (spec 002 R5)")
    schema.add_argument("--out", default="schemas", help="output directory (default: schemas/)")
    schema.set_defaults(func=_cmd_schema)

    ingest = sub.add_parser("ingest", help="parse a Harbor job directory into normalized trajectories (spec 002)")
    ingest.add_argument("job_dir", help="path to a Harbor job directory (one `harbor run` output)")
    ingest.add_argument("--out", default="data/trajectories", help="output directory (default: data/trajectories)")
    ingest.add_argument("--tasks-dir", help="directory of downloaded task definitions, for instruction.md resolution")
    ingest.set_defaults(func=_cmd_ingest)

    annotate = sub.add_parser("annotate", help="open the annotation TUI (spec 003)")
    annotate.add_argument("trajectory", help="path to a normalized trajectory JSON file")
    annotate.add_argument("--annotator", required=True, help="annotator id, e.g. human:rasmus")
    annotate.add_argument(
        "--annotations-dir",
        default="data/annotations",
        help="directory for annotation files (default: data/annotations)",
    )
    annotate.set_defaults(func=_cmd_annotate)

    args = parser.parse_args()
    sys.exit(args.func(args))
