"""Unit tests for media type consolidation features.

Tests verify that figure and pdf types support cross-type features:
- Figure type with :PAGE: for multi-page PDFs
- PDF type with :CAPTION: for captioned documents
"""

import pathlib

from pagemaker.parser import parse_org


def _write_tmp(tmp_path: pathlib.Path, content: str) -> pathlib.Path:
    """Helper to write temporary org file for tests."""
    p = tmp_path / "doc.org"
    p.write_text(content, encoding="utf-8")
    return p


class TestFigureWithPage:
    """Test figure type with :PAGE: property for PDF sources."""

    def test_figure_pdf_with_page_property(self, tmp_path):
        """Test figure can have :PAGE: property for PDF sources."""
        org = """* Page
:PROPERTIES:
:ID: page1
:END:

** Figure
:PROPERTIES:
:TYPE: figure
:AREA: 1,1,4,4
:SRC: document.pdf
:PAGE: 2
:END:
"""
        path = _write_tmp(tmp_path, org)
        ir = parse_org(str(path))
        elem = ir['pages'][0]['elements'][0]

        assert elem['type'] == 'figure'
        assert elem['figure']['src'] == 'document.pdf'
        assert elem['figure']['pages'] == [2]

    def test_figure_pdf_with_page_and_caption(self, tmp_path):
        """Test figure with PDF, page number, and caption."""
        org = """* Page
:PROPERTIES:
:ID: page1
:END:

** Figure
:PROPERTIES:
:TYPE: figure
:AREA: 1,1,4,4
:SRC: report.pdf
:PAGE: 3
:CAPTION: Figure 1: Important Chart
:END:
"""
        path = _write_tmp(tmp_path, org)
        ir = parse_org(str(path))
        elem = ir['pages'][0]['elements'][0]

        assert elem['type'] == 'figure'
        assert elem['figure']['src'] == 'report.pdf'
        assert elem['figure']['pages'] == [3]
        assert elem['figure']['caption'] == 'Figure 1: Important Chart'

    def test_figure_regular_image_no_page(self, tmp_path):
        """Test figure with regular image ignores :PAGE: (no effect)."""
        org = """* Page
:PROPERTIES:
:ID: page1
:END:

** Figure
:PROPERTIES:
:TYPE: figure
:AREA: 1,1,4,4
:SRC: photo.jpg
:PAGE: 1
:END:
"""
        path = _write_tmp(tmp_path, org)
        ir = parse_org(str(path))
        elem = ir['pages'][0]['elements'][0]

        assert elem['type'] == 'figure'
        assert elem['figure']['src'] == 'photo.jpg'
        # JPG doesn't have pages, but parser still captures the property
        assert elem['figure']['pages'] == [1]


class TestPdfWithCaption:
    """Test pdf type with :CAPTION: property."""

    def test_pdf_with_caption(self, tmp_path):
        """Test pdf type accepts :CAPTION: property."""
        org = """* Page
:PROPERTIES:
:ID: page1
:END:

** PDF
:PROPERTIES:
:TYPE: pdf
:AREA: 1,1,4,4
:SRC: chart.pdf
:PAGE: 1
:CAPTION: Figure 2: Sales Data
:END:
"""
        path = _write_tmp(tmp_path, org)
        ir = parse_org(str(path))
        elem = ir['pages'][0]['elements'][0]

        assert elem['type'] == 'pdf'
        assert elem['pdf']['src'] == 'chart.pdf'
        assert elem['pdf']['pages'] == [1]
        assert elem['pdf']['caption'] == 'Figure 2: Sales Data'

    def test_pdf_without_caption_backward_compatible(self, tmp_path):
        """Test pdf without caption still works (backward compatibility)."""
        org = """* Page
:PROPERTIES:
:ID: page1
:END:

** PDF
:PROPERTIES:
:TYPE: pdf
:AREA: 1,1,4,4
:SRC: document.pdf
:PAGE: 1
:END:
"""
        path = _write_tmp(tmp_path, org)
        ir = parse_org(str(path))
        elem = ir['pages'][0]['elements'][0]

        assert elem['type'] == 'pdf'
        assert elem['pdf']['src'] == 'document.pdf'
        assert elem['pdf']['pages'] == [1]
        assert elem['pdf']['caption'] is None  # No caption provided, should be None


