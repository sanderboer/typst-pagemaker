"""File operations and path handling utilities."""

import pathlib
from typing import Union


def ensure_export_dir(export_dir: Union[str, pathlib.Path]) -> pathlib.Path:
    """Ensure export directory exists and return Path object."""
    export_path = pathlib.Path(export_dir)
    export_path.mkdir(parents=True, exist_ok=True)
    return export_path


def resolve_asset_path(
    asset_path: Union[str, pathlib.Path], base_dir: Union[str, pathlib.Path]
) -> pathlib.Path:
    """Resolve asset path relative to base directory."""
    asset = pathlib.Path(asset_path)
    base = pathlib.Path(base_dir)

    if asset.is_absolute():
        return asset

    # Try relative to base directory first
    resolved = base / asset
    if resolved.exists():
        return resolved.resolve()

    # Try relative to current working directory
    cwd_resolved = pathlib.Path.cwd() / asset
    if cwd_resolved.exists():
        return cwd_resolved.resolve()

    # Return the base-relative path even if it doesn't exist
    return resolved


def safe_path_join(*parts: Union[str, pathlib.Path]) -> pathlib.Path:
    """Safely join path parts, handling both strings and Path objects."""
    if not parts:
        return pathlib.Path()

    result = pathlib.Path(parts[0])
    for part in parts[1:]:
        result = result / part

    return result


def make_relative_to(path: Union[str, pathlib.Path], base: Union[str, pathlib.Path]) -> str:
    """Make path relative to base directory, return as string."""
    path_obj = pathlib.Path(path)
    base_obj = pathlib.Path(base)

    try:
        return str(path_obj.relative_to(base_obj))
    except ValueError:
        # If paths don't share a common base, return absolute path
        return str(path_obj.resolve())


def get_file_size(path: Union[str, pathlib.Path]) -> int:
    """Get file size in bytes, return 0 if file doesn't exist."""
    try:
        return pathlib.Path(path).stat().st_size
    except (OSError, FileNotFoundError):
        return 0


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
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
