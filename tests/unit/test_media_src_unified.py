import pathlib
import warnings

from pagemaker.parser import parse_org


def _write_tmp(tmp_path: pathlib.Path, content: str) -> pathlib.Path:
    p = tmp_path / 'doc.org'
    p.write_text(content, encoding='utf-8')
    return p


def test_pdf_src_precedence(tmp_path):
    org = """* Page
** Item
:PROPERTIES:
:TYPE: pdf
:PDF: legacy.pdf
:SRC: new.pdf
:PAGE: 2
:SCALE: 1.5
:END:
"""
    path = _write_tmp(tmp_path, org)
    with warnings.catch_warnings(record=True) as w:
        ir = parse_org(str(path))
    pages = ir['pages']
    assert pages[0]['elements'][0]['pdf']['src'] == 'new.pdf'
    # Expect a deprecation warning about :PDF: ignored
    assert any(':PDF: ignored' in str(x.message) for x in w)


def test_pdf_src_legacy_warning(tmp_path):
    org = """* Page
** Item
:PROPERTIES:
:TYPE: pdf
:PDF: legacy.pdf
:END:
"""
    path = _write_tmp(tmp_path, org)
    with warnings.catch_warnings(record=True) as w:
        ir = parse_org(str(path))
    pdf_el = ir['pages'][0]['elements'][0]['pdf']
    assert pdf_el['src'] == 'legacy.pdf'
    assert any('deprecated :PDF:' in str(x.message) for x in w)


def test_svg_src_precedence(tmp_path):
    org = """* Page
** Item
:PROPERTIES:
:TYPE: svg
:SVG: legacy.svg
:SRC: new.svg
:SCALE: 2.0
:END:
"""
    path = _write_tmp(tmp_path, org)
    with warnings.catch_warnings(record=True) as w:
        ir = parse_org(str(path))
    svg_el = ir['pages'][0]['elements'][0]['svg']
    assert svg_el['src'] == 'new.svg'
    assert any(':SVG: ignored' in str(x.message) for x in w)


def test_svg_src_legacy_warning(tmp_path):
    org = """* Page
** Item
:PROPERTIES:
:TYPE: svg
:SVG: legacy.svg
:END:
"""
    path = _write_tmp(tmp_path, org)
    with warnings.catch_warnings(record=True) as w:
        ir = parse_org(str(path))
    svg_el = ir['pages'][0]['elements'][0]['svg']
    assert svg_el['src'] == 'legacy.svg'
    assert any('deprecated :SVG:' in str(x.message) for x in w)


def test_figure_src_overrides_link(tmp_path):
    org = """* Page
** Fig
:PROPERTIES:
:TYPE: figure
:SRC: override.jpg
:FIT: cover
:END:

[[file:implicit.jpg]]
"""
    path = _write_tmp(tmp_path, org)
    ir = parse_org(str(path))
    fig_el = ir['pages'][0]['elements'][0]['figure']
    assert fig_el['src'] == 'override.jpg'
    assert fig_el['fit'] == 'cover'


def test_figure_link_used_when_no_src(tmp_path):
    org = """* Page
** Fig
:PROPERTIES:
:TYPE: figure
:END:

[[file:implicit.jpg]]
"""
    path = _write_tmp(tmp_path, org)
    ir = parse_org(str(path))
    fig_el = ir['pages'][0]['elements'][0]['figure']
    assert fig_el['src'] == 'implicit.jpg'


def test_pdf_link_used_when_no_src(tmp_path):
    org = """* Page
** PDF Item
:PROPERTIES:
:TYPE: pdf
:AREA: A1,C3
:END:

[[file:document.pdf]]
"""
    path = _write_tmp(tmp_path, org)
    ir = parse_org(str(path))
    pdf_el = ir['pages'][0]['elements'][0]['pdf']
    assert pdf_el['src'] == 'document.pdf'


def test_pdf_src_overrides_link(tmp_path):
    org = """* Page
** PDF Item
:PROPERTIES:
:TYPE: pdf
:SRC: override.pdf
:AREA: A1,C3
:END:

[[file:implicit.pdf]]
"""
    path = _write_tmp(tmp_path, org)
    ir = parse_org(str(path))
    pdf_el = ir['pages'][0]['elements'][0]['pdf']
    assert pdf_el['src'] == 'override.pdf'


def test_pdf_link_overrides_legacy(tmp_path):
    org = """* Page
** PDF Item
:PROPERTIES:
:TYPE: pdf
:PDF: legacy.pdf
:AREA: A1,C3
:END:

[[file:link.pdf]]
"""
    path = _write_tmp(tmp_path, org)
    with warnings.catch_warnings(record=True) as w:
        ir = parse_org(str(path))
    pdf_el = ir['pages'][0]['elements'][0]['pdf']
    assert pdf_el['src'] == 'link.pdf'
    # Expect a deprecation warning about :PDF: ignored
    assert any(':PDF: ignored because [[file:]]' in str(x.message) for x in w)


def test_svg_link_used_when_no_src(tmp_path):
    org = """* Page
** SVG Item
:PROPERTIES:
:TYPE: svg
:AREA: A1,C3
:END:

[[file:graphic.svg]]
"""
    path = _write_tmp(tmp_path, org)
    ir = parse_org(str(path))
    svg_el = ir['pages'][0]['elements'][0]['svg']
    assert svg_el['src'] == 'graphic.svg'


def test_svg_src_overrides_link(tmp_path):
    org = """* Page
** SVG Item
:PROPERTIES:
:TYPE: svg
:SRC: override.svg
:AREA: A1,C3
:END:

[[file:implicit.svg]]
"""
    path = _write_tmp(tmp_path, org)
    ir = parse_org(str(path))
    svg_el = ir['pages'][0]['elements'][0]['svg']
    assert svg_el['src'] == 'override.svg'


def test_svg_link_overrides_legacy(tmp_path):
    org = """* Page
** SVG Item
:PROPERTIES:
:TYPE: svg
:SVG: legacy.svg
:AREA: A1,C3
:END:

[[file:link.svg]]
"""
    path = _write_tmp(tmp_path, org)
    with warnings.catch_warnings(record=True) as w:
        ir = parse_org(str(path))
    svg_el = ir['pages'][0]['elements'][0]['svg']
    assert svg_el['src'] == 'link.svg'
    # Expect a deprecation warning about :SVG: ignored
    assert any(':SVG: ignored because [[file:]]' in str(x.message) for x in w)
