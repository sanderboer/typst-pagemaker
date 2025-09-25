#!/usr/bin/env python3
import unittest, os, sys, tempfile, pathlib, re

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import pagemaker as pm

class TestMarginSizesMM(unittest.TestCase):
    def test_mm_margins_typst_generation(self):
        # With absolute mm margins declared via MARGINS, cw/ch are computed from content area
        org = ("""#+TITLE: MM Margins\n#+GRID: 4x4\n#+MARGINS: 10,15,20,25\n\n* P\n:PROPERTIES:\n:ID: p\n:PAGE_SIZE: A4\n:ORIENTATION: landscape\n:END:\n\n** B\n:PROPERTIES:\n:TYPE: body\n:COORDS: content\n:AREA: A1,A1\n:END:\nHello\n""")
        with tempfile.TemporaryDirectory() as td:
            org_path = pathlib.Path(td) / 'm.org'
            org_path.write_text(org, encoding='utf-8')
            ir = pm.parse_org(str(org_path))
            t = pm.generate_typst(ir)
            # Expect mm-based cw/ch computation present
            self.assertIn('#let cw = (297mm - (25.0mm + 15.0mm)) / 4', t)
            self.assertIn('#let ch = (210mm - (10.0mm + 20.0mm)) / 4', t)
            # Placement uses total grid addressing; A1 -> (1,1)
            self.assertRegex(t, re.compile(r"^#layer_grid\(gp,1,1,1,1, ", re.M))

    def test_mm_margins_expand_grid_total(self):
        org = ("""#+GRID: 3x3\n#+MARGINS: 5,5,5,5\n\n* P\n:PROPERTIES:\n:ID: p\n:END:\n\n** B\n:PROPERTIES:\n:TYPE: body\n:AREA: A1,A1\n:END:\n""")
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td)/'x.org'
            p.write_text(org, encoding='utf-8')
            ir = pm.parse_org(str(p))
            page = ir['pages'][0]
            # grid_total expands by +2 cols/rows (1 each side)
            self.assertEqual(page['grid_total']['cols'], 3 + 2)
            self.assertEqual(page['grid_total']['rows'], 3 + 2)

if __name__ == '__main__':
    unittest.main()
