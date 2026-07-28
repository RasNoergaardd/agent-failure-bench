"""Taxonomy coverage: the evidence that drives the next taxonomy version.

Subquestion 1 does not end with the merged taxonomy. Labelled runs revise it:
the escape-hatch label surfaces failure modes v0 has no code for, and codes that
never fire across a corpus are candidates for removal. This module turns a set of
judged trajectories into that evidence, so a revision cites data rather than
opinion, as `constitution.md` requires.

It reports; it never edits a taxonomy file.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from afb import taxonomy
from afb.annotation import AnnotationSet

MIN_PROPOSALS_FOR_ADDITION = 3
"""Below this, a proposed category is an anecdote rather than evidence."""


@dataclass(slots=True)
class Coverage:
    """How a corpus of annotations exercised the taxonomy."""

    version: str
    annotations: int = 0
    trajectories: int = 0
    by_code: Counter = field(default_factory=Counter)
    by_function: Counter = field(default_factory=Counter)
    proposals: Counter = field(default_factory=Counter)
    """Escape-hatch texts, normalized, with how often each was proposed."""

    @property
    def escape_hatch_count(self) -> int:
        return self.by_code.get(taxonomy.escape_hatch_code(self.version), 0)

    @property
    def escape_hatch_rate(self) -> float:
        return self.escape_hatch_count / self.annotations if self.annotations else 0.0

    def unused_codes(self) -> list[str]:
        """Codes no annotation used. Removal candidates for the next version."""
        return [code for code in taxonomy.error_types(self.version) if not self.by_code.get(code)]

    def rare_codes(self, threshold: int = 2) -> list[tuple[str, int]]:
        """Codes used at or below `threshold` times, worth inspecting by hand."""
        return sorted(
            ((code, self.by_code[code]) for code in taxonomy.error_types(self.version)
             if 0 < self.by_code[code] <= threshold),
            key=lambda item: item[1],
        )

    def addition_candidates(self, minimum: int = MIN_PROPOSALS_FOR_ADDITION) -> list[tuple[str, int]]:
        """Escape-hatch proposals frequent enough to justify a new category."""
        return [(text, n) for text, n in self.proposals.most_common() if n >= minimum]

    def summary(self) -> dict[str, object]:
        return {
            "taxonomy_version": self.version,
            "trajectories": self.trajectories,
            "annotations": self.annotations,
            "codes_used": sum(1 for code in taxonomy.error_types(self.version) if self.by_code[code]),
            "codes_total": len(taxonomy.error_types(self.version)),
            "unused_codes": self.unused_codes(),
            "escape_hatch_count": self.escape_hatch_count,
            "escape_hatch_rate": round(self.escape_hatch_rate, 3),
            "distinct_proposals": len(self.proposals),
            "addition_candidates": self.addition_candidates(),
        }


def _normalize_proposal(text: str) -> str:
    """Collapse proposals so wording differences do not hide a repeated finding."""
    return re.sub(r"[^a-z0-9 ]+", "", re.sub(r"\s+", " ", text).strip().casefold())


def analyse(
    sets: list[AnnotationSet], version: str = taxonomy.DEFAULT_VERSION
) -> Coverage:
    """Summarize how a corpus of judged trajectories used the taxonomy."""
    result = Coverage(version=version)
    escape_hatch = taxonomy.escape_hatch_code(version)

    for annotation_set in sets:
        result.trajectories += 1
        for annotation in annotation_set.annotations:
            result.annotations += 1
            result.by_code[annotation.error_type] += 1
            result.by_function[annotation.cognitive_function] += 1
            if annotation.error_type == escape_hatch and annotation.proposed_category:
                result.proposals[_normalize_proposal(annotation.proposed_category)] += 1

    return result


def revision_report(coverage: Coverage) -> str:
    """A human-readable case for or against revising the taxonomy."""
    lines = [
        f"# Taxonomy coverage, version {coverage.version}",
        "",
        f"{coverage.annotations} annotations over {coverage.trajectories} trajectories.",
        "",
        "## Usage by code",
        "",
    ]
    for code, entry in taxonomy.error_types(coverage.version).items():
        count = coverage.by_code.get(code, 0)
        marker = "  <- unused" if count == 0 else ""
        lines.append(f"  {code:8} {count:5}  {entry['name']}{marker}")

    lines += ["", "## Escape hatch", ""]
    lines.append(
        f"  {coverage.escape_hatch_count} of {coverage.annotations} annotations "
        f"({coverage.escape_hatch_rate:.1%}) found no fitting category."
    )
    if candidates := coverage.addition_candidates():
        lines += ["", "  Proposed categories with enough support to consider adding:"]
        lines += [f"    {n:4}  {text}" for text, n in candidates]
    elif coverage.proposals:
        lines.append(
            f"  {len(coverage.proposals)} distinct proposals, none reaching "
            f"{MIN_PROPOSALS_FOR_ADDITION} occurrences."
        )

    if unused := coverage.unused_codes():
        lines += ["", "## Removal candidates", "", f"  never used: {', '.join(unused)}"]
    if rare := coverage.rare_codes():
        lines.append(f"  rarely used: {', '.join(f'{c} ({n})' for c, n in rare)}")

    return "\n".join(lines)
