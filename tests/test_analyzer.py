"""Unit tests for commit classification and message generation."""
from commit_assistant.git_analyzer import (
    analyze_commit_type,
    detect_scope,
    generate_commit_body,
    generate_commit_summary,
    unquote_git_path,
)


def test_keywords_match_whole_words_only():
    files = [("M", "src/parser.py")]
    # "address" contains "add" and "remove" contains "move"; neither is its own word.
    diff = "fix the address parser and remove the unused helper"
    assert analyze_commit_type(files, diff) == "fix"


def test_prefix_and_builder_are_not_false_keywords():
    files = [("M", "src/parser.py")]
    assert analyze_commit_type(files, "return prefix + suffix") == "feat"
    assert analyze_commit_type(files, "fix the prefix parser") == "fix"
    assert analyze_commit_type(files, "update the builder image") == "feat"


def test_diff_headers_do_not_vote_for_feat():
    files = [("A", "src/parser.py")]
    diff = """diff --git a/src/parser.py b/src/parser.py
new file mode 100644
index 0000000..abc
--- /dev/null
+++ b/src/parser.py
@@ -0,0 +1 @@
+fix crash when input is empty
"""
    assert analyze_commit_type(files, diff) == "fix"


def test_stat_summary_alone_does_not_invent_a_type():
    files = [("M", "src/parser.py")]
    stat = " src/parser.py | 2 +-\n 1 file changed, 1 insertion(+), 1 deletion(-)"
    assert analyze_commit_type(files, stat) == "feat"


def test_test_and_spec_substrings_are_not_test_commits():
    assert analyze_commit_type([("M", "src/contest.py")], "") == "feat"
    assert analyze_commit_type([("A", "src/specific.py")], "") == "feat"
    assert analyze_commit_type([("A", "src/testimony.py")], "") == "feat"


def test_conventional_test_paths_are_test_commits():
    assert analyze_commit_type([("A", "tests/test_specific.py")], "") == "test"
    assert analyze_commit_type([("A", "src/parser_test.py")], "") == "test"
    assert analyze_commit_type([("A", "src/button.spec.ts")], "") == "test"
    assert analyze_commit_type([("M", "test/test_parser.py")], "fix the flaky assertion") == "test"


def test_docs_and_tests_do_not_outvote_source_changes():
    mixed_tests = [("A", "tests/test_invoice.py"), ("A", "src/billing/invoice.py")]
    assert analyze_commit_type(mixed_tests, "") == "feat"
    assert generate_commit_summary("feat", "billing", mixed_tests) == (
        "feat(billing): add invoice functionality"
    )

    mixed_docs = [("M", "README.md"), ("M", "src/parser.py")]
    assert analyze_commit_type(mixed_docs, "fix crash when the buffer is empty") == "fix"
    assert generate_commit_summary("fix", "", mixed_docs) == "fix: fix parser issue"


def test_documentation_only_change_stays_docs():
    files = [("M", "README.md")]
    assert analyze_commit_type(files, "fix the typo in the intro") == "docs"
    assert generate_commit_summary("docs", "", files) == "docs: update README documentation"


def test_configure_py_is_not_a_chore_but_real_config_paths_are():
    assert analyze_commit_type([("M", "src/configure.py")], "") == "feat"
    assert analyze_commit_type([("M", "src/reconfig.py")], "") == "feat"
    assert analyze_commit_type([("M", "src/config.py")], "") == "chore"
    assert analyze_commit_type([("M", "src/config/app.py")], "") == "chore"
    assert analyze_commit_type([("M", ".github/workflows/ci.yml")], "") == "chore"
    assert analyze_commit_type([("M", "pyproject.toml")], "") == "chore"
    assert analyze_commit_type([("M", "package.json")], "") == "chore"


def test_style_extension_is_detected():
    assert analyze_commit_type([("M", "src/app.css")], "") == "style"


def test_equal_keyword_scores_prefer_higher_priority_type():
    files = [("M", "src/parser.py")]
    assert analyze_commit_type(files, "add a guard and fix the parser") == "feat"


def test_deletion_and_rename_summaries_do_not_say_add():
    deleted = [("D", "src/parser.py")]
    assert analyze_commit_type(deleted, "- print('hello')\n") == "refactor"
    assert generate_commit_summary("refactor", "", deleted) == "refactor: remove parser"
    assert analyze_commit_type(deleted, "- fix leftover hack\n") == "fix"
    assert generate_commit_summary("fix", "", deleted) == "fix: remove parser"

    renamed = [("R100", "src/parser.py")]
    assert analyze_commit_type(renamed, "") == "refactor"
    assert generate_commit_summary("refactor", "", renamed) == "refactor: rename parser"


def test_commit_body_maps_status_codes():
    body = generate_commit_body(
        [
            ("A", "src/a.py"),
            ("R100", "src/b.py"),
            ("C90", "src/c.py"),
            ("D", "src/d.py"),
            ("M", "src/e.py"),
        ]
    )
    assert body == "\n".join(
        [
            "- Added: src/a.py",
            "- Renamed: src/b.py",
            "- Updated: src/c.py",
            "- Deleted: src/d.py",
            "- Modified: src/e.py",
        ]
    )


def test_scope_regex_does_not_match_lookalikes():
    assert detect_scope([("A", "src/envy.py")]) == ""
    assert detect_scope([("A", "pkg/environment.py")]) == ""
    assert detect_scope([("A", "src/xenv/a.py")]) == ""
    assert detect_scope([("A", "my_environment.py")]) == ""
    assert detect_scope([("A", "foo.env")]) == ""
    assert detect_scope([("A", "glib/foo.py")]) == ""
    assert detect_scope([("A", "mydb/foo.py")]) == ""

    assert detect_scope([("A", ".env")]) == "config"
    assert detect_scope([("A", "config/.env.local")]) == "config"
    assert detect_scope([("A", "src/lib/foo.py")]) == "utils"
    assert detect_scope([("A", "src/db/foo.py")]) == "db"
    assert detect_scope([("A", "src/auth/login.py")]) == "auth"
    assert detect_scope([("A", "src/login.py")]) == "auth"
    assert detect_scope([("A", "development/settings.py")]) == "config"
    assert detect_scope([("A", "src/endpoints.py")]) == "api"
    assert detect_scope([("A", "jwt/api/client.py")]) == "auth"
    assert detect_scope([("M", "src\\auth\\login.py")]) == "auth"


def test_scope_can_be_included_or_omitted():
    files = [("M", "src/parser.py")]
    assert generate_commit_summary("fix", "api", files) == "fix(api): fix parser issue"
    assert generate_commit_summary("fix", "", files) == "fix: fix parser issue"


def test_empty_file_list_still_renders_a_subject():
    assert generate_commit_summary("chore", "", []) == "chore: update files config"


def test_git_quoted_paths_are_unescaped():
    assert unquote_git_path(r'"we\"ird.py"') == 'we"ird.py'
    assert unquote_git_path("src/plain.py") == "src/plain.py"
    assert unquote_git_path(r'"\346\226\207\346\241\243.md"') == "文档.md"
    assert unquote_git_path(r'"a\tb.py"') == "a\tb.py"
