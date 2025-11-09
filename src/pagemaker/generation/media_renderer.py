"""Media rendering strategies for unified media handling.

This module implements the strategy pattern for rendering different media types
(figures, SVGs, PDFs) with consistent behavior. Each media type has a dedicated
strategy class that handles type-specific rendering logic while sharing common
infrastructure for sizing, alignment, and clipping.

Architecture:
    Layer 1: Intrinsic Size Providers (media_sizing.py) - detect media dimensions
    Layer 2: Rendering Strategies (this module) - generate Typst code
    Layer 3: Factory & Orchestration (generation/core.py) - dispatch to strategies

Example:
    >>> from pagemaker.generation.media_renderer import get_media_renderer
    >>> from pagemaker.generation.media_renderer import RenderContext
    >>>
    >>> ctx = RenderContext(
    ...     element=element_dict,
    ...     page=page_dict,
    ...     area={'x': 1, 'y': 1, 'w': 2, 'h': 2},
    ...     padding_mm=None,
    ...     frame_w_mm=100.0,
    ...     frame_h_mm=100.0,
    ...     align='center',
    ...     valign='middle'
    ... )
    >>>
    >>> renderer = get_media_renderer('svg')
    >>> result = renderer.render(ctx, 'diagram.svg', 'contain')
    >>> print(result.typst_code)
"""

import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from .media_sizing import IntrinsicSizeProvider


@dataclass
class RenderContext:
    """Context data passed to media rendering strategies.

    Contains all information needed to render a media element, including
    element properties, page dimensions, positioning, and alignment.

    Attributes:
        element: Full element dictionary from IR
        page: Page dictionary containing size and grid info
        area: Area dictionary with x, y, w, h in grid coordinates
        padding_mm: Optional padding dict with top/right/bottom/left in mm
        frame_w_mm: Available width after padding (in mm)
        frame_h_mm: Available height after padding (in mm)
        align: Horizontal alignment ('left', 'center', 'right', None)
        valign: Vertical alignment ('top', 'middle'/'horizon', 'bottom', None)
    """

    element: dict
    page: dict
    area: dict
    padding_mm: Optional[dict]
    frame_w_mm: float
    frame_h_mm: float
    align: Optional[str]
    valign: Optional[str]


@dataclass
class RenderedMedia:
    """Result of media rendering operation.

    Attributes:
        typst_code: Generated Typst code string
        needs_wrapper: If True, code should be wrapped in brackets [...]
                      If False, code is a function call or self-contained expression
    """

    typst_code: str
    needs_wrapper: bool = False


