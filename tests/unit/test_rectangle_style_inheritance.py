#!/usr/bin/env python3
"""Tests for rectangle style inheritance and stroke overrides"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import pagemaker as pm


class TestRectangleStyleInheritance(unittest.TestCase):
    def test_style_applies_color_alpha(self):
        ir = {
            'meta': {'STYLE_CALLOUT': 'color: #112233, alpha: 0.4'},
            'pages': [
                {
                    'title': 'RectStyle',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 4, 'rows': 4},
                    'elements': [
                        {
                            'id': 'r1',
                            'type': 'rectangle',
                            'style': 'callout',
                            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
                            'z': 1,
                            'rectangle': {
                                'color': '#abcdef',
                                'alpha': 0.9,
                            },  # element overrides style
                        }
                    ],
                }
            ],
        }
        # Element color/alpha override style; expect element values in output
        typst = pm.generate_typst(ir)
        self.assertIn('ColorRect("#abcdef", 0.9)', typst)

    def test_style_only_applies_when_element_rect_omits_values(self):
        # Style provides color/alpha; element rectangle dict has no color/alpha
        ir = {
            'meta': {'STYLE_CALLOUT': 'color: #112233, alpha: 0.4'},
            'pages': [
                {
                    'title': 'RectStyleOnly',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 4, 'rows': 4},
                    'elements': [
                        {
                            'id': 'r1',
                            'type': 'rectangle',
                            'style': 'callout',
                            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
                            'z': 1,
                            # Non-empty dict to trigger rectangle rendering, but no color/alpha
                            'rectangle': {'stroke': ''},
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        # Expect style values used
        self.assertIn('ColorRect("#112233", 0.4)', typst)

    def test_style_stroke_and_color(self):
        ir = {
            'meta': {'STYLE_BOX': 'color: #001122, alpha: 0.6, stroke: 1pt, stroke-color: #ff00aa'},
            'pages': [
                {
                    'title': 'RectStroke',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 4, 'rows': 4},
                    'elements': [
                        {
                            'id': 'r2',
                            'type': 'rectangle',
                            'style': 'box',
                            'area': {'x': 2, 'y': 2, 'w': 2, 'h': 2},
                            'z': 1,
                            'rectangle': {'color': '#001122', 'alpha': 0.6},
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        # Should include stroke args in ColorRect call
        self.assertIn('ColorRect("#001122", 0.6, stroke: 1pt, stroke_color: "#ff00aa")', typst)

    def test_element_overrides_style_stroke(self):
        ir = {
            'meta': {
                'STYLE_PANEL': 'color: #123456, alpha: 0.3, stroke: 2pt, stroke-color: #00ff00'
            },
            'pages': [
                {
                    'title': 'RectOverride',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 4, 'rows': 4},
                    'elements': [
                        {
                            'id': 'r3',
                            'type': 'rectangle',
                            'style': 'panel',
                            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
                            'z': 1,
                            'rectangle': {
                                'color': '#123456',
                                'alpha': 0.3,
                                'stroke': '3pt',
                                'stroke_color': '#0000ff',
                            },
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        # Element overrides style stroke and stroke_color
        self.assertIn('ColorRect("#123456", 0.3, stroke: 3pt, stroke_color: "#0000ff")', typst)


if __name__ == '__main__':
    unittest.main()
