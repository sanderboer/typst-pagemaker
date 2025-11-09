"""Intrinsic size providers for media assets.

This module provides a unified interface for obtaining the intrinsic dimensions
of various media types (PDFs, SVGs, raster images). Each provider implements
the IntrinsicSizeProvider protocol and returns dimensions in millimeters.

The provider pattern allows consistent size detection across media types while
encapsulating type-specific parsing logic.

Example:
    >>> from pagemaker.generation.media_sizing import SvgSizeProvider
    >>> provider = SvgSizeProvider()
    >>> width_mm, height_mm = provider.get_size_mm('diagram.svg')
    >>> print(f"SVG is {width_mm}mm × {height_mm}mm")

Architecture:
    Layer 1 (this module): Size detection
    Layer 2 (media_renderer): Rendering strategies
    Layer 3 (core): Factory and orchestration
"""

import pathlib
import warnings
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Optional, Tuple


class IntrinsicSizeProvider(ABC):
    """Abstract base class for media dimension providers.

    All providers must implement get_size_mm() to return intrinsic dimensions
    in millimeters or None if the size cannot be determined.
    """

    @abstractmethod
    def get_size_mm(self, src: str, **kwargs) -> Optional[Tuple[float, float]]:
        """Get intrinsic dimensions of media asset.

        Args:
            src: Path to media file (relative or absolute)
            **kwargs: Provider-specific options (e.g., box preference for PDFs)

        Returns:
            Tuple of (width_mm, height_mm) or None if indeterminate.
            Dimensions must be positive floats representing millimeters.

        Note:
            Returning None is acceptable and triggers fallback behavior in
            rendering strategies. Providers should handle errors gracefully
            and log warnings for malformed files.
        """
        pass


class PdfSizeProvider(IntrinsicSizeProvider):
    """Provider for PDF page dimensions.

    Wraps the existing pdf_intrinsic_size_mm function from pdf_processor module.
    Supports box preference for choosing which PDF page box to use (CropBox,
    TrimBox, MediaBox, etc.).

    Example:
        >>> provider = PdfSizeProvider()
        >>> # Use default box preference (CropBox → TrimBox → MediaBox)
        >>> w, h = provider.get_size_mm('document.pdf')
        >>> # Force MediaBox
        >>> w, h = provider.get_size_mm('document.pdf', box='media')
    """

    def get_size_mm(
        self, src: str, box: Optional[str] = None, **kwargs
    ) -> Optional[Tuple[float, float]]:
        """Get PDF page dimensions.

        Args:
            src: Path to PDF file
            box: Optional box preference ('media', 'crop', 'trim', 'bleed', 'art')
                 If None, uses priority order: CropBox → TrimBox → BleedBox → ArtBox → MediaBox
            **kwargs: Ignored (for interface compatibility)

        Returns:
            (width_mm, height_mm) or None if PDF cannot be read
        """
        try:
            from .pdf_processor import pdf_intrinsic_size_mm

            return pdf_intrinsic_size_mm(src, box=box)
        except Exception as e:
            warnings.warn(f"Could not determine PDF size for '{src}': {e}", UserWarning)
            return None


