"""
Integration tests for HTML export via CLI.

Tests the --html flag functionality that generates HTML output alongside PDF.
"""

import pathlib
import shutil
import subprocess

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent


def run_cli(*args):
    """Helper to run pagemaker CLI and return result."""
    cmd = ["python", "-m", "pagemaker.cli"] + list(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    return result


def cleanup_dir(path):
    """Helper to clean up test directories."""
    if path.exists():
        shutil.rmtree(path)


def test_html_flag_creates_html_output():
    """Test that --html flag creates HTML output directory and files."""
    org_file = PROJECT_ROOT / "examples" / "sample.org"
    export_dir = PROJECT_ROOT / "temp_html_test_1"

    try:
        result = run_cli("pdf", str(org_file), "--html", "--export-dir", str(export_dir))

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "HTML written to" in result.stdout

        # Check that HTML file was created (uses source file basename)
        html_file = export_dir / "sample" / "index.html"
        assert html_file.exists(), f"HTML file not found at {html_file}"

        # Check basic HTML structure
        html_content = html_file.read_text()
        assert "<!DOCTYPE html>" in html_content
        assert "<html>" in html_content
        assert "<body>" in html_content
        assert "</html>" in html_content
    finally:
        cleanup_dir(export_dir)


def test_html_contains_expected_content():
    """Test that generated HTML contains expected content from org file."""
    org_file = PROJECT_ROOT / "examples" / "sample.org"
    export_dir = PROJECT_ROOT / "temp_html_test_2"

    try:
        result = run_cli("pdf", str(org_file), "--html", "--export-dir", str(export_dir))

        assert result.returncode == 0

        html_file = export_dir / "sample" / "index.html"
        html_content = html_file.read_text()

        # Check for metadata
        assert "<title>Demo Deck</title>" in html_content
        assert 'content="Your Name"' in html_content

        # Check for page title (becomes H2)
        assert "<h2>Introduction</h2>" in html_content

        # Check for header element (becomes H3)
        assert "<h3>Unified Architecture Platform</h3>" in html_content

        # Check for body text
        assert "Assumenda temporibus sed necessitatibus" in html_content

        # Check for figure (SVG embed)
        assert "<figure>" in html_content
        assert "<figcaption>" in html_content
        assert "Embedded Spec PDF (working)" in html_content
    finally:
        cleanup_dir(export_dir)


def test_html_headers_do_not_contain_list_markup():
    """Test that headers extract plain text from lists, not list markup."""
    org_file = PROJECT_ROOT / "examples" / "sample.org"
    export_dir = PROJECT_ROOT / "temp_html_test_3"

    try:
        result = run_cli("pdf", str(org_file), "--html", "--export-dir", str(export_dir))

        assert result.returncode == 0

        html_file = export_dir / "sample" / "index.html"
        html_content = html_file.read_text()

        # The subheader should NOT contain list markup like "+ " or "- "
        # It should extract just the text
        assert "<h4>Observable. Secure.</h4>" in html_content
        # Should NOT have list markup in heading
        assert "<h4>+ Observable" not in html_content
        assert "<h4>- Observable" not in html_content
    finally:
        cleanup_dir(export_dir)


def test_pdf_and_html_combined_mode():
    """Test that --html generates both PDF and HTML outputs."""
    org_file = PROJECT_ROOT / "examples" / "sample.org"
    export_dir = PROJECT_ROOT / "temp_html_test_4"

    try:
        result = run_cli("pdf", str(org_file), "--html", "--export-dir", str(export_dir))

        assert result.returncode == 0

        # Check both outputs exist
        pdf_file = export_dir / "sample.pdf"
        html_file = export_dir / "sample" / "index.html"

        assert pdf_file.exists(), f"PDF not found at {pdf_file}"
        assert html_file.exists(), f"HTML not found at {html_file}"

        # Verify output message mentions both
        assert "PDF build success=True" in result.stdout
        assert "HTML written to" in result.stdout
    finally:
        cleanup_dir(export_dir)


def test_html_without_no_clean_removes_typst_file():
    """Test that Typst file is cleaned up after HTML compilation by default."""
    org_file = PROJECT_ROOT / "examples" / "sample.org"
    export_dir = PROJECT_ROOT / "temp_html_test_5"

    try:
        result = run_cli("pdf", str(org_file), "--html", "--export-dir", str(export_dir))

        assert result.returncode == 0

        # Check that .typ file was cleaned up
        typ_file = export_dir / "deck.typ"
        assert not typ_file.exists(), f"Typst file should be cleaned up but found at {typ_file}"
    finally:
        cleanup_dir(export_dir)


def test_html_with_no_clean_preserves_typst_file():
    """Test that --no-clean preserves Typst file after HTML compilation."""
    org_file = PROJECT_ROOT / "examples" / "sample.org"
    export_dir = PROJECT_ROOT / "temp_html_test_6"

    try:
        result = run_cli(
            "pdf", str(org_file), "--html", "--export-dir", str(export_dir), "--no-clean"
        )

        assert result.returncode == 0

        # Check that .typ file is preserved
        typ_file = export_dir / "deck.typ"
        assert typ_file.exists(), "Typst file should be preserved with --no-clean"

        # Verify it contains HTML-compatible markup
        typ_content = typ_file.read_text()
        assert "// Auto-generated Typst file for HTML export" in typ_content
        assert "#set document(" in typ_content
        # Should NOT have page setup for HTML
        assert "#set page(" not in typ_content
    finally:
        cleanup_dir(export_dir)


def test_html_export_handles_missing_text_gracefully():
    """Test that HTML export handles elements with no text content."""
    org_file = PROJECT_ROOT / "examples" / "rectangle_demo.org"
    export_dir = PROJECT_ROOT / "temp_html_test_7"

    try:
        result = run_cli("pdf", str(org_file), "--html", "--export-dir", str(export_dir))

        # Should succeed even with minimal text content
        assert result.returncode == 0

        html_file = export_dir / "rectangle_demo" / "index.html"
        assert html_file.exists()

        html_content = html_file.read_text()
        # Should have valid HTML structure
        assert "<!DOCTYPE html>" in html_content
        assert "<body>" in html_content
    finally:
        cleanup_dir(export_dir)


def test_html_svg_embedding_with_caption():
    """Test that SVG elements are embedded with captions in HTML."""
    org_file = PROJECT_ROOT / "examples" / "svg_demo.org"
    export_dir = PROJECT_ROOT / "temp_html_test_svg"

    try:
        result = run_cli("pdf", str(org_file), "--html", "--export-dir", str(export_dir))

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        html_file = export_dir / "svg_demo" / "index.html"
        assert html_file.exists()

        html_content = html_file.read_text()

        # Check that SVG is embedded as an image
        assert "<figure>" in html_content
        assert "<img" in html_content

        # SVGs should be embedded as base64 data URIs or external references
        # Typst converts them to images in HTML
        assert 'src="data:' in html_content or 'src="' in html_content

    finally:
        cleanup_dir(export_dir)


def test_html_pdf_rendering_as_image():
    """Test that PDF elements are rendered as images in HTML."""
    org_file = PROJECT_ROOT / "examples" / "media_consolidation_demo.org"
    export_dir = PROJECT_ROOT / "temp_html_test_pdf"

    try:
        result = run_cli("pdf", str(org_file), "--html", "--export-dir", str(export_dir))

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        html_file = export_dir / "media_consolidation_demo" / "index.html"
        assert html_file.exists()

        html_content = html_file.read_text()

        # Check that PDF is rendered as a figure
        assert "<figure>" in html_content
        assert "<img" in html_content

        # Check that PDF caption is present
        assert "PDFs can now have captions just like figures" in html_content

        # Should NOT have placeholder comment
        assert "PDF embed not supported" not in html_content

    finally:
        cleanup_dir(export_dir)


def test_html_figure_rendering_with_caption():
    """Test that figure elements are rendered with captions in HTML."""
    org_file = PROJECT_ROOT / "examples" / "media_consolidation_demo.org"
    export_dir = PROJECT_ROOT / "temp_html_test_figure"

    try:
        result = run_cli("pdf", str(org_file), "--html", "--export-dir", str(export_dir))

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        html_file = export_dir / "media_consolidation_demo" / "index.html"
        assert html_file.exists()

        html_content = html_file.read_text()

        # Check that figure is rendered
        assert "<figure>" in html_content
        assert "<figcaption>" in html_content

        # Check that caption from :CAPTION: property is present
        assert "You can now use :PAGE: on figure elements" in html_content

    finally:
        cleanup_dir(export_dir)


def test_html_media_without_caption():
    """Test that media elements render correctly without captions."""
    # Create a minimal test org file for this specific test
    org_file = PROJECT_ROOT / "tests" / "fixtures" / "test_html_media_no_caption.org"
    export_dir = PROJECT_ROOT / "temp_html_test_no_caption"

    # Create test file
    org_content = """#+TITLE: Media No Caption Test
#+PAGESIZE: A4

* Test Page
:PROPERTIES:
:ID: test
:END:

** Figure Without Caption
:PROPERTIES:
:TYPE: figure
:SRC: examples/assets/diagram.png
:AREA: 1,1,6,4
:END:
"""

    try:
        org_file.parent.mkdir(parents=True, exist_ok=True)
        org_file.write_text(org_content)

        result = run_cli("pdf", str(org_file), "--html", "--export-dir", str(export_dir))

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        html_file = export_dir / "test_html_media_no_caption" / "index.html"
        assert html_file.exists()

        html_content = html_file.read_text()

        # Should have figure element
        assert "<figure>" in html_content or "<img" in html_content

        # Should not crash without caption
        assert "<!DOCTYPE html>" in html_content

    finally:
        cleanup_dir(export_dir)
        if org_file.exists():
            org_file.unlink()


def test_html_multiple_media_elements():
    """Test that multiple media elements render correctly in HTML."""
    org_file = PROJECT_ROOT / "examples" / "media_consolidation_demo.org"
    export_dir = PROJECT_ROOT / "temp_html_test_multi_media"

    try:
        result = run_cli("pdf", str(org_file), "--html", "--export-dir", str(export_dir))

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        html_file = export_dir / "media_consolidation_demo" / "index.html"
        assert html_file.exists()

        html_content = html_file.read_text()

        # Count figure elements - should have at least 2 (PDF + Figure types)
        figure_count = html_content.count("<figure>")
        assert figure_count >= 2, f"Expected at least 2 figures, found {figure_count}"

        # Check both captions are present
        assert "You can now use :PAGE: on figure elements" in html_content
        assert "PDFs can now have captions just like figures" in html_content

    finally:
        cleanup_dir(export_dir)
