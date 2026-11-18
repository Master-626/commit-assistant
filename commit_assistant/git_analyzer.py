"""
Git integration and diff analysis for Commit Assistant.
"""
import re
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

COMMIT_TYPES = {
    "feat": {
        "priority": 1,
        "keywords": ["add", "create", "implement", "new", "introduce", "support"],
    },
    "fix": {
        "priority": 2,
        "keywords": ["fix", "bug", "issue", "error", "crash", "resolve", "patch", "hotfix"],
    },
    "docs": {
        "priority": 3,
        "keywords": ["doc", "readme", "comment", "documentation", "typo"],
    },
    "refactor": {
        "priority": 4,
        "keywords": ["refactor", "restructure", "cleanup", "clean up", "rename", "move"],
    },
    "perf": {
        "priority": 5,
        "keywords": ["perf", "performance", "optimize", "speed", "faster", "slow"],
    },
    "test": {
        "priority": 6,
        "keywords": ["test", "spec", "coverage", "mock", "fixture"],
    },
    "style": {
        "priority": 7,
        "keywords": ["format", "lint", "style", "prettier", "eslint", "indent"],
    },
    "chore": {
        "priority": 8,
        "keywords": ["chore", "bump", "version", "deps", "dependency", "build", "ci"],
    },
}


# Patterns are matched against the lowercased path with forward slashes.
# Directory fragments are anchored to a path boundary so "lib/" does not
# match "glib/" and so ".env" is not the regex "any character + env".
SCOPE_PATTERNS = {
    "auth": [r"(^|/)auth/", r"login", r"oauth", r"jwt", r"token", r"session"],
    "api": [r"(^|/)api/", r"(^|/)routes/", r"(^|/)controllers/", r"endpoints"],
    "ui": [r"(^|/)components/", r"(^|/)views/", r"(^|/)pages/", r"(^|/)css/", r"style"],
    "db": [r"(^|/)models/", r"(^|/)migrations/", r"(^|/)db/", r"database", r"schema"],
    "config": [r"(^|/)config/", r"(^|/)\.env($|\.)", r"settings", r"webpack", r"docker"],
    "utils": [r"(^|/)utils/", r"(^|/)helpers/", r"(^|/)lib/", r"(^|/)common/"],
}

_DOC_EXTENSIONS = (".md", ".txt", ".rst")
_STYLE_EXTENSIONS = (".css", ".scss", ".less")
_TEST_DIR_NAMES = {"test", "tests", "spec", "specs", "__tests__"}
_CHORE_FILENAMES = {"package.json", "setup.py", "pyproject.toml"}
_CHORE_DIR_NAMES = {"config", ".github"}


def run_git_command(args: List[str]) -> str:
    """Run a git command and return its output."""
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", *args],
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise RuntimeError(f"Git command failed: {exc}") from exc
    if result.returncode != 0:
        message = result.stderr.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"Git command failed: {message}")
    return result.stdout.strip()


def unquote_git_path(path: str) -> str:
    """Undo git's C-style quoting of paths that contain special characters."""
    if len(path) < 2 or path[0] != '"' or path[-1] != '"':
        return path
    inner = path[1:-1]
    try:
        decoded = inner.encode("utf-8").decode("unicode_escape")
        return decoded.encode("latin-1").decode("utf-8")
    except (UnicodeError, ValueError):
        return inner


def parse_name_status(output: str) -> List[Tuple[str, str]]:
    """Parse ``git diff --name-status`` output into ``(status, path)`` pairs.

    Renames and copies keep the destination path. Quoted paths are unescaped.
    """
    files = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = [unquote_git_path(part) for part in line.split("\t")]
        if len(parts) < 2:
            continue
        files.append((parts[0], parts[-1]))
    return files


def get_staged_files() -> List[Tuple[str, str]]:
    """
    Get list of staged files.
    Returns list of (status, filepath) tuples.
    """
    output = run_git_command(["diff", "--cached", "--name-status", "--no-color"])
    return parse_name_status(output)


def get_staged_diff_summary() -> str:
    """Get a summary of the staged diff for display."""
    return run_git_command(["diff", "--cached", "--stat", "--no-color"])


