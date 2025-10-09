import os
import pathlib
import re

from .generation.core import par_args as core_par_args
from .generation.core import style_args
from .table_render import render_table_block as _render_table_block_impl

TYPOGRAPHY = {
    'light': {
        'font_header': 'Inter',
        'font_body': 'Inter',
        'size_header': '2.6em',
        'size_subheader': '1.6em',
        'size_body': '1.0em',
    }
}

# Validation constants for known Typst values
VALID_LINEBREAKS = {'auto', 'loose', 'strict'}
VALID_WEIGHTS = {
    'thin',
    'extralight',
    'light',
    'regular',
    'medium',
    'semibold',
    'bold',
    'extrabold',
    'black',
}


# Alignment utility functions
def _get_alignment_wrapper(element):
    """Create alignment wrapper from element properties.

    This is a simplified version of the utils.alignment.AlignmentWrapper
    integrated directly into generator.py to avoid import complexity.
    """
    align = element.get('align')
    valign = element.get('valign')

    # Normalize alignment values
    if align:
        align = str(align).strip().lower()
        if align not in ('left', 'center', 'right'):
            align = None

    if valign:
        valign = str(valign).strip().lower()
        # Map 'middle' to Typst's 'horizon'
        if valign == 'middle':
            valign = 'horizon'
        elif valign not in ('top', 'horizon', 'bottom'):
            valign = None

    return align, valign


def _apply_alignment_wrapper(content, align, valign):
    """Apply Typst alignment wrapper to content."""
    if not align and not valign:
        return content

    align_terms = []
    if align:
        align_terms.append(align)
    if valign:
        align_terms.append(valign)

    if align_terms:
        inner = content
        # If inner is not a content block, inject as code inside markup block
        s = str(inner).strip()
        if not (s.startswith('[') or s.startswith('#')):
            inner = f"#{inner}"
        return f"align({' + '.join(align_terms)})[{inner}]"

    return content


# Typst generation helper functions
def _typst_text(content, text_args=None):
    """Generate Typst text command with optional styling arguments."""
    if text_args:
        return f"#text({text_args})[{content}]"
    else:
        return f"#text[{content}]"


def _typst_par(content, par_args=None):
    """Generate Typst paragraph command with optional arguments."""
    if par_args:
        return f"#par({par_args})[{content}]"
    else:
        return f"#par()[{content}]"


def _typst_grid_toc_entry(title, page_num):
    """Generate a table of contents entry using grid layout."""
    return (
        f"#grid(columns: (auto, 1fr, auto), gutter: 4pt, "
        f"[#text(font: \"Inter\")[{title}]], "
        f"[#align(center)[#text(font: \"Inter\")[#repeat[.]]]], "
        f"[#text(font: \"Inter\")[{page_num}]])"
    )


def parse_bool(val):
    """Parse a boolean value from string."""
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return None


VALID_NUMERIC_WEIGHTS = {str(i) for i in range(100, 1001, 100)}  # 100, 200, ..., 900

# Style property mappings for efficient lookup
FONT_ALIASES = {'font-family', 'font'}
WEIGHT_ALIASES = {'font-weight', 'weight'}
SIZE_ALIASES = {'font-size', 'size'}
COLOR_ALIASES = {'fill', 'color', 'colour'}
PARAGRAPH_PARAMS = {
    'leading',
    'spacing',
    'justify',
    'linebreaks',
    'first-line-indent',
    'first_line_indent',
    'hanging-indent',
    'hanging_indent',
}

TYPST_HEADER = """// Auto-generated Typst file
// Generated: {timestamp}

#set text(fill: rgb("#1b1f23"))
"""


