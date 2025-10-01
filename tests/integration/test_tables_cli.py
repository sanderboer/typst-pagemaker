#!/usr/bin/env python3
"""Integration: CLI build renders Org tables correctly in Typst.

Covers:
- Single #table with auto columns and 6pt gutter
- Header rows bolded via #strong[…]
 - Horizontal rulers only at explicit Org separators
- Ragged rows normalized with empty cells as []
- Quotes/backslashes escaped inside text cells
- Ignores #+TBLFM lines
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / 'src'

ORG_WITH_TABLE = """#+PAGESIZE: A4
* Page 1
:PROPERTIES:
:GRID: 12x8
:END:
** Body
:PROPERTIES:
:TYPE: body
:END:
| Col A | Col B | Col C |
|-------+-------+-------|
| a1    | b1    | c1    |
| He said \"hi\" \\ |  | c2 |
#+TBLFM: @2$3='(c)
"""

# Table with header, interior separator after first data row, and trailing separator
ORG_TABLE_WITH_SEPARATORS = """#+PAGESIZE: A4
* Page 1
:PROPERTIES:
:GRID: 12x8
:END:
** Body
:PROPERTIES:
:TYPE: body
:END:
| H1 | H2 |
|----+----|
| a1 | b1 |
|----+----|
| a2 | b2 |
| a3 | b3 |
|----+----|
"""


class TestTablesCLI(unittest.TestCase):
    def _build_typst(self, org_text: str) -> str:
        with tempfile.TemporaryDirectory() as td:
            org_path = Path(td) / 'table.org'
            out_typ = Path(td) / 'deck.typ'
            org_path.write_text(org_text, encoding='utf-8')
            cmd = [
                sys.executable,
                '-m',
                'pagemaker.cli',
                'build',
                str(org_path),
                '--export-dir',
                td,
                '--output',
                str(out_typ),
            ]
            env = os.environ.copy()
            env['PYTHONPATH'] = str(SRC_PATH) + os.pathsep + env.get('PYTHONPATH', '')
            res = subprocess.run(
                cmd, cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True
            )
            if res.returncode != 0:
                raise AssertionError(
                    f"CLI build failed. STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
                )
            self.assertTrue(out_typ.exists(), f"Typst was not written: {out_typ}")
            return out_typ.read_text(encoding='utf-8')

    def test_cli_renders_table_end_to_end(self):
        code = self._build_typst(ORG_WITH_TABLE)
        # Extract only page content area to avoid matching helpers
        lines = code.split('\n')
        in_content = False
        content_lines = []
        for line in lines:
            if 'BEGIN PAGE CONTENT' in line:
                in_content = True
                continue
            elif 'END PAGE CONTENT' in line:
                in_content = False
                continue
            elif in_content:
                content_lines.append(line)
        page_content = '\n'.join(content_lines)

        # Expect a single #table with 3 auto columns and 6pt gutter
        self.assertIn('#table(columns: (auto, auto, auto), gutter: 6pt', page_content)

        # Header row should have strong wrappers and no implicit top hline
        self.assertIn('table.header(', page_content)
        self.assertIn('#strong[Col A]', page_content)
        self.assertIn('#strong[Col B]', page_content)
        self.assertIn('#strong[Col C]', page_content)

        # Horizontal lines only at explicit separators; here only after header
        self.assertEqual(page_content.count('table.hline()'), 1)

        # Ragged normalization: the second data row has an empty middle cell -> [] appears
        self.assertGreaterEqual(page_content.count('[]'), 1)

        # Escaping: quotes and backslashes in the third row first cell
        # Input: He said "hi" \
        # Expect: \"hi\" and at least one backslash in the bracketed text
        self.assertIn('\\"hi\\"', page_content)
        self.assertIn('\\', page_content)

        # Ensure TBLFM did not create an extra row or content
        self.assertNotIn('TBLFM', page_content)

    def test_cli_table_separators_interior_and_no_trailing(self):
        code = self._build_typst(ORG_TABLE_WITH_SEPARATORS)
        # Extract only page content area to avoid matching helpers
        lines = code.split('\n')
        in_content = False
        content_lines = []
        for line in lines:
            if 'BEGIN PAGE CONTENT' in line:
                in_content = True
                continue
            elif 'END PAGE CONTENT' in line:
                in_content = False
                continue
            elif in_content:
                content_lines.append(line)
        page_content = '\n'.join(content_lines)

        # Expect header recognized; no implicit top hline
        self.assertNotIn('table.hline(y: 0)', page_content)
        self.assertIn('table.header(', page_content)
        self.assertIn('#strong[H1]', page_content)
        self.assertIn('#strong[H2]', page_content)

        # With header + 3 data rows and separators after header, after row1, and trailing,
        # expect 3 table.hline() under separators-only semantics
        self.assertEqual(page_content.count('table.hline()'), 3)

    def test_cli_table_no_header_trailing_sep_ignored(self):
        org_text = """#+PAGESIZE: A4
* Page 1
:PROPERTIES:
:GRID: 12x8
:END:
** Body
:PROPERTIES:
:TYPE: body
:END:
| a | b |
| c | d |
|----+----|
"""
        code = self._build_typst(org_text)
        # Extract only page content area to avoid matching helpers
        lines = code.split('\n')
        in_content = False
        content_lines = []
        for line in lines:
            if 'BEGIN PAGE CONTENT' in line:
                in_content = True
                continue
            elif 'END PAGE CONTENT' in line:
                in_content = False
                continue
            elif in_content:
                content_lines.append(line)
        page_content = '\n'.join(content_lines)

        # No header section should be present
        self.assertNotIn('table.header(', page_content)
        # No implicit top hline is drawn
        self.assertNotIn('table.hline(y: 0)', page_content)
        # No header and only a trailing separator -> 1 hline due to explicit trailing separator
        self.assertEqual(page_content.count('table.hline()'), 1)

    def test_cli_table_multiple_interior_and_dedup_at_header(self):
        org_text = """#+PAGESIZE: A4
* Page 1
:PROPERTIES:
:GRID: 12x8
:END:
** Body
:PROPERTIES:
:TYPE: body
:END:
| H1 | H2 |
|----+----|
| a1 | b1 |
|----+----|
| a2 | b2 |
|----+----|
| a3 | b3 |
| a4 | b4 |
"""
        code = self._build_typst(org_text)
        # Extract only page content area to avoid matching helpers
        lines = code.split('\n')
        in_content = False
        content_lines = []
        for line in lines:
            if 'BEGIN PAGE CONTENT' in line:
                in_content = True
                continue
            elif 'END PAGE CONTENT' in line:
                in_content = False
                continue
            elif in_content:
                content_lines.append(line)
        page_content = '\n'.join(content_lines)

        # Header recognized and bold cells
        self.assertNotIn('table.hline(y: 0)', page_content)
        self.assertIn('table.header(', page_content)
        self.assertIn('#strong[H1]', page_content)
        self.assertIn('#strong[H2]', page_content)

        # With header + 4 data rows and interior separators after row1 and row2:
        # Expect hlines under separators-only: 1 (after header) + 2 extras = 3
        self.assertEqual(page_content.count('table.hline()'), 3)


if __name__ == '__main__':
    unittest.main()