class MediaRenderStrategy(ABC):
    """Abstract base class for media rendering strategies.

    Each media type (figure, svg, pdf) implements this interface to provide
    type-specific rendering logic while sharing common decision-making code.

    The base class handles:
    - Intrinsic size detection via size providers
    - Decision logic for simple vs manual rendering paths
    - Fallback behavior when intrinsic size unavailable

    Subclasses implement:
    - can_use_simple_path: when to delegate to Typst built-ins
    - render_simple: generate code using Typst image() with fit parameter
    - render_manual: generate code with explicit sizing and clipping
    """

    def __init__(self, size_provider: Optional[IntrinsicSizeProvider] = None):
        """Initialize strategy with optional size provider.

        Args:
            size_provider: Provider for detecting intrinsic media dimensions.
                          If None, render_manual will use fallback sizing.
        """
        self.size_provider = size_provider

    @abstractmethod
    def can_use_simple_path(self, ctx: RenderContext, fit: str) -> bool:
        """Determine if simple path (Typst built-in) can be used.

        Simple path delegates to Typst's image() function with fit parameter.
        Manual path uses explicit sizing, alignment, and clipping.

        Args:
            ctx: Render context
            fit: Fit mode ('contain', 'cover', 'stretch')

        Returns:
            True if simple path sufficient, False if manual path needed

        Note:
            Generally:
            - Simple path for: no alignment, Typst handles fit mode well
            - Manual path for: alignment specified, cover mode, explicit sizing
        """
        pass

    @abstractmethod
    def render_simple(self, ctx: RenderContext, src: str, fit: str) -> RenderedMedia:
        """Render using Typst built-in image() with fit parameter.

        Args:
            ctx: Render context
            src: Media source path
            fit: Fit mode ('contain', 'cover', 'stretch')

        Returns:
            RenderedMedia with generated Typst code

        Note:
            Simple rendering should produce minimal code by delegating to
            Typst's built-in functionality wherever possible.
        """
        pass

    @abstractmethod
    def render_manual(
        self, ctx: RenderContext, src: str, fit: str, intrinsic_w_mm: float, intrinsic_h_mm: float
    ) -> RenderedMedia:
        """Render with explicit sizing, alignment, and clipping.

        Args:
            ctx: Render context
            src: Media source path
            fit: Fit mode ('contain', 'cover', 'stretch')
            intrinsic_w_mm: Intrinsic width in millimeters
            intrinsic_h_mm: Intrinsic height in millimeters

        Returns:
            RenderedMedia with generated Typst code

        Note:
            Manual rendering computes exact dimensions, applies alignment via
            place() offsets, and adds clip blocks for cover mode overflow.
        """
        pass

    def render(self, ctx: RenderContext, src: str, fit: str, **media_kwargs) -> RenderedMedia:
        """Main rendering entry point - orchestrates simple vs manual path.

        Decision logic:
        1. Check if alignment specified (triggers manual path)
        2. Try to get intrinsic size from provider
        3. Check if simple path available for this fit mode
        4. Fall back to manual path if needed

        Args:
            ctx: Render context
            src: Media source path
            fit: Fit mode ('contain', 'cover', 'stretch')
            **media_kwargs: Type-specific parameters (e.g., box, page)

        Returns:
            RenderedMedia with generated Typst code

        Raises:
            No exceptions raised - all errors handled gracefully with fallbacks
        """
        has_alignment = bool(ctx.align or ctx.valign)

        # Try to get intrinsic size from provider
        intrinsic = None
        if self.size_provider:
            try:
                intrinsic = self.size_provider.get_size_mm(src, **media_kwargs)
            except Exception as e:
                warnings.warn(f"Error getting intrinsic size for '{src}': {e}", UserWarning)

        # Decision: use simple path if no alignment and simple path supported
        if not has_alignment and self.can_use_simple_path(ctx, fit):
            return self.render_simple(ctx, src, fit)

        # Manual path: need intrinsic size or use fallback
        if intrinsic is None:
            # Fallback: assume square aspect matching frame
            # This is the old behavior that caused SVG sizing bugs
            warnings.warn(
                f"Could not determine intrinsic size for '{src}', "
                f"falling back to frame-based sizing (may produce incorrect aspect ratio)",
                UserWarning,
            )
            intrinsic = (ctx.frame_w_mm, ctx.frame_h_mm)

        intrinsic_w_mm, intrinsic_h_mm = intrinsic

        # Validate dimensions
        if intrinsic_w_mm <= 0 or intrinsic_h_mm <= 0:
            warnings.warn(
                f"Invalid intrinsic dimensions for '{src}': {intrinsic_w_mm}×{intrinsic_h_mm}mm, "
                f"using fallback",
                UserWarning,
            )
            intrinsic_w_mm = ctx.frame_w_mm if ctx.frame_w_mm > 0 else 100.0
            intrinsic_h_mm = ctx.frame_h_mm if ctx.frame_h_mm > 0 else 100.0

        return self.render_manual(ctx, src, fit, intrinsic_w_mm, intrinsic_h_mm)