def _split_paragraphs(text: str) -> list:
    """Split raw text into paragraphs.
    Separators: blank lines, or lines exactly '---' / ':::'.
    Trims surrounding whitespace per paragraph and drops empty ones.
    """
    if not isinstance(text, str) or text == "":
        return []
    lines = text.splitlines()
    paras = []
    buf: list[str] = []

    def flush():
        nonlocal buf
        s = "\n".join(buf).strip()
        if s != "":
            paras.append(s)
        buf = []

    for ln in lines:
        strip = ln.strip()
        if strip == "" or strip in ("---", ":::"):
            flush()
            continue
        buf.append(ln)
    flush()
    return paras


def _render_text_blocks(text_blocks: list, el: dict, styles: dict) -> str:
    """Render a list of text blocks (plain text, lists, tables) to Typst fragments."""
    result_parts = []

    # Get element style information
    style_name = el.get('style') or el.get('type') or 'body'
    style = styles.get(str(style_name).strip().lower(), styles.get(el.get('type'), styles['body']))
    text_args = style_args(style)
    par_args = core_par_args(style, el.get('justify'))

    def _render_text_with_hardbreaks(par_text: str) -> str:
        """Render a paragraph of text, supporting hard line breaks via trailing backslash.
        A backslash at end of a source line forces a line break in Typst without extra spacing.
        """
        # Split into source lines to detect trailing backslashes
        lines = par_text.split('\n')
        pieces = []
        for idx, ln in enumerate(lines):
            # If line ends with a backslash (optional spaces after), force a break
            if re.search(r'\\\s*$', ln):
                # Remove the backslash and trailing spaces
                clean = re.sub(r'\\\s*$', '', ln)
                if clean:
                    txt = escape_text(clean)
                    pieces.append(_typst_text(txt, text_args))
                pieces.append('#linebreak()')
            else:
                txt = escape_text(ln)
                pieces.append(_typst_text(txt, text_args))
                # Only add a space between lines when not at hard break and not last line
                if idx < len(lines) - 1:
                    pieces.append(' ')
        # Join pieces; Typst will consume the literal space separators between #text calls
        return ''.join(pieces)

    for block in text_blocks:
        if block['kind'] == 'plain':
            # Handle plain text blocks
            content = block['content']
            if content.strip():
                # Check if content contains Typst directives or code blocks
                fragments = _process_mixed_content(content)
                has_mixed_content = any(f['type'] in ('typst', 'codeblock') for f in fragments)

                if has_mixed_content:
                    # Process mixed content
                    for fragment in fragments:
                        if fragment['type'] == 'typst':
                            result_parts.append(fragment['content'])
                        elif fragment['type'] == 'codeblock':
                            code_content = fragment['content']
                            lang = fragment['lang']
                            escaped_code = (
                                code_content.replace('\\', '\\\\')
                                .replace('"', '\\"')
                                .replace('\n', '\\n')
                            )
                            if lang and lang != 'text':
                                result_parts.append(
                                    f'#raw("{escaped_code}", lang: "{lang}", block: true)'
                                )
                            else:
                                result_parts.append(f'#raw("{escaped_code}", block: true)')
                        elif fragment['type'] == 'text' and fragment['content'].strip():
                            text_content = fragment['content']
                            paras = _split_paragraphs(text_content)
                            if paras:
                                # Optimization: for single paragraphs without par args, skip #par() wrapper
                                if len(paras) == 1 and not par_args:
                                    text_call = _render_text_with_hardbreaks(paras[0])
                                    result_parts.append(text_call)
                                else:
                                    text_pieces = []
                                    for p in paras:
                                        text_call = _render_text_with_hardbreaks(p)
                                        text_pieces.append(_typst_par(text_call, par_args))
                                    result_parts.append("\n".join(text_pieces))
                else:
                    # Process as plain text
                    paras = _split_paragraphs(content)
                    if paras:
                        # Optimization: for single paragraphs without par args, skip #par() wrapper
                        if len(paras) == 1 and not par_args:
                            text_call = _render_text_with_hardbreaks(paras[0])
                            result_parts.append(text_call)
                        else:
                            text_pieces = []
                            for p in paras:
                                text_call = _render_text_with_hardbreaks(p)
                                text_pieces.append(_typst_par(text_call, par_args))
                            result_parts.append("\n".join(text_pieces))

        elif block['kind'] == 'list':
            # Handle list blocks
            list_typst = _render_list_block(block, text_args, par_args)
            if list_typst:
                result_parts.append(list_typst)
        elif block['kind'] == 'table':
            table_typst = _render_table_block(block, text_args)
            if table_typst:
                result_parts.append(table_typst)

    return "\n".join(result_parts)


