"""Typst code generation utilities."""

import re
from typing import Optional


def escape_typst_text(text: str, styled_wrapper: bool = False) -> str:
    """Escape text for safe inclusion in Typst code.

    Args:
        text: The text to escape
        styled_wrapper: If True, assumes text will be wrapped in a styled container
                       and applies additional escaping for nested brackets
    """
    if not text:
        return ""

    # Basic Typst escaping
    # Escape backslashes first
    escaped = text.replace('\\', '\\\\')

    # Escape hash symbols (Typst commands)
    escaped = escaped.replace('#', '\\#')

    # Escape square brackets if in styled wrapper
    if styled_wrapper:
        escaped = escaped.replace('[', '\\[')
        escaped = escaped.replace(']', '\\]')

    # Escape other special characters
    escaped = escaped.replace('"', '\\"')
    escaped = escaped.replace('$', '\\$')

    return escaped


def build_text_args(
    font: Optional[str] = None,
    size: Optional[str] = None,
    weight: Optional[str] = None,
    style: Optional[str] = None,
    fill: Optional[str] = None,
    lang: Optional[str] = None,
    **kwargs,
) -> str:
    """Build Typst text function arguments string.

    Returns formatted argument string like: font: "Arial", size: 12pt, weight: "bold"
    """
    args = []

    if font:
        args.append(f'font: "{font}"')

    if size:
        # Ensure size has units if it's just a number
        if size.replace('.', '').isdigit():
            size = f"{size}pt"
        args.append(f'size: {size}')

    if weight:
        args.append(f'weight: "{weight}"')

    if style:
        args.append(f'style: "{style}"')

    if fill:
        args.append(f'fill: {fill}')

    if lang:
        args.append(f'lang: "{lang}"')

    # Add any additional keyword arguments
    for key, value in kwargs.items():
        if value is not None:
            if isinstance(value, str) and not value.startswith(
                ('rgb(', 'cmyk(', 'luma(', 'color.')
            ):
                args.append(f'{key}: "{value}"')
            else:
                args.append(f'{key}: {value}')

    return ', '.join(args)


def format_dimensions(width_mm: float, height_mm: float) -> str:
    """Format dimensions for Typst (width, height) tuple."""
    return f"({width_mm}mm, {height_mm}mm)"


def format_position(x_mm: float, y_mm: float) -> str:
    """Format position for Typst (x, y) tuple."""
    return f"({x_mm}mm, {y_mm}mm)"


def build_place_command(
    content: str,
    x_mm: float,
    y_mm: float,
    width_mm: Optional[float] = None,
    height_mm: Optional[float] = None,
    dx: Optional[float] = None,
    dy: Optional[float] = None,
) -> str:
    """Build Typst place command with positioning."""
    args = [f"top + {y_mm}mm", f"left + {x_mm}mm"]

    if dx is not None:
        args.append(f"dx: {dx}mm")

    if dy is not None:
        args.append(f"dy: {dy}mm")

    place_args = ", ".join(args)

    if width_mm is not None and height_mm is not None:
        content = f"#box(width: {width_mm}mm, height: {height_mm}mm)[{content}]"
    elif width_mm is not None:
        content = f"#box(width: {width_mm}mm)[{content}]"
    elif height_mm is not None:
        content = f"#box(height: {height_mm}mm)[{content}]"

    return f"#place({place_args})[{content}]"


def wrap_with_text_styling(content: str, text_args: str) -> str:
    """Wrap content with Typst text styling."""
    if not text_args:
        return content

    return f"#text({text_args})[{content}]"


def build_typst_comment(text: str) -> str:
    """Build Typst comment line."""
    return f"// {text}"


def build_page_setup(
    width_mm: float,
    height_mm: float,
    margins: tuple[float, float, float, float],  # top, right, bottom, left
    background: Optional[str] = None,
) -> str:
    """Build Typst page setup command."""
    top, right, bottom, left = margins

    args = [
        f'width: {width_mm}mm',
        f'height: {height_mm}mm',
        f'margin: (top: {top}mm, right: {right}mm, bottom: {bottom}mm, left: {left}mm)',
    ]

    if background:
        args.append(f'background: {background}')

    return f"#page({', '.join(args)})"


def normalize_typst_identifier(name: str) -> str:
    """Normalize a name to be a valid Typst identifier."""
    # Replace invalid characters with underscores
    normalized = re.sub(r'[^a-zA-Z0-9_]', '_', name)

    # Ensure it starts with a letter or underscore
    if normalized and normalized[0].isdigit():
        normalized = f"_{normalized}"

    # Remove multiple consecutive underscores
    normalized = re.sub(r'_+', '_', normalized)

    # Remove trailing underscores
    normalized = normalized.rstrip('_')

    return normalized or 'unnamed'


def build_grid_guide(
    cols: int,
    rows: int,
    page_width_mm: float,
    page_height_mm: float,
    margins: tuple[float, float, float, float],
) -> str:
    """Build Typst code for grid guide lines (debug overlay)."""
    top, right, bottom, left = margins

    usable_width = page_width_mm - left - right
    usable_height = page_height_mm - top - bottom

    cell_width = usable_width / cols
    cell_height = usable_height / rows

    lines = []

    # Vertical lines
    for i in range(cols + 1):
        x = left + i * cell_width
        lines.append(
            f"#place(top + {top}mm, left + {x}mm)["
            f"#line(length: {usable_height}mm, angle: 90deg, stroke: 0.2pt + gray)"
            f"]"
        )

    # Horizontal lines
    for i in range(rows + 1):
        y = top + i * cell_height
        lines.append(
            f"#place(top + {y}mm, left + {left}mm)["
            f"#line(length: {usable_width}mm, stroke: 0.2pt + gray)"
            f"]"
        )

    return '\n'.join(lines)


# Org-mode markup processing functions
# These handle the conversion from Org-mode syntax to Typst formatting


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


def escape_org_text(text: str, styled_wrapper: bool = False) -> str:
    """Escape text for Typst and convert org-mode markup to Typst formatting.

    This function orchestrates a pipeline of text processing steps:
    1. Escape basic Typst characters
    2. Convert Org-mode links (with placeholder protection)
    3. Convert Org-mode emphasis markup
    4. Restore protected links

    Args:
        text: Text to escape and process
        styled_wrapper: If True, uses #strong/#emph to avoid conflicts with outer #text styling
    """
    # Step 1: Escape basic Typst characters
    text = escape_typst_chars(text)

    # Step 2: Process links with protection
    text, protected_links = process_org_links(text)

    # Step 3: Process emphasis markup (links are protected)
    text = process_org_emphasis(text)

    # Step 4: Restore protected links
    text = restore_protected_links(text, protected_links)

    return text