def get_staged_diff() -> str:
    """Return the staged patch used to classify the commit."""
    return run_git_command(["diff", "--cached", "--no-ext-diff", "--no-color"])


def get_last_commit_files() -> List[Tuple[str, str]]:
    """Return name-status entries for HEAD, used when ``--amend`` has an empty index."""
    output = run_git_command(
        [
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-status",
            "-r",
            "-M",
            "--no-color",
            "HEAD",
        ]
    )
    return parse_name_status(output)


def get_last_commit_diff() -> str:
    """Return the patch introduced by HEAD."""
    return run_git_command(["show", "--format=", "--no-color", "--no-ext-diff", "-M", "-p", "HEAD"])


def get_last_commit_summary() -> str:
    """Return a stat summary of HEAD."""
    return run_git_command(["show", "--format=", "--stat", "--no-color", "HEAD"])


def _parts(filepath: str) -> List[str]:
    normalized = filepath.lower().replace("\\", "/")
    return [part for part in normalized.split("/") if part not in ("", ".")]


def _is_doc_path(filepath: str) -> bool:
    return filepath.lower().endswith(_DOC_EXTENSIONS)


def _is_test_path(filepath: str) -> bool:
    """True for conventional test paths, not for names that merely contain 'test'."""
    parts = _parts(filepath)
    if not parts:
        return False
    if any(part in _TEST_DIR_NAMES for part in parts[:-1]):
        return True
    filename = parts[-1]
    pieces = filename.split(".")
    if any(piece in {"test", "spec"} for piece in pieces[:-1]):
        return True
    stem = filename.rsplit(".", 1)[0] if "." in filename[1:] else filename
    if stem in _TEST_DIR_NAMES:
        return True
    if stem.startswith(("test_", "spec_")) or stem.endswith(("_test", "_spec")):
        return True
    return False


def _path_kind(filepath: str) -> str:
    if _is_test_path(filepath):
        return "test"
    if _is_doc_path(filepath):
        return "docs"
    return "code"


def _is_chore_path(filepath: str) -> bool:
    """Match build/config paths without treating ``configure.py`` as config."""
    parts = _parts(filepath)
    if not parts:
        return False
    filename = parts[-1]
    if filename in _CHORE_FILENAMES:
        return True
    if any(part in _CHORE_DIR_NAMES for part in parts):
        return True
    stem = filename.rsplit(".", 1)[0] if "." in filename[1:] else filename
    return stem == "config"


def _keyword_corpus(diff_text: str) -> str:
    """Text searched for built-in keywords.

    Unified diffs contribute only added and removed lines, so boilerplate such
    as ``new file mode`` does not vote for ``feat``. Plain text is used as-is.
    """
    changed = []
    for line in diff_text.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith(("+", "-")):
            changed.append(line[1:])
    if changed:
        return "\n".join(changed)
    return diff_text


def _contains_keyword(keyword: str, text: str) -> bool:
    return re.search(r"\b" + re.escape(keyword) + r"\b", text, flags=re.IGNORECASE) is not None


def _type_priority(name: str) -> int:
    info = COMMIT_TYPES.get(name)
    if info is None:
        return 0
    return int(info["priority"])


def _custom_types(config: Optional[object]) -> Sequence[object]:
    if config is None:
        return ()
    return tuple(getattr(config, "custom_types", ()) or ())


