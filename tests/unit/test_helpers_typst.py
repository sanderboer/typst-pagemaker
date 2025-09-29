#!/usr/bin/env python3
"""Tests for dynamic helper emissions in Typst output"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

import pagemaker as pm


class TestHelpersTypst(unittest.TestCase):
    def test_dynamic_helpers_emitted(self):
        ir = {
            'meta': {},
            'pages': [
                {
                    'title': 'P1',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [],
                }
            ],
        }
        typst = pm.generate_typst(ir)
        self.assertIn('#let date_iso =', typst)
        self.assertIn('#let date_yy_mm_dd =', typst)
        self.assertIn('#let date_dd_mm_yy =', typst)
        self.assertIn('#let page_no = context counter(page).display()', typst)
        self.assertIn('#let page_total = context counter(page).final().at(0)', typst)

    def test_date_override_and_date(self):
        ir1 = {
            'meta': {'DATE_OVERRIDE': '2020-01-02'},
            'pages': [
                {
                    'title': 'P1',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [],
                }
            ],
        }
        t1 = pm.generate_typst(ir1)
        self.assertIn('#let date_iso = "2020-01-02"', t1)
        self.assertIn('#let date_yy_mm_dd = "20.01.02"', t1)
        self.assertIn('#let date_dd_mm_yy = "02.01.20"', t1)
        ir2 = {
            'meta': {'DATE': '2021-12-31'},
            'pages': [
                {
                    'title': 'P1',
                    'page_size': {'w_mm': 210.0, 'h_mm': 297.0},
                    'grid': {'cols': 12, 'rows': 8},
                    'elements': [],
                }
            ],
        }
        t2 = pm.generate_typst(ir2)
        self.assertIn('#let date_iso = "2021-12-31"', t2)
        self.assertIn('#let date_yy_mm_dd = "21.12.31"', t2)
        self.assertIn('#let date_dd_mm_yy = "31.12.21"', t2)


if __name__ == '__main__':
    unittest.main()
