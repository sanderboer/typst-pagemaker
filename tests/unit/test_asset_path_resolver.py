import os
import pathlib
import tempfile
import unittest

from pagemaker.utils.assets_paths import AssetPathResolver


class TestAssetPathResolverPrecedence(unittest.TestCase):
    def setUp(self):
        self._orig_cwd = os.getcwd()
        self.tmp_base = pathlib.Path(tempfile.mkdtemp(prefix="pm_asset_paths_"))
        # Project root structure
        self.project_root = self.tmp_base / "project"
        self.project_root.mkdir()
        # Provide marker so auto detection (if accidentally used) would still work
        (self.project_root / "pyproject.toml").write_text("[project]\nname='dummy'\n")
        self.typst_dir = self.project_root / "out"
        self.typst_dir.mkdir()
        self.source_dir = self.project_root / "srcdoc"
        self.source_dir.mkdir()
        self.run_dir = self.tmp_base / "run"
        self.run_dir.mkdir()

    def tearDown(self):
        os.chdir(self._orig_cwd)
        # Best-effort cleanup
        try:
            for p in self.tmp_base.rglob("*"):
                try:
                    if p.is_file():
                        p.unlink()
                except OSError:
                    pass
            for p in sorted(self.tmp_base.rglob("*"), reverse=True):
                try:
                    p.rmdir()
                except OSError:
                    pass
            self.tmp_base.rmdir()
        except OSError:
            pass

    def _new_resolver(self, strict: bool = False):
        return AssetPathResolver(
            typst_dir=self.typst_dir,
            source_dir=self.source_dir,
            project_root=self.project_root,
            strict=strict,
        )

    def test_precedence_cwd_over_source_over_project_over_typst(self):
        target_name = "asset.png"
        # 1. Only typst copy exists
        (self.typst_dir / target_name).write_text("typst")
        r1 = self._new_resolver()
        self.assertEqual(r1.resolve(target_name), target_name)  # relative inside typst
        # 2. Add project root copy (should now win)
        (self.project_root / target_name).write_text("project")
        r2 = self._new_resolver()
        self.assertEqual(r2.resolve(target_name), os.path.join("..", target_name))
        # 3. Add source dir copy (higher precedence than project)
        (self.source_dir / target_name).write_text("source")
        r3 = self._new_resolver()
        self.assertEqual(r3.resolve(target_name), os.path.join("..", "srcdoc", target_name))
        # 4. Add invocation CWD copy (highest precedence). Change CWD.
        (self.run_dir / target_name).write_text("cwd")
        os.chdir(self.run_dir)
        r4 = self._new_resolver()
        resolved = r4.resolve(target_name)
        # Compute expected relative path from typst_dir to run_dir/asset.png
        expected = os.path.relpath(self.run_dir / target_name, self.typst_dir)
        self.assertEqual(resolved, expected)
        # 5. Cache behavior: second call returns identical string
        self.assertIs(resolved, r4.resolve(target_name)) or self.assertEqual(
            resolved, r4.resolve(target_name)
        )

    def test_examples_fallback(self):
        # Create examples fallback file only
        rel_src = "assets/demo/example.png"
        examples_file = self.project_root / "examples" / rel_src
        examples_file.parent.mkdir(parents=True, exist_ok=True)
        examples_file.write_text("example")
        r = self._new_resolver()
        out = r.resolve(rel_src)
        expected = os.path.relpath(examples_file, self.typst_dir)
        self.assertEqual(out, expected)

    def test_strict_vs_non_strict_unresolved(self):
        missing = "does_not_exist.xyz"
        # Non-strict should rewrite via project root mapping
        r_non = self._new_resolver(strict=False)
        out_non = r_non.resolve(missing)
        expected_non = os.path.relpath(self.project_root / missing, self.typst_dir)
        self.assertEqual(out_non, expected_non)
        # Strict should leave unchanged
        r_strict = self._new_resolver(strict=True)
        out_strict = r_strict.resolve(missing)
        self.assertEqual(out_strict, missing)

    def test_absolute_and_protocol_passthrough(self):
        abs_file = self.tmp_base / "abs.png"
        abs_file.write_text("abs")
        r = self._new_resolver()
        self.assertEqual(r.resolve(str(abs_file)), str(abs_file))
        proto = "https://example.com/image.png"
        self.assertEqual(r.resolve(proto), proto)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
