#!/usr/bin/env python3
"""Check every form control in HTML files has an associated label.

Run: python3 src/html_label_checker.py page.html
     python3 src/html_label_checker.py site/
     python3 src/html_label_checker.py --stdin < page.html

A form field with no label is unusable for a screen reader
user and unclickable by its text for everyone else: the
words next to the field do nothing when you click them,
and the field announces itself as nothing at all. It is
the most common accessibility failure on the web, and it
happens because nothing stops you shipping a form where
the label is missing, or where the label points at the
wrong field. This tool finds every unlabeled control
before the page ships, instead of after a reader hits it.

It reads one or more HTML files, records every form
control — <input> except hidden, submit, button, and
reset, plus <select> and <textarea> — with its line
number, and reports each one with no associated label,
with the file and the line. A control counts as labelled
when a <label for="id"> names its id, or when a <label>
wraps around it. It exits 1 when any control is
unlabeled, so it can fail a CI run. A file where every
control has a label exits 0.

A label whose "for" names an id that no control carries
is not this tool's job and is not flagged: this tool
checks controls have labels, not that labels point at
real controls. Two controls sharing one id are a
different problem (duplicate ids), so a label for that
id counts only for the first control carrying it — the
second one is still reported. A control with no id and
no wrapping label is reported. An aria-label or
aria-labelledby is not counted as a label here: this
tool checks for a real <label> element, the visible
words a person clicks on.

It never rewrites a file, never touches the network, and
reads only the files and folders you point it at.
"""

import argparse
import fnmatch
import json
import os
import sys
from html.parser import HTMLParser
from pathlib import Path

__version__ = "1.0.0"

HTML_EXTENSIONS = {".html", ".htm"}

CONTROL_TAGS = {"input", "select", "textarea"}

IGNORED_INPUT_TYPES = {"hidden", "submit", "button", "reset"}

VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class _LabelCollector(HTMLParser):
    """Collect controls and label targets from one document."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.controls = []
        self.label_for_ids = set()
        self._stack = []

    def handle_starttag(self, tag, attrs):
        values = {name: value for name, value in attrs}
        if tag == "label":
            target = values.get("for")
            if target:
                self.label_for_ids.add(target)
        if tag in CONTROL_TAGS:
            if tag == "input":
                input_type = (values.get("type") or "text").strip().lower()
                if input_type in IGNORED_INPUT_TYPES:
                    return
            line, _ = self.getpos()
            self.controls.append({
                "line": line,
                "tag": tag,
                "type": values.get("type") if tag == "input" else None,
                "id": values.get("id"),
                "name": values.get("name"),
                "wrapped": "label" in self._stack,
            })
        if tag not in VOID_ELEMENTS:
            self._stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in self._stack:
            while self._stack and self._stack[-1] != tag:
                self._stack.pop()
            self._stack.pop()


def find_unlabeled_controls(text):
    """Return a list of form controls with no associated label.

    Each entry is {"line": int, "tag": "input"/"select"/
    "textarea", "type": str or None, "id": str or None,
    "name": str or None}. Entries are in document order.
    Controls with a <label for="id"> naming their id, or
    wrapped in a <label>, are not listed.
    """
    collector = _LabelCollector()
    collector.feed(text)
    collector.close()
    seen_ids = set()
    bad = []
    for control in collector.controls:
        if control["wrapped"]:
            continue
        control_id = control["id"]
        if control_id:
            if control_id in seen_ids:
                # A duplicate id: the label points at the first
                # control carrying it, so this one is unlabeled.
                bad.append(control)
                continue
            seen_ids.add(control_id)
            if control_id in collector.label_for_ids:
                continue
        bad.append(control)
    return bad


def check_text(text, path):
    """Check one document's text. Returns (bad controls, error)."""
    try:
        return find_unlabeled_controls(text), None
    except Exception as exc:  # a malformed document must fail, not crash
        return [], "could not parse: %s" % exc


