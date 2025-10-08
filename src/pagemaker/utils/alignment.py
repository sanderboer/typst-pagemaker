"""Alignment and positioning utilities.

Extracted from generator.py to provide unified alignment logic
across all element types.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class AlignmentWrapper:
    """Container for alignment wrapping logic."""

    align: Optional[str] = None
    valign: Optional[str] = None

    def __post_init__(self):
        self.align = normalize_alignment(self.align)
        self.valign = normalize_valignment(self.valign)

    def has_alignment(self) -> bool:
        """Check if any alignment is specified."""
        return self.align is not None or self.valign is not None

    def get_typst_wrapper(self, content: str) -> str:
        """Wrap content with Typst alignment directives."""
        if not self.has_alignment():
            return content

        wrapper_parts = []

        if self.align:
            wrapper_parts.append(f"align({self.align})")
        if self.valign:
            wrapper_parts.append(f"align({self.valign})")

        if wrapper_parts:
            wrapper = " + ".join(wrapper_parts)
            return f"#({wrapper})[{content}]"

        return content


def normalize_alignment(align: Optional[str]) -> Optional[str]:
    """Normalize horizontal alignment value to Typst format."""
    if not align:
        return None

    align_lower = align.lower().strip()

    # Map common alignment values to Typst equivalents
    alignment_map = {
        'left': 'left',
        'center': 'center',
        'centre': 'center',  # British spelling
        'right': 'right',
        'justify': 'justify',
        'justified': 'justify',
    }

    return alignment_map.get(align_lower, align_lower)


def normalize_valignment(valign: Optional[str]) -> Optional[str]:
    """Normalize vertical alignment value to Typst format."""
    if not valign:
        return None

    valign_lower = valign.lower().strip()

    # Map common vertical alignment values to Typst equivalents
    valignment_map = {
        'top': 'top',
        'middle': 'horizon',  # Typst uses 'horizon' for middle
        'center': 'horizon',
        'centre': 'horizon',
        'bottom': 'bottom',
    }

    return valignment_map.get(valign_lower, valign_lower)


def get_alignment_wrapper(element: Dict[str, Any]) -> AlignmentWrapper:
    """Extract alignment from element properties."""
    return AlignmentWrapper(align=element.get('align'), valign=element.get('valign'))


def calculate_position_mm(
    area_spec: str,
    grid_cols: int,
    grid_rows: int,
    page_width_mm: float,
    page_height_mm: float,
    margins: Tuple[float, float, float, float],  # top, right, bottom, left
) -> Tuple[float, float, float, float]:
    """Calculate element position in mm from grid coordinates.

    Returns: (x_mm, y_mm, width_mm, height_mm)
    """
    # Parse area spec like "A1,C3"
    if ',' not in area_spec:
        return (0, 0, 0, 0)

    start_cell, end_cell = area_spec.split(',')

    # Extract column and row from cell references like "A1", "C3"
    def parse_cell(cell: str) -> Tuple[int, int]:
        cell = cell.strip()
        if not cell:
            return (0, 0)

        # Find where letters end and numbers begin
        col_letters = ""
        row_numbers = ""

        for char in cell:
            if char.isalpha():
                col_letters += char
            elif char.isdigit():
                row_numbers += char

        # Convert column letters to number (A=1, B=2, etc.)
        col = 0
        for char in col_letters.upper():
            col = col * 26 + (ord(char) - ord('A') + 1)

        row = int(row_numbers) if row_numbers else 1

        return (col, row)

    start_col, start_row = parse_cell(start_cell)
    end_col, end_row = parse_cell(end_cell)

    # Calculate usable page dimensions
    top_margin, right_margin, bottom_margin, left_margin = margins

    usable_width = page_width_mm - left_margin - right_margin
    usable_height = page_height_mm - top_margin - bottom_margin

    # Calculate cell dimensions
    cell_width = usable_width / grid_cols
    cell_height = usable_height / grid_rows

    # Calculate position and size
    x_mm = left_margin + (start_col - 1) * cell_width
    y_mm = top_margin + (start_row - 1) * cell_height
    width_mm = (end_col - start_col + 1) * cell_width
    height_mm = (end_row - start_row + 1) * cell_height

    return (x_mm, y_mm, width_mm, height_mm)
