#!/usr/bin/env python3
import os
import sys
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker as pm


class TestParagraphs(unittest.TestCase):
    def test_paragraph_splitting_blank_and_markers(self):
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
                                {'kind': 'plain', 'content': 'One\n\n---\nTwo\n\n:::\nThree'}
                            ],
                            'style': None,
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        # Three paragraphs -> three par wrappers; default par() since no options
        self.assertIn('#par()[', typst)
        self.assertGreaterEqual(typst.count('#par('), 3)

    def test_paragraph_style_options_and_justify_override(self):
        ir = {
            'meta': {
                'STYLE_BODY': 'font: Inter, justify: false, leading: 1.4em, spacing: 1em, first-line-indent: 2em, hanging-indent: 1em, linebreaks: loose',
            },
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
                                {'kind': 'plain', 'content': 'Lorem ipsum dolor sit amet.'}
                            ],
                            'style': None,
                            'justify': True,  # element-level override should win over style's justify: false
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        # Should emit par(...) with style-driven paragraph options and justify: true (override)
        self.assertIn('#par(', typst)
        self.assertIn('leading: 1.4em', typst)
        self.assertIn('spacing: 1em', typst)
        self.assertIn('first-line-indent: 2em', typst)
        self.assertIn('hanging-indent: 1em', typst)
        self.assertIn('linebreaks: loose', typst)
        self.assertIn('justify: true', typst)
        self.assertNotIn('justify: false', typst)


if __name__ == '__main__':
    unittest.main()
