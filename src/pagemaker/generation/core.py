"""Core generation module - main entry point for Typst code generation.

This module provides the main generate_typst function that orchestrates
the conversion from IR to Typst code. It coordinates with other modules
in the generation package to handle layout, element rendering, and PDF processing.
"""

import pathlib
import re
import warnings
from typing import Any, Dict, List

# Style validation constants
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


def parse_style_decl(s: str) -> dict:
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


def build_styles(meta: dict) -> dict:
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
        decl = parse_style_decl(v)
        if name in styles:
            styles[name] = {**styles[name], **decl}
        else:
            styles[name] = decl
    return styles


def style_args(style: dict) -> str:
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


def bool_token(val: str) -> str:
    """Convert value to Typst boolean token."""
    s = str(val).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return "true"
    if s in ("0", "false", "no", "n", "off"):
        return "false"
    return s  # pass-through (user may supply a Typst expression)


def par_args(style: dict, justify_override: object) -> str:
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
            parts.append(f"justify: {bool_token(vj)}")
    return ', '.join(parts)


def generate_typst(ir: Dict[str, Any]) -> str:
    """Generate Typst code from intermediate representation.

    This is the main entry point for code generation that coordinates with
    other modules in the generation package.

    Args:
        ir: The intermediate representation dictionary

    Returns:
        Generated Typst code as string
    """
    # Import required modules and constants
    import warnings

    from .. import generator

    # Get typography theme
    theme_name = ir['meta'].get('THEME', 'light')
    theme = generator.TYPOGRAPHY.get(theme_name, generator.TYPOGRAPHY['light'])

    # Build styles from document meta using local functions
    styles = build_styles(ir.get('meta') or {})

    # Discover and validate fonts using local functions
    available_fonts = discover_available_fonts()
    font_warnings = validate_font_availability(styles, available_fonts)

    # Emit font warnings if any
    for warning in font_warnings:
        warnings.warn(warning, UserWarning)

    # Generate header and setup using extracted function
    out = generate_header_and_setup(ir, theme)

    # Build map of master definitions: name -> list of elements
    masters = {}
    for p in ir.get('pages', []):
        mname = (p.get('master_def') or '').strip()
        if mname:
            masters[mname] = list(p.get('elements', []))

    # Determine pages to actually render (skip pure master-def pages)
    render_pages = [p for p in ir.get('pages', []) if not (p.get('master_def') or '').strip()]

    # Process all pages
    page_content = process_pages(ir, masters, render_pages, styles)

    # Assemble final output
    output_lines = out + page_content
    return '\n'.join(output_lines)


