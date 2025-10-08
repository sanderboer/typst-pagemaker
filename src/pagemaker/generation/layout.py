"""Layout calculation and positioning utilities."""

from dataclasses import dataclass
from typing import Any, Dict, Tuple


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


def _fmt_len(val: float) -> str:
    """Format a length value removing trailing zeros."""
    try:
        return (f"{float(val):.6f}").rstrip('0').rstrip('.')
    except Exception:
        return "0"


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


# Wrapper functions for importing from generator.py
def compute_element_frame_size_mm_from_generator(page: dict, area: dict, padding: dict | None):
    """Import and use _compute_element_frame_size_mm from generator.py"""
    from .. import generator

    return generator._compute_element_frame_size_mm(page, area, padding)


def fmt_len_from_generator(val: float):
    """Import and use _fmt_len from generator.py"""
    from .. import generator

    return generator._fmt_len(val)


def split_paragraphs_from_generator(text: str):
    """Import and use _split_paragraphs from generator.py"""
    from .. import generator

    return generator._split_paragraphs(text)


@dataclass
class LayoutCalculator:
    """Calculates element positions and dimensions."""

    def __init__(
        self,
        page_width_mm: float,
        page_height_mm: float,
        grid_cols: int,
        grid_rows: int,
        margins: Tuple[float, float, float, float],
    ):
        self.page_width_mm = page_width_mm
        self.page_height_mm = page_height_mm
        self.grid_cols = grid_cols
        self.grid_rows = grid_rows
        self.margins = margins  # top, right, bottom, left

    def calculate_element_position(self, area: str) -> Tuple[float, float, float, float]:
        """Calculate element position from grid area specification."""
        # Placeholder - will be implemented from generator.py logic
        return (0.0, 0.0, 100.0, 50.0)


class MasterPageProcessor:
    """Handles master page processing and inheritance."""

    def process_master_pages(self, ir: Dict[str, Any]) -> Dict[str, Any]:
        """Process master page definitions and apply to pages."""
        # Placeholder - will be extracted from generator.py
        return ir


def calculate_element_positions(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate positions for all elements in IR."""
    # Placeholder function - will be refactored from generator.py
    return ir
