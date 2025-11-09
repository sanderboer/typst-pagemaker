"""Unit tests for SVG intrinsic size detection."""

from pagemaker.generation.media_sizing import SvgSizeProvider


class TestSvgSizeProvider:
    """Test SVG viewBox and dimension parsing."""

    def setup_method(self):
        """Initialize provider for each test."""
        self.provider = SvgSizeProvider()

    def test_viewbox_parsing_standard_format(self, tmp_path):
        """Test parsing standard viewBox="0 0 width height" format."""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg viewBox="0 0 200 100" xmlns="http://www.w3.org/2000/svg">
    <rect width="200" height="100" fill="blue"/>
</svg>''')

        result = self.provider.get_size_mm(str(svg_file))
        assert result is not None
        w_mm, h_mm = result

        # 200 units * (25.4/96) = 52.916667mm
        # 100 units * (25.4/96) = 26.458333mm
        assert abs(w_mm - 52.917) < 0.01
        assert abs(h_mm - 26.458) < 0.01

    def test_viewbox_with_negative_offset(self, tmp_path):
        """Test viewBox with negative min-x/min-y (should use width/height only)."""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg viewBox="-50 -25 300 150" xmlns="http://www.w3.org/2000/svg">
    <circle cx="0" cy="0" r="50"/>
</svg>''')

        result = self.provider.get_size_mm(str(svg_file))
        assert result is not None
        w_mm, h_mm = result

        # Should use 300x150 (width/height), ignore offset
        assert abs(w_mm - 79.375) < 0.01  # 300 * 25.4/96
        assert abs(h_mm - 39.688) < 0.01  # 150 * 25.4/96

    def test_viewbox_with_decimal_values(self, tmp_path):
        """Test viewBox with floating point dimensions."""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg viewBox="0 0 123.456 78.9" xmlns="http://www.w3.org/2000/svg"/>''')

        result = self.provider.get_size_mm(str(svg_file))
        assert result is not None
        w_mm, h_mm = result

        assert abs(w_mm - 32.664) < 0.01  # 123.456 * 25.4/96
        assert abs(h_mm - 20.880) < 0.01  # 78.9 * 25.4/96

    def test_width_height_px_units(self, tmp_path):
        """Test width/height attributes with px units."""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg width="400px" height="300px" xmlns="http://www.w3.org/2000/svg"/>''')

        result = self.provider.get_size_mm(str(svg_file))
        assert result is not None
        w_mm, h_mm = result

        assert abs(w_mm - 105.833) < 0.01  # 400 * 25.4/96
        assert abs(h_mm - 79.375) < 0.01  # 300 * 25.4/96

    def test_width_height_pt_units(self, tmp_path):
        """Test width/height with PostScript points."""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg width="144pt" height="72pt" xmlns="http://www.w3.org/2000/svg"/>''')

        result = self.provider.get_size_mm(str(svg_file))
        assert result is not None
        w_mm, h_mm = result

        # 1pt = 25.4/72 mm
        assert abs(w_mm - 50.8) < 0.01  # 144 * 25.4/72
        assert abs(h_mm - 25.4) < 0.01  # 72 * 25.4/72

    def test_width_height_cm_units(self, tmp_path):
        """Test width/height with centimeters."""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg width="10cm" height="5cm" xmlns="http://www.w3.org/2000/svg"/>''')

        result = self.provider.get_size_mm(str(svg_file))
        assert result is not None
        w_mm, h_mm = result

        assert abs(w_mm - 100.0) < 0.01  # 10cm = 100mm
        assert abs(h_mm - 50.0) < 0.01  # 5cm = 50mm

    def test_width_height_mm_units(self, tmp_path):
        """Test width/height with millimeters."""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg width="210mm" height="297mm" xmlns="http://www.w3.org/2000/svg"/>''')

        result = self.provider.get_size_mm(str(svg_file))
        assert result is not None
        w_mm, h_mm = result

        assert abs(w_mm - 210.0) < 0.01  # A4 width
        assert abs(h_mm - 297.0) < 0.01  # A4 height

    def test_width_height_inch_units(self, tmp_path):
        """Test width/height with inches."""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg width="8.5in" height="11in" xmlns="http://www.w3.org/2000/svg"/>''')

        result = self.provider.get_size_mm(str(svg_file))
        assert result is not None
        w_mm, h_mm = result

        assert abs(w_mm - 215.9) < 0.1  # Letter width
        assert abs(h_mm - 279.4) < 0.1  # Letter height

    def test_width_height_no_units(self, tmp_path):
        """Test width/height without units (treated as px)."""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg width="96" height="48" xmlns="http://www.w3.org/2000/svg"/>''')

        result = self.provider.get_size_mm(str(svg_file))
        assert result is not None
        w_mm, h_mm = result

        # No unit = user units = px at 96 DPI
        assert abs(w_mm - 25.4) < 0.01  # 96px = 1 inch = 25.4mm
        assert abs(h_mm - 12.7) < 0.01  # 48px = 0.5 inch = 12.7mm

    def test_viewbox_preferred_over_width_height(self, tmp_path):
        """Test that viewBox is used when both viewBox and width/height present."""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg viewBox="0 0 100 50" width="200" height="100" xmlns="http://www.w3.org/2000/svg"/>''')

        result = self.provider.get_size_mm(str(svg_file))
        assert result is not None
        w_mm, h_mm = result

        # Should use viewBox (100x50), not width/height (200x100)
        assert abs(w_mm - 26.458) < 0.01  # 100 * 25.4/96
        assert abs(h_mm - 13.229) < 0.01  # 50 * 25.4/96

    def test_malformed_xml(self, tmp_path):
        """Test handling of malformed XML."""
        svg_file = tmp_path / "bad.svg"
        svg_file.write_text("<svg viewBox='0 0 100 50'<rect/>")  # Missing closing bracket

        result = self.provider.get_size_mm(str(svg_file))
        assert result is None

    def test_nonexistent_file(self):
        """Test handling of nonexistent file."""
        result = self.provider.get_size_mm("/nonexistent/file.svg")
        assert result is None

    def test_svg_without_dimensions(self, tmp_path):
        """Test SVG with neither viewBox nor width/height."""
        svg_file = tmp_path / "nodim.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg">
    <circle cx="50" cy="50" r="40"/>
