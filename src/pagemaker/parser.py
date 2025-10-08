import re
import warnings
from typing import Dict, List, Optional

HEADLINE_RE = re.compile(r'^(?P<stars>\*+)\s+(?P<title>.+)$')
PROP_BEGIN_RE = re.compile(r'^:PROPERTIES:', re.I)
PROP_END_RE = re.compile(r'^:END:', re.I)
LINK_IMG_RE = re.compile(r'^\[\[file:(?P<path>[^\]]+)\]\]')

# List parsing regexes
UL_RE = re.compile(r'^(\s*)[-+*]\s+(.*)$')
OL_RE = re.compile(r'^(\s*)(\d+)[.)]\s+(.*)$')
OL_ALPHA_RE = re.compile(r'^(\s*)([a-zA-Z]+)[.)]\s+(.*)$')
CHECKBOX_RE = re.compile(r'^\[([ Xx-])\]\s*(.*)')
DESC_RE = re.compile(r'^(\s*)(.+?)\s*::\s*(.*)$')

# Table parsing regexes (Org-style simple tables)
TABLE_LINE_RE = re.compile(r'^\s*\|.*\|\s*$')
TABLE_SEP_RE = re.compile(r'^\s*\|[\-+:\s]+\|\s*$')

PAGE_SIZES_MM = {
    'A4': (210, 297),
    'A3': (297, 420),
    'A2': (420, 594),
    'A1': (594, 841),
    'A5': (148, 210),
}

# New default: no margins declared unless provided in meta/page
DEFAULTS = {
    'PAGESIZE': 'A4',
    'ORIENTATION': 'landscape',
    'GRID': '12x8',
    'THEME': 'light',
    'GRID_DEBUG': 'false',
    'MARGINS': '',
    'DEFAULT_MASTER': '',
}


def parse_padding(val: Optional[str]) -> Optional[Dict[str, float]]:
    """Parse CSS-like padding shorthand into a dict {top,right,bottom,left} in mm.
    Accepts comma and/or whitespace separated numbers (no unit suffix expected).
    Returns None if invalid.
    """
    if val is None:
        return None
    s = val.strip()
    if s == "":
        return None
    # Split on commas or whitespace
    parts = [p for p in re.split(r'[\s,]+', s) if p != ""]
    nums: List[float] = []
    for p in parts:
        try:
            nums.append(float(p))
        except Exception:
            return None
    if len(nums) == 1:
        t = r = b = left = nums[0]
    elif len(nums) == 2:
        t = b = nums[0]
        r = left = nums[1]
    elif len(nums) == 3:
        t = nums[0]
        r = left = nums[1]
        b = nums[2]
    elif len(nums) >= 4:
        t, r, b, left = nums[0], nums[1], nums[2], nums[3]
    else:
        return None
    return {'top': float(t), 'right': float(r), 'bottom': float(b), 'left': float(left)}


def parse_margin(val: Optional[str]) -> Optional[Dict[str, float]]:
    """Parse CSS-like margin shorthand into a dict {top,right,bottom,left} in mm.
    Accepts comma and/or whitespace separated numbers (no unit suffix expected).
    Returns None if invalid.
    """
    # Reuse the same logic as padding
    return parse_padding(val)


def parse_bool(val: Optional[str]) -> Optional[bool]:
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return None


def parse_align(val: Optional[str]) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in ("left", "center", "right"):
        return s
    return None


def parse_valign(val: Optional[str]) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in ("top", "middle", "bottom"):
        return s
    return None


def parse_flow(val: Optional[str]) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip().lower()
    # Accept a small set of strings for now
    if s in ("normal", "bottom-up", "center-out"):
        return s
    return None


def _get_list_indent(line: str) -> int:
    """Get indentation level in spaces for list items."""
    return len(line) - len(line.lstrip())


def _parse_checkbox(text: str) -> tuple[Optional[str], str]:
    """Parse checkbox from start of text. Returns (checkbox_state, remaining_text)."""
    m = CHECKBOX_RE.match(text)
    if not m:
        return None, text

    checkbox_char = m.group(1)
    remaining = m.group(2)

    if checkbox_char in [' ', '']:
        return 'unchecked', remaining
    elif checkbox_char.lower() == 'x':
        return 'checked', remaining
    elif checkbox_char == '-':
        return 'partial', remaining
    else:
        return 'unchecked', remaining


