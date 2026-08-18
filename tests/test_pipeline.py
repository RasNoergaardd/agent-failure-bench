"""Tests for the pipeline that do not need the network or the gated dataset.

TRAIL ingest is exercised separately in `test_trail.py`, which skips when the
dataset is not present locally.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from afb import agreement, cli, coverage, harbor, judge, mapping, prompt, runs, store, taxonomy
from afb.annotation import Annotation, AnnotationSet, Provenance
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


def test_function_baselines_are_the_numbers_accuracy_must_beat():
    """Runs A and B scored below uniform chance, which is a different claim from
    scoring poorly. The baselines have to appear next to the accuracy to say so."""
    cases = [
        build_case([("Context Handling Failure", 1, "HIGH")], [("RFL-3", "reflection", 1, "high")]),
        build_case([("Context Handling Failure", 2, "HIGH")], [("RFL-3", "reflection", 2, "high")]),
        build_case([("Goal Deviation", 3, "HIGH")], [("RFL-3", "reflection", 3, "high")]),
    ]
    report = agreement.score(cases)
    chance, majority = report.baselines("function")
    assert chance == pytest.approx(0.2)  # five cognitive functions
    # Experts said memory twice and planning once, so always answering "memory"
    # would score 2/3. The judge said reflection every time and scored 0.
    assert majority == pytest.approx(2 / 3)
    assert report.classification("function")[2] == 0.0
    assert report.summary()["function_beats_chance"] is False


def test_baselines_survive_an_empty_report():
    report = agreement.score([])
    assert report.baselines("function") == (0.2, 0.0)
    assert report.baselines("code")[0] == pytest.approx(1 / 24)


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


FIXTURE = Path(__file__).parent / "fixtures" / "harbor-trial"
"""A real Harbor trial layout.

`agent/trajectory.json` was produced by Harbor's own ATIF models (harbor 0.18.0)
so the schema is authoritative rather than assumed; `result.json` is a real
`harbor run` output with its verdict and agent identity edited to describe a
failing terminus-2 run.
"""


def write_trial(root: Path, *, result: dict, atif: dict | None) -> Path:
    """A trial directory in Harbor's layout: result.json plus agent/trajectory.json."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "result.json").write_text(json.dumps(result), encoding="utf-8")
    if atif is not None:
        (root / "agent").mkdir(exist_ok=True)
        (root / "agent" / "trajectory.json").write_text(json.dumps(atif), encoding="utf-8")
    return root


def atif_document(**overrides) -> dict:
    base = {
        "schema_version": "ATIF-v1.7",
        "agent": {"name": "terminus-2", "version": "2.0.0"},
        "steps": [
            {"step_id": 1, "source": "user", "message": "Fix the port."},
            {
                "step_id": 2,
                "source": "agent",
                "message": "Checking the config.",
                "tool_calls": [
                    {"tool_call_id": "c1", "function_name": "run_command",
                     "arguments": {"command": "grep port app.conf"}}
                ],
                "observation": {"results": [{"source_call_id": "c1", "content": "port: 8081"}]},
            },
        ],
    }
    return base | overrides


def test_harbor_reads_a_real_atif_trial():
    """The fixture is Harbor's own schema output, so this pins the real format."""
    trajectories = harbor.load_dir(FIXTURE)
    assert len(trajectories) == 1
    trajectory = trajectories[0]

    assert trajectory.trajectory_id == "terminal-bench/build-wheel::build-wheel__attempt1"
    assert trajectory.outcome is Outcome.FAILURE
    assert trajectory.task_instruction.startswith("Build a wheel")
    assert trajectory.metadata["agent"] == "terminus-2"
    assert trajectory.metadata["model"] == "Qwen/Qwen3-32B-AWQ"

    kinds = [e.kind.value for e in trajectory.events]
    assert kinds.count("action") == 3
    assert [e.index for e in trajectory.events] == list(range(len(trajectory.events)))
    assert any(e.content == "cd /app && python -m build --wheel" for e in trajectory.events)


def test_harbor_splits_one_step_into_message_command_and_output(tmp_path):
    """A single ATIF step becomes several events — how a terminal run reads."""
    trial = write_trial(tmp_path / "t", result={"task_name": "x", "trial_name": "1"},
                        atif=atif_document())
    events = harbor.load_dir(trial)[0].events
    assert [e.kind.value for e in events] == [
        "observation",  # the user step carrying the instruction
        "agent",
        "action",
        "observation",
    ]
    assert events[2].content == "grep port app.conf"


def test_harbor_keeps_reasoning_as_a_labelled_event(tmp_path):
    """A reflection failure cannot be judged without what the agent believed."""
    atif = atif_document()
    atif["steps"][1]["reasoning_content"] = "The port is probably wrong."
    trial = write_trial(tmp_path / "t", result={"task_name": "x", "trial_name": "1"}, atif=atif)
    contents = [e.content for e in harbor.load_dir(trial)[0].events]
    assert "[reasoning] The port is probably wrong." in contents