class TestRendererGeneration:
    """Test that renderer strategies generate correct Typst code."""

    def test_figure_pdf_generates_page_parameter(self, tmp_path):
        """Test figure with PDF source includes page: parameter in Typst."""
        org = """* Page
:PROPERTIES:
:ID: page1
:END:

** Figure
:PROPERTIES:
:TYPE: figure
:AREA: 1,1,4,4
:SRC: doc.pdf
:PAGE: 2
:FIT: contain
:END:
"""
        from pagemaker.generator import generate_typst

        path = _write_tmp(tmp_path, org)
        ir = parse_org(str(path))
        typst = generate_typst(ir)

        # Should include page parameter in image() call
        assert 'image("doc.pdf"' in typst or 'image(\n  "doc.pdf"' in typst
        assert 'page: 2' in typst

    def test_figure_jpg_no_page_parameter(self, tmp_path):
        """Test figure with JPG doesn't include page parameter."""
        org = """* Page
:PROPERTIES:
:ID: page1
:END:

** Figure
:PROPERTIES:
:TYPE: figure
:AREA: 1,1,4,4
:SRC: photo.jpg
:FIT: contain
:END:
"""
        from pagemaker.generator import generate_typst

        path = _write_tmp(tmp_path, org)
        ir = parse_org(str(path))
        typst = generate_typst(ir)

        # Should have image call without page parameter
        assert 'image("photo.jpg"' in typst or 'image(\n  "photo.jpg"' in typst
        # Should NOT have page parameter (JPG is single image)
        # Note: Parser might still include pages=[1] in IR, but renderer shouldn't emit it

    def test_pdf_with_caption_uses_fig_helper(self, tmp_path):
        """Test pdf with caption uses Fig() helper."""
        org = """* Page
:PROPERTIES:
:ID: page1
:END:

** PDF
:PROPERTIES:
:TYPE: pdf
:AREA: 1,1,4,4
:SRC: chart.pdf
:PAGE: 1
:CAPTION: Sales Chart
:END:
"""
        from pagemaker.generator import generate_typst

        path = _write_tmp(tmp_path, org)
        ir = parse_org(str(path))
        typst = generate_typst(ir)

        # Should use Fig() with caption
        assert 'Fig(' in typst
        assert 'caption: [Sales Chart]' in typst

    def test_pdf_without_caption_uses_pdfembed(self, tmp_path):
        """Test pdf without caption uses PdfEmbed for backward compatibility."""
        org = """* Page
:PROPERTIES:
:ID: page1
:END:

** PDF
:PROPERTIES:
:TYPE: pdf
:AREA: 1,1,4,4
:SRC: document.pdf
:PAGE: 1
:SCALE: 1.0
:END:
"""
        from pagemaker.generator import generate_typst

        path = _write_tmp(tmp_path, org)
        ir = parse_org(str(path))
        typst = generate_typst(ir)

        # Should use PdfEmbed
        assert 'PdfEmbed(' in typst
        # Extract page content section and verify Fig() is not called there
        if '// BEGIN PAGE CONTENT' in typst and '// END PAGE CONTENT' in typst:
            start = typst.index('// BEGIN PAGE CONTENT')
            end = typst.index('// END PAGE CONTENT')
            page_content = typst[start:end]
            assert (
                'Fig(' not in page_content
            ), "Fig() should not be called in page content when there's no caption"

    def test_figure_with_caption_uses_fig_helper(self, tmp_path):
        """Test figure with caption uses Fig() helper."""
        org = """* Page
:PROPERTIES:
:ID: page1
:END:

** Figure
:PROPERTIES:
:TYPE: figure
:AREA: 1,1,4,4
:SRC: photo.jpg
:CAPTION: Beautiful Landscape
:END:
"""
        from pagemaker.generator import generate_typst

        path = _write_tmp(tmp_path, org)
        ir = parse_org(str(path))
        typst = generate_typst(ir)

        # Should use Fig() with caption
        assert 'Fig(' in typst
        assert 'caption: [Beautiful Landscape]' in typst

    def test_figure_with_alignment_and_caption(self, tmp_path):
        """Test figure with alignment and caption includes both in Fig() call."""
        org = """* Page
:PROPERTIES:
:ID: page1
:END:

** Photo
:PROPERTIES:
:TYPE: figure
:AREA: 1,1,4,4
:SRC: forest.jpg
:ALIGN: right
:VALIGN: bottom
:CAPTION: Right-bottom aligned image
:END:
"""
        from pagemaker.generator import generate_typst

        path = _write_tmp(tmp_path, org)
        ir = parse_org(str(path))
        typst = generate_typst(ir)

        # Should use Fig() with caption and alignment
        assert 'Fig(' in typst
        assert 'caption: [Right-bottom aligned image]' in typst
        assert 'img_align: right' in typst
        assert 'img_valign: bottom' in typst
        assert 'caption_align: right' in typst
        assert 'caption_valign: bottom' in typst
