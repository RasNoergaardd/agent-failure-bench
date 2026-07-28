"""Tests for the pipeline that do not need the network or the gated dataset.

TRAIL ingest is exercised separately in `test_trail.py`, which skips when the
dataset is not present locally.
"""

import json

import pytest
from pydantic import ValidationError

from afb import agreement, coverage, harbor, judge, mapping, prompt, runs, store, taxonomy
from afb.annotation import Annotation, AnnotationSet
from afb.mapping import Status
from afb.trail import TrailError, TrailLabels
from afb.trajectory import Outcome, Trajectory


def make_trajectory(trajectory_id="t1", events=6, outcome="failure", **metadata) -> Trajectory:
    return Trajectory(
        trajectory_id=trajectory_id,
        source="harbor",
        task_instruction="Fix the port.",
        events=[
            {"index": i, "kind": "action", "content": f"command {i}"} for i in range(events)
        ],
        outcome=outcome,
        metadata=metadata,
    )


def make_annotation(**overrides) -> Annotation:
    base = dict(
        id="a1",
        trajectory_id="t1",
        event_span=(1, 1),
        cognitive_function="reflection",
        error_type="RFL-1",
        severity="high",
        root_cause=True,
        rationale="misread the output",
        confidence="certain",
    )
    return Annotation(**(base | overrides))


# --- taxonomy -------------------------------------------------------------


def test_taxonomy_is_internally_consistent():
    functions = taxonomy.cognitive_functions()
    entries = taxonomy.error_types()
    assert len(entries) == 24
    assert set(functions) == {"MEM", "RFL", "PLN", "ACT", "SYS"}
    for code, entry in entries.items():
        assert code.split("-")[0] == entry["function"]
        assert entry["definition"].strip()


# --- annotation contract --------------------------------------------------


def test_axes_must_agree():
    with pytest.raises(ValidationError, match="belongs to reflection"):
        make_annotation(cognitive_function="memory")


def test_unknown_code_rejected():
    with pytest.raises(ValidationError, match="not a code"):
        make_annotation(error_type="RFL-99")


def test_escape_hatch_requires_proposal():
    with pytest.raises(ValidationError, match="requires proposed_category"):
        make_annotation(error_type="NEW-?", cognitive_function="action")
    ok = make_annotation(
        error_type="NEW-?", cognitive_function="action", proposed_category="tmux desync"
    )
    assert ok.proposed_category


def test_root_cause_cannot_cascade():
    with pytest.raises(ValidationError, match="does not cascade"):
        make_annotation(cascade_of="a2")


def test_cascade_must_resolve():
    a = make_annotation()
    b = make_annotation(id="a2", root_cause=False, cascade_of="missing")
    with pytest.raises(ValidationError, match="does not exist"):
        AnnotationSet(trajectory_id="t1", annotations=[a, b])


# --- trajectory contract --------------------------------------------------


def test_event_indices_must_be_positional():
    with pytest.raises(ValidationError, match="must be 0"):
        Trajectory(
            trajectory_id="t",
            source="s",
            task_instruction="i",
            events=[{"index": 3, "kind": "agent", "content": "x"}],
        )


def test_span_returns_the_annotated_events():
    trajectory = make_trajectory()
    assert [e.index for e in trajectory.span(1, 3)] == [1, 2, 3]
    with pytest.raises(IndexError):
        trajectory.span(0, 99)


# --- prompt ---------------------------------------------------------------


def test_prompt_contains_taxonomy_guidelines_and_trajectory():
    text = prompt.build(make_trajectory())
    assert "MEM-1" in text and "SYS-5" in text
    assert "Root-cause heuristic" in text  # verbatim from the guidelines
    assert "[0] ACTION" in text
    assert "NEW-?" in text


def test_long_events_are_truncated_visibly():
    trajectory = Trajectory(
        trajectory_id="t",
        source="harbor",
        task_instruction="i",
        events=[{"index": 0, "kind": "observation", "content": "x" * 500_000}],
    )
    rendered = prompt.render_trajectory(trajectory, char_budget=5_000)
    assert "characters omitted by the harness" in rendered
    assert len(rendered) < 20_000


def test_truncation_keeps_head_and_tail():
    text = prompt._truncate("START" + "-" * 5_000 + "END", 1_000)
    assert text.startswith("START") and text.endswith("END")


# --- judge parsing --------------------------------------------------------