def test_harbor_skips_a_trial_with_no_trajectory(tmp_path):
    """`oracle` and `nop` produce no ATIF file; a job must not fail on them."""
    write_trial(tmp_path / "oracle-trial", result={"task_name": "x"}, atif=None)
    assert harbor.load_dir(tmp_path) == []
    assert harbor.read_trial(tmp_path / "oracle-trial") is None


def test_harbor_reads_a_whole_job_directory(tmp_path):
    for n in range(3):
        write_trial(tmp_path / "job" / f"trial-{n}",
                    result={"task_name": "task", "trial_name": str(n)}, atif=atif_document())
    trajectories = harbor.load_dir(tmp_path)
    assert len(trajectories) == 3
    assert [t.metadata["run_id"] for t in trajectories] == ["0", "1", "2"]


@pytest.mark.parametrize(
    "result,expected",
    [
        ({"verifier_result": {"rewards": {"reward": 1.0}}}, Outcome.SUCCESS),
        ({"verifier_result": {"rewards": {"reward": 0.0}}}, Outcome.FAILURE),
        ({"verifier_result": {"rewards": {}}}, Outcome.UNKNOWN),
        ({}, Outcome.UNKNOWN),
        # A crashed trial is not the agent failing the task.
        ({"verifier_result": {"rewards": {"reward": 0.0}},
          "exception_info": {"type": "Timeout"}}, Outcome.UNKNOWN),
    ],
)
def test_harbor_reads_the_verifier_verdict(tmp_path, result, expected):
    trial = write_trial(tmp_path / "t", result={"task_name": "x", **result}, atif=atif_document())
    assert harbor.load_dir(trial)[0].outcome is expected


def test_harbor_warns_on_an_unknown_atif_version(tmp_path):
    """The format has only added optional fields so far: warn, do not drop."""
    trial = write_trial(tmp_path / "t", result={"task_name": "x"},
                        atif=atif_document(schema_version="ATIF-v9.9"))
    with pytest.warns(UserWarning, match="unrecognized ATIF version"):
        trajectories = harbor.load_dir(trial)
    assert len(trajectories) == 1


def test_harbor_renders_a_multi_argument_tool_call(tmp_path):
    """No argument may be silently dropped: the judge annotates what it reads."""
    atif = atif_document()
    atif["steps"][1]["tool_calls"] = [
        {"tool_call_id": "c1", "function_name": "run_command",
         "arguments": {"command": "pytest", "timeout": 30}}
    ]
    trial = write_trial(tmp_path / "t", result={"task_name": "x"}, atif=atif)
    action = next(e for e in harbor.load_dir(trial)[0].events if e.kind.value == "action")
    assert action.content.startswith("pytest")
    assert "timeout" in action.content


def test_harbor_names_an_omitted_image(tmp_path):
    """An elision is always visible, so no error is inferred from removed content."""
    atif = atif_document()
    atif["steps"][1]["message"] = [
        {"type": "text", "text": "Here is the screen."},
        {"type": "image", "source": {"media_type": "image/png", "path": "s.png"}},
    ]
    trial = write_trial(tmp_path / "t", result={"task_name": "x"}, atif=atif)
    contents = "\n".join(e.content for e in harbor.load_dir(trial)[0].events)
    assert "[image omitted: image/png]" in contents


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


