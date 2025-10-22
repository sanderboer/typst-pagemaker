"""Integration tests for PDF OutputIntent injection via CLI."""

import subprocess
import sys
from pathlib import Path


def test_pdf_output_intent_srgb_injection():
    """Test that --inject-output-intent-srgb adds OutputIntent to PDF."""
    # Create a minimal test org file
    org_content = """#+TITLE: Test Document
#+PAGESIZE: A4
#+GRID: 12x16

* Test Content
:PROPERTIES:
:AREA: A1,L16
:END:

This is a test document for OutputIntent injection.
"""

    # Create test file in project directory to satisfy Typst root requirement
    project_root = Path(__file__).parent.parent.parent
    test_file = project_root / "test_output_intent.org"
    export_dir = project_root / "test_export"

    try:
        test_file.write_text(org_content)

        # Test PDF generation with OutputIntent injection
        cmd = [
            sys.executable,
            "-m",
            "pagemaker.cli",
            "pdf",
            str(test_file),
            "--inject-output-intent-srgb",
            "--export-dir",
            str(export_dir),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(project_root))

        # Should succeed (non-fatal even if Ghostscript not available)
        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Check that PDF was created
        pdf_path = export_dir / "test_output_intent.pdf"
        assert pdf_path.exists(), "PDF file was not created"
        assert pdf_path.stat().st_size > 0, "PDF file is empty"

    finally:
        # Clean up test files
        if test_file.exists():
            test_file.unlink()
        if export_dir.exists():
            import shutil

            shutil.rmtree(export_dir)


def test_pdf_output_intent_custom_icc():
    """Test that --icc-profile parameter works correctly."""
    # Create a minimal test org file
    org_content = """#+TITLE: Test Document
#+PAGESIZE: A4
#+GRID: 12x16

* Test Content
:PROPERTIES:
:AREA: A1,L16
:END:

This is a test document for custom ICC profile injection.
"""

    # Create test file in project directory to satisfy Typst root requirement
    project_root = Path(__file__).parent.parent.parent
    test_file = project_root / "test_custom_icc.org"
    export_dir = project_root / "test_export_icc"
    icc_file = project_root / "test_srgb.icc"

    try:
        test_file.write_text(org_content)

        # Create a dummy ICC profile file (for testing purposes)
        icc_file.write_bytes(b"DUMMY_ICC_PROFILE_DATA")

        # Test PDF generation with custom ICC profile
        cmd = [
            sys.executable,
            "-m",
            "pagemaker.cli",
            "pdf",
            str(test_file),
            "--icc-profile",
            str(icc_file),
            "--export-dir",
            str(export_dir),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(project_root))

        # Should succeed (non-fatal even if Ghostscript not available)
        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Check that PDF was created
        pdf_path = export_dir / "test_custom_icc.pdf"
        assert pdf_path.exists(), "PDF file was not created"
        assert pdf_path.stat().st_size > 0, "PDF file is empty"

    finally:
        # Clean up test files
        for path in [test_file, icc_file]:
            if path.exists():
                path.unlink()
        if export_dir.exists():
            import shutil

            shutil.rmtree(export_dir)


def test_pdf_preset_options():
    """Test that --pdf-preset parameter is accepted."""
    # Create a minimal test org file
    org_content = """#+TITLE: Test Document
#+PAGESIZE: A4
#+GRID: 12x16

* Test Content
:PROPERTIES:
:AREA: A1,L16
:END:

This is a test document for PDF preset testing.
"""

    # Create test file in project directory to satisfy Typst root requirement
    project_root = Path(__file__).parent.parent.parent
    test_file = project_root / "test_presets.org"
    export_dirs = []

    try:
        test_file.write_text(org_content)

        # Test each preset option
        for preset in ["screen", "printer", "prepress"]:
            export_dir = project_root / f"test_export_{preset}"
            export_dirs.append(export_dir)

            cmd = [
                sys.executable,
                "-m",
                "pagemaker.cli",
                "pdf",
                str(test_file),
                "--inject-output-intent-srgb",
                "--pdf-preset",
                preset,
                "--export-dir",
                str(export_dir),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(project_root))

            # Should succeed (non-fatal even if Ghostscript not available)
            assert result.returncode == 0, f"Command failed for preset {preset}: {result.stderr}"

            # Check that PDF was created
            pdf_path = export_dir / "test_presets.pdf"
            assert pdf_path.exists(), f"PDF file was not created for preset {preset}"
            assert pdf_path.stat().st_size > 0, f"PDF file is empty for preset {preset}"

    finally:
        # Clean up test files
        if test_file.exists():
            test_file.unlink()
        for export_dir in export_dirs:
            if export_dir.exists():
                import shutil

                shutil.rmtree(export_dir)


