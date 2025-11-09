"""HTML asset management for portable exports.

This module handles copying all referenced assets (images, SVGs, PDFs, fonts)
into the HTML export directory to make the export self-contained and portable.
"""

from __future__ import annotations

import pathlib
import shutil
from typing import Any, Dict, Set


class HtmlAssetManager:
    """Manages asset copying for portable HTML exports."""

    def __init__(self, html_output_dir: pathlib.Path, project_root: pathlib.Path | None = None):
        """Initialize the HTML asset manager.

        Args:
            html_output_dir: Directory where HTML export will be created (e.g., export/sample/)
            project_root: Optional project root directory (auto-detected if not provided)
        """
        self.html_output_dir = html_output_dir.resolve()
        self.project_root = project_root or self._detect_project_root()
        self.assets_dir = self.html_output_dir / 'assets'
        self.copied_assets: Dict[str, str] = {}  # Maps original path -> relative path in export

    def _detect_project_root(self) -> pathlib.Path:
        """Detect project root by searching upwards for pyproject.toml or .git."""
        cur = pathlib.Path(__file__).resolve()
        for parent in [cur] + list(cur.parents):
            if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
                return parent
        return pathlib.Path.cwd()

    def prepare_assets_dir(self):
        """Create the assets directory if it doesn't exist."""
        self.assets_dir.mkdir(parents=True, exist_ok=True)

    def copy_asset(self, src_path: str | pathlib.Path) -> str | None:
        """Copy an asset file to the export directory.

        Args:
            src_path: Source path to the asset (can be relative or absolute)

        Returns:
            Relative path to the copied asset (from html_output_dir), or None if copy failed
        """
        # Skip protocol URLs
        if isinstance(src_path, str) and ('://' in src_path or src_path.startswith('data:')):
            return None

        # Check cache
        src_str = str(src_path)
        if src_str in self.copied_assets:
            return self.copied_assets[src_str]

        # Store original relative path structure for destination
        original_path = pathlib.Path(src_path)

        # Resolve source path
        src = pathlib.Path(src_path)
        if not src.is_absolute():
            # Try multiple resolution strategies
            candidates = [
                pathlib.Path.cwd() / src,
                self.project_root / src,
                self.html_output_dir / src,
            ]

            # Examples fallback
            if str(src).startswith("assets/"):
                candidates.append(self.project_root / "examples" / src)

            resolved_src = None
            for candidate in candidates:
                if candidate.exists():
                    resolved_src = candidate
                    break

            if resolved_src is None:
                return None
            src = resolved_src

        if not src.exists() or not src.is_file():
            return None

        # Determine destination path - preserve original IR path structure
        # The destination is html_output_dir / original_path
        # For example: if original_path is "assets/foo.svg", dest is html_output_dir/assets/foo.svg
        dest = self.html_output_dir / original_path

        # Ensure destination directory exists
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Copy the file
        try:
            shutil.copy2(src, dest)
            # Calculate relative path from html_output_dir
            rel_path = dest.relative_to(self.html_output_dir)
            self.copied_assets[src_str] = str(rel_path)
            return str(rel_path)
        except Exception as e:
            print(f"Warning: Failed to copy asset {src}: {e}")
            return None

    def collect_ir_assets(self, ir: Dict[str, Any]) -> Set[str]:
        """Collect all asset paths from IR.

        Args:
            ir: Intermediate representation from parser

        Returns:
            Set of asset paths found in the IR
        """
        assets = set()

        for page in ir.get('pages', []):
            for element in page.get('elements', []):
                # Check for image/media assets
                for media_type in ('figure', 'pdf', 'svg'):
                    media_obj = element.get(media_type)
                    if media_obj and media_obj.get('src'):
                        assets.add(media_obj['src'])

        return assets

    def copy_all_assets(self, ir: Dict[str, Any]) -> Dict[str, str]:
        """Copy all assets referenced in IR to the export directory.

        Args:
            ir: Intermediate representation from parser

        Returns:
            Dictionary mapping original paths to new relative paths
        """
        self.prepare_assets_dir()
        assets = self.collect_ir_assets(ir)

        copied_map = {}
        for asset_path in assets:
            new_path = self.copy_asset(asset_path)
            if new_path:
                copied_map[asset_path] = new_path

        return copied_map

    def update_ir_asset_paths(self, ir: Dict[str, Any]) -> Dict[str, Any]:
        """Update IR asset paths to point to copied assets.

        This modifies the IR in-place to use the new asset paths.

        Args:
            ir: Intermediate representation from parser

        Returns:
            Modified IR with updated asset paths
        """
        for page in ir.get('pages', []):
            for element in page.get('elements', []):
                for media_type in ('figure', 'pdf', 'svg'):
                    media_obj = element.get(media_type)
                    if media_obj and media_obj.get('src'):
                        orig_path = media_obj['src']
                        if orig_path in self.copied_assets:
                            media_obj['src'] = self.copied_assets[orig_path]

        return ir


def make_html_export_portable(
    ir: Dict[str, Any], html_output_dir: pathlib.Path, project_root: pathlib.Path | None = None
) -> Dict[str, Any]:
    """Make HTML export portable by copying all assets and updating paths.

    This is a convenience function that creates an HtmlAssetManager, copies all
    assets, and updates the IR paths in one step.

    Args:
        ir: Intermediate representation from parser
        html_output_dir: Directory where HTML export will be created
        project_root: Optional project root directory

    Returns:
        Modified IR with updated asset paths
    """
    manager = HtmlAssetManager(html_output_dir, project_root)
    manager.copy_all_assets(ir)
    return manager.update_ir_asset_paths(ir)


__all__ = ['HtmlAssetManager', 'make_html_export_portable']
