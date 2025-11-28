"""
HTML export generation (formerly story mode).

This module generates standalone HTML files with CSS Grid layouts that mirror
PDF grid positioning. Each page becomes a full-viewport section with precise
element positioning using CSS Grid.
"""

import datetime
import html
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .constants import FONT_WEIGHT_MAP, BlockType, FitMode, ListType, StyleName, TextBlockKind
from .story_auto_placement import area_to_css_grid, compute_auto_placement


def _find_webfonts(font_families: Set[str], font_paths: List[str]) -> List[Dict[str, Any]]:
    """Find WOFF2 files for given font families.

    Args:
        font_families: Set of font family names (e.g., {'Inter', 'Crimson Pro'})
        font_paths: List of font search paths from _get_font_paths()

    Returns:
        List of webfont dicts:
        [
            {
                'family': 'Inter',
                'weight': 400,
                'style': 'normal',
                'path': 'assets/fonts/Inter/Inter-400-normal.woff2',
                'filename': 'Inter-400-normal.woff2'
            },
            ...
        ]
    """
    webfonts = []

    for font_path_str in font_paths:
        font_path = Path(font_path_str)
        if not font_path.exists():
            continue

        for family in font_families:
            # Check both "Font Name" and "Font_Name" variants
            family_variants = [family, family.replace(' ', '_'), family.replace('_', ' ')]

            for variant in family_variants:
                family_dir = font_path / variant
                if family_dir.exists():
                    # Find all WOFF2 files
                    for woff2_file in family_dir.glob('*.woff2'):
                        # Parse filename: Inter-400-normal.woff2
                        name = woff2_file.stem  # "Inter-400-normal"
                        parts = name.rsplit('-', 2)
                        if len(parts) == 3:
                            _, weight_str, style = parts
                            weight = int(weight_str) if weight_str.isdigit() else 400
                            webfonts.append(
                                {
                                    'family': family,
                                    'weight': weight,
                                    'style': style,
                                    'path': str(woff2_file),
                                    'filename': woff2_file.name,
                                }
                            )

    return webfonts


def _generate_font_face_css(webfonts: List[Dict[str, Any]], fonts_dir: str = 'fonts') -> str:
    """Generate @font-face CSS rules for web fonts.

    Args:
        webfonts: List of webfont dicts from _find_webfonts()
        fonts_dir: Relative path to fonts directory from HTML file

    Returns:
        CSS string with @font-face rules
    """
    if not webfonts:
        return ''

    css_rules = []

    for font in webfonts:
        rule = f"""@font-face {{
    font-family: '{font['family']}';
    font-weight: {font['weight']};
    font-style: {font['style']};
    src: url('{fonts_dir}/{font['filename']}') format('woff2');
    font-display: swap;
}}"""
        css_rules.append(rule)

    return '\n\n'.join(css_rules)


def _copy_webfonts(webfonts: List[Dict[str, Any]], export_dir: Path) -> None:
    """Copy WOFF2 files to export directory.

    Args:
        webfonts: List of webfont dicts from _find_webfonts()
        export_dir: Export directory (where HTML file will be written)
    """
    if not webfonts:
        return

    fonts_export_dir = export_dir / 'fonts'
    fonts_export_dir.mkdir(parents=True, exist_ok=True)

    for font in webfonts:
        src = Path(font['path'])
        dst = fonts_export_dir / font['filename']

        if src.exists():
            shutil.copy2(src, dst)


