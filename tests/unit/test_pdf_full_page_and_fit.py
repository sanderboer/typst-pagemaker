from pagemaker.generator import generate_typst
from pagemaker.validation import validate_ir


def _base_page():
    return {
        'id': 'p1',
        'title': 'Test',
        'page_size': {'w_mm': 210, 'h_mm': 297},
        'grid': {'cols': 4, 'rows': 4},
        'elements': [],
    }


def test_pdf_auto_contain_scale_caps_multiplier():
    ir = {
        'meta': {},
        'pages': [
            {
                **_base_page(),
                'elements': [
                    {
                        'id': 'pdf1',
                        'type': 'pdf',
                        'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
                        'pdf': {
                            'src': 'dummy.pdf',
                            'pages': [1],
                            'scale': 2.0,
                            # Legacy keys (ignored) should not affect output
                            'fit': 'contain',
                            'full_page': True,
                        },
                    }
                ],
            }
        ],
    }
    typ = generate_typst(ir)
    # Should not contain legacy helper or comments
    assert 'PdfEmbedFit(' not in typ
    assert 'FULL_PAGE placement' not in typ
    # Auto scale should cap multiplier above containment; scale should be <= 2.0 and not equal to 2.0
    assert 'PdfEmbed("dummy.pdf", page: 1, scale: 2.0)' not in typ
    assert 'PdfEmbed("dummy.pdf", page: 1, scale:' in typ


def test_pdf_scale_default_auto_contains():
    ir = {
        'meta': {},
        'pages': [
            {
                **_base_page(),
                'elements': [
                    {
                        'id': 'pdf2',
                        'type': 'pdf',
                        'area': {'x': 1, 'y': 1, 'w': 4, 'h': 2},
                        'pdf': {
                            'src': 'dummy.pdf',
                            'pages': [1],
                            # No scale provided => default 1.0 multiplier but auto contain applied
                        },
                    }
                ],
            }
        ],
    }
    typ = generate_typst(ir)
    # Expect PdfEmbed with computed auto scale (not necessarily 1.0)
    assert 'PdfEmbed("dummy.pdf", page: 1, scale:' in typ


def test_pdf_scale_with_padding_shrinks_frame():
    # Element padding should reduce available frame and thus lower base scale
    ir = {
        'meta': {},
        'pages': [
            {
                **_base_page(),
                'elements': [
                    {
                        'id': 'pdf_pad',
                        'type': 'pdf',
                        'area': {'x': 1, 'y': 1, 'w': 4, 'h': 4},
                        'padding_mm': {'top': 5, 'right': 5, 'bottom': 5, 'left': 5},
                        'pdf': {'src': 'dummy.pdf', 'pages': [1]},
                    },
                    {
                        'id': 'pdf_no_pad',
                        'type': 'pdf',
                        'area': {'x': 1, 'y': 1, 'w': 4, 'h': 4},
                        'pdf': {'src': 'dummy.pdf', 'pages': [1]},
                    },
                ],
            }
        ],
    }
    typ = generate_typst(ir)
    # Extract scale values
    import re

    scales = re.findall(r'PdfEmbed\("dummy.pdf", page: 1, scale: ([0-9.]+)\)', typ)
    assert len(scales) == 2
    s1, s2 = (float(s) for s in scales)
    # Padded version should have smaller scale
    assert s1 < s2


def test_pdf_scale_with_margins_exact_cover():
    # With margins declared, an element spanning only content tracks should not need +1 columns
    ir = {
        'meta': {},
        'pages': [
            {
                'id': 'p1',
                'title': 'Margins',
                'page_size': {'w_mm': 210, 'h_mm': 297},
                'grid': {'cols': 4, 'rows': 4},
                'margins_mm': {'top': 10, 'right': 10, 'bottom': 10, 'left': 10},
                'margins_declared': True,
                'elements': [
                    {
                        'id': 'pdf_content_only',
                        'type': 'pdf',
                        # Content grid starts at total index 2 when margins declared; span exactly content area
                        'area': {'x': 2, 'y': 2, 'w': 4, 'h': 4},
                        'pdf': {'src': 'dummy.pdf', 'pages': [1]},
                    },
                    {
                        'id': 'pdf_entire_page',
                        'type': 'pdf',
                        # Span including margin tracks (total grid 6x6 here)
                        'area': {'x': 1, 'y': 1, 'w': 6, 'h': 6},
                        'pdf': {'src': 'dummy.pdf', 'pages': [1]},
                    },
                ],
            }
        ],
    }
    typ = generate_typst(ir)
    import re

    scales = re.findall(r'PdfEmbed\("dummy.pdf", page: 1, scale: ([0-9.]+)\)', typ)
    assert len(scales) == 2
    s_content, s_full = (float(s) for s in scales)
    # Full page (including margins) frame larger => its contain scale >= content-only scale
    assert s_full >= s_content
    ir = {
        'meta': {},
        'pages': [
            {
                **_base_page(),
                'elements': [
                    {
                        'id': 'pdf2',
                        'type': 'pdf',
                        'area': {'x': 1, 'y': 1, 'w': 4, 'h': 2},
                        'pdf': {
                            'src': 'dummy.pdf',
                            'pages': [1],
                            # No scale provided => default 1.0
                        },
                    }
                ],
            }
        ],
    }
    typ = generate_typst(ir)
    # Expect PdfEmbed with computed auto scale (not necessarily 1.0)
    assert 'PdfEmbed("dummy.pdf", page: 1, scale:' in typ


