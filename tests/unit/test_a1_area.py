#!/usr/bin/env python3
"""Tests for A1-style AREA parsing"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import pagemaker as pm


class TestA1Area(unittest.TestCase):
    def test_single_cell_upper(self):
        self.assertEqual(pm.parse_area("A1"), [1, 1, 1, 1])
        self.assertEqual(pm.parse_area("C2"), [2, 3, 1, 1])

    def test_single_cell_lower(self):
        self.assertEqual(pm.parse_area("a1"), [1, 1, 1, 1])
        self.assertEqual(pm.parse_area("c2"), [2, 3, 1, 1])

    def test_range_simple(self):
        # A1 to C2 inclusive -> cols 1..2 (w=2), rows 1..3 (h=3)
        self.assertEqual(pm.parse_area("A1,C2"), [1, 1, 2, 3])

    def test_range_reverse_order(self):
        # C2 to A1 should normalize to same rectangle
        self.assertEqual(pm.parse_area("C2,A1"), [1, 1, 2, 3])

    def test_multi_letter_rows(self):
        # AA1 -> row 27, col 1
        self.assertEqual(pm.parse_area("AA1"), [1, 27, 1, 1])
        # AZ10 -> row 52, col 10
        self.assertEqual(pm.parse_area("AZ10"), [10, 52, 1, 1])

    def test_legacy_numeric_still_supported(self):
        self.assertEqual(pm.parse_area("1,2,3,4"), [1, 2, 3, 4])

    def test_invalid_inputs(self):
        self.assertIsNone(pm.parse_area(""))
        self.assertIsNone(pm.parse_area("1,2"))
        self.assertIsNone(pm.parse_area("A"))
        self.assertIsNone(pm.parse_area("1A"))
        self.assertIsNone(pm.parse_area("A1,B"))


if __name__ == '__main__':
    unittest.main()
