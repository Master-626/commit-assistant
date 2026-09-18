"""
Command-line interface for Commit Assistant.
"""
import subprocess
import sys

import click

from .git_analyzer import (
    get_staged_files,
    get_staged_diff_summary,
    analyze_commit_type,
    detect_scope,
    generate_commit_summary,
    generate_commit_body,
)
from . import __version__


@click.command()
@click.option(
    "--dry-run", is_flag=True, default=False,
    help="Preview the suggested commit message without committing.",
)
@click.option(
    "--type", "commit_type",
    type=click.Choice(["feat", "fix", "docs", "style", "refactor", "perf", "test", "chore"]),
    default=None,
    help="Override the detected commit type.",
)
@click.option(
    "--scope", default=None,
    help="Specify a scope (e.g. 'auth', 'api', 'ui').",
)
@click.option(
    "--body", is_flag=True, default=False,
    help="Include a detailed body in the commit message.",
)
@click.option(
    "--amend", is_flag=True, default=False,
    help="Amend the last commit with the new message.",
)
@click.option(
    "-v", "--verbose", is_flag=True, default=False,
    help="Show analysis details.",
)
@click.version_option(version=__version__, prog_name="commit-assistant")
def main(dry_run: bool, commit_type: str, scope: str, body: bool, amend: bool, verbose: bool):
    """
    Commit Assistant - Generate conventional commit messages from staged changes.

    Run this command inside a git repository with staged changes.
    """
    click.echo(f"📝 Commit Assistant v{__version__}")
    click.echo("")

    # Check for staged files
    try:
        files = get_staged_files()
    except RuntimeError as e:
        click.echo(f"❌ Error: {e}", err=True)
        click.echo("   Make sure you're inside a git repository.", err=True)
        sys.exit(1)

    if not files:
        click.echo("❌ No staged changes found.")
        click.echo("   Stage your changes with: git add <files>")
        sys.exit(1)

    click.echo("Analyzing staged changes...")
    click.echo("")

    # Show changed files
    click.echo("  Changed files:")
    for status, filepath in files:
        click.echo(f"    [{status}] {filepath}")
    click.echo("")

    # Get diff summary
    try:
        diff_summary = get_staged_diff_summary()
    except RuntimeError:
        diff_summary = ""

    # Analyze commit type
    if commit_type:
        detected_type = commit_type
    else:
        detected_type = analyze_commit_type(files, diff_summary)

    # Detect scope
    if scope:
        detected_scope = scope
    else:
        detected_scope = detect_scope(files)

    click.echo(f"Detected type: {click.style(detected_type, fg='green')}")
    if detected_scope:
        click.echo(f"Detected scope: {click.style(detected_scope, fg='blue')}")
    click.echo("")

    # Generate commit message
    summary = generate_commit_summary(detected_type, detected_scope, files)

    if body:
        commit_body = generate_commit_body(files)
        full_message = f"{summary}\n\n{commit_body}"
    else:
        full_message = summary

    # Show the message
    click.echo("Suggested commit message:")
    click.echo("─" * 40)
    click.echo(full_message)
    click.echo("─" * 40)
    click.echo("")

    if verbose:
        click.echo("Diff summary:")
        click.echo(diff_summary)
        click.echo("")

    if dry_run:
        click.echo("👀 Dry run - no commit created.")
        return

    # Ask for confirmation
    confirm = click.confirm("Create this commit?")

    if not confirm:
        click.echo("Cancelled.")
        return

    # Create the commit
    try:
        if amend:
            subprocess.run(
                ["git", "commit", "--amend", "-m", full_message],
                check=True,
            )
            click.echo("✅ Last commit amended successfully!")
        else:
            subprocess.run(
                ["git", "commit", "-m", full_message],
                check=True,
            )
            click.echo("✅ Commit created successfully!")
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Failed to create commit: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
