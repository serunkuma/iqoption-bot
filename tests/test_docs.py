"""Tests for the documentation checker."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.check_docs import (
    BROKEN_LINK,
    MISSING_STATUS,
    ORPHAN,
    check_docs,
    format_report,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class DocsCheckerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def minimal(self, body: str = "") -> None:
        self.write(
            "docs/index.md",
            "# Index\n\nStatus: Current\n\n- [Guide](guide.md)\n",
        )
        self.write("docs/guide.md", f"# Guide\n\nStatus: Current\n\n{body}\n")

    def test_clean_tree_has_no_issues(self) -> None:
        self.minimal()
        report = check_docs(self.root)
        self.assertTrue(report.ok)
        self.assertEqual(2, report.files_checked)

    def test_missing_status_is_reported(self) -> None:
        self.write("docs/index.md", "# Index\n\nStatus: Current\n\n- [Guide](guide.md)\n")
        self.write("docs/guide.md", "# Guide\n\nNo label here.\n")

        report = check_docs(self.root)
        issues = report.of_kind(MISSING_STATUS)
        self.assertEqual(1, len(issues))
        self.assertEqual("docs/guide.md", issues[0].path)

    def test_broken_link_is_reported(self) -> None:
        self.minimal("[Gone](missing.md)\n")
        report = check_docs(self.root)
        issues = report.of_kind(BROKEN_LINK)
        self.assertEqual(1, len(issues))
        self.assertEqual("docs/guide.md", issues[0].path)
        self.assertEqual("missing.md", issues[0].detail)

    def test_external_anchor_and_mailto_links_are_ignored(self) -> None:
        self.minimal(
            "[Site](https://example.com) [Top](#guide) [Mail](mailto:a@b.test)\n"
        )
        report = check_docs(self.root)
        self.assertTrue(report.ok)

    def test_orphan_doc_is_reported(self) -> None:
        self.minimal()
        self.write("docs/extra.md", "# Extra\n\nStatus: Current\n")

        report = check_docs(self.root)
        issues = report.of_kind(ORPHAN)
        self.assertEqual(1, len(issues))
        self.assertEqual("docs/extra.md", issues[0].path)

    def test_repository_documentation_is_clean(self) -> None:
        report = check_docs(REPOSITORY_ROOT)
        self.assertGreaterEqual(report.files_checked, 40)
        self.assertTrue(report.ok, "\n".join(format_report(report)))


if __name__ == "__main__":
    unittest.main()