def _parse_ordered_marker(marker: str) -> tuple[int, str]:
    """Parse ordered list marker. Returns (number, style)."""
    if marker.isdigit():
        return int(marker), '1'

    # Handle alphabetic markers
    marker_lower = marker.lower()
    if marker_lower.isalpha():
        if len(marker) == 1:
            if marker.islower():
                # a, b, c... -> 1, 2, 3...
                return ord(marker_lower) - ord('a') + 1, 'a'
            else:
                # A, B, C... -> 1, 2, 3...
                return ord(marker_lower) - ord('a') + 1, 'A'

    # Fallback to numeric
    return 1, '1'


def _parse_content_blocks(lines: List[str]) -> List[Dict]:
    """Parse content lines into text blocks (plain text, lists, tables)."""
    if not lines:
        return []

    blocks = []
    i = 0

    while i < len(lines):
        # Try to parse a list starting at current position
        list_block, consumed = _try_parse_list(lines, i)
        if list_block:
            blocks.append(list_block)
            i += consumed
            continue

        # Try to parse a table starting at current position
        table_block, t_consumed = _try_parse_table(lines, i)
        if table_block:
            blocks.append(table_block)
            i += t_consumed
            continue

        # If we identified a list line but couldn't parse it, treat as plain text
        line = lines[i]
        if _is_list_line(line):
            # Failed to parse list - treat this line as plain text and advance
            blocks.append({'kind': 'plain', 'content': line.strip()})
            i += 1
            continue

        # Collect non-list and non-table lines into plain text
        plain_lines = []
        while i < len(lines):
            line = lines[i]
            if _is_list_line(line) or TABLE_LINE_RE.match(line):
                break
            plain_lines.append(line)
            i += 1

        if plain_lines:
            content = '\n'.join(plain_lines).strip()
            if content:
                blocks.append({'kind': 'plain', 'content': content})

    return blocks


def _is_list_line(line: str) -> bool:
    """Check if line starts a list item."""
    stripped = line.strip()
    if not stripped:
        return False

    return (
        UL_RE.match(line) is not None
        or OL_RE.match(line) is not None
        or OL_ALPHA_RE.match(line) is not None
        or DESC_RE.match(line) is not None
    )


def _try_parse_table(lines: List[str], start_idx: int) -> tuple[Optional[Dict], int]:
    """Try to parse an Org-mode simple table starting at start_idx.
    Recognizes contiguous lines starting with '|' and optional separator lines like '|---+---|'.
    Records the first separator as header/body divider and preserves all separator positions.
    Returns (table_block, lines_consumed) or (None, 0).
    """
    if start_idx >= len(lines):
        return None, 0

    # First line must be a table content line (not a pure separator)
    if not TABLE_LINE_RE.match(lines[start_idx]) or TABLE_SEP_RE.match(lines[start_idx]):
        return None, 0

    rows: List[List[str]] = []
    header_rows = 0
    separators: List[int] = []  # positions after the Nth parsed row

    i = start_idx
    header_candidate = None
    seen_separator = False
    while i < len(lines):
        ln = lines[i]
        if not TABLE_LINE_RE.match(ln):
            break
        if TABLE_SEP_RE.match(ln):
            # Record separator position relative to parsed content rows so far
            separators.append(len(rows))
            # Mark potential header boundary, but only finalize when a body row follows
            if header_candidate is None and rows:
                header_candidate = len(rows)
                seen_separator = True
            i += 1
            continue
        # Parse a table row: split by '|' and strip cells
        parts = [p.strip() for p in ln.strip().strip('|').split('|')]
        rows.append(parts)
        i += 1
        # Finalize header_rows only after we have at least one body row
        if header_rows == 0 and header_candidate is not None:
            header_rows = header_candidate

    if not rows:
        return None, 0

    # If there was no separator, assume no header
    block = {
        'kind': 'table',
        'rows': rows,
        'header_rows': header_rows,
        'separators': separators,
    }
    return block, (i - start_idx)


