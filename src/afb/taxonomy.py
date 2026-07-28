"""Access to the machine-readable failure taxonomy.

The YAML files under `afb/data/` mirror `research/taxonomy-v*.md`, which stays
authoritative. Nothing here interprets the taxonomy; it only loads it so that
other modules validate against one source instead of restating the codes.
"""

from functools import lru_cache
from importlib import resources
from typing import Any

import yaml

DEFAULT_VERSION = "v0"


@lru_cache
def load(version: str = DEFAULT_VERSION) -> dict[str, Any]:
    """Return the parsed taxonomy of the given version.

    Cached, so the returned dict is shared: treat it as read-only.
    """
    path = resources.files("afb") / "data" / f"taxonomy-{version}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@lru_cache
def cognitive_functions(version: str = DEFAULT_VERSION) -> dict[str, str]:
    """Map function code to annotation value, e.g. `MEM` to `memory`."""
    return {f["code"]: f["name"].lower() for f in load(version)["cognitive_functions"]}


@lru_cache
def error_types(version: str = DEFAULT_VERSION) -> dict[str, dict[str, Any]]:
    """Map error code to its full entry, e.g. `RFL-1` to its definition block."""
    return {e["code"]: e for e in load(version)["error_types"]}


@lru_cache
def escape_hatch_code(version: str = DEFAULT_VERSION) -> str:
    """The code used when no category fits, `NEW-?` in v0."""
    return load(version)["escape_hatch"]["code"]