def test_labels_without_provenance_still_load(tmp_path):
    """Runs A and B were written before the annotator was recorded."""
    path = tmp_path / "legacy.jsonl"
    path.write_text(
        json.dumps(
            {
                "trajectory_id": "t1",
                "annotations": [json.loads(make_annotation().model_dump_json())],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert store.load(path)[0].provenance is None
    assert store.judge_models(path) == {None}


def test_judge_models_names_each_annotator(tmp_path):
    path = tmp_path / "judged.jsonl"
    store.save(
        path,
        [
            AnnotationSet(
                trajectory_id=f"t{n}",
                annotations=[make_annotation(trajectory_id=f"t{n}")],
                provenance=Provenance(judge_model=model),
            )
            for n, model in enumerate(("Qwen/Qwen3-14B-AWQ", "Qwen/Qwen3-32B-AWQ"))
        ],
    )
    assert store.judge_models(path) == {"Qwen/Qwen3-14B-AWQ", "Qwen/Qwen3-32B-AWQ"}


# --- provenance -----------------------------------------------------------


def test_judge_records_its_annotator():
    """Principle 6: a stored label always names the model that produced it."""
    trajectory = make_trajectory()
    good = json.dumps({"annotations": [json.loads(make_annotation().model_dump_json())]})
    config = judge.JudgeConfig(model="Qwen/Qwen3-32B-AWQ", char_budget=50_000)

    result = judge.judge(trajectory, config, complete=lambda c, m: judge.Completion(good, "stop"))
    assert result.provenance is not None
    assert result.provenance.judge_model == "Qwen/Qwen3-32B-AWQ"
    assert result.provenance.char_budget == 50_000
    assert result.provenance.guidelines_digest == prompt.guidelines_digest()
    assert result.provenance.attempts_used == 1
    assert result.provenance.finish_reasons == ["stop"]
    assert not result.provenance.repaired and not result.provenance.truncated


def test_provenance_exposes_a_truncated_first_attempt():
    """A response cut off mid-JSON is repaired into a smaller set, which records
    as a success. `truncated` is what makes that visible afterwards."""
    trajectory = make_trajectory()
    good = json.dumps({"annotations": [json.loads(make_annotation().model_dump_json())]})
    replies = iter(
        [judge.Completion('{"annotations": [{"id": "a1"', "length"), judge.Completion(good, "stop")]
    )

    result = judge.judge(trajectory, judge.JudgeConfig(attempts=2), complete=lambda c, m: next(replies))
    assert result.provenance.attempts_used == 2
    assert result.provenance.finish_reasons == ["length", "stop"]
    assert result.provenance.repaired and result.provenance.truncated


def test_complete_may_return_a_bare_string():
    """The injection point predates `Completion`; a stub need not care why the
    model stopped."""
    trajectory = make_trajectory()
    good = json.dumps({"annotations": [json.loads(make_annotation().model_dump_json())]})
    result = judge.judge(trajectory, complete=lambda c, m: good)
    assert result.provenance.finish_reasons == [None]


def test_extra_body_carries_the_reasoning_switch(monkeypatch):
    monkeypatch.setenv(
        "AFB_JUDGE_EXTRA_BODY", '{"chat_template_kwargs": {"enable_thinking": false}}'
    )
    assert judge.JudgeConfig().extra_body == {"chat_template_kwargs": {"enable_thinking": False}}


def test_explicit_extra_body_wins_over_the_environment(monkeypatch):
    monkeypatch.setenv("AFB_JUDGE_EXTRA_BODY", '{"chat_template_kwargs": {}}')
    config = judge.JudgeConfig(extra_body={"reasoning": {"effort": "high"}})
    assert config.extra_body == {"reasoning": {"effort": "high"}}


def test_unusable_extra_body_fails_before_any_inference(monkeypatch):
    """A silently dropped reasoning switch means a ladder rung that did not
    actually change, which is worse than one that refused to start."""
    monkeypatch.setenv("AFB_JUDGE_EXTRA_BODY", "enable_thinking=false")
    with pytest.raises(judge.JudgeError, match="not valid JSON"):
        judge.JudgeConfig()
    monkeypatch.setenv("AFB_JUDGE_EXTRA_BODY", '["thinking"]')
    with pytest.raises(judge.JudgeError, match="must be a JSON object"):
        judge.JudgeConfig()


# --- output guard ---------------------------------------------------------


def test_output_guard_refuses_to_mix_two_judges(tmp_path, capsys):
    path = tmp_path / "judged.jsonl"
    store.save(
        path,
        [
            AnnotationSet(
                trajectory_id="t1",
                annotations=[make_annotation()],
                provenance=Provenance(judge_model="Qwen/Qwen3-14B-AWQ"),
            )
        ],
    )
    assert cli._output_guard(path, "Qwen/Qwen3-14B-AWQ", resume=True) == 0
    assert cli._output_guard(path, "Qwen/Qwen3-32B-AWQ", resume=True) == 1
    assert "not Qwen/Qwen3-32B-AWQ" in capsys.readouterr().err


def test_output_guard_blocks_a_no_resume_append(tmp_path):
    path = tmp_path / "judged.jsonl"
    store.save(path, [AnnotationSet(trajectory_id="t1", annotations=[make_annotation()])])
    assert cli._output_guard(path, "any-model", resume=False) == 1
    assert cli._output_guard(tmp_path / "absent.jsonl", "any-model", resume=False) == 0


def test_output_guard_warns_when_the_annotator_is_unrecorded(tmp_path, capsys):
    path = tmp_path / "legacy.jsonl"
    store.save(path, [AnnotationSet(trajectory_id="t1", annotations=[make_annotation()])])
    assert cli._output_guard(path, "Qwen/Qwen3-14B-AWQ", resume=True) == 0
    assert "no recorded annotator" in capsys.readouterr().err


@pytest.mark.parametrize(
    "model,slug",
    [
        ("Qwen/Qwen3-14B-AWQ", "qwen3-14b-awq"),
        ("meta-llama/Llama-3.3-70B-Instruct-AWQ", "llama-3.3-70b-instruct-awq"),
        ("anthropic/claude-sonnet-4.5", "claude-sonnet-4.5"),
    ],
)
def test_model_slug_keeps_rungs_in_separate_files(model, slug):
    assert cli._model_slug(model) == slug
