#!/usr/bin/env python3
import os
import sys
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker as pm


class TestCustomStyles(unittest.TestCase):
    def test_meta_style_overrides_core_types(self):
        ir = {
            'meta': {
                'STYLE_HEADER': 'font: Shree714, weight: 900, size: 30pt, color: #ff00aa',
                'STYLE_BODY': 'font: Inter, color: rgb(50%,50%,50%)',
            },
            'pages': [
                {
                    'title': 'P',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [
                        {
                            'id': 'h',
                            'type': 'header',
                            'area': {'x': 1, 'y': 1, 'w': 6, 'h': 1},
                            'z': 10,
                            'text_blocks': [{'kind': 'plain', 'content': 'My Header'}],
                            'style': None,
                        },
                        {
                            'id': 'b',
                            'type': 'body',
                            'area': {'x': 1, 'y': 2, 'w': 6, 'h': 1},
                            'z': 10,
                            'text_blocks': [{'kind': 'plain', 'content': 'Body text'}],
                            'style': None,
                        },
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        self.assertIn(
            '#text(font: "Shree714", weight: 900, size: 30pt, fill: rgb("#ff00aa"))[My Header]',
            typst,
        )
        self.assertIn('#text(font: "Inter", fill: rgb(50%,50%,50%))[Body text]', typst)

    def test_custom_named_style_and_element_style_reference(self):
        ir = {
            'meta': {
                'STYLE_HERO': 'font: Inter, weight: bold, size: 36pt, color: #123456',
            },
            'pages': [
                {
                    'title': 'P',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [
                        {
                            'id': 'hero',
                            'type': 'body',
                            'area': {'x': 1, 'y': 1, 'w': 12, 'h': 2},
                            'z': 10,
                            'text_blocks': [{'kind': 'plain', 'content': 'Big Title'}],
                            'style': 'hero',
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        self.assertIn(
            '#text(font: "Inter", weight: "bold", size: 36pt, fill: rgb("#123456"))[Big Title]',
            typst,
        )


if __name__ == '__main__':
    unittest.main()