def _try_parse_list(lines: List[str], start_idx: int) -> tuple[Optional[Dict], int]:
    """Try to parse a list starting at start_idx. Returns (list_block, lines_consumed)."""
    if start_idx >= len(lines):
        return None, 0

    first_line = lines[start_idx]
    if not _is_list_line(first_line):
        return None, 0

    # Determine list type from first line
    if UL_RE.match(first_line):
        return _parse_unordered_list(lines, start_idx)
    elif OL_RE.match(first_line) or OL_ALPHA_RE.match(first_line):
        return _parse_ordered_list(lines, start_idx)
    elif DESC_RE.match(first_line):
        return _parse_description_list(lines, start_idx)

    return None, 0


def _parse_unordered_list(lines: List[str], start_idx: int) -> tuple[Optional[Dict], int]:
    """Parse unordered list starting at start_idx."""
    items = []
    consumed = 0
    tight = True
    base_indent = None

    i = start_idx
    while i < len(lines):
        line = lines[i]

        # Check for blank line
        if not line.strip():
            tight = False
            i += 1
            consumed += 1
            continue

        # Check if this is a list item at our level
        ul_match = UL_RE.match(line)
        if ul_match:
            indent = len(ul_match.group(1))
            if base_indent is None:
                base_indent = indent
            elif indent < base_indent:
                # Less indented - end of this list
                break

            if indent == base_indent:
                # Same level item
                text = ul_match.group(2)
                checkbox, clean_text = _parse_checkbox(text)

                # Collect item content and any nested lists
                item_lines = [clean_text] if clean_text.strip() else []
                item_consumed = 1

                # Look ahead for continuation lines and nested content
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    if not next_line.strip():
                        item_lines.append('')
                        j += 1
                        item_consumed += 1
                        continue

                    next_indent = _get_list_indent(next_line)
                    if next_indent > base_indent:
                        # Nested content - could be text or nested list
                        if _is_list_line(next_line):
                            # Nested list - we'll parse it later
                            break
                        else:
                            # Continuation text
                            item_lines.append(
                                next_line[base_indent + 2 :]
                            )  # Remove base indent + marker space
                            j += 1
                            item_consumed += 1
                    else:
                        # Same or less indent - end of this item
                        break

                # Create item
                item_text = '\n'.join(item_lines).strip()
                item = {'text': item_text}
                if checkbox:
                    item['checkbox'] = checkbox

                # TODO: Parse nested lists (will implement in next iteration)
                items.append(item)

                i += item_consumed
                consumed += item_consumed
                continue
            else:
                # More indented - this is nested, end current list
                break

        # Not a list item at our level - end list
        break

    if not items:
        return None, 0
    return {'kind': 'list', 'type': 'ul', 'items': items, 'tight': tight}, consumed


