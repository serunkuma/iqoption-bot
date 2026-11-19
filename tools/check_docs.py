"""Documentation checker.

Keeps the documentation tree honest. Three rules are enforced:

1. Every markdown file under ``docs/`` carries a status label.
2. Every relative markdown link resolves to a file that exists.
3. Every markdown file under ``docs/`` is reachable from ``docs/index.md``.

Run it directly or through the entry point::

    .\\.venv\\Scripts\\python.exe tools\\check_docs.py
    .\\.venv\\Scripts\\python.exe runner.py docs-check

The checker only reads files and only imports the standard library, so it runs
in a bare environment and cannot be affected by the Windows LightGBM import
ordering.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: A status label must be a line of its own, with one of three values.
STATUS_LINE = re.compile(r"^Status: (Current|Planning|Historical)\s*$", re.MULTILINE)

#: ``[text](target)``; the text may contain nested brackets in rare cases, which
#: is acceptable because documentation links are simple in this repository.
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

#: Targets that are not files in this repository.
SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#")

ROOT_DOCS = ("README.md", "AGENTS.md", "RUNBOOK.md")
INDEX_DOC = Path("docs") / "index.md"

MISSING_STATUS = "missing status"
BROKEN_LINK = "broken link"
ORPHAN = "orphan doc"

ALL_KINDS = (MISSING_STATUS, BROKEN_LINK, ORPHAN)


@dataclass(frozen=True)
class Issue:
    """One documentation problem."""

    kind: str
    path: str
    detail: str


@dataclass
class Report:
    """Result of one documentation sweep."""

    files_checked: int = 0
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def of_kind(self, kind: str) -> list[Issue]:
        return [issue for issue in self.issues if issue.kind == kind]


def markdown_files(root: Path) -> list[Path]:
    """All markdown files that take part in the check."""

    files = sorted((root / "docs").glob("**/*.md"))
    for name in ROOT_DOCS:
        candidate = root / name
        if candidate.is_file():
            files.append(candidate)
    return files


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _iter_links(text: str):
    """Yield file targets, dropping external links, anchors, and empties."""

    for raw in LINK.findall(text):
        target = raw.split("#")[0].strip()
        if not target or target.startswith(SKIP_PREFIXES):
            continue
        yield target


def _orphan_issues(root: Path, files: list[Path]) -> list[Issue]:
    index = root / INDEX_DOC
    if not index.is_file():
        return [Issue(BROKEN_LINK, INDEX_DOC.as_posix(), "index file is missing")]

    linked = {
        (index.parent / target).resolve()
        for target in _iter_links(index.read_text(encoding="utf-8"))
    }
    docs_root = (root / "docs").resolve()
    issues: list[Issue] = []
    for path in files:
        resolved = path.resolve()
        if resolved == index.resolve() or not resolved.is_relative_to(docs_root):
            continue
        if resolved not in linked:
            issues.append(
                Issue(ORPHAN, _relative(path, root), "not linked from docs/index.md")
            )
    return issues


def check_docs(root: Path | str = ".") -> Report:
    """Sweep a repository and return every documentation problem found."""

    root = Path(root).resolve()
    report = Report()
    files = markdown_files(root)
    report.files_checked = len(files)

    for path in files:
        relative = _relative(path, root)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            report.issues.append(Issue(BROKEN_LINK, relative, f"unreadable: {exc}"))
            continue

        in_docs = relative.startswith("docs/")
        if in_docs and not STATUS_LINE.search(text):
            report.issues.append(
                Issue(MISSING_STATUS, relative, "no Status: Current|Planning|Historical")
            )

        for target in _iter_links(text):
            if not (path.parent / target).resolve().exists():
                report.issues.append(Issue(BROKEN_LINK, relative, target))

    report.issues.extend(_orphan_issues(root, files))
    return report


def format_report(report: Report) -> list[str]:
    """Render a report as printable lines, without a trailing newline."""

    lines = [f"files checked                : {report.files_checked}"]
    for kind in ALL_KINDS:
        issues = report.of_kind(kind)
        lines.append(f"{kind:<29}: {len(issues)}")
        for issue in issues:
            lines.append(f"  {issue.path}: {issue.detail}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_docs.py",
        description="Validate documentation status labels, links, and index coverage.",
    )
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    args = parser.parse_args(argv)

    report = check_docs(args.root)
    for line in format_report(report):
        print(line)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
