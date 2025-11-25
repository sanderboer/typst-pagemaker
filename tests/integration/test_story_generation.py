"""
Integration tests for story mode HTML generation.
"""

from pagemaker import parse_org
from pagemaker.generation.story_generator import generate_story_html


class TestStoryGeneration:
    """Test story mode HTML generation end-to-end."""

    def test_basic_story_generation(self, tmp_path):
        """Test basic story HTML generation with auto-placement."""
        # Create a simple org file
        org_content = """#+TITLE: Test Story
#+GRID: 12x12

* Scene One
** Block One
:PROPERTIES:
:TYPE: header
:END:

Hello World

** Block Two
:PROPERTIES:
:TYPE: body
:END:

This is a test.
"""
        org_file = tmp_path / "test.org"
        org_file.write_text(org_content)

        # Parse and generate
        ir = parse_org(str(org_file))
        output_file = tmp_path / "output.html"

        generate_story_html(ir, str(output_file))

        # Verify output exists
        assert output_file.exists()

        # Check HTML content
        html_content = output_file.read_text()

        # Should contain story structure
        assert '<!DOCTYPE html>' in html_content
        assert '<section class="scene"' in html_content
        assert 'grid-container' in html_content

        # Should have grid CSS variables
        assert '--grid-cols: 12' in html_content
        assert '--grid-rows: 12' in html_content

        # Should have navigation JavaScript
        assert 'keydown' in html_content
        assert 'scrollIntoView' in html_content

    def test_multiple_scenes(self, tmp_path):
        """Test generation with multiple scenes."""
        org_content = """#+TITLE: Multi Scene
#+GRID: 12x12

* Scene One
** Block
:PROPERTIES:
:TYPE: body
:END:

First scene

* Scene Two  
** Block
:PROPERTIES:
:TYPE: body
:END:

Second scene

* Scene Three
** Block
:PROPERTIES:
:TYPE: body
:END:

Third scene
"""
        org_file = tmp_path / "multi.org"
        org_file.write_text(org_content)

        ir = parse_org(str(org_file))
        output_file = tmp_path / "output.html"

        generate_story_html(ir, str(output_file))

        html_content = output_file.read_text()

        # Should have 3 sections
        assert html_content.count('<section class="scene"') == 3
        assert 'data-scene="1"' in html_content
        assert 'data-scene="2"' in html_content
        assert 'data-scene="3"' in html_content

    def test_three_column_auto_placement(self, tmp_path):
        """Test three-column auto-placement."""
        org_content = """#+TITLE: Three Columns
#+GRID: 12x12

* Scene
** Column 1
:PROPERTIES:
:TYPE: body
:END:

First

** Column 2
:PROPERTIES:
:TYPE: body
:END:

Second

** Column 3
:PROPERTIES:
:TYPE: body
:END:

Third
"""
        org_file = tmp_path / "three_col.org"
        org_file.write_text(org_content)

        ir = parse_org(str(org_file))
        output_file = tmp_path / "output.html"

        generate_story_html(ir, str(output_file))

        html_content = output_file.read_text()

        # Should have three blocks with grid areas
        # Column 1: 1/1/13/5 (cols 1-4)
        # Column 2: 1/5/13/9 (cols 5-8)
        # Column 3: 1/9/13/13 (cols 9-12)
        assert 'grid-area: 1 / 1 / 13 / 5' in html_content
        assert 'grid-area: 1 / 5 / 13 / 9' in html_content
        assert 'grid-area: 1 / 9 / 13 / 13' in html_content

    def test_explicit_area_override(self, tmp_path):
        """Test that explicit :AREA: declarations override auto-placement."""
        org_content = """#+TITLE: Explicit Override
#+GRID: 12x12

* Scene
** Custom Position
:PROPERTIES:
:TYPE: header
:AREA: A1,L3
:END:

Custom header

** Auto Block 1
:PROPERTIES:
:TYPE: body
:END:

Auto

** Auto Block 2
:PROPERTIES:
:TYPE: body
:END:

Auto
"""
        org_file = tmp_path / "override.org"
        org_file.write_text(org_content)

        ir = parse_org(str(org_file))
        output_file = tmp_path / "output.html"

        generate_story_html(ir, str(output_file))

        html_content = output_file.read_text()

        # First block should have explicit area (A1,L3 = x:1,y:1,w:3,h:12)
        # Which converts to grid-area: 1 / 1 / 13 / 4 (row/col/row-end/col-end)
        assert 'grid-area: 1 / 1 / 13 / 4' in html_content

        # Other two blocks should auto-place as 50/50 split
        assert 'grid-area: 1 / 1 / 13 / 7' in html_content
        assert 'grid-area: 1 / 7 / 13 / 13' in html_content

    def test_custom_grid_per_scene(self, tmp_path):
        """Test scene-level grid override."""
        org_content = """#+TITLE: Custom Grid
#+GRID: 12x12

* Scene One
:PROPERTIES:
:GRID: 8x8
:END:

** Block
:PROPERTIES:
:TYPE: body
:END:

Custom 8x8 grid

* Scene Two
** Block
:PROPERTIES:
:TYPE: body
:END:

Default 12x12 grid
"""
        org_file = tmp_path / "custom_grid.org"
        org_file.write_text(org_content)

        ir = parse_org(str(org_file))
        output_file = tmp_path / "output.html"

        generate_story_html(ir, str(output_file))

        html_content = output_file.read_text()

        # First scene should have 8x8 grid
        assert '--grid-cols: 8; --grid-rows: 8' in html_content

        # Second scene should have default 12x12
        assert '--grid-cols: 12; --grid-rows: 12' in html_content

    def test_list_rendering(self, tmp_path):
        """Test that lists render correctly in story mode."""
        org_content = """#+TITLE: Lists
#+GRID: 12x12

* Scene
** List Block
:PROPERTIES:
:TYPE: body
:END:

- Item one
- Item two
- Item three
"""
        org_file = tmp_path / "lists.org"
        org_file.write_text(org_content)

        ir = parse_org(str(org_file))
        output_file = tmp_path / "output.html"

        generate_story_html(ir, str(output_file))

        html_content = output_file.read_text()

        # Should have HTML list
        assert '<ul>' in html_content
        assert '<li>Item one</li>' in html_content
        assert '<li>Item two</li>' in html_content
        assert '<li>Item three</li>' in html_content

    def test_table_rendering(self, tmp_path):
        """Test that tables render correctly in story mode."""
        org_content = """#+TITLE: Tables
#+GRID: 12x12

* Scene
** Table Block
:PROPERTIES:
:TYPE: body
:END:

| Name  | Value |
|-------|-------|
| Alpha | 100   |
| Beta  | 200   |
"""
        org_file = tmp_path / "tables.org"
        org_file.write_text(org_content)

        ir = parse_org(str(org_file))
        output_file = tmp_path / "output.html"

        generate_story_html(ir, str(output_file))

        html_content = output_file.read_text()

        # Should have HTML table
        assert '<table>' in html_content
        assert '<thead>' in html_content
        assert '<tbody>' in html_content
        assert '<th>Name</th>' in html_content
        assert '<td>Alpha</td>' in html_content
