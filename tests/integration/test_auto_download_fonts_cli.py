#!/usr/bin/env python3
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')

TEST_FONT = 'Zzz Totally Missing Font'

FAKE_FD_CODE = """
# Minimal fake fontdownloader.cli for tests
import os
from pathlib import Path

def _download_full_family(font_family: str, force: bool = False):
    # Create assets/fonts/<FontName>/Dummy-Regular.ttf under project root (cwd)
    base = Path(os.getcwd()) / 'assets' / 'fonts' / font_family
    base.mkdir(parents=True, exist_ok=True)
    # Create a dummy TTF file (contents don't matter for our dir heuristic)
    filename = font_family.replace(' ', '') + '-Regular.ttf'
    (base / filename).write_bytes(b'TTF-DUMMY\\n')
    return True
"""


class TestAutoDownloadFontsCLI(unittest.TestCase):
    def _run_cli(self, args, extra_env=None, expect_success=True):
        cmd = [sys.executable, '-m', 'pagemaker.cli'] + args
        env = os.environ.copy()
        env['PYTHONPATH'] = SRC_PATH + os.pathsep + env.get('PYTHONPATH', '')
        if extra_env:
            env.update(extra_env)
        res = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, capture_output=True, text=True)
        if expect_success and res.returncode != 0:
            self.fail(f"Command failed {cmd}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
        return res

    def test_auto_download_missing_font_via_programmatic_api(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            # Prepare fake fontdownloader package in temp directory
            pkg_dir = td_path / 'fontdownloader'
            pkg_dir.mkdir(parents=True, exist_ok=True)
            (pkg_dir / '__init__.py').write_text('', encoding='utf-8')
            (pkg_dir / 'cli.py').write_text(FAKE_FD_CODE, encoding='utf-8')

            # Ensure target font directory is absent to trigger auto-download
            target_dir = Path(PROJECT_ROOT) / 'assets' / 'fonts' / TEST_FONT
            if target_dir.exists():
                import shutil

                shutil.rmtree(target_dir)

            # Prepare a minimal org file referencing a missing font
            org_path = td_path / 'missing_font.org'
            org_path.write_text(
                f"#+TITLE: Auto Download Test\n#+FONT: {TEST_FONT}\n\n* Slide\n:PROPERTIES:\n:TYPE: body\n:AREA: 1,1,3,2\n:END:\nHello\n",
                encoding='utf-8',
            )

            # Compose env: ensure fake package takes precedence and disable fonttools scan
            extra_env = {
                'PYTHONPATH': str(td_path)
                + os.pathsep
                + SRC_PATH
                + os.pathsep
                + os.environ.get('PYTHONPATH', ''),
                'PAGEMAKER_DISABLE_FONTTOOLS': '1',
            }

            # Run build - should attempt auto-download and then succeed in making font available
            res = self._run_cli(
                ['build', str(org_path), '--export-dir', td, '-o', 'deck.typ'], extra_env=extra_env
            )
            out = res.stdout + res.stderr
            self.assertIn('Missing fonts detected', out)
            self.assertIn(f"'{TEST_FONT}' is now available", out)
            # Ensure font directory was created
            self.assertTrue((Path(PROJECT_ROOT) / 'assets' / 'fonts' / TEST_FONT).exists())

            # Second run: validate fonts strictly should pass now
            res2 = self._run_cli(
                [
                    'build',
                    str(org_path),
                    '--export-dir',
                    td,
                    '-o',
                    'deck2.typ',
                    '--validate-fonts',
                    '--strict-fonts',
                ],
                extra_env=extra_env,
            )
            self.assertIn('Built Typst', res2.stdout)


if __name__ == '__main__':
    unittest.main()
