"""Generation package for Typst code generation.

This package handles the conversion from parsed IR to Typst code:
- core: Main generate_typst entry point and orchestration
- layout: Position calculation, alignment, and master page handling
- elements: Element-specific rendering (text, images, PDFs, etc.)
- pdf_processor: PDF handling, sanitization, and fallback processing
- html_generator: HTML generation for HTML export (scrolling web narratives)
- story_auto_placement: Auto-placement algorithm for HTML export grid layout
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
from .html_generator import generate_story_html
from .html_typst_generator import generate_html_typst
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
    # HTML export
    'generate_story_html',
    'generate_html_typst',
    'compute_auto_placement',
    'area_to_css_grid',
]
