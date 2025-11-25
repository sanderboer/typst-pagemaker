"""
Tests for story mode auto-placement algorithm.
"""

from pagemaker.generation.story_auto_placement import (
    area_to_css_grid,
    compute_auto_placement,
)


class TestAutoPlacement:
    """Test auto-placement algorithm for different sibling counts."""

    def test_single_block_full_viewport(self):
        """Single block should occupy entire grid."""
        blocks = [{'id': 'block1', 'type': 'body'}]

        result = compute_auto_placement(blocks, grid_cols=12, grid_rows=12)

        assert len(result) == 1
        assert result[0]['area'] == {'x': 1, 'y': 1, 'w': 12, 'h': 12}

    def test_two_blocks_split_left_right(self):
        """Two blocks should split 50/50 left and right."""
        blocks = [
            {'id': 'left', 'type': 'body'},
            {'id': 'right', 'type': 'body'},
        ]

        result = compute_auto_placement(blocks, grid_cols=12, grid_rows=12)

        assert len(result) == 2
        # Left half: cols 1-6
        assert result[0]['area'] == {'x': 1, 'y': 1, 'w': 6, 'h': 12}
        # Right half: cols 7-12
        assert result[1]['area'] == {'x': 7, 'y': 1, 'w': 6, 'h': 12}

    def test_three_blocks_three_columns(self):
        """Three blocks should create three equal columns."""
        blocks = [
            {'id': 'col1', 'type': 'body'},
            {'id': 'col2', 'type': 'body'},
            {'id': 'col3', 'type': 'body'},
        ]

        result = compute_auto_placement(blocks, grid_cols=12, grid_rows=12)

        assert len(result) == 3
        # First third: cols 1-4
        assert result[0]['area'] == {'x': 1, 'y': 1, 'w': 4, 'h': 12}
        # Second third: cols 5-8
        assert result[1]['area'] == {'x': 5, 'y': 1, 'w': 4, 'h': 12}
        # Third third: cols 9-12
        assert result[2]['area'] == {'x': 9, 'y': 1, 'w': 4, 'h': 12}

    def test_four_blocks_two_by_two_grid(self):
        """Four blocks should create a 2x2 grid."""
        blocks = [
            {'id': 'block1', 'type': 'body'},
            {'id': 'block2', 'type': 'body'},
            {'id': 'block3', 'type': 'body'},
            {'id': 'block4', 'type': 'body'},
        ]

        result = compute_auto_placement(blocks, grid_cols=12, grid_rows=12)

        assert len(result) == 4
        # Top-left
        assert result[0]['area'] == {'x': 1, 'y': 1, 'w': 6, 'h': 6}
        # Top-right
        assert result[1]['area'] == {'x': 7, 'y': 1, 'w': 6, 'h': 6}
        # Bottom-left
        assert result[2]['area'] == {'x': 1, 'y': 7, 'w': 6, 'h': 6}
        # Bottom-right
        assert result[3]['area'] == {'x': 7, 'y': 7, 'w': 6, 'h': 6}

    def test_six_blocks_three_by_two_grid(self):
        """Six blocks should create a 2-column, 3-row grid."""
        blocks = [{'id': f'block{i}', 'type': 'body'} for i in range(1, 7)]

        result = compute_auto_placement(blocks, grid_cols=12, grid_rows=12)

        assert len(result) == 6
        # Each row should be 4 units high (12 / 3)
        # Each column should be 6 units wide (12 / 2)
        row_height = 4
        col_width = 6

        # Verify grid pattern
        for idx in range(6):
            col_idx = idx % 2
            row_idx = idx // 2

            expected_x = (col_idx * col_width) + 1
            expected_y = (row_idx * row_height) + 1

            assert result[idx]['area']['x'] == expected_x
            assert result[idx]['area']['y'] == expected_y
            assert result[idx]['area']['w'] == col_width
            assert result[idx]['area']['h'] == row_height

    def test_explicit_area_preserved(self):
        """Blocks with explicit :AREA: should not be auto-placed."""
        blocks = [
            {'id': 'explicit', 'type': 'header', 'area': {'x': 1, 'y': 1, 'w': 12, 'h': 2}},
            {'id': 'auto1', 'type': 'body'},
            {'id': 'auto2', 'type': 'body'},
        ]

        result = compute_auto_placement(blocks, grid_cols=12, grid_rows=12)

        assert len(result) == 3
        # First block keeps explicit area
        assert result[0]['area'] == {'x': 1, 'y': 1, 'w': 12, 'h': 2}
        # Remaining blocks get auto-placed (2 blocks → 50/50)
        assert result[1]['area'] == {'x': 1, 'y': 1, 'w': 6, 'h': 12}
        assert result[2]['area'] == {'x': 7, 'y': 1, 'w': 6, 'h': 12}

    def test_all_explicit_areas_unchanged(self):
        """All blocks with explicit areas should pass through unchanged."""
        blocks = [
            {'id': 'b1', 'area': {'x': 1, 'y': 1, 'w': 3, 'h': 3}},
            {'id': 'b2', 'area': {'x': 4, 'y': 1, 'w': 3, 'h': 3}},
        ]

        result = compute_auto_placement(blocks, grid_cols=12, grid_rows=12)

        assert result == blocks  # Should be unchanged

    def test_empty_blocks_list(self):
        """Empty blocks list should return empty list."""
        result = compute_auto_placement([], grid_cols=12, grid_rows=12)
        assert result == []

    def test_custom_grid_size(self):
        """Auto-placement should respect custom grid dimensions."""
        blocks = [
            {'id': 'b1', 'type': 'body'},
            {'id': 'b2', 'type': 'body'},
        ]

        # 8x10 grid
        result = compute_auto_placement(blocks, grid_cols=8, grid_rows=10)

        assert len(result) == 2
        # Left half: cols 1-4
        assert result[0]['area'] == {'x': 1, 'y': 1, 'w': 4, 'h': 10}
        # Right half: cols 5-8
        assert result[1]['area'] == {'x': 5, 'y': 1, 'w': 4, 'h': 10}


class TestAreaToCssGrid:
    """Test conversion from area dict to CSS grid-area string."""

    def test_simple_area(self):
        """Test basic area conversion."""
        area = {'x': 1, 'y': 1, 'w': 6, 'h': 4}
        result = area_to_css_grid(area)
        # row-start / col-start / row-end / col-end
        assert result == "1 / 1 / 5 / 7"

    def test_full_grid_area(self):
        """Test full grid (12x12) area."""
        area = {'x': 1, 'y': 1, 'w': 12, 'h': 12}
        result = area_to_css_grid(area)
        assert result == "1 / 1 / 13 / 13"

    def test_offset_area(self):
        """Test area that doesn't start at origin."""
        area = {'x': 4, 'y': 3, 'w': 5, 'h': 6}
        result = area_to_css_grid(area)
        # row 3->9, col 4->9
        assert result == "3 / 4 / 9 / 9"

    def test_single_cell_area(self):
        """Test single cell area."""
        area = {'x': 5, 'y': 7, 'w': 1, 'h': 1}
        result = area_to_css_grid(area)
        assert result == "7 / 5 / 8 / 6"
