import re, pathlib, datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

HEADLINE_RE = re.compile(r'^(?P<stars>\*+)\s+(?P<title>.+)$')
PROP_BEGIN_RE = re.compile(r'^:PROPERTIES:', re.I)
PROP_END_RE = re.compile(r'^:END:', re.I)
LINK_IMG_RE = re.compile(r'^\[\[file:(?P<path>[^\]]+)\]\]')

PAGE_SIZES_MM = {
    'A4': (210, 297), 'A3': (297, 420), 'A2': (420, 594), 'A1': (594, 841), 'A5': (148, 210),
}

# New default: no margins declared unless provided in meta/page
DEFAULTS = { 'PAGESIZE': 'A4', 'ORIENTATION': 'landscape', 'GRID': '12x8', 'THEME': 'light', 'GRID_DEBUG': 'false', 'MARGINS': '', 'DEFAULT_MASTER': '' }


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
        t = r = b = l = nums[0]
    elif len(nums) == 2:
        t = b = nums[0]; r = l = nums[1]
    elif len(nums) == 3:
        t = nums[0]; r = l = nums[1]; b = nums[2]
    elif len(nums) >= 4:
        t, r, b, l = nums[0], nums[1], nums[2], nums[3]
    else:
        return None
    return {'top': float(t), 'right': float(r), 'bottom': float(b), 'left': float(l)}


def parse_bool(val: Optional[str]) -> Optional[bool]:
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in ("1", "true", "yes", "y", "on"): return True
    if s in ("0", "false", "no", "n", "off"): return False
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

class OrgElement:
    def __init__(self, id_, type_, title, area=None, props=None, content_lines=None):
        self.id = id_
        self.type = type_
        self.title = title
        self.area = area
        self.props = props or {}
        self.content_lines = content_lines or []
    def to_ir(self):
        area_obj = None
        if self.area:
            area_obj = { 'x': self.area[0], 'y': self.area[1], 'w': self.area[2], 'h': self.area[3] }
        figure = None
        pdf = None
        svg = None
        rectangle = None
        if self.type == 'figure':
            img = None
            for line in self.content_lines:
                m = LINK_IMG_RE.match(line.strip())
                if m:
                    img = m.group('path'); break
            figure = { 'src': img, 'caption': self.props.get('CAPTION'), 'fit': self.props.get('FIT', 'contain') }
        if self.type == 'pdf':
            pdf = {
                'src': self.props.get('PDF'),
                'pages': [int(self.props.get('PAGE', '1'))],
                'scale': float(self.props.get('SCALE', '1.0'))
            }
        if self.type == 'svg':
            svg = {
                'src': self.props.get('SVG'),
                'scale': float(self.props.get('SCALE', '1.0'))
            }
        if self.type == 'rectangle':
            rectangle = {
                'color': self.props.get('COLOR', '#3498db'),
                'alpha': float(self.props.get('ALPHA', '1.0'))
            }
        text_blocks = []
        style = None
        padding_mm = None
        justify = None
        align = None
        valign = None
        flow = None
        if self.type in ('header', 'subheader', 'body'):
            content = '\n'.join(self.content_lines).strip()
            if content:
                text_blocks.append({'kind':'plain','content':content})
            style = self.props.get('STYLE')
            padding_mm = parse_padding(self.props.get('PADDING'))
            if 'JUSTIFY' in self.props:
                jval = self.props.get('JUSTIFY')
                jparsed = parse_bool(jval)
                justify = True if jparsed is None else jparsed
            else:
                justify = None
            align = parse_align(self.props.get('ALIGN'))
            valign = parse_valign(self.props.get('VALIGN'))
            flow = parse_flow(self.props.get('FLOW'))
        # Allow padding and alignment for figures/svg/pdf/toc too (alignment currently only used for text/toc)
        if self.type in ('figure','svg','pdf','toc'):
            if padding_mm is None:
                padding_mm = parse_padding(self.props.get('PADDING'))
            if align is None:
                align = parse_align(self.props.get('ALIGN'))
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
            'padding_mm': padding_mm
        }

