#!/usr/bin/env python3
"""Ensure no literal square brackets are emitted around helpers in text.
This guards against accidentally double-wrapping text blocks that cause
Typst to render literal '[' or ']' in the output.
"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker as pm


class TestNoLiteralBracketsAroundHelpers(unittest.TestCase):
    def test_body_text_with_helpers(self):
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
                            'area': {'x': 1, 'y': 1, 'w': 3, 'h': 1},
                            'z': 10,
                            'text_blocks': [
                                {'kind': 'plain', 'content': 'Today is #date_yy_mm_dd'}
                            ],
                            'style': None,
                        },
                        {
                            'id': 'h',
                            'type': 'header',
                            'area': {'x': 1, 'y': 2, 'w': 3, 'h': 1},
                            'z': 10,
                            'text_blocks': [{'kind': 'plain', 'content': '#date_iso'}],
                            'style': None,
                        },
                        {
                            'id': 's',
                            'type': 'subheader',
                            'area': {'x': 1, 'y': 3, 'w': 3, 'h': 1},
                            'z': 10,
                            'text_blocks': [
                                {'kind': 'plain', 'content': 'Page #page_no / #page_total'}
                            ],
                            'style': None,
                        },
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        # Core text emitters should be single-layer: #text(...)[...]
        self.assertIn('#text(font: "Inter")[Today is #date_yy_mm_dd]', typst)
        self.assertIn('#text(font: "Inter", weight: "bold", size: 24pt)[#date_iso]', typst)
        self.assertIn(
            '#text(font: "Inter", weight: "semibold", size: 18pt)[Page #page_no / #page_total]',
            typst,
        )
        # No nested literal content blocks like [[#text(...)[...]]]
        self.assertNotIn('[[#text', typst)

        # Check for ]]] only in page content, not in template functions
        lines = typst.split('\n')
        in_content = False
        content_lines = []
        for line in lines:
            if 'BEGIN PAGE CONTENT' in line:
                in_content = True
                continue
            elif 'END PAGE CONTENT' in line:
                in_content = False
                continue
            elif in_content:
                content_lines.append(line)

        page_content = '\n'.join(content_lines)
        self.assertNotIn(']]]', page_content)


if __name__ == '__main__':
    unittest.main()