def _render_table_block(table_block: dict, text_args: str) -> str:
    """Thin wrapper to delegate table rendering to pagemaker.table_render.

    Keeps the existing symbol for tests while centralizing implementation.
    """
    return _render_table_block_impl(table_block, text_args, escape_text_fn=escape_text)


def _render_list_block(list_block: dict, text_args: str, par_args: str) -> str:
    """Render a list block to Typst using hanging indent approach."""
    list_type = list_block['type']  # 'ul', 'ol', 'dl'
    items = list_block['items']
    tight = list_block.get('tight', True)

    if not items:
        return ""

    result_parts = []

    # Determine spacing between list items to match line height
    spacing_val = None
    if par_args:
        m = re.search(r'(^|,\s*)leading:\s*([^,]+)', par_args)
        if m:
            spacing_val = m.group(2).strip()
    if not spacing_val:
        spacing_val = '1.2em'

    if list_type == 'ul':
        # Unordered list with bullet points
        for item in items:
            text = item.get('text', '').strip()
            checkbox = item.get('checkbox')

            if checkbox:
                # Render checkbox
                if checkbox == 'checked':
                    marker = "[x] "
                elif checkbox == 'partial':
                    marker = "[-] "
                else:
                    marker = "[ ] "
            else:
                marker = "• "  # Unicode bullet

            if text:
                # Use hanging indent to align wrapped lines with the text start
                txt = escape_text(text)
                text_call = _typst_text(txt, text_args)

                # Create hanging indent for list items
                hanging_args = 'hanging-indent: 1.2em'
                if par_args:
                    combined_args = f'{par_args}, {hanging_args}, spacing: {spacing_val}'
                else:
                    combined_args = f'{hanging_args}, spacing: {spacing_val}'

                marker_txt = escape_text(marker)
                marker_call = _typst_text(marker_txt, text_args)

                # Combine marker and text
                combined_content = f"{marker_call}{text_call}"
                list_item = _typst_par(combined_content, combined_args)
                result_parts.append(list_item)

    elif list_type == 'ol':
        # Ordered list with numbers
        start = list_block.get('start', 1)
        style = list_block.get('style', '1')

        for i, item in enumerate(items):
            text = item.get('text', '').strip()
            checkbox = item.get('checkbox')

            # Generate marker based on style
            if style == '1':
                marker = f"{start + i}. "
            elif style == 'a':
                marker = f"{chr(ord('a') + i)}. "
            elif style == 'A':
                marker = f"{chr(ord('A') + i)}. "
            else:
                marker = f"{start + i}. "

            if checkbox:
                # Append checkbox after number
                if checkbox == 'checked':
                    marker += "[x] "
                elif checkbox == 'partial':
                    marker += "[-] "
                else:
                    marker += "[ ] "

            if text:
                txt = escape_text(text)
                text_call = _typst_text(txt, text_args)

                # Create hanging indent for list items
                hanging_args = 'hanging-indent: 1.5em'
                if par_args:
                    combined_args = f'{par_args}, {hanging_args}, spacing: {spacing_val}'
                else:
                    combined_args = f'{hanging_args}, spacing: {spacing_val}'

                marker_txt = escape_text(marker)
                marker_call = _typst_text(marker_txt, text_args)

                # Combine marker and text
                combined_content = f"{marker_call}{text_call}"
                list_item = _typst_par(combined_content, combined_args)
                result_parts.append(list_item)

    elif list_type == 'dl':
        # Description list
        for item in items:
            term = item.get('term', '').strip()
            desc = item.get('desc', '').strip()

            if term:
                # Render term in bold using #strong to avoid weight conflicts
                term_txt = escape_text(term, styled_wrapper=True)
                bold_term = f"#strong[{term_txt}]"
                term_call = _typst_text(bold_term, text_args)
                term_par = _typst_par(term_call, par_args)
                result_parts.append(term_par)

            if desc:
                # Render description with slight indent
                desc_txt = escape_text(desc, styled_wrapper=bool(text_args))
                desc_call = _typst_text(desc_txt, text_args)

                # Add left indent for description
                desc_args = 'hanging-indent: 1em'
                if par_args:
                    combined_args = f'{par_args}, {desc_args}'
                else:
                    combined_args = desc_args

                desc_par = _typst_par(desc_call, combined_args)
                result_parts.append(desc_par)

    # Add spacing between list and following content if not tight
    if not tight and result_parts:
        result_parts.append("")  # Add blank line

    return "\n".join(result_parts)


