#!/usr/bin/env python3
import unittest, os, sys, tempfile, pathlib

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import pagemaker as pm

class TestIgnoredOverridesWarning(unittest.TestCase):
    def test_per_page_overrides_warn(self):
        org = ("""#+PAGESIZE: A4
#+ORIENTATION: landscape
#+GRID: 12x8

* Slide One
:PROPERTIES:
:ID: s1
:PAGE_SIZE: A3
:ORIENTATION: portrait
:END:

** Body
:PROPERTIES:
:TYPE: body
:AREA: A1,A1
:END:
Hello
""")
        with tempfile.TemporaryDirectory() as td:
            org_path = pathlib.Path(td)/'doc.org'
            org_path.write_text(org, encoding='utf-8')
            ir = pm.parse_org(str(org_path))
            res = pm.validate_ir(ir)
            msgs = "\n".join(f"{i.severity}:{i.path}:{i.message}" for i in res.issues)
            self.assertIn('warn', msgs)
            self.assertIn('ignored_overrides', msgs)
            self.assertIn('Per-page overrides ignored', msgs)
            # Should mention which keys were ignored
            self.assertIn('PAGE_SIZE', msgs)
            self.assertIn('ORIENTATION', msgs)

if __name__ == '__main__':
    unittest.main()
