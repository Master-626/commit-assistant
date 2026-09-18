# Commit Assistant

A lightweight command-line tool that generates conventional commit messages based on your staged changes. Saves you time thinking about commit message format and keeps your git history clean and consistent.

[![PyPI version](https://img.shields.io/pypi/v/commit-assistant)](https://pypi.org/project/commit-assistant/)
[![Python versions](https://img.shields.io/pypi/pyversions/commit-assistant)](https://pypi.org/project/commit-assistant/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- ✍️ **Smart commit messages** - Analyzes staged changes and suggests conventional commit messages
- 📏 **Follows conventions** - Automatically uses Conventional Commits format (`feat:`, `fix:`, `docs:`, etc.)
- 🎯 **Context-aware** - Understands whether you're fixing a bug, adding a feature, or updating docs
- ⚡ **Fast and lightweight** - No heavy dependencies, runs in milliseconds
- 🔧 **Configurable** - Customize commit types and scope rules

## Installation

```bash
pip install commit-assistant
```

## Quick Start

Stage your changes:

```bash
git add .
```

Generate and create a commit:

```bash
commit-assist
```

Preview the suggested message without committing:

```bash
commit-assist --dry-run
```

## Usage

```
commit-assist [OPTIONS]

Options:
  --dry-run         Preview the suggested commit message without committing
  --type [feat|fix|docs|style|refactor|test|chore]
                    Override the detected commit type
  --scope TEXT       Specify a scope (e.g. 'auth', 'api', 'ui')
  --body             Include a detailed body in the commit message
  --amend            Amend the last commit with the new message
  -v, --verbose      Show analysis details
  -h, --help         Show this help message
```

## Example Output

```
📝 Commit Assistant

Analyzing staged changes...

  Modified: src/auth/login.py
  Modified: src/auth/token.py
  Added: tests/auth/login_test.py

Detected type: feat
Detected scope: auth

Suggested commit message:
─────────────────────────────────────
feat(auth): add token refresh mechanism

- Added refresh_token() function to token.py
- Updated login flow to store refresh token
- Added unit tests for token refresh
─────────────────────────────────────

Create this commit? [Y/n]
```

## Supported Commit Types

| Type | Description |
|------|-------------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation only changes |
| `style` | Changes that do not affect code meaning (formatting, etc.) |
| `refactor` | A code change that neither fixes a bug nor adds a feature |
| `perf` | A code change that improves performance |
| `test` | Adding missing tests or correcting existing tests |
| `chore` | Changes to build process, tools, or libraries |

## How It Works

Commit Assistant analyzes your staged changes by:

1. Running `git diff --cached --stat` to see which files changed
2. Categorizing changes based on file paths and extensions
3. Detecting keywords in the diff to identify bug fixes vs new features
4. Generating a structured commit message following Conventional Commits

## Configuration

Create a `.commit-assist.yml` in your project root to customize:

```yaml
# Custom commit type mappings
custom_types:
  - name: "revert"
    pattern: "Reverts"
    description: "Reverts a previous commit"

# Scope detection rules
scope_patterns:
  auth: ["auth/", "login", "oauth", "jwt"]
  api: ["api/", "routes/", "controllers/"]
  ui: ["components/", "views/", "css/"]
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](LICENSE) file for details.
