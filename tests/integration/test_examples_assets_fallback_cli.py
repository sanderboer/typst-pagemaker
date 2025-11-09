#!/usr/bin/env python3
"""Integration test for examples/ assets fallback via CLI path adjustment.

This test verifies that when an Org file references an asset under assets/... that
exists only under <project_root>/examples/assets/..., the CLI asset path adjustment
rewrites the path so that the generated .typ references the examples-based asset
relative to the export directory.
"""

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / 'src'


class TestExamplesAssetsFallbackCLI(unittest.TestCase):
    def test_examples_assets_fallback_in_typst_output(self):
        # Use a known example asset
        example_asset = PROJECT_ROOT / 'examples' / 'assets' / 'test-images' / 'forest.jpg'
        self.assertTrue(example_asset.exists(), f"Missing example asset: {example_asset}")

        # Minimal org that references an image under assets/, but we do not
        # create a top-level assets/ copy so the resolver must use the examples fallback
        org_content = """#+TITLE: Examples Assets Fallback\n\n* Slide\n:PROPERTIES:\n:ID: slide\n:END:\n\n** Image\n:PROPERTIES:\n:TYPE: figure\n:AREA: 1,1,6,4\n:END:\n\n[[file:assets/test-images/forest.jpg]]\n"""

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            org_path = td_path / 'deck.org'
            org_path.write_text(org_content, encoding='utf-8')

            cmd = [
                sys.executable,
                '-m',
                'pagemaker.cli',
                'build',
                str(org_path),
                '--export-dir',
                td,
                '-o',
                'deck.typ',
            ]
            env = os.environ.copy()
            env['PYTHONPATH'] = str(SRC_PATH) + os.pathsep + env.get('PYTHONPATH', '')
            res = subprocess.run(
                cmd, cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True
            )

            self.assertEqual(
                res.returncode, 0, f"Build failed\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
            )

            typ_path = td_path / 'deck.typ'
            self.assertTrue(typ_path.exists(), "Expected typst file was not generated")
            typ_code = typ_path.read_text(encoding='utf-8')

            # The generated Typst should reference a path under examples/assets relative to export dir
            m = re.search(r'examples/assets/test-images/forest\.jpg', typ_code)
            self.assertIsNotNone(
                m,
                f"Expected examples assets path not found in typst code.\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}\nTYPST:\n{typ_code}",
            )


if __name__ == '__main__':
    unittest.main()
