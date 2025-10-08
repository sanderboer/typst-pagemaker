from pagemaker.generator import generate_typst


def _page():
    return {
        'id': 'p',
        'title': 'PDFModes',
        'page_size': {'w_mm': 210, 'h_mm': 210},
        'grid': {'cols': 4, 'rows': 4},
        'elements': [],
    }


def test_pdf_align_center_and_right_emits_align_wrapper():
    base = _page()
    base['elements'] = [
        {
            'id': 'pdf_center',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'pdf': {'src': 'dummy.pdf', 'pages': [1], 'scale_mode': 'contain'},
            'pdf_align': 'center',
        },
        {
            'id': 'pdf_right',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'pdf': {'src': 'dummy.pdf', 'pages': [1], 'scale_mode': 'contain'},
            'pdf_align': 'right',
        },
    ]
    ir = {'meta': {}, 'pages': [base]}
    typ = generate_typst(ir)
    # Expect align wrappers present
    assert 'align(center)[PdfEmbed("dummy.pdf", page: 1, scale:' in typ
    assert 'align(right)[PdfEmbed("dummy.pdf", page: 1, scale:' in typ


def test_pdf_scale_mode_cover_uses_larger_scale():
    # Frame aspect deliberately mismatched to force difference between contain and cover
    page = _page()
    page['elements'] = [
        {
            'id': 'pdf_contain',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 1},  # wide but short frame
            'pdf': {'src': 'dummy.pdf', 'pages': [1], 'scale_mode': 'contain'},
        },
        {
            'id': 'pdf_cover',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 1},
            'pdf': {'src': 'dummy.pdf', 'pages': [1], 'scale_mode': 'cover'},
        },
    ]
    ir = {'meta': {}, 'pages': [page]}
    typ = generate_typst(ir)
    import re

    scales = re.findall(r'PdfEmbed\("dummy.pdf", page: 1, scale: ([0-9.]+)\)', typ)
    assert len(scales) == 2
    s_contain, s_cover = (float(s) for s in scales)
    assert s_cover >= s_contain
