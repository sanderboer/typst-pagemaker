"""Unit tests for snapshot functionality.

Tests cover:
- Asset path collection from IR
- Font file collection from IR
- Path resolution logic
- Snapshot directory creation
- Asset path updating in org files
"""

from pagemaker.cli import _collect_asset_paths, _collect_font_files


class TestCollectAssetPaths:
    """Test _collect_asset_paths function."""

    def test_empty_ir(self, tmp_path):
        """Should return empty list for IR with no assets."""
        ir = {'pages': []}
        org_path = tmp_path / "test.org"
        org_path.touch()

        result = _collect_asset_paths(ir, org_path)
        assert result == []

    def test_figure_assets(self, tmp_path):
        """Should collect figure assets."""
        # Create test asset
        asset_dir = tmp_path / "assets"
        asset_dir.mkdir()
        test_image = asset_dir / "test.jpg"
        test_image.write_text("fake image")

        # Create org file
        org_file = tmp_path / "test.org"
        org_file.touch()

        # Create IR with figure
        ir = {'pages': [{'elements': [{'figure': {'src': 'assets/test.jpg'}}]}]}

        result = _collect_asset_paths(ir, org_file)
        assert len(result) == 1
        assert result[0].name == "test.jpg"

    def test_pdf_and_svg_assets(self, tmp_path):
        """Should collect PDF and SVG assets."""
        # Create test assets
        asset_dir = tmp_path / "assets"
        asset_dir.mkdir()

        test_pdf = asset_dir / "doc.pdf"
        test_pdf.write_text("fake pdf")

        test_svg = asset_dir / "graphic.svg"
        test_svg.write_text("fake svg")

        org_file = tmp_path / "test.org"
        org_file.touch()

        ir = {
            'pages': [
                {
                    'elements': [
                        {'pdf': {'src': 'assets/doc.pdf'}},
                        {'svg': {'src': 'assets/graphic.svg'}},
                    ]
                }
            ]
        }

        result = _collect_asset_paths(ir, org_file)
        assert len(result) == 2
        names = {p.name for p in result}
        assert names == {"doc.pdf", "graphic.svg"}

    def test_absolute_paths(self, tmp_path):
        """Should handle absolute asset paths."""
        asset = tmp_path / "image.jpg"
        asset.write_text("fake image")

        org_file = tmp_path / "test.org"
        org_file.touch()

        ir = {'pages': [{'elements': [{'figure': {'src': str(asset.absolute())}}]}]}

        result = _collect_asset_paths(ir, org_file)
        assert len(result) == 1
        assert result[0].resolve() == asset.resolve()

    def test_parent_directory_resolution(self, tmp_path):
        """Should resolve assets in parent directory."""
        # Create parent-level asset
        parent_asset = tmp_path / "shared.jpg"
        parent_asset.write_text("fake image")

        # Create org file in subdirectory
        subdir = tmp_path / "docs"
        subdir.mkdir()
        org_file = subdir / "test.org"
        org_file.touch()

        ir = {'pages': [{'elements': [{'figure': {'src': './shared.jpg'}}]}]}

        result = _collect_asset_paths(ir, org_file)
        assert len(result) == 1
        assert result[0].name == "shared.jpg"

    def test_missing_assets_ignored(self, tmp_path):
        """Should ignore assets that don't exist."""
        org_file = tmp_path / "test.org"
        org_file.touch()

        ir = {
            'pages': [
                {
                    'elements': [
                        {'figure': {'src': 'missing.jpg'}},
                        {'pdf': {'src': 'nonexistent.pdf'}},
                    ]
                }
            ]
        }

        result = _collect_asset_paths(ir, org_file)
        assert result == []

    def test_duplicate_assets_removed(self, tmp_path):
        """Should remove duplicate asset paths."""
        asset = tmp_path / "test.jpg"
        asset.write_text("fake image")

        org_file = tmp_path / "test.org"
        org_file.touch()

        ir = {
            'pages': [
                {'elements': [{'figure': {'src': 'test.jpg'}}]},
                {'elements': [{'figure': {'src': 'test.jpg'}}]},
            ]
        }

        result = _collect_asset_paths(ir, org_file)
        assert len(result) == 1


class TestCollectFontFiles:
    """Test _collect_font_files function."""

    def test_no_fonts_referenced(self):
        """Should return empty list when no fonts are used."""
        ir = {'meta': {}, 'pages': []}

        result = _collect_font_files(ir)
        assert result == []

    def test_collects_font_family_files(self, tmp_path, monkeypatch):
        """Should collect all files for referenced font families."""
        # Create fake font directory structure
        font_dir = tmp_path / "fonts"
        font_dir.mkdir()

        # Create some Inter font files
        (font_dir / "Inter-Regular.woff2").write_text("font")
        (font_dir / "Inter-Bold.woff2").write_text("font")
        (font_dir / "Inter-Italic.woff2").write_text("font")

        # Create unrelated font
        (font_dir / "Roboto-Regular.woff2").write_text("font")

        # Mock _get_font_paths to return our temp directory
        def mock_font_paths():
            return [str(font_dir)]

        # Patch both the import location and the original
        import pagemaker.cli
        import pagemaker.fonts

        monkeypatch.setattr(pagemaker.fonts, '_get_font_paths', mock_font_paths)

        # Create IR that references Inter
        ir = {'meta': {'STYLE_BODY': 'font: Inter, size: 12pt'}, 'pages': []}

        result = _collect_font_files(ir)

        # Should only get Inter fonts, not Roboto
        assert len(result) == 3
        names = {p.name for p in result}
        assert "Inter-Regular.woff2" in names
        assert "Inter-Bold.woff2" in names
        assert "Roboto-Regular.woff2" not in names


class TestSnapshotIntegration:
    """Integration tests for the snapshot command."""

    def test_basic_snapshot_creation(self, tmp_path):
        """Should create a complete snapshot with assets and fonts."""
        # This would be an integration test that creates a real org file
        # and tests the full snapshot command
        # TODO: Implement after refactoring
        pass

    def test_snapshot_pdf_builds(self, tmp_path):
        """Should build PDF from snapshot directory."""
        # Test that the created snapshot is self-contained
        # TODO: Implement
        pass

    def test_snapshot_with_no_assets(self, tmp_path):
        """Should handle documents with no assets gracefully."""
        # TODO: Implement
        pass


class TestPathResolution:
    """Test path resolution logic."""

    def test_relative_to_org_file(self, tmp_path):
        """Should resolve paths relative to org file location."""
        # TODO: Implement detailed path resolution tests
        pass

    def test_relative_to_cwd(self, tmp_path):
        """Should fall back to CWD for path resolution."""
        # TODO: Implement
        pass


# Edge cases to test:
# - Org file with spaces in filename
# - Assets with special characters
# - Very large snapshots (100s of assets)
# - Circular symlinks in asset directories
# - Read-only files
# - Network paths
# - Unicode filenames
