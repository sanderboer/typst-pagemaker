import datetime
import os
import pathlib
import re
import sys
import warnings

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


def _parse_style_decl_from_generator(s: str) -> dict:
    """Parse a style declaration string like 'font: Inter, weight: bold, size: 24pt, color: #333'.
    Returns dict with optional keys: font, weight, size, color (strings as provided, trimmed).
    Accepts separators comma/semicolon, and key separators ':' or '='. Keys are case-insensitive.
    Aliases: font-family->font, font-weight->weight, font-size->size, fill->color.
    Safely ignores commas/semicolons inside parentheses or quotes (e.g., rgb(50%,50%,50%)).

    Also accepts paragraph options (applied via Typst par()):
    - leading, spacing, justify, linebreaks, first-line-indent (first_line_indent), hanging-indent (hanging_indent)
    """
    if not isinstance(s, str):
        return {}

    # Split on top-level commas/semicolons only (not inside () or quotes)
    parts = []
    buf = []
    depth = 0
    in_quote = None
    prev = ''
    for ch in s:
        if in_quote:
            buf.append(ch)
            if ch == in_quote and prev != '\\':
                in_quote = None
        else:
            if ch in ('"', "'"):
                in_quote = ch
                buf.append(ch)
            elif ch == '(':
                depth += 1
                buf.append(ch)
            elif ch == ')':
                if depth > 0:
                    depth -= 1
                buf.append(ch)
            elif ch in (',', ';') and depth == 0:
                parts.append(''.join(buf))
                buf = []
            else:
                buf.append(ch)
        prev = ch
    if buf:
        parts.append(''.join(buf))

    out = {}
    for part in parts:
        if not part:
            continue
        if ':' in part:
            k, v = part.split(':', 1)
        elif '=' in part:
            k, v = part.split('=', 1)
        else:
            continue
        k = k.strip().lower()
        v = v.strip()
        if not k:
            continue

        # Use efficient set lookups instead of tuple checks
        if k in FONT_ALIASES:
            out['font'] = v
        elif k in WEIGHT_ALIASES:
            # Validate weight values
            if v.lower() not in VALID_WEIGHTS and v not in VALID_NUMERIC_WEIGHTS:
                warnings.warn(
                    f"Unknown font weight '{v}'. Valid values: {', '.join(sorted(VALID_WEIGHTS | VALID_NUMERIC_WEIGHTS))}",
                    UserWarning,
                )
            out['weight'] = v
        elif k in SIZE_ALIASES:
            out['size'] = v
        elif k in COLOR_ALIASES:
            out['color'] = v
        elif k == 'linebreaks':
            # Validate linebreaks values
            if v.lower() not in VALID_LINEBREAKS:
                warnings.warn(
                    f"Unknown linebreaks value '{v}'. Valid values: {', '.join(sorted(VALID_LINEBREAKS))}",
                    UserWarning,
                )
            out['linebreaks'] = v
        elif k in PARAGRAPH_PARAMS:
            # Handle parameter name normalization
            if k in ('first_line_indent', 'first-line-indent'):
                out['first-line-indent'] = v
            elif k in ('hanging_indent', 'hanging-indent'):
                out['hanging-indent'] = v
            else:
                out[k] = v
        else:
            # Warn about unrecognized properties
            warnings.warn(f"Unrecognized style property '{k}' in declaration: {s}", UserWarning)
    return out


def _build_styles_from_generator(meta: dict) -> dict:
    """Build style map from meta keys. Keys look like 'STYLE_NAME'. Case-insensitive.
    Defaults:
      - header: Inter bold 24pt
      - subheader: Inter semibold 18pt
      - body: Inter (no size/weight by default)
    User can override by defining #+STYLE_HEADER:, #+STYLE_SUBHEADER:, #+STYLE_BODY: etc.
    Additional styles can be declared with any other suffix, e.g. #+STYLE_HERO: ...

    A global #+FONT: directive will override the default font for all styles unless explicitly overridden.
    """
    styles = {
        'header': {'font': 'Inter', 'weight': 'bold', 'size': '24pt'},
        'subheader': {'font': 'Inter', 'weight': 'semibold', 'size': '18pt'},
        'body': {'font': 'Inter'},
    }

    # Check for global FONT directive and apply it to all default styles
    if meta and 'FONT' in meta:
        global_font = meta['FONT'].strip()
        if global_font:
            for style_name in styles:
                styles[style_name]['font'] = global_font

    for k, v in (meta or {}).items():
        if not isinstance(k, str) or not k.upper().startswith('STYLE_'):
            continue
        # Skip plain STYLE without suffix
        if k.strip().upper() == 'STYLE':
            continue
        name = k.split('_', 1)[1].strip().lower()
        if not name:
            continue
        decl = _parse_style_decl_from_generator(v)
        if name in styles:
            styles[name] = {**styles[name], **decl}
        else:
            styles[name] = decl
    return styles


