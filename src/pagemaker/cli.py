#!/usr/bin/env python3
"""Unified CLI for typst-pagemaker

Subcommands:
  build     org -> typst (and optional IR export)
  pdf       org -> typst -> pdf
  story     org -> story HTML (scrolling web narrative with grid layout)
  ir        parse org and emit IR JSON
  validate  parse and validate IR
  watch     rebuild on changes (polling)
  fonts     font discovery and management utilities

"""

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from typing import Dict, List

from . import adjust_asset_paths, generate_typst, parse_org, update_html_total
from .fonts import (
    _collect_real_font_names,
    _format_size,
    _get_bundled_fonts,
    _get_font_paths,
    _get_project_fonts,
    analyze_font_usage,
)
from .generation.html_generator import generate_story_html
from .generation.pdf_processor import (
    apply_pdf_fallbacks as _apply_pdf_svg_fallbacks,
)
from .generation.pdf_processor import (
    sanitize_pdf_assets as _apply_pdf_sanitized_copies,
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


# _analyze_font_usage moved to fonts.py


def _validate_fonts_in_build(ir: dict, strict: bool = False) -> bool:
    """Validate fonts used in the document. Returns True if validation passes."""
    font_usage = analyze_font_usage(ir)

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
        initial_usage = analyze_font_usage(ir)
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
            available_after = analyze_font_usage(ir).get('available_fonts', set())
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


def _check_typst_html_support(typst_bin: str = 'typst') -> tuple[bool, str]:
    """Check if Typst supports HTML export (requires 0.14.0+).

    Returns:
        Tuple of (supported: bool, version: str)
    """
    try:
        res = subprocess.run([typst_bin, '--version'], capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            return False, 'unknown'

        # Parse version from output like "typst 0.14.0"
        version_str = res.stdout.strip()
        match = re.search(r'typst\s+(\d+)\.(\d+)\.(\d+)', version_str)
        if not match:
            return False, version_str

        major, minor, patch = map(int, match.groups())
        version = f"{major}.{minor}.{patch}"

        # HTML export requires Typst 0.14.0+
        supported = (major > 0) or (major == 0 and minor >= 14)
        return supported, version

    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False, 'unknown'


def _compile_html(
    typst_file: pathlib.Path,
    html_output_dir: pathlib.Path,
    typst_bin: str = 'typst',
    source_basename: str | None = None,
    ir: Dict | None = None,
) -> pathlib.Path | None:
    """Compile Typst file to HTML using native Typst HTML export.

    Args:
        typst_file: Path to .typ file
        html_output_dir: Directory to write HTML (creates basename/index.html)
        typst_bin: Path to typst binary
        source_basename: Optional basename for output directory (defaults to typst_file.stem)
        ir: Optional IR dict for HTML post-processing (grid layout)

    Returns:
        Path to generated index.html, or None on failure
    """
    # Check Typst version supports HTML export
    supported, version = _check_typst_html_support(typst_bin)
    if not supported:
        print("ERROR: HTML export requires Typst 0.14.0 or newer.", file=sys.stderr)
        print(f"Found: typst {version}", file=sys.stderr)
        print("Please upgrade Typst: https://github.com/typst/typst/releases", file=sys.stderr)
        return None

    # Create output directory: export/<basename>/
    basename = source_basename if source_basename else typst_file.stem
    output_dir = html_output_dir / basename
    output_dir.mkdir(parents=True, exist_ok=True)

    html_path = output_dir / 'index.html'

    try:
        project_root = pathlib.Path.cwd()
        cmd = [
            typst_bin,
            'compile',
            '--root',
            str(project_root),
        ]

        # Add font paths dynamically (same as PDF compilation)
        font_paths = _get_font_paths()
        for font_path in font_paths:
            cmd.extend(['--font-path', font_path])

        # Specify HTML format and enable HTML feature flag
        cmd.extend(['--features', 'html', '--format', 'html', str(typst_file), str(html_path)])

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"HTML written to {html_path}")

            # Apply grid layout post-processing if IR is provided
            #
            # M7.5 STATUS: Grid layout temporarily disabled (2025-11-09)
            #
            # ISSUE: Current implementation regenerates HTML from IR, losing Typst's
            # semantic HTML structure (headers, paragraphs, figures). This breaks M7
            # tests that expect Typst HTML content preservation.
            #
            # NEED: Proper element matching strategy between Typst HTML and IR elements
            # OPTIONS BEING CONSIDERED:
            #   1. Inject element IDs during Typst generation for reliable matching
            #   2. Client-side JavaScript solution with separate JSON positioning data
            #   3. Hybrid approach - minimal metadata injection + JS positioning
            #
            # M7.5: Client-side grid layout approach
            #   - Preserves M7 semantic HTML structure
            #   - Adds M7.5 grid-based slide positioning via JavaScript
            #   - Degrades gracefully (works without JavaScript)
            #
            # Grid layout is applied via client-side JavaScript matching
            if ir:
                try:
                    from .generation.html_postprocess import postprocess_html

                    postprocess_html(html_path, ir)
                    print(f"Applied grid layout to {html_path}")
                except ImportError as e:
                    print(f"WARNING: Could not apply grid layout: {e}", file=sys.stderr)
                    print(
                        "Install beautifulsoup4 for grid layout: pip install beautifulsoup4",
                        file=sys.stderr,
                    )
                except Exception as e:
                    print(f"WARNING: Grid layout post-processing failed: {e}", file=sys.stderr)

            return html_path
        else:
            # Check for known Typst HTML limitations
            if "page configuration is not allowed inside of containers" in res.stderr:
                print(
                    "ERROR: Typst HTML export does not support #set page() directives.",
                    file=sys.stderr,
                )
                print(
                    "This is a known limitation - HTML export is experimental and incompatible with PDF-specific layout.",
                    file=sys.stderr,
                )
                print(
                    "See: https://github.com/typst/typst/issues/5512",
                    file=sys.stderr,
                )
            else:
                print(
                    f"ERROR: Typst HTML compile failed (exit {res.returncode}):\n{res.stderr}",
                    file=sys.stderr,
                )
            return None

    except FileNotFoundError:
        print(f"ERROR: typst binary not found at '{typst_bin}'", file=sys.stderr)
        return None
    except Exception as e:
        print(f"ERROR: HTML compilation failed: {e}", file=sys.stderr)
        return None


def _bin_exists(name: str) -> bool:
    return shutil.which(name) is not None


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

    # If HTML export is requested, copy assets BEFORE adjust_asset_paths
    # This ensures we copy from original paths, not adjusted ones
    # Assets are copied relative to export_dir (where the .typ file will be)
    ir_html = None
    if getattr(args, 'html', False):
        import copy

        from .utils.html_assets import make_html_export_portable

        # Create a deep copy of IR for HTML export
        ir_html = copy.deepcopy(ir)

        # Copy assets relative to export_dir (where Typst file will be compiled from)
        make_html_export_portable(ir_html, export_dir)

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

    # Apply OutputIntent post-processing if requested and compilation succeeded
    if ok and (
        getattr(args, 'inject_output_intent_srgb', False) or getattr(args, 'icc_profile', None)
    ):
        from .generation.pdf_postprocess import maybe_inject_output_intent

        icc_profile_path = None
        if hasattr(args, 'icc_profile') and args.icc_profile:
            icc_profile_path = pathlib.Path(args.icc_profile)

        maybe_inject_output_intent(
            pdf_path=pdf_path,
            icc_profile_path=icc_profile_path,
            use_srgb_discovery=getattr(args, 'inject_output_intent_srgb', False),
            preset=getattr(args, 'pdf_preset', None),
        )

    # Compile HTML if requested
    if getattr(args, 'html', False):
        # Generate HTML-compatible Typst code using separate HTML generator
        from .generation.html_typst_generator import generate_html_typst

        # Use the pre-prepared ir_html with copied assets
        source_basename = pathlib.Path(args.org).stem

        html_typst_code = generate_html_typst(ir_html)
        _write(typst_path, html_typst_code)

        html_result = _compile_html(
            typst_file=typst_path,
            html_output_dir=export_dir,
            typst_bin=args.typst_bin,
            source_basename=source_basename,
            ir=ir_html,
        )
        if not html_result:
            print("WARNING: HTML compilation failed, but PDF succeeded", file=sys.stderr)

        # Clean up .typ file again if it was originally cleaned
        if not args.no_clean and typst_path.exists():
            try:
                typst_path.unlink()
            except OSError:
                pass

    print(f"PDF build success={ok} pdf={pdf_path} pages={len(ir['pages'])}")
    if not ok:
        sys.exit(1)


def cmd_ir(args):
    ir = parse_org(args.org)
    print(json.dumps(ir, indent=2))


def cmd_html(args):
    """Generate HTML export with grid-based layout."""
    ir = parse_org(args.org)

    # Prepare output path
    output_file = args.output or 'index.html'
    export_dir = pathlib.Path(args.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    output_path = (
        export_dir / output_file
        if not pathlib.Path(output_file).is_absolute()
        else pathlib.Path(output_file)
    )

    # Generate HTML
    print("Generating HTML export...")
    separate_assets = getattr(args, 'separate_assets', False)
    generate_story_html(ir, str(output_path), source_file=args.org, separate_assets=separate_assets)

    asset_mode = "separate files" if separate_assets else "inline"
    print(f"HTML written to: {output_path} (CSS/JS: {asset_mode})")
    print(f"Pages: {len(ir['pages'])}")
    print("\nOpen the file in a browser to view.")
    print("Navigation: Spacebar/ArrowDown (next), ArrowUp (previous), Home/End")


def cmd_validate(args):
    ir = parse_org(args.org)
    result = validate_ir(ir, strict_assets=args.strict_assets)
    for issue in result.issues:
        print(f"{issue.severity.upper()}: {issue.path}: {issue.message}")
    if result.ok():
        print("IR valid: no errors")
    if not result.ok():
        sys.exit(1)


def _resolve_asset_path(src: str, org_path: pathlib.Path) -> pathlib.Path:
    """Resolve an asset path relative to the org file's directory.

    Resolution order:
    1. Absolute paths are used as-is
    2. Relative to org file directory
    3. Relative to parent directory (common pattern for shared assets)
    4. Relative to current working directory

    Args:
        src: Asset path string (absolute or relative)
        org_path: Path to the org file

    Returns:
        Resolved pathlib.Path
    """
    if pathlib.Path(src).is_absolute():
        return pathlib.Path(src)

    org_dir = org_path.parent

    # Try relative to org file directory first
    relative_path = org_dir / src
    if relative_path.exists():
        return relative_path.resolve()

    # Try relative to parent directory (common pattern for shared assets)
    parent_path = org_dir.parent / src
    if parent_path.exists():
        return parent_path.resolve()

    # Try relative to current working directory as fallback
    cwd_path = pathlib.Path(src)
    if cwd_path.exists():
        return cwd_path.resolve()

    # Return the relative path even if it doesn't exist (might exist later)
    return relative_path


def _collect_asset_paths(ir, org_path: pathlib.Path) -> List[pathlib.Path]:
    """Collect all asset file paths referenced in the intermediate representation.

    Args:
        ir: Intermediate representation dictionary
        org_path: Path to the org file (used to resolve relative asset paths)

    Returns:
        List of pathlib.Path objects for all referenced asset files that exist
    """
    asset_paths = []

    for page in ir.get('pages', []):
        for el in page.get('elements', []):
            # Check for figure assets (images)
            fig = el.get('figure')
            if fig and fig.get('src'):
                asset_path = _resolve_asset_path(fig['src'], org_path)
                if asset_path.exists():
                    asset_paths.append(asset_path)

            # Check for PDF assets
            pdf = el.get('pdf')
            if pdf and pdf.get('src'):
                asset_path = _resolve_asset_path(pdf['src'], org_path)
                if asset_path.exists():
                    asset_paths.append(asset_path)

            # Check for SVG assets
            svg = el.get('svg')
            if svg and svg.get('src'):
                asset_path = _resolve_asset_path(svg['src'], org_path)
                if asset_path.exists():
                    asset_paths.append(asset_path)

    return list(set(asset_paths))  # Remove duplicates


def _collect_font_files(ir) -> List[pathlib.Path]:
    """Collect all font files used in the document.

    Args:
        ir: Intermediate representation dictionary

    Returns:
        List of pathlib.Path objects for all font files that are used
    """
    from .fonts import _get_font_paths
    from .utils.font_discovery import analyze_font_usage

    # Get fonts referenced in document
    font_usage = analyze_font_usage(ir)
    font_names = font_usage.get('fonts_found', set())

    if not font_names:
        return []

    # Get font search paths
    font_paths = _get_font_paths()

    # Collect all font files for the referenced font families
    font_files = []
    font_extensions = {'.ttf', '.otf', '.woff', '.woff2'}

    for font_name in font_names:
        # Search in all font paths
        for font_path_str in font_paths:
            font_path = pathlib.Path(font_path_str)
            if not font_path.exists():
                continue

            # Look for font files matching this font family
            # Font files are typically named like: Inter-Regular.woff2, Inter-Bold.ttf, etc.
            try:
                for file_path in font_path.rglob('*'):
                    if file_path.suffix.lower() in font_extensions:
                        # Check if filename starts with font family name (case-insensitive)
                        if file_path.stem.lower().startswith(font_name.lower().replace(' ', '')):
                            font_files.append(file_path)
            except Exception:
                pass

    return list(set(font_files))  # Remove duplicates


def cmd_watch(args):
    org_path = pathlib.Path(args.org)
    if not org_path.exists():
        print(f"ERROR: org file not found: {org_path}", file=sys.stderr)
        sys.exit(1)
    export_dir = pathlib.Path(args.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    last_hash = None
    last_asset_paths = set()

    # Determine mode
    html_mode = getattr(args, 'html_mode', False)
    mode_desc = "html" if html_mode else f"pdf={args.pdf}"
    print(f"Watching {org_path} interval={args.interval}s mode={mode_desc} (once={args.once})")

    def compute_hash(p: pathlib.Path):
        try:
            data = p.read_bytes()
            return hashlib.sha256(data).hexdigest()
        except Exception:
            return None

    def compute_combined_hash():
        """Compute combined hash of org file and all asset files."""
        hashes = []

        # Hash the org file
        org_hash = compute_hash(org_path)
        if org_hash:
            hashes.append(org_hash)

        # Parse org to get current asset paths (before adjust_asset_paths modifies them)
        try:
            ir = parse_org(str(org_path))
            current_asset_paths = _collect_asset_paths(ir, org_path)

            # Hash all asset files
            for asset_path in sorted(current_asset_paths):  # Sort for consistent ordering
                asset_hash = compute_hash(asset_path)
                if asset_hash:
                    hashes.append(f"{asset_path}:{asset_hash}")

            return hashlib.sha256('|'.join(hashes).encode()).hexdigest(), set(current_asset_paths)
        except Exception:
            return org_hash, set() if org_hash else (None, set())

    def build_once():
        ir = parse_org(str(org_path))

        # HTML mode build
        if html_mode:
            output_file = 'index.html'
            output_path = export_dir / output_file
            separate_assets = getattr(args, 'separate_assets', False)
            generate_story_html(
                ir, str(output_path), source_file=str(org_path), separate_assets=separate_assets
            )
            asset_mode = "separate files" if separate_assets else "inline"
            print(f"[watch] Rebuilt HTML: {output_path} (CSS/JS: {asset_mode})")
            return True

        # PDF/Typst mode build (existing logic)
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

            # Apply OutputIntent post-processing if requested and compilation succeeded
            if ok and (
                getattr(args, 'inject_output_intent_srgb', False)
                or getattr(args, 'icc_profile', None)
            ):
                from .generation.pdf_postprocess import maybe_inject_output_intent

                icc_profile_path = None
                if hasattr(args, 'icc_profile') and args.icc_profile:
                    icc_profile_path = pathlib.Path(args.icc_profile)

                maybe_inject_output_intent(
                    pdf_path=pdf_path,
                    icc_profile_path=icc_profile_path,
                    use_srgb_discovery=getattr(args, 'inject_output_intent_srgb', False),
                    preset=getattr(args, 'pdf_preset', None),
                )

            # Compile HTML if requested
            if getattr(args, 'html', False):
                # Regenerate HTML-specific Typst code
                from .generation.html_typst_generator import generate_html_typst

                html_typst_code = generate_html_typst(ir)
                _write(typst_path, html_typst_code)

                # Use source org file basename for HTML output directory
                source_basename = org_path.stem
                html_result = _compile_html(
                    typst_file=typst_path,
                    html_output_dir=export_dir,
                    typst_bin=args.typst_bin,
                    source_basename=source_basename,
                    ir=ir,
                )
                if html_result:
                    print(f"[watch] Rebuilt HTML: {html_result}")

            print(f"[watch] Rebuilt PDF success={ok} pages={len(ir['pages'])}")
            return ok
        else:
            typst_code = generate_typst(ir)
            _write(typst_path, typst_code)
            print(f"[watch] Rebuilt Typst pages={len(ir['pages'])}")
            return True

    while True:
        h, current_asset_paths = compute_combined_hash()

        # Check if org file, asset files, or asset list changed
        assets_changed = current_asset_paths != last_asset_paths
        hash_changed = h and h != last_hash

        if hash_changed or assets_changed:
            if assets_changed and not hash_changed:
                print(f"[watch] Asset files changed: {len(current_asset_paths)} assets")
            elif hash_changed and assets_changed:
                print(f"[watch] Org file and assets changed: {len(current_asset_paths)} assets")
            else:
                print("[watch] Org file changed")

            last_hash = h
            last_asset_paths = current_asset_paths

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
            # No changes but in --once mode ensure we build at least once
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
        font_usage = analyze_font_usage(ir)

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


def cmd_snapshot(args):
    """Create a snapshot package of the org file, all referenced assets, and compiled PDF.

    Creates a directory with format: yymmdd-<doc_name_slug>_snapshot/
    Contains:
    - The .org source file
    - All referenced media assets (images, PDFs, SVGs)
    - The compiled PDF output

    Similar to InDesign's "Package" feature.
    """
    from datetime import datetime

    org_path = pathlib.Path(args.org)
    if not org_path.exists():
        print(f"❌ Error: org file not found: {org_path}", file=sys.stderr)
        sys.exit(1)

    print(f"📦 Creating snapshot for: {org_path.name}")
    print("=" * 50)

    # Parse the org file to get IR
    print("🔍 Scanning document for assets and fonts...")
    ir = parse_org(str(org_path))

    # Collect all referenced assets
    asset_paths = _collect_asset_paths(ir, org_path)

    # Collect all font files
    font_files = _collect_font_files(ir)

    # Create snapshot directory name: yymmdd-doc_name_slug_snapshot
    now = datetime.now()
    date_prefix = now.strftime("%y%m%d")
    doc_slug = org_path.stem.replace(' ', '_').replace('-', '_').lower()
    snapshot_dir_name = f"{date_prefix}-{doc_slug}_snapshot"

    snapshot_dir = pathlib.Path(args.output_dir) / snapshot_dir_name

    # Create snapshot directory structure
    print(f"📁 Creating snapshot directory: {snapshot_dir}")
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    assets_dir = snapshot_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    fonts_dir = snapshot_dir / "fonts"
    fonts_dir.mkdir(exist_ok=True)

    # Copy org file and update asset paths
    print(f"📄 Copying org file: {org_path.name}")
    org_dest = snapshot_dir / org_path.name

    # Read org file content
    org_content = org_path.read_text(encoding='utf-8')

    # Extract all file references from org content using regex
    # This captures the exact strings used in the org file
    import re

    file_link_pattern = re.compile(r'\[\[file:([^\]]+)\]\]')
    prop_pattern = re.compile(r':(SRC|SVG|PDF|IMAGE):\s*(\S+)')

    org_file_refs = set()
    for match in file_link_pattern.finditer(org_content):
        org_file_refs.add(match.group(1))
    for match in prop_pattern.finditer(org_content):
        org_file_refs.add(match.group(2))

    # Build a mapping from resolved absolute paths to their org file reference strings
    # Use same resolution logic as _collect_asset_paths for consistency
    asset_to_org_ref = {}
    for ref_str in org_file_refs:
        resolved = _resolve_asset_path(ref_str, org_path)
        if resolved.exists():
            asset_to_org_ref[str(resolved)] = ref_str

    # Build mapping of old paths to new paths
    asset_path_mapping = {}

    # Copy all referenced assets
    print(f"🖼️  Copying {len(asset_paths)} referenced assets...")
    copied_assets = []
    for asset_path in asset_paths:
        try:
            # Preserve relative directory structure for assets
            # If asset is in a subdirectory, recreate that structure
            relative_name = asset_path.name
            asset_dest = assets_dir / relative_name

            # Handle duplicate filenames by adding parent directory
            if asset_dest.exists() and not asset_dest.samefile(asset_path):
                relative_name = f"{asset_path.parent.name}_{asset_path.name}"
                asset_dest = assets_dir / relative_name

            shutil.copy2(asset_path, asset_dest)
            copied_assets.append(relative_name)

            # Map the original org file reference string to the new path
            new_path = f"assets/{relative_name}"
            asset_key = str(asset_path.resolve())
            if asset_key in asset_to_org_ref:
                org_ref_string = asset_to_org_ref[asset_key]
                asset_path_mapping[org_ref_string] = new_path

            print(f"  ✅ {relative_name}")
        except Exception as e:
            print(f"  ⚠️  Failed to copy {asset_path.name}: {e}", file=sys.stderr)

    # Copy all font files
    print(f"🔤 Copying {len(font_files)} font files...")
    copied_fonts = []
    for font_file in font_files:
        try:
            font_dest = fonts_dir / font_file.name

            # Handle duplicate filenames by adding parent directory
            if font_dest.exists() and not font_dest.samefile(font_file):
                font_dest = fonts_dir / f"{font_file.parent.name}_{font_file.name}"

            shutil.copy2(font_file, font_dest)
            copied_fonts.append(font_file.name)
            print(f"  ✅ {font_file.name}")
        except Exception as e:
            print(f"  ⚠️  Failed to copy {font_file.name}: {e}", file=sys.stderr)

    # Update asset paths in org file content
    # Look for [[file:path]] links and :SRC: properties
    # All paths in org files should be relative
    print("🔧 Updating asset paths in org file...")
    updated_count = 0

    # Sort keys by length (longest first) to avoid partial replacements
    for old_path in sorted(asset_path_mapping.keys(), key=len, reverse=True):
        new_path = asset_path_mapping[old_path]

        # Make new_path relative with ./ prefix for consistency
        new_relative_path = f"./{new_path}"

        # Replace in [[file:...]] links
        old_link = f"[[file:{old_path}]]"
        new_link = f"[[file:{new_relative_path}]]"
        if old_link in org_content:
            org_content = org_content.replace(old_link, new_link)
            updated_count += 1

        # Replace in :SRC: properties (also make relative)
        old_src = f":SRC: {old_path}"
        new_src = f":SRC: {new_relative_path}"
        if old_src in org_content:
            org_content = org_content.replace(old_src, new_src)
            updated_count += 1

        # Replace in legacy :SVG: properties
        old_svg = f":SVG: {old_path}"
        new_svg = f":SVG: {new_relative_path}"
        if old_svg in org_content:
            org_content = org_content.replace(old_svg, new_svg)
            updated_count += 1

        # Replace in legacy :PDF: properties
        old_pdf = f":PDF: {old_path}"
        new_pdf = f":PDF: {new_relative_path}"
        if old_pdf in org_content:
            org_content = org_content.replace(old_pdf, new_pdf)
            updated_count += 1

        # Replace in legacy :IMAGE: properties (if any)
        old_image = f":IMAGE: {old_path}"
        new_image = f":IMAGE: {new_relative_path}"
        if old_image in org_content:
            org_content = org_content.replace(old_image, new_image)
            updated_count += 1

    if updated_count > 0:
        print(f"  ✅ Updated {updated_count} asset path references")

    # Write the updated org file
    org_dest.write_text(org_content, encoding='utf-8')

    # Compile PDF by default (unless --no-build-pdf is specified)
    pdf_path = None
    pdf_output_name = f"{org_path.stem}.pdf"
    build_pdf = not getattr(args, 'no_build_pdf', False)

    if build_pdf:
        print("\n📄 Compiling PDF...")

        try:
            import os

            # Parse the UPDATED org file from the snapshot directory
            # This ensures we're testing that the snapshot is self-contained
            ir_snapshot = parse_org(str(org_dest))

            # Try to auto-download missing fonts
            _attempt_auto_download_missing_fonts(ir_snapshot)

            # Build PDF directly in snapshot directory
            # The updated org file already has correct ./assets/... paths
            typst_path = snapshot_dir / 'deck.typ'
            pdf_temp_path = snapshot_dir / pdf_output_name

            # Adjust asset paths relative to snapshot directory
            adjust_asset_paths(ir_snapshot, snapshot_dir)

            # Change to snapshot directory for compilation
            # This ensures Typst can find all files with relative paths
            original_cwd = pathlib.Path.cwd()
            try:
                os.chdir(snapshot_dir)

                ok = _compile_with_fallback(
                    ir=ir_snapshot,
                    export_dir=snapshot_dir,
                    typst_path=typst_path,
                    pdf_path=pdf_temp_path,
                    typst_bin=args.typst_bin,
                    sanitize=getattr(args, 'sanitize_pdfs', False),
                    no_clean=False,
                )
            finally:
                os.chdir(original_cwd)

            if ok and pdf_temp_path.exists():
                pdf_path = pdf_temp_path
                print(f"  ✅ PDF compiled successfully: {pdf_output_name}")

            # Clean up intermediate typst file
            if typst_path.exists():
                typst_path.unlink()

        except Exception as e:
            print(f"  ⚠️  PDF compilation failed: {e}", file=sys.stderr)

    # Create a README file in the snapshot
    readme_path = snapshot_dir / "README.txt"
    readme_content = f"""Pagemaker Snapshot
==================

Created: {now.strftime("%Y-%m-%d %H:%M:%S")}
Source: {org_path.name}

Contents:
- {org_path.name} (source document)
- assets/ ({len(copied_assets)} files)
- fonts/ ({len(copied_fonts)} files)
"""
    if pdf_path and pdf_path.exists():
        readme_content += f"- {pdf_output_name} (compiled PDF)\n"
    elif build_pdf:
        readme_content += "- PDF compilation was attempted but failed\n"

    readme_content += f"""
This snapshot contains all files needed to reproduce the document.
Asset paths have been updated to reference the assets/ directory.
Font files are available in the fonts/ directory.

To rebuild:
  pagemaker pdf {org_path.name}
"""

    readme_path.write_text(readme_content, encoding='utf-8')

    # Summary
    print("\n" + "=" * 50)
    print("✅ Snapshot created successfully!")
    print(f"📂 Location: {snapshot_dir}")
    print(f"📄 Org file: {org_path.name}")
    print(f"🖼️  Assets: {len(copied_assets)} files")
    print(f"🔤 Fonts: {len(copied_fonts)} files")
    if pdf_path and pdf_path.exists():
        print(f"📑 PDF: {pdf_output_name}")
    elif build_pdf:
        print("⚠️  PDF compilation failed (snapshot created without PDF)")
    print(
        f"\n💡 Total size: {_format_size(sum(f.stat().st_size for f in snapshot_dir.rglob('*') if f.is_file()))}"
    )

    return snapshot_dir


def _generate_font_specimen_org(fonts_info: list, specimen_type: str = 'showcase') -> str:
    """Generate org-mode content for font specimen"""

    if specimen_type == 'showcase':
        # Beautiful showcase with various text samples
        content = """#+TITLE: Font Specimen Showcase
#+PAGESIZE: A4
#+ORIENTATION: portrait  
#+GRID: 12x16
#+MARGINS: 15,15,15,15
#+CUSTOM_STYLE: #page(margin: 15mm); #set text(font: "Inter", size: 10pt)

* Available Font Families

This specimen showcases all available fonts in your pagemaker installation.

"""

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
            content += f"""** {font_name}
:PROPERTIES:
:TYPE: header
:AREA: A{row},L{row}
:END:

#set text(font: "{font_name}", weight: "bold", size: 14pt)
{font_name} — {files_count} files ({size_info})

"""
            row += 1

            # Sample text in this font
            content += f"""*** Sample Text
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

"""
            row += 4

            if row > 14:  # Start new page
                content += '\n\\pagebreak\n\n'
                row = 1

    elif specimen_type == 'comparison':
        # Side-by-side comparison of fonts
        content = """#+TITLE: Font Comparison Sheet
#+PAGESIZE: A4
#+ORIENTATION: landscape
#+GRID: 16x10
#+MARGINS: 10,10,10,10
#+CUSTOM_STYLE: #page(margin: 10mm); #set text(font: "Inter", size: 9pt)

* Font Comparison

Direct comparison of all available fonts using identical text samples.

"""
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

            content += f"""** {font_name}
:PROPERTIES:
:TYPE: body
:AREA: {chr(65 + col - 1)}{row},{chr(65 + col + 6)}{row + 1}
:PADDING: 2
:END:

#set text(font: "{font_name}", size: 8pt, weight: "bold")
{font_name}

#set text(size: 9pt, weight: "normal")
{sample_text}

"""
            col += 8

    else:  # simple list
        content = """#+TITLE: Font List
#+CUSTOM_STYLE: #set text(font: "Inter", size: 11pt)

* Available Fonts

"""
        for font_info in fonts_info:
            content += f"""** {font_info['name']}
#set text(font: "{font_info['name']}")
Sample text in {font_info['name']} — {font_info['files_count']} files ({font_info['size_human']})

"""

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
    pdf.add_argument(
        '--inject-output-intent-srgb',
        action='store_true',
        help='Embed sRGB OutputIntent via Ghostscript post-processing',
    )
    pdf.add_argument(
        '--icc-profile',
        help='Path to ICC profile to embed as OutputIntent (takes precedence over --inject-output-intent-srgb)',
    )
    pdf.add_argument(
        '--pdf-preset',
        choices=['screen', 'printer', 'prepress'],
        help='PDF quality preset for Ghostscript processing (only applies with OutputIntent injection)',
    )
    pdf.add_argument(
        '--html',
        action='store_true',
        help='Also compile to HTML using Typst native HTML export (requires Typst 0.14+)',
    )
    pdf.set_defaults(func=cmd_pdf)

    irp = sub.add_parser('ir', help='emit IR JSON')
    irp.add_argument('org')
    irp.set_defaults(func=cmd_ir)

    html = sub.add_parser('html', help='org -> HTML (grid-based web export)')
    html.add_argument('org', help='org file to convert')
    html.add_argument(
        '-o', '--output', default='index.html', help='output HTML filename (default: index.html)'
    )
    html.add_argument(
        '--export-dir', default=DEFAULT_EXPORT_DIR, help='export directory (default: export)'
    )
    html.add_argument(
        '--separate-assets',
        action='store_true',
        help='Generate separate CSS/JS files instead of inline (easier to customize)',
    )
    html.set_defaults(func=cmd_html)

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
    watch.add_argument(
        '--inject-output-intent-srgb',
        action='store_true',
        help='Embed sRGB OutputIntent via Ghostscript post-processing',
    )
    watch.add_argument(
        '--icc-profile',
        help='Path to ICC profile to embed as OutputIntent (takes precedence over --inject-output-intent-srgb)',
    )
    watch.add_argument(
        '--pdf-preset',
        choices=['screen', 'printer', 'prepress'],
        help='PDF quality preset for Ghostscript processing (only applies with OutputIntent injection)',
    )
    watch.add_argument(
        '--html',
        action='store_true',
        help='Also compile to HTML using Typst native HTML export (requires Typst 0.14+)',
    )
    watch.add_argument(
        '--html-mode',
        action='store_true',
        help='Generate HTML export instead of PDF/Typst',
    )
    watch.add_argument(
        '--separate-assets',
        action='store_true',
        help='Generate separate CSS/JS files (story mode only)',
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

    # snapshot command
    snapshot_parser = sub.add_parser(
        'snapshot',
        help='create snapshot package of org file, assets, and PDF (like InDesign Package)',
    )
    snapshot_parser.add_argument('org', help='org file to snapshot')
    snapshot_parser.add_argument(
        '-o',
        '--output-dir',
        default='.',
        help='directory to create snapshot in (default: current directory)',
    )
    snapshot_parser.add_argument(
        '--no-build-pdf',
        action='store_true',
        help='skip PDF compilation (PDF is built by default)',
    )
    snapshot_parser.add_argument(
        '--typst-bin',
        default='typst',
        help='path to typst binary (default: typst)',
    )
    snapshot_parser.add_argument(
        '--sanitize-pdfs',
        action='store_true',
        help='attempt to sanitize PDFs and fallback to SVG if necessary',
    )
    snapshot_parser.set_defaults(func=cmd_snapshot)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
