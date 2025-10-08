"""Generation package for Typst code generation.

This package handles the conversion from parsed IR to Typst code:
- core: Main generate_typst entry point and orchestration
- layout: Position calculation, alignment, and master page handling
- elements: Element-specific rendering (text, images, PDFs, etc.)
- pdf_processor: PDF handling, sanitization, and fallback processing
- typst_builder: Low-level Typst code construction utilities
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
]
