"""PDF processing and fallback handling."""

import copy
import math
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict

# Global cache for PDF size calculations (keyed by (path, box_pref))
_pdf_size_cache: dict[tuple[str, str | None], tuple[float, float]] = {}

# Internal cached probe value for effective points-per-inch (pt/in)
_pdf_probe_pt_per_in: float | None = None


def probe_pdf_points_per_inch() -> float:
    """Probe effective PDF points-per-inch.

    Default implementation returns standard 72.0 points-per-inch (PostScript base)
    measurement strategy (e.g. generating a known-size PDF with Typst and
    reading its MediaBox) is implemented. Result cached for subsequent calls.

    Environment override via PAGEMAKER_PDF_PT_PER_IN takes precedence in
    pdf_intrinsic_size_mm; this probe only supplies the default when no env
    override is provided.

    Returns:
        float: points per inch value (positive finite number)
    """
    global _pdf_probe_pt_per_in
    if _pdf_probe_pt_per_in is not None:
        return _pdf_probe_pt_per_in
    try:
        # Future: implement active probing logic / verification.
        _pdf_probe_pt_per_in = 72.0
    except Exception:
        _pdf_probe_pt_per_in = 72.0
    return _pdf_probe_pt_per_in


def pdf_intrinsic_size_mm(path: str, box: str | None = None) -> tuple[float, float]:
    """Return (width_mm, height_mm) of first page of PDF.
    When `box` is provided, prefer that page box ('crop', 'trim', 'bleed', 'art', 'media').
    Otherwise prefers CropBox → TrimBox → BleedBox → ArtBox → MediaBox.
    Falls back to US Letter (612x792pt) when file missing/unreadable.
    Caches results per (path, box_pref) for efficiency so different box
    preferences do not collide.
    """
    if not isinstance(path, str) or path == "":
        return 215.9, 279.4  # letter fallback
    cache_key = (path, box if isinstance(box, str) else None)
    if cache_key in _pdf_size_cache:
        return _pdf_size_cache[cache_key]
    width_pt, height_pt = 612.0, 792.0  # letter default
    try:
        # Try to resolve path - handle both absolute and relative paths
        resolved_path = path
        if not os.path.exists(path):
            # Try from export directory (common case after asset path adjustment)
            export_path = os.path.join(os.getcwd(), 'export', path)
            if os.path.exists(export_path):
                resolved_path = export_path
            else:
                # Try from current working directory
                cwd_path = os.path.join(os.getcwd(), path)
                if os.path.exists(cwd_path):
                    resolved_path = cwd_path
                else:
                    # Path doesn't exist, use fallback dimensions
                    _pdf_size_cache[cache_key] = (width_pt * 25.4 / 72, height_pt * 25.4 / 72)
                    return _pdf_size_cache[cache_key]

        # Read limited chunk to find page box definitions
        with open(resolved_path, 'rb') as fh:
            data = fh.read(300_000)  # slightly larger window for boxes
        # Decode forgivingly
        try:
            txt = data.decode('latin-1', errors='ignore')
        except Exception:
            txt = ''

        # Helper to extract box size
        def _box_size(name: str) -> tuple[float, float] | None:
            m = re.search(
                rf'/{name}\s*\[\s*(-?\d+(?:\.\d*)?)\s+(-?\d+(?:\.\d*)?)\s+(-?\d+(?:\.\d*)?)\s+(-?\d+(?:\.\d*)?)\s*\]',
                txt,
            )
            if not m:
                return None
            try:
                x0, y0, x1, y1 = (float(m.group(i)) for i in range(1, 5))
                w = abs(x1 - x0)
                h = abs(y1 - y0)
                if w > 1 and h > 1 and math.isfinite(w) and math.isfinite(h):
                    return w, h
            except Exception:
                return None
            return None

            # Choose box preference
            preferred = []
            if isinstance(box, str):
                b = box.strip().lower()
                if b == 'media':
                    preferred = ["MediaBox"]
                elif b == 'crop':
                    preferred = ["CropBox", "TrimBox", "BleedBox", "ArtBox", "MediaBox"]
                elif b == 'trim':
                    preferred = ["TrimBox", "CropBox", "BleedBox", "ArtBox", "MediaBox"]
                elif b == 'bleed':
                    preferred = ["BleedBox", "CropBox", "TrimBox", "ArtBox", "MediaBox"]
                elif b == 'art':
                    preferred = ["ArtBox", "CropBox", "TrimBox", "BleedBox", "MediaBox"]
            if not preferred:
                preferred = ["CropBox", "TrimBox", "BleedBox", "ArtBox", "MediaBox"]

            for box_name in preferred:
                sz = _box_size(box_name)
                if sz is not None:
                    width_pt, height_pt = sz
                    break
    except Exception:
        pass
    # Convert points to mm with overrideable points-per-inch.
    raw_env = os.environ.get("PAGEMAKER_PDF_PT_PER_IN", "").strip()
    if raw_env:
        try:
            pt_per_in = float(raw_env)
            if not math.isfinite(pt_per_in) or pt_per_in <= 0:
                pt_per_in = probe_pdf_points_per_inch()
        except Exception:
            pt_per_in = probe_pdf_points_per_inch()
    else:
        pt_per_in = probe_pdf_points_per_inch()
    mm_per_pt = 25.4 / pt_per_in
    width_mm = width_pt * mm_per_pt
    height_mm = height_pt * mm_per_pt
    _pdf_size_cache[cache_key] = (width_mm, height_mm)
    return width_mm, height_mm


