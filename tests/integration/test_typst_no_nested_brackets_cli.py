#!/usr/bin/env python3
"""Integration: CLI build emits Typst without nested content blocks like [[#text.

Skips PDF compilation. Only builds Typst via CLI and inspects the output file.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
import subprocess

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / 'src'
FIXTURES = PROJECT_ROOT / 'tests' / 'fixtures'

class TestNoNestedBracketsCLI(unittest.TestCase):
    def test_build_typst_has_no_nested_text_blocks(self):
        org_path = FIXTURES / 'basic.org'
        self.assertTrue(org_path.exists(), f"Missing fixture: {org_path}")
        with tempfile.TemporaryDirectory() as td:
            out_typ = Path(td) / 'deck.typ'
            cmd = [
                sys.executable, '-m', 'pagemaker.cli', 'build', str(org_path),
                '--export-dir', td, '--output', str(out_typ)
            ]
            env = os.environ.copy()
            env['PYTHONPATH'] = str(SRC_PATH) + os.pathsep + env.get('PYTHONPATH', '')
            res = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True)
            if res.returncode != 0:
                self.fail(f"CLI build failed. STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
            self.assertTrue(out_typ.exists(), f"Typst was not written: {out_typ}")
            code = out_typ.read_text(encoding='utf-8')
            self.assertNotIn('[[#text', code)
            self.assertNotIn(']]]', code)

if __name__ == '__main__':
    unittest.main()
