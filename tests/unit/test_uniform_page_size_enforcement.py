#!/usr/bin/env python3
import unittest, os, sys

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import pagemaker as pm
from pagemaker.validation import validate_ir

class TestUniformPageSizeEnforcement(unittest.TestCase):
    def test_validation_errors_on_mixed_page_sizes(self):
        ir = {
            'meta': {},
            'pages': [
                {
                    'id': 'p1', 'title': 'One',
                    'page_size': {'w_mm': 210, 'h_mm': 297},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [
                        {'id': 't1', 'type': 'body', 'area': {'x':1,'y':1,'w':1,'h':1}, 'z': 10, 'text_blocks': [{'kind':'plain','content':'Hello'}]},
                    ],
                },
                {
                    'id': 'p2', 'title': 'Two',
                    'page_size': {'w_mm': 297, 'h_mm': 210},  # different size
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [
                        {'id': 't2', 'type': 'body', 'area': {'x':1,'y':1,'w':1,'h':1}, 'z': 10, 'text_blocks': [{'kind':'plain','content':'World'}]},
                    ],
                },
            ]
        }
        res = validate_ir(ir)
        msgs = "\n".join(f"{i.severity}:{i.path}:{i.message}" for i in res.issues)
        self.assertIn('error', msgs)
        self.assertIn('Uniform page size required', msgs)
        # Path should reference a page_size on some page (likely second)
        self.assertIn('/pages/', msgs)
        self.assertIn('/page_size', msgs)

if __name__ == '__main__':
    unittest.main()
