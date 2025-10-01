#!/usr/bin/env python3
import os
import sys
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker as pm


class TestHardBreaksAndListSpacing(unittest.TestCase):
    def test_hard_newline_with_trailing_backslash_single_paragraph(self):
        ir = {
            'meta': {},
            'pages': [
                {
                    'title': 'P',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [
                        {
                            'id': 'b',
                            'type': 'body',
                            'area': {'x': 1, 'y': 1, 'w': 6, 'h': 2},
                            'z': 10,
                            'text_blocks': [
                                {'kind': 'plain', 'content': 'First line \\\nSecond line'},
                            ],
                            'style': None,
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        # Should emit a hard line break within the same paragraph
        self.assertIn('#linebreak()', typst)
        # Optimization path: single paragraph without par args should not wrap in #par()
        self.assertNotIn('#par(', typst)

    def test_ul_list_spacing_zero_without_par_args(self):
        ir = {
            'meta': {},
            'pages': [
                {
                    'title': 'List',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [
                        {
                            'id': 'l1',
                            'type': 'body',
                            'area': {'x': 1, 'y': 1, 'w': 6, 'h': 2},
                            'z': 10,
                            'text_blocks': [
                                {
                                    'kind': 'list',
                                    'type': 'ul',
                                    'items': [
                                        {'text': 'Item one'},
                                        {'text': 'Item two'},
                                    ],
                                    'tight': True,
                                }
                            ],
                            'style': None,
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        # Each list item should enforce hanging indent and spacing matching lineheight
        self.assertIn('hanging-indent: 1.2em', typst)
        self.assertIn('spacing: 1.2em', typst)
        # Specifically when no par_args the combined args should start with hanging-indent
        self.assertIn('#par(hanging-indent: 1.2em, spacing: 1.2em)', typst)

    def test_ol_list_spacing_zero_without_par_args(self):
        ir = {
            'meta': {},
            'pages': [
                {
                    'title': 'List',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [
                        {
                            'id': 'l2',
                            'type': 'body',
                            'area': {'x': 1, 'y': 1, 'w': 6, 'h': 2},
                            'z': 10,
                            'text_blocks': [
                                {
                                    'kind': 'list',
                                    'type': 'ol',
                                    'items': [
                                        {'text': 'First'},
                                        {'text': 'Second'},
                                    ],
                                    'tight': True,
                                    'start': 1,
                                    'style': '1',
                                }
                            ],
                            'style': None,
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        self.assertIn('hanging-indent: 1.5em', typst)
        self.assertIn('spacing: 1.2em', typst)
        self.assertIn('#par(hanging-indent: 1.5em, spacing: 1.2em)', typst)

    def test_ul_list_spacing_zero_with_par_args(self):
        ir = {
            'meta': {
                # Ensure par_args exist without adding its own spacing option
                'STYLE_BODY': 'font: Inter, leading: 1.2em',
            },
            'pages': [
                {
                    'title': 'List',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [
                        {
                            'id': 'l3',
                            'type': 'body',
                            'area': {'x': 1, 'y': 1, 'w': 6, 'h': 2},
                            'z': 10,
                            'text_blocks': [
                                {
                                    'kind': 'list',
                                    'type': 'ul',
                                    'items': [
                                        {'text': 'Alpha'},
                                        {'text': 'Beta'},
                                    ],
                                    'tight': True,
                                }
                            ],
                            'style': None,
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        # Should include leading from par_args, plus hanging-indent and spacing equals leading
        self.assertIn('#par(leading: 1.2em, hanging-indent: 1.2em, spacing: 1.2em)', typst)

    def test_ol_list_spacing_zero_with_par_args(self):
        ir = {
            'meta': {
                'STYLE_BODY': 'font: Inter, leading: 1em',
            },
            'pages': [
                {
                    'title': 'List',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [
                        {
                            'id': 'l4',
                            'type': 'body',
                            'area': {'x': 1, 'y': 1, 'w': 6, 'h': 2},
                            'z': 10,
                            'text_blocks': [
                                {
                                    'kind': 'list',
                                    'type': 'ol',
                                    'items': [
                                        {'text': 'One'},
                                        {'text': 'Two'},
                                    ],
                                    'tight': True,
                                    'start': 1,
                                    'style': '1',
                                }
                            ],
                            'style': None,
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        self.assertIn('#par(leading: 1em, hanging-indent: 1.5em, spacing: 1em)', typst)


if __name__ == '__main__':
    unittest.main()
