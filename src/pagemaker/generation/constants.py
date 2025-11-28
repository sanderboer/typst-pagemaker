"""Constants for HTML generation.

This module defines constants used throughout the HTML generation pipeline
to avoid magic strings and improve maintainability.
"""


class BlockType:
    """Element block types from IR."""

    HEADER = 'header'
    SUBHEADER = 'subheader'
    BODY = 'body'
    FIGURE = 'figure'
    SVG = 'svg'
    PDF = 'pdf'
    RECTANGLE = 'rectangle'
    TOC = 'toc'


class TextBlockKind:
    """Text block kinds within elements."""

    PLAIN = 'plain'
    LIST = 'list'
    TABLE = 'table'
    HARDBREAK = 'hardbreak'


class ListType:
    """List types."""

    UNORDERED = 'ul'
    ORDERED = 'ol'
    DESCRIPTION = 'dl'


class StyleName:
    """Standard style names."""

    HEADER = 'header'
    SUBHEADER = 'subheader'
    BODY = 'body'


class FitMode:
    """Media fit modes (Typst -> CSS)."""

    CONTAIN = 'contain'
    COVER = 'cover'
    STRETCH = 'stretch'
    FILL = 'fill'  # CSS equivalent of stretch


# Font weight mapping: named -> numeric
FONT_WEIGHT_MAP = {
    'thin': '100',
    'extralight': '200',
    'light': '300',
    'regular': '400',
    'medium': '500',
    'semibold': '600',
    'bold': '700',
    'extrabold': '800',
    'black': '900',
}