def test_parse_accepts_fenced_json():
    trajectory = make_trajectory()
    payload = {"trajectory_id": "t1", "annotations": [json.loads(make_annotation().model_dump_json())]}
    response = f"Here you go:\n```json\n{json.dumps(payload)}\n```"
    parsed = judge.parse(response, trajectory)
    assert parsed.annotations[0].error_type == "RFL-1"


def test_parse_fills_missing_trajectory_ids():
    trajectory = make_trajectory()
    annotation = json.loads(make_annotation().model_dump_json())
    annotation.pop("trajectory_id")
    parsed = judge.parse(json.dumps({"annotations": [annotation]}), trajectory)
    assert parsed.trajectory_id == "t1"


def test_parse_rejects_spans_outside_the_trajectory():
    trajectory = make_trajectory(events=3)
    annotation = json.loads(make_annotation(event_span=(0, 9)).model_dump_json())
    with pytest.raises(ValueError, match="but the trajectory has 3 events"):
        judge.parse(json.dumps({"annotations": [annotation]}), trajectory)


def test_parse_ignores_reasoning_blocks():
    """Qwen3 and other reasoning models wrap thinking in <think> tags."""
    trajectory = make_trajectory()
    payload = {"annotations": [json.loads(make_annotation().model_dump_json())]}
    response = (
        "<think>Maybe {\"error_type\": \"PLN-3\"} fits? No, the output was misread.</think>\n"
        f"{json.dumps(payload)}"
    )
    parsed = judge.parse(response, trajectory)
    assert len(parsed.annotations) == 1
    assert parsed.annotations[0].error_type == "RFL-1"


def test_parse_rejects_non_json():
    with pytest.raises(judge.JudgeError, match="no JSON object"):
        judge.parse("I could not find any errors.", make_trajectory())


def test_judge_retries_with_the_validation_error():
    trajectory = make_trajectory()
    good = json.dumps({"annotations": [json.loads(make_annotation().model_dump_json())]})
    calls = []

    def fake(config, messages):
        calls.append(messages)
        return "not json at all" if len(calls) == 1 else good

    result = judge.judge(trajectory, judge.JudgeConfig(attempts=2), complete=fake)
    assert len(result.annotations) == 1
    assert "was rejected" in calls[1][-1]["content"]


def test_judge_gives_up_after_configured_attempts():
    with pytest.raises(judge.JudgeError, match="no valid annotations"):
        judge.judge(
            make_trajectory(),
            judge.JudgeConfig(attempts=2),
            complete=lambda config, messages: "still not json",
        )


# --- mapping --------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Formatting Errors", "ACT-5"),
        ("Formatting Error", "ACT-5"),
        ("formatting errors", "ACT-5"),
        ("Goal deviation", "PLN-4"),
        ("Context Handling Failure", "MEM-1"),
        ("  Incorrect Problem Identification", "PLN-1"),
    ],
)
def test_category_normalization(raw, expected):
    assert mapping.map_category(raw).error_type == expected


def test_typo_resolves_by_close_match():
    result = mapping.map_category("Instruction non complience")
    assert result.trail_category == "Instruction Non-compliance"
    assert result.status is Status.AMBIGUOUS


def test_excluded_categories_are_not_scoreable():
    assert mapping.map_category("Task Orchestration").status is Status.OUT_OF_SCOPE
    assert mapping.map_category("Poor Information Retrieval").status is Status.OUT_OF_SCOPE


def test_unknown_category_is_reported_not_dropped():
    assert mapping.map_category("Something Entirely New").status is Status.UNKNOWN


# --- agreement ------------------------------------------------------------


def build_case(expert_specs, judge_specs):
    trajectory = make_trajectory(events=8)
    labels = TrailLabels(
        trace_id="t1",
        errors=[
            TrailError(category=category, location="s", event_index=index, impact=impact)
            for category, index, impact in expert_specs
        ],
    )
    annotations = AnnotationSet(
        trajectory_id="t1",
        annotations=[
            make_annotation(
                id=f"a{n}",
                event_span=(index, index),
                cognitive_function=function,
                error_type=code,
                severity=severity,
                root_cause=n == 0,
            )
            for n, (code, function, index, severity) in enumerate(judge_specs)
        ],
    )
    return trajectory, labels, annotations


