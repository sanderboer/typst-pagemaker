#!/usr/bin/env python3
"""Tests for rectangle padding handling in generator"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker as pm


class TestRectanglePaddingEmission(unittest.TestCase):
    def make_ir(self, pad=None):
        return {
            'meta': {},
            'pages': [
                {
                    'title': 'RectPad',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 6, 'rows': 6},
                    'elements': [
                        {
                            'id': 'rect1',
                            'type': 'rectangle',
                            'area': {'x': 2, 'y': 2, 'w': 3, 'h': 2},
                            'z': 1,
                            'rectangle': {'color': '#ff0000', 'alpha': 0.5},
                            'padding_mm': pad,
                        }
                    ],
                }
            ],
        }

    def test_rectangle_emits_layer_grid_padded_when_padding_present(self):
        pad = {"top": 4.0, "right": 3.0, "bottom": 2.0, "left": 1.0}
        ir = self.make_ir(pad)
        typst = pm.generate_typst(ir)
        # Should place rectangle with padded layer helper
        self.assertIn("#layer_grid_padded", typst)
        self.assertIn("gp,2,2,3,2", typst)
        self.assertIn(" 4.0mm, 3.0mm, 2.0mm, 1.0mm", typst)
        # Should render rectangle content via ColorRect
        self.assertIn("ColorRect(\"#ff0000\", 0.5)", typst)

    def test_rectangle_emits_plain_layer_when_no_padding(self):
        ir = self.make_ir(pad=None)
        typst = pm.generate_typst(ir)
        self.assertIn("#layer_grid(gp,2,2,3,2", typst)
        self.assertIn("ColorRect(\"#ff0000\", 0.5)", typst)


if __name__ == '__main__':
    unittest.main()
