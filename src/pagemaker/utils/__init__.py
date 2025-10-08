"""Shared utilities for pagemaker.

This package contains common functionality used across multiple modules:
- alignment: Position and alignment calculations
- file_ops: File operations and path handling
- font_discovery: Font scanning and caching utilities
- typst_helpers: Typst code generation helpers
"""

from .alignment import (
    AlignmentWrapper,
    get_alignment_wrapper,
    normalize_alignment,
    normalize_valignment,
)
from .file_ops import (
    ensure_export_dir,
    resolve_asset_path,
    safe_path_join,
)
from .font_discovery import (
    FontCache,
    scan_font_directories,
    get_google_fonts_api_data,
    download_font_file,
    install_google_font,
    search_google_fonts,
    analyze_font_usage,
    validate_fonts_in_build,
    attempt_auto_download_missing_fonts,
    get_font_discovery_cache_path,
    is_cache_valid,
    save_font_discovery_cache,
    get_cached_font_discovery,
)
from .typst_helpers import (
    escape_typst_text,
    escape_org_text,
    escape_typst_chars,
    process_org_links,
    process_org_emphasis,
    restore_protected_links,
    build_text_args,
    format_dimensions,
)

__all__ = [
    # Alignment utilities
    'AlignmentWrapper',
    'get_alignment_wrapper',
    'normalize_alignment',
    'normalize_valignment',
    # File operations
    'ensure_export_dir',
    'resolve_asset_path',
    'safe_path_join',
    # Font discovery
    'FontCache',
    'scan_font_directories',
    'get_google_fonts_api_data',
    'download_font_file',
    'install_google_font',
    'search_google_fonts',
    'analyze_font_usage',
    'validate_fonts_in_build',
    'attempt_auto_download_missing_fonts',
    'get_font_discovery_cache_path',
    'is_cache_valid',
    'save_font_discovery_cache',
    'get_cached_font_discovery',
    # Typst helpers
    'escape_typst_text',
    'escape_org_text',
    'escape_typst_chars',
    'process_org_links',
    'process_org_emphasis',
    'restore_protected_links',
    'build_text_args',
    'format_dimensions',
]
