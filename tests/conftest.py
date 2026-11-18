"""Shared fixtures for git-backed tests."""
from pathlib import Path

import pytest

from tests.gitutil import run_git


@pytest.fixture
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    run_git(tmp_path, "init")
    run_git(tmp_path, "config", "user.email", "test@example.com")
    run_git(tmp_path, "config", "user.name", "Test User")
    run_git(tmp_path, "config", "commit.gpgsign", "false")
    monkeypatch.chdir(tmp_path)
    return tmp_path
