#!/usr/bin/env python3
"""Tests for AREA inheritance and cumulative PADDING percolation"""

import os
import sys
import unittest
from textwrap import dedent

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker as pm


class TestAreaAndPaddingInheritance(unittest.TestCase):
    def test_area_inheritance_and_cumulative_padding(self):
        # Meta padding + page no padding + group padding + element padding
        # AREA should percolate from group to descendants (including elements with TYPE none between)
        org = dedent(
            """
            #+PADDING: 10,10,10,10
            #+GRID: 8x6

            * Page
            :PROPERTIES:
            :ID: p1
            :END:

            ** Group
            :PROPERTIES:
            :TYPE: none
            :AREA: B2,C6
            :PADDING: 1,2,3,4
            :END:

            *** Rectangle
            :PROPERTIES:
            :TYPE: rectangle
            :COLOR: #000
            :END:

            *** Text
            :PROPERTIES:
            :TYPE: body
            :PADDING: 5,5,5,5
            :END:
            Hello
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
        # Expect two elements (rectangle + text)
        self.assertEqual(len(elements), 2)

        # Both should inherit AREA B2,C6 in total grid (rows=letters, cols=numbers). B2(row 2, col 2) to C6(row 3, col 6) => x=2,y=2,w=5,h=2
        expected_area = {'x': 2, 'y': 2, 'w': 5, 'h': 2}
        for el in elements:
            self.assertEqual(el['area'], expected_area)

        # Padding accumulation:
        # meta 10,10,10,10 + group 1,2,3,4 + element
        # Rectangle (no element padding): 11,12,13,14
        # Text (element 5,5,5,5): 16,17,18,19
        rect = next(e for e in elements if e['type'] == 'rectangle')
        text = next(e for e in elements if e['type'] == 'body')

        self.assertEqual(
            rect['padding_mm'], {'top': 11.0, 'right': 12.0, 'bottom': 13.0, 'left': 14.0}
        )
        self.assertEqual(
            text['padding_mm'], {'top': 16.0, 'right': 17.0, 'bottom': 18.0, 'left': 19.0}
        )


if __name__ == '__main__':
    unittest.main()
