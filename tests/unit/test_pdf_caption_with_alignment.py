"""Test that PDFs with both caption and alignment work correctly."""

from pagemaker.generator import generate_typst


def _page():
    return {
        'id': 'p',
        'title': 'PDFWithCaptions',
        'page_size': {'w_mm': 210, 'h_mm': 297},
        'grid': {'cols': 4, 'rows': 4},
        'elements': [],
    }


def test_pdf_with_caption_and_no_alignment_uses_100_percent_sizing():
    """PDFs with caption but no alignment should fill the cell with 100% sizing."""
    page = _page()
    page['elements'] = [
        {
            'id': 'pdf_caption_no_align',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'pdf': {
                'src': 'test.pdf',
                'pages': [1],
                'fit': 'contain',
                'caption': 'Test Caption No Align',
            },
        },
    ]
    ir = {'meta': {}, 'pages': [page]}
    typ = generate_typst(ir)

    # Should use Fig() with caption
    assert 'Fig(' in typ
    assert 'Test Caption No Align' in typ
    # Should use 100% sizing when no alignment specified
    assert 'width: 100%, height: 100%' in typ


def test_pdf_with_caption_and_alignment_omits_100_percent_sizing():
    """PDFs with caption AND alignment should NOT use 100% sizing to allow alignment."""
    page = _page()
    page['elements'] = [
        {
            'id': 'pdf_caption_with_align',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'pdf': {
                'src': 'test.pdf',
                'pages': [1],
                'fit': 'contain',
                'caption': 'Test Caption With Align',
            },
            'align': 'right',
            'valign': 'bottom',
        },
    ]
    ir = {'meta': {}, 'pages': [page]}
    typ = generate_typst(ir)

    # Should use Fig() with caption
    assert 'Fig(' in typ
    assert 'Test Caption With Align' in typ
    # Should pass fill_space: false to allow alignment
    assert 'fill_space: false' in typ
    # Image call itself should NOT have 100% sizing
    assert 'image("test.pdf", page: 1, fit: "contain")' in typ
    # Should have the alignment wrapper around Fig()
    assert 'align(right + bottom)[' in typ


def test_image_with_caption_and_alignment_omits_100_percent_sizing():
    """Regular images with caption AND alignment should NOT use 100% sizing."""
    page = _page()
    page['elements'] = [
        {
            'id': 'img_caption_with_align',
            'type': 'figure',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'figure': {
                'src': 'test.jpg',
                'fit': 'contain',
                'caption': 'Image Caption With Align',
            },
            'align': 'center',
            'valign': 'middle',
        },
    ]
    ir = {'meta': {}, 'pages': [page]}
    typ = generate_typst(ir)

    # Should use Fig() with caption
    assert 'Fig(' in typ
    assert 'Image Caption With Align' in typ
    # Should pass fill_space: false to allow alignment
    assert 'fill_space: false' in typ
    # Image call itself should NOT have 100% sizing
    assert 'image("test.jpg", fit: "contain")' in typ
    # Should have alignment wrapper (middle maps to horizon)
    assert 'align(center + horizon)[' in typ


def test_image_with_caption_no_alignment_uses_100_percent_sizing():
    """Images with caption but no alignment should fill the cell."""
    page = _page()
    page['elements'] = [
        {
            'id': 'img_caption_no_align',
            'type': 'figure',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'figure': {
                'src': 'test.jpg',
                'fit': 'contain',
                'caption': 'Image Caption No Align',
            },
        },
    ]
    ir = {'meta': {}, 'pages': [page]}
    typ = generate_typst(ir)

    # Should use Fig() with caption
    assert 'Fig(' in typ
    assert 'Image Caption No Align' in typ
    # Should use 100% sizing when no alignment
    assert 'width: 100%, height: 100%' in typ


def test_pdf_without_caption_uses_pdfembed():
    """PDFs without captions should use PdfEmbed (legacy behavior)."""
    page = _page()
    page['elements'] = [
        {
            'id': 'pdf_no_caption',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'pdf': {
                'src': 'test.pdf',
                'pages': [1],
                'fit': 'contain',
            },
        },
    ]
    ir = {'meta': {}, 'pages': [page]}
    typ = generate_typst(ir)

    # Should use PdfEmbed in actual rendering (not Fig)
    import re

    element_section = re.search(r'// Element pdf_no_caption.*?// END PAGE CONTENT', typ, re.DOTALL)
    assert element_section is not None
    element_code = element_section.group(0)
    assert 'PdfEmbed(' in element_code
    assert 'Fig(' not in element_code
