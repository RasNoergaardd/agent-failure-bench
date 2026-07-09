from pathlib import Path

import pytest

from afb.models import Trajectory

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_trajectory() -> Trajectory:
    return Trajectory.model_validate_json((FIXTURES / "sample_trajectory.json").read_text())