def _render_text_element(el: dict, styles: dict) -> str:
    """Render a header/subheader/body element to a Typst fragment string.
    Handles styles, paragraph splitting, par(...) args, and justify override.
    Paragraphs are joined with newlines; no stray '+' between paragraphs.
    Now also handles mixed content with Typst directives, code blocks, and lists.
    """
    # Handle mixed content blocks (text, lists, etc.)
    text_blocks = el.get('text_blocks', [])
    if text_blocks:
        return _render_text_blocks(text_blocks, el, styles)

    # Fallback to legacy text processing
    raw = el_text(el)

    # Check if content contains Typst directives or code blocks
    fragments = _process_mixed_content(raw)
    has_mixed_content = any(f['type'] in ('typst', 'codeblock') for f in fragments)

    if has_mixed_content:
        # Handle mixed content with text, Typst directives, and code blocks
        result_parts = []
        for fragment in fragments:
            if fragment['type'] == 'typst':
                # Insert Typst directives directly
                result_parts.append(fragment['content'])
            elif fragment['type'] == 'codeblock':
                # Convert code blocks to Typst raw syntax with syntax highlighting
                code_content = fragment['content']
                lang = fragment['lang']

                # Escape the code content for Typst strings
                escaped_code = (
                    code_content.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                )

                # Use Typst's raw function with language and block parameters
                if lang and lang != 'text':
                    result_parts.append(f'#raw("{escaped_code}", lang: "{lang}", block: true)')
                else:
                    result_parts.append(f'#raw("{escaped_code}", block: true)')
            elif fragment['type'] == 'text' and fragment['content'].strip():
                # Process text content normally
                text_content = fragment['content']
                paras = _split_paragraphs(text_content)
                if paras:
                    style_name = el.get('style') or el.get('type') or 'body'
                    style = styles.get(
                        str(style_name).strip().lower(), styles.get(el.get('type'), styles['body'])
                    )
                    text_args = style_args(style)
                    par_args = core_par_args(style, el.get('justify'))

                    text_pieces = []
                    for p in paras:
                        txt = escape_text(p, styled_wrapper=bool(text_args))
                        text_call = _typst_text(txt, text_args)
                        text_pieces.append(_typst_par(text_call, par_args))
                    result_parts.append("\n".join(text_pieces))
        return "\n".join(result_parts)

    # Pure text content path
    paras = _split_paragraphs(raw)
    style_name = el.get('style') or el.get('type') or 'body'
    style = styles.get(str(style_name).strip().lower(), styles.get(el.get('type'), styles['body']))
    text_args = style_args(style)
    par_args = core_par_args(style, el.get('justify'))
    if len(paras) <= 1 and not par_args:
        txt = escape_text(raw, styled_wrapper=bool(text_args))
        return f"#text({text_args})[{txt}]" if text_args else f"#text[{txt}]"
    if not paras:
        paras = [""]
    pieces = []
    for p in paras:
        txt = escape_text(p, styled_wrapper=bool(text_args))
        text_call = _typst_text(txt, text_args)
        pieces.append(_typst_par(text_call, par_args))
    return "\n".join(pieces)


