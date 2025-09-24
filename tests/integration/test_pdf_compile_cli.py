#!/usr/bin/env python3
"""Optional integration test that compiles PDF via the CLI.
Skips gracefully if `typst` is not installed or the muchpdf package
is unavailable (e.g., offline environments).
"""
import unittest
import os
import sys
import tempfile
import subprocess
from pathlib import Path

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')

class TestPDFCompileCLI(unittest.TestCase):
    def _has_typst_and_muchpdf(self) -> bool:
        try:
            # Check typst binary
            res = subprocess.run(['typst', '--version'], capture_output=True, text=True)
            if res.returncode != 0:
                return False
            # Create a tiny typst file that only imports muchpdf
            with tempfile.TemporaryDirectory() as td:
                typ_path = Path(td) / 'check.typ'
                typ_path.write_text('#import "@preview/muchpdf:0.1.1": muchpdf\n#page(width: 10pt, height: 10pt)[]\n', encoding='utf-8')
                out_pdf = Path(td) / 'check.pdf'
                res2 = subprocess.run([
                    'typst', 'compile', '--root', str(Path(PROJECT_ROOT).resolve()),
                    str(typ_path), str(out_pdf)
                ], capture_output=True, text=True)
                return res2.returncode == 0
        except FileNotFoundError:
            return False

    def test_cli_pdf_compile_if_available(self):
        if not self._has_typst_and_muchpdf():
            self.skipTest("typst or muchpdf not available; skipping PDF compile test")
        fixtures = Path(PROJECT_ROOT) / 'tests' / 'fixtures'
        org_path = fixtures / 'pdf_test.org'
        with tempfile.TemporaryDirectory() as td:
            cmd = [sys.executable, '-m', 'pagemaker.cli', 'pdf', str(org_path), '--export-dir', td, '--pdf-output', 'out.pdf', '--no-clean']
            env = os.environ.copy(); env['PYTHONPATH'] = SRC_PATH + os.pathsep + env.get('PYTHONPATH','')
            res = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, capture_output=True, text=True)
            if res.returncode != 0:
                self.fail(f"CLI pdf compile failed. STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
            self.assertTrue((Path(td)/'out.pdf').exists())

if __name__ == '__main__':
    unittest.main()
