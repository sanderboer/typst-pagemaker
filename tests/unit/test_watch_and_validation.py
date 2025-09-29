#!/usr/bin/env python3
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')


class TestWatchAndValidation(unittest.TestCase):
    def setUp(self):
        self.fixtures = pathlib.Path(PROJECT_ROOT) / 'tests' / 'fixtures'
        self.org_basic = self.fixtures / 'basic.org'

    def _run_cli(self, args, expect_success=True):
        cmd = [sys.executable, '-m', 'pagemaker.cli'] + args
        env = os.environ.copy()
        env['PYTHONPATH'] = SRC_PATH + os.pathsep + env.get('PYTHONPATH', '')
        res = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, capture_output=True, text=True)
        if expect_success and res.returncode != 0:
            self.fail(f"Command failed {cmd}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
        return res

    def test_watch_once_builds(self):
        with tempfile.TemporaryDirectory() as td:
            tmp_org = pathlib.Path(td) / 'deck.org'
            tmp_org.write_text(self.org_basic.read_text(encoding='utf-8'), encoding='utf-8')
            res = self._run_cli(['watch', str(tmp_org), '--once', '--export-dir', td])
            self.assertIn('[watch] Rebuilt Typst', res.stdout)
            self.assertTrue((pathlib.Path(td) / 'deck.typ').exists())

    def test_validation_duplicate_ids(self):
        # Construct minimal IR by writing org with duplicate headlines
        org_content = """* Page One\n** Element\n:PROPERTIES:\n:TYPE: header\n:END:\n** Element\n:PROPERTIES:\n:TYPE: header\n:END:\n"""
        with tempfile.TemporaryDirectory() as td:
            org_file = pathlib.Path(td) / 'dup.org'
            org_file.write_text(org_content, encoding='utf-8')
            res = self._run_cli(['validate', str(org_file)], expect_success=False)
            self.assertIn('Duplicate element id', res.stdout + res.stderr)

    def test_validation_alpha_out_of_range(self):
        org_content = """* Page
** Rect
:PROPERTIES:
:TYPE: rectangle
:AREA: 1,1,2,2
:ALPHA: 1.5
:END:
"""
        with tempfile.TemporaryDirectory() as td:
            org_file = pathlib.Path(td) / 'alpha.org'
            org_file.write_text(org_content, encoding='utf-8')
            res = self._run_cli(['validate', str(org_file)], expect_success=False)
            self.assertIn('Alpha out of range', res.stdout + res.stderr)

    def test_validation_missing_asset_warning(self):
        org_content = """* Page
 ** Img
 :PROPERTIES:
 :TYPE: figure
 :AREA: 1,1,2,2
 :END:
 [[file:nonexistent_dir/nonexistent.png]]
 """
        with tempfile.TemporaryDirectory() as td:
            org_file = pathlib.Path(td) / 'missing_asset.org'
            org_file.write_text(org_content, encoding='utf-8')
            res = self._run_cli(['validate', str(org_file)], expect_success=True)
            # Should be a warning not an error
            self.assertIn('Figure asset not found', res.stdout + res.stderr)

    def test_validation_missing_asset_strict_error(self):
        org_content = """* Page
 ** Img
 :PROPERTIES:
 :TYPE: figure
 :AREA: 1,1,2,2
 :END:
 [[file:nonexistent_dir/nonexistent.png]]
 """
        with tempfile.TemporaryDirectory() as td:
            org_file = pathlib.Path(td) / 'missing_asset_strict.org'
            org_file.write_text(org_content, encoding='utf-8')
            res = self._run_cli(
                ['validate', '--strict-assets', str(org_file)], expect_success=False
            )
            self.assertIn('Figure asset not found', res.stdout + res.stderr)


if __name__ == '__main__':
    unittest.main()