def generate_typst(ir):
    """Generate Typst content from internal representation.

    This function serves as a compatibility wrapper that delegates to the
    core API while maintaining backward compatibility.

    Args:
        ir: Internal representation dictionary

    Returns:
        str: Complete Typst document content
    """
    from .generation.core import generate_typst as core_generate_typst

    return core_generate_typst(ir)


def el_text(el):
    for tb in el.get('text_blocks', []):
        if tb['kind'] == 'plain':
            return tb['content']
    return el.get('title', '')


def escape_typst_chars(text: str) -> str:
    """Handle basic Typst character escaping.

    Args:
        text: Raw text to escape

    Returns:
        Text with backslashes and quotes escaped for Typst
    """
    return text.replace('\\', '\\\\').replace('"', '\\"')


def process_org_links(text: str) -> tuple[str, list]:
    """Convert Org-mode links to Typst format.

    Uses placeholder protection to prevent interference with other markup processing.
    Supports both [[url][description]] and [[url]] formats.
    Processes emphasis markup within descriptions during link creation.

    Args:
        text: Text containing Org-mode link syntax

    Returns:
        Tuple of (text_with_placeholders, list_of_processed_links)
    """
    import re

    # Step 1: Replace links with temporary placeholders to protect them
    links: list[str] = []

    def link_replacer(match):
        url = match.group(1)
        desc = match.group(2) if match.lastindex >= 2 else None
        if desc:
            # Process emphasis markup in the description before storing
            processed_desc = process_org_emphasis(desc)
            placeholder = f"__LINK_{len(links)}__"
            links.append(f'#link("{url}")[{processed_desc}]')
        else:
            placeholder = f"__LINK_{len(links)}__"
            links.append(f'#link("{url}")')
        return placeholder

    # Handle [[url][description]] format
    text = re.sub(r'\[\[([^\]]+)\]\[([^\]]+)\]\]', link_replacer, text)
    # Handle [[url]] format (plain URLs)
    text = re.sub(r'\[\[([^\]]+)\]\]', link_replacer, text)

    # Step 2: Process other markup safely (URLs are protected by placeholders)
    # This function only handles the placeholder part - restoration happens later

    return text, links


def process_org_emphasis(text: str) -> str:
    """Convert Org-mode emphasis markup to Typst format.

    Converts *bold* to #strong[bold] and /italic/ to #emph[italic].
    Always uses #strong and #emph to avoid weight/style conflicts.

    Args:
        text: Text containing Org-mode emphasis markup

    Returns:
        Text with emphasis markup converted to Typst format
    """
    import re

    # Convert org-mode bold markup (*text*) to strong content
    text = re.sub(r'\*([^*\n]+)\*', r'#strong[\1]', text)
    # Convert org-mode italic markup (/text/) to emphasized content
    text = re.sub(r'/([^/\n]+)/', r'#emph[\1]', text)

    return text


def restore_protected_links(text: str, links: list) -> str:
    """Restore protected links from placeholders.

    Args:
        text: Text containing link placeholders
        links: List of Typst link strings to restore

    Returns:
        Text with placeholders replaced by actual Typst link calls
    """
    for i, link in enumerate(links):
        text = text.replace(f"__LINK_{i}__", link)
    return text


