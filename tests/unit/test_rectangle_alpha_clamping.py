#!/usr/bin/env python3
"""Tests for rectangle alpha clamping behavior in generation."""

import os
import sys
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import pagemaker as pm


class TestRectangleAlphaClamping(unittest.TestCase):
    def make_ir(self, alpha_value):
        return {
            'meta': {},
            'pages': [
                {
                    'title': 'AlphaClamp',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 2, 'rows': 2},
                    'elements': [
                        {
                            'id': f'rect_{alpha_value}',
                            'type': 'rectangle',
                            'area': {'x': 1, 'y': 1, 'w': 1, 'h': 1},
                            'z': 1,
                            'rectangle': {'color': '#000000', 'alpha': alpha_value},
                        }
                    ],
                }
            ],
        }

    def extract_alpha_call(self, typst):
        # Return the first ColorRect call substring for inspection
        import re

        m = re.search(r'ColorRect\("#000000", ([0-9]+\.?[0-9]*)', typst)
        return m.group(1) if m else None

    def test_alpha_below_zero_clamped(self):
        ir = self.make_ir(-0.4)
        typst = pm.generate_typst(ir)
        self.assertIn('ColorRect("#000000", 0.0)', typst)

    def test_alpha_above_one_clamped(self):
        ir = self.make_ir(2.5)
        typst = pm.generate_typst(ir)
        self.assertIn('ColorRect("#000000", 1.0)', typst)

    def test_alpha_valid_passes_through(self):
        ir = self.make_ir(0.45)
        typst = pm.generate_typst(ir)
        self.assertIn('ColorRect("#000000", 0.45)', typst)

    def test_alpha_non_numeric_defaults_to_one(self):
        ir = self.make_ir("notanumber")
        typst = pm.generate_typst(ir)
        # Non-numeric becomes 1.0 internally
        self.assertIn('ColorRect("#000000", 1.0)', typst)


if __name__ == '__main__':
    unittest.main()
