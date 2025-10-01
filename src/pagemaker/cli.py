#!/usr/bin/env python3
"""Unified CLI for typst-pagemaker

Subcommands:
  build     org -> typst (and optional IR export)
  pdf       org -> typst -> pdf
  ir        parse org and emit IR JSON
  validate  parse and validate IR
  watch     rebuild on changes (polling)
  fonts     font discovery and management utilities

"""

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

from . import adjust_asset_paths, generate_typst, parse_org, update_html_total
from .fonts import (
    _collect_real_font_names,
    _format_size,
    _get_bundled_fonts,
    _get_font_paths,
    _get_project_fonts,
)
from .validation import validate_ir

DEFAULT_EXPORT_DIR = 'export'

# Shared helper: collect real font family names via fontTools (with TTC support)
# Returns a set of family names found across provided paths. Empty set when fontTools missing.
# Only TTF/OTF/TTC/OTC are considered (Typst-usable font formats).


def _get_google_fonts_api_data() -> dict:
    """Fetch Google Fonts API data. Returns cached data or fetches from API."""
    cache_dir = pathlib.Path.home() / '.pagemaker' / 'cache'
    cache_file = cache_dir / 'google_fonts.json'

    # Check cache freshness (24 hours)
    if cache_file.exists():
        cache_age = time.time() - cache_file.stat().st_mtime
        if cache_age < 86400:  # 24 hours
            try:
                return json.loads(cache_file.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, OSError):
                pass

    # Fetch from Google Fonts API
    api_url = 'https://www.googleapis.com/webfonts/v1/webfonts?sort=popularity'
    try:
        with urllib.request.urlopen(api_url, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        # Cache the result
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
        return data

    except Exception as e:
        print(f"⚠️  Failed to fetch Google Fonts data: {e}", file=sys.stderr)
        print("Using offline fallback list...", file=sys.stderr)

        # Fallback list of popular fonts
        return {
            'items': [
                {
                    'family': 'Inter',
                    'variants': ['regular', '700'],
                    'files': {
                        'regular': 'https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hiA.ttf',
                        '700': 'https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuBWYAZ9hiA.ttf',
                    },
                },
                {
                    'family': 'Roboto',
                    'variants': ['regular', '700'],
                    'files': {
                        'regular': 'https://fonts.gstatic.com/s/roboto/v30/KFOmCnqEu92Fr1Mu4mxK.ttf',
                        '700': 'https://fonts.gstatic.com/s/roboto/v30/KFOlCnqEu92Fr1MmWUlfBBc4.ttf',
                    },
                },
                {
                    'family': 'Open Sans',
                    'variants': ['regular', '700'],
                    'files': {
                        'regular': 'https://fonts.gstatic.com/s/opensans/v34/memSYaGs126MiZpBA-UvWbX2vVnXBbObj2OVZyOOSr4dVJWUgsg-1x4gaVQ.ttf',
                        '700': 'https://fonts.gstatic.com/s/opensans/v34/memSYaGs126MiZpBA-UvWbX2vVnXBbObj2OVZyOOSr4dVJWUgsjZ1x4gaVQ.ttf',
                    },
                },
                {
                    'family': 'Lora',
                    'variants': ['regular'],
                    'files': {
                        'regular': 'https://fonts.gstatic.com/s/lora/v26/0QI6MX1D_JOuGQbT0gvTJPa787weuxJBkqsxzqExlA.ttf'
                    },
                },
                {
                    'family': 'Playfair Display',
                    'variants': ['regular'],
                    'files': {
                        'regular': 'https://fonts.gstatic.com/s/playfairdisplay/v30/nuFvD-vYSZviVYUb_rj3ij__anPXJzDwcbmjWBN2PKdFvXDXbtXK-F2qC0s.ttf'
                    },
                },
            ]
        }


def _download_font_file(url: str, dest_path: pathlib.Path) -> bool:
    """Download a font file from URL to destination"""
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        with urllib.request.urlopen(url, timeout=30) as response:
            if response.status == 200:
                dest_path.write_bytes(response.read())
                return True
        return False

    except Exception as e:
        print(f"  ❌ Failed to download {url}: {e}", file=sys.stderr)
        return False


def _install_google_font(font_family: str, variants=None, force: bool = False) -> bool:
    """Install a Google Font to assets/fonts/"""
    assets_fonts = pathlib.Path('assets/fonts')
    font_dir = assets_fonts / font_family

    # Check if already installed
    if font_dir.exists() and not force:
        existing_files = list(font_dir.glob('*.ttf')) + list(font_dir.glob('*.otf'))
        if existing_files:
            print(f"✅ Font '{font_family}' already installed ({len(existing_files)} files)")
            return True

    # Get Google Fonts data
    fonts_data = _get_google_fonts_api_data()

    # Find the font
    font_info = None
    for font in fonts_data.get('items', []):
        if font['family'].lower() == font_family.lower():
            font_info = font
            break

    if not font_info:
        print(f"❌ Font '{font_family}' not found in Google Fonts")
        return False

    # Determine variants to download
    available_variants = list(font_info.get('files', {}).keys())
    if not variants:
        # Default to common variants
        variants = ['regular']
        if '700' in available_variants:
            variants.append('700')
        if 'italic' in available_variants:
            variants.append('italic')

    # Filter to available variants
    variants = [v for v in variants if v in available_variants]
    if not variants:
        print(f"❌ No valid variants found for '{font_family}'")
        print(f"Available: {', '.join(available_variants)}")
        return False

    print(f"📥 Installing '{font_family}' variants: {', '.join(variants)}")

    # Download variants
    success_count = 0
    for variant in variants:
        url = font_info['files'][variant]

        # Generate filename
        if variant == 'regular':
            filename = f"{font_family.replace(' ', '')}-Regular.ttf"
        elif variant.isdigit():
            filename = f"{font_family.replace(' ', '')}-{variant}.ttf"
        else:
            filename = f"{font_family.replace(' ', '')}-{variant.title()}.ttf"

        dest_path = font_dir / filename

        print(f"  📁 {filename}...", end=' ')
        if _download_font_file(url, dest_path):
            size = _format_size(dest_path.stat().st_size)
            print(f"✅ ({size})")
            success_count += 1
        else:
            print("❌")

    if success_count > 0:
        print(f"✅ Installed {success_count}/{len(variants)} variants of '{font_family}'")
        return True
    else:
        print(f"❌ Failed to install '{font_family}'")
        return False


def _analyze_font_usage(ir: dict) -> dict:
    """Analyze which fonts are referenced in the IR.

    Sources scanned:
    - CUSTOM_STYLE meta/header blocks (quoted font names)
    - STYLE_* meta declarations (quoted or unquoted font: ...)
    - Global FONT meta directive
    - Inline Typst directives in element content (#set text(font: "..."))
    """
    font_usage = {'fonts_found': set(), 'missing_fonts': set(), 'usage_locations': []}

    meta = ir.get('meta', {}) or {}

    # 1) CUSTOM_STYLE headers (quoted fonts inside the style string)
    custom_style = ir.get('custom_style', '') or meta.get('CUSTOM_STYLE', '')
    for font_name in re.findall(r'font:\s*"([^"]+)"', custom_style):
        if font_name:
            font_usage['fonts_found'].add(font_name)
            font_usage['usage_locations'].append(
                {
                    'type': 'custom_style',
                    'font': font_name,
                    'location': 'document header (#+CUSTOM_STYLE)',
                }
            )

    # 2) STYLE_* meta declarations: accept quoted or unquoted
    #    Examples: 'font: Playfair Display, size: 20mm' or 'font:"Inter"'
    style_keys = [
        k
        for k in meta.keys()
        if isinstance(k, str) and k.upper().startswith('STYLE_') and k.upper() != 'STYLE'
    ]
    for sk in style_keys:
        decl = meta.get(sk, '') or ''
        # Prefer quoted first
        names = re.findall(r'font\s*:\s*"([^"]+)"', decl)
        if not names:
            # Fallback to unquoted up to comma/semicolon/end
            m = re.search(r'font\s*:\s*([^,;]+)', decl)
            if m:
                candidate = m.group(1).strip()
                # Strip potential trailing tokens
                candidate = candidate.strip('"\' )')
                if candidate:
                    names = [candidate]
        for name in names:
            n = name.strip()
            if not n:
                continue
            font_usage['fonts_found'].add(n)
            font_usage['usage_locations'].append(
                {'type': 'style_meta', 'font': n, 'location': f'meta {sk}'}
            )

    # 3) Global FONT meta override
    if isinstance(meta.get('FONT'), str) and meta.get('FONT').strip():
        n = meta['FONT'].strip()
        font_usage['fonts_found'].add(n)
        font_usage['usage_locations'].append({'type': 'meta', 'font': n, 'location': 'meta FONT'})

    # 4) Inline Typst in element content
    for page_idx, page in enumerate(ir.get('pages', []), 1):
        for elem_idx, element in enumerate(page.get('elements', []), 1):
            content = element.get('content', '')
            if isinstance(content, str):
                for font_name in re.findall(r'#set\s+text\([^)]*font:\s*"([^"]+)"', content):
                    font_usage['fonts_found'].add(font_name)
                    font_usage['usage_locations'].append(
                        {
                            'type': 'element_content',
                            'font': font_name,
                            'location': f'page {page_idx}, element {elem_idx}',
                        }
                    )

    # Build availability set using real font names, with optional env override
    font_paths = _get_font_paths()
    disable_ft = str(os.environ.get('PAGEMAKER_DISABLE_FONTTOOLS', '')).strip().lower()
    force_dirnames = disable_ft not in ('', '0', 'false', 'no')
    available_real = set() if force_dirnames else _collect_real_font_names(font_paths)

    # Directory-name heuristic (forced or fallback)
    if force_dirnames or not available_real:
        available_dirnames = set()
        for font_path in font_paths:
            path_obj = pathlib.Path(font_path)
            if not path_obj.exists():
                continue
            try:
                for item in path_obj.iterdir():
                    if item.is_dir() and not item.name.startswith('.'):
                        font_files = list(item.glob('*.ttf')) + list(item.glob('*.otf'))
                        if font_files:
                            n = item.name
                            available_dirnames.add(n)
                            if '_' in n:
                                available_dirnames.add(n.replace('_', ' '))
                            if ' ' in n:
                                available_dirnames.add(n.replace(' ', '_'))
            except OSError:
                continue
        if force_dirnames:
            available_real = available_dirnames
        else:
            available_real |= available_dirnames

    # Determine missing fonts
    font_usage['missing_fonts'] = font_usage['fonts_found'] - available_real
    font_usage['available_fonts'] = available_real

    return font_usage


def _validate_fonts_in_build(ir: dict, strict: bool = False) -> bool:
    """Validate fonts used in the document. Returns True if validation passes."""
    font_usage = _analyze_font_usage(ir)

    if not font_usage['fonts_found']:
        return True  # No fonts referenced, nothing to validate

    if font_usage['missing_fonts']:
        print("⚠️  Font Validation Issues:")
        for font in sorted(font_usage['missing_fonts']):
            print(f"   ❌ Missing font: '{font}'")
            # Show where it's used
            for usage in font_usage['usage_locations']:
                if usage['font'] == font:
                    print(f"      Used in: {usage['location']}")

        print("\n💡 Suggestions:")
        print("   • Install missing fonts: pagemaker fonts install \"FontName\"")
        print("   • Search for alternatives: pagemaker fonts search \"FontName\"")
        print(
            f"   • Use available fonts: {', '.join(sorted(list(font_usage['available_fonts'])[:5]))}"
        )

        if strict:
            print("\n❌ Build failed due to missing fonts (strict mode)")
            return False
        else:
            print("\n⚠️  Build continuing with font fallbacks...")

    return True


def _get_font_discovery_cache_path() -> pathlib.Path:
    """Get path to font discovery cache file"""
    cache_dir = pathlib.Path.home() / '.pagemaker' / 'cache'
    return cache_dir / 'font_discovery.json'


def _is_cache_valid(cache_path: pathlib.Path, font_paths: list) -> bool:
    """Check if font discovery cache is still valid"""
    if not cache_path.exists():
        return False

    try:
        cache_data = json.loads(cache_path.read_text(encoding='utf-8'))

        # Check cache age (5 minutes)
        cache_age = time.time() - cache_data.get('timestamp', 0)
        if cache_age > 300:  # 5 minutes
            return False

        # Check if font paths changed
        if cache_data.get('font_paths') != font_paths:
            return False

        # Check if any font directories were modified since cache
        cache_time = cache_data.get('timestamp', 0)
        for font_path in font_paths:
            path_obj = pathlib.Path(font_path)
            if path_obj.exists():
                try:
                    if path_obj.stat().st_mtime > cache_time:
                        return False
                except OSError:
                    continue

        return True

    except (json.JSONDecodeError, OSError, KeyError):
        return False


def _save_font_discovery_cache(cache_path: pathlib.Path, font_paths: list, discovery_results: dict):
    """Save font discovery results to cache"""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        cache_data = {
            'timestamp': time.time(),
            'font_paths': font_paths,
            'results': discovery_results,
        }

        cache_path.write_text(json.dumps(cache_data, indent=2), encoding='utf-8')
    except Exception:
        # Cache failures shouldn't break functionality
        pass


def _get_cached_font_discovery() -> dict:
    """Get font discovery results with caching"""
    font_paths = _get_font_paths()
    cache_path = _get_font_discovery_cache_path()

    # Try to use cache
    if _is_cache_valid(cache_path, font_paths):
        try:
            cache_data = json.loads(cache_path.read_text(encoding='utf-8'))
            return cache_data['results']
        except (json.JSONDecodeError, OSError, KeyError):
            pass

    # Cache miss - do fresh discovery
    results = {
        'bundled': _get_bundled_fonts(),
        'project': _get_project_fonts(),
        'font_paths': font_paths,
    }

    # Save to cache
    _save_font_discovery_cache(cache_path, font_paths, results)

    return results


def _search_google_fonts(query: str, limit: int = 10) -> list:
    """Search Google Fonts by name"""
    fonts_data = _get_google_fonts_api_data()
    query_lower = query.lower()

    matches = []
    for font in fonts_data.get('items', []):
        family = font.get('family', '')
        if family and query_lower in family.lower():
            matches.append(
                {
                    'family': family,
                    'variants': len(font.get('files', {})),
                    'variants_list': list(font.get('files', {}).keys()),
                    'category': font.get('category', 'unknown'),
                }
            )

    return matches[:limit]


def _print_font_info(font_info: dict, title: str, show_details: bool = False):
    """Print formatted font information"""
    print(f"\n{title}")
    print("=" * len(title))

    if not font_info['exists']:
        print(f"❌ Path not found: {font_info['path']}")
        return

    if 'error' in font_info:
        print(f"⚠️  Error reading path: {font_info['error']}")
        return

    if not font_info['families']:
        print(f"📂 Path exists but no fonts found: {font_info['path']}")
        return

    print(f"📂 Path: {font_info['path']}")
    print(f"📊 Found {len(font_info['families'])} font families")

    total_files = sum(len(family['files']) for family in font_info['families'].values())
    total_size = sum(family['total_size'] for family in font_info['families'].values())
    print(f"📄 Total files: {total_files} ({_format_size(total_size)})")

    # List families
    for family_name, family_info in sorted(font_info['families'].items()):
        file_count = len(family_info['files'])
        size_info = family_info['total_size_human']
        print(f"  🔤 {family_name}: {file_count} files ({size_info})")

        if show_details:
            for font_file in sorted(family_info['files'], key=lambda x: x['name']):
                print(f"    📁 {font_file['name']} ({font_file['size_human']})")


def _check_typst_binary(typst_bin: str = 'typst') -> bool:
    """Check if Typst binary is available and working"""
    try:
        result = subprocess.run(
            [typst_bin, '--version'], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return True
        else:
            print(
                f"ERROR: Typst binary '{typst_bin}' returned error code {result.returncode}",
                file=sys.stderr,
            )
            return False
    except FileNotFoundError:
        print(f"ERROR: Typst binary '{typst_bin}' not found in PATH", file=sys.stderr)
        print("Please install Typst: https://github.com/typst/typst/releases", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print(f"ERROR: Typst binary '{typst_bin}' timed out", file=sys.stderr)
        return False
    except Exception as e:
        print(f"ERROR: Failed to check Typst binary '{typst_bin}': {e}", file=sys.stderr)
        return False


def _write(path: pathlib.Path, data: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding='utf-8')


def _attempt_auto_download_missing_fonts(ir: dict) -> None:
    """Try to download missing fonts referenced in the IR using fontdownloader.

    Downloads into ./assets/fonts/<FontName>/ as provided by fontdownloader.
    Ignores WOFF files for Typst availability checks; relies on TTF/OTF/TTC.
    After each download attempt, rescans availability and reports status.
    """
    try:
        initial_usage = _analyze_font_usage(ir)
        missing = sorted(initial_usage.get('missing_fonts', []))
        if not missing:
            return
        print(f"🔤 Missing fonts detected: {', '.join(missing)}")

        # Try programmatic API first, then CLI fallback per font
        for name in missing:
            attempted = False
            try:
                from fontdownloader import cli as fd_cli  # type: ignore

                try:
                    print(f"📥 Attempting to download '{name}' via fontdownloader...")
                    fd_cli._download_full_family(name, force=False)  # noqa: SLF001
                    attempted = True
                except Exception as e:
                    print(f"  ⚠️  Auto-download failed for '{name}': {e}")
            except Exception:
                # programmatic import failed; try CLI
                pass

            if not attempted:
                try:
                    print(f"📥 Attempting to download '{name}' via fontdownloader CLI...")
                    res = subprocess.run(
                        [sys.executable, '-m', 'fontdownloader.cli', 'download', name],
                        capture_output=True,
                        text=True,
                    )
                    if res.stdout:
                        sys.stdout.write(res.stdout)
                    if res.stderr:
                        sys.stderr.write(res.stderr)
                except Exception as e:
                    print(f"  ⚠️  Auto-download (CLI) failed for '{name}': {e}")

            # Rescan availability after this attempt
            available_after = _analyze_font_usage(ir).get('available_fonts', set())
            if name in available_after:
                print(f"  ✅ '{name}' is now available")
            else:
                print(f"  ❌ '{name}' still not available after download attempt")
    except Exception as e:
        # Non-fatal
        print(f"⚠️  Font auto-download step encountered an issue: {e}")


def cmd_build(args):
    ir = parse_org(args.org)

    # Try to fetch any missing fonts automatically
    _attempt_auto_download_missing_fonts(ir)

    # Validate fonts if requested (after auto-download attempt)
    if getattr(args, 'validate_fonts', False):
        if not _validate_fonts_in_build(ir, strict=getattr(args, 'strict_fonts', False)):
            sys.exit(1)

    export_dir = pathlib.Path(args.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    adjust_asset_paths(ir, export_dir)
    if args.ir:
        ir_path = (
            export_dir / args.ir
            if not pathlib.Path(args.ir).is_absolute()
            else pathlib.Path(args.ir)
        )
        ir_path.parent.mkdir(parents=True, exist_ok=True)
        ir_path.write_text(json.dumps(ir, indent=2), encoding='utf-8')
    out_path = (
        export_dir / args.output
        if not pathlib.Path(args.output).is_absolute()
        else pathlib.Path(args.output)
    )
    typst_code = generate_typst(ir)
    _write(out_path, typst_code)
    if args.update_html:
        update_html_total(pathlib.Path(args.update_html), len(ir['pages']))
    print(f"Built Typst: {out_path} pages={len(ir['pages'])}")


def _compile_pdf(
    typst_file: pathlib.Path, pdf_path: pathlib.Path, typst_bin: str = 'typst'
) -> bool:
    if not _check_typst_binary(typst_bin):
        return False

    try:
        project_root = pathlib.Path.cwd()
        cmd = [
            typst_bin,
            'compile',
            '--root',
            str(project_root),
        ]

        # Add font paths dynamically (user fonts take precedence over bundled)
        font_paths = _get_font_paths()
        for font_path in font_paths:
            cmd.extend(['--font-path', font_path])

        cmd.extend([str(typst_file), str(pdf_path)])

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            return True
        else:
            print(
                f"ERROR: Typst compile failed (exit {res.returncode}):\n{res.stderr}",
                file=sys.stderr,
            )
            print(f"Font paths used: {font_paths}", file=sys.stderr)
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


def _convert_pdf_to_svg(src_pdf: pathlib.Path, out_svg: pathlib.Path, page: int = 1) -> bool:
    if not _bin_exists('mutool'):
        return False
    # Render only the requested page to a single SVG
    res = subprocess.run(
        ['mutool', 'draw', '-F', 'svg', '-o', str(out_svg), str(src_pdf), str(page)],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return False
    return out_svg.exists()


def _convert_pdf_to_png(
    src_pdf: pathlib.Path, out_png: pathlib.Path, page: int = 1, dpi: int = 160
) -> bool:
    # Prefer mutool PNG rendering; fallback to Ghostscript pngalpha
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
                abs_src = pathlib.Path.cwd() / src_path
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


def _compile_with_fallback(
    ir: dict,
    export_dir: pathlib.Path,
    typst_path: pathlib.Path,
    pdf_path: pathlib.Path,
    typst_bin: str,
    sanitize: bool,
    no_clean: bool,
) -> bool:
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
        try:
            typst_path.unlink()
        except OSError:
            pass
    return ok


def cmd_pdf(args):
    ir = parse_org(args.org)

    # Try to fetch any missing fonts automatically
    _attempt_auto_download_missing_fonts(ir)

    # Validate fonts if requested (after auto-download attempt)
    if getattr(args, 'validate_fonts', False):
        if not _validate_fonts_in_build(ir, strict=getattr(args, 'strict_fonts', False)):
            sys.exit(1)

    export_dir = pathlib.Path(args.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    adjust_asset_paths(ir, export_dir)
    typst_filename = args.output if args.output else 'deck.typ'
    typst_path = (
        export_dir / typst_filename
        if not pathlib.Path(typst_filename).is_absolute()
        else pathlib.Path(typst_filename)
    )
    pdf_out = args.pdf_output or f"{pathlib.Path(args.org).stem}.pdf"
    pdf_path = (
        export_dir / pdf_out if not pathlib.Path(pdf_out).is_absolute() else pathlib.Path(pdf_out)
    )

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
            data = p.read_bytes()
            return hashlib.sha256(data).hexdigest()
        except Exception:
            return None

    def build_once():
        ir = parse_org(str(org_path))
        # Try to fetch any missing fonts automatically
        _attempt_auto_download_missing_fonts(ir)
        adjust_asset_paths(ir, export_dir)
        if args.update_html:
            update_html_total(pathlib.Path(args.update_html), len(ir['pages']))
        typst_filename = args.output
        typst_path = (
            export_dir / typst_filename
            if not pathlib.Path(typst_filename).is_absolute()
            else pathlib.Path(typst_filename)
        )
        if args.pdf:
            pdf_out = args.pdf_output or f"{org_path.stem}.pdf"
            pdf_path = (
                export_dir / pdf_out
                if not pathlib.Path(pdf_out).is_absolute()
                else pathlib.Path(pdf_out)
            )
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
                    print("[watch] Initial build complete")
                except Exception as e:
                    print(f"[watch] ERROR during initial build: {e}", file=sys.stderr)
                    sys.exit(1)
            break
        time.sleep(args.interval)


def cmd_fonts_list_bundled(args):
    """List bundled fonts"""
    font_info = _get_bundled_fonts()
    _print_font_info(font_info, "Bundled Fonts", args.details)


def cmd_fonts_list_project(args):
    """List project fonts in assets/fonts"""
    font_info = _get_project_fonts()
    _print_font_info(font_info, "Project Fonts (assets/fonts/)", args.details)


def cmd_fonts_list_all(args):
    """List all available fonts"""
    print("🔍 Font Discovery Report")
    print("=" * 40)

    # Use cached discovery for better performance
    cached_results = _get_cached_font_discovery()
    bundled_info = cached_results['bundled']
    project_info = cached_results['project']
    font_paths = cached_results['font_paths']

    # Show bundled fonts
    _print_font_info(bundled_info, "1. Bundled Fonts (Always Available)", args.details)

    # Show project fonts
    _print_font_info(project_info, "2. Project Fonts (Custom Library)", args.details)

    # Show font resolution order
    print("\n🎯 Font Resolution Order")
    print("=" * 25)
    for i, path in enumerate(font_paths, 1):
        print(f"  {i}. {path}")

    # Summary
    bundled_families = len(bundled_info['families']) if bundled_info['exists'] else 0
    project_families = len(project_info['families']) if project_info['exists'] else 0
    total_families = bundled_families + project_families

    print("\n📊 Summary")
    print("=" * 10)
    print(f"  Bundled families: {bundled_families}")
    print(f"  Project families: {project_families}")
    print(f"  Total families: {total_families}")


def cmd_fonts_validate(args):
    """Validate font availability using real font family names.

    Uses fontTools to scan TTF/OTF/TTC/OTC files under known font paths and
    matches against the requested family name (case-insensitive). Also accepts
    underscore/space variants for convenience (e.g., "Open_Sans" == "Open Sans").
    """
    font_name = args.font
    print(f"🔍 Validating font: '{font_name}'")
    print("=" * 40)

    # Prepare query variants
    queries = {font_name}
    if '_' in font_name:
        queries.add(font_name.replace('_', ' '))
    if ' ' in font_name:
        queries.add(font_name.replace(' ', '_'))
    queries_lower = {q.lower() for q in queries}

    font_paths = _get_font_paths()
    found_locations = []

    def _list_matching_files(root: pathlib.Path) -> list[tuple[str, int]]:
        matches: list[tuple[str, int]] = []
        try:
            from fontTools.ttLib import TTFont
            from fontTools.ttLib.ttCollection import TTCollection
        except Exception:
            return matches
        font_exts = {'.ttf', '.otf', '.ttc', '.otc'}
        try:
            for f in root.rglob('*'):
                try:
                    if not f.is_file() or f.suffix.lower() not in font_exts:
                        continue
                    if f.suffix.lower() in {'.ttc', '.otc'}:
                        tc = TTCollection(str(f))
                        hit = False
                        for ttf in tc.fonts:
                            nm = ttf.get('name')
                            if not nm:
                                continue
                            for rec in nm.names:
                                if rec.nameID in (1, 16):
                                    try:
                                        fam = rec.toUnicode().strip()
                                        if fam and fam.lower() in queries_lower:
                                            hit = True
                                    except Exception:
                                        pass
                        if hit:
                            try:
                                size = f.stat().st_size
                            except OSError:
                                size = 0
                            matches.append((f.name, size))
                    else:
                        t = TTFont(str(f), lazy=True)
                        nm = t.get('name')
                        fams = set()
                        if nm:
                            for rec in nm.names:
                                if rec.nameID in (1, 16):
                                    try:
                                        fams.add(rec.toUnicode().strip().lower())
                                    except Exception:
                                        pass
                        try:
                            t.close()
                        except Exception:
                            pass
                        if fams & queries_lower:
                            try:
                                size = f.stat().st_size
                            except OSError:
                                size = 0
                            matches.append((f.name, size))
                except Exception:
                    continue
        except Exception:
            pass
        return matches

    for i, font_path in enumerate(font_paths, 1):
        path_obj = pathlib.Path(font_path)
        if not path_obj.exists():
            print(f"  {i}. {font_path} - ❌ Path not found")
            continue

        available_names = _collect_real_font_names([font_path])
        available_lower = {n.lower() for n in available_names}
        present = bool(available_lower & queries_lower)

        if present:
            found_locations.append(font_path)
            print(f"  {i}. {font_path} - ✅ Found via real-name scan")
            if args.details:
                files = _list_matching_files(path_obj)
                for name, size in sorted(files):
                    print(f"     📁 {name} ({_format_size(size)})")
        else:
            print(f"  {i}. {font_path} - ❌ Font family not found")

    # Final result
    print("\n🎯 Result")
    print("=" * 10)
    if found_locations:
        print(f"✅ Font '{font_name}' is available")
        print(f"   First found in: {found_locations[0]}")
        if len(found_locations) > 1:
            print(f"   Also available in: {', '.join(found_locations[1:])}")
    else:
        print(f"❌ Font '{font_name}' not found in any font path")
        print("   Ensure TTF/OTF/TTC files are present or check spelling")


def cmd_fonts_search(args):
    """Search Google Fonts using fontdownloader"""
    query = args.query
    limit = args.limit

    print(f"🔍 Searching Google Fonts for: '{query}'")
    print("=" * 50)

    try:
        from fontdownloader import cli as fd_cli  # type: ignore

        matches = fd_cli._search_google_fonts(query, limit)  # noqa: SLF001
    except Exception:
        # Fallback to invoking the fontdownloader CLI and returning early
        try:
            subprocess.run(
                [sys.executable, '-m', 'fontdownloader.cli', 'search', query, '--limit', str(limit)]
                + (['--details'] if args.details else []),
                check=False,
            )
            return
        except Exception as e:
            print(f"❌ Search failed: {e}")
            return

    if not matches:
        print(f"❌ No fonts found matching '{query}'")
        return

    print(f"📊 Found {len(matches)} matching fonts:")

    for i, font in enumerate(matches, 1):
        family = font['family']
        variants_count = font['variants']
        category = font['category'].title()

        print(f"  {i:2d}. {family}")
        print(f"      📂 {category} • {variants_count} variants")

        if args.details:
            variants_list = ', '.join(font['variants_list'][:8])  # Show first 8 variants
            if len(font['variants_list']) > 8:
                variants_list += "..."
            print(f"      🔤 Variants: {variants_list}")


def cmd_fonts_install(args):
    """Install font using fontdownloader (full family into assets/fonts/<FontName>/)"""
    font_family = args.font
    # variants are ignored; fontdownloader installs full family
    force = args.force

    print(f"📥 Installing Google Font: '{font_family}' (via fontdownloader)")
    print("=" * 50)

    ok = False
    try:
        from fontdownloader import cli as fd_cli  # type: ignore

        fd_cli._download_full_family(font_family, force)  # noqa: SLF001
        ok = True
    except Exception:
        # Fallback to CLI invocation
        try:
            res = subprocess.run(
                [sys.executable, '-m', 'fontdownloader.cli', 'download', font_family]
                + (['--force'] if force else []),
                capture_output=True,
                text=True,
            )
            ok = res.returncode == 0
            sys.stdout.write(res.stdout)
            if res.stderr:
                sys.stderr.write(res.stderr)
        except Exception as e:
            print(f"❌ Installation failed: {e}")
            ok = False

    if ok:
        print("\n✅ Installation complete!")
        print(f"Font '{font_family}' is now available for use in your documents.")
        print("\nUsage example:")
        print(f'#+CUSTOM_STYLE: #set text(font: "{font_family}", size: 12pt)')
    else:
        print("\n❌ Installation failed!")
        print("Try searching for the exact font name first:")
        print(f"  pagemaker fonts search \"{font_family}\"")
        sys.exit(1)


def cmd_fonts_cache_clear(args):
    """Clear font cache"""
    cache_dir = pathlib.Path.home() / '.pagemaker' / 'cache'
    cache_file = cache_dir / 'google_fonts.json'

    try:
        if cache_file.exists():
            cache_file.unlink()
            print("✅ Font cache cleared")
        else:
            print("ℹ️  No cache to clear")
    except OSError as e:
        print(f"❌ Failed to clear cache: {e}")
        sys.exit(1)


def cmd_fonts_analyze(args):
    """Analyze font usage in document"""
    org_file = args.org
    print(f"🔍 Analyzing font usage in: {org_file}")
    print("=" * 50)

    try:
        ir = parse_org(org_file)
        font_usage = _analyze_font_usage(ir)

        if not font_usage['fonts_found']:
            print("📊 No fonts explicitly referenced in document")
            print("   Document will use system defaults or Typst fallbacks")
            return

        print("📊 Font Usage Analysis:")
        print(f"   Referenced fonts: {len(font_usage['fonts_found'])}")
        print(f"   Available fonts: {len(font_usage['available_fonts'])}")
        print(f"   Missing fonts: {len(font_usage['missing_fonts'])}")

        # Show referenced fonts
        print("\n🔤 Fonts Referenced in Document:")
        for font in sorted(font_usage['fonts_found']):
            status = "✅" if font in font_usage['available_fonts'] else "❌"
            print(f"   {status} {font}")

            # Show usage locations for this font
            if args.details:
                for usage in font_usage['usage_locations']:
                    if usage['font'] == font:
                        print(f"      └─ {usage['location']}")

        # Show missing fonts with suggestions
        if font_usage['missing_fonts']:
            print("\n⚠️  Missing Fonts:")
            for font in sorted(font_usage['missing_fonts']):
                print(f"   ❌ {font}")
                print(f"      Install: pagemaker fonts install \"{font}\"")
                print(f"      Search: pagemaker fonts search \"{font}\"")

        # Show available alternatives
        if font_usage['available_fonts'] and len(font_usage['available_fonts']) > len(
            font_usage['fonts_found']
        ):
            unused_fonts = font_usage['available_fonts'] - font_usage['fonts_found']
            print("\n💡 Available Alternative Fonts:")
            for font in sorted(list(unused_fonts)[:10]):  # Show first 10
                print(f"   • {font}")
            if len(unused_fonts) > 10:
                print(f"   ... and {len(unused_fonts) - 10} more")

    except Exception as e:
        print(f"❌ Failed to analyze document: {e}")
        sys.exit(1)


def _generate_font_specimen_org(fonts_info: list, specimen_type: str = 'showcase') -> str:
    """Generate org-mode content for font specimen"""

    if specimen_type == 'showcase':
        # Beautiful showcase with various text samples
        content = '''#+TITLE: Font Specimen Showcase
#+PAGESIZE: A4
#+ORIENTATION: portrait  
#+GRID: 12x16
#+MARGINS: 15,15,15,15
#+CUSTOM_STYLE: #page(margin: 15mm); #set text(font: "Inter", size: 10pt)

* Available Font Families

This specimen showcases all available fonts in your pagemaker installation.

'''

        sample_texts = [
            "The quick brown fox jumps over the lazy dog",
            "TYPOGRAPHY & Design Elements 1234567890",
            "Hamburgefonstiv — A classic font testing phrase",
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        ]

        row = 1
        for font_info in fonts_info:
            font_name = font_info['name']
            files_count = font_info['files_count']
            size_info = font_info['size_human']

            # Font family header
            content += f'''** {font_name}
:PROPERTIES:
:TYPE: header
:AREA: A{row},L{row}
:END:

#set text(font: "{font_name}", weight: "bold", size: 14pt)
{font_name} — {files_count} files ({size_info})

'''
            row += 1

            # Sample text in this font
            content += f'''*** Sample Text
:PROPERTIES:
:TYPE: body
:AREA: A{row},L{row + 2}
:PADDING: 0,0,8,0
:END:

#set text(font: "{font_name}", size: 11pt)

{sample_texts[0]}

#set text(size: 9pt, style: "italic")
{sample_texts[1]}

#set text(size: 10pt, style: "normal")
{sample_texts[3]}

'''
            row += 4

            if row > 14:  # Start new page
                content += '\n\\pagebreak\n\n'
                row = 1

    elif specimen_type == 'comparison':
        # Side-by-side comparison of fonts
        content = '''#+TITLE: Font Comparison Sheet
#+PAGESIZE: A4
#+ORIENTATION: landscape
#+GRID: 16x10
#+MARGINS: 10,10,10,10
#+CUSTOM_STYLE: #page(margin: 10mm); #set text(font: "Inter", size: 9pt)

* Font Comparison

Direct comparison of all available fonts using identical text samples.

'''
        sample_text = "The quick brown fox jumps over the lazy dog 1234567890"

        col = 1
        row = 2
        for i, font_info in enumerate(fonts_info):
            font_name = font_info['name']

            if col > 15:  # New row
                col = 1
                row += 2

            if row > 8:  # New page
                content += '\n\\pagebreak\n\n'
                row = 2
                col = 1

            content += f'''** {font_name}
:PROPERTIES:
:TYPE: body
:AREA: {chr(65 + col - 1)}{row},{chr(65 + col + 6)}{row + 1}
:PADDING: 2
:END:

#set text(font: "{font_name}", size: 8pt, weight: "bold")
{font_name}

#set text(size: 9pt, weight: "normal")
{sample_text}

'''
            col += 8

    else:  # simple list
        content = '''#+TITLE: Font List
#+CUSTOM_STYLE: #set text(font: "Inter", size: 11pt)

* Available Fonts

'''
        for font_info in fonts_info:
            content += f'''** {font_info['name']}
#set text(font: "{font_info['name']}")
Sample text in {font_info['name']} — {font_info['files_count']} files ({font_info['size_human']})

'''

    return content


def cmd_fonts_specimen(args):
    """Generate font specimen document"""
    output_file = args.output or 'font-specimen.org'
    specimen_type = args.type
    build_pdf = args.pdf

    print(f"📋 Generating font specimen: {specimen_type}")
    print("=" * 50)

    # Collect font information
    all_fonts = []

    # Add bundled fonts
    bundled_info = _get_bundled_fonts()
    if bundled_info['exists']:
        for family_name, family_info in bundled_info['families'].items():
            all_fonts.append(
                {
                    'name': family_name,
                    'files_count': len(family_info['files']),
                    'size_human': family_info['total_size_human'],
                    'source': 'bundled',
                }
            )

    # Add project fonts
    project_info = _get_project_fonts()
    if project_info['exists']:
        for family_name, family_info in project_info['families'].items():
            all_fonts.append(
                {
                    'name': family_name,
                    'files_count': len(family_info['files']),
                    'size_human': family_info['total_size_human'],
                    'source': 'project',
                }
            )

    if not all_fonts:
        print("❌ No fonts found to generate specimen")
        return

    # Sort fonts alphabetically
    all_fonts.sort(key=lambda x: x['name'].lower())

    print(f"📊 Found {len(all_fonts)} font families")

    # Generate org content
    org_content = _generate_font_specimen_org(all_fonts, specimen_type)

    # Write to file
    output_path = pathlib.Path(output_file)
    output_path.write_text(org_content, encoding='utf-8')

    print(f"✅ Specimen written to: {output_path}")

    # Optionally build PDF
    if build_pdf:
        print("📄 Building PDF...")

        # Use the existing build functionality
        import subprocess
        import sys

        try:
            cmd = [sys.executable, '-m', 'pagemaker.cli', 'pdf', str(output_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                pdf_name = output_path.stem + '.pdf'
                print(f"✅ PDF built: export/{pdf_name}")
            else:
                print(f"❌ PDF build failed: {result.stderr}")
        except Exception as e:
            print(f"❌ PDF build error: {e}")

    print("\n💡 Usage:")
    print(f"   Preview: pagemaker build {output_file}")
    print(f"   PDF: pagemaker pdf {output_file}")
    print(f"   Open: open export/{output_path.stem}.pdf")


def build_parser():
    p = argparse.ArgumentParser(prog='pagemaker')
    sub = p.add_subparsers(dest='command', required=True)

    b = sub.add_parser('build', help='org -> typst')
    b.add_argument('org')
    b.add_argument('-o', '--output', default='deck.typ')
    b.add_argument('--ir')
    b.add_argument('--update-html')
    b.add_argument('--export-dir', default=DEFAULT_EXPORT_DIR)
    b.add_argument(
        '--validate-fonts',
        action='store_true',
        help='validate all fonts are available before build',
    )
    b.add_argument(
        '--strict-fonts', action='store_true', help='fail build if any fonts are missing'
    )
    b.set_defaults(func=cmd_build)

    pdf = sub.add_parser('pdf', help='org -> typst -> pdf')
    pdf.add_argument('org')
    pdf.add_argument('-o', '--output', default='deck.typ')
    pdf.add_argument('--pdf-output')
    pdf.add_argument('--typst-bin', default='typst')
    pdf.add_argument('--export-dir', default=DEFAULT_EXPORT_DIR)
    pdf.add_argument('--no-clean', action='store_true')

    pdf.add_argument(
        '--validate-fonts',
        action='store_true',
        help='validate all fonts are available before build',
    )
    pdf.add_argument(
        '--strict-fonts', action='store_true', help='fail build if any fonts are missing'
    )
    pdf.add_argument(
        '--sanitize-pdfs',
        action='store_true',
        help='Attempt to sanitize PDFs and fallback to SVG if necessary',
    )
    pdf.set_defaults(func=cmd_pdf)

    irp = sub.add_parser('ir', help='emit IR JSON')
    irp.add_argument('org')
    irp.set_defaults(func=cmd_ir)

    val = sub.add_parser('validate', help='validate IR')
    val.add_argument('org')
    val.add_argument(
        '--strict-assets', action='store_true', help='Treat missing figure/pdf assets as errors'
    )
    val.set_defaults(func=cmd_validate)

    watch = sub.add_parser('watch', help='watch org file and rebuild on change')
    watch.add_argument('org')
    watch.add_argument('-o', '--output', default='deck.typ')
    watch.add_argument('--export-dir', default=DEFAULT_EXPORT_DIR)
    watch.add_argument('--interval', type=float, default=1.0)
    watch.add_argument('--pdf', action='store_true')
    watch.add_argument('--pdf-output')
    watch.add_argument('--typst-bin', default='typst')
    watch.add_argument('--no-clean', action='store_true')
    watch.add_argument('--update-html')
    watch.add_argument(
        '--once', action='store_true', help='Run single build then exit (for testing)'
    )
    watch.add_argument(
        '--sanitize-pdfs',
        action='store_true',
        help='Attempt to sanitize PDFs and fallback to SVG if necessary',
    )
    watch.set_defaults(func=cmd_watch)

    # Font management commands
    fonts = sub.add_parser('fonts', help='font discovery and management utilities')
    fonts_sub = fonts.add_subparsers(dest='fonts_command', required=True, title='font commands')

    # fonts list-bundled
    bundled = fonts_sub.add_parser('list-bundled', help='list bundled fonts')
    bundled.add_argument('--details', action='store_true', help='show detailed file information')
    bundled.set_defaults(func=cmd_fonts_list_bundled)

    # fonts list-project
    project = fonts_sub.add_parser('list-project', help='list project fonts in assets/fonts/')
    project.add_argument('--details', action='store_true', help='show detailed file information')
    project.set_defaults(func=cmd_fonts_list_project)

    # fonts list-all
    all_fonts = fonts_sub.add_parser('list-all', help='list all available fonts')
    all_fonts.add_argument('--details', action='store_true', help='show detailed file information')
    all_fonts.set_defaults(func=cmd_fonts_list_all)

    # fonts validate
    validate_font = fonts_sub.add_parser('validate', help='validate font availability')
    validate_font.add_argument('font', help='font family name to validate')
    validate_font.add_argument(
        '--details', action='store_true', help='show detailed file information'
    )
    validate_font.set_defaults(func=cmd_fonts_validate)

    # fonts search
    search_font = fonts_sub.add_parser('search', help='search Google Fonts')
    search_font.add_argument('query', help='search query for font names')
    search_font.add_argument(
        '--limit', type=int, default=10, help='maximum number of results (default: 10)'
    )
    search_font.add_argument(
        '--details', action='store_true', help='show detailed variant information'
    )
    search_font.set_defaults(func=cmd_fonts_search)

    # fonts install
    install_font = fonts_sub.add_parser('install', help='install font from Google Fonts')
    install_font.add_argument('font', help='Google Fonts family name to install')
    install_font.add_argument(
        '--variants', help='comma-separated list of variants (e.g., "regular,700,italic")'
    )
    install_font.add_argument(
        '--force', action='store_true', help='reinstall even if font already exists'
    )
    install_font.set_defaults(func=cmd_fonts_install)

    # fonts cache-clear
    cache_clear = fonts_sub.add_parser('cache-clear', help='clear Google Fonts cache')
    cache_clear.set_defaults(func=cmd_fonts_cache_clear)

    # fonts analyze
    analyze = fonts_sub.add_parser('analyze', help='analyze font usage in document')
    analyze.add_argument('org', help='org file to analyze')
    analyze.add_argument('--details', action='store_true', help='show detailed usage locations')
    analyze.set_defaults(func=cmd_fonts_analyze)

    # fonts specimen
    specimen = fonts_sub.add_parser('specimen', help='generate font specimen/preview document')
    specimen.add_argument(
        '--output',
        '-o',
        default='font-specimen.org',
        help='output filename (default: font-specimen.org)',
    )
    specimen.add_argument(
        '--type',
        choices=['showcase', 'comparison', 'simple'],
        default='showcase',
        help='specimen type (default: showcase)',
    )
    specimen.add_argument(
        '--pdf', action='store_true', help='automatically build PDF after generating org file'
    )
    specimen.set_defaults(func=cmd_fonts_specimen)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
