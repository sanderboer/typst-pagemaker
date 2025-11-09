from pagemaker.generator import generate_typst


def _page():
    return {
        'id': 'pClamp',
        'title': 'ClampContain',
        'page_size': {'w_mm': 210, 'h_mm': 297},
        'grid': {'cols': 4, 'rows': 4},
        'elements': [],
    }


def test_pdf_contain_upscale_allowed():
    # Frame larger than intrinsic dummy (Letter default converted)
    # area spans full grid; containment scale may exceed 1.0 when upscaling allowed.
    page = _page()
    page['elements'] = [
        {
            'id': 'pdf_big_frame',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 4, 'h': 4},
            'pdf': {'src': 'dummy.pdf', 'pages': [1], 'fit': 'contain'},
        }
    ]
    ir = {'meta': {}, 'pages': [page]}
    typ = generate_typst(ir)
    import re

    m = re.search(r'PdfEmbed\("dummy.pdf", page: 1, scale: ([0-9.]+)\)', typ)
    assert m, 'PdfEmbed call with scale not found'
    scale = float(m.group(1))
    assert scale > 0


def test_pdf_cover_behaves_as_contain_same_scale():
    # Cover requested; policy enforces contain so scale identical.
    page = _page()
    page['elements'] = [
        {
            'id': 'pdf_cover',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 4, 'h': 4},
            'pdf': {'src': 'dummy.pdf', 'pages': [1], 'fit': 'cover'},
        },
        {
            'id': 'pdf_contain',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 4, 'h': 4},
            'pdf': {'src': 'dummy.pdf', 'pages': [1], 'fit': 'contain'},
        },
    ]
    ir = {'meta': {}, 'pages': [page]}
    typ = generate_typst(ir)
    import re

    scales = re.findall(r'PdfEmbed\("dummy.pdf", page: 1, scale: ([0-9.]+)\)', typ)
    assert len(scales) == 2
    assert abs(float(scales[0]) - float(scales[1])) < 1e-9
