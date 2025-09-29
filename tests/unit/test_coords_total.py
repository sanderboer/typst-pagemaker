#!/usr/bin/env python3
import os
import pathlib
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import pagemaker as pm


class TestCoordsTotal(unittest.TestCase):
    def test_total_coords_with_margins_draws_total_grid_and_layer_grid(self):
        # With mm margins declared, total grid draws and total addressing works
        org = """#+TITLE: Total Coords With Margins
#+GRID: 3x3
#+MARGINS: 1,1,1,1
#+GRID_DEBUG: true

* P
:PROPERTIES:
:ID: p
:END:

** Rect
:PROPERTIES:
:TYPE: rectangle
:AREA: 1,1,1,1
:END:
"""
        with tempfile.TemporaryDirectory() as td:
            org_path = pathlib.Path(td) / 'total_with_margins.org'
            org_path.write_text(org, encoding='utf-8')
            ir = pm.parse_org(str(org_path))
            t = pm.generate_typst(ir)
            self.assertIn('#layer_grid(gp,1,1,1,1, ', t)
            self.assertIn('#draw_total_grid(gp)', t)

    def test_total_coords_with_mm_uses_layer_grid(self):
        # With absolute mm margins declared, total grid has 4x4 tracks (2x2 content + 1 margin each side)
        org = """#+TITLE: Total Coords With MM
#+GRID: 2x2
#+MARGINS: 10,20,30,40

* P
:PROPERTIES:
:ID: p
:END:

** Rect
:PROPERTIES:
:TYPE: rectangle
:AREA: 1,1,4,4
:END:
"""
        with tempfile.TemporaryDirectory() as td:
            org_path = pathlib.Path(td) / 'total_mm.org'
            org_path.write_text(org, encoding='utf-8')
            ir = pm.parse_org(str(org_path))
            t = pm.generate_typst(ir)
            # Expect layer_grid addressing across the full total grid
            self.assertIn('#layer_grid(gp,1,1,4,4, ', t)
            # Ensure mm-based cw/ch computation present
            self.assertIn('#let cw = (', t)
            self.assertIn('#let gp = (lc: 1, rc: 1, lr: 1, br: 1, cc: 2, cr: 2', t)

    # Removed: content coords mode is no longer supported; AREA is always total

    def test_no_margins_identity_and_simple_grid_debug(self):
        # Without margins, total grid equals content; debug uses draw_grid
        org = """#+TITLE: No Margins
#+GRID: 2x2
#+GRID_DEBUG: true

* P
:PROPERTIES:
:ID: p
:END:

** Rect
:PROPERTIES:
:TYPE: rectangle
:AREA: A1,A1
:END:
"""
        with tempfile.TemporaryDirectory() as td:
            org_path = pathlib.Path(td) / 'content_no_margins.org'
            org_path.write_text(org, encoding='utf-8')
            ir = pm.parse_org(str(org_path))
            t = pm.generate_typst(ir)
            self.assertIn('#layer_grid(gp,1,1,1,1, ', t)
            self.assertIn('#draw_grid(2, 2, cw, ch)', t)
            self.assertNotIn('#draw_total_grid(gp)', t)


if __name__ == '__main__':
    unittest.main()