def _collect_asset_paths(ir: Dict[str, Any]) -> Set[str]:
    """Collect all asset paths referenced in the IR."""
    paths = set()

    pages = ir.get('pages', [])
    for page in pages:
        # Check for page background
        page_props = page.get('props', {})
        background_src = page_props.get('BACKGROUND', '')
        if background_src and not background_src.startswith(('http://', 'https://', 'data:')):
            paths.add(background_src)

        elements = page.get('elements', [])
        for element in elements:
            # Check for figure
            figure_data = element.get('figure')
            if figure_data:
                if isinstance(figure_data, dict):
                    src = figure_data.get('src', '')
                else:
                    src = str(figure_data) if figure_data else ''
                if src and not src.startswith(('http://', 'https://', 'data:')):
                    paths.add(src)

            # Check for SVG
            svg_data = element.get('svg')
            if svg_data:
                if isinstance(svg_data, dict):
                    src = svg_data.get('src', '')
                else:
                    src = str(svg_data) if svg_data else ''
                if src and not src.startswith(('http://', 'https://', 'data:')):
                    paths.add(src)

            # Check for PDF
            pdf_data = element.get('pdf')
            if pdf_data:
                if isinstance(pdf_data, dict):
                    src = pdf_data.get('src', '')
                else:
                    src = str(pdf_data) if pdf_data else ''
                if src and not src.startswith(('http://', 'https://', 'data:')):
                    paths.add(src)

    return paths


def _copy_assets(ir: Dict[str, Any], output_dir: Path, source_dir: Path) -> Dict[str, str]:
    """
    Copy all referenced assets to output/assets/ directory.

    Returns a mapping from original path -> new relative path (e.g., 'assets/forest.jpg')
    """
    assets_mapping = {}
    assets_output_dir = output_dir / 'assets'
    assets_output_dir.mkdir(parents=True, exist_ok=True)

    # Collect all asset paths from IR
    asset_paths = _collect_asset_paths(ir)

    # Track used filenames to handle collisions
    used_filenames = set()

    for original_path in asset_paths:
        # Resolve the source file path
        src_path = source_dir / original_path

        if not src_path.exists():
            continue

        # Validate path doesn't escape source directory (security)
        try:
            resolved_src = src_path.resolve()
            resolved_source_dir = source_dir.resolve()
            if not str(resolved_src).startswith(str(resolved_source_dir)):
                print(f"Warning: Skipping asset outside source directory: {original_path}")
                continue
        except Exception:
            print(f"Warning: Could not resolve asset path: {original_path}")
            continue

        # Generate unique filename to avoid collisions
        base_filename = src_path.name
        dest_filename = base_filename
        counter = 1

        # If filename already used, append counter
        while dest_filename in used_filenames:
            stem = src_path.stem
            suffix = src_path.suffix
            dest_filename = f"{stem}_{counter}{suffix}"
            counter += 1

        used_filenames.add(dest_filename)
        dest_path = assets_output_dir / dest_filename

        # Copy the file
        try:
            shutil.copy2(src_path, dest_path)
            # Store mapping: original -> new relative path
            assets_mapping[original_path] = f'assets/{dest_filename}'
        except Exception as e:
            # If copy fails, keep original path
            print(f"Warning: Could not copy asset {original_path}: {e}")

    return assets_mapping


def generate_story_html(
    ir: Dict[str, Any],
    output_path: str,
    source_file: Optional[str] = None,
    separate_assets: bool = False,
) -> None:
    """
    Generate a single standalone HTML file with grid-faithful layout.

    Each page becomes a <section> with:
    - Full viewport height
    - CSS Grid container mirroring PDF grid
    - Web fonts matching PDF typography
    - Precise element positioning

    Args:
        ir: Intermediate representation from parser
        output_path: Path to output HTML file (e.g., 'output/index.html')
        source_file: Path to source .org file (used to resolve relative asset paths)
        separate_assets: If True, generate separate CSS/JS files; if False, inline (default)
    """
    # Parse grid declaration from document metadata
    meta = ir.get('meta', {})
    grid_str = meta.get('GRID', '12x12')

    try:
        cols, rows = (int(x) for x in grid_str.lower().split('x'))
    except Exception:
        cols, rows = 12, 12

    # Default grid for scenes
    default_grid = {'cols': cols, 'rows': rows}

    # Collect all asset paths and copy them
    output_file = Path(output_path)
    source_dir = Path(source_file).parent if source_file else Path.cwd()
    assets_copied = _copy_assets(ir, output_file.parent, source_dir)

    # Collect and copy web fonts
    try:
        from ..fonts import _get_font_paths, analyze_font_usage

        # Analyze which fonts are used
        font_usage = analyze_font_usage(ir)
        font_families = font_usage.get('fonts_found', set())

        # Get font search paths
        font_paths = _get_font_paths()

        # Find web fonts
        webfonts = _find_webfonts(font_families, font_paths)

        # Copy web fonts to export directory
        _copy_webfonts(webfonts, output_file.parent)

        print(f"  📦 Web fonts: {len(webfonts)} variants from {len(font_families)} families")
    except ImportError as e:
        print(f"  ⚠️  Font utilities not available: {e}")
        webfonts = []
    except OSError as e:
        print(f"  ⚠️  Font file operation failed: {e}")
        webfonts = []
    except (KeyError, ValueError, TypeError) as e:
        print(f"  ⚠️  Font data parsing error: {e}")
        webfonts = []

    # Generate HTML structure (with updated asset paths and web fonts)
    html_content = _generate_html_structure(
        ir, default_grid, assets_copied, output_file.parent, separate_assets, webfonts
    )

    # Write to output file
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)


