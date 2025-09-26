#!/usr/bin/env python3
"""Tests for JUSTIFY toggle on text and padding on images/PDF/SVG"""
import unittest
import sys
import os

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker as pm


class TestTextJustifyAndImagePadding(unittest.TestCase):
    def test_text_justify_flag(self):
        ir = {
            'meta': {},
            'pages': [{
                'title': 'P',
                'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                'grid': {'cols': 12, 'rows': 8},
                'elements': [{
                    'id': 'h', 'type': 'header',
                    'area': {'x': 1, 'y': 1, 'w': 3, 'h': 1},
                    'z': 10,
                    'text_blocks': [{'kind': 'plain', 'content': 'Title'}],
                    'style': None,
                    'justify': True,
                },{
                    'id': 'b', 'type': 'body',
                    'area': {'x': 1, 'y': 2, 'w': 4, 'h': 2},
                    'z': 10,
                    'text_blocks': [{'kind': 'plain', 'content': 'Lorem ipsum'}],
                    'style': None,
                    'justify': True,
                }]
            }]
        }
        typst = pm.generate_typst(ir)
        # Should wrap text in a justified paragraph
        self.assertIn('#par(justify: true)', typst)

    def test_padding_on_figure_svg_pdf(self):
        pad = {"top": 1.0, "right": 2.0, "bottom": 3.0, "left": 4.0}
        ir = {
            'meta': {},
            'pages': [{
                'title': 'P',
                'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                'grid': {'cols': 12, 'rows': 8},
                'elements': [
                    {'id': 'f', 'type': 'figure', 'area': {'x':1,'y':1,'w':3,'h':2}, 'z': 10, 'figure': {'src': 'examples/assets/test-images/kittens/kitten-1.jpg', 'caption': None, 'fit': 'contain'}, 'padding_mm': pad},
                    {'id': 's', 'type': 'svg', 'area': {'x':4,'y':1,'w':3,'h':2}, 'z': 10, 'svg': {'src': 'examples/assets/test-svgs/test-plan-p11.svg', 'scale': 1.0}, 'padding_mm': pad},
                    {'id': 'p', 'type': 'pdf', 'area': {'x':7,'y':1,'w':3,'h':2}, 'z': 10, 'pdf': {'src': 'test-pdfs/test-plan.pdf', 'pages': [1], 'scale': 1.0}, 'padding_mm': pad},
                ]
            }]
        }
        typst = pm.generate_typst(ir)
        # All three should use the padded placement
        self.assertGreaterEqual(typst.count('#layer_grid_padded'), 3)
        self.assertIn(' 1.0mm, 2.0mm, 3.0mm, 4.0mm', typst)


if __name__ == '__main__':
    unittest.main()
