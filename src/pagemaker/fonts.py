import pathlib
from typing import Dict, List, Set


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
    """Get font paths in order of preference: user-specified -> bundled fallback"""
    font_paths: List[str] = []

    # 1. Check for project-local assets/fonts (for development/user customization)
    local_fonts = pathlib.Path('assets/fonts')
    if local_fonts.exists():
        font_paths.append(str(local_fonts))
        # Add static subdirectory if it exists
        static_path = local_fonts / 'static'
        if static_path.exists():
            font_paths.append(str(static_path))

    # 1b. Check examples/assets/fonts as fallback (example fonts)
    examples_fonts = pathlib.Path('examples/assets/fonts')
    if examples_fonts.exists():
        font_paths.append(str(examples_fonts))
        # Add static subdirectory if it exists
        static_path = examples_fonts / 'static'
        if static_path.exists():
            font_paths.append(str(static_path))

    # 2. Add bundled fonts as fallback
    try:
        # Get the path to bundled fonts in the installed package
        import pagemaker

        package_path = pathlib.Path(pagemaker.__file__).parent
        package_fonts_path = package_path / 'fonts'
        if package_fonts_path.exists():
            font_paths.append(str(package_fonts_path))
            # Also add any font family subdirectories
            for font_family_dir in package_fonts_path.iterdir():
                if font_family_dir.is_dir() and not font_family_dir.name.startswith('.'):
                    font_paths.append(str(font_family_dir))
    except Exception:
        # Fallback: fonts not bundled or package not found
        pass

    # Filter out None values and return unique paths
    return list(dict.fromkeys(fp for fp in font_paths if fp is not None))


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