def _parse_ordered_list(lines: List[str], start_idx: int) -> tuple[Optional[Dict], int]:
    """Parse ordered list starting at start_idx."""
    items = []
    consumed = 0
    tight = True
    base_indent = None
    start_num = 1
    style = '1'

    i = start_idx
    while i < len(lines):
        line = lines[i]

        # Check for blank line
        if not line.strip():
            tight = False
            i += 1
            consumed += 1
            continue

        # Check numeric ordered list
        ol_match = OL_RE.match(line)
        ol_alpha_match = OL_ALPHA_RE.match(line) if not ol_match else None

        if ol_match:
            indent = len(ol_match.group(1))
            marker = ol_match.group(2)
            text = ol_match.group(3)

            if base_indent is None:
                base_indent = indent
                start_num = int(marker)
                style = '1'
            elif indent < base_indent:
                # Less indented - end of this list
                break

            if indent == base_indent:
                # Same level item
                checkbox, clean_text = _parse_checkbox(text)

                # Collect item content (similar to unordered)
                item_lines = [clean_text] if clean_text.strip() else []
                item_consumed = 1

                # Look ahead for continuation lines
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    if not next_line.strip():
                        item_lines.append('')
                        j += 1
                        item_consumed += 1
                        continue

                    next_indent = _get_list_indent(next_line)
                    if next_indent > base_indent:
                        if _is_list_line(next_line):
                            break
                        else:
                            item_lines.append(
                                next_line[base_indent + len(marker) + 2 :]
                            )  # Remove indent + marker + space
                            j += 1
                            item_consumed += 1
                    else:
                        break

                # Create item
                item_text = '\n'.join(item_lines).strip()
                item = {'text': item_text}
                if checkbox:
                    item['checkbox'] = checkbox

                items.append(item)

                i += item_consumed
                consumed += item_consumed
                continue
            else:
                # More indented - this is nested, end current list
                break

        elif ol_alpha_match:
            indent = len(ol_alpha_match.group(1))
            marker = ol_alpha_match.group(2)
            text = ol_alpha_match.group(3)

            if base_indent is None:
                base_indent = indent
                start_num, style = _parse_ordered_marker(marker)
            elif indent < base_indent:
                # Less indented - end of this list
                break

            if indent == base_indent:
                # Same level item
                checkbox, clean_text = _parse_checkbox(text)

                # Collect item content (similar to unordered)
                item_lines = [clean_text] if clean_text.strip() else []
                item_consumed = 1

                # Look ahead for continuation lines
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    if not next_line.strip():
                        item_lines.append('')
                        j += 1
                        item_consumed += 1
                        continue

                    next_indent = _get_list_indent(next_line)
                    if next_indent > base_indent:
                        if _is_list_line(next_line):
                            break
                        else:
                            item_lines.append(
                                next_line[base_indent + len(marker) + 2 :]
                            )  # Remove indent + marker + space
                            j += 1
                            item_consumed += 1
                    else:
                        break

                # Create item
                item_text = '\n'.join(item_lines).strip()
                item = {'text': item_text}
                if checkbox:
                    item['checkbox'] = checkbox

                items.append(item)

                i += item_consumed
                consumed += item_consumed
                continue
            else:
                # More indented - this is nested, end current list
                break

        # Not a list item at our level - end list
        break

    if not items:
        return None, 0
    return {
        'kind': 'list',
        'type': 'ol',
        'items': items,
        'tight': tight,
        'start': start_num,
        'style': style,
    }, consumed


def _parse_description_list(lines: List[str], start_idx: int) -> tuple[Optional[Dict], int]:
    """Parse description list starting at start_idx."""
    items = []
    consumed = 0
    tight = True
    base_indent = None

    i = start_idx
    while i < len(lines):
        line = lines[i]

        # Check for blank line
        if not line.strip():
            tight = False
            i += 1
            consumed += 1
            continue

        # Check for description list item
        desc_match = DESC_RE.match(line)
        if desc_match:
            indent = len(desc_match.group(1))
            if base_indent is None:
                base_indent = indent
            elif indent < base_indent:
                break

            if indent == base_indent:
                term = desc_match.group(2).strip()
                desc = desc_match.group(3).strip()

                # For now, simple term/desc - no multiline support yet
                items.append({'term': term, 'desc': desc})

                i += 1
                consumed += 1
                continue
            else:
                # indent > base_indent: more indented than expected, skip this line
                i += 1
                consumed += 1
                continue

        # Not a description item at our level
        break

    if not items:
        return None, 0
    return {'kind': 'list', 'type': 'dl', 'items': items, 'tight': tight}, consumed


