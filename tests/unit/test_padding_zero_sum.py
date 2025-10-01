#!/usr/bin/env python3
"""Tests for zero-sum padding inheritance and generator emission

Scenario: Document-level PADDING: 5 and element-level PADDING: -5
should cancel to 0 on all sides for both text and rectangle elements.
"""

import os
import sys
import unittest
from textwrap import dedent

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker as pm


class TestZeroSumPadding(unittest.TestCase):
    def test_zero_sum_padding_for_text_and_rectangle(self):
        org = dedent(
            """
            #+PADDING: 5,5,5,5
            #+GRID: 6x6

            * Page
            :PROPERTIES:
            :ID: p1
            :END:

            ** Text
            :PROPERTIES:
            :TYPE: body
            :AREA: A1,A1
            :PADDING: -5,-5,-5,-5
            :END:
            Hello

            ** Rectangle
            :PROPERTIES:
            :TYPE: rectangle
            :COLOR: #000
            :AREA: A2,A2
            :PADDING: -5,-5,-5,-5
            :END:
            """
        ).strip()

        # Write to a temp file and parse
        import tempfile

        with tempfile.TemporaryDirectory() as tmpd:
            org_path = os.path.join(tmpd, 'doc.org')
            with open(org_path, 'w', encoding='utf-8') as f:
                f.write(org)
            ir = pm.parse_org(org_path)

        pages = ir['pages']
        self.assertEqual(len(pages), 1)
        elements = pages[0]['elements']
        # Expect two elements (text + rectangle)
        self.assertEqual(len(elements), 2)

        text = next(e for e in elements if e['type'] == 'body')
        rect = next(e for e in elements if e['type'] == 'rectangle')

        expected_zero = {'top': 0.0, 'right': 0.0, 'bottom': 0.0, 'left': 0.0}
        self.assertEqual(text['padding_mm'], expected_zero)
        self.assertEqual(rect['padding_mm'], expected_zero)

        # Generator should emit padded placement with 0mm on all sides
        typst = pm.generate_typst(ir)
        # Text at A1 -> (x=1,y=1,w=1,h=1)
        self.assertIn("#layer_grid_padded", typst)
        self.assertIn("gp,1,1,1,1", typst)
        self.assertIn(" 0.0mm, 0.0mm, 0.0mm, 0.0mm", typst)
        # Rectangle at A2 -> (x=2,y=1,w=1,h=1)
        self.assertIn("gp,2,1,1,1", typst)


if __name__ == '__main__':
    unittest.main()