def _style_args_from_generator(style: dict) -> str:
    """Render Typst #text argument list from a style dict.
    Order: font, weight, size, fill. Omit missing.
    Quotes font always. For weight, quote if non-numeric; keep numeric bare.
    For color, if starts with '#', render as fill: rgb("#xxxxxx"). If starts with rgb( or hsl( etc., pass through.
    """
    if not isinstance(style, dict):
        style = {}
    parts = []
    f = style.get('font')
    if isinstance(f, str) and f:
        parts.append(f'font: "{f}"')
    w = style.get('weight')
    if isinstance(w, str) and w:
        if re.fullmatch(r'[0-9]+', w.strip()):
            parts.append(f'weight: {w.strip()}')
        else:
            parts.append(f'weight: "{w.strip()}"')
    s = style.get('size')
    if isinstance(s, str) and s:
        parts.append(f'size: {s.strip()}')
    c = style.get('color')
    if isinstance(c, str) and c:
        cv = c.strip()
        if cv.startswith('#'):
            parts.append(f'fill: rgb("{cv}")')
        elif re.match(r'^[a-zA-Z]+\(', cv):
            parts.append(f'fill: {cv}')
        else:
            # Assume hex-like or named color
            parts.append(f'fill: rgb("{cv}")')
    return ', '.join(parts)


def _split_paragraphs(text: str) -> list:
    """Split raw text into paragraphs.
    Separators: blank lines, or lines exactly '---' / ':::'.
    Trims surrounding whitespace per paragraph and drops empty ones.
    """
    if not isinstance(text, str) or text == "":
        return []
    lines = text.splitlines()
    paras = []
    buf = []

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


def _bool_token(val: str) -> str:
    s = str(val).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return "true"
    if s in ("0", "false", "no", "n", "off"):
        return "false"
    return s  # pass-through (user may supply a Typst expression)


def _par_args_from_generator(style: dict, justify_override: object) -> str:
    """Build Typst par(...) argument list from style and element override.
    Includes: leading, spacing, first-line-indent, hanging-indent, linebreaks, justify.
    Element-level justify overrides style value when provided.
    """
    if not isinstance(style, dict):
        style = {}
    parts = []
    # leading, spacing: lengths
    for key in ("leading", "spacing"):
        v = style.get(key)
        if isinstance(v, str) and v.strip():
            parts.append(f"{key}: {v.strip()}")
    # first-line-indent, hanging-indent
    v = style.get("first-line-indent")
    if isinstance(v, str) and v.strip():
        parts.append(f"first-line-indent: {v.strip()}")
    v = style.get("hanging-indent")
    if isinstance(v, str) and v.strip():
        parts.append(f"hanging-indent: {v.strip()}")
    # linebreaks: raw token (e.g., auto/loose/strict). User is responsible for correctness
    v = style.get("linebreaks")
    if isinstance(v, str) and v.strip():
        parts.append(f"linebreaks: {v.strip()}")
    # justify: override from element wins; else from style
    if isinstance(justify_override, bool):
        parts.append(f"justify: {'true' if justify_override else 'false'}")
    else:
        vj = style.get("justify")
        if isinstance(vj, str) and vj.strip():
            parts.append(f"justify: {_bool_token(vj)}")
    return ', '.join(parts)


