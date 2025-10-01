#!/usr/bin/env python3
"""Unit tests for Typst table rendering"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker.generator as gen


class TestTableRendering(unittest.TestCase):
    def test_basic_structure_and_header_bold(self):
        table = {
            'kind': 'table',
            'rows': [
                ['Col A', 'Col B'],
                ['a1', 'b1'],
            ],
            'header_rows': 1,
        }
        out = gen._render_table_block(table, 'font: "Inter"')
        # One Typst table with columns and gutter
        self.assertIn('#table(columns: (auto, auto), gutter: 6pt', out)
        # Header section present; no implicit top hline
        self.assertIn('table.header(', out)
        # Header cells are bolded
        self.assertIn('#strong[Col A]', out)
        self.assertIn('#strong[Col B]', out)
        # Data cells are not bolded
        self.assertNotIn('#strong[a1]', out)
        self.assertNotIn('#strong[b1]', out)
        # Horizontal lines only at explicit separators; none provided here
        self.assertEqual(out.count('table.hline()'), 0)

    def test_ragged_rows_are_normalized_with_empty_cells(self):
        table = {
            'kind': 'table',
            'rows': [
                ['a', 'b', 'c'],
                ['1', '2'],
                ['x'],
            ],
            'header_rows': 1,
        }
        out = gen._render_table_block(table, 'font: "Inter"')
        # Header row complete -> no [] from header, subsequent rows: 1 + 2 empty cells
        self.assertEqual(out.count('[]'), 3)
        # Columns tuple has three autos
        self.assertIn('#table(columns: (auto, auto, auto), gutter: 6pt', out)

    def test_escaping_of_quotes_and_backslashes(self):
        table = {
            'kind': 'table',
            'rows': [
                ['He said "hi" \\'],
            ],
            'header_rows': 0,
        }
        out = gen._render_table_block(table, 'font: "Inter"')
        # Quotes and backslashes are escaped in Typst text context
        self.assertIn('\\"hi\\"', out)
        # One trailing backslash in input becomes two in output
        self.assertIn('\\\\', out)

    def test_empty_cells_render_to_empty_blocks(self):
        table = {
            'kind': 'table',
            'rows': [
                ['a', '', 'c'],
                ['', '', ''],
            ],
            'header_rows': 1,
        }
        out = gen._render_table_block(table, '')  # no style args
        # Header includes bolded first cell, and one empty header cell -> []
        self.assertIn('#strong[a]', out)
        # Total empty cells: one in header + three in second row
        self.assertEqual(out.count('[]'), 4)

    def test_interior_separator_emits_extra_rule_and_no_trailing(self):
        # Header + 3 data rows; separators at header boundary, after row1, and trailing
        table = {
            'kind': 'table',
            'rows': [
                ['H1', 'H2'],
                ['a1', 'b1'],
                ['a2', 'b2'],
                ['a3', 'b3'],
            ],
            'header_rows': 1,
            'separators': [1, 2, 4],
        }
        out = gen._render_table_block(table, 'font: "Inter"')
        # Expect three hlines at explicit separators: after header, after row1, and trailing
        self.assertEqual(out.count('table.hline()'), 3)

    def test_trailing_separator_is_ignored_without_header(self):
        # No header; 2 rows; under separators-only semantics the explicit trailing separator yields one hline
        table = {
            'kind': 'table',
            'rows': [
                ['a', 'b'],
                ['c', 'd'],
            ],
            'header_rows': 0,
            'separators': [2],
        }
        out = gen._render_table_block(table, 'font: "Inter"')
        # Only the natural boundary between the two rows should be present
        self.assertEqual(out.count('table.hline()'), 1)


if __name__ == '__main__':
    unittest.main()
