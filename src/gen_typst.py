#!/usr/bin/env python3
"""
Org -> IR -> Typst generator (prototype)
- Extracts pages/elements with basic properties
- Emits Typst code with grid-derived positioning helpers (placeholder absolute emulation)
- Optionally updates the HTML viewer's total page count placeholder

NOTE: The positioning macro is a simplification. Typst does not (yet) expose fully
CSS-like absolute positioning; we approximate by stacking blocks with insets.
Future refinement may switch to more idiomatic Typst constructs as they evolve.
"""
import re
import json
import argparse
import datetime
import pathlib
import sys, subprocess, os, shutil

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
    try:
        parts = [int(x.strip()) for x in val.split(',')]
        if len(parts) == 4:
            return parts
    except Exception:
        return None
    return None

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
        if line.startswith('#+'):
            try:
                k,v = line[2:].split(':',1)
                meta[k.strip().upper()] = v.strip()
            except ValueError:
                pass
            continue
        m = HEADLINE_RE.match(line)
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
        if PROP_BEGIN_RE.match(line):
            prop_mode = True; prop_buf = {}; continue
        if PROP_END_RE.match(line):
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
            if ':' in line:
                parts = line.split(':', 2)
                if len(parts) >= 3:
                    key = parts[1].strip().upper(); val = parts[2].strip()
                    if key: prop_buf[key] = val
            continue
        if current_element is not None:
            content_buf.append(line)
    close_element()

    ir = { 'meta': meta, 'pages': [p.to_ir(meta_defaults(meta)) for p in pages] }
    return ir

def slugify(s):
    s = s.lower(); s = re.sub(r'[^a-z0-9]+','-', s); s = s.strip('-'); return s or 'item'

def meta_defaults(meta):
    d = DEFAULTS.copy();
    for k,v in meta.items():
        if k in d: d[k] = v
    return d

TYPOGRAPHY = {
    'light': {
        'font_header': 'Manrope',
        'font_body': 'Manrope',
        'size_header': '2.6em',
        'size_subheader': '1.6em',
        'size_body': '1.0em'
    }
}

TYPST_HEADER = """// Auto-generated Typst file
// Generated: {timestamp}

#set text(fill: rgb("#1b1f23"))
"""

