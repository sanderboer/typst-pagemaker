#!/usr/bin/env python3
import unittest, os, sys, tempfile, pathlib

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import pagemaker as pm
from pagemaker.validation import validate_ir

class TestSVGAndMargins(unittest.TestCase):
    def test_adjust_asset_paths_for_svg(self):
        ir = {
            'meta': {},
            'pages': [{
                'grid': {'cols': 12, 'rows': 8},
                'elements': [
                    {'type': 'svg', 'area': {'x':1,'y':1,'w':2,'h':2}, 'z': 10, 'svg': {'src': 'assets/test-svgs/test-plan-p11.svg'}},
                ],
            }]
        }
        with tempfile.TemporaryDirectory() as td:
            export_dir = pathlib.Path(td)
            pm.adjust_asset_paths(ir, export_dir)
            ssrc = ir['pages'][0]['elements'][0]['svg']['src']
            self.assertFalse(os.path.isabs(ssrc))
            self.assertIn('assets', ssrc)

    def test_validation_svg_missing_asset_strict(self):
        ir = {
            'meta': {},
            'pages': [{
                'id': 'p1', 'title': 't', 'page_size': {'w_mm': 210, 'h_mm': 297}, 'grid': {'cols': 12, 'rows': 8}, 'elements': [
                    {'id': 'v', 'type': 'svg', 'area': {'x':1,'y':1,'w':1,'h':1}, 'z': 10, 'svg': {'src': 'nonexistent_dir/nonexistent.svg'}},
                ],
            }]
        }
        res = validate_ir(ir, strict_assets=True)
        msgs = "\n".join(f"{i.severity}:{i.message}" for i in res.issues)
        self.assertIn('error', msgs)
        self.assertIn('SVG asset not found', msgs)

    def test_margins_expand_grid_total(self):
        org = ("""#+GRID: 12x8\n#+MARGINS: 5,5,5,5\n\n* P\n:PROPERTIES:\n:ID: p\n:END:\n\n** B\n:PROPERTIES:\n:TYPE: body\n:AREA: A1,A1\n:END:\n""")
        with tempfile.TemporaryDirectory() as td:
            org_path = pathlib.Path(td)/'m.org'
            org_path.write_text(org, encoding='utf-8')
            ir = pm.parse_org(str(org_path))
            page = ir['pages'][0]
            self.assertEqual(page['grid_total']['cols'], 12 + 2)
            self.assertEqual(page['grid_total']['rows'], 8 + 2)

if __name__ == '__main__':
    unittest.main()
