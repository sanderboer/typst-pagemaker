"""Generation package for Typst code generation.

This package handles the conversion from parsed IR to Typst code:
- core: Main generate_typst entry point and orchestration
- layout: Position calculation, alignment, and master page handling
- elements: Element-specific rendering (text, images, PDFs, etc.)
- pdf_processor: PDF handling, sanitization, and fallback processing
- typst_builder: Low-level Typst code construction utilities
- story_generator: HTML generation for story mode (scrolling web narratives)
- story_auto_placement: Auto-placement algorithm for story mode grid layout
"""

from .core import generate_typst
from .layout import (
    LayoutCalculator,
    MasterPageProcessor,
    calculate_element_positions,
)
from .elements import (
    ElementRenderer,
    render_text_element,
    render_image_element,
    render_pdf_element,
    render_table_element,
)
from .pdf_processor import (
    PDFProcessor,
    sanitize_pdf_assets,
    apply_pdf_fallbacks,
)
from .story_generator import generate_story_html
from .story_auto_placement import compute_auto_placement, area_to_css_grid

__all__ = [
    # Core functionality
    'generate_typst',
    # Layout processing
    'LayoutCalculator',
    'MasterPageProcessor',
    'calculate_element_positions',
    # Element rendering
    'ElementRenderer',
    'render_text_element',
    'render_image_element',
    'render_pdf_element',
    'render_table_element',
    # PDF processing
    'PDFProcessor',
    'sanitize_pdf_assets',
    'apply_pdf_fallbacks',
    # Story mode
    'generate_story_html',
    'compute_auto_placement',
    'area_to_css_grid',
]
