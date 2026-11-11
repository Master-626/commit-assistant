# Commit Assistant

## 简介

Commit Assistant 是一个轻量命令行工具。它读取 Git 暂存区中的改动，推断 Conventional Commits 类型（如 `feat`、`fix`、`docs`）和可选作用域，并生成提交说明；确认后可以直接执行 `git commit`。判断依据是文件路径和 diff 里的关键词，不需要联网。仓库根目录的 `.commit-assist.yml` 可以追加自定义类型和作用域。

A local command-line tool that drafts a [Conventional Commit](https://www.conventionalcommits.org/) message from the staged diff. It shells out to `git`, prints a subject such as `fix(auth): fix parser issue`, and creates the commit only after you confirm.

Detection is a heuristic: path rules first, then whole-word keywords on added and removed lines. It does not call an external service.

## Requirements

- Python 3.8 or newer
- `git` on your `PATH`

## Installation

```bash
pip install commit-assistant
```

From a checkout, install the package with the test and lint tools:

```bash
pip install -e ".[dev]"
```

The `commit-assist` command is registered as a console script.

## Usage

Stage the changes you want to describe:

```bash
git add src/parser.py
commit-assist
```

The prompt is `Create this commit? [y/N]`. Pressing Enter does not commit.

Preview the message and leave the index untouched:

```bash
commit-assist --dry-run
```

```text
📝 Commit Assistant v1.1.0

Analyzing staged changes...

  Changed files:
    [M] src/parser.py

Detected type: fix

Suggested commit message:
────────────────────────────────────────
fix: fix parser issue
────────────────────────────────────────

👀 Dry run - no commit created.
```

Force the type and scope, and list each file in the body:

```bash
commit-assist --type fix --scope auth --body
```

```text
fix(auth): fix parser issue

- Modified: src/parser.py
```

Amend the previous commit. Staged changes are used when the index is not empty; otherwise the last commit itself is analyzed:

```bash
commit-assist --amend
```

Show the diff stat and, when present, the config file path:

```bash
commit-assist --dry-run --verbose
```

## Options

| Option | Description |
| --- | --- |
| `--dry-run` | Print the message and do not run `git commit`. |
| `--type` | Override the detected type. One of `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, or a custom type from `.commit-assist.yml`. |
| `--scope TEXT` | Set the scope (`auth`, `api`, `ui`, …). When omitted, a scope is detected from paths. |
| `--body` | Append a bullet list of changed files. |
| `--amend` | Amend `HEAD`. Uses staged changes when present, otherwise the last commit. |
| `-v`, `--verbose` | Show the diff stat and the config path. |
| `--version` | Print the version and exit. |
| `--help` | Print the option summary and exit. |

## Commit types

| Type | When it is chosen |
| --- | --- |
| `feat` | Default when nothing else matches a new or modified change. |
| `fix` | Added or removed lines contain a whole word such as `fix`, `bug`, or `crash`. |
| `docs` | Every staged path is documentation (`.md`, `.rst`, `.txt`). |
| `test` | Every staged path is a test path (`tests/`, `test_*.py`, `*_test.py`, `*.spec.ts`, …). |
| `refactor` | Refactor keywords, or a change that only renames or only deletes files. |
| `perf` | Performance keywords (`optimize`, `faster`, …). |
| `style` | Stylesheets (`.css`, `.scss`, `.less`) when they are not outweighed by another signal. |
| `chore` | Build and config paths such as `pyproject.toml`, `package.json`, `setup.py`, `config.py`, or `.github/`. |

`src/contest.py` and `src/specific.py` are not treated as tests. `src/configure.py` is not treated as config. A feature staged together with its tests stays `feat`; a code fix staged together with a README stays `fix`.

When every path is a rename, the subject uses `rename`. When every path is a deletion, it uses `remove` instead of `add … functionality`.

If two types score the same, the earlier row in the table wins (`feat` before `fix`).

## Scope

Built-in scopes are `auth`, `api`, `ui`, `db`, `config`, and `utils`. Patterns are regular expressions matched against the lowercased path. Directory fragments are anchored, so `lib/` does not match `glib/` and `.env` does not match `environment.py`.

The subject names the first source file. A test or doc staged beside it is not used as the name.

## Configuration

Optional file: `.commit-assist.yml` in the git repository root. A copy in a subdirectory is ignored. If the file is absent, the built-in rules are used.

```yaml
# scope_patterns replace the built-in list for that name.
# Other built-in scopes are kept. An empty list disables a scope.
scope_patterns:
  auth: []
  billing: ["billing/"]

# pattern is a regex against added and removed lines.
# It is case-sensitive; prefix it with (?i) to ignore case.
custom_types:
  - name: revert
    pattern: "Reverts"
    description: "Reverts a previous commit"
```

`description` becomes the subject with its first character lowercased, for example `revert(billing): reverts a previous commit`. Custom type names are lowercase tokens (`revert`) and cannot replace a built-in type. They are valid `--type` values. Invalid YAML or an unknown key stops the command with an error.

`-v` prints the absolute path of the file that was loaded.

## How it works

1. `git diff --cached --name-status` lists staged files. Paths that git quotes (`"we\"ird.py"`) are unquoted. Non-UTF-8 patch bytes are replaced so the command does not crash.
2. The commit type is scored from those paths and from `git diff --cached` (added and removed lines only, not the `new file mode` header and not the `--stat` summary).
3. The scope is the best match in the scope table, including names added in `.commit-assist.yml`.
4. After confirmation, the tool runs `git commit -m …` or `git commit --amend -m …`.

## Running tests

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

GitHub Actions (`.github/workflows/ci.yml`) runs Ruff and pytest on Python 3.8, 3.9, 3.10, 3.11, and 3.12.

## License

MIT. See [LICENSE](LICENSE).
