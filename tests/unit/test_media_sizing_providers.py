"""Unit tests for PDF and Raster size providers."""

from unittest.mock import MagicMock, Mock, patch

from pagemaker.generation.media_sizing import PdfSizeProvider, RasterSizeProvider


class TestPdfSizeProvider:
    """Test PDF intrinsic size detection."""

    def setup_method(self):
        """Initialize provider for each test."""
        self.provider = PdfSizeProvider()

    def test_pdf_size_provider_calls_pdf_processor(self):
        """Test that PdfSizeProvider delegates to pdf_intrinsic_size_mm."""
        with patch('pagemaker.generation.pdf_processor.pdf_intrinsic_size_mm') as mock_pdf_size:
            mock_pdf_size.return_value = (210.0, 297.0)  # A4 dimensions

            result = self.provider.get_size_mm('test.pdf')

            assert result == (210.0, 297.0)
            mock_pdf_size.assert_called_once_with('test.pdf', box=None)

    def test_pdf_size_provider_passes_box_parameter(self):
        """Test that box parameter is forwarded correctly."""
        with patch('pagemaker.generation.pdf_processor.pdf_intrinsic_size_mm') as mock_pdf_size:
            mock_pdf_size.return_value = (200.0, 280.0)

            result = self.provider.get_size_mm('test.pdf', box='trim')

            assert result == (200.0, 280.0)
            mock_pdf_size.assert_called_once_with('test.pdf', box='trim')

    def test_pdf_size_provider_handles_exception(self):
        """Test graceful handling when PDF cannot be read."""
        with patch('pagemaker.generation.pdf_processor.pdf_intrinsic_size_mm') as mock_pdf_size:
            mock_pdf_size.side_effect = Exception("PDF corrupted")

            result = self.provider.get_size_mm('bad.pdf')

            # Should return None and emit warning
            assert result is None

    def test_pdf_size_provider_returns_none_for_nonexistent(self):
        """Test handling of nonexistent PDF."""
        with patch('pagemaker.generation.pdf_processor.pdf_intrinsic_size_mm') as mock_pdf_size:
            mock_pdf_size.side_effect = FileNotFoundError("File not found")

            result = self.provider.get_size_mm('/nonexistent/file.pdf')

            assert result is None


