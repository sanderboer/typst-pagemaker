#!/usr/bin/env python3
"""Ensure minimal ColorRect form when no stroke/radius provided"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker as pm


class TestRectangleMinimalColorRect(unittest.TestCase):
    def test_minimal_colorrect_without_optional_args(self):
        ir = {
            'meta': {},
            'pages': [
                {
                    'title': 'RectMinimal',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 6, 'rows': 6},
                    'elements': [
                        {
                            'id': 'r1',
                            'type': 'rectangle',
                            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
                            'z': 1,
                            'rectangle': {'color': '#00ff00', 'alpha': 0.75},
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        # Should emit the compact call with only color + alpha
        self.assertIn('ColorRect("#00ff00", 0.75)', typst)
        # Specifically ensure the placed element uses the minimal call without optional args
        self.assertIn('#layer_grid(gp,1,1,2,2, ColorRect("#00ff00", 0.75))', typst)


if __name__ == '__main__':
    unittest.main()
