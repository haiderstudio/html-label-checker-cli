# html-label-checker-cli

Check every form control in HTML files has an associated label, fail CI when one does not.

[![CI](https://github.com/haiderstudio/html-label-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/html-label-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`html_label_checker` reads HTML files and finds every
form control with no associated label — a `<label
for="id">` naming its id, or a `<label>` wrapped around
it — and reports each one with the file and the line
number. It exits 1 when any control is unlabeled, so it
can fail a CI run. A file where every control has a
label exits 0.

- A form field with no label is unusable for a screen
  reader user and unclickable by its text for everyone
  else: the words next to the field do nothing when you
  click them, and the field announces itself as nothing
  at all. It is the most common accessibility failure on
  the web, and nothing stops you shipping a form like
  that — this catches it before the page ships.
- It checks `<input>` (except hidden, submit, button,
  and reset — those take no label), `<select>`, and
  `<textarea>`. An `<input>` with no `type` is treated
  as a text input and checked.
- A label may come before or after its control: a
  `<label for="id">` counts wherever it sits in the
  document. Uppercase tags and attributes (`INPUT`,
  `LABEL FOR`) count the same as lowercase ones.
- A label whose `for` names an id no control carries is
  not flagged: this tool checks controls have labels,
  not that labels point at real controls. That is a
  different check.
- Two controls sharing one id are a different problem
  (duplicate ids), so a label for that id counts only
  for the first control carrying it — the second one is
  still reported.
- An `aria-label` or `aria-labelledby` is not counted
  as a label here: this tool checks for a real
  `<label>` element, the visible words a person clicks
  on.
- A file given directly on the command line is always
  checked, whatever its name. A folder is walked for
  `.html` and `.htm` files, recursively by default
  (`--no-recursive` stops at the top level). `.git`
  folders are never walked, and directory links are never
  followed.
- `--json` prints the result as JSON, and `--stdin`
  checks one HTML document read from standard input.

## Who it is for

Anyone who owns a website with a form — front-end
developers, teams that review each other's templates,
and anyone whose pages carry forms added by hand or by
a CMS. A signup form, a contact form, a search box:
if a person has to type into it, it needs a label.

## What it does NOT do

- It does not check images. That is repo #30,
  image-alt-checker-cli, which checks `<img>` alt text
  — form labels are a different check on the same
  pages.
- It does not check whether a label points at a real
  control. A `<label for="ghost">` with no control
  carrying `id="ghost"` is left alone — the orphan
  label is a different check.
- It does not check duplicate ids as its own report.
  A duplicated id only shows up here when the second
  control carrying it has no label of its own. Repo
  #60, html-duplicate-id-checker-cli, checks duplicate
  ids directly.
- It does not check whether a label's words are good
  — `Name` and `Field 1` both pass. Whether the label
  text makes sense is a human judgement.
- It does not fetch a live site, and it never rewrites
  a file. It is report-only, and it never touches the
  network.

## How this differs

- The big accessibility engines (axe-core and friends)
  check labels as one rule among dozens and need a
  browser or Node to run. This is a tested standard
  library CLI that checks local files directly — a
  different, smaller job: one check, no browser, no
  install, in a CI gate. The same broad-vs-narrow
  pattern let repo #27, heading-order-checker-cli,
  stand against axe-core.
- The field is empty for this job: a fresh search of
  GitHub on Nov 11, 2026 found 0 results for
  `"html-label-checker-cli"` and 1 result for `html
  form label checker` — a login-strength checker
  built with HTML, not a label checker. No rival
  checks form labels with a CI gate.

## Install

```sh
git clone https://github.com/haiderstudio/html-label-checker-cli.git
cd html-label-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one HTML file:

```sh
python3 src/html_label_checker.py page.html
```

A file where every form control has a label passes:

```sh
$ python3 src/html_label_checker.py examples/good.html
OK — 1 file(s) checked, every form control has a label.
```

A file with unlabeled controls fails, with the control
and line for each one:

```sh
$ python3 src/html_label_checker.py examples/bad.html
FAIL examples/bad.html: <input type="text" id="name"> line 8 has no label
FAIL examples/bad.html: <select id="country"> line 10 has no label
FAIL examples/bad.html: <textarea name="message"> line 13 has no label
FAIL examples/bad.html: <input type="text" id="dup"> line 15 has no label
FAIL examples/bad.html: <input type="email" name="email"> line 18 has no label
Checked 1 file(s), 5 problem(s) in 1 file(s).
```

Check a whole folder (HTML files only):

```sh
$ python3 src/html_label_checker.py examples/
FAIL examples/bad.html: <input type="text" id="name"> line 8 has no label
FAIL examples/bad.html: <select id="country"> line 10 has no label
FAIL examples/bad.html: <textarea name="message"> line 13 has no label
FAIL examples/bad.html: <input type="text" id="dup"> line 15 has no label
FAIL examples/bad.html: <input type="email" name="email"> line 18 has no label
Checked 3 file(s), 5 problem(s) in 1 file(s).
```

Check one document from standard input:

```sh
$ python3 src/html_label_checker.py --stdin < examples/bad.html
FAIL <stdin>: <input type="text" id="name"> line 8 has no label
FAIL <stdin>: <select id="country"> line 10 has no label
FAIL <stdin>: <textarea name="message"> line 13 has no label
FAIL <stdin>: <input type="text" id="dup"> line 15 has no label
FAIL <stdin>: <input type="email" name="email"> line 18 has no label
Checked 1 file(s), 5 problem(s) in 1 file(s).
```

Machine-readable output:

```sh
$ python3 src/html_label_checker.py --json examples/bad.html
{
  "files": [
    {
      "path": "examples/bad.html",
      "controls": [
        {
          "line": 8,
          "tag": "input",
          "type": "text",
          "id": "name",
          "name": "name",
          "wrapped": false
        },
        {
          "line": 10,
          "tag": "select",
          "type": null,
          "id": "country",
          "name": "country",
          "wrapped": false
        },
        {
          "line": 13,
          "tag": "textarea",
          "type": null,
          "id": null,
          "name": "message",
          "wrapped": false
        },
        {
          "line": 15,
          "tag": "input",
          "type": "text",
          "id": "dup",
          "name": "second",
          "wrapped": false
        },
        {
          "line": 18,
          "tag": "input",
          "type": "email",
          "id": null,
          "name": "email",
          "wrapped": false
        }
      ],
      "error": null
    }
  ],
  "checked": 1,
  "problems": 5
}
```

Exit codes: 0 when every form control has a label, 1
when any control is unlabeled or a file cannot be
read, 2 for a usage error (a missing path, a bad flag,
or no HTML files found).

## Examples

A label pointing at the wrong id does not save the
control — the input on line 8 of `examples/bad.html`
has `id="name"` but the label says `for="other"`, so
it fails. The second control sharing `id="dup"` on
line 15 fails too, even though the label for `dup`
covers the first one on line 14. And the label for
`ghost` on line 17 points at nothing, so it saves
nobody — the email input on line 18 still fails:

```sh
$ python3 src/html_label_checker.py examples/bad.html
FAIL examples/bad.html: <input type="text" id="name"> line 8 has no label
FAIL examples/bad.html: <select id="country"> line 10 has no label
FAIL examples/bad.html: <textarea name="message"> line 13 has no label
FAIL examples/bad.html: <input type="text" id="dup"> line 15 has no label
FAIL examples/bad.html: <input type="email" name="email"> line 18 has no label
Checked 1 file(s), 5 problem(s) in 1 file(s).
```

Both ways of labelling pass — the `for` label and the
wrapping label in `examples/good.html` — and so do the
controls that take no label: the hidden input and the
submit, button, and reset inputs are skipped. The
uppercase `INPUT` and `LABEL FOR` on lines 20–21 pass
as well, because the label comes after its control and
that still counts:

```sh
$ python3 src/html_label_checker.py examples/good.html
OK — 1 file(s) checked, every form control has a label.
```

Run every bundled example at once with `sh
examples/run-example.sh` — the output is saved in
[examples/sample-output.md](examples/sample-output.md).

## How it is tested

```sh
python3 tests/test_html_label_checker.py
```

The tests cover label matching (a `for` label before
and after its control, a wrapping label, a label for a
different id fails, a label for an id no control
carries is not flagged, an `aria-label` alone does not
count, uppercase tags and attributes, a control with
no id and no label fails, duplicate ids where only
the first is covered), the controls themselves
(checkbox and radio need labels, an input with no type
is treated as text, hidden, submit, button, and reset
inputs are ignored, `select` and `textarea` are
covered, a self-closing input, a control inside a
comment or a `<script>` is ignored, unclosed tags and
malformed HTML are tolerated, an empty document, a
document with no controls), the check itself (controls
reported in document order, each with the right line,
tag, type, id, and name, clean files pass), the CLI
(exit 0/1/2, folder walking, `.html` and `.htm` only,
`.git` skipped, `--no-recursive`, `--exclude`, a direct
file checked even without an HTML name, `--stdin`,
`--json` output, `--version`, bad flags, missing paths,
empty folders, a non-UTF-8 file reported, input files
left unchanged), the bundled examples (sample output
compared byte-for-byte against a fresh run, and the
README-quoted outputs checked against it), and
hygiene checks (no placeholder text, no absolute
paths, no secrets, standard library imports only,
`.env` first in `.gitignore`, CI file runs the test
file).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The
idea of checking form labels is not new — it is the
most common accessibility rule there is — but no
existing tool does this one job as a tested
command-line gate on local files, as the search above
shows, and every line of code here is original, built
on nothing but Python's standard library.