class OrgElement:
    def __init__(
        self,
        id_,
        type_,
        title,
        area=None,
        props=None,
        content_lines=None,
        level: Optional[int] = None,
    ):
        self.id = id_
        self.type = type_
        self.title = title
        self.area = area
        self.props = props or {}
        self.content_lines = content_lines or []
        self.level = level
        # New flags for ignore semantics
        self.ignored_self = False
        self.ignored_by_parent = False

    def to_ir(self):
        area_obj = None
        if self.area:
            area_obj = {'x': self.area[0], 'y': self.area[1], 'w': self.area[2], 'h': self.area[3]}
        figure = None
        pdf = None
        svg = None
        rectangle = None
        if self.type == 'figure':
            img = None
            for line in self.content_lines:
                m = LINK_IMG_RE.match(line.strip())
                if m:
                    img = m.group('path')
                    break
            figure = {
                'src': img,
                'caption': self.props.get('CAPTION'),
                'fit': self.props.get('FIT', 'contain'),
            }
        if self.type == 'pdf':
            pdf = {
                'src': self.props.get('PDF'),
                'pages': [int(self.props.get('PAGE', '1'))],
                'scale': float(self.props.get('SCALE', '1.0')),
                # New: scale mode (contain | cover) for auto scaling strategy
                'scale_mode': (self.props.get('PDF_SCALE_MODE') or 'contain').strip().lower(),
            }
        if self.type == 'svg':
            svg = {'src': self.props.get('SVG'), 'scale': float(self.props.get('SCALE', '1.0'))}
        if self.type == 'rectangle':
            rectangle = {
                'color': self.props.get('COLOR', '#3498db'),
                'alpha': float(self.props.get('ALPHA', '1.0')),
            }
        text_blocks = []
        style = None
        padding_mm = None
        had_margin_decl = False
        justify = None
        align = None
        valign = None
        flow = None
        if self.type in ('header', 'subheader', 'body'):
            # Parse content into mixed text blocks (plain text and lists)
            text_blocks = _parse_content_blocks(self.content_lines)
            style = self.props.get('STYLE')
            padding_mm = parse_padding(self.props.get('PADDING'))
            m_parsed = parse_margin(self.props.get('MARGIN'))
            if m_parsed is not None:
                had_margin_decl = True
                if padding_mm is None:
                    padding_mm = m_parsed
                    warnings.warn(
                        f"Element-level MARGIN is deprecated; mapped to PADDING on '{self.id}'",
                        UserWarning,
                    )
            if 'JUSTIFY' in self.props:
                jval = self.props.get('JUSTIFY')
                jparsed = parse_bool(jval)
                justify = True if jparsed is None else jparsed
            else:
                justify = None
            align = parse_align(self.props.get('ALIGN'))
            valign = parse_valign(self.props.get('VALIGN'))
            flow = parse_flow(self.props.get('FLOW'))
        # Allow padding and alignment for figures/svg/pdf/rectangle/toc too (alignment currently only used for text/toc)
        if self.type in ('figure', 'svg', 'pdf', 'rectangle', 'toc'):
            if padding_mm is None:
                padding_mm = parse_padding(self.props.get('PADDING'))
            m_parsed2 = parse_margin(self.props.get('MARGIN'))
            if m_parsed2 is not None:
                had_margin_decl = True
                if padding_mm is None:
                    padding_mm = m_parsed2
                    warnings.warn(
                        f"Element-level MARGIN is deprecated; mapped to PADDING on '{self.id}'",
                        UserWarning,
                    )
            if align is None:
                align = parse_align(self.props.get('ALIGN'))
            if valign is None:
                valign = parse_valign(self.props.get('VALIGN'))
        return {
            'id': self.id,
            'type': self.type,
            'title': self.title,
            'area': area_obj,
            # coords removed; AREA always in total grid
            'coords': '',
            'z': int(self.props.get('Z', '10')),
            'figure': figure,
            'pdf': pdf,
            'svg': svg,
            'rectangle': rectangle,
            'text_blocks': text_blocks,
            'style': style,
            'justify': justify,
            'align': align,
            'valign': valign,
            'flow': flow,
            'padding_mm': padding_mm,
            'had_margin_decl': had_margin_decl,
        }


