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


def test_full_page_pdf_generates_full_page_place():
    ir = {
        'meta': {},
        'pages': [
            {
                **_base_page(),
                'elements': [
                    {
                        'id': 'pdf1',
                        'type': 'pdf',
                        'area': {
                            'x': 1,
                            'y': 1,
                            'w': 2,
                            'h': 2,
                        },  # Smaller than grid to trigger warning semantics
                        'padding_mm': {'top': 5, 'right': 5, 'bottom': 5, 'left': 5},
                        'pdf': {
                            'src': 'dummy.pdf',
                            'pages': [1],
                            'fit': 'contain',  # fit provided
                            'full_page': True,
                        },
                    }
                ],
            }
        ],
    }
    typ = generate_typst(ir)
    # Expect full page placement comment and a place covering entire page
    assert 'FULL_PAGE placement' in typ
    # Since page size 210x297mm set at top; placement block should use that
    assert '#place(dx: 0mm, dy: 0mm' in typ
    # Ensure PdfEmbedFit helper used (fit / full_page path)
    assert 'PdfEmbedFit("dummy.pdf"' in typ


def test_pdf_fit_ignores_scale_and_uses_pdfembedfit():
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
                            'fit': 'contain',
                            'scale': 2.0,  # Should be ignored when fit present
                            'full_page': False,
                        },
                    }
                ],
            }
        ],
    }
    typ = generate_typst(ir)
    # Should use PdfEmbedFit (auto scaling)
    assert 'PdfEmbedFit("dummy.pdf"' in typ
    # PdfEmbedFit signature does not include scale parameter; ensure no explicit scale with dummy.pdf line
    lines = [line for line in typ.splitlines() if 'PdfEmbedFit("dummy.pdf"' in line]
    assert lines, 'Expected a line containing PdfEmbedFit call'
    for line in lines:
        assert 'scale:' not in line


def test_validation_warnings_for_full_page_and_scale_ignored():
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
                        'padding_mm': {'top': 1, 'right': 0, 'bottom': 0, 'left': 0},
                        'pdf': {
                            'src': 'dummy.pdf',
                            'pages': [1],
                            'fit': 'contain',
                            'full_page': True,
                        },
                    },
                    {
                        'id': 'pdf4',
                        'type': 'pdf',
                        'area': {'x': 1, 'y': 2, 'w': 4, 'h': 2},
                        'pdf': {
                            'src': 'dummy.pdf',
                            'pages': [1],
                            'fit': 'cover',
                            'scale': 1.5,
                        },
                    },
                ],
            }
        ],
    }
    result = validate_ir(ir)
    msgs = {(iss.path, iss.message, iss.severity) for iss in result.issues}
    # full_page padding warning
    assert any('full_page PDF ignores element padding' in m for _, m, _ in msgs)
    # full_page area dimension ignore warning
    assert any('full_page PDF ignores AREA dimensions' in m for _, m, _ in msgs)
    # scale ignored when fit specified
    assert any('scale ignored when fit specified for PDF' in m for _, m, _ in msgs)