def _extract_page_settings(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Extract page settings from IR."""
    return {
        'pagesize': ir.get('pagesize', 'A4'),
        'orientation': ir.get('orientation', 'portrait'),
        'margins': ir.get('margins', [15, 15, 15, 15]),  # top, right, bottom, left
        'grid': ir.get('grid', [12, 16]),  # cols, rows
        'background': ir.get('background'),
    }


def _calculate_page_dimensions(pagesize: str, orientation: str) -> tuple[float, float]:
    """Calculate page dimensions in mm."""
    # Standard page sizes in mm (width, height for portrait)
    page_sizes = {
        'A4': (210, 297),
        'A3': (297, 420),
        'A5': (148, 210),
        'Letter': (216, 279),
        'Legal': (216, 356),
    }

    width, height = page_sizes.get(pagesize.upper(), (210, 297))

    if orientation.lower() == 'landscape':
        width, height = height, width

    return width, height


def _build_document_header(page_settings: Dict[str, Any]) -> List[str]:
    """Build document header with page setup."""
    lines = []

    # Add comment header
    lines.append("// Generated by pagemaker")
    lines.append("")

    # Calculate page dimensions
    width_mm, height_mm = _calculate_page_dimensions(
        page_settings['pagesize'], page_settings['orientation']
    )

    # Build page setup - simplified inline version
    margins = page_settings['margins']
    if len(margins) == 4:
        top_mm, right_mm, bottom_mm, left_mm = margins
    else:
        # Fallback to equal margins
        margin = margins[0] if margins else 15
        top_mm = right_mm = bottom_mm = left_mm = margin

    # Simple page setup
    lines.append(f"#set page(width: {width_mm}mm, height: {height_mm}mm)")
    lines.append(
        f"#set page(margin: (top: {top_mm}mm, right: {right_mm}mm, bottom: {bottom_mm}mm, left: {left_mm}mm))"
    )
    if page_settings.get('background'):
        lines.append(f"#set page(fill: {page_settings['background']})")
    lines.append("")

    return lines


def _should_show_grid(ir: Dict[str, Any]) -> bool:
    """Check if grid overlay should be shown."""
    return ir.get('debug_grid', False) or ir.get('show_grid', False)


def discover_available_fonts() -> dict:
    """Discover available fonts and map real family names to files.
    Uses fontTools to read family names from TTF/OTF/TTC/OTC. Falls back to
    directory-based heuristics when fontTools is unavailable or yields nothing.
    Returns: {family_name: [{name, path, size}, ...]}
    """
    font_families: dict[str, list[dict]] = {}

    # Resolve candidate font paths (project, examples, bundled)
    font_paths: list[str] = []
    try:
        from ..fonts import _get_font_paths  # reuse CLI resolution order

        font_paths = _get_font_paths()
    except Exception:
        # Minimal fallback paths
        for p in ('assets/fonts', 'examples/assets/fonts'):
            if pathlib.Path(p).exists():
                font_paths.append(p)

    # Try real-name discovery first (Typst-usable formats only)
    try:
        from fontTools.ttLib import TTFont
        from fontTools.ttLib.ttCollection import TTCollection

        supported_exts = {'.ttf', '.otf', '.ttc', '.otc'}

        def add_mapping(family: str, file_path: pathlib.Path):
            if not family:
                return
            info = {
                'name': file_path.name,
                'path': str(file_path),
                'size': file_path.stat().st_size if file_path.exists() else 0,
            }
            # Primary key
            font_families.setdefault(family, []).append(info)
            # Compatibility aliases (underscores/spaces)
            if '_' in family:
                font_families.setdefault(family.replace('_', ' '), []).append(info)
            if ' ' in family:
                font_families.setdefault(family.replace(' ', '_'), []).append(info)

        for root_str in font_paths:
            root = pathlib.Path(root_str)
            if not root.exists():
                continue
            for f in root.rglob('*'):
                try:
                    if not f.is_file() or f.suffix.lower() not in supported_exts:
                        continue
                    if f.suffix.lower() in {'.ttc', '.otc'}:
                        tc = TTCollection(str(f))
                        for ttf in tc.fonts:
                            nm = ttf.get('name')
                            if not nm:
                                continue
                            # Preferred Family (16) then Family (1)
                            fams = set()
                            for rec in nm.names:
                                if rec.nameID in (16, 1):
                                    try:
                                        fams.add(rec.toUnicode().strip())
                                    except Exception:
                                        pass
                            for fam in fams:
                                add_mapping(fam, f)
                    else:
                        t = TTFont(str(f), lazy=True)
                        nm = t.get('name')
                        if nm:
                            fams = set()
                            for rec in nm.names:
                                if rec.nameID in (16, 1):
                                    try:
                                        fams.add(rec.toUnicode().strip())
                                    except Exception:
                                        pass
                            for fam in fams:
                                add_mapping(fam, f)
                        try:
                            t.close()
                        except Exception:
                            pass
                except Exception:
                    # Ignore unreadable/corrupt font files
                    continue
    except Exception:
        # fontTools missing or failed; skip to heuristic fallback
        pass

    # Heuristic discovery (directory-based) to complement fontTools results
    try:
        # Prefer using fonts helper to gather files grouped by top-level dir
        from ..fonts import _discover_fonts_in_path

        def _is_probable_font(path_str: str) -> bool:
            try:
                p = pathlib.Path(path_str)
                if not p.exists() or not p.is_file():
                    return False
                # Quick header check for common font containers
                with p.open('rb') as fh:
                    header = fh.read(4)
                return header in {
                    b'\x00\x01\x00\x00',
                    b'OTTO',
                    b'ttcf',
                    b'true',
                    b'typ1',
                    b'wOFF',
                    b'wOF2',
                }
            except Exception:
                return False

        for root_str in font_paths or []:
            font_info = _discover_fonts_in_path(pathlib.Path(root_str))
            for family_name, family_data in (font_info.get('families') or {}).items():
                files = []
                for font_file in family_data.get('files', []):
                    # Skip files that clearly aren't valid font containers
                    if not _is_probable_font(font_file.get('path', '')):
                        continue
                    files.append(
                        {
                            'name': font_file['name'],
                            'path': font_file['path'],
                            'size': font_file['size'],
                        }
                    )
                if not files:
                    continue
                # Add with underscore/space aliases
                variants = {family_name}
                if '_' in family_name:
                    variants.add(family_name.replace('_', ' '))
                if ' ' in family_name:
                    variants.add(family_name.replace(' ', '_'))
                for v in variants:
                    # Merge files into existing families, avoiding duplicate paths
                    existing = font_families.setdefault(v, [])
                    existing_paths = {e['path'] for e in existing}
                    for info in files:
                        if info['path'] not in existing_paths:
                            existing.append(info)
                            existing_paths.add(info['path'])
    except Exception:
        # Final minimal heuristic over assets and examples (very approximate)
        try:

            def _is_probable_font_path(p: pathlib.Path) -> bool:
                try:
                    if not p.exists() or not p.is_file():
                        return False
                    with p.open('rb') as fh:
                        header = fh.read(4)
                    return header in {
                        b'\x00\x01\x00\x00',
                        b'OTTO',
                        b'ttcf',
                        b'true',
                        b'typ1',
                        b'wOFF',
                        b'wOF2',
                    }
                except Exception:
                    return False

            for base in ('assets/fonts', 'examples/assets/fonts'):
                base_path = pathlib.Path(base)
                if not base_path.exists():
                    continue
                for font_file in base_path.rglob('*'):
                    if not font_file.is_file():
                        continue
                    if not _is_probable_font_path(font_file):
                        continue
                    family_name = font_file.parent.name
                    info = {
                        'name': font_file.name,
                        'path': str(font_file),
                        'size': font_file.stat().st_size if font_file.exists() else 0,
                    }
                    variants = {family_name}
                    if '_' in family_name:
                        variants.add(family_name.replace('_', ' '))
                    if ' ' in family_name:
                        variants.add(family_name.replace(' ', '_'))
                    for fam in variants:
                        existing = font_families.setdefault(fam, [])
                        if all(e['path'] != info['path'] for e in existing):
                            existing.append(info)
        except Exception:
            pass

    return font_families


def validate_font_availability(styles: dict, available_fonts: dict) -> list:
    """Validate that fonts referenced in styles exist in discovered fonts.

    Returns list of warning strings for missing font families or empty families.
    """
    warnings_list: list[str] = []
    for style_name, style in (styles or {}).items():
        font = style.get('font') if isinstance(style, dict) else None
        if not font:
            continue
        if font not in available_fonts:
            warnings_list.append(
                f"Font family '{font}' referenced by style '{style_name}' not found; Typst may fallback"
            )
        elif not available_fonts.get(font):
            warnings_list.append(f"Font family '{font}' found but contains no font files")
    return warnings_list


def generate_header_and_setup(ir: Dict[str, Any], theme: dict) -> List[str]:
    """Generate complete Typst header with imports, themes, and helper functions.

    This function creates all the necessary Typst setup code including:
    - Document imports and configuration
    - Typography theme definitions and font mappings
    - Page size and orientation settings
    - Grid layout helper functions
    - Date and content formatting utilities

    Args:
        ir: Internal representation dictionary containing:
            - meta: Document metadata (page size, theme, etc.)
            - pages: Page definitions for size determination
        theme: Typography theme configuration with font families and styling

    Returns:
        List of strings containing complete Typst header content ready for compilation
    """
    import datetime

    out = []

    # Add header with timestamp
    from .. import generator

    out.append(
        generator.TYPST_HEADER.format(
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
    )
    out.append("#import \"@preview/muchpdf:0.1.1\": muchpdf\n")

    # Theme definition
    out.append("#let theme = (")
    out.append(f"  font_header: \"{theme['font_header']}\",")
    out.append(f"  font_body: \"{theme['font_body']}\",")
    out.append(f"  size_header: {theme['size_header']},")
    out.append(f"  size_subheader: {theme['size_subheader']},")
    out.append(f"  size_body: {theme['size_body']}")
    out.append(")\n")

    # Text helper functions
    out.append("#let Header(txt) = text(weight: 700, size: 24pt)[txt]\n")
    out.append("#let Subheader(txt) = text(weight: 600, size: 24pt)[txt]\n")
    out.append("#let Body(txt) = text(size: 24pt)[txt]\n")

    # Set uniform page size from first render page
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

    # Dynamic date helpers
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

    # Figure helper function
    out.append(
        "#let Fig(img, caption: none, caption_align: left, img_align: left) = if caption == none { \n  block(width: 100%, height: 100%)[#align(img_align)[#img]] \n} else { \n  block(width: 100%, height: 100%)[\n    #block(height: 85%)[#align(img_align)[#img]] \n    #block(height: 15%)[#align(caption_align)[#text(size: 0.75em, fill: rgb(60%,60%,60%), font: theme.font_body)[#caption]]] \n  ] \n}\n"
    )

    # ColorRect helper function
    out.append(
        "#let ColorRect(color, alpha) = {\n  block(width: 100%, height: 100%, fill: rgb(color).transparentize(100% - alpha * 100%))[]\n}\n"
    )

    # PDF embed helper function
    out.append(
        "#let PdfEmbed(path, page: 1, scale: 1.0) = {\n  let pdf_data = read(path, encoding: none)\n  let pg = page - 1\n  let pdf_img = muchpdf(pdf_data, pages: pg, scale: scale)\n  // Allow overflow so explicit scale can extend beyond frame intentionally\n  block(width: 100%, height: 100%)[\n    #pdf_img\n  ]\n}\n"
    )

    # Layer helpers
    out.append(
        "#let layer(cw, ch, x, y, w, h, body) = place(\n  dx: (x - 1) * cw,\n  dy: (y - 1) * ch,\n  block(\n    width: w * cw,\n    height: h * ch,\n    body\n  )\n)\n"
    )
    out.append(
        "#let layer_mm(cw, ch, left_mm, top_mm, x, y, w, h, body) = place(\n  dx: left_mm + (x - 1) * cw,\n  dy: top_mm + (y - 1) * ch,\n  block(\n    width: w * cw,\n    height: h * ch,\n    body\n  )\n)\n"
    )

    # Grid drawing functions
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

    # Variable-track grid helpers
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

    return out


def process_pages(ir, masters, render_pages, styles):
    """Process all render pages and generate their Typst content.

    Args:
        ir: Internal representation dictionary
        masters: Map of master definitions (name -> list of elements)
        render_pages: List of pages to render (excludes master-def pages)
        styles: Built styles dictionary

    Returns:
        List of strings containing page content
    """
    import pathlib
    import sys
    import warnings

    from ..generator import (
        _apply_alignment_wrapper,
        _compute_element_frame_size_mm,
        _get_alignment_wrapper,
        _pdf_intrinsic_size_mm,
        _render_text_element,
        _typst_grid_toc_entry,
        escape_text,
        parse_bool,
    )

    out = []

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
                    pdf_w_mm, pdf_h_mm = _pdf_intrinsic_size_mm(psrc)
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
                            pdf_w_mm, pdf_h_mm = _pdf_intrinsic_size_mm(psrc)
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
    return out