class OrgPage:
    def __init__(self, id_, title, props):
        self.id = id_
        self.title = title
        self.props = props
        self.elements = []
        self.master = None
        # New: page-level ignore
        self.ignore_page = False

    def to_ir(self, global_defaults):
        # Page size and orientation are document-level settings.
        # Ignore per-page overrides to ensure uniform output (Typst limitation).
        ps = global_defaults['PAGESIZE']
        orientation = global_defaults['ORIENTATION']
        w_mm, h_mm = PAGE_SIZES_MM.get(ps, PAGE_SIZES_MM['A4'])
        if isinstance(orientation, str) and orientation.lower() == 'landscape' and w_mm < h_mm:
            w_mm, h_mm = h_mm, w_mm
        if isinstance(orientation, str) and orientation.lower() == 'portrait' and w_mm > h_mm:
            w_mm, h_mm = h_mm, w_mm
        grid = self.props.get('GRID', global_defaults['GRID'])
        try:
            cols, rows = (int(x) for x in grid.lower().split('x'))
        except Exception:
            cols, rows = 12, 8
        # New semantics: MARGINS are absolute sizes in mm in CSS order TRBL (top,right,bottom,left)
        margins_val = self.props.get('MARGINS', global_defaults.get('MARGINS', ''))
        margins_declared = isinstance(margins_val, str) and margins_val.strip() != ''
        top_mm = right_mm = bottom_mm = left_mm = 0.0
        if margins_declared:
            try:
                t, r, b, left_val = (float(x.strip()) for x in margins_val.split(','))
                top_mm, right_mm, bottom_mm, left_mm = t, r, b, left_val
            except Exception:
                # If parsing fails, treat as not declared
                margins_declared = False
        grid_total_cols = cols + (2 if margins_declared else 0)
        grid_total_rows = rows + (2 if margins_declared else 0)
        return {
            'id': self.id,
            'title': self.title,
            'page_size': {'w_mm': w_mm, 'h_mm': h_mm},
            'orientation': orientation,
            'grid': {'cols': cols, 'rows': rows},
            'grid_total': {'cols': grid_total_cols, 'rows': grid_total_rows},
            'margins_mm': {'top': top_mm, 'right': right_mm, 'bottom': bottom_mm, 'left': left_mm}
            if margins_declared
            else None,
            'margins_declared': margins_declared,
            'master': self.props.get('MASTER', global_defaults.get('DEFAULT_MASTER', '')).strip(),
            'master_def': self.props.get('MASTER_DEF', '').strip(),
            # Record any per-page overrides that are ignored for validation/warnings
            'ignored_overrides': [
                k for k in ('PAGE_SIZE', 'PAGESIZE', 'ORIENTATION') if k in self.props
            ],
            'props': self.props,
            'elements': [e.to_ir() for e in self.elements],
        }


def parse_area(val):
    val = (val or "").strip()
    # Support new RowCol notation where rows are letters from top (A=1) and columns are numbers.
    # Examples:
    #  - "A1" -> [1,1,1,1]
    #  - "A1,C2" -> rectangle from A1 to C2 inclusive -> [1,1,2,3]
    # Backward-compatible with legacy "x,y,w,h" integer format.
    cell_re = re.compile(r'^\s*([A-Za-z]+)\s*(\d+)\s*$')
    block_re = re.compile(r'^\s*([A-Za-z]+)\s*(\d+)\s*,\s*([A-Za-z]+)\s*(\d+)\s*$')

    def letters_to_num(s: str):
        n = 0
        s = s.strip().upper()
        if not s:
            return None
        for ch in s:
            if 'A' <= ch <= 'Z':
                n = n * 26 + (ord(ch) - ord('A') + 1)
            else:
                return None
        return n if n > 0 else None

    mb = block_re.match(val)
    if mb:
        r1 = letters_to_num(mb.group(1))
        c1 = int(mb.group(2))
        r2 = letters_to_num(mb.group(3))
        c2 = int(mb.group(4))
        if r1 and r2:
            x = min(c1, c2)
            y = min(r1, r2)
            w = abs(c2 - c1) + 1
            h = abs(r2 - r1) + 1
            return [x, y, w, h]
        return None

    mc = cell_re.match(val)
    if mc:
        r = letters_to_num(mc.group(1))
        c = int(mc.group(2))
        if r:
            return [c, r, 1, 1]
        return None

    # Legacy x,y,w,h format
    try:
        parts = [int(x.strip()) for x in val.split(',')]
        if len(parts) == 4:
            return parts
    except Exception:
        return None
    return None


def slugify(s):
    import re as _re

    s = s.lower()
    s = _re.sub(r'[^a-z0-9]+', '-', s)
    s = s.strip('-')
    return s or 'item'


def meta_defaults(meta):
    d = DEFAULTS.copy()
    for k, v in meta.items():
        if k in d:
            d[k] = v
    return d


