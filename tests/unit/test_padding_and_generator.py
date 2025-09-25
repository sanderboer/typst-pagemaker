#!/usr/bin/env python3
"""Tests for padding parsing and generator emission"""
import unittest
import sys
import os

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker as pm
from pagemaker.parser import parse_padding


class TestParsePadding(unittest.TestCase):
    def test_none_and_empty(self):
        self.assertIsNone(parse_padding(None))
        self.assertIsNone(parse_padding(" "))

    def test_single_value(self):
        pad = parse_padding("10")
        self.assertEqual(pad, {"top": 10.0, "right": 10.0, "bottom": 10.0, "left": 10.0})

    def test_two_values(self):
        pad = parse_padding("10, 20")
        self.assertEqual(pad, {"top": 10.0, "right": 20.0, "bottom": 10.0, "left": 20.0})

    def test_three_values(self):
        pad = parse_padding("10 20 30")
        self.assertEqual(pad, {"top": 10.0, "right": 20.0, "bottom": 30.0, "left": 20.0})

    def test_four_values(self):
        pad = parse_padding("1,2,3,4")
        self.assertEqual(pad, {"top": 1.0, "right": 2.0, "bottom": 3.0, "left": 4.0})

    def test_invalid(self):
        self.assertIsNone(parse_padding("a,b"))
        self.assertIsNone(parse_padding("1, two"))


class TestGeneratorPaddedEmission(unittest.TestCase):
    def make_ir(self, pad=None):
        return {
            'meta': {},
            'pages': [{
                'title': 'P',
                'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                'grid': {'cols': 12, 'rows': 8},
                'elements': [{
                    'id': 't', 'type': 'body',
                    'area': {'x': 1, 'y': 1, 'w': 2, 'h': 1},
                    'z': 10,
                    'text_blocks': [{'kind': 'plain', 'content': 'Hello'}],
                    'style': None,
                    'padding_mm': pad,
                }]
            }]
        }

    def test_emits_layer_grid_padded(self):
        pad = {"top": 5.0, "right": 10.0, "bottom": 15.0, "left": 20.0}
        ir = self.make_ir(pad)
        typst = pm.generate_typst(ir)
        self.assertIn("#layer_grid_padded", typst)
        # Check the specific invocation values appear
        self.assertIn("gp,1,1,2,1", typst)
        self.assertIn(" 5.0mm, 10.0mm, 15.0mm, 20.0mm", typst)

    def test_emits_layer_grid_when_no_padding(self):
        ir = self.make_ir(pad=None)
        typst = pm.generate_typst(ir)
        # No padded call, should contain the plain layer_grid placement
        self.assertIn("#layer_grid(gp,1,1,2,1", typst)

    def test_macro_contains_clamp_logic(self):
        # The macro should clamp negative frame sizes to 0mm
        ir = self.make_ir(pad={"top": 1000.0, "right": 1000.0, "bottom": 1000.0, "left": 1000.0})
        typst = pm.generate_typst(ir)
        self.assertIn("if frame_w < 0mm { frame_w = 0mm }", typst)
        self.assertIn("if frame_h < 0mm { frame_h = 0mm }", typst)


if __name__ == '__main__':
    unittest.main()
