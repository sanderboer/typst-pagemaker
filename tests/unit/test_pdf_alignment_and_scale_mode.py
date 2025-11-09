from pagemaker.generator import generate_typst


def _page():
    return {
        'id': 'p',
        'title': 'PDFModes',
        'page_size': {'w_mm': 210, 'h_mm': 210},
        'grid': {'cols': 4, 'rows': 4},
        'elements': [],
    }


def test_pdf_align_center_right_and_valign_middle_emits_align_wrapper():
    base = _page()
    base['elements'] = [
        {
            'id': 'pdf_center',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'pdf': {'src': 'dummy.pdf', 'pages': [1], 'fit': 'contain'},
            'align': 'center',
        },
        {
            'id': 'pdf_right',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'pdf': {'src': 'dummy.pdf', 'pages': [1], 'fit': 'contain'},
            'align': 'right',
        },
        {
            'id': 'pdf_middle',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'pdf': {'src': 'dummy.pdf', 'pages': [1], 'fit': 'contain'},
            'valign': 'middle',
        },
    ]
    ir = {'meta': {}, 'pages': [base]}
    typ = generate_typst(ir)
    # Expect align wrappers present for aligned PDFs
    assert 'align(center)[' in typ
    assert 'align(right)[' in typ
    # Middle vertical alignment maps to horizon token
    assert 'align(horizon)[' in typ


def test_pdf_scale_mode_always_contain():
    page = _page()
    page['elements'] = [
        {
            'id': 'pdf_contain',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 1},
            'pdf': {'src': 'dummy.pdf', 'pages': [1], 'fit': 'contain'},
        },
        {
            'id': 'pdf_cover_ignored',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 1},
            'pdf': {'src': 'dummy.pdf', 'pages': [1], 'fit': 'cover'},
        },
    ]
    ir = {'meta': {}, 'pages': [page]}
    typ = generate_typst(ir)
    import re

    scales = re.findall(r'PdfEmbed\("dummy.pdf", page: 1, scale: ([0-9.]+)\)', typ)
    # Both elements should now share identical contain scaling
    assert len(scales) == 2
    assert abs(float(scales[0]) - float(scales[1])) < 1e-9
