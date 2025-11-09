from pagemaker.generator import generate_typst


def _page():
    return {
        'id': 'p',
        'title': 'SVGFits',
        'page_size': {'w_mm': 200, 'h_mm': 200},
        'grid': {'cols': 4, 'rows': 4},
        'elements': [],
    }


def test_svg_cover_emits_clip_and_place_offset():
    # Frame is square (2x2 cells => 100x100mm if page 200mm with 4 cols/rows) and intrinsic fallback same;
    # Use cover mode with alignment to trigger manual path and clip wrapper (needs_clip False if no overflow).
    # To force overflow we give intrinsic aspect wider than frame by simulating via scale > 1
    base = _page()
    base['elements'] = [
        {
            'id': 'svg_cover',
            'type': 'svg',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 2},
            'align': 'center',
            'svg': {'src': 'dummy.svg', 'fit': 'cover', 'scale': 1.5},
        }
    ]
    ir = {'meta': {}, 'pages': [base]}
    typ = generate_typst(ir)
    # Expect clip wrapper block(... clip: true) due to cover overflow or manual path
    assert 'clip: true' in typ, typ
    # Expect place() offsets present (dx or dy) for centering overflow
    assert 'place(' in typ, typ


def test_svg_stretch_alignment_uses_manual_place_no_clip():
    base = _page()
    base['elements'] = [
        {
            'id': 'svg_stretch',
            'type': 'svg',
            'area': {'x': 1, 'y': 1, 'w': 2, 'h': 3},
            'align': 'right',
            'svg': {'src': 'dummy.svg', 'fit': 'stretch'},
        }
    ]
    ir = {'meta': {}, 'pages': [base]}
    typ = generate_typst(ir)
    # Alignment present with stretch triggers manual path (no Fig(image(... fit: "stretch")))
    assert 'Fig(image("dummy.svg", width: 100%, height: 100%, fit: "stretch")' not in typ
    # Stretch should not need clip wrapper
    assert 'clip: true' not in typ
    # place may be absent if no offset needed (stretch fills frame), so just assert image size explicit mm
    assert 'image("dummy.svg", width:' in typ and 'height:' in typ
