"""Judge validity: agreement with TRAIL's expert annotations.

This answers subquestion 2, and it runs before the judge's labels are used
anywhere else. Agreement is measured at two levels, because the mapping in
`research/trail-mapping.md` only determines an error code for some of TRAIL's
categories and only a cognitive function for others.

An expert error and a judge annotation are treated as the same finding when they
are located at the same event. Location is the one thing both label sets express
in the same units, once TRAIL's span ids are resolved to event indices by the
ingest.
"""

from collections import Counter
from dataclasses import dataclass, field

from afb import mapping
from afb.annotation import Annotation, AnnotationSet
from afb.mapping import Status
from afb.trail import TrailLabels
from afb.trajectory import Trajectory


@dataclass(slots=True)
class Pair:
    """One expert error matched to one judge annotation."""

    trajectory_id: str
    event_index: int
    expert_category: str
    expert_impact: str
    judge: Annotation
    mapped: mapping.Mapped

    @property
    def function_agrees(self) -> bool | None:
        """Whether the cognitive functions agree, or None if undecidable."""
        if self.mapped.cognitive_function is None:
            return None
        return self.judge.cognitive_function == self.mapped.cognitive_function

    @property
    def code_agrees(self) -> bool | None:
        """Whether the error codes agree, or None if the mapping is not one to one."""
        if self.mapped.status is not Status.MAPPED:
            return None
        return self.judge.error_type == self.mapped.error_type

    @property
    def severity_agrees(self) -> bool:
        return self.judge.severity == self.expert_impact.strip().lower()


