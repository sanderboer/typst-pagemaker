#!/usr/bin/env python3
"""Unified CLI for pagemaker

Subcommands:
  build     org -> typst (and optional IR export)
  pdf       org -> typst -> pdf
  ir        parse org and emit IR JSON
  validate  parse and validate IR
  watch     rebuild on changes (polling)

"""
import argparse, pathlib, json, sys, subprocess, os, time, hashlib, shutil, tempfile
from . import parse_org, generate_typst, adjust_asset_paths, update_html_total
from .validation import validate_ir

DEFAULT_EXPORT_DIR = 'export'

def _write(path: pathlib.Path, data: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding='utf-8')

def cmd_build(args):
    ir = parse_org(args.org)
    export_dir = pathlib.Path(args.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    adjust_asset_paths(ir, export_dir)
    if args.ir:
        ir_path = export_dir / args.ir if not pathlib.Path(args.ir).is_absolute() else pathlib.Path(args.ir)
        ir_path.parent.mkdir(parents=True, exist_ok=True)
        ir_path.write_text(json.dumps(ir, indent=2), encoding='utf-8')
    out_path = export_dir / args.output if not pathlib.Path(args.output).is_absolute() else pathlib.Path(args.output)
    typst_code = generate_typst(ir)
    _write(out_path, typst_code)
    if args.update_html:
        update_html_total(pathlib.Path(args.update_html), len(ir['pages']))
    print(f"Built Typst: {out_path} pages={len(ir['pages'])}")


def _compile_pdf(typst_file: pathlib.Path, pdf_path: pathlib.Path, typst_bin: str = 'typst') -> bool:
    try:
        project_root = pathlib.Path.cwd()
        cmd = [
            typst_bin,
            'compile',
            '--root', str(project_root),
            '--font-path', 'assets/fonts',
            '--font-path', 'assets/fonts/static',
            str(typst_file),
            str(pdf_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            return True
        else:
            print(f"ERROR: Typst compile failed (exit {res.returncode}):\n{res.stderr}", file=sys.stderr)
    except FileNotFoundError:
        print(f"ERROR: typst binary not found at '{typst_bin}'", file=sys.stderr)
    return False

def _bin_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _make_sanitized_copy(src: pathlib.Path, dst: pathlib.Path) -> bool:
    # Try qpdf repair; mutool clean; ghostscript distill. Writes to dst.
    tmpdir = pathlib.Path(tempfile.mkdtemp(prefix='pm_pdf_'))
    try:
        work_in = src
        # qpdf stage
        qpdf_out = tmpdir / 'q1.pdf'
        if _bin_exists('qpdf'):
            res = subprocess.run(['qpdf', '--stream-data=uncompress', '--recompress-flate', '--object-streams=disable', str(work_in), str(qpdf_out)], capture_output=True, text=True)
            if res.returncode == 0 and qpdf_out.exists():
                work_in = qpdf_out
        # mutool clean stage
        mutool_out = tmpdir / 'm1.pdf'
        if _bin_exists('mutool'):
            res = subprocess.run(['mutool', 'clean', '-gg', '-d', str(work_in), str(mutool_out)], capture_output=True, text=True)
            if res.returncode == 0 and mutool_out.exists():
                work_in = mutool_out
        # ghostscript stage
        gs_out = tmpdir / 'g1.pdf'
        if _bin_exists('gs'):
            res = subprocess.run(['gs', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.7', '-dPDFSETTINGS=/prepress', '-dNOPAUSE', '-dBATCH', f'-sOutputFile={gs_out}', str(work_in)], capture_output=True, text=True)
            if res.returncode == 0 and gs_out.exists():
                work_in = gs_out
        # Finalize to dst
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(pathlib.Path(work_in).read_bytes())
            return True
        except Exception:
            return False
    finally:
        try:
            for p in tmpdir.glob('*'):
                try: p.unlink()
                except OSError: pass
            tmpdir.rmdir()
        except OSError:
            pass


def _convert_pdf_to_svg(src_pdf: pathlib.Path, out_svg: pathlib.Path, page: int = 1) -> bool:
    if not _bin_exists('mutool'):
        return False
    # Render only the requested page to a single SVG
    res = subprocess.run(['mutool', 'draw', '-F', 'svg', '-o', str(out_svg), str(src_pdf), str(page)], capture_output=True, text=True)
    if res.returncode != 0:
        return False
    return out_svg.exists()


def _convert_pdf_to_png(src_pdf: pathlib.Path, out_png: pathlib.Path, page: int = 1, dpi: int = 160) -> bool:
    # Prefer mutool PNG rendering; fallback to Ghostscript pngalpha
    if _bin_exists('mutool'):
        res = subprocess.run(['mutool', 'draw', '-F', 'png', '-r', str(dpi), '-o', str(out_png), str(src_pdf), str(page)], capture_output=True, text=True)
        if res.returncode == 0 and out_png.exists():
            return True
    if _bin_exists('gs'):
        res = subprocess.run(['gs', '-sDEVICE=pngalpha', f'-r{dpi}', '-dNOPAUSE', '-dBATCH', f'-dFirstPage={page}', f'-dLastPage={page}', f'-sOutputFile={out_png}', str(src_pdf)], capture_output=True, text=True)
        if res.returncode == 0 and out_png.exists():
            return True
    return False


def _apply_pdf_sanitized_copies(ir: dict, export_dir: pathlib.Path) -> dict:
    import copy
    new_ir = copy.deepcopy(ir)
    for page in new_ir.get('pages', []):
        for el in page.get('elements', []):
            pdf = el.get('pdf')
            if not pdf or not pdf.get('src'):
                continue
            src_path = pathlib.Path(pdf['src'])
            if src_path.suffix.lower() != '.pdf':
                continue
            abs_src = src_path if src_path.is_absolute() else (export_dir / src_path)
            if not abs_src.exists():
                abs_src = (pathlib.Path.cwd() / src_path)
            abs_src = abs_src.resolve()
            if not abs_src.exists():
                continue
            out_dir = export_dir / 'assets' / 'sanitized-pdfs'
            out_dir.mkdir(parents=True, exist_ok=True)
            sanitized = out_dir / abs_src.name
            if _make_sanitized_copy(abs_src, sanitized):
                pdf['src'] = os.path.relpath(sanitized, export_dir)
    return new_ir


def _apply_pdf_svg_fallbacks(ir: dict, export_dir: pathlib.Path) -> dict:
    import copy
    new_ir = copy.deepcopy(ir)
    for page in new_ir.get('pages', []):
        for el in page.get('elements', []):
            pdf = el.get('pdf')
            if not pdf or not pdf.get('src'):
                continue
            src_path = pathlib.Path(pdf['src'])
            # Only handle PDFs; skip if already not a PDF (e.g., sanitized to SVG/PNG)
            if src_path.suffix.lower() != '.pdf':
                continue
            abs_src = src_path if src_path.is_absolute() else (export_dir / src_path)
            if not abs_src.exists():
                abs_src = (pathlib.Path.cwd() / src_path)
            abs_src = abs_src.resolve()
            if not abs_src.exists():
                continue
            # Determine page (1-based in IR), default 1
            try:
                pg = int(pdf.get('pages', [1])[0])
            except Exception:
                pg = 1
            # Try SVG first
            svg_name = f"{abs_src.stem}-p{pg}.svg"
            svg_out = export_dir / 'assets' / 'pdf-fallbacks' / svg_name
            svg_out.parent.mkdir(parents=True, exist_ok=True)
            if _convert_pdf_to_svg(abs_src, svg_out, page=pg):
                pdf['src'] = os.path.relpath(svg_out, export_dir)
                continue
            # If SVG fails, try PNG raster fallback
            png_name = f"{abs_src.stem}-p{pg}.png"
            png_out = export_dir / 'assets' / 'pdf-fallbacks' / png_name
            png_out.parent.mkdir(parents=True, exist_ok=True)
            if _convert_pdf_to_png(abs_src, png_out, page=pg):
                pdf['src'] = os.path.relpath(png_out, export_dir)
    return new_ir


def _compile_with_fallback(ir: dict, export_dir: pathlib.Path, typst_path: pathlib.Path, pdf_path: pathlib.Path, typst_bin: str, sanitize: bool, no_clean: bool) -> bool:
    def try_compile(with_ir: dict) -> bool:
        typst_code_local = generate_typst(with_ir)
        _write(typst_path, typst_code_local)
        return _compile_pdf(typst_path, pdf_path, typst_bin)

    ok = try_compile(ir)

    if not ok and sanitize:
        print("typst compile failed; trying sanitized PDFs...", file=sys.stderr)
        ir_sanitized = _apply_pdf_sanitized_copies(ir, export_dir)
        ok = try_compile(ir_sanitized)
        if not ok:
            print("still failing; trying SVG fallbacks for PDFs...", file=sys.stderr)
            ir_svg = _apply_pdf_svg_fallbacks(ir_sanitized, export_dir)
            ok = try_compile(ir_svg)

    if ok and not no_clean:
        try: typst_path.unlink()
        except OSError: pass
    return ok


def cmd_pdf(args):
    ir = parse_org(args.org)
    export_dir = pathlib.Path(args.export_dir); export_dir.mkdir(parents=True, exist_ok=True)
    adjust_asset_paths(ir, export_dir)
    typst_filename = args.output if args.output else 'deck.typ'
    typst_path = export_dir / typst_filename if not pathlib.Path(typst_filename).is_absolute() else pathlib.Path(typst_filename)
    pdf_out = args.pdf_output or f"{pathlib.Path(args.org).stem}.pdf"
    pdf_path = export_dir / pdf_out if not pathlib.Path(pdf_out).is_absolute() else pathlib.Path(pdf_out)

    ok = _compile_with_fallback(
        ir=ir,
        export_dir=export_dir,
        typst_path=typst_path,
        pdf_path=pdf_path,
        typst_bin=args.typst_bin,
        sanitize=getattr(args, 'sanitize_pdfs', False),
        no_clean=args.no_clean,
    )

    print(f"PDF build success={ok} pdf={pdf_path} pages={len(ir['pages'])}")
    if not ok:
        sys.exit(1)


def cmd_ir(args):
    ir = parse_org(args.org)
    print(json.dumps(ir, indent=2))


def cmd_validate(args):
    ir = parse_org(args.org)
    result = validate_ir(ir, strict_assets=args.strict_assets)
    for issue in result.issues:
        print(f"{issue.severity.upper()}: {issue.path}: {issue.message}")
    if result.ok():
        print("IR valid: no errors")
    if not result.ok():
        sys.exit(1)


def cmd_watch(args):
    org_path = pathlib.Path(args.org)
    if not org_path.exists():
        print(f"ERROR: org file not found: {org_path}", file=sys.stderr)
        sys.exit(1)
    export_dir = pathlib.Path(args.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    last_hash = None
    print(f"Watching {org_path} interval={args.interval}s pdf={args.pdf} (once={args.once})")
    def compute_hash(p: pathlib.Path):
        try:
            data = p.read_bytes(); return hashlib.sha256(data).hexdigest()
        except Exception:
            return None
    def build_once():
        ir = parse_org(str(org_path))
        adjust_asset_paths(ir, export_dir)
        if args.update_html:
            update_html_total(pathlib.Path(args.update_html), len(ir['pages']))
        typst_filename = args.output
        typst_path = export_dir / typst_filename if not pathlib.Path(typst_filename).is_absolute() else pathlib.Path(typst_filename)
        if args.pdf:
            pdf_out = args.pdf_output or f"{org_path.stem}.pdf"
            pdf_path = export_dir / pdf_out if not pathlib.Path(pdf_out).is_absolute() else pathlib.Path(pdf_out)
            ok = _compile_with_fallback(
                ir=ir,
                export_dir=export_dir,
                typst_path=typst_path,
                pdf_path=pdf_path,
                typst_bin=args.typst_bin,
                sanitize=getattr(args, 'sanitize_pdfs', False),
                no_clean=args.no_clean,
            )
            print(f"[watch] Rebuilt PDF success={ok} pages={len(ir['pages'])}")
            return ok
        else:
            typst_code = generate_typst(ir)
            _write(typst_path, typst_code)
            print(f"[watch] Rebuilt Typst pages={len(ir['pages'])}")
            return True
    while True:
        h = compute_hash(org_path)
        if h and h != last_hash:
            last_hash = h
            try:
                ok = build_once()
                if not ok and args.once:
                    sys.exit(1)
            except Exception as e:
                print(f"[watch] ERROR during build: {e}", file=sys.stderr)
                if args.once:
                    sys.exit(1)
            if args.once:
                break
        if args.once:
            # File hash didn't change but in --once mode ensure we build at least once
            if last_hash is None:
                try:
                    ok = build_once()
                    if not ok:
                        sys.exit(1)
                    print(f"[watch] Initial build complete")
                except Exception as e:
                    print(f"[watch] ERROR during initial build: {e}", file=sys.stderr)
                    sys.exit(1)
            break
        time.sleep(args.interval)

def build_parser():
    p = argparse.ArgumentParser(prog='pagemaker')
    sub = p.add_subparsers(dest='command', required=True)

    b = sub.add_parser('build', help='org -> typst')
    b.add_argument('org'); b.add_argument('-o','--output', default='deck.typ'); b.add_argument('--ir'); b.add_argument('--update-html'); b.add_argument('--export-dir', default=DEFAULT_EXPORT_DIR)
    b.set_defaults(func=cmd_build)

    pdf = sub.add_parser('pdf', help='org -> typst -> pdf')
    pdf.add_argument('org'); pdf.add_argument('-o','--output', default='deck.typ'); pdf.add_argument('--pdf-output'); pdf.add_argument('--typst-bin', default='typst'); pdf.add_argument('--export-dir', default=DEFAULT_EXPORT_DIR); pdf.add_argument('--no-clean', action='store_true'); pdf.add_argument('--sanitize-pdfs', action='store_true', help='Attempt to sanitize PDFs and fallback to SVG if necessary')
    pdf.set_defaults(func=cmd_pdf)

    irp = sub.add_parser('ir', help='emit IR JSON')
    irp.add_argument('org'); irp.set_defaults(func=cmd_ir)

    val = sub.add_parser('validate', help='validate IR')
    val.add_argument('org'); val.add_argument('--strict-assets', action='store_true', help='Treat missing figure/pdf assets as errors'); val.set_defaults(func=cmd_validate)
 
    watch = sub.add_parser('watch', help='watch org file and rebuild on change')
    watch.add_argument('org')
    watch.add_argument('-o','--output', default='deck.typ')
    watch.add_argument('--export-dir', default=DEFAULT_EXPORT_DIR)
    watch.add_argument('--interval', type=float, default=1.0)
    watch.add_argument('--pdf', action='store_true')
    watch.add_argument('--pdf-output')
    watch.add_argument('--typst-bin', default='typst')
    watch.add_argument('--no-clean', action='store_true')
    watch.add_argument('--update-html')
    watch.add_argument('--once', action='store_true', help='Run single build then exit (for testing)')
    watch.add_argument('--sanitize-pdfs', action='store_true', help='Attempt to sanitize PDFs and fallback to SVG if necessary')
    watch.set_defaults(func=cmd_watch)
 
    return p


def main(argv=None):
    parser = build_parser(); args = parser.parse_args(argv); args.func(args)

if __name__ == '__main__':
    main()
