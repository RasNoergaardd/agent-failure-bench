"""Analysis over repeated Terminal-Bench runs.

Two subquestions are answered here, both of which need the *same* task run more
than once:

- whether variation across repeated runs separates systematic failures from
  stochastic ones (subquestion 3), and
- whether failure profiles differ across agents on the same tasks
  (subquestion 4).

A single run cannot distinguish a failure the agent will always make from one it
made once. Repetition is what makes that difference observable, so everything
here is keyed by (agent, task) and counts how often a failure recurs.
"""

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from afb.annotation import AnnotationSet
from afb.trajectory import Outcome, Trajectory

SYSTEMATIC_THRESHOLD = 0.8
"""A failure recurring in at least this share of runs is treated as systematic."""

Case = tuple[Trajectory, AnnotationSet]


@dataclass(slots=True)
class TaskVariance:
    """How one agent behaved over repeated runs of one task."""

    agent: str
    task_id: str
    runs: int = 0
    successes: int = 0
    runs_with_code: Counter = field(default_factory=Counter)
    """Runs in which each error code appeared at least once."""

    @property
    def success_rate(self) -> float:
        return self.successes / self.runs if self.runs else 0.0

    @property
    def outcome_is_stable(self) -> bool:
        """True when every run agreed, so the outcome itself is not stochastic."""
        return self.successes in (0, self.runs)

    def rate(self, code: str) -> float:
        return self.runs_with_code[code] / self.runs if self.runs else 0.0

    def systematic(self, threshold: float = SYSTEMATIC_THRESHOLD) -> list[tuple[str, float]]:
        """Codes recurring in most runs: properties of the agent on this task."""
        return sorted(
            ((code, self.rate(code)) for code in self.runs_with_code if self.rate(code) >= threshold),
            key=lambda item: -item[1],
        )

    def stochastic(self, threshold: float = SYSTEMATIC_THRESHOLD) -> list[tuple[str, float]]:
        """Codes appearing in some runs but not most: sampling artefacts."""
        return sorted(
            ((code, self.rate(code)) for code in self.runs_with_code if 0 < self.rate(code) < threshold),
            key=lambda item: -item[1],
        )

    def summary(self, threshold: float = SYSTEMATIC_THRESHOLD) -> dict[str, object]:
        return {
            "agent": self.agent,
            "task_id": self.task_id,
            "runs": self.runs,
            "success_rate": round(self.success_rate, 3),
            "outcome_stable": self.outcome_is_stable,
            "systematic": self.systematic(threshold),
            "stochastic": self.stochastic(threshold),
        }


def _key(trajectory: Trajectory) -> tuple[str, str]:
    metadata = trajectory.metadata
    return (
        str(metadata.get("agent") or "unknown-agent"),
        str(metadata.get("task_id") or trajectory.trajectory_id),
    )


def variance(cases: list[Case], threshold: float = SYSTEMATIC_THRESHOLD) -> list[TaskVariance]:
    """Group runs by agent and task, then measure recurrence of each error code.

    A code is counted once per run however often it was annotated, so a retry
    loop annotated five times does not masquerade as five failures.
    """
    grouped: dict[tuple[str, str], TaskVariance] = {}

    for trajectory, annotations in cases:
        agent, task_id = _key(trajectory)
        entry = grouped.setdefault((agent, task_id), TaskVariance(agent=agent, task_id=task_id))
        entry.runs += 1
        entry.successes += trajectory.outcome is Outcome.SUCCESS
        for code in {annotation.error_type for annotation in annotations.annotations}:
            entry.runs_with_code[code] += 1

    return sorted(grouped.values(), key=lambda item: (item.agent, item.task_id))


def variance_summary(
    entries: list[TaskVariance], threshold: float = SYSTEMATIC_THRESHOLD
) -> dict[str, object]:
    """Aggregate the systematic versus stochastic split across all tasks."""
    repeated = [entry for entry in entries if entry.runs > 1]
    systematic = sum(len(entry.systematic(threshold)) for entry in repeated)
    stochastic = sum(len(entry.stochastic(threshold)) for entry in repeated)
    total = systematic + stochastic
    return {
        "tasks": len(entries),
        "tasks_with_repeats": len(repeated),
        "tasks_with_unstable_outcome": sum(not entry.outcome_is_stable for entry in repeated),
        "systematic_findings": systematic,
        "stochastic_findings": stochastic,
        "systematic_share": round(systematic / total, 3) if total else 0.0,
        "threshold": threshold,
    }


@dataclass(slots=True)
class AgentProfile:
    """One agent's failure distribution, for comparison against another's."""

    agent: str
    runs: int = 0
    successes: int = 0
    by_function: Counter = field(default_factory=Counter)
    by_code: Counter = field(default_factory=Counter)
    tasks: set[str] = field(default_factory=set)

    @property
    def success_rate(self) -> float:
        return self.successes / self.runs if self.runs else 0.0

    def distribution(self, level: str = "function") -> dict[str, float]:
        """Normalized profile, so agents with different run counts compare."""
        counts = self.by_function if level == "function" else self.by_code
        total = sum(counts.values())
        return {str(key): value / total for key, value in counts.items()} if total else {}

    def summary(self) -> dict[str, object]:
        return {
            "agent": self.agent,
            "runs": self.runs,
            "tasks": len(self.tasks),
            "success_rate": round(self.success_rate, 3),
            "annotations": sum(self.by_code.values()),
            "profile": {k: round(v, 3) for k, v in sorted(self.distribution().items())},
        }


def profiles(cases: list[Case]) -> list[AgentProfile]:
    """One profile per agent, over whatever tasks that agent ran."""
    grouped: dict[str, AgentProfile] = defaultdict(lambda: AgentProfile(agent=""))

    for trajectory, annotations in cases:
        agent, task_id = _key(trajectory)
        entry = grouped[agent]
        entry.agent = agent
        entry.runs += 1
        entry.successes += trajectory.outcome is Outcome.SUCCESS
        entry.tasks.add(task_id)
        for annotation in annotations.annotations:
            entry.by_function[annotation.cognitive_function] += 1
            entry.by_code[annotation.error_type] += 1

    return sorted(grouped.values(), key=lambda item: item.agent)


def divergence(left: dict[str, float], right: dict[str, float]) -> float:
    """Jensen-Shannon divergence in bits, 0 identical and 1 disjoint.

    Symmetric and defined when one profile uses a category the other never does,
    which plain KL divergence is not.
    """
    keys = set(left) | set(right)
    if not keys:
        return 0.0

    def entropy_term(p: float, m: float) -> float:
        return p * math.log2(p / m) if p > 0 and m > 0 else 0.0

    total = 0.0
    for key in keys:
        p, q = left.get(key, 0.0), right.get(key, 0.0)
        m = (p + q) / 2
        total += 0.5 * entropy_term(p, m) + 0.5 * entropy_term(q, m)
    return max(0.0, min(1.0, total))


def compare(entries: list[AgentProfile], level: str = "function") -> list[dict[str, object]]:
    """Pairwise distance between agent profiles, most different first."""
    results = []
    for i, left in enumerate(entries):
        for right in entries[i + 1 :]:
            results.append(
                {
                    "agents": (left.agent, right.agent),
                    "level": level,
                    "divergence": round(
                        divergence(left.distribution(level), right.distribution(level)), 3
                    ),
                    "shared_tasks": len(left.tasks & right.tasks),
                }
            )
    return sorted(results, key=lambda item: -item["divergence"])
