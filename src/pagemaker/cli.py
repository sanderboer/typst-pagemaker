#!/usr/bin/env python3
"""Unified CLI for pagemaker

Subcommands:
  build     org -> typst (and optional IR export)
  pdf       org -> typst -> pdf
  ir        parse org and emit IR JSON
  validate  parse and validate IR

Legacy single-script interface still exists in gen_typst.py and will be
deprecated in favor of `python -m pagemaker.cli <subcommand>` (or future
installed entry point).
"""
import argparse, pathlib, json, sys, subprocess, os
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
        cmd = [typst_bin, 'compile', '--font-path', 'assets/fonts', '--font-path', 'assets/fonts/static', str(typst_file), str(pdf_path)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            return True
        else:
            print(f"ERROR: Typst compile failed (exit {res.returncode}):\n{res.stderr}", file=sys.stderr)
    except FileNotFoundError:
        print(f"ERROR: typst binary not found at '{typst_bin}'", file=sys.stderr)
    return False

def cmd_pdf(args):
    ir = parse_org(args.org)
    export_dir = pathlib.Path(args.export_dir); export_dir.mkdir(parents=True, exist_ok=True)
    adjust_asset_paths(ir, export_dir)
    typst_filename = args.output if args.output else 'deck.typ'
    typst_path = export_dir / typst_filename if not pathlib.Path(typst_filename).is_absolute() else pathlib.Path(typst_filename)
    typst_code = generate_typst(ir)
    _write(typst_path, typst_code)
    pdf_out = args.pdf_output or f"{pathlib.Path(args.org).stem}.pdf"
    pdf_path = export_dir / pdf_out if not pathlib.Path(pdf_out).is_absolute() else pathlib.Path(pdf_out)
    ok = _compile_pdf(typst_path, pdf_path, args.typst_bin)
    if ok and not args.no_clean:
        try: typst_path.unlink()
        except OSError: pass
    print(f"PDF build success={ok} pdf={pdf_path} pages={len(ir['pages'])}")
    if not ok:
        sys.exit(1)


def cmd_ir(args):
    ir = parse_org(args.org)
    print(json.dumps(ir, indent=2))


def cmd_validate(args):
    ir = parse_org(args.org)
    result = validate_ir(ir)
    if result.ok():
        print("IR valid: no errors")
    else:
        for issue in result.issues:
            print(f"{issue.severity.upper()}: {issue.path}: {issue.message}")
    if not result.ok():
        sys.exit(1)


def build_parser():
    p = argparse.ArgumentParser(prog='pagemaker')
    sub = p.add_subparsers(dest='command', required=True)

    b = sub.add_parser('build', help='org -> typst')
    b.add_argument('org'); b.add_argument('-o','--output', default='deck.typ'); b.add_argument('--ir'); b.add_argument('--update-html'); b.add_argument('--export-dir', default=DEFAULT_EXPORT_DIR)
    b.set_defaults(func=cmd_build)

    pdf = sub.add_parser('pdf', help='org -> typst -> pdf')
    pdf.add_argument('org'); pdf.add_argument('-o','--output', default='deck.typ'); pdf.add_argument('--pdf-output'); pdf.add_argument('--typst-bin', default='typst'); pdf.add_argument('--export-dir', default=DEFAULT_EXPORT_DIR); pdf.add_argument('--no-clean', action='store_true')
    pdf.set_defaults(func=cmd_pdf)

    irp = sub.add_parser('ir', help='emit IR JSON')
    irp.add_argument('org'); irp.set_defaults(func=cmd_ir)

    val = sub.add_parser('validate', help='validate IR')
    val.add_argument('org'); val.set_defaults(func=cmd_validate)

    return p


def main(argv=None):
    parser = build_parser(); args = parser.parse_args(argv); args.func(args)

if __name__ == '__main__':
    main()
