"""PDF post-processing utilities for OutputIntent injection."""

import pathlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class OutputIntentConfig:
    """Configuration for PDF OutputIntent injection."""

    icc_profile: pathlib.Path
    preset: Optional[Literal["screen", "printer", "prepress"]] = None
    leave_color_unchanged: bool = True


@dataclass
class InjectResult:
    """Result of OutputIntent injection attempt."""

    ok: bool
    reason: Optional[str] = None
    used_preset: Optional[str] = None
    tool: str = "gs"


def _gs_exists() -> bool:
    """Check if Ghostscript is available."""
    return shutil.which('gs') is not None


def pdf_has_output_intent(pdf_path: pathlib.Path) -> bool:
    """Check if PDF already contains an OutputIntent.

    Args:
        pdf_path: Path to PDF file to check

    Returns:
        True if PDF contains /OutputIntents
    """
    if not pdf_path.exists():
        return False

    try:
        # Read first 200KB to find /OutputIntents
        with open(pdf_path, 'rb') as f:
            data = f.read(200_000)

        # Decode forgivingly
        try:
            text = data.decode('latin-1', errors='ignore')
        except Exception:
            return False

        return '/OutputIntents' in text
    except Exception:
        return False


def find_srgb_icc() -> Optional[pathlib.Path]:
    """Discover system sRGB ICC profile.

    Returns:
        Path to sRGB profile if found, None otherwise
    """
    # Common sRGB ICC profile locations
    candidates = [
        # macOS
        '/System/Library/ColorSync/Profiles/sRGB Profile.icc',
        '/Library/ColorSync/Profiles/sRGB Profile.icc',
        # Linux
        '/usr/share/color/icc/srgb.icc',
        '/usr/share/color/icc/colord/sRGB.icc',
        '/usr/share/color/icc/ghostscript/srgb.icc',
        '/usr/local/share/color/icc/sRGB.icc',
        # Windows
        'C:\\Windows\\System32\\spool\\drivers\\color\\sRGB Color Space Profile.icm',
    ]

    for candidate in candidates:
        path = pathlib.Path(candidate)
        if path.exists():
            return path

    return None


def inject_output_intent(
    pdf_in: pathlib.Path, pdf_out: pathlib.Path, config: OutputIntentConfig
) -> InjectResult:
    """Inject OutputIntent into PDF using Ghostscript.

    Args:
        pdf_in: Input PDF path
        pdf_out: Output PDF path
        config: OutputIntent configuration

    Returns:
        InjectResult with success status and details
    """
    if not _gs_exists():
        return InjectResult(ok=False, reason="gs missing")

    if not pdf_in.exists():
        return InjectResult(ok=False, reason="input PDF not found")

    if not config.icc_profile.exists():
        return InjectResult(ok=False, reason="ICC profile not found")

    # Check if PDF already has OutputIntent
    if pdf_has_output_intent(pdf_in):
        return InjectResult(ok=False, reason="already has OutputIntent")

    # Build Ghostscript command
    cmd = ['gs', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.7', '-dNOPAUSE', '-dBATCH']

    # Add preset if specified (before explicit overrides)
    used_preset = None
    if config.preset:
        cmd.append(f'-dPDFSETTINGS=/{config.preset}')
        used_preset = config.preset

    # Color handling (after preset to override)
    if config.leave_color_unchanged:
        cmd.append('-dColorConversionStrategy=/LeaveColorUnchanged')

    # OutputIntent injection
    cmd.append(f'-sOutputICCProfile={config.icc_profile}')

    # Create temporary output file
    try:
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_path = pathlib.Path(tmp_file.name)

        cmd.extend([f'-sOutputFile={tmp_path}', str(pdf_in)])

        # Run Ghostscript
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
        )

        if result.returncode != 0:
            # Clean up temp file
            try:
                tmp_path.unlink()
            except Exception:
                pass
            return InjectResult(
                ok=False,
                reason=f"ghostscript failed: {result.stderr.strip()[:100]}",
                used_preset=used_preset,
            )

        # Verify output was created
        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            try:
                tmp_path.unlink()
            except Exception:
                pass
            return InjectResult(
                ok=False, reason="ghostscript produced no output", used_preset=used_preset
            )

        # Atomic move to final location
        try:
            pdf_out.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.replace(pdf_out)
        except Exception as e:
            try:
                tmp_path.unlink()
            except Exception:
                pass
            return InjectResult(
                ok=False, reason=f"failed to move output: {e}", used_preset=used_preset
            )

        return InjectResult(ok=True, used_preset=used_preset)

    except subprocess.TimeoutExpired:
        return InjectResult(ok=False, reason="ghostscript timeout", used_preset=used_preset)
    except Exception as e:
        return InjectResult(ok=False, reason=f"unexpected error: {e}", used_preset=used_preset)


def maybe_inject_output_intent(
    pdf_path: pathlib.Path,
    icc_profile_path: Optional[pathlib.Path] = None,
    use_srgb_discovery: bool = False,
    preset: Optional[Literal["screen", "printer", "prepress"]] = None,
) -> InjectResult:
    """Convenience wrapper for OutputIntent injection with discovery.

    Args:
        pdf_path: PDF file to process (modified in-place on success)
        icc_profile_path: Explicit ICC profile path (takes precedence)
        use_srgb_discovery: Discover system sRGB profile if no explicit path
        preset: Optional PDF quality preset

    Returns:
        InjectResult with success status and details
    """
    # Resolve ICC profile
    icc_path = None
    if icc_profile_path:
        icc_path = icc_profile_path
    elif use_srgb_discovery:
        icc_path = find_srgb_icc()
        if not icc_path:
            return InjectResult(ok=False, reason="sRGB ICC profile not found")
    else:
        return InjectResult(ok=False, reason="no ICC profile specified")

    # Create config
    config = OutputIntentConfig(icc_profile=icc_path, preset=preset, leave_color_unchanged=True)

    # Inject with atomic replacement
    return inject_output_intent(pdf_path, pdf_path, config)
