"""
HTML-specific Typst code generation.

This module generates Typst code optimized for HTML export using Typst's html module.
Unlike PDF generation which uses absolute positioning, HTML generation creates semantic
HTML structure with proper headings, paragraphs, and sections.
"""

import datetime
from typing import Any, Dict


def generate_html_typst(ir: Dict[str, Any]) -> str:
    """
    Generate HTML-compatible Typst code from IR.

    This function creates Typst code that uses semantic markup suitable for HTML export.
    It does NOT use page setup directives or absolute positioning.

    Args:
        ir: Intermediate representation from parser

    Returns:
        Typst code string optimized for HTML export
    """
    out = []

    # Header
    out.append("// Auto-generated Typst file for HTML export")
    out.append(f"// Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n")

    # Generate header and setup (no page directives)
    out.append(_generate_html_header_and_setup(ir))

    # Generate content for each page (non-master pages)
    pages = ir.get('pages', [])
    for page in pages:
        # Skip master definition pages
        if page.get('master_def'):
            continue

        out.append(_generate_html_page(page, ir))

    return '\n'.join(out)


def _generate_html_header_and_setup(ir: Dict[str, Any]) -> str:
    """Generate HTML-compatible header without page setup directives."""
    out = []

    # Basic text color (theme could be expanded later)
    out.append('#set text(fill: rgb("#1b1f23"))\n')

    # Theme setup (simplified for HTML)
    meta = ir.get('meta', {})
    theme = meta.get('THEME', 'light')

    out.append('#let theme = (')
    out.append('  font_header: "Inter",')
    out.append('  font_body: "Inter",')
    out.append('  size_header: 2.0em,')
    out.append('  size_subheader: 1.5em,')
    out.append('  size_body: 1.0em')
    out.append(')\n')

    # Date helpers
    d = _parse_date_from_meta(meta)
    yy = d.strftime('%y')
    mm = d.strftime('%m')
    dd = d.strftime('%d')
    y4 = d.strftime('%Y')
    iso = f"{y4}-{mm}-{dd}"

    out.append(f'#let date_iso = "{iso}"')
    out.append(f'#let date_yy_mm_dd = "{yy}.{mm}.{dd}"')
    out.append(f'#let date_dd_mm_yy = "{dd}.{mm}.{yy}"\n')

    # Document metadata
    title = meta.get('TITLE', 'Document')
    author = meta.get('AUTHOR', '')

    out.append(
        f'#set document(title: "{_escape_string(title)}", author: "{_escape_string(author)}", date: datetime(year: {y4}, month: {mm}, day: {dd}))\n'
    )

    return '\n'.join(out)


def _generate_html_page(page: Dict[str, Any], ir: Dict[str, Any]) -> str:
    """Generate HTML content for a single page using semantic markup."""
    out = []

    page_title = page.get('title', '')
    page_id = page.get('id', '')

    out.append(f'\n// Page: {page_title} ({page_id})')

    # Add page title as a level 1 heading if it exists
    if page_title:
        out.append(f'= {_escape_string(page_title)}\n')

    # Process elements in order (skip master elements, they're decorative)
    elements = page.get('elements', [])
    for elem in elements:
        elem_content = _generate_html_element(elem, ir)
        if elem_content:
            out.append(elem_content)

    # Add page break between pages (might not render in HTML but keeps structure)
    out.append('#pagebreak(weak: true)\n')

    return '\n'.join(out)


