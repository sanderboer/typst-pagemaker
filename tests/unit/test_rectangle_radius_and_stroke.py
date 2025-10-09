#!/usr/bin/env python3
"""Tests for rectangle radius emission and stroke fallback behavior."""

import os
import sys
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import pagemaker as pm


class TestRectangleRadiusAndStroke(unittest.TestCase):
    def test_radius_only_emits_radius_argument(self):
        ir = {
            'meta': {},
            'pages': [
                {
                    'title': 'RadiusOnly',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 4, 'rows': 4},
                    'elements': [
                        {
                            'id': 'r1',
                            'type': 'rectangle',
                            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
                            'z': 1,
                            'rectangle': {'color': '#101010', 'alpha': 0.75, 'radius': '5mm'},
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        # Expect stroke: none placeholders when only radius provided
        self.assertIn(
            'ColorRect("#101010", 0.75, stroke: none, stroke_color: none, radius: "5mm")', typst
        )

    def test_radius_with_stroke(self):
        ir = {
            'meta': {},
            'pages': [
                {
                    'title': 'RadiusStroke',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 4, 'rows': 4},
                    'elements': [
                        {
                            'id': 'r2',
                            'type': 'rectangle',
                            'area': {'x': 2, 'y': 2, 'w': 2, 'h': 2},
                            'z': 1,
                            'rectangle': {
                                'color': '#222222',
                                'alpha': 0.5,
                                'stroke': '2pt',
                                'stroke_color': '#333333',
                                'radius': '3pt',
                            },
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        self.assertIn(
            'ColorRect("#222222", 0.5, stroke: "2pt", stroke_color: "#333333", radius: "3pt")',
            typst,
        )

    def test_stroke_color_fallback_to_fill(self):
        # stroke provided but no stroke_color => fallback to fill color
        ir = {
            'meta': {},
            'pages': [
                {
                    'title': 'StrokeFallback',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 4, 'rows': 4},
                    'elements': [
                        {
                            'id': 'r3',
                            'type': 'rectangle',
                            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
                            'z': 1,
                            'rectangle': {
                                'color': '#abcdef',
                                'alpha': 1.0,
                                'stroke': '1pt',
                                'radius': '2mm',
                            },
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        # Expect stroke_color equals fill color (#abcdef)
        self.assertIn(
            'ColorRect("#abcdef", 1.0, stroke: "1pt", stroke_color: "#abcdef", radius: "2mm")',
            typst,
        )


if __name__ == '__main__':
    unittest.main()
