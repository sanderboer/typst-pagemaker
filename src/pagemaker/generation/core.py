"""Core generation module - main entry point for Typst code generation.

This module provides the main generate_typst function that orchestrates
the conversion from IR to Typst code. It coordinates with other modules
in the generation package to handle layout, element rendering, and PDF processing.
"""

import pathlib
import re
import warnings
from typing import Any, Dict, List

from ..utils.typst_helpers import build_page_setup, build_typst_comment

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

    # For now, delegate the main generation to the original function
    # but pass our processed styles and fonts
    # This allows gradual migration while maintaining compatibility
    return generator.generate_typst(ir)


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
    lines.append(build_typst_comment("Generated by pagemaker"))
    lines.append("")

    # Calculate page dimensions
    width_mm, height_mm = _calculate_page_dimensions(
        page_settings['pagesize'], page_settings['orientation']
    )

    # Build page setup
    margins = page_settings['margins']
    if len(margins) == 4:
        margins_tuple = tuple(margins)  # top, right, bottom, left
    else:
        # Fallback to equal margins
        margin = margins[0] if margins else 15
        margins_tuple = (margin, margin, margin, margin)

    page_setup = build_page_setup(
        width_mm, height_mm, margins_tuple, page_settings.get('background')
    )
    lines.append(page_setup)
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