class SvgSizeProvider(IntrinsicSizeProvider):
    """Provider for SVG intrinsic dimensions.

    Parses SVG viewBox attribute or width/height attributes to determine
    intrinsic size. Converts SVG units to millimeters using standard DPI
    assumptions (96 DPI for user units).

    Supported unit conversions:
        - px (pixels): 1px = 25.4/96 mm (assumes 96 DPI)
        - pt (points): 1pt = 25.4/72 mm
        - cm (centimeters): 1cm = 10mm
        - mm (millimeters): 1mm = 1mm
        - in (inches): 1in = 25.4mm
        - User units (no suffix): treated as px

    Example:
        >>> provider = SvgSizeProvider()
        >>> # SVG with viewBox="0 0 200 100"
        >>> w, h = provider.get_size_mm('icon.svg')
        >>> # Returns (52.92, 26.46) - 200px × 100px at 96 DPI

    Note:
        Percentage units are not supported (would require parent context).
        Malformed SVGs return None with a warning.
    """

    # Unit conversion factors to millimeters
    # Reference: https://www.w3.org/TR/css-values-3/#absolute-lengths
    UNIT_TO_MM = {
        'px': 25.4 / 96,  # 96 DPI standard
        'pt': 25.4 / 72,  # PostScript point
        'cm': 10.0,  # Centimeter
        'mm': 1.0,  # Millimeter
        'in': 25.4,  # Inch
    }

    def get_size_mm(self, src: str, **kwargs) -> Optional[Tuple[float, float]]:
        """Get SVG intrinsic dimensions.

        Args:
            src: Path to SVG file
            **kwargs: Ignored (for interface compatibility)

        Returns:
            (width_mm, height_mm) or None if SVG cannot be parsed

        Note:
            Parsing order:
            1. Try viewBox attribute (most reliable)
            2. Fall back to width/height attributes
            3. Return None if neither available
        """
        try:
            # Try to resolve path - handle both absolute and relative paths
            path = pathlib.Path(src)

            # If path doesn't exist as-is, try resolving from common locations
            if not path.exists():
                # Try from export directory (common case after asset path adjustment)
                export_path = pathlib.Path.cwd() / 'export' / src
                if export_path.exists():
                    path = export_path
                else:
                    # Try from current working directory
                    cwd_path = pathlib.Path.cwd() / src
                    if cwd_path.exists():
                        path = cwd_path
                    else:
                        # Path still doesn't exist
                        return None

            # Parse SVG XML
            tree = ET.parse(path)
            root = tree.getroot()

            # Try viewBox first (most reliable for intrinsic size)
            viewbox = root.get('viewBox')
            if viewbox:
                result = self._parse_viewbox(viewbox)
                if result:
                    return result

            # Fall back to width/height attributes
            width_attr = root.get('width')
            height_attr = root.get('height')
            if width_attr and height_attr:
                result = self._parse_width_height(width_attr, height_attr)
                if result:
                    return result

            # No usable dimensions found
            warnings.warn(f"SVG '{src}' has no viewBox or width/height attributes", UserWarning)
            return None

        except ET.ParseError as e:
            warnings.warn(f"Malformed XML in SVG '{src}': {e}", UserWarning)
            return None
        except Exception as e:
            warnings.warn(f"Could not parse SVG '{src}': {e}", UserWarning)
            return None

    def _parse_viewbox(self, viewbox: str) -> Optional[Tuple[float, float]]:
        """Parse SVG viewBox attribute.

        Args:
            viewbox: Value of viewBox attribute (e.g., "0 0 200 100")

        Returns:
            (width_mm, height_mm) or None if invalid format

        Note:
            viewBox format: "min-x min-y width height"
            We only care about width and height (3rd and 4th values)
        """
        try:
            parts = viewbox.strip().split()
            if len(parts) != 4:
                return None

            # viewBox values are in user units (treat as px)
            width_units = float(parts[2])
            height_units = float(parts[3])

            if width_units <= 0 or height_units <= 0:
                return None

            # Convert user units to mm (96 DPI)
            width_mm = width_units * self.UNIT_TO_MM['px']
            height_mm = height_units * self.UNIT_TO_MM['px']

            return (width_mm, height_mm)

        except (ValueError, IndexError):
            return None

    def _parse_width_height(self, width: str, height: str) -> Optional[Tuple[float, float]]:
        """Parse SVG width/height attributes with units.

        Args:
            width: Value of width attribute (e.g., "200px", "5cm", "2in")
            height: Value of height attribute

        Returns:
            (width_mm, height_mm) or None if invalid format

        Note:
            Handles numeric values with optional unit suffix.
            No unit = user units (treated as px).
            Percentage units not supported.
        """
        try:
            width_mm = self._parse_dimension(width)
            height_mm = self._parse_dimension(height)

            if width_mm is None or height_mm is None:
                return None
            if width_mm <= 0 or height_mm <= 0:
                return None

            return (width_mm, height_mm)

        except Exception:
            return None

    def _parse_dimension(self, value: str) -> Optional[float]:
        """Parse a single dimension value with optional unit.

        Args:
            value: Dimension string (e.g., "200", "5cm", "2.5in")

        Returns:
            Value in millimeters or None if invalid
        """
        value = value.strip()

        # Check for percentage (not supported)
        if '%' in value:
            return None

        # Try to extract number and unit
        # Match: optional sign, digits with optional decimal, optional unit
        import re

        match = re.match(r'^([+-]?[0-9]*\.?[0-9]+)\s*([a-zA-Z]*)$', value)
        if not match:
            return None

        number = float(match.group(1))
        unit = match.group(2).lower()

        # No unit = user units (treat as px)
        if not unit:
            unit = 'px'

        # Convert to mm
        factor = self.UNIT_TO_MM.get(unit)
        if factor is None:
            # Unknown unit
            return None

        return number * factor


