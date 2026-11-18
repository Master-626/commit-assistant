"""Tests for .commit-assist.yml loading and the detection it customizes."""
from pathlib import Path

import pytest

from commit_assistant.config import ConfigError, load_config, parse_config_file
from commit_assistant.git_analyzer import analyze_commit_type, detect_scope, generate_commit_summary
from tests.gitutil import run_git


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_empty_file_keeps_builtin_rules(tmp_path: Path):
    config = parse_config_file(_write(tmp_path / ".commit-assist.yml", ""))
    assert config.custom_types == ()
    assert detect_scope([("A", "src/auth/login.py")], config) == "auth"


def test_scope_patterns_merge_and_custom_type_wins(tmp_path: Path):
    config = parse_config_file(
        _write(
            tmp_path / ".commit-assist.yml",
            """
scope_patterns:
  auth: []
  billing:
    - billing/
custom_types:
  - name: revert
    pattern: "Reverts"
    description: "Reverts a previous commit"
""",
        )
    )
    assert detect_scope([("A", "src/auth/login.py")], config) == ""
    assert detect_scope([("A", "billing/invoice.py")], config) == "billing"
    assert detect_scope([("A", "src/db/foo.py")], config) == "db"

    files = [("M", "billing/invoice.py")]
    matched = "+ Reverts the old invoice flow\n"
    assert analyze_commit_type(files, matched, config) == "revert"
    assert generate_commit_summary("revert", "billing", files, config) == (
        "revert(billing): reverts a previous commit"
    )
    # A matching custom type outranks a single built-in keyword.
    assert analyze_commit_type(files, "+ Reverts the crash fix\n", config) == "revert"
    assert analyze_commit_type(files, "+ add a field\n", config) == "feat"


def test_invalid_config_is_rejected(tmp_path: Path):
    path = tmp_path / ".commit-assist.yml"
    cases = {
        "custom_types: [\n": "Invalid YAML",
        "[]\n": "YAML mapping",
        "extra: true\n": "Unknown setting",
        "scope_patterns: [billing]\n": "scope_patterns",
        "scope_patterns:\n  billing: ['[']\n": "Invalid regex",
        "custom_types:\n  - name: Feat\n    pattern: Reverts\n": "lowercase",
        "custom_types:\n  - name: feat\n    pattern: Reverts\n": "built-in",
        (
            "custom_types:\n  - name: revert\n    pattern: Reverts\n"
            "  - name: revert\n    pattern: Other\n"
        ): "duplicate",
        "custom_types:\n  - pattern: Reverts\n": "name",
        "scope_patterns:\n  'bad scope': ['x']\n": "Invalid scope",
    }
    for text, match in cases.items():
        _write(path, text)
        with pytest.raises(ConfigError, match=match):
            parse_config_file(path)


def test_hyphenated_scope_name_is_allowed(tmp_path: Path):
    config = parse_config_file(
        _write(
            tmp_path / ".commit-assist.yml",
            "scope_patterns:\n  my-api: ['payments/']\n",
        )
    )
    assert detect_scope([("A", "payments/client.py")], config) == "my-api"


def test_repository_root_config_is_used_from_a_subdirectory(
    git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _write(
        git_repo / ".commit-assist.yml",
        "scope_patterns:\n  billing: ['billing/']\n",
    )
    nested = git_repo / "pkg"
    nested.mkdir()
    _write(nested / ".commit-assist.yml", "scope_patterns:\n  other: ['other/']\n")
    monkeypatch.chdir(nested)
    config = load_config()
    assert "billing" in config.scope_patterns
    assert "other" not in config.scope_patterns


def test_outside_a_repository_parent_config_is_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _write(tmp_path / ".commit-assist.yml", "scope_patterns:\n  billing: ['billing/']\n")
    child = tmp_path / "child"
    child.mkdir()
    monkeypatch.chdir(child)
    config = load_config()
    assert detect_scope([("A", "billing/invoice.py")], config) == "billing"


def test_missing_config_in_a_repository_uses_defaults(git_repo: Path):
    run_git(git_repo, "status")
    config = load_config()
    assert config.custom_types == ()
    assert detect_scope([("A", "src/lib/foo.py")], config) == "utils"
