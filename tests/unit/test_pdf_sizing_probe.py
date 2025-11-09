import math

from pagemaker.generation.pdf_processor import pdf_intrinsic_size_mm, probe_pdf_points_per_inch


def test_probe_returns_float_and_caches():
    v1 = probe_pdf_points_per_inch()
    v2 = probe_pdf_points_per_inch()
    assert isinstance(v1, float) and isinstance(v2, float)
    assert v1 == v2  # cached
    assert math.isfinite(v1) and v1 > 0


def test_intrinsic_size_uses_probe_default_when_no_env():
    # Use a path that does not exist but is a non-empty string
    w_mm, h_mm = pdf_intrinsic_size_mm("nonexistent.pdf")
    # Expected dimensions for Letter at 72 pt/in (probe default):
    # width_pt = 612 -> 612 * 25.4 / 72 = 215.9 mm approx
    # height_pt = 792 -> 792 * 25.4 / 72 = 279.4 mm approx
    assert abs(w_mm - 215.9) < 0.5
    assert abs(h_mm - 279.4) < 0.5


def test_intrinsic_size_respects_env_override(monkeypatch):
    # Use a different path to avoid cached size from previous test
    monkeypatch.setenv("PAGEMAKER_PDF_PT_PER_IN", "72")
    w_mm, h_mm = pdf_intrinsic_size_mm("nonexistent_override.pdf")
    # Letter at 72 pt/in => 215.9 x 279.4 mm approx
    assert abs(w_mm - 215.9) < 0.5
    assert abs(h_mm - 279.4) < 0.5