def _generate_html_structure(
    ir: Dict[str, Any],
    default_grid: Dict[str, int],
    assets_mapping: Dict[str, str],
    output_dir: Path,
    separate_assets: bool = False,
    webfonts: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Generate complete HTML document structure."""
    meta = ir.get('meta', {})
    title = meta.get('TITLE', 'Story')

    webfonts = webfonts or []

    sections_html = _generate_sections(ir, default_grid, assets_mapping)

    # Generate web font CSS
    font_face_css = _generate_font_face_css(webfonts, fonts_dir='fonts')

    # Parse IR styles and generate typography CSS (use build_styles from core)
    from .core import build_styles

    styles = build_styles(meta)
    typography_css = _generate_typography_css(styles)

    # Generate main CSS (with web fonts and typography prepended)
    base_css = _generate_css()
    css_parts = [font_face_css, typography_css, base_css]
    css = '\n\n'.join(part for part in css_parts if part)

    js = _generate_js()

    if separate_assets:
        # Write separate CSS and JS files
        css_filename = 'story.css'
        js_filename = 'story.js'

        css_path = output_dir / css_filename
        js_path = output_dir / js_filename

        css_path.write_text(css, encoding='utf-8')
        js_path.write_text(js, encoding='utf-8')

        # Generate HTML with external references
        html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <link rel="stylesheet" href="{html.escape(css_filename)}">
</head>
<body>
    <main class="story-container">
{sections_html}
    </main>
    <script src="{html.escape(js_filename)}"></script>
</body>
</html>"""
    else:
        # Generate HTML with inline CSS/JS (default, backward compatible)
        html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
{css}
    </style>
</head>
<body>
    <main class="story-container">
{sections_html}
    </main>
    <script>
{js}
    </script>
</body>
</html>"""

    return html_doc


def _generate_sections(
    ir: Dict[str, Any], default_grid: Dict[str, int], assets_mapping: Dict[str, str]
) -> str:
    """Generate HTML sections for each scene."""
    pages = ir.get('pages', [])
    sections = []

    for idx, page in enumerate(pages):
        # Skip master definition pages
        if page.get('master_def'):
            continue

        # Get grid for this scene (inherit from document if not specified)
        page_grid = page.get('grid', default_grid)
        grid_cols = page_grid.get('cols', default_grid['cols'])
        grid_rows = page_grid.get('rows', default_grid['rows'])

        # Check for background image
        page_props = page.get('props', {})
        background_src = page_props.get('BACKGROUND', '')
        background_style = ''

        if background_src:
            # Map to copied asset path
            bg_src = assets_mapping.get(background_src, background_src)
            # Escape background URL properly for HTML attribute
            bg_src_safe = str(bg_src).replace("'", "\\'").replace('"', '&quot;')
            background_style = f' style="--grid-cols: {grid_cols}; --grid-rows: {grid_rows}; background-image: url(&quot;{bg_src_safe}&quot;); background-size: cover; background-position: center;"'
        else:
            background_style = f' style="--grid-cols: {grid_cols}; --grid-rows: {grid_rows};"'

        # Get blocks (elements) for this scene
        blocks = page.get('elements', [])

        # Apply auto-placement
        placed_blocks = compute_auto_placement(blocks, grid_cols, grid_rows)

        # Generate section HTML
        scene_title = page.get('title', f'Scene {idx + 1}')
        scene_id = page.get('id', f'scene-{idx + 1}')

        section_html = f"""    <section class="scene" id="{html.escape(scene_id)}" data-scene="{idx + 1}"{background_style}>
        <div class="grid-container">
{_generate_blocks_html(placed_blocks, grid_cols, grid_rows, assets_mapping)}
        </div>
    </section>"""

        sections.append(section_html)

    return '\n'.join(sections)


def _generate_blocks_html(
    blocks: List[Dict], grid_cols: int, grid_rows: int, assets_mapping: Dict[str, str]
) -> str:
    """Generate HTML for blocks within a scene."""
    block_htmls = []

    for block in blocks:
        area = block.get('area')
        if not area:
            continue  # Skip blocks without area (shouldn't happen after auto-placement)

        # Convert area to CSS grid-area
        grid_area = area_to_css_grid(area)

        block_type = block.get('type', 'body')
        block_id = block.get('id', '')

        # Check for custom style (already parsed by parser into 'style' field)
        custom_style = block.get('style', '')

        # Build style attribute with grid-area
        style_parts = [f'grid-area: {grid_area}']

        # Add padding from element properties (padding_mm from IR)
        padding_mm = block.get('padding_mm')
        if padding_mm and isinstance(padding_mm, dict):
            top = padding_mm.get('top', 0)
            right = padding_mm.get('right', 0)
            bottom = padding_mm.get('bottom', 0)
            left = padding_mm.get('left', 0)

            # Only add padding if at least one value is non-zero
            if top != 0 or right != 0 or bottom != 0 or left != 0:
                style_parts.append(f'padding: {top}mm {right}mm {bottom}mm {left}mm')

        style_attr = '; '.join(style_parts)

        # Build data attributes
        data_attrs = f'data-block-id="{html.escape(block_id)}"'
        if custom_style:
            # Add data-style attribute for custom CSS selector
            data_attrs += f' data-style="{html.escape(custom_style)}"'

        # Generate block content based on type
        content_html = _generate_block_content(block, assets_mapping)

        block_html = f"""            <div class="block block-{block_type}" {data_attrs} style="{style_attr}">
{content_html}
            </div>"""

        block_htmls.append(block_html)

    return '\n'.join(block_htmls)


def _extract_plain_text(text_blocks: List[Dict[str, Any]], fallback: str = '') -> str:
    """Extract plain text content from text_blocks.

    Args:
        text_blocks: List of text block dicts with 'kind' and 'content' keys
        fallback: Default text if no plain blocks found

    Returns:
        Concatenated plain text content or fallback
    """
    content_parts = []
    for tb in text_blocks:
        if tb.get('kind') == TextBlockKind.PLAIN:
            content = tb.get('content', '')
            if content:
                content_parts.append(content)

    return ' '.join(content_parts) if content_parts else fallback


def _generate_block_content(block: Dict[str, Any], assets_mapping: Dict[str, str]) -> str:
    """Generate HTML content for a single block based on its type."""
    block_type = block.get('type', BlockType.BODY)

    if block_type == BlockType.HEADER:
        text_blocks = block.get('text_blocks', [])
        header_text = _extract_plain_text(text_blocks, fallback=block.get('title', ''))
        return f'                <h1>{html.escape(header_text)}</h1>'

    elif block_type == BlockType.SUBHEADER:
        text_blocks = block.get('text_blocks', [])
        header_text = _extract_plain_text(text_blocks, fallback=block.get('title', ''))
        return f'                <h2>{html.escape(header_text)}</h2>'

    elif block_type == BlockType.BODY:
        # Render text blocks (plain text, lists, tables)
        return _generate_text_blocks_html(block)

    elif block_type == BlockType.FIGURE:
        return _generate_figure_html(block, assets_mapping)

    elif block_type == BlockType.SVG:
        return _generate_svg_html(block, assets_mapping)

    elif block_type == BlockType.PDF:
        return _generate_pdf_html(block, assets_mapping)

    elif block_type == BlockType.RECTANGLE:
        return _generate_rectangle_html(block)

    else:
        # Unknown type
        return f'                <div class="unknown-type">Type: {html.escape(block_type)}</div>'


def _generate_text_blocks_html(block: Dict[str, Any]) -> str:
    """Generate HTML for text blocks (paragraphs, lists, tables)."""
    text_blocks = block.get('text_blocks', [])
    if not text_blocks:
        return ''

    parts = []

    for tb in text_blocks:
        kind = tb.get('kind')

        if kind == TextBlockKind.PLAIN:
            content = tb.get('content', '')
            if content.strip():
                parts.append(f'                <p>{html.escape(content)}</p>')

        elif kind == TextBlockKind.LIST:
            list_html = _generate_list_html(tb)
            if list_html:
                parts.append(list_html)

        elif kind == TextBlockKind.TABLE:
            table_html = _generate_table_html(tb)
            if table_html:
                parts.append(table_html)

        elif kind == TextBlockKind.HARDBREAK:
            parts.append('                <br>')

    return '\n'.join(parts)


def _generate_list_html(list_block: Dict[str, Any]) -> str:
    """Generate HTML for list blocks."""
    list_type = list_block.get('type', ListType.UNORDERED)
    items = list_block.get('items', [])

    if not items:
        return ''

    # Determine HTML tag
    if list_type == ListType.ORDERED:
        tag = 'ol'
    elif list_type == ListType.DESCRIPTION:
        # Description list
        parts = ['                <dl>']
        for item in items:
            term = item.get('term', '')
            desc = item.get('description', '')
            parts.append(f'                    <dt>{html.escape(term)}</dt>')
            parts.append(f'                    <dd>{html.escape(desc)}</dd>')
        parts.append('                </dl>')
        return '\n'.join(parts)
    else:
        tag = 'ul'

    # Regular list (ul/ol)
    parts = [f'                <{tag}>']
    for item in items:
        item_text = item.get('text', '')
        checkbox = item.get('checkbox')

        if checkbox:
            # Render checkbox
            checked_attr = 'checked' if checkbox == 'checked' else ''
            parts.append(
                f'                    <li><input type="checkbox" {checked_attr} disabled> {html.escape(item_text)}</li>'
            )
        else:
            parts.append(f'                    <li>{html.escape(item_text)}</li>')

    parts.append(f'                </{tag}>')
    return '\n'.join(parts)


def _generate_table_html(table_block: Dict[str, Any]) -> str:
    """Generate HTML for table blocks."""
    rows = table_block.get('rows', [])
    header_rows = table_block.get('header_rows', 0)

    if not rows:
        return ''

    # Filter out separator rows (rows with only dashes/spaces)
    def is_separator_row(row):
        """Check if a row is a separator line (only dashes, spaces, pipes, colons, plus)."""
        for cell in row:
            cell_str = str(cell).strip()
            if cell_str and not all(c in '-+: ' for c in cell_str):
                return False
        return True

    filtered_rows = [row for row in rows if not is_separator_row(row)]

    if not filtered_rows:
        return ''

    # If header_rows is 0 but we have filtered rows, assume first row is header
    # (common org-mode convention when separator is present)
    if header_rows == 0 and len(filtered_rows) > 1:
        # Check if original rows had a separator after first row
        if len(rows) > 1 and is_separator_row(rows[1]):
            header_rows = 1

    parts = ['                <table>']

    # Generate table header if header rows exist
    if header_rows > 0:
        parts.append('                    <thead>')
        for row in filtered_rows[:header_rows]:
            row_html = '                        <tr>'
            for cell in row:
                row_html += f'<th>{html.escape(str(cell))}</th>'
            row_html += '</tr>'
            parts.append(row_html)
        parts.append('                    </thead>')

    # Generate table body
    parts.append('                    <tbody>')
    for row in filtered_rows[header_rows:]:
        row_html = '                        <tr>'
        for cell in row:
            row_html += f'<td>{html.escape(str(cell))}</td>'
        row_html += '</tr>'
        parts.append(row_html)
    parts.append('                    </tbody>')

    parts.append('                </table>')
    return '\n'.join(parts)


def _generate_figure_html(block: Dict[str, Any], assets_mapping: Dict[str, str]) -> str:
    """Generate HTML for figure/image blocks."""
    figure_data = block.get('figure', {})

    if isinstance(figure_data, dict):
        src = figure_data.get('src', '')
        caption = figure_data.get('caption', '')
        fit = figure_data.get('fit', FitMode.CONTAIN)
    else:
        src = str(figure_data) if figure_data else ''
        caption = ''
        fit = FitMode.CONTAIN

    if not src:
        return ''

    # Replace with copied asset path if available
    src = assets_mapping.get(src, src)

    # Convert fit mode to CSS object-fit
    # Typst fit modes: contain, cover, stretch (fit-to-width/height)
    # CSS object-fit: contain, cover, fill, scale-down, none
    object_fit = 'contain'  # default
    if fit == FitMode.COVER:
        object_fit = 'cover'
    elif fit == FitMode.STRETCH:
        object_fit = 'fill'
    elif fit == FitMode.CONTAIN:
        object_fit = 'contain'

    parts = ['                <figure>']
    parts.append(
        f'                    <img src="{html.escape(src)}" alt="{html.escape(caption or "")}" style="width: 100%; height: 100%; object-fit: {object_fit};">'
    )

    if caption:
        parts.append(f'                    <figcaption>{html.escape(caption)}</figcaption>')

    parts.append('                </figure>')
    return '\n'.join(parts)


def _generate_svg_html(block: Dict[str, Any], assets_mapping: Dict[str, str]) -> str:
    """Generate HTML for SVG blocks."""
    svg_data = block.get('svg', {})

    if isinstance(svg_data, dict):
        src = svg_data.get('src', '')
        caption = svg_data.get('caption', '')
        fit = svg_data.get('fit', FitMode.CONTAIN)
    else:
        src = str(svg_data) if svg_data else ''
        caption = ''
        fit = FitMode.CONTAIN

    if not src:
        return ''

    # Replace with copied asset path if available
    src = assets_mapping.get(src, src)

    # Convert fit mode to CSS object-fit
    object_fit = 'contain'  # default
    if fit == FitMode.COVER:
        object_fit = 'cover'
    elif fit == FitMode.STRETCH:
        object_fit = 'fill'
    elif fit == FitMode.CONTAIN:
        object_fit = 'contain'

    # For SVGs, we can embed them directly or use <img>
    parts = ['                <figure>']
    parts.append(
        f'                    <img src="{html.escape(src)}" alt="{html.escape(caption or "")}" style="width: 100%; height: 100%; object-fit: {object_fit};">'
    )

    if caption:
        parts.append(f'                    <figcaption>{html.escape(caption)}</figcaption>')

    parts.append('                </figure>')
    return '\n'.join(parts)


def _generate_pdf_html(block: Dict[str, Any], assets_mapping: Dict[str, str]) -> str:
    """Generate HTML for embedded PDF blocks."""
    pdf_data = block.get('pdf', {})

    if isinstance(pdf_data, dict):
        src = pdf_data.get('src', '')
        caption = pdf_data.get('caption', '')
    else:
        src = str(pdf_data) if pdf_data else ''
        caption = ''

    if not src:
        return ''

    # Replace with copied asset path if available
    src = assets_mapping.get(src, src)

    # Embed PDF using iframe or object
    parts = ['                <figure>']
    parts.append(
        f'                    <embed src="{html.escape(src)}" type="application/pdf" width="100%" height="100%">'
    )

    if caption:
        parts.append(f'                    <figcaption>{html.escape(caption)}</figcaption>')

    parts.append('                </figure>')
    return '\n'.join(parts)


def _generate_rectangle_html(block: Dict[str, Any]) -> str:
    """Generate HTML for decorative rectangle blocks."""
    rect_data = block.get('rectangle', {})

    # Extract color
    color = rect_data.get('color', '#cccccc')

    # Generate a colored div
    return f'                <div class="rectangle" style="background-color: {html.escape(color)}; width: 100%; height: 100%;"></div>'


def _convert_typst_unit_to_css(value: str) -> str:
    """Convert Typst units to CSS units.

    Typst uses: mm, cm, pt, em, etc.
    CSS uses: mm, cm, pt, em, rem, px, etc.

    Most units are compatible, but we may need conversions.
    For now, pass through directly (mm, pt, em work in both).
    """
    if not value:
        return value

    # Strip whitespace
    value = value.strip()

    # Pass through directly (Typst and CSS share most units)
    # Common units: mm, cm, pt, em, rem, px
    return value


def _generate_typography_css(styles: Dict[str, Dict]) -> str:
    """Generate CSS rules from parsed IR styles.

    Args:
        styles: Dict of style definitions from build_styles()

    Returns:
        CSS string with typography rules for each style
    """
    css_rules = []

    for style_name, style_props in styles.items():
        # Map style name to CSS class using constants
        if style_name == StyleName.HEADER:
            selector = '.block-header h1'
        elif style_name == StyleName.SUBHEADER:
            selector = '.block-subheader h2'
        elif style_name == StyleName.BODY:
            selector = '.block-body'
        else:
            # Custom styles use data attribute
            selector = f'.block[data-style="{style_name}"]'

        properties = []

        # Font family
        if 'font' in style_props:
            font_family = style_props['font']
            properties.append(f'    font-family: "{font_family}", serif;')

        # Font size
        if 'size' in style_props:
            size = _convert_typst_unit_to_css(style_props['size'])
            properties.append(f'    font-size: {size};')

        # Font weight (use constant map)
        if 'weight' in style_props:
            weight = style_props['weight']
            weight_css = FONT_WEIGHT_MAP.get(weight.lower(), weight)
            properties.append(f'    font-weight: {weight_css};')

        # Color (fill in Typst)
        if 'color' in style_props:
            color = style_props['color']
            # Handle rgb() functions or hex colors
            if color.startswith('rgb(') or color.startswith('hsl('):
                # Convert Typst rgb(98%, 50%, 50%) to CSS rgb(98%, 50%, 50%)
                properties.append(f'    color: {color};')
            elif color.startswith('#'):
                properties.append(f'    color: {color};')
            else:
                # Assume hex-like or named color
                properties.append(f'    color: {color};')

        # Line height (leading in Typst)
        if 'leading' in style_props:
            leading = _convert_typst_unit_to_css(style_props['leading'])
            properties.append(f'    line-height: {leading};')

        # Paragraph spacing (spacing in Typst)
        if 'spacing' in style_props:
            spacing = _convert_typst_unit_to_css(style_props['spacing'])
            # In CSS, paragraph spacing is margin-bottom
            properties.append(f'    margin-bottom: {spacing};')

        # Text justification
        if 'justify' in style_props:
            justify = style_props['justify']
            if justify.lower() in ('true', '1', 'yes'):
                properties.append('    text-align: justify;')
                properties.append('    hyphens: auto;')

        # First line indent
        if 'first-line-indent' in style_props:
            indent = _convert_typst_unit_to_css(style_props['first-line-indent'])
            properties.append(f'    text-indent: {indent};')

        if properties:
            css_rule = f"{selector} {{\n" + '\n'.join(properties) + '\n}'
            css_rules.append(css_rule)

    return '\n\n'.join(css_rules)


def _generate_css() -> str:
    """Generate CSS for story mode layout and styling."""
    return """/* Reset and base styles */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    line-height: 1.6;
    color: #1b1f23;
    background: #ffffff;
    overflow-x: hidden;
    scroll-behavior: smooth;
}