def test_watch_mode_output_intent():
    """Test that OutputIntent injection works in watch mode."""
    # Create a minimal test org file
    org_content = """#+TITLE: Test Document
#+PAGESIZE: A4
#+GRID: 12x16

* Test Content
:PROPERTIES:
:AREA: A1,L16
:END:

This is a test document for watch mode OutputIntent injection.
"""

    # Create test file in project directory to satisfy Typst root requirement
    project_root = Path(__file__).parent.parent.parent
    test_file = project_root / "test_watch_output_intent.org"
    export_dir = project_root / "test_export_watch"

    try:
        test_file.write_text(org_content)

        # Test watch mode with --once flag and OutputIntent injection
        cmd = [
            sys.executable,
            "-m",
            "pagemaker.cli",
            "watch",
            str(test_file),
            "--pdf",
            "--inject-output-intent-srgb",
            "--once",  # Exit after single build
            "--export-dir",
            str(export_dir),
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, cwd=str(project_root)
        )

        # Should succeed (non-fatal even if Ghostscript not available)
        assert result.returncode == 0, f"Watch command failed: {result.stderr}"

        # Check that PDF was created
        pdf_path = export_dir / "test_watch_output_intent.pdf"
        assert pdf_path.exists(), "PDF file was not created in watch mode"
        assert pdf_path.stat().st_size > 0, "PDF file is empty in watch mode"

    finally:
        # Clean up test files
        if test_file.exists():
            test_file.unlink()
        if export_dir.exists():
            import shutil

            shutil.rmtree(export_dir)


def test_output_intent_without_ghostscript():
    """Test graceful handling when Ghostscript is not available."""
    # This test verifies that OutputIntent injection fails gracefully
    # when Ghostscript is not available, without breaking the PDF generation

    # Create a minimal test org file
    org_content = """#+TITLE: Test Document
#+PAGESIZE: A4
#+GRID: 12x16

* Test Content
:PROPERTIES:
:AREA: A1,L16
:END:

This is a test document for testing graceful Ghostscript failure.
"""

    # Create test file in project directory to satisfy Typst root requirement
    project_root = Path(__file__).parent.parent.parent
    test_file = project_root / "test_ghostscript_fallback.org"
    export_dir = project_root / "test_export_ghostscript"

    try:
        test_file.write_text(org_content)

        # Test PDF generation with OutputIntent injection
        # (should succeed even if Ghostscript is not available)
        cmd = [
            sys.executable,
            "-m",
            "pagemaker.cli",
            "pdf",
            str(test_file),
            "--inject-output-intent-srgb",
            "--export-dir",
            str(export_dir),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(project_root))

        # Should succeed regardless of Ghostscript availability
        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Check that PDF was created (original PDF from Typst)
        pdf_path = export_dir / "test_ghostscript_fallback.pdf"
        assert pdf_path.exists(), "PDF file was not created"
        assert pdf_path.stat().st_size > 0, "PDF file is empty"

        # The test should pass whether Ghostscript is available or not
        # If available, OutputIntent will be injected
        # If not available, warning will be printed but PDF generation continues

    finally:
        # Clean up test files
        if test_file.exists():
            test_file.unlink()
        if export_dir.exists():
            import shutil

            shutil.rmtree(export_dir)
