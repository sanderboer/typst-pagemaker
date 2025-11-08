#!/usr/bin/env python3
"""Regression test: legacy MuchPDF path appears only when PAGEMAKER_ENABLE_MUCHPDF_LEGACY=1.

This test explicitly sets the environment variable and verifies that
pm.generate_typst emits the deprecated muchpdf import and macro usage.
It skips if typst CLI is not installed (since legacy path still relies on typst).
"""

import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import pagemaker as pm  # noqa: E402


class TestLegacyMuchPDFFlag(unittest.TestCase):
    def setUp(self):
        # Force legacy mode for duration of test
        os.environ['PAGEMAKER_ENABLE_MUCHPDF_LEGACY'] = '1'
        self.fixtures_path = Path(__file__).parent.parent / "fixtures"

    def tearDown(self):
        # Remove the flag to avoid leaking into other tests
        os.environ.pop('PAGEMAKER_ENABLE_MUCHPDF_LEGACY', None)

    def _has_typst(self) -> bool:
        from shutil import which

        return which('typst') is not None

    def test_legacy_import_and_macro_present(self):
        if not self._has_typst():
            self.skipTest('typst CLI unavailable; skipping legacy MuchPDF regression test')
        org_path = self.fixtures_path / 'pdf_test.org'
        ir = pm.parse_org(str(org_path))
        typst_code = pm.generate_typst(ir)
        # Import line
        self.assertIn('#import "@preview/muchpdf:0.1.1"', typst_code)
        # Macro usage (PdfEmbed resolves to muchpdf() call when flag enabled)
        self.assertIn('muchpdf', typst_code)
        self.assertIn('PdfEmbed(', typst_code)


if __name__ == '__main__':
    unittest.main()