/* Story container with scroll snap */
.story-container {
    scroll-snap-type: y mandatory;
    overflow-y: scroll;
    height: 100vh;
}

/* Individual scenes (full viewport sections) */
.scene {
    min-height: 100vh;
    width: 100%;
    scroll-snap-align: start;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
}

/* Alternate scene backgrounds for visual separation */
.scene:nth-child(even) {
    background: #f6f8fa;
}

.scene:nth-child(odd) {
    background: #ffffff;
}

/* Grid container within each scene */
.grid-container {
    display: grid;
    grid-template-columns: repeat(var(--grid-cols, 12), 1fr);
    grid-template-rows: repeat(var(--grid-rows, 12), 1fr);
    gap: 0;
    width: 100%;
    max-width: 1400px;
    height: 100%;
    max-height: 900px;
}

/* Individual blocks */
.block {
    position: relative;
    padding: 0;
    overflow: auto;
}

/* Block type specific styles - NO defaults, only from IR styles */
.block-header h1 {
    margin: 0;
    padding: 0;
}

.block-subheader h2 {
    margin: 0;
    padding: 0;
}

.block-body {
    /* No default font-size - use IR styles */
}

.block-body p {
    margin: 0;
    padding: 0;
}

.block-body ul,
.block-body ol {
    margin: 0;
    padding: 0;
    list-style-position: inside;
}

