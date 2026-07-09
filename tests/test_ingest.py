"""Golden-file tests for the Harbor ingest parser (spec 002 R6-R7).

Fixture: tests/fixtures/harbor_job is one real (trimmed to a single trial)
`harbor run` output — oracle agent, terminal-bench-2, Harbor 0.18.0.
"""

import json
import shutil
from pathlib import Path

import pytest

from afb.ingest.harbor import HarborParseError, parse_job, parse_trial
from afb.models import Outcome, Trajectory

FIXTURES = Path(__file__).parent / "fixtures"
JOB_DIR = FIXTURES / "harbor_job"
TASKS_DIR = FIXTURES / "harbor_tasks"
TRIAL_DIR = JOB_DIR / "circuit-fibsqrt__ZAV5p9S"


def test_parse_job_golden():
    trajectories = parse_job(JOB_DIR, tasks_dir=TASKS_DIR)
    assert len(trajectories) == 1
    t = trajectories[0]
    assert t.trajectory_id == "circuit-fibsqrt__ZAV5p9S"
    assert t.task_id == "terminal-bench/circuit-fibsqrt"
    assert t.task_source == "terminal-bench/terminal-bench-2"
    assert t.agent == "oracle"
    assert t.agent_version == "1.0.0"
    assert t.model is None
    assert t.outcome is Outcome.SUCCESS
    assert t.run_config.harness == "harbor"
    assert t.run_config.harness_version == "0.18.0"
    assert t.run_config.run_date == "2026-07-09"
    assert t.run_config.extra["task_ref"].startswith("sha256:")
    assert t.events == []  # oracle records no trajectory
    assert "3 passed" in t.test_output
    assert "instruction" not in (t.instruction or "").lower() or t.instruction  # present
    assert t.instruction and len(t.instruction) > 50
    assert t.raw_ref == str(TRIAL_DIR)


def test_parse_trial_is_rederivable():
    a = parse_trial(TRIAL_DIR, harbor_version="0.18.0", tasks_dir=TASKS_DIR)
    b = parse_trial(TRIAL_DIR, harbor_version="0.18.0", tasks_dir=TASKS_DIR)
    assert a == b
    assert Trajectory.model_validate_json(a.model_dump_json()) == a


def test_missing_instruction_dir_leaves_none():
    t = parse_trial(TRIAL_DIR, harbor_version="0.18.0", tasks_dir=None)
    assert t.instruction is None


def _copy_trial(tmp_path: Path) -> Path:
    dst = tmp_path / "job"
    shutil.copytree(JOB_DIR, dst)
    return dst


def test_unknown_agent_fails_loudly(tmp_path):
    job = _copy_trial(tmp_path)
    result_path = job / "circuit-fibsqrt__ZAV5p9S" / "result.json"
    result = json.loads(result_path.read_text())
    result["agent_info"]["name"] = "terminus-2"
    result_path.write_text(json.dumps(result))
    with pytest.raises(HarborParseError, match="no event extractor for agent 'terminus-2'"):
        parse_job(job)


def test_zero_reward_maps_to_failure(tmp_path):
    job = _copy_trial(tmp_path)
    result_path = job / "circuit-fibsqrt__ZAV5p9S" / "result.json"
    result = json.loads(result_path.read_text())
    result["verifier_result"]["rewards"]["reward"] = 0.0
    result_path.write_text(json.dumps(result))
    assert parse_job(job)[0].outcome is Outcome.FAILURE


def test_exception_maps_to_error(tmp_path):
    job = _copy_trial(tmp_path)
    result_path = job / "circuit-fibsqrt__ZAV5p9S" / "result.json"
    result = json.loads(result_path.read_text())
    result["exception_info"] = {"type": "AgentTimeoutError"}
    result_path.write_text(json.dumps(result))
    assert parse_job(job)[0].outcome is Outcome.ERROR


def test_job_without_trials_fails_loudly(tmp_path):
    job = _copy_trial(tmp_path)
    shutil.rmtree(job / "circuit-fibsqrt__ZAV5p9S")
    with pytest.raises(HarborParseError, match="no trial directories"):
        parse_job(job)


def test_corrupt_result_json_fails_loudly(tmp_path):
    job = _copy_trial(tmp_path)
    (job / "circuit-fibsqrt__ZAV5p9S" / "result.json").write_text("{not json")
    with pytest.raises(HarborParseError, match="cannot read"):
        parse_job(job)
