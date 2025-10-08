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


def test_pdf_scale_explicit_embeds_scale_only():
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
    # Should contain PdfEmbed with explicit scale 2.0
    assert 'PdfEmbed("dummy.pdf", page: 1, scale: 2.0)' in typ


def test_pdf_scale_default_is_one():
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
    # Expect PdfEmbed with scale 1.0 (default)
    assert 'PdfEmbed("dummy.pdf", page: 1, scale: 1.0)' in typ


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
