"""
Command-line interface for Commit Assistant.
"""
import subprocess
import sys
from typing import Optional

import click

from . import __version__
from .config import ConfigError, find_config_file, load_config
from .git_analyzer import (
    COMMIT_TYPES,
    analyze_commit_type,
    detect_scope,
    generate_commit_body,
    generate_commit_summary,
    get_last_commit_diff,
    get_last_commit_files,
    get_last_commit_summary,
    get_staged_diff,
    get_staged_diff_summary,
    get_staged_files,
)


class CommitTypeParam(click.ParamType):
    """Built-in conventional types, plus custom types declared in config."""

    name = "type"

    def get_metavar(
        self,
        param: click.Parameter,
        ctx: Optional[click.Context] = None,
    ) -> str:
        return "[feat|fix|docs|style|refactor|perf|test|chore]"

    def convert(self, value, param, ctx):
        try:
            config = load_config()
        except ConfigError as exc:
            self.fail(str(exc), param, ctx)
        allowed = list(COMMIT_TYPES) + [item.name for item in config.custom_types]
        if value not in allowed:
            choices = ", ".join(allowed)
            self.fail(f"invalid choice: {value}. (choose from {choices})", param, ctx)
        return value


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview the suggested commit message without committing.",
)
@click.option(
    "--type",
    "commit_type",
    type=CommitTypeParam(),
    default=None,
    help="Override the detected commit type. Custom types from .commit-assist.yml are accepted.",
)
@click.option(
    "--scope",
    default=None,
    help="Specify a scope (e.g. 'auth', 'api', 'ui').",
)
@click.option(
    "--body",
    is_flag=True,
    default=False,
    help="Include a detailed body in the commit message.",
)
@click.option(
    "--amend",
    is_flag=True,
    default=False,
    help="Amend the last commit. Uses staged changes when present, otherwise the last commit.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Show analysis details.",
)
@click.version_option(version=__version__, prog_name="commit-assistant")
def main(
    dry_run: bool,
    commit_type: Optional[str],
    scope: Optional[str],
    body: bool,
    amend: bool,
    verbose: bool,
) -> None:
    """
    Commit Assistant - Generate conventional commit messages from staged changes.

    Run this command inside a git repository with staged changes.
    With --amend and an empty index, the last commit is analyzed instead.
    """
    click.echo(f"📝 Commit Assistant v{__version__}")
    click.echo("")

    try:
        config = load_config()
    except ConfigError as exc:
        click.echo(f"❌ Error: {exc}", err=True)
        sys.exit(1)

    try:
        files = get_staged_files()
    except RuntimeError as exc:
        click.echo(f"❌ Error: {exc}", err=True)
        click.echo("   Make sure you're inside a git repository.", err=True)
        sys.exit(1)

    using_head = False
    if not files and amend:
        try:
            files = get_last_commit_files()
        except RuntimeError as exc:
            click.echo(f"❌ Error: {exc}", err=True)
            click.echo("   --amend needs an existing commit when nothing is staged.", err=True)
            sys.exit(1)
        using_head = True

    if not files:
        click.echo("❌ No staged changes found.")
        click.echo("   Stage your changes with: git add <files>")
        sys.exit(1)

    if using_head:
        click.echo("No staged changes. Analyzing the last commit for --amend...")
    else:
        click.echo("Analyzing staged changes...")
    click.echo("")

    click.echo("  Changed files:")
    for status, filepath in files:
        click.echo(f"    [{status}] {filepath}")
    click.echo("")

    try:
        if using_head:
            diff_summary = get_last_commit_summary()
            diff_text = get_last_commit_diff()
        else:
            diff_summary = get_staged_diff_summary()
            diff_text = get_staged_diff()
    except RuntimeError:
        diff_summary = ""
        diff_text = ""

    if commit_type:
        detected_type = commit_type
    else:
        detected_type = analyze_commit_type(files, diff_text, config)

    if scope:
        detected_scope = scope
    else:
        detected_scope = detect_scope(files, config)

    click.echo(f"Detected type: {click.style(detected_type, fg='green')}")
    if detected_scope:
        click.echo(f"Detected scope: {click.style(detected_scope, fg='blue')}")
    click.echo("")

    summary = generate_commit_summary(detected_type, detected_scope, files, config)
    if body:
        full_message = f"{summary}\n\n{generate_commit_body(files)}"
    else:
        full_message = summary

    click.echo("Suggested commit message:")
    click.echo("─" * 40)
    click.echo(full_message)
    click.echo("─" * 40)
    click.echo("")

    if verbose:
        config_path = find_config_file()
        if config_path is not None:
            click.echo(f"Config: {config_path}")
            click.echo("")
        click.echo("Diff summary:")
        click.echo(diff_summary)
        click.echo("")

    if dry_run:
        click.echo("👀 Dry run - no commit created.")
        return

    confirm = click.confirm("Create this commit?", default=False)
    if not confirm:
        click.echo("Cancelled.")
        return

    try:
        command = ["git", "commit"]
        if amend:
            command.append("--amend")
        command.extend(["-m", full_message])
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        click.echo(f"❌ Failed to create commit: {exc}", err=True)
        sys.exit(1)
    except OSError as exc:
        click.echo(f"❌ Failed to create commit: {exc}", err=True)
        sys.exit(1)

    if amend:
        click.echo("✅ Last commit amended successfully!")
    else:
        click.echo("✅ Commit created successfully!")


if __name__ == "__main__":
    main()
