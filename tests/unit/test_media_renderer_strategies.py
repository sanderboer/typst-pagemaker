"""Unit tests for media rendering strategies.

Tests verify that the strategy pattern correctly renders media elements
with proper sizing, alignment, and clipping. Focus on validating that
the SVG sizing bug is fixed.
"""

from unittest.mock import Mock, patch

import pytest

from pagemaker.generation.media_renderer import (
    FigureRenderStrategy,
    PdfRenderStrategy,
    RenderContext,
    SvgRenderStrategy,
    get_media_renderer,
)


def make_context(frame_w_mm=100.0, frame_h_mm=100.0, align=None, valign=None, element_extra=None):
    """Helper to create RenderContext for tests."""
    element = {'id': 'test', 'type': 'test'}
    if element_extra:
        element.update(element_extra)

    return RenderContext(
        element=element,
        page={'page_size': {'w_mm': 210, 'h_mm': 297}, 'grid': {'cols': 4, 'rows': 4}},
        area={'x': 1, 'y': 1, 'w': 2, 'h': 2},
        padding_mm=None,
        frame_w_mm=frame_w_mm,
        frame_h_mm=frame_h_mm,
        align=align,
        valign=valign,
    )


class TestFactory:
    """Test the factory function."""

    def test_get_figure_renderer(self):
        """Test factory returns FigureRenderStrategy for figures."""
        renderer = get_media_renderer('figure')
        assert isinstance(renderer, FigureRenderStrategy)
        assert renderer.size_provider is not None

    def test_get_svg_renderer(self):
        """Test factory returns SvgRenderStrategy for SVGs."""
        renderer = get_media_renderer('svg')
        assert isinstance(renderer, SvgRenderStrategy)
        assert renderer.size_provider is not None

    def test_get_pdf_renderer(self):
        """Test factory returns PdfRenderStrategy for PDFs."""
        renderer = get_media_renderer('pdf')
        assert isinstance(renderer, PdfRenderStrategy)
        assert renderer.size_provider is not None

    def test_unknown_type_raises(self):
        """Test factory raises for unknown types."""
        with pytest.raises(ValueError, match="Unknown media type"):
            get_media_renderer('video')


class TestFigureStrategy:
    """Test figure (raster image) rendering strategy."""

    def setup_method(self):
        """Initialize strategy for each test."""
        self.strategy = FigureRenderStrategy()

    def test_can_use_simple_path_for_all_fits(self):
        """Test figures can use simple path for all fit modes."""
        ctx = make_context()
        assert self.strategy.can_use_simple_path(ctx, 'contain')
        assert self.strategy.can_use_simple_path(ctx, 'cover')
        assert self.strategy.can_use_simple_path(ctx, 'stretch')

    def test_render_simple_contain_no_caption(self):
        """Test simple rendering without caption."""
        ctx = make_context(element_extra={'figure': {'src': 'photo.jpg'}})
        result = self.strategy.render_simple(ctx, 'photo.jpg', 'contain')

        assert 'image("photo.jpg")' in result.typst_code
        assert 'Fig(' in result.typst_code
        assert result.needs_wrapper is False

    def test_render_simple_with_caption(self):
        """Test rendering with caption."""
        ctx = make_context(element_extra={'figure': {'src': 'photo.jpg', 'caption': 'Test Photo'}})
        result = self.strategy.render_simple(ctx, 'photo.jpg', 'contain')

        assert 'caption: [Test Photo]' in result.typst_code
        assert 'Fig(' in result.typst_code

    def test_render_cover_mode(self):
        """Test cover mode uses explicit fit parameter."""
        ctx = make_context(element_extra={'figure': {'src': 'photo.jpg'}})
        result = self.strategy.render_simple(ctx, 'photo.jpg', 'cover')

        assert 'fit: "cover"' in result.typst_code
        assert 'width: 100%, height: 100%' in result.typst_code


