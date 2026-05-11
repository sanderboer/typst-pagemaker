import os
import sys
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker as pm
from pagemaker.parser import OrgElement


class TestColumnsParser(unittest.TestCase):
    def test_columns_parsed(self):
        el = OrgElement('test', 'body', 'Title', props={'COLUMNS': '2'})
        ir = el.to_ir()
        self.assertEqual(ir['columns'], 2)

    def test_columns_default_none(self):
        el = OrgElement('test', 'body', 'Title', props={})
        ir = el.to_ir()
        self.assertIsNone(ir['columns'])

    def test_columns_invalid(self):
        el = OrgElement('test', 'body', 'Title', props={'COLUMNS': 'abc'})
        ir = el.to_ir()
        self.assertIsNone(ir['columns'])

    def test_column_gap_parsed(self):
        el = OrgElement('test', 'body', 'Title', props={'COLUMN_GAP': '5'})
        ir = el.to_ir()
        self.assertEqual(ir['column_gap'], 5.0)

    def test_column_gap_with_mm_suffix(self):
        el = OrgElement('test', 'body', 'Title', props={'COLUMN_GAP': '5mm'})
        ir = el.to_ir()
        self.assertEqual(ir['column_gap'], 5.0)

    def test_column_gap_default_none(self):
        el = OrgElement('test', 'body', 'Title', props={})
        ir = el.to_ir()
        self.assertIsNone(ir['column_gap'])

    def test_columns_only_on_text_types(self):
        el = OrgElement('test', 'rectangle', 'Title', props={'COLUMNS': '2'})
        ir = el.to_ir()
        self.assertIsNone(ir['columns'])

    def test_columns_on_header(self):
        el = OrgElement('test', 'header', 'Title', props={'COLUMNS': '3'})
        ir = el.to_ir()
        self.assertEqual(ir['columns'], 3)

    def test_columns_on_subheader(self):
        el = OrgElement('test', 'subheader', 'Title', props={'COLUMNS': '2', 'COLUMN_GAP': '4'})
        ir = el.to_ir()
        self.assertEqual(ir['columns'], 2)
        self.assertEqual(ir['column_gap'], 4.0)


class TestColumnsGenerator(unittest.TestCase):
    def make_ir(self, columns=None, column_gap=None, text='Hello World'):
        props = {}
        if columns is not None:
            props['COLUMNS'] = str(columns)
        if column_gap is not None:
            props['COLUMN_GAP'] = column_gap
        return {
            'meta': {},
            'pages': [
                {
                    'title': 'P',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [
                        {
                            'id': 't',
                            'type': 'body',
                            'area': {'x': 1, 'y': 1, 'w': 6, 'h': 4},
                            'z': 10,
                            'text_blocks': [{'kind': 'plain', 'content': text}],
                            'style': None,
                            'columns': columns,
                            'column_gap': column_gap,
                        }
                    ],
                }
            ],
        }

    def test_no_columns_no_wrap(self):
        ir = self.make_ir(columns=None)
        typst = pm.generate_typst(ir)
        self.assertNotIn('#columns(', typst)

    def test_single_column_no_wrap(self):
        ir = self.make_ir(columns=1)
        typst = pm.generate_typst(ir)
        self.assertNotIn('#columns(', typst)

    def test_two_columns_wraps(self):
        ir = self.make_ir(columns=2)
        typst = pm.generate_typst(ir)
        self.assertIn('#columns(2)[', typst)

    def test_three_columns_wraps(self):
        ir = self.make_ir(columns=3)
        typst = pm.generate_typst(ir)
        self.assertIn('#columns(3)[', typst)

    def test_columns_with_gap(self):
        ir = self.make_ir(columns=2, column_gap=5.0)
        typst = pm.generate_typst(ir)
        self.assertIn('#columns(2, gutter: 5mm)[', typst)

    def test_columns_with_text_content(self):
        ir = self.make_ir(columns=2, text='Col1 text\n\nCol2 text')
        typst = pm.generate_typst(ir)
        self.assertIn('#columns(2)[', typst)
        self.assertIn('Col1 text', typst)
        self.assertIn('Col2 text', typst)

    def test_columns_with_legacy_text(self):
        ir = self.make_ir(columns=2, text='Single paragraph')
        typst = pm.generate_typst(ir)
        self.assertIn('#columns(2)[', typst)


if __name__ == '__main__':
    unittest.main()
