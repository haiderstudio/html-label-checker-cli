#!/usr/bin/env python3
"""Tests for html_label_checker — stdlib unittest only."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import html_label_checker as checker

REPO = Path(__file__).resolve().parent.parent


def run_cli(argv):
    """Run main(argv), capture stdout/stderr, return (code, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = checker.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def write(tmp, name, text, encoding="utf-8"):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding=encoding)
    return str(path)


class TestFindUnlabeledControls(unittest.TestCase):
    def test_input_with_for_label_passes(self):
        html = ('<label for="name">Name</label>'
                '<input type="text" id="name" name="name">')
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_for_label_after_control_passes(self):
        html = ('<input type="text" id="name" name="name">'
                '<label for="name">Name</label>')
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_wrapping_label_passes(self):
        html = ('<label>Name <input type="text" name="name"></label>')
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_wrapping_label_passes_select(self):
        html = ('<label>Country <select name="country">'
                '<option>Pakistan</option></select></label>')
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_wrapping_label_passes_textarea(self):
        html = ('<label>Message <textarea name="msg"></textarea></label>')
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_input_with_no_label_fails_with_line(self):
        html = '<input type="text" id="name" name="name">'
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["line"], 1)
        self.assertEqual(got[0]["tag"], "input")
        self.assertEqual(got[0]["type"], "text")
        self.assertEqual(got[0]["id"], "name")
        self.assertEqual(got[0]["name"], "name")

    def test_input_with_no_id_and_no_label_fails(self):
        html = '<input type="email" name="email">'
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(len(got), 1)
        self.assertIsNone(got[0]["id"])
        self.assertEqual(got[0]["name"], "email")

    def test_input_with_id_but_label_for_other_id_fails(self):
        html = ('<label for="other">Name</label>'
                '<input type="text" id="name" name="name">')
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["id"], "name")

    def test_label_for_nonexistent_id_is_not_flagged(self):
        html = '<label for="ghost">Ghost</label>'
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_label_for_nonexistent_id_saves_nobody(self):
        html = ('<label for="ghost">Ghost</label>'
                '<input type="text" name="real">')
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["name"], "real")

    def test_duplicate_ids_only_first_is_covered(self):
        html = ('<input type="text" id="dup" name="first">\n'
                '<input type="text" id="dup" name="second">\n'
                '<label for="dup">Duplicate</label>')
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["line"], 2)
        self.assertEqual(got[0]["name"], "second")

    def test_duplicate_ids_both_fail_without_label(self):
        html = ('<input type="text" id="dup" name="first">\n'
                '<input type="text" id="dup" name="second">')
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(len(got), 2)

    def test_hidden_input_ignored(self):
        html = '<input type="hidden" name="token" value="abc">'
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_submit_input_ignored(self):
        html = '<input type="submit" value="Send">'
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_button_input_ignored(self):
        html = '<input type="button" value="Cancel">'
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_reset_input_ignored(self):
        html = '<input type="reset" value="Clear">'
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_ignored_types_are_case_insensitive(self):
        html = ('<input type="HIDDEN" name="a">'
                '<input type="Submit" value="Go">'
                '<input TYPE="BUTTON" value="No">')
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_checkbox_needs_a_label(self):
        html = '<input type="checkbox" name="agree">'
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["type"], "checkbox")

    def test_checkbox_with_label_passes(self):
        html = ('<label><input type="checkbox" name="agree"> '
                'I agree</label>')
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_radio_needs_a_label(self):
        html = '<input type="radio" name="choice" value="a">'
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(len(got), 1)

    def test_input_with_no_type_is_text_and_checked(self):
        html = '<input name="plain">'
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(len(got), 1)
        self.assertIsNone(got[0]["type"])

    def test_select_without_label_fails(self):
        html = '<select id="country" name="country"></select>'
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["tag"], "select")
        self.assertEqual(got[0]["id"], "country")
        self.assertIsNone(got[0]["type"])

    def test_select_with_for_label_passes(self):
        html = ('<label for="country">Country</label>'
                '<select id="country" name="country"></select>')
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_textarea_without_label_fails(self):
        html = '<textarea name="message"></textarea>'
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["tag"], "textarea")
        self.assertEqual(got[0]["name"], "message")

    def test_textarea_with_for_label_passes(self):
        html = ('<label for="msg">Message</label>'
                '<textarea id="msg" name="msg"></textarea>')
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_aria_label_alone_does_not_count(self):
        html = '<input type="text" name="name" aria-label="Name">'
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(len(got), 1)

    def test_aria_labelledby_alone_does_not_count(self):
        html = ('<span id="lbl">Name</span>'
                '<input type="text" name="name" aria-labelledby="lbl">')
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(len(got), 1)

    def test_uppercase_tags_and_attributes(self):
        html = ('<LABEL FOR="name">Name</LABEL>'
                '<INPUT TYPE="text" ID="name" NAME="name">')
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_uppercase_unlabeled_found(self):
        html = '<INPUT TYPE="text" ID="name">'
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["id"], "name")

    def test_self_closing_input_checked(self):
        html = '<input type="text" name="name" />'
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(len(got), 1)

    def test_controls_reported_in_document_order_with_lines(self):
        html = ('<input type="text" name="a">\n'
                '<p>text</p>\n'
                '<label for="b">B</label>\n'
                '<input type="text" id="b" name="b">\n'
                '<select name="c"></select>\n'
                '<textarea name="d"></textarea>')
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(
            [(g["tag"], g["name"], g["line"]) for g in got],
            [("input", "a", 1), ("select", "c", 5), ("textarea", "d", 6)])

    def test_control_inside_comment_ignored(self):
        html = ('<label for="a">A</label>'
                '<input type="text" id="a" name="a">\n'
                '<!-- <input type="text" name="b"> not a real control -->')
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_control_inside_script_ignored(self):
        html = ('<script>\n'
                'var s = \'<input type="text" name="fake">\';\n</script>\n'
                '<label for="a">A</label>'
                '<input type="text" id="a" name="a">')
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_control_inside_style_ignored(self):
        html = ('<style>\ninput { color: red; }\n</style>\n'
                '<label for="a">A</label>'
                '<input type="text" id="a" name="a">')
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_unclosed_tags_still_parsed(self):
        html = '<input type="text" name="a">\n<p>text'
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(len(got), 1)

    def test_malformed_html_tolerated(self):
        html = ('<form><label for="a">A</label>'
                '<input type="text" id="a" name="a">'
                '<input type="text" name="b">'
                '<select name="c">')
        got = checker.find_unlabeled_controls(html)
        self.assertEqual(
            [(g["tag"], g["name"]) for g in got],
            [("input", "b"), ("select", "c")])

    def test_empty_document(self):
        self.assertEqual(checker.find_unlabeled_controls(""), [])

    def test_no_controls_at_all(self):
        html = '<div><p>plain text</p></div>'
        self.assertEqual(checker.find_unlabeled_controls(html), [])

    def test_label_without_for_and_no_control_inside(self):
        html = '<label>Just words</label>'
        self.assertEqual(checker.find_unlabeled_controls(html), [])