def test_validation_errors_for_invalid_pdf_scale():
    ir = {
        'meta': {},
        'pages': [
            {
                **_base_page(),
                'elements': [
                    {
                        'id': 'pdf3',
                        'type': 'pdf',
                        'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
                        'pdf': {
                            'src': 'dummy.pdf',
                            'pages': [1],
                            'scale': 0,  # invalid
                        },
                    },
                    {
                        'id': 'pdf4',
                        'type': 'pdf',
                        'area': {'x': 1, 'y': 2, 'w': 4, 'h': 2},
                        'pdf': {
                            'src': 'dummy.pdf',
                            'pages': [1],
                            'scale': -1,  # invalid
                        },
                    },
                    {
                        'id': 'pdf5',
                        'type': 'pdf',
                        'area': {'x': 1, 'y': 3, 'w': 4, 'h': 1},
                        'pdf': {
                            'src': 'dummy.pdf',
                            'pages': [1],
                            'scale': 'big',  # not numeric
                        },
                    },
                ],
            }
        ],
    }
    result = validate_ir(ir)
    msgs = {(iss.path, iss.message) for iss in result.issues}
    assert ('/pages/0/elements/0/pdf/scale', 'PDF scale must be > 0') in msgs
    assert ('/pages/0/elements/1/pdf/scale', 'PDF scale must be > 0') in msgs
    assert ('/pages/0/elements/2/pdf/scale', 'PDF scale must be a number') in msgs


def test_pdf_scale_with_subunit_multiplier_is_ignored():
    # Two identical frames; second has user multiplier 0.5 but scaling is auto-contained and ignores user multiplier.
    ir = {
        'meta': {},
        'pages': [
            {
                **_base_page(),
                'elements': [
                    {
                        'id': 'pdf_full',
                        'type': 'pdf',
                        'area': {'x': 1, 'y': 1, 'w': 4, 'h': 4},
                        'pdf': {'src': 'dummy.pdf', 'pages': [1]},  # implicit multiplier 1.0
                    },
                    {
                        'id': 'pdf_half',
                        'type': 'pdf',
                        'area': {'x': 1, 'y': 1, 'w': 4, 'h': 4},
                        'pdf': {'src': 'dummy.pdf', 'pages': [1], 'scale': 0.5},
                    },
                ],
            }
        ],
    }
    typ = generate_typst(ir)
    import re

    scales = re.findall(r'PdfEmbed\("dummy.pdf", page: 1, scale: ([0-9.]+)\)', typ)
    assert len(scales) == 2
    s_full, s_half = (float(s) for s in scales)
    # User multiplier 0.5 ignored => scales equal (allow tiny formatting diff)
    assert abs(s_full - s_half) < 1e-9


def test_pdf_scale_with_margins_and_padding_combined():
    # One element spans full page (including margins) with padding; another without padding.
    # Padded element should have reduced frame and thus smaller scale.
    ir = {
        'meta': {},
        'pages': [
            {
                'id': 'p1',
                'title': 'MarginsPad',
                'page_size': {'w_mm': 210, 'h_mm': 297},
                'grid': {'cols': 4, 'rows': 4},
                'margins_mm': {'top': 12, 'right': 15, 'bottom': 12, 'left': 15},
                'margins_declared': True,
                'elements': [
                    {
                        'id': 'pdf_full_no_pad',
                        'type': 'pdf',
                        'area': {
                            'x': 1,
                            'y': 1,
                            'w': 6,
                            'h': 6,
                        },  # total grid includes margin tracks
                        'pdf': {'src': 'dummy.pdf', 'pages': [1]},
                    },
                    {
                        'id': 'pdf_full_padded',
                        'type': 'pdf',
                        'area': {'x': 1, 'y': 1, 'w': 6, 'h': 6},
                        'padding_mm': {'top': 4, 'right': 8, 'bottom': 4, 'left': 8},
                        'pdf': {'src': 'dummy.pdf', 'pages': [1]},
                    },
                ],
            }
        ],
    }
    typ = generate_typst(ir)
    import re

    scales = re.findall(r'PdfEmbed\("dummy.pdf", page: 1, scale: ([0-9.]+)\)', typ)
    assert len(scales) == 2
    s_no_pad, s_padded = (float(s) for s in scales)
    assert s_padded < s_no_pad
