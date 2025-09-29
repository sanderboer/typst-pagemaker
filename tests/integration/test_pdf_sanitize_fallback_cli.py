#!/usr/bin/env python3
"""Integration test for --sanitize-pdfs fallback behavior in the CLI.

This test forces Typst to be unavailable (via a bogus --typst-bin) so the
compile step fails and the CLI proceeds to sanitize and then SVG/PNG fallback
conversion for embedded PDFs. It then inspects the generated .typ file to
verify that the PDF element has been rewritten to use an image() pointing at
assets/pdf-fallbacks/<name>-p1.svg or .png, and that the fallback file exists.

The test is skipped if neither `mutool` nor `gs` (Ghostscript) are available,
because one of them is required to generate the fallback asset.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / 'src'
ASSETS_DIR = PROJECT_ROOT / 'examples' / 'assets' / 'test-pdfs'


def _have_tool(name: str) -> bool:
    return shutil.which(name) is not None


class TestPDFSanitizeFallbackCLI(unittest.TestCase):
    def test_sanitize_then_fallback_rewrites_pdf_to_image_when_compile_fails(self):
        # Require at least one renderer for fallbacks
        if not (_have_tool('mutool') or _have_tool('gs')):
            self.skipTest("mutool/gs not available; skipping sanitize+fallback test")

        problem_pdf = ASSETS_DIR / 'test-exploded-view.pdf'
        self.assertTrue(problem_pdf.exists(), f"Missing test asset: {problem_pdf}")

        # Minimal org that embeds the problematic PDF on page 1
        org_content = """#+TITLE: Fallback Test\n\n* Slide\n:PROPERTIES:\n:ID: slide\n:END:\n\n** PDF\n:PROPERTIES:\n:TYPE: pdf\n:AREA: 1,1,6,4\n:PDF: examples/assets/test-pdfs/test-exploded-view.pdf\n:PAGE: 1\n:SCALE: 1.0\n:END:\n"""

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            org_path = td_path / 'deck.org'
            org_path.write_text(org_content, encoding='utf-8')

            cmd = [
                sys.executable,
                '-m',
                'pagemaker.cli',
                'pdf',
                str(org_path),
                '--export-dir',
                td,
                '--pdf-output',
                'out.pdf',
                '--sanitize-pdfs',
                '--no-clean',
                '--typst-bin',
                'typst-bogus-not-found',  # force compile failure
                '-o',
                'deck.typ',
            ]
            env = os.environ.copy()
            env['PYTHONPATH'] = str(SRC_PATH) + os.pathsep + env.get('PYTHONPATH', '')
            res = subprocess.run(
                cmd, cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True
            )

            # Compile is expected to fail due to bogus typst, but the .typ should
            # still be generated on the last attempt (after fallback IR is applied).
            self.assertNotEqual(
                res.returncode, 0, "Compile unexpectedly succeeded with bogus typst-bin"
            )

            typ_path = td_path / 'deck.typ'
            self.assertTrue(typ_path.exists(), "Expected typst file was not generated")
            typ_code = typ_path.read_text(encoding='utf-8')

            # Look for fallback asset reference in typst code
            m = re.search(r'assets/pdf-fallbacks/(test-exploded-view-p1)\.(svg|png)', typ_code)
            self.assertIsNotNone(
                m,
                f"Expected fallback asset path not found in typst code.\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}",
            )

            fallback_rel = m.group(0)  # relative path inside export dir
            fallback_abs = td_path / fallback_rel
            self.assertTrue(fallback_abs.exists(), f"Fallback asset not created: {fallback_abs}")


if __name__ == '__main__':
    unittest.main()
