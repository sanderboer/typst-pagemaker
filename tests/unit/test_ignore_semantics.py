#!/usr/bin/env python3
"""Tests for IGNORE semantics in the Org parser"""

import os
import pathlib
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker as pm


class TestIgnoreSemantics(unittest.TestCase):
    def test_page_level_ignore_removes_page(self):
        org = """#+TITLE: Ignore Page Test

* Page One
:PROPERTIES:
:IGNORE: true
:END:

** Section Visible
:PROPERTIES:
:TYPE: body
:END:
Visible text

* Page Two
:PROPERTIES:
:END:

** Section Two
:PROPERTIES:
:TYPE: body
:END:
Content
"""
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / 'ignore_page.org'
            p.write_text(org, encoding='utf-8')
            ir = pm.parse_org(str(p))
            # Only Page Two should remain
            self.assertEqual(len(ir['pages']), 1)
            self.assertEqual(ir['pages'][0]['title'], 'Page Two')
            # Elements under ignored page must not leak
            types = [e['type'] for e in ir['pages'][0]['elements']]
            self.assertIn('body', types)

    def test_section_level_ignore_removes_subtree(self):
        org = """#+TITLE: Ignore Section Test

* Page
:PROPERTIES:
:END:

** Keep Me
:PROPERTIES:
:TYPE: body
:END:
Keep text

** Ignore Me
:PROPERTIES:
:TYPE: body
:IGNORE: true
:END:
Ignored body content

*** Child A
:PROPERTIES:
:TYPE: figure
:END:
[[file:examples/test-images/forest.jpg]]

*** Child B
:PROPERTIES:
:TYPE: body
:END:
Nested text

** Sibling Visible
:PROPERTIES:
:TYPE: body
:END:
Sibling text
"""
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / 'ignore_section.org'
            p.write_text(org, encoding='utf-8')
            ir = pm.parse_org(str(p))
            els = ir['pages'][0]['elements']
            titles = [e['title'] for e in els]
            # The ignored section and its children should be absent
            self.assertIn('Keep Me', titles)
            self.assertIn('Sibling Visible', titles)
            self.assertNotIn('Ignore Me', titles)
            self.assertNotIn('Child A', titles)
            self.assertNotIn('Child B', titles)

    def test_type_none_or_missing_omits_element_but_keeps_children(self):
        org = """#+TITLE: Type None/Missing Test

* Page
:PROPERTIES:
:END:

** Parent None
:PROPERTIES:
:TYPE: none
:END:
This element should be omitted

*** Child Of None
:PROPERTIES:
:TYPE: body
:END:
I should appear

** Missing Type With Image
:PROPERTIES:
:END:
[[file:examples/test-images/forest.jpg]]

*** Child Of Missing Type
:PROPERTIES:
:TYPE: figure
:END:
[[file:examples/test-images/forest.jpg]]
"""
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / 'type_none_missing.org'
            p.write_text(org, encoding='utf-8')
            ir = pm.parse_org(str(p))
            els = ir['pages'][0]['elements']
            titles = [e['title'] for e in els]
            types = [e['type'] for e in els]
            # Parent with TYPE none is omitted
            self.assertNotIn('Parent None', titles)
            # Child under TYPE none parent should exist
            self.assertIn('Child Of None', titles)
            # Missing TYPE with single image should NOT be emitted (no inference emission)
            self.assertNotIn('Missing Type With Image', titles)
            # But its child with declared TYPE should appear
            self.assertIn('Child Of Missing Type', titles)
            # Ensure types only include declared ones (body/figure), not inferred from parent
            self.assertIn('body', types)
            self.assertIn('figure', types)


if __name__ == '__main__':
    unittest.main()