def generate_typst(ir):
    theme_name = ir['meta'].get('THEME','light')
    theme = TYPOGRAPHY.get(theme_name, TYPOGRAPHY['light'])
    out = []
    out.append(TYPST_HEADER.format(timestamp=datetime.datetime.now(datetime.UTC).isoformat()))
    out.append("#import \"@preview/muchpdf:0.1.1\": muchpdf\n")
    out.append(f"#let theme = (")
    out.append(f"  font_header: \"{theme['font_header']}\",")
    out.append(f"  font_body: \"{theme['font_body']}\",")
    out.append(f"  size_header: {theme['size_header']},")
    out.append(f"  size_subheader: {theme['size_subheader']},")
    out.append(f"  size_body: {theme['size_body']}")
    out.append(")\n")
    out.append("#let Header(txt) = text(weight: 700, size: 24pt)[txt]\n")
    out.append("#let Subheader(txt) = text(weight: 600, size: 24pt)[txt]\n")
    out.append("#let Body(txt) = text(size: 24pt)[txt]\n")
    out.append("#let Fig(img, caption: none) = if caption == none { \n  block(width: 100%, height: 100%, clip: true)[#img] \n} else { \n  block(width: 100%, height: 100%)[\n    #block(height: 85%, clip: true)[#img] \n    #block(height: 15%)[#text(size: 0.75em, fill: rgb(60%,60%,60%))[caption]] \n  ] \n}\n")
    out.append("#let ColorRect(color, alpha) = {\n  block(width: 100%, height: 100%, fill: rgb(color).transparentize(100% - alpha * 100%))[]\n}\n")
    out.append("#let PdfEmbed(path, page: 1, scale: 1.0) = {\n  // Try muchpdf first for vector preservation\n  let pdf_data = read(path, encoding: none)\n  // Note: muchpdf may fail with some PDF files, fallback handled at application level\n  let muchpdf_image = muchpdf(pdf_data, pages: page - 1, scale: scale)\n  block(width: 100%, height: 100%, clip: true)[\n    #muchpdf_image\n  ]\n}\n")
    out.append("// Overlay positioning macros (layer-based absolute emulation)\n")
    out.append("#let layer(cw, ch, x, y, w, h, body) = place(\n  dx: (x - 1) * cw,\n  dy: (y - 1) * ch,\n  block(\n    width: w * cw,\n    height: h * ch,\n    body\n  )\n)\n")
    out.append("#let draw_grid(cols, rows, cw, ch) = {\n  for col in range(1, cols + 1) {\n    place(line(start: ((col - 1) * cw, 0pt), end: ((col - 1) * cw, rows * ch), stroke: 0.5pt + rgb(\"#ccc\")))\n  }\n  for row in range(1, rows + 1) {\n    place(line(start: (0pt, (row - 1) * ch), end: (cols * cw, (row - 1) * ch), stroke: 0.5pt + rgb(\"#ccc\")))\n  }\n}\n")
    for page_index, page in enumerate(ir['pages']):
        w = page['page_size']['w_mm']; h = page['page_size']['h_mm']
        cols = page['grid']['cols']; rows = page['grid']['rows']
        out.append(f"// Page {page_index+1}: {page['title']}\n")
        out.append(f"#set page(width: {w}mm, height: {h}mm, margin: 0mm)\n")
        out.append(f"#let cw = {w}mm / {cols}\n#let ch = {h}mm / {rows}\n")
        out.append("// BEGIN PAGE CONTENT\n")
        elements = sorted(page['elements'], key=lambda e: e.get('z',100))
        for el in elements:
            area = el['area'] or {'x':1,'y':1,'w':cols,'h':1}
            x,y,wc,hc = area['x'], area['y'], area['w'], area['h']
            if (x < 1 or y < 1 or wc < 1 or hc < 1 or x+wc-1 > cols or y+hc-1 > rows):
                print(f"WARNING: AREA out-of-bounds for element {el['id']} on page {page['title']}: ({x},{y},{wc},{hc}) grid {cols}x{rows}", file=sys.stderr)
            content_fragments = []
            if el['type'] == 'header':
                txt = escape_text(el_text(el)); content_fragments.append(f"[#text(font: \"Manrope\", weight: \"bold\", size: 24pt)[{txt}]]")
            elif el['type'] == 'subheader':
                txt = escape_text(el_text(el)); content_fragments.append(f"[#text(font: \"Manrope\", weight: \"semibold\", size: 18pt)[{txt}]]")
            elif el['type'] == 'body':
                txt = escape_text(el_text(el)); content_fragments.append(f"[#text(font: \"Manrope\")[{txt}]]")
            elif el['type'] == 'rectangle' and el.get('rectangle'):
                rect = el['rectangle']; color = rect['color']; alpha = rect.get('alpha', 1.0)
                content_fragments.append(f"ColorRect(\"{color}\", {alpha})")
            elif el['type'] == 'figure' and el.get('figure'):
                src = el['figure']['src']; cap = el['figure'].get('caption'); fit = el['figure'].get('fit', 'contain')
                if cap:
                    cap_e = escape_text(cap); content_fragments.append(f"Fig(image(\"{src}\", width: 100%, height: 100%, fit: \"{fit}\"), caption: \"{cap_e}\")")
                else:
                    content_fragments.append(f"Fig(image(\"{src}\", width: 100%, height: 100%, fit: \"{fit}\"))")
            elif el['type'] == 'pdf' and el.get('pdf'):
                pdf = el['pdf']; psrc = pdf['src']; ppage = pdf['pages'][0]; scale = pdf.get('scale',1.0)
                content_fragments.append(f"PdfEmbed(\"{psrc}\", page: {ppage}, scale: {scale})")
            frag = ' + '.join(content_fragments) if content_fragments else '""'
            out.append(f"// Element {el['id']} ({el['type']})\n")
            out.append(f"#layer(cw,ch,{x},{y},{wc},{hc}, {frag})\n")
        if ir['meta'].get('GRID_DEBUG', 'false').lower() == 'true':
            out.append(f"#draw_grid({cols}, {rows}, cw, ch)\n")
        out.append("// END PAGE CONTENT\n")
        # Only add pagebreak if this is not the last page
        if page_index < len(ir['pages']) - 1:
            out.append("#pagebreak()\n")
        out.append("\n")
    return '\n'.join(out)

def el_text(el):
    for tb in el.get('text_blocks', []):
        if tb['kind'] == 'plain': return tb['content']
    return el.get('title','')

def escape_text(s):
    return s.replace('\\','\\\\').replace('"','\\"')

def update_html_total(html_path: pathlib.Path, total: int):
    if not html_path.exists():
        return False
    txt = html_path.read_text(encoding='utf-8')
    # Replace only first occurrence of the undefined placeholder.
    new_txt, count = re.subn(r'let total = undefined;', f'let total = {total};', txt, count=1)
    if count == 0:
        # Fallback: look for generic let total = ...;
        new_txt, count2 = re.subn(r'let total = [^;]+;', f'let total = {total};', txt, count=1)
        if count2 == 0:
            return False
        else:
            html_path.write_text(new_txt, encoding='utf-8'); return True
    else:
        html_path.write_text(new_txt, encoding='utf-8'); return True