def check_file(path):
    """Check one file. Returns (bad controls, error)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [], "not valid UTF-8"
    except OSError as exc:
        return [], str(exc)
    return check_text(text, str(path))


def _is_html_file(path):
    return Path(path).suffix.lower() in HTML_EXTENSIONS


def collect_files(paths, recursive=True, exclude=None):
    """Expand CLI paths into a sorted list of HTML files to check.

    A file given directly is always checked, whatever its name. A
    folder is walked for .html/.htm files. .git folders are never
    walked, and directory links are never followed.
    """
    exclude = exclude or []
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            found.append(str(path))
        elif path.is_dir():
            for root, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = [
                    d for d in dirs
                    if d != ".git"
                    and not any(fnmatch.fnmatch(d, pat) for pat in exclude)
                ]
                for name in files:
                    candidate = Path(root) / name
                    if not _is_html_file(candidate):
                        continue
                    if any(
                        fnmatch.fnmatch(str(candidate), pat)
                        or fnmatch.fnmatch(name, pat)
                        for pat in exclude
                    ):
                        continue
                    found.append(str(candidate))
                if not recursive:
                    break
        else:
            raise FileNotFoundError("no such file or folder: %s" % raw)
    seen = set()
    unique = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return sorted(unique)


def describe_control(control):
    """A short readable form of one control, like <input type="text" id="name">."""
    parts = [control["tag"]]
    if control["type"] is not None:
        parts.append('type="%s"' % control["type"])
    if control["id"]:
        parts.append('id="%s"' % control["id"])
    elif control["name"]:
        parts.append('name="%s"' % control["name"])
    return "<%s>" % " ".join(parts)


def format_problem(path, control):
    """One human-readable line for one unlabeled control."""
    return "FAIL %s: %s line %d has no label" % (
        path, describe_control(control), control["line"])


def run(paths, recursive=True, exclude=None, as_json=False):
    """Check paths, print the report, return the exit code."""
    try:
        files = collect_files(paths, recursive=recursive, exclude=exclude)
    except FileNotFoundError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if not files:
        print("error: no HTML files found", file=sys.stderr)
        return 2
    results = []
    problems = 0
    files_with_problems = 0
    for path in files:
        bad, error = check_file(path)
        count = len(bad) + (1 if error else 0)
        if count:
            problems += count
            files_with_problems += 1
        results.append({"path": path, "controls": bad, "error": error})
    if as_json:
        print(json.dumps(
            {"files": results, "checked": len(files),
             "problems": problems},
            indent=2))
    else:
        for result in results:
            if result["error"]:
                print("FAIL %s: %s" % (result["path"], result["error"]))
            for control in result["controls"]:
                print(format_problem(result["path"], control))
        if problems:
            print("Checked %d file(s), %d problem(s) in %d file(s)."
                  % (len(files), problems, files_with_problems))
        else:
            print("OK — %d file(s) checked, every form control has "
                  "a label." % len(files))
    return 1 if problems else 0


def run_stdin(as_json=False):
    """Check one HTML document read from standard input."""
    text = sys.stdin.read()
    bad, error = check_text(text, "<stdin>")
    problems = len(bad) + (1 if error else 0)
    if as_json:
        print(json.dumps(
            {"files": [{"path": "<stdin>", "controls": bad,
                        "error": error}],
             "checked": 1, "problems": problems},
            indent=2))
    else:
        if error:
            print("FAIL <stdin>: %s" % error)
        for control in bad:
            print(format_problem("<stdin>", control))
        if problems:
            print("Checked 1 file(s), %d problem(s) in 1 file(s)." % problems)
        else:
            print("OK — 1 file(s) checked, every form control has "
                  "a label.")
    return 1 if problems else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="html_label_checker",
        description="Check every form control in HTML files has an "
                    "associated label, fail CI when one does not.")
    parser.add_argument("paths", nargs="*", help="HTML files or folders")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk into subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        help="skip files or folders matching this pattern "
                             "(repeatable)")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON")
    parser.add_argument("--stdin", action="store_true",
                        help="check one HTML document from standard input")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)
    if args.stdin:
        if args.paths:
            parser.error("--stdin takes no file or folder arguments")
        return run_stdin(as_json=args.json)
    if not args.paths:
        parser.error("give at least one HTML file or folder")
    return run(args.paths, recursive=not args.no_recursive,
               exclude=args.exclude, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