.block-body li {
    margin: 0;
    padding: 0;
}

/* Figures and images */
.block-figure figure,
.block-svg figure,
.block-pdf figure {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}

.block-figure img,
.block-svg img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
}

/* Note: object-fit is set inline per element based on FIT property */

figcaption {
    margin: 0;
    padding: 0;
    font-size: 0.9rem;
    color: #586069;
    text-align: center;
}

/* Tables */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 0;
    padding: 0;
}

th, td {
    border: 1px solid #d1d5da;
    padding: 0.5rem;
    text-align: left;
}

th {
    background: #f6f8fa;
    font-weight: 600;
}

/* Rectangles */
.rectangle {
    border-radius: 0;
}

/* Responsive adjustments */
@media (max-width: 768px) {
    .scene {
        padding: 0;
    }
    
    .grid-container {
        gap: 0;
    }
}"""


def _generate_js() -> str:
    """Generate JavaScript for story navigation."""
    return """// Spacebar navigation between scenes
let currentSceneIndex = 0;
const scenes = document.querySelectorAll('.scene');

document.addEventListener('keydown', (e) => {
    // Spacebar or Arrow Down: next scene
    if (e.code === 'Space' || e.code === 'ArrowDown') {
        e.preventDefault();
        if (currentSceneIndex < scenes.length - 1) {
            currentSceneIndex++;
            scenes[currentSceneIndex].scrollIntoView({ behavior: 'smooth' });
        }
    }
    
    // Arrow Up: previous scene
    if (e.code === 'ArrowUp') {
        e.preventDefault();
        if (currentSceneIndex > 0) {
            currentSceneIndex--;
            scenes[currentSceneIndex].scrollIntoView({ behavior: 'smooth' });
        }
    }
    
    // Home: first scene
    if (e.code === 'Home') {
        e.preventDefault();
        currentSceneIndex = 0;
        scenes[0].scrollIntoView({ behavior: 'smooth' });
    }
    
    // End: last scene
    if (e.code === 'End') {
        e.preventDefault();
        currentSceneIndex = scenes.length - 1;
        scenes[currentSceneIndex].scrollIntoView({ behavior: 'smooth' });
    }
});

// Track current scene on scroll
const observerOptions = {
    root: null,
    threshold: 0.5
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const sceneIndex = parseInt(entry.target.dataset.scene) - 1;
            currentSceneIndex = sceneIndex;
        }
    });
}, observerOptions);

scenes.forEach(scene => observer.observe(scene));"""


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