@dataclass(slots=True)
class Agreement:
    """Accumulated agreement over any number of trajectories."""

    label: str = ""
    trajectories: int = 0
    expert_errors: int = 0
    out_of_scope: int = 0
    """Expert errors whose category the taxonomy deliberately excludes."""

    judge_annotations: int = 0
    judge_escape_hatch: int = 0
    pairs: list[Pair] = field(default_factory=list)
    unmatched_expert: int = 0
    unmatched_judge: int = 0

    @property
    def scoreable_expert_errors(self) -> int:
        """Expert errors a judge running this taxonomy could in principle produce."""
        return self.expert_errors - self.out_of_scope

    @property
    def precision(self) -> float:
        """Of the judge's annotations, the share that sit on a real expert error."""
        return _ratio(len(self.pairs), self.judge_annotations)

    @property
    def recall(self) -> float:
        """Of the scoreable expert errors, the share the judge located."""
        return _ratio(len(self.pairs), self.scoreable_expert_errors)

    @property
    def f1(self) -> float:
        total = self.precision + self.recall
        return 0.0 if total == 0 else 2 * self.precision * self.recall / total

    def classification(self, level: str) -> tuple[int, int, float]:
        """Agreeing pairs, decidable pairs, and the rate, for `function` or `code`."""
        decided = [
            value
            for pair in self.pairs
            if (value := (pair.function_agrees if level == "function" else pair.code_agrees))
            is not None
        ]
        return sum(decided), len(decided), _ratio(sum(decided), len(decided))

    def severity(self) -> tuple[int, int, float]:
        agreeing = sum(pair.severity_agrees for pair in self.pairs)
        return agreeing, len(self.pairs), _ratio(agreeing, len(self.pairs))

    def function_kappa(self) -> float:
        """Cohen's kappa on the cognitive-function axis, over decidable pairs.

        Accuracy alone flatters a judge when one function dominates, and in this
        taxonomy several do.
        """
        decided = [p for p in self.pairs if p.mapped.cognitive_function is not None]
        if not decided:
            return 0.0
        expert = Counter(p.mapped.cognitive_function for p in decided)
        judge = Counter(p.judge.cognitive_function for p in decided)
        n = len(decided)
        observed = _ratio(sum(p.function_agrees for p in decided), n)
        expected = sum(expert[k] * judge[k] for k in expert) / (n * n)
        return 0.0 if expected == 1 else (observed - expected) / (1 - expected)

    def confusion(self) -> Counter:
        """Expert function against judge function, for the report's error analysis."""
        return Counter(
            (p.mapped.cognitive_function, p.judge.cognitive_function)
            for p in self.pairs
            if p.mapped.cognitive_function is not None
        )

    def summary(self) -> dict[str, object]:
        function_hits, function_n, function_rate = self.classification("function")
        code_hits, code_n, code_rate = self.classification("code")
        severity_hits, severity_n, severity_rate = self.severity()
        return {
            "label": self.label,
            "trajectories": self.trajectories,
            "expert_errors": self.expert_errors,
            "out_of_scope": self.out_of_scope,
            "scoreable_expert_errors": self.scoreable_expert_errors,
            "judge_annotations": self.judge_annotations,
            "judge_escape_hatch": self.judge_escape_hatch,
            "matched": len(self.pairs),
            "unmatched_expert": self.unmatched_expert,
            "unmatched_judge": self.unmatched_judge,
            "localization_precision": round(self.precision, 3),
            "localization_recall": round(self.recall, 3),
            "localization_f1": round(self.f1, 3),
            "function_accuracy": round(function_rate, 3),
            "function_decidable": function_n,
            "function_kappa": round(self.function_kappa(), 3),
            "code_accuracy": round(code_rate, 3),
            "code_decidable": code_n,
            "severity_accuracy": round(severity_rate, 3),
            "severity_scored": severity_n,
        }


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def match(
    trajectory: Trajectory,
    expert: TrailLabels,
    judged: AnnotationSet,
    tolerance: int = 0,
    version: str = mapping.DEFAULT_VERSION,
) -> tuple[list[Pair], int, int]:
    """Pair expert errors with judge annotations by trajectory location.

    Greedy and one to one: an annotation is consumed by the first expert error it
    matches, so neither side can be counted twice. `tolerance` widens the window
    in events, for the case where judge and expert disagree about exactly where a
    distributed error manifests.
    """
    available = list(judged.annotations)
    pairs: list[Pair] = []
    unmatched_expert = 0

    for error in expert.errors:
        if error.event_index is None:
            unmatched_expert += 1
            continue
        mapped = mapping.map_category(error.category, version)
        if mapped.status is Status.OUT_OF_SCOPE:
            continue

        hit = next(
            (
                annotation
                for annotation in available
                if annotation.event_span[0] - tolerance
                <= error.event_index
                <= annotation.event_span[1] + tolerance
            ),
            None,
        )
        if hit is None:
            unmatched_expert += 1
            continue
        available.remove(hit)
        pairs.append(
            Pair(
                trajectory_id=trajectory.trajectory_id,
                event_index=error.event_index,
                expert_category=error.category,
                expert_impact=error.impact,
                judge=hit,
                mapped=mapped,
            )
        )

    return pairs, unmatched_expert, len(available)


def score(
    cases: list[tuple[Trajectory, TrailLabels, AnnotationSet]],
    label: str = "",
    tolerance: int = 0,
    version: str = mapping.DEFAULT_VERSION,
) -> Agreement:
    """Agreement over a set of judged trajectories."""
    result = Agreement(label=label)
    escape_hatch = mapping.taxonomy.escape_hatch_code()

    for trajectory, expert, judged in cases:
        pairs, unmatched_expert, unmatched_judge = match(
            trajectory, expert, judged, tolerance, version
        )
        result.trajectories += 1
        result.expert_errors += len(expert.errors)
        result.out_of_scope += sum(
            mapping.map_category(e.category, version).status is Status.OUT_OF_SCOPE
            for e in expert.errors
        )
        result.judge_annotations += len(judged.annotations)
        result.judge_escape_hatch += sum(
            a.error_type == escape_hatch for a in judged.annotations
        )
        result.pairs += pairs
        result.unmatched_expert += unmatched_expert
        result.unmatched_judge += unmatched_judge

    return result