def _generate_html_element(elem: Dict[str, Any], ir: Dict[str, Any]) -> str:
    """Generate HTML-compatible Typst code for a single element."""
    elem_type = elem.get('type')
    elem_id = elem.get('id', '')

    out = []
    out.append(f'// Element: {elem_id} (type: {elem_type})')

    # Handle different element types
    if elem_type == 'header':
        content = _generate_text_content(elem, plain_text_only=True)
        if content:
            out.append(f'== {content}\n')

    elif elem_type == 'subheader':
        content = _generate_text_content(elem, plain_text_only=True)
        if content:
            out.append(f'=== {content}\n')

    elif elem_type == 'body':
        content = _generate_text_content(elem)
        if content:
            out.append(f'{content}\n')

    elif elem_type == 'rectangle':
        # Skip decorative rectangles in HTML export
        out.append('// (decorative rectangle skipped in HTML)\n')

    elif elem_type == 'svg':
        svg_data = elem.get('svg')
        if svg_data:
            # svg field is a dict with 'src', 'scale', 'fit', 'caption'
            if isinstance(svg_data, dict):
                svg_path = svg_data.get('src', '')
                svg_caption = svg_data.get('caption', '')
            else:
                svg_path = str(svg_data)
                svg_caption = ''

            if svg_path:
                out.append('#figure(')
                out.append(f'  image("{svg_path}", width: 80%),')
                # Use caption from svg dict or element title
                caption = svg_caption or elem.get('title', '')
                if caption:
                    out.append(f'  caption: [{_escape_string(caption)}]')
                out.append(')\n')

    elif elem_type == 'figure':
        fig_data = elem.get('figure')
        if fig_data:
            # figure field might also be a dict
            if isinstance(fig_data, dict):
                fig_path = fig_data.get('src', '')
                fig_caption = fig_data.get('caption', '')
            else:
                fig_path = str(fig_data)
                fig_caption = ''

            if fig_path:
                out.append('#figure(')
                out.append(f'  image("{fig_path}", width: 80%),')
                # Use caption from figure dict or element title
                caption = fig_caption or elem.get('title', '')
                if caption:
                    out.append(f'  caption: [{_escape_string(caption)}]')
                out.append(')\n')

    elif elem_type == 'pdf':
        # Render PDF as an image in HTML (Typst will handle the conversion)
        pdf_data = elem.get('pdf')
        if pdf_data:
            if isinstance(pdf_data, dict):
                pdf_path = pdf_data.get('src', '')
                pdf_caption = pdf_data.get('caption', '')
                pdf_pages = pdf_data.get('pages', [])
            else:
                pdf_path = str(pdf_data)
                pdf_caption = ''
                pdf_pages = []

            if pdf_path:
                out.append('#figure(')
                # If specific pages are requested, use them; otherwise use default
                if pdf_pages:
                    # For HTML, we'll just use the first page for simplicity
                    out.append(f'  image("{pdf_path}", width: 80%),')
                else:
                    out.append(f'  image("{pdf_path}", width: 80%),')
                # Use caption from pdf dict or element title
                caption = pdf_caption or elem.get('title', '')
                if caption:
                    out.append(f'  caption: [{_escape_string(caption)}]')
                out.append(')\n')

    else:
        out.append(f'// (unknown element type: {elem_type})\n')

    return '\n'.join(out)


def _generate_text_content(elem: Dict[str, Any], plain_text_only: bool = False) -> str:
    """
    Extract and format text content from an element.

    Args:
        elem: Element dictionary containing text_blocks
        plain_text_only: If True, only extract plain text content (skip lists, tables, etc.)
                        Useful for headers where structured content doesn't make sense.
    """
    text_blocks = elem.get('text_blocks', [])
    if not text_blocks:
        return ''

    parts = []

    for block in text_blocks:
        kind = block.get('kind')

        if kind == 'plain':
            # Regular plain text or paragraph
            parts.append(block.get('content', ''))

        elif kind == 'list':
            if plain_text_only:
                # For headers, just extract the text from list items without list markup
                items = block.get('items', [])
                for item in items:
                    item_text = item.get('text', '')
                    if item_text:
                        parts.append(item_text)
            else:
                # For body content, render as Typst list
                list_type = block.get('type', 'ul')
                items = block.get('items', [])

                for item in items:
                    item_text = item.get('text', '')
                    if list_type == 'ol':
                        parts.append(f'+ {item_text}')
                    else:
                        parts.append(f'- {item_text}')

        elif kind == 'table':
            if not plain_text_only:
                # Tables (simplified for now)
                parts.append(_generate_table(block))

        elif kind == 'hardbreak':
            # Line break
            parts.append('\n')

        else:
            # Unknown block kind, try to extract content or text
            content = block.get('content', block.get('text', ''))
            if content:
                parts.append(content)

    content = '\n\n'.join(parts)
    if not content:
        return content
    cols = elem.get('columns')
    if cols and cols > 1:
        gap = elem.get('column_gap')
        gap_part = f', gutter: {gap:g}mm' if gap else ''
        return f'#columns({cols}{gap_part})[{content}]'
    return content


def _generate_table(table_block: Dict[str, Any]) -> str:
    """Generate Typst table from table block."""
    # This is a simplified implementation
    # Full table support would need column parsing, alignment, etc.
    return '// (table rendering simplified in HTML)\n'


def _parse_date_from_meta(meta: Dict[str, Any]) -> datetime.date:
    """Parse date from metadata or use today."""
    d = None
    try:
        ds = (meta.get('DATE_OVERRIDE') or meta.get('DATE') or '').strip()
        if ds:
            ds_norm = ds.replace('/', '-').replace('.', '-')
            d = datetime.date.fromisoformat(ds_norm)
    except Exception:
        d = None

    if d is None:
        d = datetime.date.today()

    return d


def _escape_string(s: str) -> str:
    """Escape string for Typst string literals."""
    if not s:
        return ''
    # Escape quotes and backslashes
    s = s.replace('\\', '\\\\')
    s = s.replace('"', '\\"')
    return s
