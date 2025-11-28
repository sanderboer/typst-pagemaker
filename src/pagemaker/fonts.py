import os
import pathlib
import re
from typing import Any, Dict, List, Set


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable form"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


def _get_font_paths() -> List[str]:
    """Get font paths in order of preference, supporting repo and installed usage.

    Order:
    1) Project-local assets/fonts (+/static), with repo-root fallback
    2) Examples assets/fonts (+/static), with repo-root fallback
    3) Packaged fonts next to this module (installed or repo): <module_dir>/fonts and family subdirs
    4) Repo source fonts at src/pagemaker/fonts (when running from project root without importing package)
    """
    font_paths: List[str] = []

    # Detect repo root relative to this module when available (src/pagemaker/ -> repo root)
    module_dir = pathlib.Path(__file__).resolve().parent
    repo_root = module_dir.parent.parent
    repo_root_exists = (repo_root / 'examples' / 'assets' / 'fonts').exists() or (
        repo_root / 'assets' / 'fonts'
    ).exists()

    # 1. Project-local assets/fonts (for development/user customization)
    local_fonts = pathlib.Path('assets/fonts')
    if local_fonts.exists():
        font_paths.append(str(local_fonts))
        static_path = local_fonts / 'static'
        if static_path.exists():
            font_paths.append(str(static_path))
    # 1b. Repo-root fallback for assets/fonts when CWD differs
    if repo_root_exists:
        repo_assets = repo_root / 'assets' / 'fonts'
        if repo_assets.exists():
            font_paths.append(str(repo_assets))
            repo_assets_static = repo_assets / 'static'
            if repo_assets_static.exists():
                font_paths.append(str(repo_assets_static))

    # 2. Examples assets/fonts as fallback (example fonts)
    examples_fonts = pathlib.Path('examples/assets/fonts')
    if examples_fonts.exists():
        font_paths.append(str(examples_fonts))
        static_path = examples_fonts / 'static'
        if static_path.exists():
            font_paths.append(str(static_path))
    # 2b. Repo-root fallback for examples/assets/fonts
    if repo_root_exists:
        repo_examples = repo_root / 'examples' / 'assets' / 'fonts'
        if repo_examples.exists():
            font_paths.append(str(repo_examples))
            repo_examples_static = repo_examples / 'static'
            if repo_examples_static.exists():
                font_paths.append(str(repo_examples_static))

    # 3. Packaged fonts next to this module (works for installed package and repo src)
    # Avoid relying on import-time resolution; use __file__ to find the module directory
    module_fonts_base = module_dir / 'fonts'
    if module_fonts_base.exists():
        # Include both normalized and raw path forms to tolerate non-normalized __file__ in callers
        font_paths.append(str(module_fonts_base))
        raw_module_fonts_base = pathlib.Path(__file__).parent / 'fonts'
        if raw_module_fonts_base.exists():
            font_paths.append(str(raw_module_fonts_base))
        # Add known families explicitly and any other family subdirectories
        key_families = ['Inter', 'Crimson_Pro', 'JetBrains_Mono']
        # Include all subdirectories under fonts for completeness
        try:
            for sub in module_fonts_base.iterdir():
                if sub.is_dir() and not sub.name.startswith('.'):
                    font_paths.append(str(sub))
        except Exception:
            pass
        # Ensure key families are included even if filtered by above
        for fam in key_families:
            sub = module_fonts_base / fam
            if sub.exists():
                font_paths.append(str(sub))

    # 4. Explicit repo source path if running from project root without importing package
    repo_src_fonts = pathlib.Path('src/pagemaker/fonts')
    if repo_src_fonts.exists():
        font_paths.append(str(repo_src_fonts))
        try:
            for sub in repo_src_fonts.iterdir():
                if sub.is_dir() and not sub.name.startswith('.'):
                    font_paths.append(str(sub))
        except Exception:
            pass

    # Return unique paths, preserving order
    return list(dict.fromkeys(fp for fp in font_paths if fp))