def _render_text_blocks(text_blocks: list, el: dict, styles: dict) -> str:
    """Render a list of text blocks (plain text, lists, tables) to Typst fragments."""
    result_parts = []

    # Get element style information
    style_name = el.get('style') or el.get('type') or 'body'
    style = styles.get(str(style_name).strip().lower(), styles.get(el.get('type'), styles['body']))
    text_args = _style_args_from_generator(style)
    par_args = _par_args_from_generator(style, el.get('justify'))

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
                    text_args = _style_args_from_generator(style)
                    par_args = _par_args_from_generator(style, el.get('justify'))

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
    text_args = _style_args_from_generator(style)
    par_args = _par_args_from_generator(style, el.get('justify'))
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
    theme_name = ir['meta'].get('THEME', 'light')
    theme = TYPOGRAPHY.get(theme_name, TYPOGRAPHY['light'])

    # Build styles from document meta
    styles = _build_styles_from_generator(ir.get('meta') or {})

    # Discover and validate fonts
    available_fonts = _discover_available_fonts()
    font_warnings = _validate_font_availability(styles, available_fonts)

    # Emit font warnings if any
    for warning in font_warnings:
        warnings.warn(warning, UserWarning)

    out = []
    out.append(
        TYPST_HEADER.format(timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat())
    )
    out.append("#import \"@preview/muchpdf:0.1.1\": muchpdf\n")
    out.append("#let theme = (")
    out.append(f"  font_header: \"{theme['font_header']}\",")
    out.append(f"  font_body: \"{theme['font_body']}\",")
    out.append(f"  size_header: {theme['size_header']},")
    out.append(f"  size_subheader: {theme['size_subheader']},")
    out.append(f"  size_body: {theme['size_body']}")
    out.append(")\n")
    out.append("#let Header(txt) = text(weight: 700, size: 24pt)[txt]\n")
    out.append("#let Subheader(txt) = text(weight: 600, size: 24pt)[txt]\n")
    out.append("#let Body(txt) = text(size: 24pt)[txt]\n")
    # Set a uniform page size for the entire document (Typst cannot vary per page)
    first_render_page = None
    try:
        for p in ir.get('pages', []):
            if not (p.get('master_def') or '').strip():
                first_render_page = p
                break
    except Exception:
        first_render_page = None
    if first_render_page is not None:
        pw = first_render_page.get('page_size', {}).get('w_mm', 210)
        ph = first_render_page.get('page_size', {}).get('h_mm', 297)
    else:
        pw, ph = 210, 297
    out.append(f"#set page(width: {pw}mm, height: {ph}mm, margin: 0mm)\n")

    # Dynamic date and page helpers
    # Prefer reproducible date from meta: DATE_OVERRIDE or DATE (YYYY-MM-DD). Fallback to today.
    d = None
    try:
        meta = ir.get('meta') or {}
        ds = (meta.get('DATE_OVERRIDE') or meta.get('DATE') or '').strip()
        if ds:
            ds_norm = ds.replace('/', '-').replace('.', '-')
            d = datetime.date.fromisoformat(ds_norm)
    except Exception:
        d = None
    if d is None:
        d = datetime.date.today()
    yy = d.strftime('%y')
    mm = d.strftime('%m')
    dd = d.strftime('%d')
    y4 = d.strftime('%Y')
    iso = f"{y4}-{mm}-{dd}"
    out.append(f"#let date_iso = \"{iso}\"\n")
    out.append(f"#let date_yy_mm_dd = \"{yy}.{mm}.{dd}\"\n")
    out.append(f"#let date_dd_mm_yy = \"{dd}.{mm}.{yy}\"\n")
    out.append("#let page_no = context counter(page).display()\n")
    out.append("#let page_total = context counter(page).final().at(0)\n")
    out.append(
        "#let Fig(img, caption: none, caption_align: left, img_align: left) = if caption == none { \n  block(width: 100%, height: 100%)[#align(img_align)[#img]] \n} else { \n  block(width: 100%, height: 100%)[\n    #block(height: 85%)[#align(img_align)[#img]] \n    #block(height: 15%)[#align(caption_align)[#text(size: 0.75em, fill: rgb(60%,60%,60%), font: theme.font_body)[#caption]]] \n  ] \n}\n"
    )
    out.append(
        "#let ColorRect(color, alpha) = {\n  block(width: 100%, height: 100%, fill: rgb(color).transparentize(100% - alpha * 100%))[]\n}\n"
    )
    out.append(
        "#let PdfEmbed(path, page: 1, scale: 1.0) = {\n  let pdf_data = read(path, encoding: none)\n  let pg = page - 1\n  let pdf_img = muchpdf(pdf_data, pages: pg, scale: scale)\n  // Allow overflow so explicit scale can extend beyond frame intentionally\n  block(width: 100%, height: 100%)[\n    #pdf_img\n  ]\n}\n"
    )
    out.append(
        "#let layer(cw, ch, x, y, w, h, body) = place(\n  dx: (x - 1) * cw,\n  dy: (y - 1) * ch,\n  block(\n    width: w * cw,\n    height: h * ch,\n    body\n  )\n)\n"
    )
    out.append(
        "#let layer_mm(cw, ch, left_mm, top_mm, x, y, w, h, body) = place(\n  dx: left_mm + (x - 1) * cw,\n  dy: top_mm + (y - 1) * ch,\n  block(\n    width: w * cw,\n    height: h * ch,\n    body\n  )\n)\n"
    )
    out.append("""#let draw_grid(cols, rows, cw, ch) = {
  // grid lines
  for col in range(1, cols + 1) {
    place(line(start: ((col - 1) * cw, 0pt), end: ((col - 1) * cw, rows * ch), stroke: 0.5pt + rgb("#ccc")))
  }
  for row in range(1, rows + 1) {
    place(line(start: (0pt, (row - 1) * ch), end: (cols * cw, (row - 1) * ch), stroke: 0.5pt + rgb("#ccc")))
  }
  // column labels on top
  for col in range(1, cols + 1) {
    place(dx: (col - 1) * cw + 2pt, dy: 2pt, text(size: 8pt, fill: rgb("#888"))[#col])
  }
  // row labels on left (lowercase)
  let letters = ("a","b","c","d","e","f","g","h","i","j","k","l","m","n","o","p","q","r","s","t","u","v","w","x","y","z")
  for row in range(1, rows + 1) {
    let label = if row <= 26 { letters.at(row - 1) } else { str(row) }
    place(dx: 2pt, dy: (row - 1) * ch + 2pt, text(size: 8pt, fill: rgb("#888"))[#label])
  }
}
""")
    out.append("""#let draw_grid_offset(cols, rows, cw, ch, dx, dy) = {
  // grid lines with offset
  for col in range(1, cols + 1) {
    place(line(start: (dx + (col - 1) * cw, dy), end: (dx + (col - 1) * cw, dy + rows * ch), stroke: 0.5pt + rgb("#ccc")))
  }
  for row in range(1, rows + 1) {
    place(line(start: (dx, dy + (row - 1) * ch), end: (dx + cols * cw, dy + (row - 1) * ch), stroke: 0.5pt + rgb("#ccc")))
  }
  // column labels on top
  for col in range(1, cols + 1) {
    place(dx: dx + (col - 1) * cw + 2pt, dy: dy + 2pt, text(size: 8pt, fill: rgb("#888"))[#col])
  }
  // row labels on left (lowercase)
  let letters = ("a","b","c","d","e","f","g","h","i","j","k","l","m","n","o","p","q","r","s","t","u","v","w","x","y","z")
  for row in range(1, rows + 1) {
    let label = if row <= 26 { letters.at(row - 1) } else { str(row) }
    place(dx: dx + 2pt, dy: dy + (row - 1) * ch + 2pt, text(size: 8pt, fill: rgb("#888"))[#label])
  }
}
""")
    out.append("""// Variable-track grid helpers (support mm-sized outer tracks)
#let col_width(i, gp) = if i <= gp.lc { if gp.lc == 0 { 0mm } else { gp.lm / gp.lc } } else if i <= gp.lc + gp.cc { gp.cw } else { if gp.rc == 0 { 0mm } else { gp.rm / gp.rc } }
#let row_height(j, gp) = if j <= gp.lr { if gp.lr == 0 { 0mm } else { gp.tm / gp.lr } } else if j <= gp.lr + gp.cr { gp.ch } else { if gp.br == 0 { 0mm } else { gp.bm / gp.br } }
#let sum_cols(from, count, gp) = {
  let total = 0mm
  if count <= 0 { return total }
  for i in range(from, from + count) { total = total + col_width(i, gp) }
  total
}
#let sum_rows(from, count, gp) = {
  let total = 0mm
  if count <= 0 { return total }
  for j in range(from, from + count) { total = total + row_height(j, gp) }
  total
}
#let layer_grid(gp, x, y, w, h, body) = place(
  dx: sum_cols(1, x - 1, gp),
  dy: sum_rows(1, y - 1, gp),
  block(width: sum_cols(x, w, gp), height: sum_rows(y, h, gp), body)
)
#let layer_grid_padded(gp, x, y, w, h, top, right, bottom, left, body) = {
  let dx = sum_cols(1, x - 1, gp) + left
  let dy = sum_rows(1, y - 1, gp) + top
  let frame_w = sum_cols(x, w, gp) - left - right
  let frame_h = sum_rows(y, h, gp) - top - bottom
  if frame_w < 0mm { frame_w = 0mm }
  if frame_h < 0mm { frame_h = 0mm }
  place(dx: dx, dy: dy, block(width: frame_w, height: frame_h, body))
}
#let layer_grid_margin(gp, x, y, w, h, margin_top, margin_right, margin_bottom, margin_left, body) = {
  let dx = sum_cols(1, x - 1, gp) + margin_left
  let dy = sum_rows(1, y - 1, gp) + margin_top
  let frame_w = sum_cols(x, w, gp) - margin_left - margin_right
  let frame_h = sum_rows(y, h, gp) - margin_top - margin_bottom
  if frame_w < 0mm { frame_w = 0mm }
  if frame_h < 0mm { frame_h = 0mm }
  place(dx: dx, dy: dy, block(width: frame_w, height: frame_h, body))
}
#let layer_grid_margin_padded(gp, x, y, w, h, margin_top, margin_right, margin_bottom, margin_left, pad_top, pad_right, pad_bottom, pad_left, body) = {
  let dx = sum_cols(1, x - 1, gp) + margin_left + pad_left
  let dy = sum_rows(1, y - 1, gp) + margin_top + pad_top
  let frame_w = sum_cols(x, w, gp) - margin_left - margin_right - pad_left - pad_right
  let frame_h = sum_rows(y, h, gp) - margin_top - margin_bottom - pad_top - pad_bottom
  if frame_w < 0mm { frame_w = 0mm }
  if frame_h < 0mm { frame_h = 0mm }
  place(dx: dx, dy: dy, block(width: frame_w, height: frame_h, body))
}
#let draw_total_grid(gp) = {
  let tot_cols = gp.lc + gp.cc + gp.rc
  let tot_rows = gp.lr + gp.cr + gp.br
  // vertical lines
  for col in range(1, tot_cols + 1) {
    place(line(start: (sum_cols(1, col - 1, gp), 0mm), end: (sum_cols(1, col - 1, gp), sum_rows(1, tot_rows, gp)), stroke: 0.5pt + rgb("#ccc")))
  }
  // horizontal lines
  for row in range(1, tot_rows + 1) {
    place(line(start: (0mm, sum_rows(1, row - 1, gp)), end: (sum_cols(1, tot_cols, gp), sum_rows(1, row - 1, gp)), stroke: 0.5pt + rgb("#ccc")))
  }
  // total column labels on top (include margin tracks)
  for col in range(1, tot_cols + 1) {
    place(dx: sum_cols(1, col - 1, gp) + 2pt, dy: 2pt, text(size: 8pt, fill: rgb("#888"))[#col])
  }
  // total row labels on left (lowercase, include margin tracks)
  let letters = ("a","b","c","d","e","f","g","h","i","j","k","l","m","n","o","p","q","r","s","t","u","v","w","x","y","z")
  for row in range(1, tot_rows + 1) {
    let label = if row <= 26 { letters.at(row - 1) } else { str(row) }
    place(dx: 2pt, dy: sum_rows(1, row - 1, gp) + 2pt, text(size: 8pt, fill: rgb("#888"))[#label])
  }
}
""")

    # Build map of master definitions: name -> list of elements
    masters = {}
    for p in ir.get('pages', []):
        mname = (p.get('master_def') or '').strip()
        if mname:
            masters[mname] = list(p.get('elements', []))

    # Determine pages to actually render (skip pure master-def pages)
    render_pages = [p for p in ir.get('pages', []) if not (p.get('master_def') or '').strip()]

    for page_index, page in enumerate(render_pages):
        w = page['page_size']['w_mm']
        h = page['page_size']['h_mm']
        cols = page['grid']['cols']
        rows = page['grid']['rows']
        margins_mm = page.get('margins_mm')
        margins_declared = bool(page.get('margins_declared')) and isinstance(margins_mm, dict)
        # Determine total grid for debug drawing when no margins declared
        total_cols = cols + (2 if margins_declared else 0)
        total_rows = rows + (2 if margins_declared else 0)
        # Extract mm values (0 when not declared)
        top_mm = float((margins_mm or {}).get('top', 0.0))
        right_mm = float((margins_mm or {}).get('right', 0.0))
        bottom_mm = float((margins_mm or {}).get('bottom', 0.0))
        left_mm = float((margins_mm or {}).get('left', 0.0))
        out.append(f"// Page {page_index + 1}: {page['title']}\n")
        # Per-page page size not supported in Typst; set once at document top.
        if margins_declared:
            # Compute content cell sizes using page minus absolute margins
            out.append(f"#let cw = ({w}mm - ({left_mm}mm + {right_mm}mm)) / {cols}\n")
            out.append(f"#let ch = ({h}mm - ({top_mm}mm + {bottom_mm}mm)) / {rows}\n")
            # Total grid params: one margin track per side
            out.append(
                f"#let gp = (lc: 1, rc: 1, lr: 1, br: 1, cc: {cols}, cr: {rows}, lm: {left_mm}mm, rm: {right_mm}mm, tm: {top_mm}mm, bm: {bottom_mm}mm, cw: cw, ch: ch)\n"
            )
        else:
            # No margins: total grid equals content grid; tracks are uniform
            out.append(f"#let cw = {w}mm / {cols}\n#let ch = {h}mm / {rows}\n")
            out.append(
                f"#let gp = (lc: 0, rc: 0, lr: 0, br: 0, cc: {cols}, cr: {rows}, lm: 0mm, rm: 0mm, tm: 0mm, bm: 0mm, cw: cw, ch: ch)\n"
            )
        out.append("// BEGIN PAGE CONTENT\n")
        # Combine master elements (if any) with page elements
        combined_elements = []
        mref = (page.get('master') or '').strip()
        if not mref and (ir.get('meta') or {}).get('DEFAULT_MASTER'):
            mref = (ir['meta'].get('DEFAULT_MASTER') or '').strip()
        if mref and mref in masters:
            combined_elements.extend(masters[mref])
        combined_elements.extend(page.get('elements', []))
        elements = sorted(combined_elements, key=lambda e: e.get('z', 100))
        seen_area_warnings = set()
        for el in elements:
            area = el['area'] or {'x': 1, 'y': 1, 'w': cols, 'h': 1}
            x, y, wc, hc = area['x'], area['y'], area['w'], area['h']
            # Always interpret AREA in total grid coordinates.
            x_total = x
            y_total = y
            # Validate bounds against total grid when margins exist, else content grid.
            limit_cols = total_cols if margins_declared else cols
            limit_rows = total_rows if margins_declared else rows
            out_of_bounds = (
                x < 1
                or y < 1
                or wc < 1
                or hc < 1
                or (x + wc - 1) > limit_cols
                or (y + hc - 1) > limit_rows
            )
            if out_of_bounds:
                warn_key = (el.get('id'), x, y, wc, hc)
                if warn_key not in seen_area_warnings:
                    seen_area_warnings.add(warn_key)
                    print(
                        f"WARNING: AREA out-of-bounds for element {el['id']} on page {page['title']}: ({x},{y},{wc},{hc})",
                        file=sys.stderr,
                    )
            content_fragments = []
            pre_comments = []
            if el['type'] in ('header', 'subheader', 'body'):
                content_fragments.append(_render_text_element(el, styles))
            elif el['type'] == 'rectangle' and el.get('rectangle'):
                rect = el['rectangle']
                color = rect['color']
                alpha = rect.get('alpha', 1.0)
                content_fragments.append(f"ColorRect(\"{color}\", {alpha})")
            elif el['type'] == 'figure' and el.get('figure'):
                src = el['figure']['src']
                cap = el['figure'].get('caption')
                fit = el['figure'].get('fit', 'contain')
                align, _ = _get_alignment_wrapper(el)
                align = align or 'left'  # Default to left for figures
                fit_map = {
                    'fill': 'cover',
                    'contain': 'contain',
                    'cover': 'cover',
                    'stretch': 'stretch',
                }
                fit_val = fit_map.get(str(fit).lower(), str(fit))
                # For contain fit with alignment, use different approach
                if fit_val == "contain" and align != "center":
                    img_call = f"image(\"{src}\")"
                else:
                    img_call = f"image(\"{src}\", width: 100%, height: 100%, fit: \"{fit_val}\")"

                if cap:
                    cap_e = escape_text(cap)
                    content_fragments.append(
                        f"Fig({img_call}, caption: [{cap_e}], caption_align: {align}, img_align: {align})"
                    )
                else:
                    content_fragments.append(
                        f"Fig({img_call}, caption_align: {align}, img_align: {align})"
                    )
            elif el['type'] == 'svg' and el.get('svg'):
                svg = el['svg']
                ssrc = svg.get('src')
                # Render SVG via image fit contain into the frame
                content_fragments.append(
                    f"Fig(image(\"{ssrc}\", width: 100%, height: 100%, fit: \"contain\"))"
                )
            elif el['type'] == 'pdf' and el.get('pdf'):
                pdf = el['pdf']
                psrc = pdf['src']
                ppage = pdf['pages'][0]
                user_scale = pdf.get('scale', 1.0) or 1.0
                # Compute auto-contain scale so PDF fits inside its frame.
                try:
                    pad_dict = el.get('padding_mm') if isinstance(el, dict) else None
                    frame_w_mm, frame_h_mm = _compute_element_frame_size_mm(page, area, pad_dict)
                    pdf_w_mm, pdf_h_mm = _pdf_intrinsic_size_mm_from_generator(psrc)
                    if pdf_w_mm <= 0 or pdf_h_mm <= 0:
                        base_scale = 1.0
                    else:
                        base_scale = min(frame_w_mm / pdf_w_mm, frame_h_mm / pdf_h_mm)
                        if base_scale <= 0 or not (base_scale == base_scale):  # NaN guard
                            base_scale = 1.0
                    # Ignore user-supplied :SCALE: for now; always use containment base_scale
                    if isinstance(user_scale, (int, float)) and abs(float(user_scale) - 1.0) > 1e-6:
                        warnings.warn(
                            f":SCALE: {user_scale} specified for PDF '{psrc}' is currently ignored (auto-contain scaling enforced).",
                            UserWarning,
                        )
                    final_scale = base_scale
                    scale_numeric = float(f"{final_scale:.6f}")
                except Exception:
                    scale_numeric = (
                        float(user_scale) if isinstance(user_scale, (int, float)) else 1.0
                    )
                if pathlib.Path(psrc).suffix.lower() != '.pdf':
                    content_fragments.append(
                        f"Fig(image(\"{psrc}\", width: 100%, height: 100%, fit: \"contain\"))"
                    )
                else:
                    scale_mode = (pdf.get('scale_mode') or 'contain').strip().lower()
                    if scale_mode not in ('contain', 'cover'):
                        scale_mode = 'contain'
                    # For cover, recompute scale to fill and possibly crop
                    if scale_mode == 'cover':
                        try:
                            pad_dict = el.get('padding_mm') if isinstance(el, dict) else None
                            frame_w_mm, frame_h_mm = _compute_element_frame_size_mm(
                                page, area, pad_dict
                            )
                            pdf_w_mm, pdf_h_mm = _pdf_intrinsic_size_mm_from_generator(psrc)
                            if pdf_w_mm > 0 and pdf_h_mm > 0:
                                cover_scale = max(frame_w_mm / pdf_w_mm, frame_h_mm / pdf_h_mm)
                                scale_numeric = float(f"{cover_scale:.6f}")
                        except Exception:
                            pass
                    mode_comment = "contain" if scale_mode == 'contain' else 'cover (may crop)'
                    # Add comment separate from expression to avoid syntax issues inside layer_grid_padded
                    pre_comments.append(f"// auto pdf scale base {mode_comment} applied")
                    content_fragments.append(
                        f"PdfEmbed(\"{psrc}\", page: {ppage}, scale: {scale_numeric})"
                    )
            elif el['type'] == 'toc':
                # TOC with page numbers and dot leaders
                toc_entries = []
                page_counter = 1
                for rp in render_pages:
                    # Skip pages marked with TOC_IGNORE
                    if parse_bool(rp.get('props', {}).get('TOC_IGNORE')):
                        page_counter += 1
                        continue
                    title = escape_text(rp.get('title', ''))
                    toc_entries.append(_typst_grid_toc_entry(title, page_counter))
                    page_counter += 1
                if toc_entries:
                    toc_content = "\n".join(toc_entries)
                    content_fragments.append(f"[{toc_content}]")
                else:
                    content_fragments.append("[#text(font: \"Inter\")[No pages to display]]")
            frag = ' + '.join(content_fragments) if content_fragments else '""'
            # Apply ALIGN/VALIGN wrappers if present using helper functions
            wrapped = frag
            align, valign = _get_alignment_wrapper(el)

            # Handle FLOW as vertical alignment fallback
            flow = (
                (el.get('flow') or '').strip().lower() if isinstance(el.get('flow'), str) else None
            )
            if not valign and flow:
                if flow == 'bottom-up':
                    valign = 'bottom'
                elif flow == 'center-out':
                    valign = 'horizon'

            wrapped = _apply_alignment_wrapper(wrapped, align, valign)
            # Emit any pre-comments collected (e.g., pdf scaling mode)
            for c in pre_comments:
                out.append(f"{c}\n")
            out.append(f"// Element {el['id']} ({el['type']})\n")
            # Emit flow hint comment when provided
            if flow:
                out.append(f"// FLOW: {flow}\n")
            # Handle padding-only placement (element-level margins deprecated)
            pad = el.get('padding_mm') if isinstance(el, dict) else None
            arg = wrapped
            sarg = str(arg).lstrip()
            # Wrap all content expressions in brackets, except standalone function calls like Fig(...) or ColorRect(...)
            if not (
                sarg
                and not sarg.startswith('#')
                and '(' in sarg
                and sarg.count('(') == sarg.count(')')
            ):
                arg = f"[{arg}]"
            # Place elements with padding when specified (text, figure, svg, pdf, rectangle, toc)
            if el.get('type') in (
                'header',
                'subheader',
                'body',
                'figure',
                'svg',
                'pdf',
                'rectangle',
                'toc',
            ) and isinstance(pad, dict):
                t = float(pad.get('top', 0.0))
                r = float(pad.get('right', 0.0))
                b = float(pad.get('bottom', 0.0))
                left = float(pad.get('left', 0.0))
                out.append(
                    f"#layer_grid_padded(gp,{x_total},{y_total},{wc},{hc}, {t}mm, {r}mm, {b}mm, {left}mm, {arg})\n"
                )
            else:
                out.append(f"#layer_grid(gp,{x_total},{y_total},{wc},{hc}, {arg})\n")
        if ir['meta'].get('GRID_DEBUG', 'false').lower() == 'true':
            if margins_declared:
                out.append("#draw_total_grid(gp)\n")
            else:
                out.append(f"#draw_grid({cols}, {rows}, cw, ch)\n")
        out.append("// END PAGE CONTENT\n")
        if page_index < len(render_pages) - 1:
            out.append("#pagebreak()\n")
        out.append("\n")
    return '\n'.join(out)


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
    links = []

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


