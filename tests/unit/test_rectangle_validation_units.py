#!/usr/bin/env python3
"""Tests validating stroke and radius unit errors at style and element levels."""

import os
import sys
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import pagemaker.validation as pv


class TestRectangleValidationUnits(unittest.TestCase):
    def test_invalid_style_stroke_and_radius_units(self):
        ir = {
            'meta': {
                'STYLE_BAD': 'color: #000, stroke: 5, radius: 10',  # missing units
            },
            'pages': [
                {
                    'id': 'p1',
                    'title': 'Page',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 1, 'rows': 1},
                    'elements': [],
                }
            ],
        }
        res = pv.validate_ir(ir)
        msgs = [i.message for i in res.issues if i.severity == 'error']
        self.assertTrue(any('stroke' in m for m in msgs))
        self.assertTrue(any('radius' in m for m in msgs))
        self.assertFalse(res.ok())

    def test_invalid_element_stroke_and_radius_units(self):
        ir = {
            'meta': {},
            'pages': [
                {
                    'id': 'p1',
                    'title': 'Page',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 2, 'rows': 2},
                    'elements': [
                        {
                            'id': 'r1',
                            'type': 'rectangle',
                            'area': {'x': 1, 'y': 1, 'w': 1, 'h': 1},
                            'z': 1,
                            'rectangle': {
                                'color': '#333333',
                                'alpha': 0.5,
                                'stroke': '2',
                                'radius': '4',
                            },  # missing units
                        }
                    ],
                }
            ],
        }
        res = pv.validate_ir(ir)
        msgs = [i.message for i in res.issues if i.severity == 'error']
        self.assertTrue(any('Stroke length' in m for m in msgs))
        self.assertTrue(any('Radius length' in m for m in msgs))
        self.assertFalse(res.ok())


if __name__ == '__main__':
    unittest.main()
