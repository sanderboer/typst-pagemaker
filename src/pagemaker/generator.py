import datetime, pathlib, os, re, sys, subprocess, json
from .parser import DEFAULTS

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
    out.append("#let PdfEmbed(path, page: 1, scale: 1.0) = {\n  let pdf_data = read(path, encoding: none)\n  let pg = page - 1\n  let muchpdf_image = muchpdf(pdf_data, pages: [pg], scale: scale)\n  block(width: 100%, height: 100%, clip: true)[\n    #muchpdf_image\n  ]\n}\n")
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
    import re
    new_txt, count = re.subn(r'let total = undefined;', f'let total = {total};', txt, count=1)
    if count == 0:
        new_txt, count2 = re.subn(r'let total = [^;]+;', f'let total = {total};', txt, count=1)
        if count2 == 0:
            return False
        else:
            html_path.write_text(new_txt, encoding='utf-8'); return True
    else:
        html_path.write_text(new_txt, encoding='utf-8'); return True

def adjust_asset_paths(ir, typst_dir: pathlib.Path):
    try:
        typst_dir = typst_dir.resolve()
    except Exception:
        return
    for page in ir.get('pages', []):
        for el in page.get('elements', []):
            fig = el.get('figure')
            if fig and fig.get('src'):
                src = fig['src']
                if not os.path.isabs(src) and not re.match(r'^[a-zA-Z]+:', src):
                    abs_candidate = (pathlib.Path.cwd() / src).resolve()
                    try:
                        rel = os.path.relpath(abs_candidate, typst_dir); fig['src'] = rel
                    except Exception:
                        pass
            pdf = el.get('pdf')
            if pdf and pdf.get('src'):
                src = pdf['src']
                if not os.path.isabs(src) and not re.match(r'^[a-zA-Z]+:', src):
                    abs_candidate = (pathlib.Path.cwd() / src).resolve()
                    try:
                        rel = os.path.relpath(abs_candidate, typst_dir); pdf['src'] = rel
                    except Exception:
                        pass
