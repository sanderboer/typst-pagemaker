"""
CLI integration test for story mode.
"""

import subprocess
import sys


def test_story_cli_command(tmp_path):
    """Test the story CLI command end-to-end."""
    # Create a test org file
    org_content = """#+TITLE: CLI Test
#+GRID: 12x12

* Scene One
** Block
:PROPERTIES:
:TYPE: header
:END:

CLI Test Scene
"""

    org_file = tmp_path / "test.org"
    org_file.write_text(org_content)

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Run pagemaker story command
    result = subprocess.run(
        [
            sys.executable,
            '-m',
            'pagemaker.cli',
            'story',
            str(org_file),
            '--export-dir',
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )

    # Check command succeeded
    assert result.returncode == 0, f"Command failed: {result.stderr}"

    # Check output file exists
    output_file = output_dir / "index.html"
    assert output_file.exists(), f"Output file not created at {output_file}"

    # Verify content
    html_content = output_file.read_text()
    assert '<!DOCTYPE html>' in html_content
    assert 'CLI Test Scene' in html_content
    assert '<section class="scene"' in html_content

    # Check CLI output
    assert 'Story HTML written to' in result.stdout
    assert 'Scenes: 1' in result.stdout
