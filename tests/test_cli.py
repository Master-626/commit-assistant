"""CLI tests against a temporary git repository."""
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from commit_assistant.cli import main
from commit_assistant.git_analyzer import get_staged_diff, get_staged_files
from tests.gitutil import run_git

runner = CliRunner()


def _text(result) -> str:
    """Stdout plus stderr, across Click versions that split the streams."""
    return (result.output or "") + (getattr(result, "stderr", None) or "")


def _commit_file(repo: Path, relative: str, content: str, message: str = "wip") -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    run_git(repo, "add", "--", relative)
    run_git(repo, "commit", "-m", message)


def test_help_and_version():
    help_result = runner.invoke(main, ["--help"], color=False)
    assert help_result.exit_code == 0
    help_text = _text(help_result)
    assert "--dry-run" in help_text
    assert "--amend" in help_text
    assert "--body" in help_text

    version = runner.invoke(main, ["--version"], color=False)
    assert version.exit_code == 0
    assert "1.1.0" in _text(version)


def test_outside_a_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(main, ["--dry-run"], color=False)
    assert result.exit_code == 1
    assert "git repository" in _text(result).lower()


def test_missing_git_binary_is_reported(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    result = runner.invoke(main, ["--dry-run"], color=False)
    assert result.exit_code == 1
    assert "Git command failed" in _text(result)


def test_no_staged_changes(git_repo: Path):
    _commit_file(git_repo, "README.md", "hello\n")
    result = runner.invoke(main, ["--dry-run"], color=False)
    assert result.exit_code == 1
    assert "No staged changes" in _text(result)


def test_dry_run_classifies_the_patch_and_does_not_commit(git_repo: Path):
    _commit_file(git_repo, "src/parser.py", "value = 1\n")
    (git_repo / "src/parser.py").write_text("fix crash on empty input\n", encoding="utf-8")
    run_git(git_repo, "add", "--", "src/parser.py")

    result = runner.invoke(main, ["--dry-run"], color=False)
    assert result.exit_code == 0
    output = _text(result)
    assert "Detected type: fix" in output
    assert "fix: fix parser issue" in output
    assert "Dry run" in output
    assert run_git(git_repo, "log", "-1", "--format=%s").stdout.strip() == "wip"


def test_confirmation_creates_or_cancels_the_commit(git_repo: Path):
    (git_repo / "src").mkdir()
    (git_repo / "src/parser.py").write_text("fix crash on empty input\n", encoding="utf-8")
    run_git(git_repo, "add", "--", "src/parser.py")

    cancelled = runner.invoke(main, input="n\n", color=False)
    assert cancelled.exit_code == 0
    assert "Cancelled" in _text(cancelled)
    assert subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True).returncode != 0

    created = runner.invoke(main, input="y\n", color=False)
    assert created.exit_code == 0
    assert "Commit created successfully" in _text(created)
    assert run_git(git_repo, "log", "-1", "--format=%s").stdout.strip() == "fix: fix parser issue"


def test_type_scope_and_body_overrides(git_repo: Path):
    (git_repo / "src").mkdir()
    (git_repo / "src/parser.py").write_text("value = 1\n", encoding="utf-8")
    run_git(git_repo, "add", "--", "src/parser.py")
    result = runner.invoke(
        main,
        ["--dry-run", "--type", "chore", "--scope", "api", "--body"],
        color=False,
    )
    assert result.exit_code == 0
    output = _text(result)
    assert "chore(api): update parser config" in output
    assert "- Added: src/parser.py" in output


def test_unknown_type_is_rejected(git_repo: Path):
    result = runner.invoke(main, ["--type", "nope", "--dry-run"], color=False)
    assert result.exit_code != 0
    assert "invalid choice" in _text(result)


