import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vdi.config import load_settings
from vdi.demo import generate_demo_assets


@pytest.fixture
def profile(tmp_path):
    generate_demo_assets()
    settings = load_settings()
    settings.data["database"] = str(tmp_path / "test.sqlite3")
    return settings
