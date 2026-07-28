"""Translation of TRAIL's expert categories into this project's taxonomy.

The judge labels with taxonomy v0 while TRAIL's experts labelled with TRAIL's own
categories, so the agreement study of subquestion 2 needs an explicit bridge.
The bridge is data (`afb/data/trail-mapping-v*.yaml`) and its rationale is
`research/trail-mapping.md`; this module only applies it.

Category strings in the published data are not a controlled vocabulary. They
carry case variants, singular and plural forms, stray whitespace and typos, so
they are normalized before lookup.
"""

import difflib
import re
from enum import StrEnum
from functools import lru_cache
from importlib import resources
from typing import Any, NamedTuple

import yaml

from afb import taxonomy

DEFAULT_VERSION = "v0"
FUZZY_CUTOFF = 0.88
"""Close-match threshold for typos such as `Instruction non complience`."""


class Status(StrEnum):
    MAPPED = "mapped"
    """Corresponds to exactly one taxonomy code."""

    AMBIGUOUS = "ambiguous"
    """Spans several codes; only the cognitive function is decidable."""

    OUT_OF_SCOPE = "out_of_scope"
    """Deliberately excluded from the taxonomy, so it cannot be scored."""

    UNKNOWN = "unknown"
    """Not in the mapping at all. Counted and reported, never silently dropped."""


class Mapped(NamedTuple):
    """The result of translating one TRAIL category."""

    status: Status
    error_type: str | None
    cognitive_function: str | None
    candidates: tuple[str, ...]
    trail_category: str
    """The canonical TRAIL category the raw string was resolved to."""


def normalize(category: str) -> str:
    """Casefold, collapse whitespace and drop a trailing plural."""
    text = re.sub(r"\s+", " ", category).strip().casefold()
    return text[:-1] if text.endswith("s") else text


@lru_cache
def _table(version: str) -> dict[str, Any]:
    path = resources.files("afb") / "data" / f"trail-mapping-{version}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@lru_cache
def _index(version: str) -> dict[str, dict[str, Any]]:
    """Every spelling of a category, normalized, pointing at its entry."""
    index: dict[str, dict[str, Any]] = {}
    for entry in _table(version)["categories"]:
        for name in [entry["trail"], *entry.get("aliases", [])]:
            index[normalize(name)] = entry
    return index


def categories(version: str = DEFAULT_VERSION) -> list[dict[str, Any]]:
    """The mapping entries, as written in the data file."""
    return _table(version)["categories"]


def map_category(category: str, version: str = DEFAULT_VERSION) -> Mapped:
    """Translate one TRAIL category string into taxonomy terms."""
    index = _index(version)
    key = normalize(category)
    entry = index.get(key)

    if entry is None:
        if close := difflib.get_close_matches(key, index, n=1, cutoff=FUZZY_CUTOFF):
            entry = index[close[0]]
        else:
            return Mapped(Status.UNKNOWN, None, None, (), category)

    status = Status(entry["status"])
    if status is Status.MAPPED:
        code = entry["error_type"]
        function_code = taxonomy.error_types(entry_version := _table(version)["taxonomy_version"])[code]["function"]
        function = taxonomy.cognitive_functions(entry_version)[function_code]
        return Mapped(status, code, function, (code,), entry["trail"])

    return Mapped(
        status,
        None,
        entry.get("function"),
        tuple(entry.get("candidates", ())),
        entry["trail"],
    )


def coverage_report(version: str = DEFAULT_VERSION) -> dict[str, int]:
    """How many TRAIL categories are scoreable, by status."""
    counts = {status.value: 0 for status in Status if status is not Status.UNKNOWN}
    for entry in categories(version):
        counts[entry["status"]] += 1
    return counts