class TestCheckFile(unittest.TestCase):
    def test_clean_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.html",
                         '<label for="a">A</label>'
                         '<input type="text" id="a" name="a">')
            bad, err = checker.check_file(path)
            self.assertEqual((bad, err), ([], None))

    def test_bad_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", '<input type="text" name="a">')
            bad, err = checker.check_file(path)
            self.assertIsNone(err)
            self.assertEqual(len(bad), 1)

    def test_missing_file_reports_error(self):
        bad, err = checker.check_file("/nonexistent/page.html")
        self.assertEqual(bad, [])
        self.assertIsNotNone(err)

    def test_non_utf8_file_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", b'<input name="a\xff">')
            bad, err = checker.check_file(path)
            self.assertEqual(bad, [])
            self.assertEqual(err, "not valid UTF-8")

    def test_input_file_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = '<input type="text" name="a">'
            path = write(tmp, "bad.html", text)
            checker.check_file(path)
            self.assertEqual(Path(path).read_text(), text)


class TestCollectFiles(unittest.TestCase):
    def test_direct_file_any_name_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "page.txt", '<input name="a">')
            self.assertEqual(checker.collect_files([path]), [path])

    def test_folder_walk_finds_html_and_htm_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", "")
            b = write(tmp, "sub/b.htm", "")
            write(tmp, "c.md", "")
            write(tmp, "d.txt", "")
            got = checker.collect_files([tmp])
            self.assertEqual(got, sorted([a, b]))

    def test_git_folder_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, ".git/hooks/sample.html", "")
            a = write(tmp, "a.html", "")
            self.assertEqual(checker.collect_files([tmp]), [a])

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", "")
            write(tmp, "sub/b.html", "")
            self.assertEqual(
                checker.collect_files([tmp], recursive=False), [a])

    def test_exclude_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", "")
            write(tmp, "skip.html", "")
            got = checker.collect_files([tmp], exclude=["skip.html"])
            self.assertEqual(got, [a])

    def test_missing_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            checker.collect_files(["/nonexistent/path"])

    def test_duplicates_deduped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.html", "")
            self.assertEqual(
                checker.collect_files([path, path]), [path])