class RasterSizeProvider(IntrinsicSizeProvider):
    """Provider for raster image dimensions (PNG, JPEG, etc.).

    Uses PIL/Pillow to read image dimensions and DPI metadata.
    If PIL is not available, returns None gracefully.

    DPI Handling:
        - Prefers DPI from EXIF/metadata
        - Falls back to 96 DPI if no metadata present
        - Converts pixels to mm: mm = px / dpi * 25.4

    Example:
        >>> provider = RasterSizeProvider()
        >>> w, h = provider.get_size_mm('photo.jpg')
        >>> # Returns dimensions based on image size and DPI

    Note:
        If PIL/Pillow is not installed, all calls return None.
        Install with: pip install Pillow
    """

    DEFAULT_DPI = 96  # Standard screen DPI

    def get_size_mm(self, src: str, **kwargs) -> Optional[Tuple[float, float]]:
        """Get raster image dimensions.

        Args:
            src: Path to image file (PNG, JPEG, GIF, etc.)
            **kwargs: Ignored (for interface compatibility)

        Returns:
            (width_mm, height_mm) or None if image cannot be read or PIL unavailable
        """
        try:
            from PIL import Image
        except ImportError:
            # PIL not available - return None silently
            # (Not a warning because it's optional dependency)
            return None

        try:
            # Try to resolve path - handle both absolute and relative paths
            path = pathlib.Path(src)

            # If path doesn't exist as-is, try resolving from common locations
            if not path.exists():
                # Try from export directory (common case after asset path adjustment)
                export_path = pathlib.Path.cwd() / 'export' / src
                if export_path.exists():
                    path = export_path
                else:
                    # Try from current working directory
                    cwd_path = pathlib.Path.cwd() / src
                    if cwd_path.exists():
                        path = cwd_path
                    else:
                        # Path still doesn't exist
                        return None

            with Image.open(path) as img:
                width_px, height_px = img.size

                # Try to get DPI from metadata
                dpi = img.info.get('dpi', (self.DEFAULT_DPI, self.DEFAULT_DPI))

                # Handle different DPI formats
                if isinstance(dpi, (tuple, list)) and len(dpi) >= 2:
                    dpi_x, dpi_y = float(dpi[0]), float(dpi[1])
                else:
                    dpi_x = dpi_y = float(dpi) if dpi else self.DEFAULT_DPI

                # Avoid division by zero
                if dpi_x <= 0:
                    dpi_x = self.DEFAULT_DPI
                if dpi_y <= 0:
                    dpi_y = self.DEFAULT_DPI

                # Convert pixels to mm
                width_mm = width_px / dpi_x * 25.4
                height_mm = height_px / dpi_y * 25.4

                return (width_mm, height_mm)

        except Exception as e:
            warnings.warn(f"Could not read raster image '{src}': {e}", UserWarning)
            return None
