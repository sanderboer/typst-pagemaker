#!/usr/bin/env python3
"""Integration tests for counters and date helpers in Typst output.

- Verifies the sample example generates no AREA warnings and includes
  footer macros in the Typst output.
- Optionally compiles a minimal Org using the helpers if Typst + muchpdf
  are available on the system (skips otherwise).
"""

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / 'src'
EXAMPLES_DIR = PROJECT_ROOT / 'examples'

sys.path.insert(0, str(SRC_PATH))
import pagemaker as pm  # noqa: E402


def _has_typst_and_muchpdf() -> bool:
    try:
        res = subprocess.run(['typst', '--version'], capture_output=True, text=True)
        if res.returncode != 0:
            return False
        with tempfile.TemporaryDirectory() as td:
            typ_path = Path(td) / 'check.typ'
            typ_path.write_text(
                '#import "@preview/muchpdf:0.1.1": muchpdf\n#page(width: 10pt, height: 10pt)[]\n',
                encoding='utf-8',
            )
            out_pdf = Path(td) / 'check.pdf'
            res2 = subprocess.run(
                [
                    'typst',
                    'compile',
                    '--root',
                    str(PROJECT_ROOT.resolve()),
                    str(typ_path),
                    str(out_pdf),
                ],
                capture_output=True,
                text=True,
            )
            return res2.returncode == 0
    except FileNotFoundError:
        return False


class TestHelpersIntegration(unittest.TestCase):
    def test_sample_org_has_footer_and_no_area_warnings(self):
        sample_org = EXAMPLES_DIR / 'sample.org'
        self.assertTrue(sample_org.exists(), f"Missing sample org: {sample_org}")
        ir = pm.parse_org(str(sample_org))
        buf = io.StringIO()
        with redirect_stderr(buf):
            typst_code = pm.generate_typst(ir)
        stderr_out = buf.getvalue()
        self.assertNotIn('WARNING: AREA out-of-bounds', stderr_out)
        # Footer macros from sample should appear in Typst code (page counters)
        self.assertIn('Page #page_no / #page_total', typst_code)
        # And a date helper is used somewhere in the document
        self.assertTrue(('#date_yy_mm_dd' in typst_code) or ('#date_iso' in typst_code))
        # Also ensure helper definitions are present
        self.assertIn('#let date_iso =', typst_code)
        self.assertIn('#let page_no = context counter(page).display()', typst_code)
        self.assertIn('#let page_total = context counter(page).final().at(0)', typst_code)

    def test_cli_pdf_compile_with_helpers_if_available(self):
        if not _has_typst_and_muchpdf():
            self.skipTest('typst or muchpdf not available; skipping helpers PDF compile test')
        org_content = (
            "#+TITLE: Helpers Test\n\n"
            "* Slide\n:PROPERTIES:\n:ID: s1\n:END:\n\n"
            "** Text\n:PROPERTIES:\n:TYPE: body\n:AREA: 1,1,6,2\n:END:\n"
            "Page #page_no / #page_total — #date_iso\n"
        )
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
                '--no-clean',
            ]
            env = os.environ.copy()
            env['PYTHONPATH'] = str(SRC_PATH) + os.pathsep + env.get('PYTHONPATH', '')
            res = subprocess.run(
                cmd, cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True
            )
            if res.returncode != 0:
                self.fail(
                    f"CLI PDF compile with helpers failed. STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
                )
            self.assertTrue((td_path / 'out.pdf').exists())


if __name__ == '__main__':
    unittest.main()