def escape_text(s, styled_wrapper=False):
    """Escape text for Typst and convert org-mode markup to Typst formatting.

    This function orchestrates a pipeline of text processing steps:
    1. Escape basic Typst characters
    2. Convert Org-mode links (with placeholder protection)
    3. Convert Org-mode emphasis markup
    4. Restore protected links

    Args:
        s: Text to escape
        styled_wrapper: If True, uses #strong/#emph to avoid conflicts with outer #text styling
    """
    # Step 1: Escape basic Typst characters
    s = escape_typst_chars(s)

    # Step 2: Process links with protection
    s, protected_links = process_org_links(s)

    # Step 3: Process emphasis markup (links are protected)
    s = process_org_emphasis(s)

    # Step 4: Restore protected links
    s = restore_protected_links(s, protected_links)

    return s


# --- PDF intrinsic size helpers for auto-contain scaling ---


def _compute_element_frame_size_mm(
    page: dict, area: dict, padding: dict | None
) -> tuple[float, float]:
    """Compute the usable frame (content box) size in mm for an element.

    Mirrors Typst runtime helpers layer_grid / layer_grid_padded by summing track widths.
    AREA coordinates are always expressed in the *total* grid when margins are declared
    (i.e. margin tracks present), otherwise they map directly onto the content grid.

    When margins are declared, the total grid structure is:
      [ left_margin_track ] [ content cols ... ] [ right_margin_track ]
      [ top_margin_track ]  [ content rows ... ] [ bottom_margin_track ]
    Each outer margin track has absolute size equal to the declared margin mm value.

    We sum the exact contributions of tracks overlapped by the AREA span. If the span
    includes a margin track, that entire margin size contributes. Content tracks contribute
    their uniform cw or ch size. Finally element padding (if any) is subtracted from both
    dimensions (clamped >= 0).
    """
    page_w = page['page_size']['w_mm']
    page_h = page['page_size']['h_mm']
    cols = page['grid']['cols']
    rows = page['grid']['rows']
    margins_decl = bool(page.get('margins_declared')) and isinstance(page.get('margins_mm'), dict)
    # Derive content cell sizes
    if margins_decl:
        mmm = page.get('margins_mm') or {}
        top_m = float(mmm.get('top', 0.0))
        right_m = float(mmm.get('right', 0.0))
        bottom_m = float(mmm.get('bottom', 0.0))
        left_m = float(mmm.get('left', 0.0))
        content_w = page_w - (left_m + right_m)
        content_h = page_h - (top_m + bottom_m)
        cw = content_w / cols
        ch = content_h / rows
        # Total grid indices range: 1 .. cols+2 (with margins), similarly for rows.
        x_tot = area['x']
        y_tot = area['y']
        w_tot = area['w']
        h_tot = area['h']
        # Iterate horizontally over covered total grid tracks
        frame_w = 0.0
        for col_index in range(x_tot, x_tot + w_tot):
            if col_index == 1:
                frame_w += left_m
            elif col_index == cols + 2:  # right margin track
                frame_w += right_m
            else:
                frame_w += cw
        frame_h = 0.0
        for row_index in range(y_tot, y_tot + h_tot):
            if row_index == 1:
                frame_h += top_m
            elif row_index == rows + 2:  # bottom margin track
                frame_h += bottom_m
            else:
                frame_h += ch
    else:
        # Simple uniform grid
        cw = page_w / cols
        ch = page_h / rows
        frame_w = area['w'] * cw
        frame_h = area['h'] * ch
        top_m = right_m = bottom_m = left_m = 0.0  # for clarity though unused later
    # Subtract padding (element padding sits *inside* frame)
    if isinstance(padding, dict):
        t = float(padding.get('top', 0.0))
        r = float(padding.get('right', 0.0))
        b = float(padding.get('bottom', 0.0))
        left_pad = float(padding.get('left', 0.0))
        frame_w -= left_pad + r
        frame_h -= t + b
    if frame_w < 0:
        frame_w = 0.0
    if frame_h < 0:
        frame_h = 0.0
    return frame_w, frame_h


