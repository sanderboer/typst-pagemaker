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


def test_pdf_fit_contain_vs_cover_rendering_paths():
    """Test that contain uses PdfEmbed (simple path) and cover uses manual path with clipping."""
    page = _page()
    page['elements'] = [
        {
            'id': 'pdf_contain',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 1},
            'pdf': {'src': 'dummy.pdf', 'pages': [1], 'fit': 'contain'},
        },
        {
            'id': 'pdf_cover',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 1},
            'pdf': {'src': 'dummy.pdf', 'pages': [1], 'fit': 'cover'},
        },
    ]
    ir = {'meta': {}, 'pages': [page]}
    typ = generate_typst(ir)
    import re

    # Contain mode uses PdfEmbed (simple path)
    pdf_embeds = re.findall(r'PdfEmbed\("dummy.pdf", page: 1, scale: ([0-9.]+)\)', typ)
    assert len(pdf_embeds) == 1, "Contain mode should use PdfEmbed"

    # Cover mode uses manual path with explicit image() call and clipping
    # Pattern: block(width: X, height: Y, clip: true)[...image("dummy.pdf", page: 1, width: X, height: Y)...]
    assert 'clip: true' in typ, "Cover mode should use clipping"
    manual_images = re.findall(
        r'image\("dummy.pdf", page: 1, width: ([0-9.]+)mm, height: ([0-9.]+)mm\)', typ
    )
    assert len(manual_images) == 1, "Cover mode should use manual image() rendering"