</svg>''')

        result = self.provider.get_size_mm(str(svg_file))
        # Should return None and emit warning
        assert result is None

    def test_invalid_viewbox_format(self, tmp_path):
        """Test viewBox with invalid format (wrong number of values)."""
        svg_file = tmp_path / "badviewbox.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg viewBox="0 0 100" xmlns="http://www.w3.org/2000/svg"/>''')

        # Should fall back to width/height (which don't exist), return None
        result = self.provider.get_size_mm(str(svg_file))
        assert result is None

    def test_percentage_units_not_supported(self, tmp_path):
        """Test that percentage units are rejected."""
        svg_file = tmp_path / "percent.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg width="100%" height="50%" xmlns="http://www.w3.org/2000/svg"/>''')

        result = self.provider.get_size_mm(str(svg_file))
        # Percentages not supported, should return None
        assert result is None

    def test_zero_dimensions(self, tmp_path):
        """Test rejection of zero-width or zero-height SVGs."""
        svg_file = tmp_path / "zero.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg viewBox="0 0 0 100" xmlns="http://www.w3.org/2000/svg"/>''')

        result = self.provider.get_size_mm(str(svg_file))
        # Zero dimensions invalid
        assert result is None

    def test_negative_dimensions(self, tmp_path):
        """Test rejection of negative dimensions."""
        svg_file = tmp_path / "negative.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg viewBox="0 0 -100 50" xmlns="http://www.w3.org/2000/svg"/>''')

        result = self.provider.get_size_mm(str(svg_file))
        # Negative dimensions invalid
        assert result is None

    def test_svg_without_namespace(self, tmp_path):
        """Test SVG without XML namespace declaration."""
        svg_file = tmp_path / "nonamespace.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg viewBox="0 0 200 100">
    <rect width="200" height="100"/>
</svg>''')

        result = self.provider.get_size_mm(str(svg_file))
        # Should still work (namespace optional for parsing)
        assert result is not None
        w_mm, h_mm = result
        assert abs(w_mm - 52.917) < 0.01

    def test_complex_svg_with_multiple_elements(self, tmp_path):
        """Test parsing doesn't break on complex SVG structure."""
        svg_file = tmp_path / "complex.svg"
        svg_file.write_text('''<?xml version="1.0"?>
<svg viewBox="0 0 500 250" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="grad1">
            <stop offset="0%" stop-color="rgb(255,255,0)"/>
        </linearGradient>
    </defs>
    <g transform="translate(50,50)">
        <rect x="0" y="0" width="100" height="100" fill="url(#grad1)"/>
        <text x="50" y="50">Hello</text>
    </g>
</svg>''')

        result = self.provider.get_size_mm(str(svg_file))
        assert result is not None
        w_mm, h_mm = result
        # Should parse viewBox correctly despite complexity
        assert abs(w_mm - 132.292) < 0.01  # 500 * 25.4/96
        assert abs(h_mm - 66.146) < 0.01  # 250 * 25.4/96
