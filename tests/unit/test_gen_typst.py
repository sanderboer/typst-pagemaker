#!/usr/bin/env python3
"""Unit tests for gen_typst.py functions"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
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

if __name__ == '__main__':
    unittest.main()