def adjust_asset_paths(ir, typst_dir: pathlib.Path):
    """Adjust relative asset paths in IR to be relative to typst_dir.

    Delegates to AssetPathResolver for centralized behavior parity with generator.
    """
    try:
        from ..utils.assets_paths import AssetPathResolver
    except Exception:
        # Fallback to no-op if resolver import fails
        return
    resolver = AssetPathResolver(typst_dir=pathlib.Path(typst_dir))
    resolver.adjust_ir_asset_paths(ir)


def _bin_exists(name: str) -> bool:
    return shutil.which(name) is not None


def make_sanitized_copy(src: pathlib.Path, dst: pathlib.Path) -> bool:
    """Create a sanitized copy of a PDF using qpdf/mutool/ghostscript stages."""
    tmpdir = pathlib.Path(tempfile.mkdtemp(prefix='pm_pdf_'))
    try:
        work_in = src
        # qpdf stage
        qpdf_out = tmpdir / 'q1.pdf'
        if _bin_exists('qpdf'):
            res = subprocess.run(
                [
                    'qpdf',
                    '--stream-data=uncompress',
                    '--recompress-flate',
                    '--object-streams=disable',
                    str(work_in),
                    str(qpdf_out),
                ],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0 and qpdf_out.exists():
                work_in = qpdf_out
        # mutool clean stage
        mutool_out = tmpdir / 'm1.pdf'
        if _bin_exists('mutool'):
            res = subprocess.run(
                ['mutool', 'clean', '-gg', '-d', str(work_in), str(mutool_out)],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0 and mutool_out.exists():
                work_in = mutool_out
        # ghostscript stage
        gs_out = tmpdir / 'g1.pdf'
        if _bin_exists('gs'):
            res = subprocess.run(
                [
                    'gs',
                    '-sDEVICE=pdfwrite',
                    '-dCompatibilityLevel=1.7',
                    '-dPDFSETTINGS=/prepress',
                    '-dNOPAUSE',
                    '-dBATCH',
                    f'-sOutputFile={gs_out}',
                    str(work_in),
                ],
                capture_output=True,
                text=True,
            )
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
                try:
                    p.unlink()
                except OSError:
                    pass
            tmpdir.rmdir()
        except OSError:
            pass


def convert_to_svg(src_pdf: pathlib.Path, out_svg: pathlib.Path, page: int = 1) -> bool:
    """Convert a single PDF page to SVG using mutool."""
    if not _bin_exists('mutool'):
        return False
    res = subprocess.run(
        ['mutool', 'draw', '-F', 'svg', '-o', str(out_svg), str(src_pdf), str(page)],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return False
    return out_svg.exists()


def convert_to_png(
    src_pdf: pathlib.Path, out_png: pathlib.Path, page: int = 1, dpi: int = 160
) -> bool:
    """Convert a single PDF page to PNG using mutool or gs as fallback."""
    if _bin_exists('mutool'):
        res = subprocess.run(
            [
                'mutool',
                'draw',
                '-F',
                'png',
                '-r',
                str(dpi),
                '-o',
                str(out_png),
                str(src_pdf),
                str(page),
            ],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0 and out_png.exists():
            return True
    if _bin_exists('gs'):
        res = subprocess.run(
            [
                'gs',
                '-sDEVICE=pngalpha',
                f'-r{dpi}',
                '-dNOPAUSE',
                '-dBATCH',
                f'-dFirstPage={page}',
                f'-dLastPage={page}',
                f'-sOutputFile={out_png}',
                str(src_pdf),
            ],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0 and out_png.exists():
            return True
    return False


class PDFProcessor:
    """Handles PDF assets, sanitization, and fallback processing."""

    def __init__(self, export_dir: pathlib.Path):
        self.export_dir = export_dir

    def sanitize_pdf(self, pdf_path: pathlib.Path) -> bool:
        return make_sanitized_copy(pdf_path, pdf_path)

    def convert_to_svg(
        self, pdf_path: pathlib.Path, output_path: pathlib.Path, page: int = 1
    ) -> bool:
        return convert_to_svg(pdf_path, output_path, page)

    def convert_to_png(
        self, pdf_path: pathlib.Path, output_path: pathlib.Path, page: int = 1
    ) -> bool:
        return convert_to_png(pdf_path, output_path, page)


def sanitize_pdf_assets(ir: Dict[str, Any], export_dir: pathlib.Path) -> Dict[str, Any]:
    """Apply PDF sanitization to all PDF assets in IR."""
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
                abs_src = pathlib.Path.cwd() / src_path
            abs_src = abs_src.resolve()
            if not abs_src.exists():
                continue
            out_dir = export_dir / 'assets' / 'sanitized-pdfs'
            out_dir.mkdir(parents=True, exist_ok=True)
            sanitized = out_dir / abs_src.name
            if make_sanitized_copy(abs_src, sanitized):
                pdf['src'] = os.path.relpath(sanitized, export_dir)
    return new_ir


def apply_pdf_fallbacks(ir: Dict[str, Any], export_dir: pathlib.Path) -> Dict[str, Any]:
    """Apply SVG/PNG fallbacks for problematic PDFs."""
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
                abs_src = pathlib.Path.cwd() / src_path
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
            if convert_to_svg(abs_src, svg_out, page=pg):
                pdf['src'] = os.path.relpath(svg_out, export_dir)
                continue
            # If SVG fails, try PNG raster fallback
            png_name = f"{abs_src.stem}-p{pg}.png"
            png_out = export_dir / 'assets' / 'pdf-fallbacks' / png_name
            png_out.parent.mkdir(parents=True, exist_ok=True)
            if convert_to_png(abs_src, png_out, page=pg):
                pdf['src'] = os.path.relpath(png_out, export_dir)
    return new_ir
