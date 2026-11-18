"""Load optional ``.commit-assist.yml`` settings from the git repository root."""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import yaml

from .git_analyzer import COMMIT_TYPES, SCOPE_PATTERNS, run_git_command

CONFIG_FILENAME = ".commit-assist.yml"
_TYPE_NAME = re.compile(r"^[a-z][a-z0-9]*$")
_SCOPE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_KNOWN_KEYS = {"custom_types", "scope_patterns"}


class ConfigError(ValueError):
    """The project config file is missing required fields or is invalid."""


@dataclass(frozen=True)
class CustomCommitType:
    name: str
    pattern: str
    description: str = ""


@dataclass(frozen=True)
class AssistantConfig:
    scope_patterns: Dict[str, List[str]]
    custom_types: Tuple[CustomCommitType, ...] = ()


def default_config() -> AssistantConfig:
    return AssistantConfig(
        scope_patterns={name: list(patterns) for name, patterns in SCOPE_PATTERNS.items()},
    )


def find_config_file(start: Optional[Path] = None) -> Optional[Path]:
    """Return the repository's config file, if one exists.

    Inside a git checkout only the repository root is consulted, so a config
    file in a parent directory is not picked up by accident. Outside a
    repository, parent directories are searched from ``start``.
    """
    start = (start or Path.cwd()).resolve()
    try:
        toplevel = Path(run_git_command(["rev-parse", "--show-toplevel"]))
    except RuntimeError:
        toplevel = None
    if toplevel is not None:
        candidate = toplevel / CONFIG_FILENAME
        return candidate if candidate.is_file() else None
    for directory in [start, *start.parents]:
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def load_config(start: Optional[Path] = None) -> AssistantConfig:
    """Load project settings, or the built-in defaults when no file exists."""
    path = find_config_file(start)
    if path is None:
        return default_config()
    return parse_config_file(path)


def parse_config_file(path: Path) -> AssistantConfig:
    """Parse a ``.commit-assist.yml`` file and merge it with built-in rules."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Could not read {path}: {exc}") from exc
    except UnicodeError as exc:
        raise ConfigError(f"Could not read {path} as UTF-8: {exc}") from exc

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a YAML mapping")

    unknown = sorted(set(data) - _KNOWN_KEYS)
    if unknown:
        raise ConfigError(f"Unknown setting(s) in {path}: {', '.join(unknown)}")

    scope_patterns = {name: list(patterns) for name, patterns in SCOPE_PATTERNS.items()}
    raw_scopes = data.get("scope_patterns") or {}
    if not isinstance(raw_scopes, dict):
        raise ConfigError("'scope_patterns' must be a mapping of scope name to regex list")
    for name, patterns in raw_scopes.items():
        if not isinstance(name, str) or not _SCOPE_NAME.match(name):
            raise ConfigError(f"Invalid scope name: {name!r}")
        parsed = _string_list(patterns, f"scope_patterns.{name}")
        _compile_patterns(parsed, f"scope_patterns.{name}")
        scope_patterns[name] = parsed

    raw_types = data.get("custom_types") or []
    if not isinstance(raw_types, list):
        raise ConfigError("'custom_types' must be a list")
    custom_types = tuple(_parse_custom_type(item, index) for index, item in enumerate(raw_types))
    names = [item.name for item in custom_types]
    if len(names) != len(set(names)):
        raise ConfigError("custom_types contains a duplicate name")
    for item in custom_types:
        if item.name in COMMIT_TYPES:
            raise ConfigError(f"custom type {item.name!r} overrides a built-in type")

    return AssistantConfig(scope_patterns=scope_patterns, custom_types=custom_types)


def _string_list(value: object, label: str) -> List[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"'{label}' must be a list of strings")
    return list(value)


def _compile_patterns(patterns: Sequence[str], label: str) -> None:
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ConfigError(f"Invalid regex in {label}: {pattern!r} ({exc})") from exc


def _parse_custom_type(item: object, index: int) -> CustomCommitType:
    label = f"custom_types[{index}]"
    if not isinstance(item, dict):
        raise ConfigError(f"{label} must be a mapping")
    unknown = sorted(set(item) - {"name", "pattern", "description"})
    if unknown:
        raise ConfigError(f"Unknown field(s) in {label}: {', '.join(unknown)}")

    name = item.get("name")
    pattern = item.get("pattern")
    description = item.get("description", "")
    if not isinstance(name, str) or not _TYPE_NAME.match(name):
        raise ConfigError(f"{label}.name must be a lowercase conventional type token")
    if not isinstance(pattern, str) or not pattern:
        raise ConfigError(f"{label}.pattern must be a non-empty regex")
    if description is None:
        description = ""
    if not isinstance(description, str):
        raise ConfigError(f"{label}.description must be a string")
    _compile_patterns([pattern], f"{label}.pattern")
    return CustomCommitType(name=name, pattern=pattern, description=description.strip())