_pdf_size_cache = {}


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


def _discover_available_fonts() -> dict:
    """Wrapper for backward compatibility. Font discovery has been moved to core.py."""
    from .generation.core import discover_available_fonts

    return discover_available_fonts()


def _validate_font_availability(styles: dict, available_fonts: dict) -> list:
    """Wrapper for backward compatibility. Font validation has been moved to core.py."""
    from .generation.core import validate_font_availability

    return validate_font_availability(styles, available_fonts)


def update_html_total(html_path: pathlib.Path, total: int):
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


# =============================================================================
# WRAPPERS FOR EXTRACTED FUNCTIONS (Stage 3.4 - PDF Processing)
# =============================================================================


def _pdf_intrinsic_size_mm_from_generator(path: str) -> tuple[float, float]:
    """Wrapper for pdf_intrinsic_size_mm from generation.pdf_processor."""
    from .generation.pdf_processor import pdf_intrinsic_size_mm

    return pdf_intrinsic_size_mm(path)


def adjust_asset_paths_from_generator(ir, typst_dir):
    """Wrapper for adjust_asset_paths from generation.pdf_processor."""
    from .generation.pdf_processor import adjust_asset_paths

    return adjust_asset_paths(ir, typst_dir)


# =============================================================================
# WRAPPERS FOR EXTRACTED FUNCTIONS (Stage 3.5 - Core/Style Processing)
# =============================================================================


def _build_styles_from_generator(meta: dict) -> dict:
    """Wrapper for build_styles from generation.core."""
    from .generation.core import build_styles

    return build_styles(meta)


def _style_args_from_generator(style: dict) -> str:
    """Wrapper for style_args from generation.core."""
    from .generation.core import style_args

    return style_args(style)


def _par_args_from_generator(style: dict, justify_override: object) -> str:
    """Wrapper for par_args from generation.core."""
    from .generation.core import par_args

    return par_args(style, justify_override)


def _parse_style_decl_from_generator(s: str) -> dict:
    """Wrapper for parse_style_decl from generation.core."""
    from .generation.core import parse_style_decl

    return parse_style_decl(s)
