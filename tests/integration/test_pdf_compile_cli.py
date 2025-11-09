#!/usr/bin/env python3
"""Optional integration test that compiles PDF via the CLI.
Skips gracefully if `typst` is not installed.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')


class TestPDFCompileCLI(unittest.TestCase):
    def _has_typst(self) -> bool:
        """Return True if typst CLI is available.

        Legacy MuchPDF import test removed; native image() embedding is now standard.
        """
        try:
            res = subprocess.run(['typst', '--version'], capture_output=True, text=True)
            return res.returncode == 0
        except FileNotFoundError:
            return False

    def test_cli_pdf_compile_if_available(self):
        if not self._has_typst():
            self.skipTest("typst CLI not available; skipping PDF compile test")
        fixtures = Path(PROJECT_ROOT) / 'tests' / 'fixtures'
        org_path = fixtures / 'pdf_test.org'
        with tempfile.TemporaryDirectory() as td:
            export_dir = Path(PROJECT_ROOT) / 'temp_test_pdfcli_export'
            export_dir.mkdir(parents=True, exist_ok=True)
            try:
                cmd = [
                    sys.executable,
                    '-m',
                    'pagemaker.cli',
                    'pdf',
                    str(org_path),
                    '--export-dir',
                    str(export_dir),
                    '--pdf-output',
                    'out.pdf',
                    '--no-clean',
                ]
                env = os.environ.copy()
                env['PYTHONPATH'] = SRC_PATH + os.pathsep + env.get('PYTHONPATH', '')
                res = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, capture_output=True, text=True)
                if res.returncode != 0:
                    self.fail(
                        f"CLI pdf compile failed. STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
                    )
                self.assertTrue((export_dir / 'out.pdf').exists())
            finally:
                try:
                    pdf_path = export_dir / 'out.pdf'
                    if pdf_path.exists():
                        pdf_path.unlink()
                    export_dir.rmdir()
                except OSError:
                    pass


if __name__ == '__main__':
    unittest.main()