def test_amend_with_a_clean_index_describes_head(git_repo: Path):
    _commit_file(git_repo, "src/parser.py", "fix crash on empty input\n", message="wip")
    preview = runner.invoke(main, ["--amend", "--dry-run"], color=False)
    assert preview.exit_code == 0
    preview_text = _text(preview)
    assert "last commit" in preview_text.lower()
    assert "fix: fix parser issue" in preview_text
    assert run_git(git_repo, "log", "-1", "--format=%s").stdout.strip() == "wip"

    amended = runner.invoke(main, ["--amend"], input="y\n", color=False)
    assert amended.exit_code == 0
    assert "amended successfully" in _text(amended)
    subjects = run_git(git_repo, "log", "--format=%s").stdout.splitlines()
    assert subjects == ["fix: fix parser issue"]


def test_amend_prefers_staged_changes_over_head(git_repo: Path):
    _commit_file(git_repo, "README.md", "hello\n", message="docs")
    (git_repo / "src").mkdir()
    (git_repo / "src/parser.py").write_text("fix crash on empty input\n", encoding="utf-8")
    run_git(git_repo, "add", "--", "src/parser.py")
    result = runner.invoke(main, ["--amend", "--dry-run"], color=False)
    assert result.exit_code == 0
    output = _text(result)
    assert "No staged changes" not in output
    assert "fix: fix parser issue" in output


def test_amend_without_any_commit(git_repo: Path):
    result = runner.invoke(main, ["--amend", "--dry-run"], color=False)
    assert result.exit_code == 1
    assert "--amend" in _text(result)


def test_non_utf8_patch_does_not_crash(git_repo: Path):
    (git_repo / "bad.py").write_bytes(b"a\xffb\n")
    run_git(git_repo, "add", "--", "bad.py")
    diff = get_staged_diff()
    assert "bad.py" in diff
    assert get_staged_files() == [("A", "bad.py")]
    result = runner.invoke(main, ["--dry-run"], color=False)
    assert result.exit_code == 0
    assert result.exception is None


def test_quoted_and_unicode_paths(git_repo: Path):
    (git_repo / 'we"ird.py').write_text("fix crash\n", encoding="utf-8")
    (git_repo / "说明.md").write_text("hello\n", encoding="utf-8")
    run_git(git_repo, "add", "-A")
    statuses = get_staged_files()
    assert ("A", 'we"ird.py') in statuses
    assert ("A", "说明.md") in statuses
    result = runner.invoke(main, ["--dry-run"], color=False)
    assert result.exit_code == 0
    output = _text(result)
    assert "Detected type: fix" in output
    assert 'we"ird.py' in output
    assert "说明.md" in output
    assert '\\' not in output.split("Changed files:", 1)[-1].split("Detected type:", 1)[0]


def test_project_config_adds_a_scope_and_type(git_repo: Path, monkeypatch: pytest.MonkeyPatch):
    (git_repo / ".commit-assist.yml").write_text(
        """
custom_types:
  - name: revert
    pattern: "Reverts"
    description: "Reverts a previous commit"
scope_patterns:
  billing: ["billing/"]
""",
        encoding="utf-8",
    )
    billing = git_repo / "billing"
    billing.mkdir()
    (billing / "invoice.py").write_text("Reverts the old invoice flow\n", encoding="utf-8")
    run_git(git_repo, "add", "-A")
    monkeypatch.chdir(billing)

    result = runner.invoke(main, ["--dry-run", "--verbose"], color=False)
    assert result.exit_code == 0
    output = _text(result)
    assert "revert(billing): reverts a previous commit" in output
    assert ".commit-assist.yml" in output

    overridden = runner.invoke(main, ["--dry-run", "--type", "revert"], color=False)
    assert overridden.exit_code == 0
    assert "revert" in _text(overridden)


def test_invalid_project_config_stops_the_command(git_repo: Path):
    (git_repo / ".commit-assist.yml").write_text("not: valid-for-us\n", encoding="utf-8")
    (git_repo / "README.md").write_text("hello\n", encoding="utf-8")
    run_git(git_repo, "add", "--", "README.md")
    result = runner.invoke(main, ["--dry-run"], color=False)
    assert result.exit_code == 1
    assert "Unknown setting" in _text(result)


def test_unconfigured_custom_type_is_rejected(git_repo: Path):
    result = runner.invoke(main, ["--type", "revert", "--dry-run"], color=False)
    assert result.exit_code != 0
    assert "invalid choice" in _text(result)
