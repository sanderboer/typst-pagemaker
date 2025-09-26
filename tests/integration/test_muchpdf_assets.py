#!/usr/bin/env python3
"""Integration tests for MuchPDF handling of sample PDFs in assets/test-pdfs.

These tests attempt to compile a minimal Typst document that imports the
@preview/muchpdf package and embeds exactly the first page of each sample PDF.

- Skips gracefully if `typst` or the MuchPDF package is unavailable.
- Verifies known-good PDFs compile successfully.
- Documents a known problem file as an expected failure (if it compiles
  successfully in your environment, this test will show as an unexpected pass).
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = PROJECT_ROOT / "examples" / "assets" / "test-pdfs"


class TestMuchPDFOnAssets(unittest.TestCase):
    def _has_typst_and_muchpdf(self) -> bool:
        """Return True if typst CLI is available and can import MuchPDF."""
        try:
            res = subprocess.run(["typst", "--version"], capture_output=True, text=True)
            if res.returncode != 0:
                return False
            with tempfile.TemporaryDirectory() as td:
                td_path = Path(td)
                typ_path = td_path / "check.typ"
                typ_path.write_text(
                    '#import "@preview/muchpdf:0.1.1": muchpdf\n#page(width: 10pt, height: 10pt)[]\n',
                    encoding="utf-8",
                )
                out_pdf = td_path / "check.pdf"
                res2 = subprocess.run(
                    [
                        "typst",
                        "compile",
                        "--root",
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

    def _compile_with_muchpdf(self, pdf_rel_path: Path):
        """Compile a minimal Typst file that embeds the first page of pdf_rel_path.

        Returns (returncode, stdout, stderr, out_pdf_path)
        """
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            typ_path = td_path / "doc.typ"
            out_pdf = td_path / "out.pdf"

            # Build minimal Typst that embeds one page via MuchPDF at scale 1.0
            typ_code = (
                '#import "@preview/muchpdf:0.1.1": muchpdf\n'
                f'#let data = read("{pdf_rel_path.as_posix()}", encoding: none)\n'
                "#muchpdf(data, pages: 0, scale: 1.0)\n"
            )
            typ_path.write_text(typ_code, encoding="utf-8")

            res = subprocess.run(
                [
                    "typst",
                    "compile",
                    "--root",
                    str(PROJECT_ROOT.resolve()),
                    str(typ_path),
                    str(out_pdf),
                ],
                capture_output=True,
                text=True,
            )
            return res.returncode, res.stdout, res.stderr, out_pdf

    def test_known_good_pdfs_compile(self):
        if not self._has_typst_and_muchpdf():
            self.skipTest("typst or muchpdf not available; skipping MuchPDF asset tests")

        # Known-good samples expected to succeed with MuchPDF
        cases = [
            ASSETS_DIR / "test-plan.pdf",
            ASSETS_DIR / "test-exploded-view-fixed.pdf",
        ]

        for pdf_path in cases:
            with self.subTest(pdf=pdf_path.name):
                self.assertTrue(pdf_path.exists(), f"Missing test asset: {pdf_path}")
                rc, out, err, out_pdf = self._compile_with_muchpdf(pdf_path.relative_to(PROJECT_ROOT))
                msg = (
                    f"MuchPDF failed to compile {pdf_path.name}\n"
                    f"Return code: {rc}\nSTDOUT:\n{out}\nSTDERR:\n{err}\n"
                )
                self.assertEqual(rc, 0, msg)
                self.assertTrue(out_pdf.exists(), f"Expected output PDF not found for {pdf_path.name}")

    @unittest.expectedFailure
    def test_known_problem_pdf_expected_to_fail(self):
        """Documents a known problematic PDF that often fails in MuchPDF.

        If this unexpectedly passes in your environment (e.g., MuchPDF or MuPDF
        has improved), this test will be reported as an unexpected success.
        """
        if not self._has_typst_and_muchpdf():
            self.skipTest("typst or muchpdf not available; skipping MuchPDF asset tests")

        pdf_path = ASSETS_DIR / "test-exploded-view.pdf"
        self.assertTrue(pdf_path.exists(), f"Missing test asset: {pdf_path}")
        rc, out, err, _ = self._compile_with_muchpdf(pdf_path.relative_to(PROJECT_ROOT))
        # We assert success here, but the decorator marks this test as expected to fail.
        self.assertEqual(rc, 0, f"Unexpected failure compiling {pdf_path.name}:\nSTDERR:\n{err}")


if __name__ == "__main__":
    unittest.main()
