#!/usr/bin/env python3
"""Test that a bare :JUSTIFY: property is treated as true for text elements"""
import unittest
import sys
import os
import tempfile
from pathlib import Path

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker as pm

class TestJustifyParseFromOrg(unittest.TestCase):
    def test_bare_justify_flag_parses_true(self):
        org = (
            "* P\n"
            ":PROPERTIES:\n:ID: p\n:END:\n\n"
            "** B\n"
            ":PROPERTIES:\n:TYPE: body\n:AREA: A1,A1\n:PADDING: 5\n:JUSTIFY:\n:END:\n\n"
            "Some text\n"
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'x.org'
            p.write_text(org, encoding='utf-8')
            ir = pm.parse_org(str(p))
            el = ir['pages'][0]['elements'][0]
            self.assertIn('justify', el)
            self.assertTrue(el['justify'])

if __name__ == '__main__':
    unittest.main()
