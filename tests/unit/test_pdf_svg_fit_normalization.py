import pathlib
import warnings

from pagemaker.parser import parse_org


def _write_tmp(tmp_path: pathlib.Path, content: str) -> pathlib.Path:
    p = tmp_path / "doc.org"
    p.write_text(content, encoding="utf-8")
    return p


def test_pdf_fit_valid_cover_no_warning(tmp_path):
    """Valid FIT value 'cover' should be preserved with no FIT warning."""
    org = """* Page
** PDF Item
:PROPERTIES:
:TYPE: pdf
:FIT: cover
:PDF: example.pdf
:END:
"""
    path = _write_tmp(tmp_path, org)
    with warnings.catch_warnings(record=True) as w:
        ir = parse_org(str(path))
    pdf_el = ir["pages"][0]["elements"][0]["pdf"]
    assert pdf_el["fit"] == "cover"  # preserved
    # No FIT warning for valid value (filter out deprecation warnings about :PDF:)
    fit_warnings = [x for x in w if ":FIT:" in str(x.message) and "PDF" in str(x.message)]
    assert len(fit_warnings) == 0


def test_svg_fit_valid_stretch_no_warning(tmp_path):
    """Valid FIT value 'stretch' should be preserved with no FIT warning."""
    org = """* Page
** SVG Item
:PROPERTIES:
:TYPE: svg
:FIT: stretch
:SVG: example.svg
:END:
"""
    path = _write_tmp(tmp_path, org)
    with warnings.catch_warnings(record=True) as w:
        ir = parse_org(str(path))
    svg_el = ir["pages"][0]["elements"][0]["svg"]
    assert svg_el["fit"] == "stretch"  # preserved
    fit_warnings = [x for x in w if ":FIT:" in str(x.message) and "SVG" in str(x.message)]
    assert len(fit_warnings) == 0


def test_pdf_fit_unknown_fallback(tmp_path):
    """Unknown FIT value should fallback to contain with warning."""
    org = """* Page
** PDF Item
:PROPERTIES:
:TYPE: pdf
:FIT: weirdmode
:PDF: example.pdf
:END:
"""
    path = _write_tmp(tmp_path, org)
    with warnings.catch_warnings(record=True) as w:
        ir = parse_org(str(path))
    pdf_el = ir["pages"][0]["elements"][0]["pdf"]
    assert pdf_el["fit"] == "contain"  # fallback
    fit_warnings = [x for x in w if ":FIT:" in str(x.message) and "PDF" in str(x.message)]
    assert len(fit_warnings) == 1
    msg = str(fit_warnings[0].message)
    assert "'weirdmode'" in msg and "falling back to 'contain'" in msg


def test_svg_fit_unknown_fallback(tmp_path):
    """Unknown FIT value should fallback to contain with warning for SVG."""
    org = """* Page
** SVG Item
:PROPERTIES:
:TYPE: svg
:FIT: oddity
:SVG: example.svg
:END:
"""
    path = _write_tmp(tmp_path, org)
    with warnings.catch_warnings(record=True) as w:
        ir = parse_org(str(path))
    svg_el = ir["pages"][0]["elements"][0]["svg"]
    assert svg_el["fit"] == "contain"  # fallback
    fit_warnings = [x for x in w if ":FIT:" in str(x.message) and "SVG" in str(x.message)]
    assert len(fit_warnings) == 1
    msg = str(fit_warnings[0].message)
    assert "'oddity'" in msg and "falling back to 'contain'" in msg
