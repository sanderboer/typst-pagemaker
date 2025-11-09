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


def test_pdf_cover_uses_manual_path_with_clipping():
    """Test that cover mode uses manual rendering path with clipping, while contain uses PdfEmbed."""
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

    # Contain should use PdfEmbed (simple path)
    pdf_embeds = re.findall(r'PdfEmbed\("dummy.pdf", page: 1, scale: ([0-9.]+)\)', typ)
    assert len(pdf_embeds) == 1, "Contain mode should use PdfEmbed"

    # Cover should use manual path with clipping
    assert 'clip: true' in typ, "Cover mode should use clipping"
    # Cover uses image() with explicit dimensions in a clipping block
    manual_images = re.findall(
        r'image\("dummy.pdf", page: 1, width: ([0-9.]+)mm, height: ([0-9.]+)mm\)', typ
    )
    assert len(manual_images) == 1, "Cover mode should use manual image() rendering"
