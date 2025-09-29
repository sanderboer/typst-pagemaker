#!/usr/bin/env python3
"""Tests for ALIGN/VALIGN/FLOW mapping in generator"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker as pm


class TestAlignAndFlow(unittest.TestCase):
    def test_align_and_valign_wrapping(self):
        ir = {
            'meta': {},
            'pages': [
                {
                    'title': 'P',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [
                        {
                            'id': 't',
                            'type': 'body',
                            'area': {'x': 1, 'y': 1, 'w': 3, 'h': 2},
                            'z': 10,
                            'text_blocks': [{'kind': 'plain', 'content': 'Hello'}],
                            'style': None,
                            'align': 'center',
                            'valign': 'middle',
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        # Should emit align(center + horizon)[...]
        self.assertIn('align(center + horizon)[', typst)

    def test_flow_comment(self):
        ir = {
            'meta': {},
            'pages': [
                {
                    'title': 'P',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [
                        {
                            'id': 't',
                            'type': 'body',
                            'area': {'x': 2, 'y': 2, 'w': 3, 'h': 1},
                            'z': 10,
                            'text_blocks': [{'kind': 'plain', 'content': 'Flow Me'}],
                            'style': None,
                            'flow': 'bottom-up',
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        self.assertIn('// FLOW: bottom-up', typst)

    def test_flow_bottom_up_implies_bottom_valign(self):
        ir = {
            'meta': {},
            'pages': [
                {
                    'title': 'P',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [
                        {
                            'id': 't',
                            'type': 'body',
                            'area': {'x': 3, 'y': 3, 'w': 2, 'h': 2},
                            'z': 10,
                            'text_blocks': [{'kind': 'plain', 'content': 'Bottom'}],
                            'style': None,
                            'flow': 'bottom-up',
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        self.assertIn('align(bottom)[', typst)

    def test_flow_center_out_implies_vertical_center(self):
        ir = {
            'meta': {},
            'pages': [
                {
                    'title': 'P',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [
                        {
                            'id': 't',
                            'type': 'body',
                            'area': {'x': 3, 'y': 3, 'w': 2, 'h': 2},
                            'z': 10,
                            'text_blocks': [{'kind': 'plain', 'content': 'Center'}],
                            'style': None,
                            'flow': 'center-out',
                        }
                    ],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        self.assertIn('align(horizon)[', typst)


if __name__ == '__main__':
    unittest.main()