class FigureRenderStrategy(MediaRenderStrategy):
    """Strategy for rendering raster images (PNG, JPG, etc.).

    Figures (raster images) can almost always use Typst's built-in image()
    function with fit parameter. Typst handles contain/cover/stretch natively
    and correctly for raster images.

    Example:
        >>> strategy = FigureRenderStrategy()
        >>> result = strategy.render(ctx, 'photo.jpg', 'cover')
        >>> print(result.typst_code)
        Fig(image("photo.jpg", width: 100%, height: 100%, fit: "cover"), ...)
    """

    def can_use_simple_path(self, ctx: RenderContext, fit: str) -> bool:
        """Figures can use simple path for contain/stretch, but not cover.

        Cover mode requires manual path with explicit clipping to prevent overflow.
        """
        # Cover mode needs manual path for clipping, like SVGs
        return fit in ('contain', 'stretch')

    def render_simple(self, ctx: RenderContext, src: str, fit: str) -> RenderedMedia:
        """Render figure using Typst image() with fit parameter."""
        # Import here to avoid circular dependency
        from ..generator import escape_text

        align = ctx.align or 'left'
        valign = ctx.valign or 'top'
        has_alignment = bool(ctx.align or ctx.valign)

        # Map fit values (handle legacy 'fill' alias)
        fit_map = {
            'fill': 'cover',
            'contain': 'contain',
            'cover': 'cover',
            'stretch': 'stretch',
        }
        fit_val = fit_map.get(fit.lower(), fit)

        # Check if source is a PDF and page is specified (for multi-page PDF support)
        pages_list = ctx.element.get('figure', {}).get('pages', [1])
        page_num = pages_list[0] if pages_list else 1
        src_lower = src.lower()
        is_pdf = src_lower.endswith('.pdf')

        # Get caption to determine sizing strategy
        caption = ctx.element.get('figure', {}).get('caption')

        # IMPORTANT: When there's a caption AND alignment, don't use 100% dimensions
        # Instead, the image will be contained naturally within the Fig() grid cell,
        # allowing the align() wrapper inside Fig() to actually position it
        if caption and has_alignment:
            # For alignment to work, image must not fill 100% - it should size to content
            # We still apply contain fit, but without forcing 100% dimensions
            if is_pdf and page_num:
                img_call = f'image("{src}", page: {page_num}, fit: "{fit_val}")'
            else:
                img_call = f'image("{src}", fit: "{fit_val}")'
        else:
            # No caption or no alignment: fill the entire space as before
            if is_pdf and page_num:
                img_call = (
                    f'image("{src}", page: {page_num}, width: 100%, height: 100%, fit: "{fit_val}")'
                )
            else:
                img_call = f'image("{src}", width: 100%, height: 100%, fit: "{fit_val}")'

        if caption:
            cap_e = escape_text(caption)
            # When caption + alignment, pass fill_space: false to allow alignment
            fill_space = "false" if has_alignment else "true"
            code = (
                f"Fig({img_call}, caption: [{cap_e}], caption_align: {align}, img_align: {align}, "
                f"caption_valign: {valign}, img_valign: {valign}, fill_space: {fill_space})"
            )
        else:
            code = (
                f"Fig({img_call}, caption_align: {align}, img_align: {align}, "
                f"caption_valign: {valign}, img_valign: {valign})"
            )

        return RenderedMedia(code, needs_wrapper=False)

    def render_manual(
        self, ctx: RenderContext, src: str, fit: str, intrinsic_w_mm: float, intrinsic_h_mm: float
    ) -> RenderedMedia:
        """Render figure with explicit sizing and clipping for cover mode.

        For contain mode with alignment, delegate to render_simple since Fig()
        can handle alignment internally. Only cover mode truly needs explicit clipping.
        """
        # For contain mode, delegate to render_simple which uses Fig() with alignment
        # Fig() helper handles alignment internally without needing manual sizing
        if fit == 'contain':
            return self.render_simple(ctx, src, fit)

        # Cover mode requires explicit clipping
        # Import here to avoid circular dependency
        from ..generator import _compute_media_drawn_and_offsets

        # Compute drawn size based on fit mode
        drawn_w_mm, drawn_h_mm, offset_x_mm, offset_y_mm, needs_clip = (
            _compute_media_drawn_and_offsets(
                intrinsic_w_mm,
                intrinsic_h_mm,
                ctx.frame_w_mm,
                ctx.frame_h_mm,
                fit,
                align=ctx.align,
                valign=ctx.valign,
            )
        )

        # Check if source is a PDF with page number
        pages_list = ctx.element.get('figure', {}).get('pages', [1])
        page_num = pages_list[0] if pages_list else 1
        src_lower = src.lower()
        is_pdf = src_lower.endswith('.pdf')

        # Build image call with explicit dimensions
        if is_pdf and page_num:
            img_inner = f'image("{src}", page: {page_num}, width: {drawn_w_mm:.6f}mm, height: {drawn_h_mm:.6f}mm)'
        else:
            img_inner = f'image("{src}", width: {drawn_w_mm:.6f}mm, height: {drawn_h_mm:.6f}mm)'

        # Add place() offsets for centering overflow
        place_args = []
        if offset_x_mm != 0.0:
            place_args.append(f"dx: {offset_x_mm:.6f}mm")
        if offset_y_mm != 0.0:
            place_args.append(f"dy: {offset_y_mm:.6f}mm")
        if place_args:
            img_inner = f"place({', '.join(place_args)}, {img_inner})"

        # Check for caption - need to adjust frame height to leave room for caption
        caption = ctx.element.get('figure', {}).get('caption')
        if caption and fit == 'cover':
            # Estimate caption height: typically 0.75em text + 0.3em gutter ≈ 2.5mm
            # This is a rough estimate; actual height depends on font size and content
            caption_height_mm = 5.0  # Conservative estimate

            # Recalculate with reduced frame height
            adjusted_frame_h_mm = max(ctx.frame_h_mm - caption_height_mm, 1.0)

            # Recompute layout with adjusted frame
            drawn_w_mm_adj, drawn_h_mm_adj, offset_x_mm_adj, offset_y_mm_adj, needs_clip_adj = (
                _compute_media_drawn_and_offsets(
                    intrinsic_w_mm,
                    intrinsic_h_mm,
                    ctx.frame_w_mm,
                    adjusted_frame_h_mm,
                    fit,
                    align=ctx.align,
                    valign=ctx.valign,
                )
            )

            # Build image with adjusted dimensions
            if is_pdf and page_num:
                img_inner_adj = f'image("{src}", page: {page_num}, width: {drawn_w_mm_adj:.6f}mm, height: {drawn_h_mm_adj:.6f}mm)'
            else:
                img_inner_adj = (
                    f'image("{src}", width: {drawn_w_mm_adj:.6f}mm, height: {drawn_h_mm_adj:.6f}mm)'
                )

            # Add place() offsets
            place_args_adj = []
            if offset_x_mm_adj != 0.0:
                place_args_adj.append(f"dx: {offset_x_mm_adj:.6f}mm")
            if offset_y_mm_adj != 0.0:
                place_args_adj.append(f"dy: {offset_y_mm_adj:.6f}mm")
            if place_args_adj:
                img_inner_adj = f"place({', '.join(place_args_adj)}, {img_inner_adj})"

            # Add clip block with adjusted frame height
            if needs_clip_adj:
                body_expr_adj = f"block(width: {ctx.frame_w_mm:.6f}mm, height: {adjusted_frame_h_mm:.6f}mm, clip: true)[#{img_inner_adj}]"
            else:
                body_expr_adj = img_inner_adj

            from ..generator import escape_text

            cap_e = escape_text(caption)
            align = ctx.align or 'left'
            valign = ctx.valign or 'top'

            code = (
                f"Fig({body_expr_adj}, caption: [{cap_e}], caption_align: {align}, img_align: {align}, "
                f"caption_valign: {valign}, img_valign: {valign}, fill_space: false)"
            )
            return RenderedMedia(code, needs_wrapper=False)

        # Add clip block if content overflows frame
        if needs_clip:
            body_expr = f"block(width: {ctx.frame_w_mm:.6f}mm, height: {ctx.frame_h_mm:.6f}mm, clip: true)[#{img_inner}]"
        else:
            body_expr = img_inner

        return RenderedMedia(body_expr, needs_wrapper=True)


