def render_table_block(table_block: dict, text_args: str, escape_text_fn) -> str:
    """Render an Org-style simple table block to Typst as a single table.

    - Uses Typst table with auto-sized columns (consistent across rows)
    - Applies element text style via #text(text_args)[...]
    - Bolds header rows using #strong[...] inside the text call
    - Draws horizontal rulers only where explicit Org separator lines exist
    - No implicit top rule and no natural between-row rules

    The caller must provide an escape_text_fn(s: str, styled_wrapper: bool=False) -> str
    to avoid circular imports.
    """
    rows = table_block.get('rows') or []
    if not rows:
        return ""

    # Normalize column count across rows
    max_cols = max((len(r) for r in rows), default=0)
    if max_cols == 0:
        return ""
    norm_rows = [list(r) + [""] * (max_cols - len(r)) for r in rows]

    header_rows = int(table_block.get('header_rows') or 0)
    # Separator positions are recorded as "after the Nth parsed row"
    # Convert to a set for efficient lookups and de-duplication
    try:
        sep_positions = set(int(p) for p in (table_block.get('separators') or []))
    except Exception:
        sep_positions = set()

    # If there's an explicit separator right after the last non-empty data row,
    # drop only trailing all-empty rows that follow it. This prevents a final
    # empty data row from shifting the trailing rule upward (overlapping text).
    if header_rows < len(norm_rows):
        data = norm_rows[header_rows:]

        def row_is_empty(r):
            return all((str(c).strip() == "") for c in r)

        # Find last non-empty data row index
        last_nonempty_idx = None
        for i in range(len(data) - 1, -1, -1):
            if not row_is_empty(data[i]):
                last_nonempty_idx = i
                break

        if last_nonempty_idx is not None:
            # Global position after that row
            last_nonempty_global_pos = header_rows + last_nonempty_idx + 1
            if last_nonempty_global_pos in sep_positions:
                # Trim any empty rows that come after it
                j = len(data) - 1
                while j > last_nonempty_idx and row_is_empty(data[j]):
                    j -= 1
                data = data[: j + 1]
                norm_rows = norm_rows[:header_rows] + data

    # Build Typst columns tuple like (auto, auto, ...)
    cols_tuple = f"({', '.join(['auto'] * max_cols)})"

    parts = []
    # Table prelude: columns, gutter, and stroke disabled
    parts.append(f"#table(columns: {cols_tuple}, gutter: 6pt, stroke: none,")

    # Emit header rows inside table.header if present
    if header_rows > 0:
        header_cells = []
        for i in range(header_rows):
            for cell in norm_rows[i]:
                cell_text = (cell or '').strip()
                if not cell_text:
                    header_cells.append("[]")
                else:
                    escaped = escape_text_fn(cell_text, styled_wrapper=bool(text_args))
                    inner = f"#strong[{escaped}]"
                    cell_call = f"#text({text_args})[{inner}]" if text_args else f"#text[{inner}]"
                    header_cells.append(f"[{cell_call}]")
        parts.append(f"  table.header(\n    {', '.join(header_cells)}\n  ),")
        # Draw a horizontal rule after the header only if an explicit separator exists there
        if header_rows in sep_positions:
            parts.append("  table.hline(),")

    # Emit data rows and horizontal rules only at explicit separator positions
    data_rows = norm_rows[header_rows:]
    for idx, r in enumerate(data_rows):
        row_cells = []
        for cell in r:
            cell_text = (cell or '').strip()
            if not cell_text:
                row_cells.append("[]")
            else:
                escaped = escape_text_fn(cell_text, styled_wrapper=bool(text_args))
                cell_call = f"#text({text_args})[{escaped}]" if text_args else f"#text[{escaped}]"
                row_cells.append(f"[{cell_call}]")
        parts.append(f"  {', '.join(row_cells)},")

        # Separator-specified boundary after this row: global position is header_rows + idx + 1
        global_pos_after_this_row = header_rows + idx + 1
        if global_pos_after_this_row in sep_positions:
            parts.append("  table.hline(),")

    # Close table
    parts.append(")")

    return "\n".join(parts)