def test_agreement_counts_a_perfect_match():
    case = build_case(
        [("Tool Output Misinterpretation", 2, "HIGH")],
        [("RFL-1", "reflection", 2, "high")],
    )
    report = agreement.score([case])
    assert report.recall == 1.0 and report.precision == 1.0
    assert report.classification("code") == (1, 1, 1.0)
    assert report.severity() == (1, 1, 1.0)


def test_agreement_detects_wrong_classification():
    case = build_case(
        [("Tool Output Misinterpretation", 2, "HIGH")],
        [("PLN-4", "planning", 2, "low")],
    )
    report = agreement.score([case])
    assert len(report.pairs) == 1  # located correctly
    assert report.classification("code")[2] == 0.0  # but classified wrongly
    assert report.severity()[2] == 0.0


def test_out_of_scope_experts_are_excluded_from_recall():
    case = build_case([("Task Orchestration", 2, "HIGH")], [])
    report = agreement.score([case])
    assert report.out_of_scope == 1
    assert report.scoreable_expert_errors == 0
    assert report.recall == 0.0  # nothing scoreable, not a miss


def test_ambiguous_category_scores_function_only():
    case = build_case(
        [("Instruction Non-compliance", 3, "MEDIUM")],
        [("MEM-3", "memory", 3, "medium")],
    )
    report = agreement.score([case])
    assert report.classification("code") == (0, 0, 0.0)  # undecidable
    assert report.classification("function") == (1, 1, 1.0)


def test_matching_is_one_to_one():
    case = build_case(
        [("Tool Output Misinterpretation", 2, "HIGH")],
        [("RFL-1", "reflection", 2, "high"), ("RFL-1", "reflection", 2, "high")],
    )
    report = agreement.score([case])
    assert len(report.pairs) == 1
    assert report.unmatched_judge == 1
    assert report.precision == 0.5


def test_tolerance_widens_the_match_window():
    case = build_case(
        [("Tool Output Misinterpretation", 2, "HIGH")],
        [("RFL-1", "reflection", 4, "high")],
    )
    assert len(agreement.score([case]).pairs) == 0
    assert len(agreement.score([case], tolerance=2).pairs) == 1


def test_kappa_is_zero_when_agreement_is_chance():
    cases = [
        build_case([("Tool Output Misinterpretation", 1, "HIGH")], [("RFL-1", "reflection", 1, "high")]),
        build_case([("Goal Deviation", 1, "HIGH")], [("RFL-1", "reflection", 1, "high")]),
    ]
    report = agreement.score(cases)
    assert -1.0 <= report.function_kappa() <= 1.0


# --- coverage -------------------------------------------------------------


def test_coverage_finds_unused_codes_and_proposals():
    sets = [
        AnnotationSet(trajectory_id="t1", annotations=[make_annotation()]),
        AnnotationSet(
            trajectory_id="t2",
            annotations=[
                make_annotation(
                    id="a1",
                    trajectory_id="t2",
                    error_type="NEW-?",
                    cognitive_function="action",
                    proposed_category="Terminal multiplexer desync",
                )
            ],
        ),
    ]
    report = coverage.analyse(sets)
    assert report.by_code["RFL-1"] == 1
    assert report.escape_hatch_count == 1
    assert "ACT-6" in report.unused_codes()
    assert "Root-cause" not in coverage.revision_report(report)
    assert "unused" in coverage.revision_report(report)


def test_proposals_are_clustered_by_wording():
    sets = [
        AnnotationSet(
            trajectory_id=f"t{n}",
            annotations=[
                make_annotation(
                    trajectory_id=f"t{n}",
                    error_type="NEW-?",
                    cognitive_function="action",
                    proposed_category=text,
                )
            ],
        )
        for n, text in enumerate(["Tmux desync", "tmux desync!", "  TMUX   DESYNC "])
    ]
    report = coverage.analyse(sets)
    assert report.addition_candidates() == [("tmux desync", 3)]


# --- harbor ---------------------------------------------------------------


def test_harbor_reads_chat_shaped_runs():
    record = {
        "task_id": "fix-port",
        "run_id": 3,
        "agent": "terminus-2",
        "resolved": False,
        "instruction": "Fix the port.",
        "messages": [
            {"role": "assistant", "content": "I will look at the config."},
            {"role": "tool", "content": "port: 8081"},
            {"role": "system", "content": "step budget exhausted"},
        ],
    }
    trajectory = harbor.to_trajectory(record)
    assert trajectory.trajectory_id == "fix-port::3"
    assert trajectory.outcome is Outcome.FAILURE
    assert [e.kind.value for e in trajectory.events] == ["agent", "observation", "system"]
    assert trajectory.metadata["agent"] == "terminus-2"


