from pathlib import Path

import pytest
import yaml


@pytest.fixture
def rules():
    return yaml.safe_load((Path(__file__).parents[1] / "config/keywords.yaml").read_text())