class TestRun(unittest.TestCase):
    def test_clean_run_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.html",
                         '<label for="a">A</label>'
                         '<input type="text" id="a" name="a">')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 0)
            self.assertIn(
                "OK — 1 file(s) checked, every form control has a label.",
                out)

    def test_dirty_run_exit_1_and_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", '<input type="text" name="a">')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            # CWD-robust: assert on the file name and message, never
            # on the absolute path the CLI echoes.
            self.assertIn("bad.html", out)
            self.assertIn('<input type="text" name="a"> line 1 has no label',
                          out)
            self.assertIn("Checked 1 file(s), 1 problem(s) in 1 file(s).",
                          out)

    def test_select_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html",
                         '<select id="country" name="country"></select>')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("bad.html", out)
            self.assertIn('<select id="country"> line 1 has no label', out)

    def test_textarea_line_without_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html",
                         '<textarea name="message"></textarea>')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("bad.html", out)
            self.assertIn('<textarea name="message"> line 1 has no label',
                          out)

    def test_control_without_id_or_name_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", '<input type="text">')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("bad.html", out)
            self.assertIn('<input type="text"> line 1 has no label', out)

    def test_duplicate_id_second_control_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = ('<input type="text" id="dup" name="first">\n'
                    '<input type="text" id="dup" name="second">\n'
                    '<label for="dup">Duplicate</label>')
            path = write(tmp, "bad.html", html)
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn('<input type="text" id="dup"> line 2 has no label',
                          out)
            self.assertNotIn("line 1 has no label", out)

    def test_folder_summary_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "good.html",
                  '<label for="a">A</label>'
                  '<input type="text" id="a" name="a">')
            write(tmp, "bad.html", '<input type="text" name="a">')
            code, out, _ = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 2 file(s), 1 problem(s) in 1 file(s).",
                          out)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html",
                         '<input type="text" name="a">\n'
                         '<select id="b" name="b"></select>')
            code, out, _ = run_cli(["--json", path])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertEqual(data["checked"], 1)
            self.assertEqual(data["problems"], 2)
            self.assertEqual(
                os.path.basename(data["files"][0]["path"]), "bad.html")
            self.assertEqual(data["files"][0]["controls"][0]["tag"], "input")
            self.assertEqual(data["files"][0]["controls"][0]["name"], "a")
            self.assertEqual(data["files"][0]["controls"][1]["tag"], "select")
            self.assertEqual(data["files"][0]["controls"][1]["id"], "b")
            self.assertIsNone(data["files"][0]["error"])

    def test_stdin_clean(self):
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO("")
            code, out, _ = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 0)
        self.assertIn(
            "OK — 1 file(s) checked, every form control has a label.",
            out)

    def test_stdin_dirty_via_main(self):
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO('<input type="text" name="a">')
            code, out, _ = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 1)
        self.assertIn(
            'FAIL <stdin>: <input type="text" name="a"> line 1 has no label',
            out)

    def test_stdin_with_paths_is_usage_error(self):
        code, _, err = run_cli(["--stdin", "x.html"])
        self.assertEqual(code, 2)
        self.assertIn("--stdin takes no file", err)

    def test_no_paths_is_usage_error(self):
        code, _, err = run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("at least one HTML file", err)

    def test_missing_path_exit_2(self):
        code, _, err = run_cli(["/nonexistent/page.html"])
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_empty_folder_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli([tmp])
            self.assertEqual(code, 2)
            self.assertIn("no HTML files found", err)

    def test_bad_flag_exit_2(self):
        code, _, _ = run_cli(["--nope"])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("html_label_checker 1.0.0", out)

    def test_non_utf8_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", b'<input name="a\xff">')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("not valid UTF-8", out)


