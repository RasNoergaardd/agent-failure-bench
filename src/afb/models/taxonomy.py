"""Failure taxonomy registry and label model (specs 001 R6, 002 R3).

The registry below is the machine-readable single source of truth for taxonomy
codes; tests/test_taxonomy_sync.py enforces that it matches the codes documented
in research/taxonomy-v0.md.
"""

from enum import Enum

from pydantic import BaseModel, model_validator


class CognitiveFunction(str, Enum):
    MEMORY = "memory"
    REFLECTION = "reflection"
    PLANNING = "planning"
    ACTION = "action"
    SYSTEM = "system"


#: Escape-hatch code for failures no existing category fits (taxonomy v0, "Escape hatch").
#: Annotations using it must carry a proposed_category description.
ESCAPE_HATCH = "NEW-?"

TAXONOMY_VERSION = "v0"

#: code -> (cognitive function, short name)
TAXONOMY_REGISTRY: dict[str, tuple[CognitiveFunction, str]] = {
    "MEM-1": (CognitiveFunction.MEMORY, "Context loss"),
    "MEM-2": (CognitiveFunction.MEMORY, "Recall fabrication"),
    "MEM-3": (CognitiveFunction.MEMORY, "Instruction drift"),
    "RFL-1": (CognitiveFunction.REFLECTION, "Output misinterpretation"),
    "RFL-2": (CognitiveFunction.REFLECTION, "Progress misjudgment"),
    "RFL-3": (CognitiveFunction.REFLECTION, "Verification omission"),
    "RFL-4": (CognitiveFunction.REFLECTION, "Causal misattribution"),
    "RFL-5": (CognitiveFunction.REFLECTION, "Evaluation fabrication"),
    "PLN-1": (CognitiveFunction.PLANNING, "Task misunderstanding"),
    "PLN-2": (CognitiveFunction.PLANNING, "Constraint ignorance"),
    "PLN-3": (CognitiveFunction.PLANNING, "Redundant looping"),
    "PLN-4": (CognitiveFunction.PLANNING, "Goal deviation"),
    "PLN-5": (CognitiveFunction.PLANNING, "Infeasible strategy"),
    "ACT-1": (CognitiveFunction.ACTION, "Command construction error"),
    "ACT-2": (CognitiveFunction.ACTION, "Wrong command/tool selection"),
    "ACT-3": (CognitiveFunction.ACTION, "Parameter error"),
    "ACT-4": (CognitiveFunction.ACTION, "Plan-action mismatch"),
    "ACT-5": (CognitiveFunction.ACTION, "Artifact format error"),
    "ACT-6": (CognitiveFunction.ACTION, "Destructive action"),
    "SYS-1": (CognitiveFunction.SYSTEM, "Budget exhaustion"),
    "SYS-2": (CognitiveFunction.SYSTEM, "Timeout"),
    "SYS-3": (CognitiveFunction.SYSTEM, "Environment defect"),
    "SYS-4": (CognitiveFunction.SYSTEM, "Model/API failure"),
    "SYS-5": (CognitiveFunction.SYSTEM, "Resource exhaustion"),
}


def error_types_for(function: CognitiveFunction) -> dict[str, str]:
    """Codes and names available under one cognitive function (drives the annotation UI)."""
    return {
        code: name
        for code, (fn, name) in TAXONOMY_REGISTRY.items()
        if fn is function
    }


class TaxonomyLabel(BaseModel):
    cognitive_function: CognitiveFunction
    error_type: str
    taxonomy_version: str = TAXONOMY_VERSION

    @model_validator(mode="after")
    def _check_code(self) -> "TaxonomyLabel":
        if self.error_type == ESCAPE_HATCH:
            return self
        entry = TAXONOMY_REGISTRY.get(self.error_type)
        if entry is None:
            raise ValueError(
                f"unknown error_type {self.error_type!r}; must be a registry code or {ESCAPE_HATCH!r}"
            )
        expected_fn, _ = entry
        if self.cognitive_function is not expected_fn:
            raise ValueError(
                f"error_type {self.error_type} belongs to {expected_fn.value}, "
                f"not {self.cognitive_function.value}"
            )
        return self