class TestSvgStrategy:
    """Test SVG rendering strategy - critical for bug fix validation."""

    def setup_method(self):
        """Initialize strategy with mock size provider."""
        self.mock_provider = Mock()
        self.strategy = SvgRenderStrategy(self.mock_provider)

    def test_can_use_simple_path_contain_no_align(self):
        """Test simple path for contain without alignment."""
        ctx = make_context()
        assert self.strategy.can_use_simple_path(ctx, 'contain')

    def test_cannot_use_simple_path_with_alignment(self):
        """Test manual path required when alignment specified."""
        ctx = make_context(align='center')
        # Simple path still allowed, but render() will choose manual due to alignment
        assert self.strategy.can_use_simple_path(ctx, 'contain')

    def test_cannot_use_simple_path_cover_mode(self):
        """Test manual path required for cover mode."""
        ctx = make_context()
        assert not self.strategy.can_use_simple_path(ctx, 'cover')

    def test_render_simple_contain(self):
        """Test simple rendering for contain mode."""
        ctx = make_context(element_extra={'svg': {'src': 'icon.svg'}})
        result = self.strategy.render_simple(ctx, 'icon.svg', 'contain')

        assert 'image("icon.svg", width: 100%, height: 100%, fit: "contain")' in result.typst_code
        assert 'Fig(' in result.typst_code

    @patch('pagemaker.generator._compute_media_drawn_and_offsets')
    def test_render_manual_uses_intrinsic_size(self, mock_compute):
        """CRITICAL: Test SVG manual rendering uses actual intrinsic size, not frame.

        This test validates the SVG sizing bug fix. Previously, SVGs with alignment
        would incorrectly assume intrinsic size = frame size.
        """
        # Mock the compute function to return specific values
        mock_compute.return_value = (75.0, 37.5, 0.0, 0.0, False)  # drawn_w, drawn_h, dx, dy, clip

        ctx = make_context(
            frame_w_mm=100.0,
            frame_h_mm=100.0,  # Square frame
            align='center',
            element_extra={'svg': {'src': 'logo.svg', 'scale': 1.0}},
        )

        # Intrinsic size is 2:1 aspect (wider than square frame)
        result = self.strategy.render_manual(ctx, 'logo.svg', 'contain', 150.0, 75.0)

        # Verify _compute_media_drawn_and_offsets was called with CORRECT intrinsic dimensions
        mock_compute.assert_called_once_with(
            150.0,  # intrinsic_w_mm - NOT frame size!
            75.0,  # intrinsic_h_mm - NOT frame size!
            100.0,  # frame_w_mm
            100.0,  # frame_h_mm
            'contain',
        )

        # Verify output contains explicit mm dimensions
        assert 'width: 75.000000mm' in result.typst_code
        assert 'height: 37.500000mm' in result.typst_code

    @patch('pagemaker.generator._compute_media_drawn_and_offsets')
    def test_render_manual_cover_with_clip(self, mock_compute):
        """Test cover mode generates clip block."""
        # Mock overflow scenario
        mock_compute.return_value = (150.0, 150.0, -25.0, 0.0, True)  # needs_clip=True

        ctx = make_context(
            frame_w_mm=100.0,
            frame_h_mm=100.0,
            element_extra={'svg': {'src': 'bg.svg', 'scale': 1.0}},
        )

        result = self.strategy.render_manual(ctx, 'bg.svg', 'cover', 100.0, 100.0)

        # Verify clip block present
        assert 'clip: true' in result.typst_code
        assert 'block(width: 100.000000mm, height: 100.000000mm, clip: true)' in result.typst_code

        # Verify place() offset for centering overflow
        assert 'place(dx: -25.000000mm' in result.typst_code

    @patch('pagemaker.generator._compute_media_drawn_and_offsets')
    def test_render_manual_applies_user_scale(self, mock_compute):
        """Test user scale multiplier applied to drawn dimensions."""
        mock_compute.return_value = (100.0, 50.0, 0.0, 0.0, False)

        ctx = make_context(element_extra={'svg': {'src': 'icon.svg', 'scale': 2.0}})

        result = self.strategy.render_manual(ctx, 'icon.svg', 'contain', 100.0, 50.0)

        # Dimensions should be doubled (100*2=200, 50*2=100)
        assert 'width: 200.000000mm' in result.typst_code
        assert 'height: 100.000000mm' in result.typst_code