_pdf_size_cache: dict[str, tuple[float, float]] = {}


def _fmt_len(val: float) -> str:
    try:
        return (f"{float(val):.6f}").rstrip('0').rstrip('.')
    except Exception:
        return "0"


def _pdf_intrinsic_size_mm(path: str) -> tuple[float, float]:
    """Return (width_mm, height_mm) of first page of PDF by parsing MediaBox.
    Falls back to US Letter (612x792pt) when file missing/unreadable.
    Caches results per path for efficiency.
    """
    import math
    import os
    import re

    if not isinstance(path, str) or path == "":
        return 215.9, 279.4  # letter fallback
    if path in _pdf_size_cache:
        return _pdf_size_cache[path]
    width_pt, height_pt = 612.0, 792.0  # letter default
    try:
        if os.path.exists(path):
            # Read limited chunk to find /MediaBox [a b c d]
            with open(path, 'rb') as fh:
                data = fh.read(200_000)  # first 200KB usually enough
            # Decode forgivingly
            try:
                txt = data.decode('latin-1', errors='ignore')
            except Exception:
                txt = ''
            m = re.search(
                r'/MediaBox\s*\[\s*(-?\d+(?:\.\d*)?)\s+(-?\d+(?:\.\d*)?)\s+(-?\d+(?:\.\d*)?)\s+(-?\d+(?:\.\d*)?)\s*\]',
                txt,
            )
            if m:
                x0, y0, x1, y1 = (float(m.group(i)) for i in range(1, 5))
                w = abs(x1 - x0)
                h = abs(y1 - y0)
                # Guard against zero/NaN
                if w > 1 and h > 1 and math.isfinite(w) and math.isfinite(h):
                    width_pt, height_pt = w, h
    except Exception:
        pass
    # Convert points (1/72") to mm
    # Empirical correction: muchpdf appears to render PDF user units ~90 per inch
    # rather than the traditional 72 pt/in. Observed embedded PDFs were ~0.8x
    # expected size (scale deficit of 1/1.25). Adjust conversion so intrinsic
    # size is smaller, yielding a larger auto-contain scale that fills frames.
    # When muchpdf clarifies its internal DPI, revisit this (possibly 96/in etc.).
    mm_per_pt = 25.4 / 90.0
    width_mm = width_pt * mm_per_pt
    height_mm = height_pt * mm_per_pt
    _pdf_size_cache[path] = (width_mm, height_mm)
    return width_mm, height_mm


def _is_typst_directive(line):
    """Check if a line is a Typst directive that should not be escaped."""
    stripped = line.strip()
    return (
        stripped.startswith('#set ')
        or stripped.startswith('#show ')
        or stripped.startswith('#let ')
        or stripped.startswith('#import ')
    )


def _process_mixed_content(content):
    """Process content that may contain both regular text, Typst directives, and code blocks.
    Returns a list of fragments where each fragment is either:
    - {'type': 'text', 'content': str} - regular text that needs escaping
    - {'type': 'typst', 'content': str} - raw Typst code to insert directly
    - {'type': 'codeblock', 'content': str, 'lang': str} - code block for syntax highlighting
    """
    if not content.strip():
        return [{'type': 'text', 'content': content}]

    lines = content.split('\n')
    fragments = []
    current_text_lines = []

    def flush_text_lines():
        if current_text_lines:
            fragments.append({'type': 'text', 'content': '\n'.join(current_text_lines)})
            current_text_lines.clear()

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for Typst directives
        if _is_typst_directive(line):
            flush_text_lines()
            fragments.append({'type': 'typst', 'content': line.strip()})
            i += 1
            continue

        # Check for code blocks (lines starting with ```)
        if line.strip().startswith('```'):
            flush_text_lines()

            # Extract language from the opening line
            lang_match = line.strip()[3:].strip()
            lang = lang_match if lang_match else 'text'

            # Collect code block content until closing ```
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1

            # Add the code block fragment
            code_content = '\n'.join(code_lines)
            fragments.append({'type': 'codeblock', 'content': code_content, 'lang': lang})

            # Skip the closing ``` line
            if i < len(lines):
                i += 1
            continue

        # Regular text line
        current_text_lines.append(line)
        i += 1

    flush_text_lines()
    return fragments


