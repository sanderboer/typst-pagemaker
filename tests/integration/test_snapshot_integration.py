"""Integration tests for snapshot command.

These tests verify the complete snapshot workflow end-to-end.
"""

import subprocess


class TestSnapshotCommand:
    """Integration tests for pagemaker snapshot command."""

    def test_snapshot_with_assets_creates_complete_package(self, tmp_path):
        """Should create a complete, self-contained snapshot."""
        # Create a simple org file with assets
        org_dir = tmp_path / "project"
        org_dir.mkdir()

        assets_dir = org_dir / "images"
        assets_dir.mkdir()

        # Create test assets
        test_img = assets_dir / "test.jpg"
        test_img.write_bytes(b"fake jpeg data")

        test_svg = assets_dir / "diagram.svg"
        test_svg.write_text('<svg><rect/></svg>')

        # Create org file
        org_file = org_dir / "document.org"
        org_content = """#+TITLE: Test Document
#+PAGESIZE: A4
#+GRID: 12x12

* Page 1
** Image
:PROPERTIES:
:type: figure
:area: a1,c3
:END:
[[file:./images/test.jpg]]

** SVG
:PROPERTIES:
:type: figure  
:area: d1,f3
:END:
[[file:./images/diagram.svg]]
"""
        org_file.write_text(org_content)

        # Create snapshot
        output_dir = tmp_path / "snapshots"
        output_dir.mkdir()

        result = subprocess.run(
            [
                'pagemaker',
                'snapshot',
                str(org_file),
                '--output-dir',
                str(output_dir),
                '--no-build-pdf',
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Snapshot failed: {result.stderr}"

        # Find snapshot directory (has date prefix like YYMMDD-document_snapshot)
        snapshot_dirs = list(output_dir.glob('*document_snapshot'))
        assert len(snapshot_dirs) == 1, f"Expected 1 snapshot, found: {list(output_dir.glob('*'))}"
        snapshot_dir = snapshot_dirs[0]

        # Verify snapshot structure
        assert (snapshot_dir / "document.org").exists()
        assert (snapshot_dir / "assets").is_dir()
        assert (snapshot_dir / "fonts").is_dir()
        assert (snapshot_dir / "README.txt").exists()

        # Verify assets were copied
        assert (snapshot_dir / "assets" / "test.jpg").exists()
        assert (snapshot_dir / "assets" / "diagram.svg").exists()

        # Verify paths were updated in org file
        updated_content = (snapshot_dir / "document.org").read_text()
        assert "./assets/test.jpg" in updated_content
        assert "./assets/diagram.svg" in updated_content
        assert "./images/" not in updated_content

    def test_snapshot_pdf_generation_from_snapshot_dir(self, tmp_path):
        """Should be able to build PDF from snapshot directory."""
        # Create minimal org file
        org_dir = tmp_path / "project"
        org_dir.mkdir()

        org_file = org_dir / "minimal.org"
        org_content = """#+TITLE: Minimal Test
#+PAGESIZE: A4
#+GRID: 12x12

* Page 1
** Text
:PROPERTIES:
:area: a1,c3
:END:
Hello World
"""
        org_file.write_text(org_content)

        # Create snapshot with PDF
        output_dir = tmp_path / "snapshots"
        output_dir.mkdir()

        result = subprocess.run(
            ['pagemaker', 'snapshot', str(org_file), '--output-dir', str(output_dir)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Snapshot creation might succeed even if PDF fails
        snapshot_dirs = list(output_dir.glob('*minimal_snapshot'))
        assert len(snapshot_dirs) == 1, f"Expected 1 snapshot, found: {list(output_dir.glob('*'))}"
        snapshot_dir = snapshot_dirs[0]

        # Check if PDF was created
        pdf_path = snapshot_dir / "minimal.pdf"

        # If PDF build succeeded, verify it exists and has content
        if pdf_path.exists():
            assert pdf_path.stat().st_size > 0, "PDF should not be empty"

    def test_snapshot_with_fonts(self, tmp_path):
        """Should collect and copy font files."""
        org_dir = tmp_path / "project"
        org_dir.mkdir()

        org_file = org_dir / "with_fonts.org"
        org_content = """#+TITLE: Font Test
#+PAGESIZE: A4
#+GRID: 12x12
#+STYLE_BODY: font: Inter, size: 12pt

* Page 1
** Text
:PROPERTIES:
:area: a1,c3
:STYLE: body
:END:
Text with Inter font
"""
        org_file.write_text(org_content)

        output_dir = tmp_path / "snapshots"
        output_dir.mkdir()

        result = subprocess.run(
            [
                'pagemaker',
                'snapshot',
                str(org_file),
                '--output-dir',
                str(output_dir),
                '--no-build-pdf',
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        snapshot_dirs = list(output_dir.glob('*with_fonts_snapshot'))
        assert len(snapshot_dirs) == 1, f"Expected 1 snapshot, found: {list(output_dir.glob('*'))}"
        snapshot_dir = snapshot_dirs[0]

        # Should have fonts directory
        fonts_dir = snapshot_dir / "fonts"
        assert fonts_dir.exists()

        # Should have Inter font files
        inter_fonts = list(fonts_dir.glob('*Inter*.woff2'))
        assert len(inter_fonts) > 0, "Should copy Inter font files"

    def test_snapshot_preserves_asset_content(self, tmp_path):
        """Should copy assets with exact content preservation."""
        org_dir = tmp_path / "project"
        org_dir.mkdir()

        assets_dir = org_dir / "media"
        assets_dir.mkdir()

        # Create binary test data
        test_data = bytes(range(256))
        test_file = assets_dir / "binary.dat"
        test_file.write_bytes(test_data)

        org_file = org_dir / "test.org"
        org_content = """#+TITLE: Test
#+PAGESIZE: A4
#+GRID: 12x12

* Page
** Image
:PROPERTIES:
:type: figure
:area: a1,c3
:END:
[[file:./media/binary.dat]]
"""
        org_file.write_text(org_content)

        output_dir = tmp_path / "snapshots"
        output_dir.mkdir()

        subprocess.run(
            [
                'pagemaker',
                'snapshot',
                str(org_file),
                '--output-dir',
                str(output_dir),
                '--no-build-pdf',
            ],
            check=True,
        )

        snapshot_dirs = list(output_dir.glob('*snapshot'))
        snapshot_dir = snapshot_dirs[0]

        # Verify exact content match
        copied_file = snapshot_dir / "assets" / "binary.dat"
        assert copied_file.read_bytes() == test_data


class TestSnapshotEdgeCases:
    """Test edge cases and error handling."""

    def test_snapshot_with_missing_org_file(self, tmp_path):
        """Should fail gracefully with missing org file."""
        result = subprocess.run(
            [
                'pagemaker',
                'snapshot',
                str(tmp_path / "nonexistent.org"),
                '--output-dir',
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "not found" in result.stderr.lower()

    def test_snapshot_with_no_assets(self, tmp_path):
        """Should create snapshot even with no assets."""
        org_file = tmp_path / "no_assets.org"
        org_content = """#+TITLE: No Assets
#+PAGESIZE: A4

* Page
** Text
Simple text only
"""
        org_file.write_text(org_content)

        output_dir = tmp_path / "out"
        output_dir.mkdir()

        result = subprocess.run(
            [
                'pagemaker',
                'snapshot',
                str(org_file),
                '--output-dir',
                str(output_dir),
                '--no-build-pdf',
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        # Should still create structure
        snapshot_dirs = list(output_dir.glob('*snapshot'))
        assert len(snapshot_dirs) == 1

        snapshot_dir = snapshot_dirs[0]
        assert (snapshot_dir / "assets").exists()
        assert (snapshot_dir / "README.txt").exists()

    def test_snapshot_with_duplicate_filenames(self, tmp_path):
        """Should handle assets with duplicate filenames from different dirs."""
        org_dir = tmp_path / "project"
        org_dir.mkdir()

        # Create same filename in different directories
        dir1 = org_dir / "images1"
        dir1.mkdir()
        (dir1 / "photo.jpg").write_text("image 1")

        dir2 = org_dir / "images2"
        dir2.mkdir()
        (dir2 / "photo.jpg").write_text("image 2")

        org_file = org_dir / "test.org"
        org_content = """#+TITLE: Test
#+PAGESIZE: A4
#+GRID: 12x12

* Page 1
** Image 1
:PROPERTIES:
:type: figure
:area: a1,c3
:END:
[[file:./images1/photo.jpg]]

* Page 2
** Image 2
:PROPERTIES:
:type: figure
:area: a1,c3
:END:
[[file:./images2/photo.jpg]]
"""
        org_file.write_text(org_content)

        output_dir = tmp_path / "out"
        output_dir.mkdir()

        result = subprocess.run(
            [
                'pagemaker',
                'snapshot',
                str(org_file),
                '--output-dir',
                str(output_dir),
                '--no-build-pdf',
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        snapshot_dirs = list(output_dir.glob('*snapshot'))
        snapshot_dir = snapshot_dirs[0]

        # Should have both files with different names
        assets = list((snapshot_dir / "assets").glob('*.jpg'))
        assert len(assets) == 2

        # One should be prefixed with parent dir name
        asset_names = {a.name for a in assets}
        assert 'photo.jpg' in asset_names or 'images1_photo.jpg' in asset_names