class TestPdfStrategy:
    """Test PDF rendering strategy."""

    def setup_method(self):
        """Initialize strategy with mock size provider."""
        self.mock_provider = Mock()
        self.strategy = PdfRenderStrategy(self.mock_provider)

    def test_can_use_simple_path(self):
        """Test PDFs can use simple path (PdfEmbed)."""
        ctx = make_context()
        assert self.strategy.can_use_simple_path(ctx, 'contain')
        assert self.strategy.can_use_simple_path(ctx, 'cover')

    def test_render_simple_pdfembed(self):
        """Test simple rendering uses PdfEmbed macro."""
        # Mock size provider to return PDF dimensions
        self.mock_provider.get_size_mm.return_value = (215.9, 279.4)  # Letter size

        ctx = make_context(
            frame_w_mm=100.0,
            frame_h_mm=150.0,
            element_extra={'pdf': {'src': 'doc.pdf', 'pages': [1]}},
        )

        result = self.strategy.render_simple(ctx, 'doc.pdf', 'contain')

        # Should use PdfEmbed with computed scale
        assert 'PdfEmbed("doc.pdf", page: 1, scale:' in result.typst_code

        # Scale should be min(100/215.9, 150/279.4) = min(0.463, 0.537) = 0.463
        assert '0.4' in result.typst_code  # Approximate check

    @patch('pagemaker.generator._compute_media_drawn_and_offsets')
    @patch('pagemaker.generator._get_alignment_wrapper')
    def test_render_manual_with_alignment(self, mock_align, mock_compute):
        """Test manual rendering with alignment."""
        mock_compute.return_value = (80.0, 100.0, 0.0, 0.0, False)
        mock_align.return_value = ('center', 'horizon')

        ctx = make_context(
            frame_w_mm=100.0,
            frame_h_mm=120.0,
            align='center',
            valign='middle',
            element_extra={'pdf': {'src': 'doc.pdf', 'pages': [2], 'scale': 1.0}},
        )

        result = self.strategy.render_manual(ctx, 'doc.pdf', 'contain', 215.9, 279.4)

        # Should use image() with explicit dimensions and contain fit
        assert (
            'image("doc.pdf", page: 2, width: 80.000000mm, height: 100.000000mm, fit: "contain")'
            in result.typst_code
        )

        # Alignment is handled by core.py, not by render_manual
        # render_manual should only handle sizing, NOT alignment wrapping
        assert 'align(' not in result.typst_code


class TestStrategyRendering:
    """Integration-style tests for full rendering flow."""

    def test_svg_strategy_uses_provider(self):
        """Test SVG strategy actually calls size provider."""
        mock_provider = Mock()
        mock_provider.get_size_mm.return_value = (200.0, 100.0)  # 2:1 aspect

        strategy = SvgRenderStrategy(mock_provider)
        ctx = make_context(
            frame_w_mm=100.0,
            frame_h_mm=100.0,
            align='center',  # Trigger manual path
            element_extra={'svg': {'src': 'test.svg', 'scale': 1.0}},
        )

        with patch('pagemaker.generator._compute_media_drawn_and_offsets') as mock_compute:
            mock_compute.return_value = (100.0, 50.0, 0.0, 0.0, False)
            result = strategy.render(ctx, 'test.svg', 'contain')

        # Verify provider was called
        mock_provider.get_size_mm.assert_called_once_with('test.svg')

        # Verify compute was called with provider's dimensions, NOT frame dimensions
        mock_compute.assert_called_once_with(
            200.0,  # From provider
            100.0,  # From provider
            100.0,  # frame_w
            100.0,  # frame_h
            'contain',
        )

    def test_strategy_fallback_when_provider_fails(self):
        """Test fallback to frame size when provider returns None."""
        mock_provider = Mock()
        mock_provider.get_size_mm.return_value = None  # Provider fails

        strategy = SvgRenderStrategy(mock_provider)
        ctx = make_context(
            frame_w_mm=100.0,
            frame_h_mm=80.0,
            align='center',
            element_extra={'svg': {'src': 'bad.svg', 'scale': 1.0}},
        )

        with patch('pagemaker.generator._compute_media_drawn_and_offsets') as mock_compute:
            mock_compute.return_value = (100.0, 80.0, 0.0, 0.0, False)

            with pytest.warns(UserWarning, match="Could not determine intrinsic size"):
                result = strategy.render(ctx, 'bad.svg', 'contain')

        # Should fall back to frame dimensions
        mock_compute.assert_called_once_with(
            100.0,  # Fallback to frame_w
            80.0,  # Fallback to frame_h
            100.0,
            80.0,
            'contain',
        )
