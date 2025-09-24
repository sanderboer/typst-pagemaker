#!/usr/bin/env python3
"""Unit tests for gen_typst.py functions"""
import unittest
import sys
import os
import pathlib

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import gen_typst

class TestParseArea(unittest.TestCase):
    def test_valid_area(self):
        result = gen_typst.parse_area("1,2,3,4")
        self.assertEqual(result, [1, 2, 3, 4])
    
    def test_invalid_area(self):
        result = gen_typst.parse_area("invalid")
        self.assertIsNone(result)

class TestSlugify(unittest.TestCase):
    def test_basic_slugify(self):
        result = gen_typst.slugify("Hello World")
        self.assertEqual(result, "hello-world")

class TestEscapeText(unittest.TestCase):
    def test_basic_escape(self):
        result = gen_typst.escape_text("Hello World")
        self.assertEqual(result, "Hello World")

class TestAdjustAssetPaths(unittest.TestCase):
    def test_relative_rewrite(self):
        ir = {
            'meta': {},
            'pages': [{
                'elements': [
                    {'figure': {'src': 'diagram.png', 'caption': None, 'fit': 'contain'}, 'pdf': None},
                    {'figure': None, 'pdf': {'src': 'spec.pdf', 'pages': [1], 'scale': 1.0}}
                ]
            }]
        }
        export_dir = os.path.join(PROJECT_ROOT, 'export_test_tmp')
        os.makedirs(export_dir, exist_ok=True)
        gen_typst.adjust_asset_paths(ir, pathlib.Path(export_dir))
        fig_src = ir['pages'][0]['elements'][0]['figure']['src']
        pdf_src = ir['pages'][0]['elements'][1]['pdf']['src']
        expected_fig = os.path.relpath(os.path.join(PROJECT_ROOT, 'diagram.png'), export_dir)
        expected_pdf = os.path.relpath(os.path.join(PROJECT_ROOT, 'spec.pdf'), export_dir)
        # On most systems export dir is inside project root, so relative path should not start with '/'
        self.assertEqual(fig_src, expected_fig)
        self.assertEqual(pdf_src, expected_pdf)

if __name__ == '__main__':
    unittest.main()