def update_html_total(html_path: pathlib.Path, total: int):
    """Update the total page count in an HTML file.

    This function finds and replaces JavaScript variable declarations for 'total'
    in HTML files to reflect the actual page count. Used for updating web viewers
    or HTML exports with correct pagination information.

    Args:
        html_path: Path to the HTML file to update
        total: The total page count to set

    Returns:
        bool: True if the update was successful, False if no update pattern was found
    """
    if not html_path.exists():
        return False
    txt = html_path.read_text(encoding='utf-8')
    import re

    new_txt, count = re.subn(r'let total = undefined;', f'let total = {total};', txt, count=1)
    if count == 0:
        new_txt, count2 = re.subn(r'let total = [^;]+;', f'let total = {total};', txt, count=1)
        if count2 == 0:
            return False
        else:
            html_path.write_text(new_txt, encoding='utf-8')
            return True
    else:
        html_path.write_text(new_txt, encoding='utf-8')
        return True


def adjust_asset_paths(ir, typst_dir: pathlib.Path):
    """Adjust relative asset paths in IR to be relative to typst_dir.

    This function modifies asset paths in the intermediate representation
    to ensure they are correctly resolved relative to the target Typst
    directory for proper compilation.

    Args:
        ir: Intermediate representation dictionary
        typst_dir: Target directory for Typst compilation
    """
    try:
        typst_dir = typst_dir.resolve()
    except Exception:
        return
    # Determine project root relative to this module (../../)
    try:
        project_root = pathlib.Path(__file__).resolve().parents[2]
    except Exception:
        project_root = pathlib.Path.cwd()

    def resolve_rel(src: str) -> str:
        if os.path.isabs(src) or re.match(r'^[a-zA-Z]+:', src):
            return src

        # If file exists relative to current working directory,
        # compute path relative to typst_dir (where .typ file will be)
        cwd_path = pathlib.Path.cwd() / src
        try:
            if cwd_path.resolve().exists():
                return os.path.relpath(cwd_path.resolve(), typst_dir)
        except Exception:
            pass

        # Try other candidates if not found in cwd
        candidates = [
            (project_root / src),
            (typst_dir / src),
        ]
        for cand in candidates:
            try:
                c = cand.resolve()
            except Exception:
                continue
            if c.exists():
                # Found existing file, rewrite relative to export dir
                try:
                    return os.path.relpath(c, typst_dir)
                except Exception:
                    continue

        # Special fallback: if user referenced 'assets/...', also look under examples/assets
        if src.startswith('assets/'):
            alt = project_root / 'examples' / src
            try:
                alt_res = alt.resolve()
                if alt_res.exists():
                    try:
                        return os.path.relpath(alt_res, typst_dir)
                    except Exception:
                        pass
            except Exception:
                pass

        # If no file found but src is relative, try best-effort path adjustment
        # relative to project root (common case for assets)
        if not os.path.isabs(src):
            try:
                project_asset_path = (project_root / src).resolve()
                return os.path.relpath(project_asset_path, typst_dir)
            except Exception:
                pass
        return src

    for page in ir.get('pages', []):
        for el in page.get('elements', []):
            fig = el.get('figure')
            if fig and fig.get('src'):
                fig['src'] = resolve_rel(fig['src'])
            pdf = el.get('pdf')
            if pdf and pdf.get('src'):
                pdf['src'] = resolve_rel(pdf['src'])
            svg = el.get('svg')
            if svg and svg.get('src'):
                svg['src'] = resolve_rel(svg['src'])
