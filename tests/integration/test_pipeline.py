#!/usr/bin/env python3
"""Integration tests for the full org->typst pipeline"""
import unittest
import sys
import os
import tempfile
import subprocess
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import gen_typst

class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.fixtures_path = Path(__file__).parent.parent / "fixtures"
        self.temp_dir = tempfile.mkdtemp()
    
    def test_basic_org_to_typst(self):
        """Test converting basic org file to typst"""
        org_path = self.fixtures_path / "basic.org"
        ir = gen_typst.parse_org(str(org_path))
        
        # Check that we got valid IR
        self.assertIn('meta', ir)
        self.assertIn('pages', ir)
        self.assertEqual(len(ir['pages']), 1)
        
        # Generate typst code
        typst_code = gen_typst.generate_typst(ir)
        self.assertIsInstance(typst_code, str)
        self.assertIn('#import "@preview/muchpdf:0.1.1"', typst_code)
    
    def test_pdf_org_to_typst(self):
        """Test converting PDF org file to typst"""
        org_path = self.fixtures_path / "pdf_test.org"
        ir = gen_typst.parse_org(str(org_path))
        
        # Generate typst code
        typst_code = gen_typst.generate_typst(ir)
        self.assertIn('muchpdf', typst_code)
        self.assertIn('assets/test-pdfs/test-plan.pdf', typst_code)

if __name__ == '__main__':
    unittest.main()
