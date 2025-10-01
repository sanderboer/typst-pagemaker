#!/usr/bin/env python3
"""Unit tests for font helper utilities in pagemaker.fonts.

Covers:
- _discover_fonts_in_path: groups files by top-level family directory and totals sizes
- _collect_real_font_names: extracts real family names from TTF/TTC/OTF via fontTools
- _get_font_paths: includes examples and bundled fonts in expected environments
"""

import os
import pathlib
import sys
import unittest

# Ensure src is importable
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

from pagemaker.fonts import (  # noqa: E402
    _collect_real_font_names,
    _discover_fonts_in_path,
    _get_font_paths,
)


class TestFontHelpers(unittest.TestCase):
    def setUp(self):
        self.repo_root = pathlib.Path(PROJECT_ROOT).resolve()
        self.test_fonts_dir = self.repo_root / 'test' / 'assets' / 'fonts'
        self.examples_fonts_dir = self.repo_root / 'examples' / 'assets' / 'fonts'
        # Bundled fonts live next to the package in src/pagemaker/fonts
        import pagemaker  # noqa: E402

        self.bundled_fonts_dir = pathlib.Path(pagemaker.__file__).parent / 'fonts'

    def test_discover_fonts_in_path_groups_by_family(self):
        info = _discover_fonts_in_path(self.test_fonts_dir)
        self.assertTrue(info['exists'])
        families = info['families']
        # Expect test families present
        for fam in ['Inter', 'Manrope', 'Playfair Display', 'Fauna One']:
            self.assertIn(fam, families)
            self.assertGreater(len(families[fam]['files']), 0)
            # total_size is computed and human alias present
            self.assertIn('total_size', families[fam])
            self.assertIn('total_size_human', families[fam])

    def test_collect_real_font_names_from_ttf(self):
        # Should include the real family names from TTFs in test assets
        names = _collect_real_font_names([str(self.test_fonts_dir)])
        # fontTools may normalize spacing; check expected set membership
        expected = {'Inter', 'Manrope', 'Playfair Display', 'Fauna One'}
        self.assertTrue(expected.issubset(names))

    def test_get_font_paths_includes_examples_and_bundled(self):
        paths = _get_font_paths()
        # examples assets fonts path should be present in this repo
        self.assertTrue(any('examples/assets/fonts' in p for p in paths))
        # bundled fonts directory should also be present
        self.assertTrue(any(str(self.bundled_fonts_dir) == p for p in paths))


if __name__ == '__main__':
    unittest.main()