def analyze_commit_type(
    files: List[Tuple[str, str]],
    diff_text: str,
    config: Optional[object] = None,
) -> str:
    """
    Analyze staged changes to determine the most likely commit type.

    Documentation-only and test-only changes keep those types. Otherwise test
    and doc paths do not outvote the source change. Keywords match whole words
    in added and removed lines.
    """
    diff_text = diff_text or ""
    scores: Dict[str, int] = {name: 0 for name in COMMIT_TYPES}
    custom_types = _custom_types(config)
    for custom in custom_types:
        scores.setdefault(custom.name, 0)

    if files:
        kinds = [_path_kind(path) for _, path in files]
        if all(kind == "docs" for kind in kinds):
            scores["docs"] += 3
        elif all(kind == "test" for kind in kinds):
            scores["test"] += 3
        else:
            for (_, filepath), kind in zip(files, kinds):
                if kind != "code":
                    continue
                if _is_chore_path(filepath):
                    scores["chore"] += 2
                if filepath.lower().endswith(_STYLE_EXTENSIONS):
                    scores["style"] += 2
            corpus = _keyword_corpus(diff_text).lower()
            for commit_type, info in COMMIT_TYPES.items():
                for keyword in info["keywords"]:
                    if _contains_keyword(keyword, corpus):
                        scores[commit_type] += 1

    corpus = _keyword_corpus(diff_text)
    for custom in custom_types:
        pattern = getattr(custom, "pattern", "") or ""
        if pattern and re.search(pattern, corpus):
            scores[custom.name] += 5

    best_type = max(scores, key=lambda name: (scores[name], -_type_priority(name)))
    if scores[best_type] == 0:
        if files and {status[:1] for status, _ in files} == {"R"}:
            return "refactor"
        if files and {status[:1] for status, _ in files} == {"D"}:
            return "refactor"
        return "feat"
    return best_type


def detect_scope(files: List[Tuple[str, str]], config: Optional[object] = None) -> str:
    """
    Detect the most likely scope based on file paths.
    """
    if config is None:
        patterns_map = SCOPE_PATTERNS
    else:
        patterns_map = getattr(config, "scope_patterns", SCOPE_PATTERNS)
    scope_scores: Dict[str, int] = {name: 0 for name in patterns_map}
    if not scope_scores:
        return ""

    for _, filepath in files:
        lower_path = filepath.lower().replace("\\", "/")
        for scope, patterns in patterns_map.items():
            for pattern in patterns:
                if re.search(pattern, lower_path):
                    scope_scores[scope] += 1

    best_scope = max(scope_scores, key=lambda name: scope_scores[name])
    if scope_scores[best_scope] == 0:
        return ""
    return best_scope


def _primary_file(files: Sequence[Tuple[str, str]]) -> Tuple[str, str]:
    """Prefer a source file over a test or doc that was staged alongside it."""
    for status, filepath in files:
        if _path_kind(filepath) == "code":
            return status, filepath
    return files[0]


def _basename(filepath: str) -> str:
    path = Path(filepath)
    return path.stem or path.name or "files"


def generate_commit_summary(
    commit_type: str,
    scope: str,
    files: List[Tuple[str, str]],
    config: Optional[object] = None,
) -> str:
    """
    Generate a short commit summary message.
    """
    descriptions = {}
    for custom in _custom_types(config):
        description = getattr(custom, "description", "") or ""
        if description:
            descriptions[custom.name] = description

    basename = _basename(_primary_file(files)[1]) if files else "files"
    all_deleted = bool(files) and all(status[:1] == "D" for status, _ in files)
    all_renamed = bool(files) and all(status[:1] == "R" for status, _ in files)

    if all_deleted:
        summary = f"remove {basename}"
    elif all_renamed:
        summary = f"rename {basename}"
    elif commit_type in descriptions:
        text = " ".join(descriptions[commit_type].split())
        summary = text[0].lower() + text[1:] if text else f"update {basename}"
    else:
        type_actions = {
            "feat": f"add {basename} functionality",
            "fix": f"fix {basename} issue",
            "docs": f"update {basename} documentation",
            "refactor": f"refactor {basename} module",
            "perf": f"improve {basename} performance",
            "test": f"add tests for {basename}",
            "style": f"format {basename}",
            "chore": f"update {basename} config",
        }
        summary = type_actions.get(commit_type, f"update {basename}")

    if scope:
        return f"{commit_type}({scope}): {summary}"
    return f"{commit_type}: {summary}"


def generate_commit_body(files: Iterable[Tuple[str, str]]) -> str:
    """
    Generate a detailed commit body listing changed files.
    """
    lines = []
    for status, filepath in files:
        status_symbol = {
            "A": "Added",
            "M": "Modified",
            "D": "Deleted",
            "R": "Renamed",
        }.get(status[:1], "Updated")
        lines.append(f"- {status_symbol}: {filepath}")
    return "\n".join(lines)
