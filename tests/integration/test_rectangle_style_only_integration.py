#!/usr/bin/env python3
"""Integration tests for style-driven rectangles via parse_org -> generate_typst"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import pagemaker as pm


class TestRectangleStyleOnlyIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def _write_org(self, content: str) -> str:
        p = Path(self.temp_dir) / "style_only_rect.org"
        p.write_text(content, encoding="utf-8")
        return str(p)

    def test_style_only_rectangle_renders_with_style_values(self):
        org = """
#+TITLE: Style Only Rect
#+GRID: 12x8
#+STYLE_CALLOUT: color: #ff0000, alpha: 0.6, stroke: 5pt, stroke-color: #00ff00, radius: 10pt

* Page
** Box
:PROPERTIES:
:TYPE: rectangle
:STYLE: callout
:AREA: 1,1,3,2
:END:
""".strip()
        path = self._write_org(org)
        ir = pm.parse_org(path)
        typst = pm.generate_typst(ir)
        # Should render rectangle using style color/alpha and include stroke + radius
        self.assertIn(
            'ColorRect("#ff0000", 0.6, stroke: 5pt, stroke_color: "#00ff00", radius: 10pt)', typst
        )

    def test_style_only_rectangle_with_element_alpha_override(self):
        org = """
#+TITLE: Style Only Rect Alpha Override
#+GRID: 12x8
#+STYLE_PANEL: color: #123456, alpha: 0.8, stroke: 2pt, stroke-color: #abcdef

* Page
** Box
:PROPERTIES:
:TYPE: rectangle
:STYLE: panel
:AREA: 2,2,4,3
:ALPHA: 0.3
:END:
""".strip()
        path = self._write_org(org)
        ir = pm.parse_org(path)
        typst = pm.generate_typst(ir)
        # Element alpha should override style alpha; stroke from style should be present
        self.assertIn('ColorRect("#123456", 0.3, stroke: 2pt, stroke_color: "#abcdef")', typst)


if __name__ == '__main__':
    unittest.main()
