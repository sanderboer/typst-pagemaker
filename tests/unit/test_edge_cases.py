#!/usr/bin/env python3
"""Edge case and error handling tests"""

import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
import pagemaker as pm


class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.fixtures_path = Path(__file__).parent.parent / "fixtures"

    def test_parse_edge_cases_org(self):
        """Test parsing org file with edge cases"""
        org_path = self.fixtures_path / "edge_cases.org"
        ir = pm.parse_org(str(org_path))

        # Should still parse successfully
        self.assertIn('meta', ir)
        self.assertIn('pages', ir)
        self.assertEqual(len(ir['pages']), 2)

    def test_parse_area_edge_cases(self):
        """Test parse_area with various edge cases"""
        # None input
        self.assertIsNone(pm.parse_area(None))

        # Too few components
        self.assertIsNone(pm.parse_area("1,2"))

        # Too many components
        self.assertIsNone(pm.parse_area("1,2,3,4,5"))

        # Non-integer values
        self.assertIsNone(pm.parse_area("1.5,2,3,4"))

    def test_nonexistent_file(self):
        """Test parsing nonexistent org file"""
        try:
            pm.parse_org("nonexistent.org")
            self.fail("Should raise FileNotFoundError")
        except FileNotFoundError:
            pass  # Expected

    def test_empty_meta_defaults(self):
        """Test meta_defaults with None input"""
        result = pm.meta_defaults({})
        # Should return defaults
        expected = pm.DEFAULTS.copy()
        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