def adjust_asset_paths(ir, typst_dir: pathlib.Path):
    """
    Rewrite relative asset paths (figure.src, pdf.src) so they are relative to
    the directory containing the Typst file (typst_dir). This allows the
    generated Typst file to live inside an export directory while still
    resolving assets that are stored elsewhere in the project tree.
    """
    try:
        typst_dir = typst_dir.resolve()
    except Exception:
        return
    for page in ir.get('pages', []):
        for el in page.get('elements', []):
            # Figure image
            fig = el.get('figure')
            if fig and fig.get('src'):
                src = fig['src']
                if not os.path.isabs(src) and not re.match(r'^[a-zA-Z]+:', src):
                    abs_candidate = (pathlib.Path.cwd() / src).resolve()
                    try:
                        rel = os.path.relpath(abs_candidate, typst_dir)
                        fig['src'] = rel
                    except Exception:
                        pass
            pdf = el.get('pdf')
            if pdf and pdf.get('src'):
                src = pdf['src']
                if not os.path.isabs(src) and not re.match(r'^[a-zA-Z]+:', src):
                    abs_candidate = (pathlib.Path.cwd() / src).resolve()
                    try:
                        rel = os.path.relpath(abs_candidate, typst_dir)
                        pdf['src'] = rel
                    except Exception:
                        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('org', help='Input org file')
    ap.add_argument('-o','--output', default='deck.typ', help='Output Typst file (relative to export dir if provided)')
    ap.add_argument('--ir', default=None, help='Write IR JSON to path (relative to export dir if provided)')
    ap.add_argument('--update-html', default=None, help='Update HTML viewer page count placeholder (path relative to CWD, not export dir)')
    ap.add_argument('--export-dir', default='export', help='Directory for build artifacts (created if missing)')
    ap.add_argument('--no-clean', action='store_true', help='Keep intermediate Typst file (do not delete after PDF compile)')
    ap.add_argument('--pdf', action='store_true', help='Also compile resulting Typst to PDF')
    ap.add_argument('--pdf-output', default=None, help='PDF output filename (relative to export dir if not absolute). Defaults to <org-stem>.pdf')
    ap.add_argument('--typst-bin', default='typst', help='Path to typst executable')
    args = ap.parse_args()

    export_dir = pathlib.Path(args.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    # Normalize output paths relative to export dir
    output_path = export_dir / args.output if not pathlib.Path(args.output).is_absolute() else pathlib.Path(args.output)
    ir_path = None
    if args.ir:
        ir_path = export_dir / args.ir if not pathlib.Path(args.ir).is_absolute() else pathlib.Path(args.ir)

    ir = parse_org(args.org)
    # Adjust asset paths to be relative to the directory containing the Typst file
    # This ensures references remain valid when compiling from within export dir.
    adjust_asset_paths(ir, pathlib.Path(args.export_dir))
    total_pages = len(ir['pages'])

    if ir_path:
        ir_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ir_path,'w',encoding='utf-8') as f: json.dump(ir,f,indent=2)

    typst_code = generate_typst(ir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path,'w',encoding='utf-8') as f: f.write(typst_code)

    updated = False
    if args.update_html:
        updated = update_html_total(pathlib.Path(args.update_html), total_pages)

    pdf_path = None
    pdf_success = False
    if args.pdf:
        # Determine PDF path
        if args.pdf_output:
            pdf_path = export_dir / args.pdf_output if not pathlib.Path(args.pdf_output).is_absolute() else pathlib.Path(args.pdf_output)
        else:
            org_stem = pathlib.Path(args.org).stem
            pdf_path = export_dir / f"{org_stem}.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        # Invoke typst compile
        try:
            cmd = [args.typst_bin, 'compile', '--font-path', 'assets/fonts', '--font-path', 'assets/fonts/static', str(output_path), str(pdf_path)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                pdf_success = True
            else:
                print(f"ERROR: Typst compile failed (exit {res.returncode}):\n{res.stderr}", file=sys.stderr)
        except FileNotFoundError:
            print(f"ERROR: typst binary not found at '{args.typst_bin}'", file=sys.stderr)
        # Cleanup intermediate if requested
        if pdf_success and not args.no_clean:
            try:
                output_path.unlink()
            except OSError:
                pass
    print(f"Generated {output_path if (args.no_clean or not pdf_success) else '(cleaned)'} with {total_pages} pages. PDF={pdf_success} PDF_path={pdf_path if pdf_path else 'N/A'} HTML updated={updated}")
    if args.pdf and not pdf_success:
        sys.exit(1)

if __name__ == '__main__':
    main()
