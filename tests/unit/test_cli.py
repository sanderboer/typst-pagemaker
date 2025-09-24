#!/usr/bin/env python3
import unittest, sys, os, subprocess, json, tempfile, pathlib

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')

class TestCLI(unittest.TestCase):
    def setUp(self):
        self.fixtures = pathlib.Path(PROJECT_ROOT) / 'tests' / 'fixtures'
        self.org_basic = self.fixtures / 'basic.org'

    def _run(self, args, expect_success=True):
        cmd = [sys.executable, '-m', 'pagemaker.cli'] + args
        env = os.environ.copy(); env['PYTHONPATH'] = SRC_PATH + os.pathsep + env.get('PYTHONPATH','')
        res = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, capture_output=True, text=True)
        if expect_success and res.returncode != 0:
            self.fail(f"Command failed {cmd}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
        return res

    def test_ir_subcommand(self):
        res = self._run(['ir', str(self.org_basic)])
        data = json.loads(res.stdout)
        self.assertIn('pages', data)
        self.assertGreaterEqual(len(data['pages']), 1)

    def test_build_subcommand_output(self):
        with tempfile.TemporaryDirectory() as td:
            res = self._run(['build', str(self.org_basic), '--export-dir', td, '-o', 'deck.typ'])
            self.assertIn('Built Typst', res.stdout)
            self.assertTrue(os.path.exists(os.path.join(td, 'deck.typ')))

    def test_validate_subcommand(self):
        res = self._run(['validate', str(self.org_basic)])
        self.assertIn('IR valid', res.stdout)

if __name__ == '__main__':
    unittest.main()
