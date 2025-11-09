from pagemaker.generator import generate_typst


def _page():
    return {
        'id': 'p2',
        'title': 'PDFAlignSizing',
        'page_size': {'w_mm': 200, 'h_mm': 200},
        'grid': {'cols': 5, 'rows': 5},
        'elements': [],
    }


def test_pdf_left_top_alignment_uses_sized_block():
    base = _page()
    base['elements'] = [
        {
            'id': 'pdf_left_top',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 3, 'h': 3},
            'pdf': {'src': 'dummy.pdf', 'pages': [1], 'fit': 'contain'},
            'align': 'left',
            'valign': 'top',
        },
        {
            'id': 'pdf_no_align',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 3, 'h': 3},
            'pdf': {'src': 'dummy.pdf', 'pages': [1], 'fit': 'contain'},
        },
    ]
    ir = {'meta': {}, 'pages': [base]}
    typ = generate_typst(ir)
    # Aligned element should use align wrapper directly with sized image (no extra block wrapper)
    assert 'align(left + top)[#image("dummy.pdf", page: 1, width:' in typ
    # Non-aligned should use PdfEmbed with scale mode
    assert 'PdfEmbed("dummy.pdf", page: 1, scale:' in typ