class SvgRenderStrategy(MediaRenderStrategy):
    """Strategy for rendering SVG assets.

    SVGs require more sophisticated handling than raster images:
    - Simple path: contain/stretch without alignment
    - Manual path: cover mode OR alignment specified

    The manual path fixes the SVG sizing bug where intrinsic size was
    incorrectly assumed to equal frame size.

    Example:
        >>> from pagemaker.generation.media_sizing import SvgSizeProvider
        >>> strategy = SvgRenderStrategy(SvgSizeProvider())
        >>> result = strategy.render(ctx, 'icon.svg', 'cover')
        >>> # Produces correctly-sized SVG with clipping
    """

    def can_use_simple_path(self, ctx: RenderContext, fit: str) -> bool:
        """SVG simple path only for contain/stretch without alignment."""
        return fit in ('contain', 'stretch')

    def render_simple(self, ctx: RenderContext, src: str, fit: str) -> RenderedMedia:
        """Render SVG using Typst image() with fit parameter."""
        img_call = f'image("{src}", width: 100%, height: 100%, fit: "{fit}")'
        return RenderedMedia(f"Fig({img_call})", needs_wrapper=False)

    def render_manual(
        self, ctx: RenderContext, src: str, fit: str, intrinsic_w_mm: float, intrinsic_h_mm: float
    ) -> RenderedMedia:
        """Render SVG with explicit sizing and clipping.

        This is the FIX for the SVG sizing bug - now uses actual intrinsic
        dimensions from SvgSizeProvider instead of assuming frame size.
        """
        # Import here to avoid circular dependency
        from ..generator import _compute_media_drawn_and_offsets

        # Get user scale multiplier from SVG metadata
        user_scale = ctx.element.get('svg', {}).get('scale', 1.0) or 1.0

        # Compute drawn size based on fit mode
        drawn_w_mm, drawn_h_mm, offset_x_mm, offset_y_mm, needs_clip = (
            _compute_media_drawn_and_offsets(
                intrinsic_w_mm,
                intrinsic_h_mm,
                ctx.frame_w_mm,
                ctx.frame_h_mm,
                fit,
                align=ctx.align,
                valign=ctx.valign,
            )
        )

        # Apply user scale multiplicatively
        if isinstance(user_scale, (int, float)) and user_scale not in (0, 1):
            drawn_w_mm *= float(user_scale)
            drawn_h_mm *= float(user_scale)

            # For cover mode, recompute overflow after scaling
            if fit == 'cover':
                overflow_x = drawn_w_mm - ctx.frame_w_mm
                overflow_y = drawn_h_mm - ctx.frame_h_mm
                if overflow_x > 0:
                    offset_x_mm = -overflow_x / 2.0
                    needs_clip = True
                if overflow_y > 0:
                    offset_y_mm = -overflow_y / 2.0
                    needs_clip = True

        # For contain mode: use percentage-based sizing to allow alignment to work
        # For cover/stretch: use explicit mm dimensions (cover needs oversized content for clipping)
        if fit == 'contain':
            img_inner = f'image("{src}", width: 100%, height: 100%, fit: "contain")'
        else:
            img_inner = f'image("{src}", width: {drawn_w_mm:.6f}mm, height: {drawn_h_mm:.6f}mm, fit: "{fit}")'

        # Add place() offsets for centering/alignment
        place_args = []
        if offset_x_mm != 0.0:
            place_args.append(f"dx: {offset_x_mm:.6f}mm")
        if offset_y_mm != 0.0:
            place_args.append(f"dy: {offset_y_mm:.6f}mm")
        if place_args:
            img_inner = f"place({', '.join(place_args)}, {img_inner})"

        # Check for caption - need to adjust frame height to leave room for caption
        caption = ctx.element.get('svg', {}).get('caption')
        if caption and fit == 'cover':
            # Estimate caption height: typically 0.75em text + 0.3em gutter ≈ 2.5mm
            caption_height_mm = 5.0

            # Recalculate with reduced frame height
            adjusted_frame_h_mm = max(ctx.frame_h_mm - caption_height_mm, 1.0)

            # Recompute layout with adjusted frame
            drawn_w_mm_adj, drawn_h_mm_adj, offset_x_mm_adj, offset_y_mm_adj, needs_clip_adj = (
                _compute_media_drawn_and_offsets(
                    intrinsic_w_mm,
                    intrinsic_h_mm,
                    ctx.frame_w_mm,
                    adjusted_frame_h_mm,
                    fit,
                    align=ctx.align,
                    valign=ctx.valign,
                )
            )

            # Apply user scale if present
            if isinstance(user_scale, (int, float)) and user_scale not in (0, 1):
                drawn_w_mm_adj *= float(user_scale)
                drawn_h_mm_adj *= float(user_scale)

                # Recompute overflow after scaling
                overflow_x = drawn_w_mm_adj - ctx.frame_w_mm
                overflow_y = drawn_w_mm_adj - adjusted_frame_h_mm
                if overflow_x > 0:
                    offset_x_mm_adj = -overflow_x / 2.0
                    needs_clip_adj = True
                if overflow_y > 0:
                    offset_y_mm_adj = -overflow_y / 2.0
                    needs_clip_adj = True

            # Build image with adjusted dimensions
            img_inner_adj = f'image("{src}", width: {drawn_w_mm_adj:.6f}mm, height: {drawn_h_mm_adj:.6f}mm, fit: "cover")'

            # Add place() offsets
            place_args_adj = []
            if offset_x_mm_adj != 0.0:
                place_args_adj.append(f"dx: {offset_x_mm_adj:.6f}mm")
            if offset_y_mm_adj != 0.0:
                place_args_adj.append(f"dy: {offset_y_mm_adj:.6f}mm")
            if place_args_adj:
                img_inner_adj = f"place({', '.join(place_args_adj)}, {img_inner_adj})"

            # Add clip block with adjusted frame height
            if needs_clip_adj:
                body_expr_adj = f"block(width: {ctx.frame_w_mm:.6f}mm, height: {adjusted_frame_h_mm:.6f}mm, clip: true)[#{img_inner_adj}]"
            else:
                body_expr_adj = img_inner_adj

            from ..generator import escape_text

            cap_e = escape_text(caption)
            align = ctx.align or 'left'
            valign = ctx.valign or 'top'

            code = (
                f"Fig({body_expr_adj}, caption: [{cap_e}], caption_align: {align}, img_align: {align}, "
                f"caption_valign: {valign}, img_valign: {valign}, fill_space: false)"
            )
            return RenderedMedia(code, needs_wrapper=False)

        # Add clip block if content overflows frame
        if needs_clip:
            body_expr = f"block(width: {ctx.frame_w_mm:.6f}mm, height: {ctx.frame_h_mm:.6f}mm, clip: true)[#{img_inner}]"
        else:
            body_expr = img_inner

        return RenderedMedia(body_expr, needs_wrapper=True)


