"""Parser from Harbor run output to normalized Trajectory objects (spec 002 R6-R7).

Written against the observed format documented in
specs/002-trajectory-data-model/harbor-format-notes.md — read that first.
The trial envelope (result.json, verifier/) is agent-independent; the agent/
directory is not, so event extraction is a per-agent registry. Unknown agents
fail loudly rather than producing an eventless trajectory that looks parsed.
"""

import json
from pathlib import Path
from typing import Callable

from afb.models import Event, Outcome, RunConfig, Trajectory


class HarborParseError(Exception):
    """A trial could not be parsed. Always carries the trial path — no silent skips."""


def _oracle_events(agent_dir: Path) -> list[Event]:
    """The oracle agent replays the reference solution and records no trajectory."""
    return []


#: agent name -> extractor(agent_dir) -> ordered events.
#: terminus-2 is added once its agent/ layout has been observed from a real run
#: (harbor-format-notes.md, "Agent trajectory") — never guessed.
EVENT_EXTRACTORS: dict[str, Callable[[Path], list[Event]]] = {
    "oracle": _oracle_events,
}


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise HarborParseError(f"cannot read {path}: {exc}") from exc


def _outcome(result: dict) -> Outcome:
    if result.get("exception_info") is not None:
        return Outcome.ERROR
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    reward = rewards.get("reward")
    if reward is None:
        raise HarborParseError("result.json has neither exception_info nor a reward")
    return Outcome.SUCCESS if reward >= 1.0 else Outcome.FAILURE


def _instruction_for(task_name: str, tasks_dir: Path | None) -> str | None:
    if tasks_dir is None:
        return None
    short_name = task_name.split("/")[-1]
    path = tasks_dir / short_name / "instruction.md"
    return path.read_text() if path.exists() else None


def parse_trial(
    trial_dir: Path,
    harbor_version: str,
    tasks_dir: Path | None = None,
) -> Trajectory:
    """Parse one trial directory into a Trajectory. Raises HarborParseError with
    the trial path on any missing/unknown piece."""
    result_path = trial_dir / "result.json"
    if not result_path.exists():
        raise HarborParseError(f"{trial_dir}: no result.json — not a trial directory?")
    result = _read_json(result_path)
    try:
        trial_name = result["trial_name"]
        task_name = result["task_name"]
        agent_info = result["agent_info"]
        agent_name = agent_info["name"]
    except KeyError as exc:
        raise HarborParseError(f"{result_path}: missing key {exc}") from exc

    extractor = EVENT_EXTRACTORS.get(agent_name)
    if extractor is None:
        raise HarborParseError(
            f"{trial_dir}: no event extractor for agent {agent_name!r} — its agent/ "
            f"log format has not been observed and documented yet (spec 002 R6)"
        )
    events = extractor(trial_dir / "agent")

    test_stdout = trial_dir / "verifier" / "test-stdout.txt"
    run_config = RunConfig(
        harness="harbor",
        harness_version=harbor_version,
        run_date=(result.get("started_at") or "")[:10],
        extra={
            "task_ref": (result.get("task_id") or {}).get("ref", ""),
            "task_checksum": result.get("task_checksum", ""),
            "job_id": (result.get("config") or {}).get("job_id", ""),
        },
    )
    return Trajectory(
        trajectory_id=trial_name,
        task_id=task_name,
        task_source=result.get("source", ""),
        instruction=_instruction_for(task_name, tasks_dir),
        agent=agent_name,
        agent_version=agent_info.get("version"),
        model=agent_info.get("model_info"),
        run_config=run_config,
        outcome=_outcome(result),
        test_output=test_stdout.read_text() if test_stdout.exists() else None,
        events=events,
        raw_ref=str(trial_dir),
    )


def parse_job(job_dir: Path, tasks_dir: Path | None = None) -> list[Trajectory]:
    """Parse every trial in a Harbor job directory (one `harbor run` invocation).

    Spec 002 R7: any unparseable trial raises — a job is either fully ingested
    or the failure names the trial that broke.
    """
    lock = _read_json(job_dir / "lock.json")
    harbor_version = (lock.get("harbor") or {}).get("version")
    if not harbor_version:
        raise HarborParseError(f"{job_dir}/lock.json: no harbor.version — cannot pin run")

    trial_dirs = sorted(d for d in job_dir.iterdir() if d.is_dir() and (d / "result.json").exists())
    if not trial_dirs:
        raise HarborParseError(f"{job_dir}: no trial directories found")
    return [parse_trial(d, harbor_version, tasks_dir) for d in trial_dirs]
