"""
Git integration and diff analysis for Commit Assistant.
"""
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


COMMIT_TYPES = {
    "feat": {"priority": 1, "keywords": ["add", "create", "implement", "new", "introduce", "support"]},
    "fix": {"priority": 2, "keywords": ["fix", "bug", "issue", "error", "crash", "resolve", "patch", "hotfix"]},
    "docs": {"priority": 3, "keywords": ["doc", "readme", "comment", "documentation", "typo"]},
    "refactor": {"priority": 4, "keywords": ["refactor", "restructure", "cleanup", "clean up", "rename", "move"]},
    "perf": {"priority": 5, "keywords": ["perf", "performance", "optimize", "speed", "faster", "slow"]},
    "test": {"priority": 6, "keywords": ["test", "spec", "coverage", "mock", "fixture"]},
    "style": {"priority": 7, "keywords": ["format", "lint", "style", "prettier", "eslint", "indent"]},
    "chore": {"priority": 8, "keywords": ["chore", "bump", "version", "deps", "dependency", "build", "ci"]},
}


SCOPE_PATTERNS = {
    "auth": [r"auth/", r"login", r"oauth", r"jwt", r"token", r"session"],
    "api": [r"api/", r"routes/", r"controllers/", r"endpoints"],
    "ui": [r"components/", r"views/", r"pages/", r"css/", r"style"],
    "db": [r"models/", r"migrations/", r"db/", r"database", r"schema"],
    "config": [r"config/", r".env", r"settings", r"webpack", r"docker"],
    "utils": [r"utils/", r"helpers/", r"lib/", r"common/"],
}


def run_git_command(args: List[str]) -> str:
    """Run a git command and return its output."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Git command failed: {result.stderr.strip()}")
    return result.stdout.strip()


def get_staged_files() -> List[Tuple[str, str]]:
    """
    Get list of staged files.
    Returns list of (status, filepath) tuples.
    """
    output = run_git_command(["diff", "--cached", "--name-status"])
    files = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        filepath = parts[-1]
        files.append((status, filepath))
    return files


def get_staged_diff_summary() -> str:
    """Get a summary of the staged diff for analysis."""
    return run_git_command(["diff", "--cached", "--stat"])


def analyze_commit_type(files: List[Tuple[str, str]], diff_text: str) -> str:
    """
    Analyze staged changes to determine the most likely commit type.
    """
    scores: Dict[str, int] = {t: 0 for t in COMMIT_TYPES}

    # Score based on file paths
    for status, filepath in files:
        lower_path = filepath.lower()

        # Docs files
        if any(lower_path.endswith(ext) for ext in [".md", ".txt", ".rst"]):
            scores["docs"] += 3
        # Test files
        if "test" in lower_path or "spec" in lower_path:
            scores["test"] += 3
        # Config/build files
        if any(part in lower_path for part in ["config", "package.json", "setup.py", "pyproject.toml", ".github/"]):
            scores["chore"] += 2
        # Style files
        if any(lower_path.endswith(ext) for ext in [".css", ".scss", ".less"]):
            scores["style"] += 2

    # Score based on diff content keywords
    for commit_type, info in COMMIT_TYPES.items():
        for keyword in info["keywords"]:
            if keyword in diff_text.lower():
                scores[commit_type] += 1

    # Find the best scoring type
    best_type = max(scores, key=lambda t: scores[t])

    # If nothing scored, default to feat
    if scores[best_type] == 0:
        return "feat"

    return best_type


def detect_scope(files: List[Tuple[str, str]]) -> str:
    """
    Detect the most likely scope based on file paths.
    """
    scope_scores: Dict[str, int] = {s: 0 for s in SCOPE_PATTERNS}

    for _, filepath in files:
        lower_path = filepath.lower()
        for scope, patterns in SCOPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, lower_path):
                    scope_scores[scope] += 1

    best_scope = max(scope_scores, key=lambda s: scope_scores[s])

    if scope_scores[best_scope] == 0:
        return ""

    return best_scope


def generate_commit_summary(commit_type: str, scope: str, files: List[Tuple[str, str]]) -> str:
    """
    Generate a short commit summary message.
    """
    # Get the main file that changed
    main_file = files[0][1] if files else ""

    # Extract the basename without extension
    basename = Path(main_file).stem

    # Generate a summary based on the type
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

    # Add scope if detected
    if scope:
        return f"{commit_type}({scope}): {summary}"
    else:
        return f"{commit_type}: {summary}"


def generate_commit_body(files: List[Tuple[str, str]]) -> str:
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
        }.get(status[0], "Updated")
        lines.append(f"- {status_symbol}: {filepath}")

    return "\n".join(lines)
