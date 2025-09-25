#!/usr/bin/env python3
"""Tests for TOC element parsing and generation"""
import unittest
import sys
import os
import tempfile
import pathlib

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker as pm

class TestTocElement(unittest.TestCase):
    def test_parser_accepts_toc_type(self):
        org = ("""#+TITLE: TOC Test

* Slide 1
:PROPERTIES:
:ID: s1
:END:

** TOC
:PROPERTIES:
:TYPE: toc
:AREA: 1,1,3,2
:END:

** Body
:PROPERTIES:
:TYPE: body
:AREA: 4,1,3,2
:END:
Content
""")
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / 'toc.org'
            p.write_text(org, encoding='utf-8')
            ir = pm.parse_org(str(p))
            els = ir['pages'][0]['elements']
            types = [e['type'] for e in els]
            self.assertIn('toc', types)

    def test_generator_emits_bulleted_titles(self):
        ir = {
            'meta': {},
            'pages': [
                {'title': 'P1', 'page_size': {'w_mm': 210.0, 'h_mm': 297.0}, 'grid': {'cols': 4, 'rows': 4}, 'elements': [
                    {'id': 'toc1', 'type': 'toc', 'area': {'x':1,'y':1,'w':2,'h':2}, 'z': 10, 'text_blocks': [], 'style': None, 'padding_mm': None}
                ]},
                {'title': 'P2', 'page_size': {'w_mm': 210.0, 'h_mm': 297.0}, 'grid': {'cols': 4, 'rows': 4}, 'elements': []}
            ]
        }
        typst = pm.generate_typst(ir)
        # Expect bullet marker and both page titles in the TOC text
        self.assertIn('• P1', typst)
        self.assertIn('• P2', typst)
        # Ensure the element is placed via layer_grid
        self.assertIn('#layer_grid(gp,1,1,2,2, ', typst)

if __name__ == '__main__':
    unittest.main()
