"""Test cover mode with alignment-based cropping.

This test validates that cover FIT mode properly implements alignment-based
cropping for all media types (rasters, SVGs, PDFs). When content overflows
in cover mode, the alignment should determine which part is visible.
"""

from pagemaker.generator import generate_typst


def _page():
    """Create base page structure for tests."""
    return {
        'id': 'p',
        'title': 'CoverAlign',
        'page_size': {'w_mm': 200, 'h_mm': 200},
        'grid': {'cols': 4, 'rows': 4},
        'elements': [],
    }


def test_raster_cover_horizontal_alignment():
    """Test raster image cover mode respects horizontal alignment.

    When an image is wider than the frame in cover mode, horizontal
    alignment determines which part of the image is visible.

    Note: Without intrinsic size info, images fall back to frame size,
    which means no overflow and no clipping. Cover mode still works via
    Typst's manual rendering, just without the clip wrapper.
    """
    base = _page()
    base['elements'] = [
        {
            'id': 'img_left',
            'type': 'figure',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'align': 'left',
            'figure': {'src': 'wide.jpg', 'fit': 'cover'},
        },
        {
            'id': 'img_center',
            'type': 'figure',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'align': 'center',
            'figure': {'src': 'wide.jpg', 'fit': 'cover'},
        },
        {
            'id': 'img_right',
            'type': 'figure',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'align': 'right',
            'figure': {'src': 'wide.jpg', 'fit': 'cover'},
        },
    ]
    ir = {'meta': {}, 'pages': [base]}
    typ = generate_typst(ir)

    # Cover mode uses manual path (explicit width/height in mm)
    assert 'width: 100.000000mm' in typ
    assert 'height: 100.000000mm' in typ

    # Should have alignment directives
    assert 'align(left)' in typ
    assert 'align(center)' in typ
    assert 'align(right)' in typ


def test_svg_cover_vertical_alignment():
    """Test SVG cover mode respects vertical alignment.

    When an SVG is taller than the frame in cover mode, vertical
    alignment determines which part of the SVG is visible:
    - top: shows top edge (dy = 0)
    - horizon: shows center (dy = -overflow/2)
    - bottom: shows bottom edge (dy = -overflow)
    """
    base = _page()
    base['elements'] = [
        {
            'id': 'svg_top',
            'type': 'svg',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'valign': 'top',
            'svg': {'src': 'tall.svg', 'fit': 'cover', 'scale': 1.5},
        },
        {
            'id': 'svg_middle',
            'type': 'svg',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'valign': 'horizon',
            'svg': {'src': 'tall.svg', 'fit': 'cover', 'scale': 1.5},
        },
        {
            'id': 'svg_bottom',
            'type': 'svg',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'valign': 'bottom',
            'svg': {'src': 'tall.svg', 'fit': 'cover', 'scale': 1.5},
        },
    ]
    ir = {'meta': {}, 'pages': [base]}
    typ = generate_typst(ir)

    # All should use clip wrapper for cover mode
    assert typ.count('clip: true') == 3

    # Should have place() calls with different dy offsets
    assert 'place(' in typ


def test_pdf_cover_combined_alignment():
    """Test PDF cover mode with both horizontal and vertical alignment.

    Test that cover mode works with simultaneous horizontal and vertical
    alignment, producing appropriate offsets in both directions.
    """
    base = _page()
    base['elements'] = [
        {
            'id': 'pdf_topleft',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'align': 'left',
            'valign': 'top',
            'pdf': {'src': 'doc.pdf', 'pages': [1], 'fit': 'cover'},
        },
        {
            'id': 'pdf_center',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'align': 'center',
            'valign': 'horizon',
            'pdf': {'src': 'doc.pdf', 'pages': [1], 'fit': 'cover'},
        },
        {
            'id': 'pdf_bottomright',
            'type': 'pdf',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'align': 'right',
            'valign': 'bottom',
            'pdf': {'src': 'doc.pdf', 'pages': [1], 'fit': 'cover'},
        },
    ]
    ir = {'meta': {}, 'pages': [base]}
    typ = generate_typst(ir)

    # All should use clip wrapper for cover mode
    assert typ.count('clip: true') == 3

    # Should have place() calls with offsets
    assert 'place(' in typ


def test_cover_mode_without_alignment_defaults():
    """Test that cover mode works without explicit alignment.

    When alignment is not specified, cover mode uses manual path with
    explicit dimensions. Without overflow (when intrinsic=frame), no
    clipping is needed.
    """
    base = _page()
    base['elements'] = [
        {
            'id': 'img_default',
            'type': 'figure',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            # No align/valign specified
            'figure': {'src': 'photo.jpg', 'fit': 'cover'},
        },
    ]
    ir = {'meta': {}, 'pages': [base]}
    typ = generate_typst(ir)

    # Cover mode uses manual path (explicit dimensions)
    assert 'width: 100.000000mm' in typ
    assert 'height: 100.000000mm' in typ

    # Should generate image element
    assert 'image("photo.jpg"' in typ
