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
    # Both should use PdfEmbed (no caption), but aligned gets align wrapper
    assert 'align(left + top)[#PdfEmbed("dummy.pdf", page: 1, scale:' in typ
    # Non-aligned should use PdfEmbed without align wrapper
    import re

    # Find the non-aligned element section (entire layer_grid call)
    no_align_match = re.search(
        r'// Element pdf_no_align.*?#layer_grid\([^)]+, (PdfEmbed[^)]+\)[^)]*)\)', typ, re.DOTALL
    )
    assert no_align_match is not None
    no_align_code = no_align_match.group(1)
    assert 'PdfEmbed("dummy.pdf", page: 1, scale:' in no_align_code
    assert 'align(' not in no_align_code