class TestRasterSizeProvider:
    """Test raster image size detection with PIL."""

    def setup_method(self):
        """Initialize provider for each test."""
        self.provider = RasterSizeProvider()

    def test_raster_with_dpi_metadata(self):
        """Test raster image with DPI metadata."""
        mock_img = MagicMock()
        mock_img.size = (1920, 1080)  # pixels
        mock_img.info = {'dpi': (300, 300)}  # DPI from EXIF
        mock_img.__enter__ = Mock(return_value=mock_img)
        mock_img.__exit__ = Mock(return_value=False)

        from PIL import Image

        with patch.object(Image, 'open', return_value=mock_img):
            with patch('pagemaker.generation.media_sizing.pathlib.Path.exists', return_value=True):
                result = self.provider.get_size_mm('photo.jpg')

                assert result is not None
                w_mm, h_mm = result
                # 1920px @ 300 DPI = 1920 / 300 * 25.4 = 162.56mm
                # 1080px @ 300 DPI = 1080 / 300 * 25.4 = 91.44mm
                assert abs(w_mm - 162.56) < 0.01
                assert abs(h_mm - 91.44) < 0.01

    def test_raster_without_dpi_uses_default_96(self):
        """Test raster image without DPI metadata defaults to 96 DPI."""
        mock_img = MagicMock()
        mock_img.size = (96, 48)  # pixels
        mock_img.info = {}  # No DPI metadata
        mock_img.__enter__ = Mock(return_value=mock_img)
        mock_img.__exit__ = Mock(return_value=False)

        from PIL import Image

        with patch.object(Image, 'open', return_value=mock_img):
            with patch('pagemaker.generation.media_sizing.pathlib.Path.exists', return_value=True):
                result = self.provider.get_size_mm('image.png')

                assert result is not None
                w_mm, h_mm = result
                # 96px @ 96 DPI = 1 inch = 25.4mm
                # 48px @ 96 DPI = 0.5 inch = 12.7mm
                assert abs(w_mm - 25.4) < 0.01
                assert abs(h_mm - 12.7) < 0.01

    def test_raster_pil_not_available(self):
        """Test graceful handling when PIL/Pillow not installed."""
        # Patch the import statement inside the get_size_mm method
        with patch.dict('sys.modules', {'PIL': None, 'PIL.Image': None}):
            # Reload the provider to trigger import failure
            from importlib import reload

            import pagemaker.generation.media_sizing as media_sizing_module

            reload(media_sizing_module)

            # Now test
            provider = media_sizing_module.RasterSizeProvider()
            result = provider.get_size_mm('photo.jpg')

            # Should return None silently (PIL is optional)
            assert result is None

            # Reload again to restore normal state
            reload(media_sizing_module)

    def test_raster_nonexistent_file(self):
        """Test handling of nonexistent file."""
        result = self.provider.get_size_mm('/nonexistent/image.jpg')

        # Should return None (file doesn't exist)
        assert result is None

    def test_raster_corrupted_file(self):
        """Test handling of corrupted image file."""
        with patch('PIL.Image') as mock_Image:
            with patch('pagemaker.generation.media_sizing.pathlib.Path.exists', return_value=True):
                mock_Image.open.side_effect = Exception("Cannot identify image file")

                result = self.provider.get_size_mm('corrupted.jpg')

                # Should return None and emit warning
                assert result is None

    def test_raster_handles_tuple_dpi(self):
        """Test handling of DPI as tuple."""
        mock_img = MagicMock()
        mock_img.size = (600, 400)
        mock_img.info = {'dpi': (150, 150)}
        mock_img.__enter__ = Mock(return_value=mock_img)
        mock_img.__exit__ = Mock(return_value=False)

        with patch('PIL.Image') as mock_Image:
            with patch('pagemaker.generation.media_sizing.pathlib.Path.exists', return_value=True):
                mock_Image.open.return_value = mock_img

                result = self.provider.get_size_mm('image.png')

                assert result is not None
                w_mm, h_mm = result
                # 600px @ 150 DPI = 600 / 150 * 25.4 = 101.6mm
                # 400px @ 150 DPI = 400 / 150 * 25.4 = 67.73mm
                assert abs(w_mm - 101.6) < 0.01
                assert abs(h_mm - 67.73) < 0.01

    def test_raster_handles_list_dpi(self):
        """Test handling of DPI as list."""
        mock_img = MagicMock()
        mock_img.size = (300, 200)
        mock_img.info = {'dpi': [72, 72]}  # List instead of tuple
        mock_img.__enter__ = Mock(return_value=mock_img)
        mock_img.__exit__ = Mock(return_value=False)

        with patch('PIL.Image') as mock_Image:
            with patch('pagemaker.generation.media_sizing.pathlib.Path.exists', return_value=True):
                mock_Image.open.return_value = mock_img

                result = self.provider.get_size_mm('image.jpg')

                assert result is not None
                w_mm, h_mm = result
                # 300px @ 72 DPI = 300 / 72 * 25.4 = 105.83mm
                # 200px @ 72 DPI = 200 / 72 * 25.4 = 70.56mm
                assert abs(w_mm - 105.83) < 0.01
                assert abs(h_mm - 70.56) < 0.01

    def test_raster_handles_zero_dpi(self):
        """Test handling of zero or invalid DPI (should use default)."""
        mock_img = MagicMock()
        mock_img.size = (192, 96)
        mock_img.info = {'dpi': (0, 0)}  # Invalid DPI
        mock_img.__enter__ = Mock(return_value=mock_img)
        mock_img.__exit__ = Mock(return_value=False)

        with patch('PIL.Image') as mock_Image:
            with patch('pagemaker.generation.media_sizing.pathlib.Path.exists', return_value=True):
                mock_Image.open.return_value = mock_img

                result = self.provider.get_size_mm('image.bmp')

                assert result is not None
                w_mm, h_mm = result
                # Should fall back to 96 DPI
                # 192px @ 96 DPI = 2 inches = 50.8mm
                # 96px @ 96 DPI = 1 inch = 25.4mm
                assert abs(w_mm - 50.8) < 0.01
                assert abs(h_mm - 25.4) < 0.01

    def test_raster_different_dpi_x_y(self):
        """Test handling of different horizontal and vertical DPI."""
        mock_img = MagicMock()
        mock_img.size = (200, 100)
        mock_img.info = {'dpi': (100, 50)}  # Different X and Y DPI
        mock_img.__enter__ = Mock(return_value=mock_img)
        mock_img.__exit__ = Mock(return_value=False)

        with patch('PIL.Image') as mock_Image:
            with patch('pagemaker.generation.media_sizing.pathlib.Path.exists', return_value=True):
                mock_Image.open.return_value = mock_img

                result = self.provider.get_size_mm('stretched.png')

                assert result is not None
                w_mm, h_mm = result
                # 200px @ 100 DPI = 200 / 100 * 25.4 = 50.8mm
                # 100px @ 50 DPI = 100 / 50 * 25.4 = 50.8mm
                assert abs(w_mm - 50.8) < 0.01
                assert abs(h_mm - 50.8) < 0.01
