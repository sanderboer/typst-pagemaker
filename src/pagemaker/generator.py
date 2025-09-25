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
    out.append(TYPST_HEADER.format(timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()))
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
    # Dynamic date and page helpers
    # Prefer reproducible date from meta: DATE_OVERRIDE or DATE (YYYY-MM-DD). Fallback to today.
    d = None
    try:
        meta = ir.get('meta') or {}
        ds = (meta.get('DATE_OVERRIDE') or meta.get('DATE') or '').strip()
        if ds:
            ds_norm = ds.replace('/', '-').replace('.', '-')
            d = datetime.date.fromisoformat(ds_norm)
    except Exception:
        d = None
    if d is None:
        d = datetime.date.today()
    yy = d.strftime('%y'); mm = d.strftime('%m'); dd = d.strftime('%d'); y4 = d.strftime('%Y')
    iso = f"{y4}-{mm}-{dd}"
    out.append(f"#let date_iso = \"{iso}\"\n")
    out.append(f"#let date_yy_mm_dd = \"{yy}.{mm}.{dd}\"\n")
    out.append(f"#let date_dd_mm_yy = \"{dd}.{mm}.{yy}\"\n")
    out.append("#let page_no = context counter(page).display()\n")
    out.append("#let page_total = context counter(page).final().at(0)\n")
    out.append("#let Fig(img, caption: none) = if caption == none { \n  block(width: 100%, height: 100%, clip: true)[#img] \n} else { \n  block(width: 100%, height: 100%)[\n    #block(height: 85%, clip: true)[#img] \n    #block(height: 15%)[#text(size: 0.75em, fill: rgb(60%,60%,60%))[caption]] \n  ] \n}\n")
    out.append("#let ColorRect(color, alpha) = {\n  block(width: 100%, height: 100%, fill: rgb(color).transparentize(100% - alpha * 100%))[]\n}\n")
    out.append("#let PdfEmbed(path, page: 1, scale: 1.0) = {\n  let pdf_data = read(path, encoding: none)\n  let pg = page - 1\n  let muchpdf_image = muchpdf(pdf_data, pages: pg, scale: scale)\n  block(width: 100%, height: 100%, clip: true)[\n    #muchpdf_image\n  ]\n}\n")
    out.append("#let layer(cw, ch, x, y, w, h, body) = place(\n  dx: (x - 1) * cw,\n  dy: (y - 1) * ch,\n  block(\n    width: w * cw,\n    height: h * ch,\n    body\n  )\n)\n")
    out.append("#let layer_mm(cw, ch, left_mm, top_mm, x, y, w, h, body) = place(\n  dx: left_mm + (x - 1) * cw,\n  dy: top_mm + (y - 1) * ch,\n  block(\n    width: w * cw,\n    height: h * ch,\n    body\n  )\n)\n")
    out.append("""#let draw_grid(cols, rows, cw, ch) = {
  // grid lines
  for col in range(1, cols + 1) {
    place(line(start: ((col - 1) * cw, 0pt), end: ((col - 1) * cw, rows * ch), stroke: 0.5pt + rgb("#ccc")))
  }
  for row in range(1, rows + 1) {
    place(line(start: (0pt, (row - 1) * ch), end: (cols * cw, (row - 1) * ch), stroke: 0.5pt + rgb("#ccc")))
  }
  // column labels on top
  for col in range(1, cols + 1) {
    place(dx: (col - 1) * cw + 2pt, dy: 2pt, text(size: 8pt, fill: rgb("#888"))[#col])
  }
  // row labels on left (lowercase)
  let letters = ("a","b","c","d","e","f","g","h","i","j","k","l","m","n","o","p","q","r","s","t","u","v","w","x","y","z")
  for row in range(1, rows + 1) {
    let label = if row <= 26 { letters.at(row - 1) } else { str(row) }
    place(dx: 2pt, dy: (row - 1) * ch + 2pt, text(size: 8pt, fill: rgb("#888"))[#label])
  }
}
""")
    out.append("""#let draw_grid_offset(cols, rows, cw, ch, dx, dy) = {
  // grid lines with offset
  for col in range(1, cols + 1) {
    place(line(start: (dx + (col - 1) * cw, dy), end: (dx + (col - 1) * cw, dy + rows * ch), stroke: 0.5pt + rgb("#ccc")))
  }
  for row in range(1, rows + 1) {
    place(line(start: (dx, dy + (row - 1) * ch), end: (dx + cols * cw, dy + (row - 1) * ch), stroke: 0.5pt + rgb("#ccc")))
  }
  // column labels on top
  for col in range(1, cols + 1) {
    place(dx: dx + (col - 1) * cw + 2pt, dy: dy + 2pt, text(size: 8pt, fill: rgb("#888"))[#col])
  }
  // row labels on left (lowercase)
  let letters = ("a","b","c","d","e","f","g","h","i","j","k","l","m","n","o","p","q","r","s","t","u","v","w","x","y","z")
  for row in range(1, rows + 1) {
    let label = if row <= 26 { letters.at(row - 1) } else { str(row) }
    place(dx: dx + 2pt, dy: dy + (row - 1) * ch + 2pt, text(size: 8pt, fill: rgb("#888"))[#label])
  }
}
""")
    out.append("""// Variable-track grid helpers (support mm-sized outer tracks)
#let col_width(i, gp) = if i <= gp.lc { if gp.lc == 0 { 0mm } else { gp.lm / gp.lc } } else if i <= gp.lc + gp.cc { gp.cw } else { if gp.rc == 0 { 0mm } else { gp.rm / gp.rc } }
#let row_height(j, gp) = if j <= gp.lr { if gp.lr == 0 { 0mm } else { gp.tm / gp.lr } } else if j <= gp.lr + gp.cr { gp.ch } else { if gp.br == 0 { 0mm } else { gp.bm / gp.br } }
#let sum_cols(from, count, gp) = {
  let total = 0mm
  if count <= 0 { return total }
  for i in range(from, from + count) { total = total + col_width(i, gp) }
  total
}
#let sum_rows(from, count, gp) = {
  let total = 0mm
  if count <= 0 { return total }
  for j in range(from, from + count) { total = total + row_height(j, gp) }
  total
}
#let layer_grid(gp, x, y, w, h, body) = place(
  dx: sum_cols(1, x - 1, gp),
  dy: sum_rows(1, y - 1, gp),
  block(width: sum_cols(x, w, gp), height: sum_rows(y, h, gp), body)
)
#let layer_grid_padded(gp, x, y, w, h, top, right, bottom, left, body) = {
  let dx = sum_cols(1, x - 1, gp) + left
  let dy = sum_rows(1, y - 1, gp) + top
  let frame_w = sum_cols(x, w, gp) - left - right
  let frame_h = sum_rows(y, h, gp) - top - bottom
  if frame_w < 0mm { frame_w = 0mm }
  if frame_h < 0mm { frame_h = 0mm }
  place(dx: dx, dy: dy, block(width: frame_w, height: frame_h, body))
}
#let draw_total_grid(gp) = {
  let tot_cols = gp.lc + gp.cc + gp.rc
  let tot_rows = gp.lr + gp.cr + gp.br
  // vertical lines
  for col in range(1, tot_cols + 1) {
    place(line(start: (sum_cols(1, col - 1, gp), 0mm), end: (sum_cols(1, col - 1, gp), sum_rows(1, tot_rows, gp)), stroke: 0.5pt + rgb("#ccc")))
  }
  // horizontal lines
  for row in range(1, tot_rows + 1) {
    place(line(start: (0mm, sum_rows(1, row - 1, gp)), end: (sum_cols(1, tot_cols, gp), sum_rows(1, row - 1, gp)), stroke: 0.5pt + rgb("#ccc")))
  }
  // total column labels on top (include margin tracks)
  for col in range(1, tot_cols + 1) {
    place(dx: sum_cols(1, col - 1, gp) + 2pt, dy: 2pt, text(size: 8pt, fill: rgb("#888"))[#col])
  }
  // total row labels on left (lowercase, include margin tracks)
  let letters = ("a","b","c","d","e","f","g","h","i","j","k","l","m","n","o","p","q","r","s","t","u","v","w","x","y","z")
  for row in range(1, tot_rows + 1) {
    let label = if row <= 26 { letters.at(row - 1) } else { str(row) }
    place(dx: 2pt, dy: sum_rows(1, row - 1, gp) + 2pt, text(size: 8pt, fill: rgb("#888"))[#label])
  }
}
""")

    # Build map of master definitions: name -> list of elements
    masters = {}
    for p in ir.get('pages', []):
        mname = (p.get('master_def') or '').strip()
        if mname:
            masters[mname] = list(p.get('elements', []))

    # Determine pages to actually render (skip pure master-def pages)
    render_pages = [p for p in ir.get('pages', []) if not (p.get('master_def') or '').strip()]

    for page_index, page in enumerate(render_pages):
        w = page['page_size']['w_mm']; h = page['page_size']['h_mm']
        cols = page['grid']['cols']; rows = page['grid']['rows']
        margins_mm = page.get('margins_mm')
        margins_declared = bool(page.get('margins_declared')) and isinstance(margins_mm, dict)
        # Determine total grid for debug drawing when no margins declared
        total_cols = cols + (2 if margins_declared else 0)
        total_rows = rows + (2 if margins_declared else 0)
        # Extract mm values (0 when not declared)
        top_mm = float((margins_mm or {}).get('top', 0.0))
        right_mm = float((margins_mm or {}).get('right', 0.0))
        bottom_mm = float((margins_mm or {}).get('bottom', 0.0))
        left_mm = float((margins_mm or {}).get('left', 0.0))
        out.append(f"// Page {page_index+1}: {page['title']}\n")
        out.append(f"#set page(width: {w}mm, height: {h}mm, margin: 0mm)\n")
        if margins_declared:
            # Compute content cell sizes using page minus absolute margins
            out.append(f"#let cw = ({w}mm - ({left_mm}mm + {right_mm}mm)) / {cols}\n")
            out.append(f"#let ch = ({h}mm - ({top_mm}mm + {bottom_mm}mm)) / {rows}\n")
            # Total grid params: one margin track per side
            out.append(
                f"#let gp = (lc: 1, rc: 1, lr: 1, br: 1, cc: {cols}, cr: {rows}, lm: {left_mm}mm, rm: {right_mm}mm, tm: {top_mm}mm, bm: {bottom_mm}mm, cw: cw, ch: ch)\n"
            )
        else:
            # No margins: total grid equals content grid; tracks are uniform
            out.append(f"#let cw = {w}mm / {cols}\n#let ch = {h}mm / {rows}\n")
            out.append(
                f"#let gp = (lc: 0, rc: 0, lr: 0, br: 0, cc: {cols}, cr: {rows}, lm: 0mm, rm: 0mm, tm: 0mm, bm: 0mm, cw: cw, ch: ch)\n"
            )
        out.append("// BEGIN PAGE CONTENT\n")
        # Combine master elements (if any) with page elements
        combined_elements = []
        mref = (page.get('master') or '').strip()
        if not mref and (ir.get('meta') or {}).get('DEFAULT_MASTER'):
            mref = (ir['meta'].get('DEFAULT_MASTER') or '').strip()
        if mref and mref in masters:
            combined_elements.extend(masters[mref])
        combined_elements.extend(page.get('elements', []))
        elements = sorted(combined_elements, key=lambda e: e.get('z',100))
        for el in elements:
            area = el['area'] or {'x':1,'y':1,'w':cols,'h':1}
            x,y,wc,hc = area['x'], area['y'], area['w'], area['h']
            # Always interpret AREA in total grid coordinates.
            x_total = x
            y_total = y
            # Validate bounds against total grid when margins exist, else content grid.
            limit_cols = (total_cols if margins_declared else cols)
            limit_rows = (total_rows if margins_declared else rows)
            out_of_bounds = (x < 1 or y < 1 or wc < 1 or hc < 1 or (x + wc - 1) > limit_cols or (y + hc - 1) > limit_rows)
            if out_of_bounds:
                print(
                    f"WARNING: AREA out-of-bounds for element {el['id']} on page {page['title']}: ({x},{y},{wc},{hc})",
                    file=sys.stderr,
                )
            content_fragments = []
            if el['type'] == 'header':
                txt = escape_text(el_text(el))
                if el.get('justify'):
                    content_fragments.append(f"[#par(justify: true)[#text(font: \"Manrope\", weight: \"bold\", size: 24pt)[{txt}]]]")
                else:
                    content_fragments.append(f"[#text(font: \"Manrope\", weight: \"bold\", size: 24pt)[{txt}]]")
            elif el['type'] == 'subheader':
                txt = escape_text(el_text(el))
                if el.get('justify'):
                    content_fragments.append(f"[#par(justify: true)[#text(font: \"Manrope\", weight: \"semibold\", size: 18pt)[{txt}]]]")
                else:
                    content_fragments.append(f"[#text(font: \"Manrope\", weight: \"semibold\", size: 18pt)[{txt}]]")
            elif el['type'] == 'body':
                txt = escape_text(el_text(el))
                if el.get('justify'):
                    content_fragments.append(f"[#par(justify: true)[#text(font: \"Manrope\")[{txt}]]]")
                else:
                    content_fragments.append(f"[#text(font: \"Manrope\")[{txt}]]")
            elif el['type'] == 'rectangle' and el.get('rectangle'):
                rect = el['rectangle']; color = rect['color']; alpha = rect.get('alpha', 1.0)
                content_fragments.append(f"ColorRect(\"{color}\", {alpha})")
            elif el['type'] == 'figure' and el.get('figure'):
                src = el['figure']['src']; cap = el['figure'].get('caption'); fit = el['figure'].get('fit', 'contain')
                fit_map = {'fill':'cover', 'contain':'contain', 'cover':'cover', 'stretch':'stretch'}
                fit_val = fit_map.get(str(fit).lower(), str(fit))
                if cap:
                    cap_e = escape_text(cap); content_fragments.append(f"Fig(image(\"{src}\", width: 100%, height: 100%, fit: \"{fit_val}\"), caption: \"{cap_e}\")")
                else:
                    content_fragments.append(f"Fig(image(\"{src}\", width: 100%, height: 100%, fit: \"{fit_val}\"))")
            elif el['type'] == 'svg' and el.get('svg'):
                svg = el['svg']; ssrc = svg.get('src');
                # Render SVG via image fit contain into the frame
                content_fragments.append(f"Fig(image(\"{ssrc}\", width: 100%, height: 100%, fit: \"contain\"))")
            elif el['type'] == 'pdf' and el.get('pdf'):
                pdf = el['pdf']; psrc = pdf['src']; ppage = pdf['pages'][0]; scale = pdf.get('scale',1.0)
                if pathlib.Path(psrc).suffix.lower() != '.pdf':
                    content_fragments.append(f"Fig(image(\"{psrc}\", width: 100%, height: 100%, fit: \"contain\"))")
                else:
                    content_fragments.append(f"PdfEmbed(\"{psrc}\", page: {ppage}, scale: {scale})")
            elif el['type'] == 'toc':
                # Minimal TOC: bullet list of page titles
                bullets = []
                for rp in render_pages:
                    title = escape_text(rp.get('title', ''))
                    bullets.append(f"• {title}")
                toc_text = "\\n".join(bullets)
                content_fragments.append(f"[#text(font: \"Manrope\")[{toc_text}]]")
            frag = ' + '.join(content_fragments) if content_fragments else '""'
            out.append(f"// Element {el['id']} ({el['type']})\n")
            # Place elements with padding when specified (text, figure, svg, pdf, toc)
            pad = el.get('padding_mm') if isinstance(el, dict) else None
            if el.get('type') in ('header','subheader','body','figure','svg','pdf','toc') and isinstance(pad, dict):
                t = float(pad.get('top', 0.0)); r = float(pad.get('right', 0.0)); b = float(pad.get('bottom', 0.0)); l = float(pad.get('left', 0.0))
                out.append(f"#layer_grid_padded(gp,{x_total},{y_total},{wc},{hc}, {t}mm, {r}mm, {b}mm, {l}mm, {frag})\n")
            else:
                # Always place via total grid helper
                out.append(f"#layer_grid(gp,{x_total},{y_total},{wc},{hc}, {frag})\n")
        if ir['meta'].get('GRID_DEBUG', 'false').lower() == 'true':
            if margins_declared:
                out.append(f"#draw_total_grid(gp)\n")
            else:
                out.append(f"#draw_grid({cols}, {rows}, cw, ch)\n")
        out.append("// END PAGE CONTENT\n")
        if page_index < len(render_pages) - 1:
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
    # Determine project root relative to this module (../../)
    try:
        project_root = pathlib.Path(__file__).resolve().parents[2]
    except Exception:
        project_root = pathlib.Path.cwd()
    def resolve_rel(src: str) -> str:
        if os.path.isabs(src) or re.match(r'^[a-zA-Z]+:', src):
            return src
        # Try project root first
        candidates = [
            (project_root / src),
            (typst_dir / src),
            (pathlib.Path.cwd() / src),
        ]
        for cand in candidates:
            try:
                c = cand.resolve()
            except Exception:
                continue
            if c.exists() or True:
                # Even if not existing, rewrite relative to export dir deterministically
                try:
                    return os.path.relpath(c, typst_dir)
                except Exception:
                    continue
        return src
    for page in ir.get('pages', []):
        for el in page.get('elements', []):
            fig = el.get('figure')
            if fig and fig.get('src'):
                fig['src'] = resolve_rel(fig['src'])
            pdf = el.get('pdf')
            if pdf and pdf.get('src'):
                pdf['src'] = resolve_rel(pdf['src'])
            svg = el.get('svg')
            if svg and svg.get('src'):
                svg['src'] = resolve_rel(svg['src'])
