"""Reset cached DataManager and working directory between tests."""

from __future__ import annotations

import os
from pathlib import Path

import data_io.manifest as manifest_module
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _reset_data_manager() -> None:
    manifest_module._default_manager = None
    original_cwd = os.getcwd()
    os.chdir(_REPO_ROOT)
    yield
    manifest_module._default_manager = None
    os.chdir(original_cwd)