class TestExamples(unittest.TestCase):
    def test_run_example_output_matches_sample(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        expected = (REPO / "examples/sample-output.md").read_text()
        self.assertEqual(result.stdout, expected)

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO / "README.md").read_text()
        good = subprocess.run(
            [sys.executable, "src/html_label_checker.py",
             "examples/good.html"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0)
        self.assertIn(good.stdout.strip(), readme)
        bad = subprocess.run(
            [sys.executable, "src/html_label_checker.py",
             "examples/bad.html"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn(bad.stdout.strip(), readme)
        folder = subprocess.run(
            [sys.executable, "src/html_label_checker.py",
             "examples/"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(folder.returncode, 1)
        self.assertIn("Checked 3 file(s), 5 problem(s) in 1 file(s).",
                      folder.stdout)
        self.assertIn("Checked 3 file(s), 5 problem(s) in 1 file(s).",
                      readme)
        js = subprocess.run(
            [sys.executable, "src/html_label_checker.py",
             "--json", "examples/bad.html"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(js.returncode, 1)
        self.assertIn(js.stdout.strip(), readme)


class TestHygiene(unittest.TestCase):
    def _repo_files(self):
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__")]
            for name in files:
                if name.endswith(".pyc"):
                    continue
                yield Path(root) / name

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "FIXME", "XXX"]
        hits = []
        for path in self._repo_files():
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="ignore")
            for word in banned:
                if word in text:
                    hits.append("%s: %s" % (path.name, word))
        self.assertEqual(hits, [])

    def test_no_absolute_paths(self):
        hits = []
        for path in self._repo_files():
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="ignore")
            for marker in ("/home/", "/Users/", "C:\\"):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_no_secrets(self):
        hits = []
        for path in self._repo_files():
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="ignore").lower()
            for marker in ("api_key", "api-key", "password", "secret=",
                           "token="):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_stdlib_imports_only(self):
        import ast
        src = REPO / "src/html_label_checker.py"
        tree = ast.parse(src.read_text())
        stdlib = set(sys.stdlib_module_names)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(imported - stdlib, imported)
        self.assertNotIn("yaml", imported)

    def test_gitignore_lists_env_first(self):
        lines = (REPO / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (REPO / ".github/workflows/ci.yml").read_text()
        self.assertIn("tests/test_html_label_checker.py", ci)
        self.assertIn("ubuntu-latest", ci)
        self.assertIn("3.12", ci)
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)


if __name__ == "__main__":
    unittest.main()