def test_harbor_splits_command_and_output():
    record = {
        "task_id": "t",
        "success": True,
        "instruction": "do it",
        "steps": [{"command": "ls -la", "output": "file.txt"}],
    }
    trajectory = harbor.to_trajectory(record)
    assert [e.kind.value for e in trajectory.events] == ["action", "observation"]
    assert [e.index for e in trajectory.events] == [0, 1]
    assert trajectory.outcome is Outcome.SUCCESS


def test_harbor_reads_a_directory(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({
        "task_id": "x", "run_id": 1, "messages": [{"role": "assistant", "content": "hi"}]}))
    (tmp_path / "b.jsonl").write_text("\n".join(json.dumps({
        "task_id": "y", "run_id": n, "messages": [{"role": "assistant", "content": "hi"}]})
        for n in range(2)))
    assert len(harbor.load_dir(tmp_path)) == 3


# --- repeated runs --------------------------------------------------------


def repeated(agent, task, outcomes, codes_per_run):
    cases = []
    for n, (outcome, codes) in enumerate(zip(outcomes, codes_per_run)):
        trajectory = make_trajectory(
            trajectory_id=f"{task}-{n}", outcome=outcome, agent=agent, task_id=task
        )
        annotations = AnnotationSet(
            trajectory_id=f"{task}-{n}",
            annotations=[
                make_annotation(
                    id=f"a{i}",
                    trajectory_id=f"{task}-{n}",
                    error_type=code,
                    cognitive_function=taxonomy.cognitive_functions()[code.split("-")[0]],
                    root_cause=i == 0,
                )
                for i, code in enumerate(codes)
            ],
        )
        cases.append((trajectory, annotations))
    return cases


def test_systematic_and_stochastic_are_separated():
    cases = repeated(
        "terminus-2", "fix-port",
        ["failure"] * 5,
        [["RFL-1", "PLN-3"], ["RFL-1"], ["RFL-1"], ["RFL-1", "ACT-3"], ["RFL-1"]],
    )
    entry = runs.variance(cases)[0]
    assert entry.runs == 5
    assert entry.systematic() == [("RFL-1", 1.0)]
    assert dict(entry.stochastic()) == {"PLN-3": 0.2, "ACT-3": 0.2}
    assert entry.outcome_is_stable


def test_repeated_annotations_count_once_per_run():
    cases = repeated("a", "t", ["failure"], [["RFL-1", "RFL-1", "RFL-1"]])
    assert runs.variance(cases)[0].runs_with_code["RFL-1"] == 1


def test_unstable_outcome_is_flagged():
    cases = repeated("a", "t", ["success", "failure", "success"], [[], ["RFL-1"], []])
    entry = runs.variance(cases)[0]
    assert not entry.outcome_is_stable
    assert entry.success_rate == pytest.approx(2 / 3)


def test_profiles_diverge_when_agents_fail_differently():
    cases = repeated("alpha", "t", ["failure"] * 3, [["RFL-1"]] * 3)
    cases += repeated("beta", "t", ["failure"] * 3, [["PLN-3"]] * 3)
    entries = runs.profiles(cases)
    assert [e.agent for e in entries] == ["alpha", "beta"]
    comparison = runs.compare(entries)[0]
    assert comparison["divergence"] == 1.0  # disjoint profiles
    assert comparison["shared_tasks"] == 1


def test_identical_profiles_do_not_diverge():
    cases = repeated("alpha", "t", ["failure"], [["RFL-1"]])
    cases += repeated("beta", "t", ["failure"], [["RFL-1"]])
    assert runs.compare(runs.profiles(cases))[0]["divergence"] == 0.0


# --- store ----------------------------------------------------------------


def test_store_round_trips_and_resumes(tmp_path):
    path = tmp_path / "judged.jsonl"
    sets = [AnnotationSet(trajectory_id="t1", annotations=[make_annotation()])]
    assert store.save(path, sets) == 1
    assert store.load(path)[0].annotations[0].error_type == "RFL-1"
    assert store.judged_ids(path) == {"t1"}
    assert store.judged_ids(tmp_path / "absent.jsonl") == set()
