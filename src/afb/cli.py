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


def main() -> None:
    parser = argparse.ArgumentParser(prog="afb", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    schema = sub.add_parser("schema", help="export JSON Schemas for the public models (spec 002 R5)")
    schema.add_argument("--out", default="schemas", help="output directory (default: schemas/)")
    schema.set_defaults(func=_cmd_schema)

    annotate = sub.add_parser("annotate", help="open the annotation TUI (spec 003, not yet implemented)")
    annotate.add_argument("trajectory", help="path to a normalized trajectory JSON file")
    annotate.add_argument("--annotator", help="annotator id, e.g. human:rasmus")
    annotate.set_defaults(func=None)

    args = parser.parse_args()
    if args.func is None:
        parser.exit(2, f"afb {args.command}: not implemented yet — see specs/003-annotation-tool/\n")
    sys.exit(args.func(args))
