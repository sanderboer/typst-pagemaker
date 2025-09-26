#!/usr/bin/env python3
"""Integration tests for SVG embedding, master pages, and margins behavior.

These tests do not require typst or external tools; they operate on IR and
generated Typst code to verify expected behaviors.
"""
import os
import sys
import unittest
import tempfile
import pathlib
import re

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import pagemaker as pm


class TestSVGMasterMarginsIntegration(unittest.TestCase):
    def test_svg_element_generates_image(self):
        org = (
            """#+TITLE: SVG Test\n\n* Slide\n:PROPERTIES:\n:ID: s1\n:END:\n\n** Vector\n:PROPERTIES:\n:TYPE: svg\n:AREA: 1,1,3,2\n:SVG: examples/assets/test-svgs/test-plan-p11.svg\n:END:\n"""
        )
        with tempfile.TemporaryDirectory() as td:
            org_path = pathlib.Path(td) / 'svg.org'
            org_path.write_text(org, encoding='utf-8')
            ir = pm.parse_org(str(org_path))
            t = pm.generate_typst(ir)
            self.assertIn('image("', t)
            self.assertIn('examples/assets/test-svgs/test-plan-p11.svg', t)
            self.assertIn('fit: "contain"', t)

    def test_master_pages_elements_included_and_master_page_not_rendered(self):
        org = (
            """#+TITLE: Master Test\n#+DEFAULT_MASTER: Base\n\n* Base Master (not rendered)\n:PROPERTIES:\n:MASTER_DEF: Base\n:END:\n\n** Head\n:PROPERTIES:\n:TYPE: subheader\n:AREA: A2,A11\n:END:\nMaster Head\n\n* Slide One\n:PROPERTIES:\n:ID: s1\n:END:\n\n** Title\n:PROPERTIES:\n:TYPE: header\n:AREA: B2,C11\n:END:\nSlide Title\n\n* Slide Two\n:PROPERTIES:\n:ID: s2\n:MASTER: Base\n:END:\n\n** Body\n:PROPERTIES:\n:TYPE: body\n:AREA: D2,G11\n:END:\nBody Text\n"""
        )
        with tempfile.TemporaryDirectory() as td:
            org_path = pathlib.Path(td) / 'm.org'
            org_path.write_text(org, encoding='utf-8')
            ir = pm.parse_org(str(org_path))
            t = pm.generate_typst(ir)
            # Two rendered pages (Slide One, Slide Two), master-def page skipped
            page_headers = len(re.findall(r"^// Page ", t, flags=re.M))
            self.assertEqual(page_headers, 2)
            # Master text appears on slides
            self.assertIn('Master Head', t)
            self.assertIn('Slide Title', t)
            self.assertIn('Body Text', t)

    def test_margins_offset_layer_coordinates(self):
        org = (
            """#+TITLE: Margins Test\n#+GRID: 3x3\n#+MARGINS: 5,0,0,5\n\n* Slide\n:PROPERTIES:\n:ID: s1\n:END:\n\n** Body\n:PROPERTIES:\n:TYPE: body\n:AREA: A1,A1\n:END:\nHi\n"""
        )
        with tempfile.TemporaryDirectory() as td:
            org_path = pathlib.Path(td) / 'g.org'
            org_path.write_text(org, encoding='utf-8')
            ir = pm.parse_org(str(org_path))
            t = pm.generate_typst(ir)
            # With margins declared, AREA uses total grid: A1 -> (1,1)
            m = re.search(r"^#layer_grid\(gp,1,1,1,1, ", t, flags=re.M)
            self.assertIsNotNone(m, f"Expected total-grid addressing not found. Typst was:\n{t}")


if __name__ == '__main__':
    unittest.main()
