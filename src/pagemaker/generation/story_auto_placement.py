"""
Auto-placement algorithm for story mode.

This module calculates implicit grid area assignments for blocks within a scene
based on sibling count and existing explicit :AREA: declarations.
"""

from typing import Dict, List


def compute_auto_placement(blocks: List[Dict], grid_cols: int, grid_rows: int) -> List[Dict]:
    """
    Assign grid areas to blocks based on sibling count.

    Layout rules:
    - 1 block:  Full viewport (uses all grid cells)
    - 2 blocks: Left|Right split (50/50)
    - 3 blocks: Three columns (33/33/33)
    - 4+ blocks: Auto-flow grid (2x2 or responsive)

    Blocks with explicit :AREA: declarations keep their areas unchanged.

    Args:
        blocks: List of block dictionaries (elements from a scene)
        grid_cols: Number of columns in the grid
        grid_rows: Number of rows in the grid

    Returns:
        List of blocks with computed 'area' fields
    """
    if not blocks:
        return []

    # Separate blocks with explicit areas from those needing auto-placement
    explicit_blocks = []
    auto_blocks = []

    for block in blocks:
        if block.get('area') is not None:
            explicit_blocks.append(block)
        else:
            auto_blocks.append(block)

    # If all blocks have explicit areas, return as-is
    if not auto_blocks:
        return blocks

    # Count blocks needing auto-placement
    n = len(auto_blocks)

    # Apply layout rules based on count
    if n == 1:
        # Full viewport
        auto_blocks[0]['area'] = {'x': 1, 'y': 1, 'w': grid_cols, 'h': grid_rows}

    elif n == 2:
        # Left|Right split (50/50)
        mid_col = (grid_cols // 2) + 1

        auto_blocks[0]['area'] = {'x': 1, 'y': 1, 'w': mid_col - 1, 'h': grid_rows}

        auto_blocks[1]['area'] = {
            'x': mid_col,
            'y': 1,
            'w': grid_cols - mid_col + 1,
            'h': grid_rows,
        }

    elif n == 3:
        # Three columns (33/33/33)
        col_width = grid_cols // 3

        auto_blocks[0]['area'] = {'x': 1, 'y': 1, 'w': col_width, 'h': grid_rows}

        auto_blocks[1]['area'] = {'x': col_width + 1, 'y': 1, 'w': col_width, 'h': grid_rows}

        auto_blocks[2]['area'] = {
            'x': 2 * col_width + 1,
            'y': 1,
            'w': grid_cols - (2 * col_width),
            'h': grid_rows,
        }

    else:
        # 4+ blocks: 2x2 grid or auto-flow
        # For simplicity, create a 2-column layout with multiple rows
        col_width = grid_cols // 2
        row_height = grid_rows // ((n + 1) // 2)  # Ceiling division

        for idx, block in enumerate(auto_blocks):
            col_idx = idx % 2
            row_idx = idx // 2

            block['area'] = {
                'x': (col_idx * col_width) + 1,
                'y': (row_idx * row_height) + 1,
                'w': col_width,
                'h': row_height,
            }

    # Reconstruct full block list preserving original order
    result = []
    auto_idx = 0
    explicit_idx = 0

    for block in blocks:
        if block.get('area') is not None and block in explicit_blocks:
            result.append(explicit_blocks[explicit_idx])
            explicit_idx += 1
        else:
            result.append(auto_blocks[auto_idx])
            auto_idx += 1

    return result


def area_to_css_grid(area: Dict[str, int]) -> str:
    """
    Convert area dict to CSS grid-area string.

    Args:
        area: Dict with keys 'x', 'y', 'w', 'h' (1-indexed)

    Returns:
        CSS grid-area string: "row-start / col-start / row-end / col-end"

    Example:
        {'x': 1, 'y': 1, 'w': 6, 'h': 4} → "1 / 1 / 5 / 7"
    """
    x = area['x']
    y = area['y']
    w = area['w']
    h = area['h']

    # CSS grid uses end positions (exclusive), so add width/height
    row_start = y
    col_start = x
    row_end = y + h
    col_end = x + w

    return f"{row_start} / {col_start} / {row_end} / {col_end}"
