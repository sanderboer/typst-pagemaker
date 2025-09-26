#!/usr/bin/env python3
import unittest, os, sys

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import pagemaker as pm

class TestSingleTypstPageSetting(unittest.TestCase):
    def test_generate_typst_emits_single_page_set(self):
        ir = {
            'meta': {},
            'pages': [
                {
                    'id': 'p1', 'title': 'One',
                    'page_size': {'w_mm': 210, 'h_mm': 297},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [
                        {'id': 't1', 'type': 'body', 'area': {'x':1,'y':1,'w':2,'h':1}, 'z': 10,
                         'text_blocks': [{'kind':'plain','content':'Hello'}]},
                    ],
                },
                {
                    'id': 'p2', 'title': 'Two',
                    'page_size': {'w_mm': 210, 'h_mm': 297},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [
                        {'id': 't2', 'type': 'body', 'area': {'x':3,'y':2,'w':2,'h':1}, 'z': 10,
                         'text_blocks': [{'kind':'plain','content':'World'}]},
                    ],
                },
            ]
        }
        t = pm.generate_typst(ir)
        # Ensure exactly one document-level page setting is emitted
        self.assertEqual(t.count('#set page('), 1, msg=t)

if __name__ == '__main__':
    unittest.main()
