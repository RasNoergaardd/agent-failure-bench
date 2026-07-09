"""Spec 001 R6: the code registry and research/taxonomy-v0.md must not diverge."""

import re
from pathlib import Path

from afb.models import TAXONOMY_REGISTRY, TAXONOMY_VERSION, error_types_for, CognitiveFunction

TAXONOMY_DOC = Path(__file__).parent.parent / "research" / f"taxonomy-{TAXONOMY_VERSION}.md"


def doc_codes() -> set[str]:
    text = TAXONOMY_DOC.read_text()
    return set(re.findall(r"^### ([A-Z]{3}-\d+)\b", text, flags=re.MULTILINE))


def test_registry_matches_document():
    assert doc_codes() == set(TAXONOMY_REGISTRY), (
        "taxonomy registry (afb.models.taxonomy) and research/taxonomy doc are out of sync"
    )


def test_code_prefixes_match_functions():
    prefix_to_fn = {
        "MEM": CognitiveFunction.MEMORY,
        "RFL": CognitiveFunction.REFLECTION,
        "PLN": CognitiveFunction.PLANNING,
        "ACT": CognitiveFunction.ACTION,
        "SYS": CognitiveFunction.SYSTEM,
    }
    for code, (fn, _name) in TAXONOMY_REGISTRY.items():
        assert prefix_to_fn[code[:3]] is fn, f"{code} mapped to {fn}"


def test_every_function_has_error_types():
    for fn in CognitiveFunction:
        assert error_types_for(fn), f"no error types under {fn.value}"