class PdfRenderStrategy(MediaRenderStrategy):
    """Strategy for rendering PDF page embedding.

    PDFs have three rendering cases:
    - Simple (contain/stretch, no caption): Use PdfEmbed macro with align wrapper if needed
    - Simple (contain/stretch, with caption): Use Fig() helper with alignment
    - Manual (cover mode): Use image() with explicit dimensions and clipping

    The simple path is preferred for performance and cleaner output.

    Example:
        >>> from pagemaker.generation.media_sizing import PdfSizeProvider
        >>> strategy = PdfRenderStrategy(PdfSizeProvider())
        >>> result = strategy.render(ctx, 'doc.pdf', 'contain', page=1)
        >>> print(result.typst_code)
        PdfEmbed("doc.pdf", page: 1, scale: 0.8435)
    """

    def can_use_simple_path(self, ctx: RenderContext, fit: str) -> bool:
        """PDFs can use simple path only for contain/stretch, not cover.

        Cover mode requires manual path with explicit clipping to prevent overflow.
        """
        # Cover mode needs manual path for clipping
        return fit in ('contain', 'stretch')

    def render(self, ctx: RenderContext, src: str, fit: str, **media_kwargs) -> RenderedMedia:
        """Override render to allow simple path for contain/stretch even with alignment.

        PDFs use simple path (PdfEmbed or Fig) for contain/stretch modes regardless
        of alignment, and only use manual path for cover mode.
        """
        # Try to get intrinsic size from provider
        intrinsic = None
        if self.size_provider:
            try:
                intrinsic = self.size_provider.get_size_mm(src, **media_kwargs)
            except Exception as e:
                warnings.warn(f"Error getting intrinsic size for '{src}': {e}", UserWarning)

        # Decision: use simple path for contain/stretch (alignment handled in render_simple)
        if self.can_use_simple_path(ctx, fit):
            return self.render_simple(ctx, src, fit)

        # Manual path (cover mode): need intrinsic size or use fallback
        if intrinsic is None:
            warnings.warn(
                f"Could not determine intrinsic size for '{src}', "
                f"falling back to frame-based sizing (may produce incorrect aspect ratio)",
                UserWarning,
            )
            intrinsic = (ctx.frame_w_mm, ctx.frame_h_mm)

        intrinsic_w_mm, intrinsic_h_mm = intrinsic

        # Validate dimensions
        if intrinsic_w_mm <= 0 or intrinsic_h_mm <= 0:
            warnings.warn(
                f"Invalid intrinsic size for '{src}': {intrinsic_w_mm}x{intrinsic_h_mm}mm",
                UserWarning,
            )
            # Use frame dimensions as fallback
            intrinsic_w_mm = ctx.frame_w_mm if ctx.frame_w_mm > 0 else 100.0
            intrinsic_h_mm = ctx.frame_h_mm if ctx.frame_h_mm > 0 else 100.0

        return self.render_manual(ctx, src, fit, intrinsic_w_mm, intrinsic_h_mm)

    def render_simple(self, ctx: RenderContext, src: str, fit: str) -> RenderedMedia:
        """Render PDF using PdfEmbed macro or Fig() if caption is present."""
        # Import here to avoid circular dependency
        from ..generator import escape_text

        page_num = ctx.element.get('pdf', {}).get('pages', [1])[0]
        caption = ctx.element.get('pdf', {}).get('caption')
        align = ctx.align or 'left'
        valign = ctx.valign or 'top'
        has_alignment = bool(ctx.align or ctx.valign)

        # Get intrinsic size for computing contain scale
        # Size provider should already be set, but handle gracefully
        intrinsic = None
        if self.size_provider:
            box = ctx.element.get('pdf', {}).get('box')
            intrinsic = self.size_provider.get_size_mm(src, box=box)

        if intrinsic and ctx.frame_w_mm > 0 and ctx.frame_h_mm > 0:
            pdf_w_mm, pdf_h_mm = intrinsic
            scale_w = ctx.frame_w_mm / pdf_w_mm
            scale_h = ctx.frame_h_mm / pdf_h_mm
            base_scale = min(scale_w, scale_h)  # contain scale
        else:
            base_scale = 1.0

        # If caption is present, use Fig() helper for consistent caption rendering
        if caption:
            cap_e = escape_text(caption)
            # IMPORTANT: When there's alignment, don't use 100% dimensions
            # This allows align() inside Fig() to actually position the image
            if has_alignment:
                img_call = f'image("{src}", page: {page_num}, fit: "contain")'
            else:
                img_call = (
                    f'image("{src}", page: {page_num}, width: 100%, height: 100%, fit: "contain")'
                )
            # When caption + alignment, pass fill_space: false to allow alignment
            fill_space = "false" if has_alignment else "true"
            code = (
                f'Fig({img_call}, caption: [{cap_e}], caption_align: {align}, img_align: {align}, '
                f'caption_valign: {valign}, img_valign: {valign}, fill_space: {fill_space})'
            )
        else:
            # No caption: use PdfEmbed for backward compatibility
            pdf_embed = f'PdfEmbed("{src}", page: {page_num}, scale: {base_scale:.6f})'

            # If alignment specified, wrap PdfEmbed in align()
            if has_alignment:
                align_terms = []
                if ctx.align:
                    align_terms.append(ctx.align)
                if ctx.valign:
                    align_terms.append(ctx.valign)
                code = f"align({' + '.join(align_terms)})[#{pdf_embed}]"
            else:
                code = pdf_embed

        return RenderedMedia(code, needs_wrapper=False)

    def render_manual(
        self, ctx: RenderContext, src: str, fit: str, intrinsic_w_mm: float, intrinsic_h_mm: float
    ) -> RenderedMedia:
        """Render PDF with explicit sizing and clipping for cover mode.

        Cover mode requires explicit clipping to prevent overflow, similar to
        Figure and SVG handling.
        """
        # Import here to avoid circular dependency
        from ..generator import _compute_media_drawn_and_offsets

        # Get page number from metadata
        page_num = ctx.element.get('pdf', {}).get('pages', [1])[0]

        # Compute drawn size based on fit mode
        drawn_w_mm, drawn_h_mm, offset_x_mm, offset_y_mm, needs_clip = (
            _compute_media_drawn_and_offsets(
                intrinsic_w_mm,
                intrinsic_h_mm,
                ctx.frame_w_mm,
                ctx.frame_h_mm,
                fit,
                align=ctx.align,
                valign=ctx.valign,
            )
        )

        # Build image call with explicit dimensions
        img_inner = f'image("{src}", page: {page_num}, width: {drawn_w_mm:.6f}mm, height: {drawn_h_mm:.6f}mm)'

        # Add place() offsets for centering overflow
        place_args = []
        if offset_x_mm != 0.0:
            place_args.append(f"dx: {offset_x_mm:.6f}mm")
        if offset_y_mm != 0.0:
            place_args.append(f"dy: {offset_y_mm:.6f}mm")
        if place_args:
            img_inner = f"place({', '.join(place_args)}, {img_inner})"

        # Check for caption - need to adjust frame height to leave room for caption
        caption = ctx.element.get('pdf', {}).get('caption')
        if caption and fit == 'cover':
            # Estimate caption height: typically 0.75em text + 0.3em gutter ≈ 2.5mm
            caption_height_mm = 5.0

            # Recalculate with reduced frame height
            adjusted_frame_h_mm = max(ctx.frame_h_mm - caption_height_mm, 1.0)

            # Recompute layout with adjusted frame
            drawn_w_mm_adj, drawn_h_mm_adj, offset_x_mm_adj, offset_y_mm_adj, needs_clip_adj = (
                _compute_media_drawn_and_offsets(
                    intrinsic_w_mm,
                    intrinsic_h_mm,
                    ctx.frame_w_mm,
                    adjusted_frame_h_mm,
                    fit,
                    align=ctx.align,
                    valign=ctx.valign,
                )
            )

            # Build image with adjusted dimensions
            img_inner_adj = f'image("{src}", page: {page_num}, width: {drawn_w_mm_adj:.6f}mm, height: {drawn_h_mm_adj:.6f}mm)'

            # Add place() offsets
            place_args_adj = []
            if offset_x_mm_adj != 0.0:
                place_args_adj.append(f"dx: {offset_x_mm_adj:.6f}mm")
            if offset_y_mm_adj != 0.0:
                place_args_adj.append(f"dy: {offset_y_mm_adj:.6f}mm")
            if place_args_adj:
                img_inner_adj = f"place({', '.join(place_args_adj)}, {img_inner_adj})"

            # Add clip block with adjusted frame height
            if needs_clip_adj:
                body_expr_adj = f"block(width: {ctx.frame_w_mm:.6f}mm, height: {adjusted_frame_h_mm:.6f}mm, clip: true)[#{img_inner_adj}]"
            else:
                body_expr_adj = img_inner_adj

            from ..generator import escape_text

            cap_e = escape_text(caption)
            align = ctx.align or 'left'
            valign = ctx.valign or 'top'

            code = (
                f"Fig({body_expr_adj}, caption: [{cap_e}], caption_align: {align}, img_align: {align}, "
                f"caption_valign: {valign}, img_valign: {valign}, fill_space: false)"
            )
            return RenderedMedia(code, needs_wrapper=False)

        # Add clip block if content overflows frame
        if needs_clip:
            body_expr = f"block(width: {ctx.frame_w_mm:.6f}mm, height: {ctx.frame_h_mm:.6f}mm, clip: true)[#{img_inner}]"
        else:
            body_expr = img_inner

        return RenderedMedia(body_expr, needs_wrapper=True)


# Factory function for obtaining appropriate strategy
def get_media_renderer(element_type: str) -> MediaRenderStrategy:
    """Factory function to get appropriate renderer for element type.

    Args:
        element_type: Type of element ('figure', 'svg', 'pdf')

    Returns:
        Appropriate MediaRenderStrategy instance with size provider configured

    Raises:
        ValueError: If element_type is not recognized

    Example:
        >>> renderer = get_media_renderer('svg')
        >>> isinstance(renderer, SvgRenderStrategy)
        True
    """
    from .media_sizing import PdfSizeProvider, RasterSizeProvider, SvgSizeProvider

    if element_type == 'figure':
        return FigureRenderStrategy(RasterSizeProvider())
    elif element_type == 'svg':
        return SvgRenderStrategy(SvgSizeProvider())
    elif element_type == 'pdf':
        return PdfRenderStrategy(PdfSizeProvider())
    else:
        raise ValueError(f"Unknown media type: {element_type}")
