"""Font discovery and caching utilities."""

import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set


@dataclass
class FontFamily:
    """Font family information."""

    name: str
    files: List[str]
    total_size: int

    @property
    def total_size_human(self) -> str:
        """Human-readable size string."""
        # Import here to avoid circular imports
        size_bytes = self.total_size
        if size_bytes == 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0
        size = float(size_bytes)

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"


@dataclass
class FontDiscoveryResult:
    """Result of font discovery scan."""

    exists: bool
    families: Dict[str, FontFamily]
    scan_time: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for caching."""
        return {
            'exists': self.exists,
            'families': {name: asdict(family) for name, family in self.families.items()},
            'scan_time': self.scan_time,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FontDiscoveryResult':
        """Create from dictionary."""
        families = {}
        for name, family_data in data.get('families', {}).items():
            families[name] = FontFamily(**family_data)

        return cls(
            exists=data.get('exists', False),
            families=families,
            scan_time=data.get('scan_time', 0.0),
        )


class FontCache:
    """Font discovery cache manager."""

    def __init__(self, cache_dir: Optional[pathlib.Path] = None):
        if cache_dir is None:
            cache_dir = pathlib.Path.home() / '.pagemaker' / 'cache'

        self.cache_dir = cache_dir
        self.cache_file = cache_dir / 'font_discovery.json'
        self.cache_duration = 3600  # 1 hour in seconds

    def _ensure_cache_dir(self):
        """Ensure cache directory exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cached_result(self, cache_key: str) -> Optional[FontDiscoveryResult]:
        """Get cached font discovery result if valid."""
        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file) as f:
                cache_data = json.load(f)

            if cache_key not in cache_data:
                return None

            entry = cache_data[cache_key]

            # Check if cache is expired
            cache_time = entry.get('cached_at', 0)
            if time.time() - cache_time > self.cache_duration:
                return None

            return FontDiscoveryResult.from_dict(entry['result'])

        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def cache_result(self, cache_key: str, result: FontDiscoveryResult):
        """Cache font discovery result."""
        self._ensure_cache_dir()

        # Load existing cache
        cache_data = {}
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    cache_data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                cache_data = {}

        # Add new entry
        cache_data[cache_key] = {'result': result.to_dict(), 'cached_at': time.time()}

        # Write back to cache
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except OSError:
            pass  # Ignore cache write failures

    def clear_cache(self):
        """Clear font cache."""
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
        except OSError:
            pass


def scan_font_directories(font_paths: List[str]) -> Dict[str, FontDiscoveryResult]:
    """Scan font directories and return discovery results."""
    results = {}

    for font_path in font_paths:
        path_obj = pathlib.Path(font_path)
        cache_key = f"scan_{path_obj.name}_{font_path}"

        # Try cache first
        cache = FontCache()
        cached_result = cache.get_cached_result(cache_key)
        if cached_result is not None:
            results[font_path] = cached_result
            continue

        # Perform actual scan
        start_time = time.time()
        result = _scan_single_directory(path_obj)
        scan_time = time.time() - start_time

        discovery_result = FontDiscoveryResult(
            exists=result['exists'], families=result['families'], scan_time=scan_time
        )

        # Cache the result
        cache.cache_result(cache_key, discovery_result)
        results[font_path] = discovery_result

    return results


def _scan_single_directory(font_dir: pathlib.Path) -> Dict[str, Any]:
    """Scan a single font directory."""
    if not font_dir.exists():
        return {'exists': False, 'families': {}}

    families = {}
    font_extensions = {'.ttf', '.otf', '.ttc', '.otc', '.woff', '.woff2'}

    try:
        for font_file in font_dir.rglob('*'):
            if font_file.is_file() and font_file.suffix.lower() in font_extensions:
                # Extract family name from path structure
                # Assume structure: font_dir / Family_Name / font_files
                if font_file.parent != font_dir:
                    family_name = font_file.parent.name
                else:
                    # Fallback: use filename without extension
                    family_name = font_file.stem

                # Clean up family name (replace underscores with spaces)
                family_name = family_name.replace('_', ' ')

                if family_name not in families:
                    families[family_name] = FontFamily(name=family_name, files=[], total_size=0)

                families[family_name].files.append(str(font_file))
                try:
                    families[family_name].total_size += font_file.stat().st_size
                except OSError:
                    pass

    except OSError:
        pass

    return {'exists': True, 'families': families}


def collect_font_names(font_paths: List[str]) -> Set[str]:
    """Collect all available font family names from given paths."""
    all_names = set()

    scan_results = scan_font_directories(font_paths)
    for result in scan_results.values():
        if result.exists:
            all_names.update(result.families.keys())

    return all_names


# Google Fonts API Functions


def get_google_fonts_api_data() -> dict:
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


def download_font_file(url: str, dest_path: pathlib.Path) -> bool:
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


def install_google_font(font_family: str, variants=None, force: bool = False) -> bool:
    """Install a Google Font to assets/fonts/"""
    # Import here to avoid circular imports
    from ..fonts import _format_size

    assets_fonts = pathlib.Path('assets/fonts')
    font_dir = assets_fonts / font_family

    # Check if already installed
    if font_dir.exists() and not force:
        existing_files = list(font_dir.glob('*.ttf')) + list(font_dir.glob('*.otf'))
        if existing_files:
            print(f"✅ Font '{font_family}' already installed ({len(existing_files)} files)")
            return True

    # Get Google Fonts data
    fonts_data = get_google_fonts_api_data()

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
        if download_font_file(url, dest_path):
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


def search_google_fonts(query: str, limit: int = 10) -> list:
    """Search Google Fonts by name"""
    fonts_data = get_google_fonts_api_data()
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


# Font Analysis Functions


def analyze_font_usage(ir: dict) -> dict:
    """Analyze which fonts are referenced in the IR.

    Sources scanned:
    - CUSTOM_STYLE meta/header blocks (quoted font names)
    - STYLE_* meta declarations (quoted or unquoted font: ...)
    - Global FONT meta directive
    - Inline Typst directives in element content (#set text(font: "..."))
    """
    # Import here to avoid circular imports
    from ..fonts import _collect_real_font_names, _get_font_paths

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
    font_meta = meta.get('FONT')
    if isinstance(font_meta, str) and font_meta.strip():
        n = font_meta.strip()
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


def validate_fonts_in_build(ir: dict, strict: bool = False) -> bool:
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


def attempt_auto_download_missing_fonts(ir: dict) -> None:
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


# Font Discovery Caching Functions


def get_font_discovery_cache_path() -> pathlib.Path:
    """Get path to font discovery cache file"""
    cache_dir = pathlib.Path.home() / '.pagemaker' / 'cache'
    return cache_dir / 'font_discovery.json'


def is_cache_valid(cache_path: pathlib.Path, font_paths: list) -> bool:
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


def save_font_discovery_cache(cache_path: pathlib.Path, font_paths: list, discovery_results: dict):
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


def get_cached_font_discovery() -> dict:
    """Get font discovery results with caching"""
    # Import here to avoid circular imports
    from ..fonts import _get_bundled_fonts, _get_font_paths, _get_project_fonts

    font_paths = _get_font_paths()
    cache_path = get_font_discovery_cache_path()

    # Try to use cache
    if is_cache_valid(cache_path, font_paths):
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
    save_font_discovery_cache(cache_path, font_paths, results)

    return results
