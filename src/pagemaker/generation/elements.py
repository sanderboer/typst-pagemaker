"""Element rendering utilities for Pagemaker generation system."""

from typing import Any, Dict


# For now, import core rendering functions from generator.py
# These will be moved here in future extraction steps
def render_text_element_from_generator(el: dict, styles: dict):
    """Import and use _render_text_element from generator.py"""
    from .. import generator

    return generator._render_text_element(el, styles)


def render_text_blocks_from_generator(text_blocks: list, el: dict, styles: dict):
    """Import and use _render_text_blocks from generator.py"""
    from .. import generator

    return generator._render_text_blocks(text_blocks, el, styles)


def render_list_block_from_generator(list_block: dict, text_args: str, par_args: str):
    """Import and use _render_list_block from generator.py"""
    from .. import generator

    return generator._render_list_block(list_block, text_args, par_args)


def render_table_block_from_generator(table_block: dict, text_args: str):
    """Import and use _render_table_block from generator.py"""
    from .. import generator

    return generator._render_table_block(table_block, text_args)


def escape_text_from_generator(text: str, styled_wrapper: bool = False):
    """Import and use escape_text from generator.py"""
    from .. import generator

    return generator.escape_text(text, styled_wrapper)


def el_text_from_generator(el: dict):
    """Import and use el_text from generator.py"""
    from .. import generator

    return generator.el_text(el)


class ElementRenderer:
    """Renders individual elements to Typst code."""

    def render_element(self, element: Dict[str, Any]) -> str:
        """Render a single element based on its type."""
        element_type = element.get('type', 'text')

        if element_type == 'text':
            return render_text_element(element)
        elif element_type == 'image':
            return render_image_element(element)
        elif element_type == 'pdf':
            return render_pdf_element(element)
        elif element_type == 'table':
            return render_table_element(element)
        else:
            return f"// Unknown element type: {element_type}"


def render_text_element(element: Dict[str, Any]) -> str:
    """Render text element to Typst code."""
    # For now, delegate to generator.py function
    return "// Text element rendering - delegate to generator"


def render_image_element(element: Dict[str, Any]) -> str:
    """Render image element to Typst code."""
    # This will be implemented when we extract image rendering from generator.py
    return "// Image element placeholder"


def render_pdf_element(element: Dict[str, Any]) -> str:
    """Render PDF element to Typst code."""
    # This will be implemented when we extract PDF rendering from generator.py
    return "// PDF element placeholder"


def render_table_element(element: Dict[str, Any]) -> str:
    """Render table element to Typst code."""
    # This will be implemented using table_render.py functionality
    return "// Table element placeholder"