def _discover_fonts_in_path(font_path: pathlib.Path) -> Dict:
    """Discover fonts in a given path and return structured information"""
    font_info: Dict = {'path': str(font_path), 'exists': font_path.exists(), 'families': {}}

    if not font_path.exists():
        return font_info

    # Look for font files (TTF, OTF, WOFF, WOFF2)
    font_extensions = {'.ttf', '.otf', '.woff', '.woff2'}

    try:
        for item in font_path.rglob('*'):
            if item.is_file() and item.suffix.lower() in font_extensions:
                # Extract family name from path structure
                relative_path = item.relative_to(font_path)
                family_name = relative_path.parts[0] if len(relative_path.parts) > 1 else 'Root'

                if family_name not in font_info['families']:
                    font_info['families'][family_name] = {'files': [], 'total_size': 0}

                file_size = item.stat().st_size
                font_info['families'][family_name]['files'].append(
                    {
                        'name': item.name,
                        'path': str(item),
                        'size': file_size,
                        'size_human': _format_size(file_size),
                    }
                )
                font_info['families'][family_name]['total_size'] += file_size

        # Add human-readable sizes for families
        for family in font_info['families'].values():
            family['total_size_human'] = _format_size(family['total_size'])

    except Exception as e:
        font_info['error'] = str(e)

    return font_info


def _get_bundled_fonts() -> Dict:
    """Get information about bundled fonts"""
    try:
        import pagemaker

        package_path = pathlib.Path(pagemaker.__file__).parent
        package_fonts_path = package_path / 'fonts'
        return _discover_fonts_in_path(package_fonts_path)
    except Exception:
        return {'path': 'Not found', 'exists': False, 'families': {}}


def _get_project_fonts() -> Dict:
    """Get information about project fonts in assets/fonts"""
    assets_fonts = pathlib.Path('assets/fonts')
    return _discover_fonts_in_path(assets_fonts)


def _collect_real_font_names(paths: List[str]) -> Set[str]:
    """Collect real font family names via fontTools (with TTC support).
    Returns a set of family names found across provided paths. Empty set when fontTools missing.
    Only TTF/OTF/TTC/OTC are considered (Typst-usable font formats).
    """
    names: Set[str] = set()
    try:
        from fontTools.ttLib import TTFont
        from fontTools.ttLib.ttCollection import TTCollection
    except Exception:
        return names
    font_exts = {'.ttf', '.otf', '.ttc', '.otc'}
    for p in paths:
        try:
            root = pathlib.Path(p)
            if not root.exists():
                continue
            for f in root.rglob('*'):
                try:
                    if not f.is_file() or f.suffix.lower() not in font_exts:
                        continue
                    if f.suffix.lower() in {'.ttc', '.otc'}:
                        tc = TTCollection(str(f))
                        for ttf in tc.fonts:
                            nm = ttf.get('name')
                            if not nm:
                                continue
                            for rec in nm.names:
                                if rec.nameID in (1, 16):
                                    try:
                                        names.add(rec.toUnicode().strip())
                                    except Exception:
                                        pass
                    else:
                        t = TTFont(str(f), lazy=True)
                        nm = t.get('name')
                        if nm:
                            for rec in nm.names:
                                if rec.nameID in (1, 16):
                                    try:
                                        names.add(rec.toUnicode().strip())
                                    except Exception:
                                        pass
                        try:
                            t.close()
                        except Exception:
                            pass
                except Exception:
                    continue
        except Exception:
            continue
    return {n for n in names if n}


def analyze_font_usage(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze which fonts are referenced in the IR.

    Sources scanned:
    - CUSTOM_STYLE meta/header blocks (quoted font names)
    - STYLE_* meta declarations (quoted or unquoted font: ...)
    - Global FONT meta directive
    - Inline Typst directives in element content (#set text(font: "..."))

    Returns:
        Dict with keys:
        - fonts_found: Set[str] - all font families referenced
        - missing_fonts: Set[str] - fonts not available in font paths
        - usage_locations: List[Dict] - where each font was found
    """
    font_usage: Dict[str, Any] = {
        'fonts_found': set(),
        'missing_fonts': set(),
        'usage_locations': [],
    }

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
                {
                    'type': 'style_meta',
                    'font': n,
                    'location': f'meta {sk}',
                }
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
                        # Add both underscore and space variants
                        available_dirnames.add(item.name)
                        available_dirnames.add(item.name.replace('_', ' '))
                        available_dirnames.add(item.name.replace(' ', '_'))
            except Exception:
                continue
        available = available_dirnames
    else:
        available = available_real

    # Determine missing fonts
    for font_name in font_usage['fonts_found']:
        # Check both exact match and underscore/space variants
        variants = {font_name, font_name.replace(' ', '_'), font_name.replace('_', ' ')}
        if not any(v in available for v in variants):
            font_usage['missing_fonts'].add(font_name)

    return font_usage
