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

DEFAULTS = { 'PAGESIZE': 'A4', 'ORIENTATION': 'landscape', 'GRID': '12x8', 'THEME': 'light', 'GRID_DEBUG': 'false' }

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
        if self.type == 'rectangle':
            rectangle = {
                'color': self.props.get('COLOR', '#3498db'),
                'alpha': float(self.props.get('ALPHA', '1.0'))
            }
        text_blocks = []
        if self.type in ('header', 'subheader', 'body'):
            content = '\n'.join(self.content_lines).strip()
            if content:
                text_blocks.append({'kind':'plain','content':content})
        return {
            'id': self.id,
            'type': self.type,
            'title': self.title,
            'area': area_obj,
            'z': int(self.props.get('Z', '10')),
            'figure': figure,
            'pdf': pdf,
            'rectangle': rectangle,
            'text_blocks': text_blocks
        }

class OrgPage:
    def __init__(self, id_, title, props):
        self.id = id_
        self.title = title
        self.props = props
        self.elements = []
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
        return {
            'id': self.id,
            'title': self.title,
            'page_size': {'w_mm': w_mm, 'h_mm': h_mm},
            'orientation': orientation,
            'grid': {'cols': cols, 'rows': rows},
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
                if etype in ('header','subheader','body','figure','pdf','rectangle'):
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