def parse_org(path):
    with open(path, encoding='utf-8') as f:
        lines = f.readlines()
    meta = {}
    pages: List[OrgPage] = []
    current_page: Optional[OrgPage] = None
    current_element: Optional[OrgElement] = None
    prop_mode = False
    prop_buf: Dict[str, str] = {}
    content_buf: List[str] = []
    # Track subtree ignore depth (headline level that activated ignore)
    ignore_depth: Optional[int] = None
    # Inheritable padding context: map headline level -> padding string (e.g., "10,20,10,20")
    padding_context: Dict[int, Optional[str]] = {}
    # Inheritable AREA context: map headline level -> parsed area [x,y,w,h]
    area_context: Dict[int, Optional[List[int]]] = {}
    # Current page-level padding declaration string (if any)
    current_page_padding_str: Optional[str] = None

    def close_element():
        nonlocal current_element, content_buf, current_page
        if current_element:
            current_element.content_lines = content_buf
            # Skip appending if element is ignored (self or by parent), or has no declared type, or TYPE: none
            type_declared = 'TYPE' in (current_element.props or {})
            type_is_none = (
                str((current_element.props or {}).get('TYPE', '')).strip().lower() == 'none'
            )
            if (
                current_page
                and not current_element.ignored_self
                and not current_element.ignored_by_parent
                and type_declared
                and not type_is_none
            ):
                current_page.elements.append(current_element)
        current_element = None
        content_buf = []

    for raw in lines:
        line = raw.rstrip('\n')
        line_stripped = line.lstrip()
        if line_stripped.upper().startswith('#+TBLFM:'):
            # Ignore Org table formula lines
            continue
        if line_stripped.startswith('#+'):
            try:
                k, v = line_stripped[2:].split(':', 1)
                key = k.strip().upper()
                if key == 'TBLFM':
                    # Extra guard: ignore table formulas
                    continue
                meta[key] = v.strip()
            except ValueError:
                pass
            continue
        m = HEADLINE_RE.match(line_stripped)
        if m and not prop_mode:
            level = len(m.group('stars'))
            title = m.group('title').strip()
            close_element()
            # Leaving an ignored subtree if we move to a headline at or above ignore depth
            if ignore_depth is not None and level <= ignore_depth:
                ignore_depth = None
            # Trim contexts for new headline scope (siblings shouldn't inherit each other's context)
            if level == 1:
                padding_context = {}
                area_context = {}
                current_page_padding_str = None
            else:
                # Remove contexts at or below this level
                for lv in [lv for lv in list(padding_context.keys()) if lv >= level]:
                    padding_context.pop(lv, None)
                for lv in [lv for lv in list(area_context.keys()) if lv >= level]:
                    area_context.pop(lv, None)
            if level == 1:
                current_page = OrgPage(id_=slugify(title), title=title, props={})
                pages.append(current_page)
            elif level >= 2 and current_page:
                current_element = OrgElement(
                    id_=slugify(title), type_='body', title=title, props={}, area=None, level=level
                )
                # If we are inside an ignored subtree, mark this element as ignored by parent
                if ignore_depth is not None and level > ignore_depth:
                    current_element.ignored_by_parent = True
            continue
        if PROP_BEGIN_RE.match(line_stripped):
            prop_mode = True
            prop_buf = {}
            continue
        if PROP_END_RE.match(line_stripped):
            prop_mode = False
            if current_element:
                current_element.props.update(prop_buf)
                etype = prop_buf.get('TYPE', '').lower()
                if etype in (
                    'header',
                    'subheader',
                    'body',
                    'figure',
                    'pdf',
                    'rectangle',
                    'svg',
                    'toc',
                ):
                    current_element.type = etype
                else:
                    # Legacy: infer figure from single image line, but this does NOT count as declared TYPE
                    if len(content_buf) == 1 and LINK_IMG_RE.match(content_buf[0].strip()):
                        current_element.type = 'figure'
                if 'AREA' in prop_buf:
                    ar = parse_area(prop_buf['AREA'])
                    if ar:
                        current_element.area = ar
                # Element-level ignore semantics
                ig = parse_bool(prop_buf.get('IGNORE'))
                if ig is True and current_element.level:
                    current_element.ignored_self = True
                    # Ignore entire subtree under this section
                    ignore_depth = current_element.level
                # If TYPE is explicitly 'none' or missing, ignore just this element (not its children)
                type_declared = 'TYPE' in prop_buf
                if (type_declared and etype == 'none') or (not type_declared):
                    current_element.ignored_self = True
                # Inheritable PADDING is cumulative across meta -> page -> ancestors -> element
                try:
                    lvl = int(current_element.level or 2)
                except Exception:
                    lvl = 2

                def _pad_to_list(s: Optional[str]) -> List[float]:
                    d = parse_padding(s)
                    if not d:
                        return [0.0, 0.0, 0.0, 0.0]
                    return [
                        float(d['top']),
                        float(d['right']),
                        float(d['bottom']),
                        float(d['left']),
                    ]

                cum: List[float] = [0.0, 0.0, 0.0, 0.0]
                had_any_decl = False
                # Document/meta padding
                meta_pad_str = meta.get('PADDING')
                if isinstance(meta_pad_str, str) and meta_pad_str.strip() != '':
                    p = _pad_to_list(meta_pad_str)
                    cum = [a + b for a, b in zip(cum, p)]
                    had_any_decl = True
                # Page padding
                if (
                    isinstance(current_page_padding_str, str)
                    and current_page_padding_str.strip() != ''
                ):
                    p = _pad_to_list(current_page_padding_str)
                    cum = [a + b for a, b in zip(cum, p)]
                    had_any_decl = True
                # Ancestors' padding (sum all declarations from level 2 up to parent)
                for ancestor_lv in range(2, lvl):
                    anc_str = padding_context.get(ancestor_lv)
                    if isinstance(anc_str, str) and anc_str.strip() != '':
                        p = _pad_to_list(anc_str)
                        cum = [a + b for a, b in zip(cum, p)]
                        had_any_decl = True
                # Element-level PADDING or (deprecated) MARGIN
                elem_pad_str = current_element.props.get('PADDING')
                elem_margin_str = current_element.props.get('MARGIN')
                declared_ctx = None
                if isinstance(elem_pad_str, str) and elem_pad_str.strip() != '':
                    p = _pad_to_list(elem_pad_str)
                    cum = [a + b for a, b in zip(cum, p)]
                    declared_ctx = elem_pad_str
                    had_any_decl = True
                elif isinstance(elem_margin_str, str) and elem_margin_str.strip() != '':
                    p = _pad_to_list(elem_margin_str)
                    cum = [a + b for a, b in zip(cum, p)]
                    # Treat MARGIN as a padding source for descendants (deprecated)
                    declared_ctx = elem_margin_str
                    had_any_decl = True
                # Apply cumulative padding whenever any declaration exists (even if it sums to zero)
                if had_any_decl:
                    current_element.props['PADDING'] = f"{cum[0]},{cum[1]},{cum[2]},{cum[3]}"
                # Update context for this level based on this element's own declaration (not the cumulative value)
                if declared_ctx:
                    padding_context[lvl] = declared_ctx

                # AREA inheritance: percolate from nearest ancestor that declared AREA
                if current_element.area is None:
                    inherited_area = None
                    for ancestor_lv in range(lvl - 1, 1, -1):
                        if area_context.get(ancestor_lv):
                            inherited_area = area_context.get(ancestor_lv)
                            break
                    if inherited_area is not None:
                        current_element.area = inherited_area
                # Update AREA context only if this element explicitly declared a valid AREA
                if 'AREA' in prop_buf and current_element.area is not None:
                    area_context[lvl] = current_element.area
            elif current_page:
                current_page.props.update(prop_buf)
                # Page-level ignore: drop entire page from IR later
                ig = parse_bool(prop_buf.get('IGNORE'))
                if ig is True:
                    current_page.ignore_page = True
                    # Also ignore all subsequent sections until next page
                    ignore_depth = 1
                # Capture page-level PADDING for inheritance
                if (
                    isinstance(prop_buf.get('PADDING'), str)
                    and prop_buf.get('PADDING').strip() != ''
                ):
                    current_page_padding_str = prop_buf.get('PADDING')
            prop_buf = {}
            continue
        if prop_mode:
            if ':' in line_stripped:
                parts = line_stripped.split(':', 2)
                if len(parts) >= 3:
                    key = parts[1].strip().upper()
                    val = parts[2].strip()
                    if key:
                        prop_buf[key] = val
            continue
        if current_element is not None:
            content_buf.append(line)
    close_element()

    # Filter out ignored pages entirely
    pages_ir = [p.to_ir(meta_defaults(meta)) for p in pages if not getattr(p, 'ignore_page', False)]
    ir = {'meta': meta, 'pages': pages_ir}
    return ir
