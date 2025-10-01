#!/usr/bin/env python3
"""Unit tests for Org table parsing"""

import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import pagemaker as pm


class TestTableParsing(unittest.TestCase):
    def _write_org(self, body: str) -> str:
        fd, path = tempfile.mkstemp(suffix='.org')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write("#+PAGESIZE: A4\n")
            f.write("* Page 1\n")
            f.write(":PROPERTIES:\n:GRID: 12x8\n:END:\n")
            f.write("** Section\n")
            f.write(":PROPERTIES:\n:TYPE: body\n:END:\n")
            f.write(body)
        return path

    def test_simple_table_with_header_separator(self):
        body = "| Col A | Col B |\n|-------+-------|\n| a1    | b1    |\n| a2    | b2    |\n"
        path = self._write_org(body)
        try:
            ir = pm.parse_org(path)
            pages = ir['pages']
            self.assertEqual(len(pages), 1)
            el = pages[0]['elements'][0]
            blocks = el['text_blocks']
            self.assertEqual(len(blocks), 1)
            tb = blocks[0]
            self.assertEqual(tb['kind'], 'table')
            self.assertEqual(tb['header_rows'], 1)
            self.assertEqual(tb['rows'][0], ['Col A', 'Col B'])
            self.assertEqual(tb['rows'][1], ['a1', 'b1'])
            self.assertEqual(tb['rows'][2], ['a2', 'b2'])
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

    def test_table_without_header(self):
        body = "| a | b |\n| c | d |\n"
        path = self._write_org(body)
        try:
            ir = pm.parse_org(path)
            tb = ir['pages'][0]['elements'][0]['text_blocks'][0]
            self.assertEqual(tb['header_rows'], 0)
            self.assertEqual(tb['rows'], [['a', 'b'], ['c', 'd']])
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

    def test_ragged_rows_are_preserved_in_parser(self):
        # Parser keeps ragged; generator normalizes for rendering
        body = "| a | b | c |\n|---+---+---|\n| 1 | 2 |\n| 3 | 4 | 5 | 6 |\n"
        path = self._write_org(body)
        try:
            ir = pm.parse_org(path)
            tb = ir['pages'][0]['elements'][0]['text_blocks'][0]
            self.assertEqual(tb['header_rows'], 1)
            self.assertEqual(tb['rows'][0], ['a', 'b', 'c'])
            self.assertEqual(tb['rows'][1], ['1', '2'])
            self.assertEqual(tb['rows'][2], ['3', '4', '5', '6'])
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

    def test_tblfm_is_ignored(self):
        body = "| a | b |\n#+TBLFM: @2$2=@2$1 * 2\n| 1 | 2 |\n"
        path = self._write_org(body)
        try:
            ir = pm.parse_org(path)
            tb = ir['pages'][0]['elements'][0]['text_blocks'][0]
            # Should parse as two data rows; formulas ignored
            self.assertEqual(tb['header_rows'], 0)
            self.assertEqual(tb['rows'], [['a', 'b'], ['1', '2']])
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

    def test_empty_cells(self):
        body = "| a |  | c |\n|---+--+---|\n|  | x |  |\n"
        path = self._write_org(body)
        try:
            ir = pm.parse_org(path)
            tb = ir['pages'][0]['elements'][0]['text_blocks'][0]
            self.assertEqual(tb['header_rows'], 1)
            self.assertEqual(tb['rows'][0], ['a', '', 'c'])
            self.assertEqual(tb['rows'][1], ['', 'x', ''])
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

    def test_parser_records_multiple_and_duplicate_separators(self):
        body = (
            "| H1 | H2 |\n"
            "|----+----|\n"  # header separator
            "| a1 | b1 |\n"
            "|----+----|\n"  # interior separator after first data row
            "| a2 | b2 |\n"
            "| a3 | b3 |\n"
            "|----+----|\n"  # trailing separator (should be recorded but later ignored in rendering)
        )
        path = self._write_org(body)
        try:
            ir = pm.parse_org(path)
            tb = ir['pages'][0]['elements'][0]['text_blocks'][0]
            self.assertEqual(tb['header_rows'], 1)
            # Separators positions are recorded as "after the Nth parsed row"
            # After header -> 1, after first data row -> 2, after all rows -> 4
            self.assertEqual(tb.get('separators'), [1, 2, 4])
            # Rows captured (header + 3 data rows)
            self.assertEqual(len(tb['rows']), 4)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

    def test_trailing_separator_without_header_is_ignored(self):
        body = "| a | b |\n| c | d |\n|----+----|\n"
        path = self._write_org(body)
        try:
            ir = pm.parse_org(path)
            tb = ir['pages'][0]['elements'][0]['text_blocks'][0]
            self.assertEqual(tb['header_rows'], 0)
            self.assertEqual(tb['rows'], [['a', 'b'], ['c', 'd']])
            # Parser still records trailing separator position after 2 rows
            self.assertEqual(tb.get('separators'), [2])
        finally:
            try:
                os.remove(path)
            except Exception:
                pass


if __name__ == '__main__':
    unittest.main()