class OrgPage:
    def __init__(self, id_, title, props):
        self.id = id_
        self.title = title
        self.props = props
        self.elements = []
        self.master = None
    def to_ir(self, global_defaults):
        ps = self.props.get('PAGE_SIZE', global_defaults['PAGESIZE'])
        orientation = self.props.get('ORIENTATION', global_defaults['ORIENTATION'])
        w_mm, h_mm = PAGE_SIZES_MM.get(ps, PAGE_SIZES_MM['A4'])
        if orientation.lower() == 'landscape' and w_mm < h_mm:
            w_mm, h_mm = h_mm, w_mm
        if orientation.lower() == 'portrait' and w_mm > h_mm:
            w_mm, h_mm = h_mm, w_mm
        grid = self.props.get('GRID', global_defaults['GRID'])
        try:
            cols, rows = [int(x) for x in grid.lower().split('x')]
        except Exception:
            cols, rows = 12, 8
        # New semantics: MARGINS are absolute sizes in mm in CSS order TRBL (top,right,bottom,left)
        margins_val = self.props.get('MARGINS', global_defaults.get('MARGINS',''))
        margins_declared = isinstance(margins_val, str) and margins_val.strip() != ''
        top_mm = right_mm = bottom_mm = left_mm = 0.0
        if margins_declared:
            try:
                t, r, b, l = [float(x.strip()) for x in margins_val.split(',')]
                top_mm, right_mm, bottom_mm, left_mm = t, r, b, l
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
            'margins_mm': {'top': top_mm, 'right': right_mm, 'bottom': bottom_mm, 'left': left_mm} if margins_declared else None,
            'margins_declared': margins_declared,
            'master': self.props.get('MASTER', global_defaults.get('DEFAULT_MASTER','')).strip(),
            'master_def': self.props.get('MASTER_DEF','').strip(),
            'elements': [e.to_ir() for e in self.elements]
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
        r1 = letters_to_num(mb.group(1)); c1 = int(mb.group(2))
        r2 = letters_to_num(mb.group(3)); c2 = int(mb.group(4))
        if r1 and r2:
            x = min(c1, c2); y = min(r1, r2)
            w = abs(c2 - c1) + 1; h = abs(r2 - r1) + 1
            return [x, y, w, h]
        return None

    mc = cell_re.match(val)
    if mc:
        r = letters_to_num(mc.group(1)); c = int(mc.group(2))
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
    s = s.lower(); s = _re.sub(r'[^a-z0-9]+','-', s); s = s.strip('-'); return s or 'item'

def meta_defaults(meta):
    d = DEFAULTS.copy();
    for k,v in meta.items():
        if k in d: d[k] = v
    return d

def parse_org(path):
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    meta = {}; pages = []
    current_page = None; current_element = None
    prop_mode = False; prop_buf = {}; content_buf = []

    def close_element():
        nonlocal current_element, content_buf, current_page
        if current_element:
            current_element.content_lines = content_buf
            if current_page:
                current_page.elements.append(current_element)
        current_element = None; content_buf = []

    for raw in lines:
        line = raw.rstrip('\n')
        line_stripped = line.lstrip()
        if line_stripped.startswith('#+'):
            try:
                k,v = line_stripped[2:].split(':',1)
                meta[k.strip().upper()] = v.strip()
            except ValueError:
                pass
            continue
        m = HEADLINE_RE.match(line_stripped)
        if m and not prop_mode:
            level = len(m.group('stars'))
            title = m.group('title').strip()
            close_element()
            if level == 1:
                current_page = OrgPage(id_=slugify(title), title=title, props={})
                pages.append(current_page)
            elif level >= 2 and current_page:
                current_element = OrgElement(id_=slugify(title), type_='body', title=title, props={}, area=None)
            continue
        if PROP_BEGIN_RE.match(line_stripped):
            prop_mode = True; prop_buf = {}; continue
        if PROP_END_RE.match(line_stripped):
            prop_mode = False
            if current_element:
                current_element.props.update(prop_buf)
                etype = prop_buf.get('TYPE','').lower()
                if etype in ('header','subheader','body','figure','pdf','rectangle','svg','toc'):
                    current_element.type = etype
                else:
                    if len(content_buf)==1 and LINK_IMG_RE.match(content_buf[0].strip()):
                        current_element.type = 'figure'
                if 'AREA' in prop_buf:
                    ar = parse_area(prop_buf['AREA'])
                    if ar: current_element.area = ar
            elif current_page:
                current_page.props.update(prop_buf)
            prop_buf = {}; continue
        if prop_mode:
            if ':' in line_stripped:
                parts = line_stripped.split(':', 2)
                if len(parts) >= 3:
                    key = parts[1].strip().upper(); val = parts[2].strip()
                    if key: prop_buf[key] = val
            continue
        if current_element is not None:
            content_buf.append(line_stripped)
    close_element()

    ir = { 'meta': meta, 'pages': [p.to_ir(meta_defaults(meta)) for p in pages] }
    return ir
