# Media Rendering Architecture

**Version**: 1.0  
**Last Updated**: 2025-11-09  
**Status**: Current Implementation

---

## Overview

This document describes the architecture for media rendering in pagemaker. The system provides a unified interface for embedding images, SVGs, and PDFs with consistent support for sizing, alignment, and fit modes (contain, cover, stretch).

**Status**: All three media types (raster images, SVGs, PDFs) now support full cover mode with alignment-based cropping (M3 complete, Nov 2025).

### Problem Statement

Prior to this architecture, media rendering was handled by 160+ lines of duplicated code with type-specific if/elif branches. Key issues included:

- **Code Duplication**: Similar logic repeated for each media type (figure/svg/pdf)
- **SVG Sizing Bug**: SVG alignment used frame size instead of intrinsic dimensions ✅ **FIXED**
- **Cover Mode Broken**: Cover mode didn't work for any media type ✅ **FIXED**
- **Poor Extensibility**: Adding new media types required modifying core rendering logic

All issues have been resolved through the unified architecture (M1-M4 complete, Nov 2025).

### Solution Architecture

The new architecture uses a **layered strategy pattern**:

1. **Layer 1: Size Providers** - Detect intrinsic dimensions (media_sizing.py)
2. **Layer 2: Render Strategies** - Generate Typst code (media_renderer.py)
3. **Layer 3: Factory & Orchestration** - Coordinate rendering (core.py)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    core.py (Layer 3)                        │
│  ┌────────────────────────────────────────────────────┐    │
│  │  get_media_renderer(type) → Strategy Instance      │    │
│  │  Provides: RenderContext, coordinates rendering    │    │
│  └────────────────────────────────────────────────────┘    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              media_renderer.py (Layer 2)                    │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │ MediaRenderStrategy (ABC)              │               │
│  │  • can_use_simple_path()               │               │
│  │  • render_simple()                     │               │
│  │  • render_manual()                     │               │
│  │  • render() [orchestrator]             │               │
│  └──────────────────┴──────────────────┬──┘               │
│           ▲              ▲              ▲                   │
│           │              │              │                   │
│  ┌────────┴────┐  ┌──────┴──────┐  ┌───┴──────┐           │
│  │   Figure    │  │     SVG     │  │   PDF    │           │
│  │  Strategy   │  │  Strategy   │  │ Strategy │           │
│  └─────────────┘  └─────────────┘  └──────────┘           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              media_sizing.py (Layer 1)                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ IntrinsicSizeProvider (ABC)                          │  │
│  │  • get_size_mm(src, **kwargs) → (w_mm, h_mm)        │  │
│  └───────────────────┬──────────────────────────────────┘  │
│           ▲          ▲          ▲                           │
│           │          │          │                           │
│  ┌────────┴────┐  ┌──┴──────┐  ┌┴──────────┐               │
│  │    PDF     │  │   SVG   │  │  Raster   │               │
│  │  Provider  │  │ Provider│  │  Provider │               │
│  └────────────┘  └─────────┘  └───────────┘               │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Intrinsic Size Providers

**Module**: `src/pagemaker/generation/media_sizing.py`

### Purpose
Detect the intrinsic (natural) dimensions of media assets and return them in millimeters.

### Interface

```python
class IntrinsicSizeProvider(ABC):
    @abstractmethod
    def get_size_mm(self, src: str, **kwargs) -> Optional[Tuple[float, float]]:
        """Return (width_mm, height_mm) or None if indeterminate."""
        pass
```

### Implementations

#### PdfSizeProvider
- Wraps `pdf_intrinsic_size_mm()` from pdf_processor
- Supports box preference parameter (media, crop, trim, bleed, art)
- Default priority: CropBox → TrimBox → BleedBox → ArtBox → MediaBox
- Returns dimensions at 72 pt/in standard

**Example**:
```python
provider = PdfSizeProvider()
width_mm, height_mm = provider.get_size_mm('doc.pdf', box='media')
```

#### SvgSizeProvider
- Parses XML to extract viewBox or width/height attributes
- Supports units: px (default), pt, cm, mm, in
- Converts to mm using 96 DPI for user units (1px = 25.4/96 mm)
- Handles malformed XML gracefully (returns None)

**Example**:
```python
provider = SvgSizeProvider()
width_mm, height_mm = provider.get_size_mm('diagram.svg')
# For SVG with viewBox="0 0 200 100"
# Returns: (52.916..., 26.458...) mm
```

#### RasterSizeProvider
- Uses PIL/Pillow to read image dimensions
- Extracts DPI from EXIF metadata or defaults to 96 DPI
- Converts pixels to mm: `mm = px / dpi * 25.4`
- Gracefully degrades if PIL unavailable

**Example**:
```python
provider = RasterSizeProvider()
width_mm, height_mm = provider.get_size_mm('photo.jpg')
```

### Design Principles

1. **Graceful Failure**: Return `None` instead of raising exceptions
2. **Warning on Error**: Emit `UserWarning` for malformed/missing files
3. **Unit Consistency**: Always return millimeters
4. **Type Isolation**: Each provider handles only its media type

---

## Layer 2: Media Render Strategies

**Module**: `src/pagemaker/generation/media_renderer.py`

### Purpose
Generate Typst code for embedding media with proper sizing, alignment, and fit modes.

### Core Data Structures

#### RenderContext
Input parameters provided by core.py:

```python
@dataclass
class RenderContext:
    element: dict           # Full element IR
    frame_w_mm: float      # Available width in mm
    frame_h_mm: float      # Available height in mm
    align: Optional[str]   # Horizontal alignment (left/center/right)
    valign: Optional[str]  # Vertical alignment (top/middle/bottom)
```

#### RenderedMedia
Output produced by strategies:

```python
@dataclass
class RenderedMedia:
    typst_code: str        # Generated Typst expression
    needs_wrapper: bool    # Whether to wrap in align() helper
```

### Strategy Interface

```python
class MediaRenderStrategy(ABC):
    def can_use_simple_path(self, ctx: RenderContext) -> bool:
        """Check if simple rendering path is sufficient."""
        
    def render_simple(self, ctx: RenderContext) -> RenderedMedia:
        """Generate simple Typst using built-in image() function."""
        
    def render_manual(self, ctx: RenderContext) -> RenderedMedia:
        """Generate manual layout with clipping/positioning."""
        
    def render(self, ctx: RenderContext) -> RenderedMedia:
        """Orchestrate rendering by choosing simple or manual path."""
```

### Decision Tree

Each strategy's `render()` method follows this pattern:

```
┌─────────────────────────────────────────────────┐
│ render(ctx)                                     │
│  1. Extract properties (src, fit, caption, ...) │
│  2. Get intrinsic size from provider            │
│  3. Can use simple path?                        │
│     YES → render_simple()                       │
│     NO  → render_manual()                       │
└─────────────────────────────────────────────────┘
```

### Implementations

#### FigureRenderStrategy
Handles raster images (PNG, JPEG, GIF, etc.).

**Simple Path**:
- No alignment or cover mode
- Delegates to Typst `image(fit: "contain/stretch")`

**Manual Path**:
- Cover mode: clips oversized content
- With alignment: positions within frame
- With caption: reserves space and uses `Fig()` helper

**Example Output (cover with caption)**:
```typst
Fig(
  block(width: 148.5mm, height: 100mm, clip: true)[
    #place(dy: -24.25mm, image("photo.jpg", width: 148.5mm, height: 148.5mm))
  ],
  caption: [My Photo],
  fill_space: false
)
```

#### SvgRenderStrategy
Handles SVG vector graphics.

**Simple Path**:
- Contain/stretch without alignment
- Uses Typst `image(fit: "contain")`

**Manual Path**:
- Cover mode OR with alignment
- Uses intrinsic size from SvgSizeProvider (fixes sizing bug!)
- Applies `:SCALE:` parameter multiplicatively
- Clips overflow with `block(clip: true)`

**Key Fix**: Previously used frame size as fallback, causing incorrect scaling. Now uses actual SVG viewBox dimensions.

#### PdfRenderStrategy
Handles PDF documents.

**Simple Path**:
- No alignment: uses `PdfEmbed()` macro
- With caption but no alignment: uses `Fig()` with 100% sizing

**Manual Path**:
- Cover mode with caption: reduces frame height for caption space
- With alignment: positions PDF within frame
- Supports `:PAGE:` parameter for multi-page PDFs

---

## Layer 3: Factory & Orchestration

**Module**: `src/pagemaker/generation/core.py` (lines 1022-1069)

### Factory Function

```python
def get_media_renderer(element_type: str) -> MediaRenderStrategy:
    """Get appropriate strategy for element type.
    
    Args:
        element_type: One of 'figure', 'svg', 'pdf'
    
    Returns:
        Strategy instance with providers injected
        
    Raises:
        ValueError: If element_type is unknown
    """
```

### Usage in Core

```python
# Old code (160 lines of if/elif branches):
if el_type == 'figure':
    # ... 50+ lines of figure logic
elif el_type == 'svg':
    # ... 50+ lines of SVG logic
elif el_type == 'pdf':
    # ... 50+ lines of PDF logic

# New code (~10 lines):
strategy = get_media_renderer(el_type)
ctx = RenderContext(
    element=el,
    frame_w_mm=frame_w_mm,
    frame_h_mm=frame_h_mm,
    align=align,
    valign=valign
)
result = strategy.render(ctx)
```

---

## Fit Modes Explained

All three fit modes work consistently across media types:

### Contain (Default)
- **Behavior**: Scale media to fit entirely within frame
- **Aspect Ratio**: Preserved
- **Clipping**: Never needed
- **Formula**: `scale = min(frame_w / intrinsic_w, frame_h / intrinsic_h)`
- **Use Case**: Document pages, diagrams with margins

**Example**: 200mm × 300mm image in 100mm × 100mm frame → scales to 66.67mm × 100mm

### Cover
- **Behavior**: Scale media to completely fill frame (crops excess)
- **Aspect Ratio**: Preserved
- **Clipping**: Required for overflow
- **Formula**: `scale = max(frame_w / intrinsic_w, frame_h / intrinsic_h)`
- **Use Case**: Hero images, backgrounds, full-bleed graphics

**Example**: 200mm × 300mm image in 100mm × 100mm frame → scales to 100mm × 150mm (50mm clipped)

### Stretch
- **Behavior**: Scale independently per axis to fill frame exactly
- **Aspect Ratio**: **NOT** preserved (may distort)
- **Clipping**: Never needed
- **Formula**: `scale_x = frame_w / intrinsic_w`, `scale_y = frame_h / intrinsic_h`
- **Use Case**: Decorative elements, technical drawings where distortion acceptable

**Example**: 200mm × 300mm image in 100mm × 100mm frame → scales to 100mm × 100mm (distorted)

---

## Alignment & Cropping

When using **cover mode**, alignment determines which part of the media is visible:

### Horizontal Alignment
- `left`: Shows left edge, crops right side
- `center`: Shows center, crops both sides equally (default)
- `right`: Shows right edge, crops left side

### Vertical Alignment
- `top`: Shows top edge, crops bottom
- `middle`: Shows middle, crops top and bottom equally (default)
- `bottom`: Shows bottom edge, crops top

### Implementation

Alignment is implemented via Typst `place()` offsets:

```typst
# Center-aligned cover: center the oversized content
place(dx: -24.5mm, dy: -24.5mm, image(...))

# Left-aligned cover: no x offset (left edge at origin)
place(dy: -24.5mm, image(...))

# Right-aligned cover: negative offset shows right edge
place(dx: -49mm, dy: -24.5mm, image(...))
```

---

## Caption Handling

Captions are rendered using the `Fig()` Typst helper:

```typst
#let Fig(img, caption: none, caption_align: left, img_align: left, 
         caption_valign: top, img_valign: top, fill_space: true) = {
  if caption == none {
    block(width: 100%, height: 100%)[#align(img_alignment)[#img]]
  } else {
    block(width: 100%, height: 100%)[
      #grid(
        columns: (100%),
        rows: (1fr, auto),
        row-gutter: 0.3em,
        if fill_space {
          block(width: 100%, height: 100%)[#align(img_alignment)[#img]]
        } else {
          align(img_alignment)[#img]
        },
        align(caption_align)[#text(size: 0.75em, fill: rgb(60%,60%,60%))[#caption]]
      )
    ]
  }
}
```

### Cover Mode with Captions

**Challenge**: Cover mode creates oversized content that fills the entire frame. With captions, we need to reserve vertical space.

**Solution**: Reduce frame height by estimated caption height (5mm) before computing cover layout:

```python
if caption and fit == 'cover':
    caption_height_mm = 5.0  # 0.75em text + 0.3em gutter + buffer
    adjusted_frame_h_mm = frame_h_mm - caption_height_mm
    # Recompute layout with adjusted frame
    drawn_w_mm, drawn_h_mm, offset_x_mm, offset_y_mm, needs_clip = (
        _compute_media_drawn_and_offsets(
            intrinsic_w_mm, intrinsic_h_mm, frame_w_mm, adjusted_frame_h_mm, fit
        )
    )
```

This ensures the clipping block has reduced height, leaving physical space for the caption.

---

## Cover Mode Implementation Details

### The `_compute_media_drawn_and_offsets()` Function

Cover mode is implemented through a core function in `generator.py` that computes scaling, positioning, and clipping requirements:

```python
def _compute_media_drawn_and_offsets(
    intrinsic_w: float,
    intrinsic_h: float, 
    frame_w: float,
    frame_h: float,
    fit: str,
    align: Optional[str] = None,
    valign: Optional[str] = None
) -> Tuple[float, float, float, float, bool]:
    """
    Compute drawn dimensions and positioning offsets for media rendering.
    
    Args:
        intrinsic_w, intrinsic_h: Media's intrinsic dimensions (mm)
        frame_w, frame_h: Available frame dimensions (mm)
        fit: 'contain', 'cover', or 'stretch'
        align: 'left', 'center', 'right' (optional)
        valign: 'top', 'horizon', 'bottom' (optional)
        
    Returns:
        (drawn_w, drawn_h, offset_x, offset_y, needs_clip)
    """
```

**Key Implementation:**

1. **Scaling Calculation**:
   - `contain`: `scale = min(frame_w/intrinsic_w, frame_h/intrinsic_h)`
   - `cover`: `scale = max(frame_w/intrinsic_w, frame_h/intrinsic_h)`
   - `stretch`: `scale_x = frame_w/intrinsic_w`, `scale_y = frame_h/intrinsic_h`

2. **Overflow Detection**:
   - Check if `drawn_w > frame_w` or `drawn_h > frame_h`
   - Set `needs_clip = True` when overflow detected

3. **Offset Calculation** (alignment-based):
   - **Horizontal** (`:ALIGN:`):
     - `left`: `offset_x = 0` (left edge at origin)
     - `center`: `offset_x = -(drawn_w - frame_w) / 2` (center visible)
     - `right`: `offset_x = -(drawn_w - frame_w)` (right edge visible)
   - **Vertical** (`:VALIGN:`):
     - `top`: `offset_y = 0` (top edge at origin)
     - `horizon`/`middle`: `offset_y = -(drawn_h - frame_h) / 2` (center visible)
     - `bottom`: `offset_y = -(drawn_h - frame_h)` (bottom edge visible)

### Strategy Integration

Each media strategy (`FigureRenderStrategy`, `SvgRenderStrategy`, `PdfRenderStrategy`) calls this function and uses the results:

```python
# In media_renderer.py strategies
drawn_w_mm, drawn_h_mm, offset_x_mm, offset_y_mm, needs_clip = (
    _compute_media_drawn_and_offsets(
        intrinsic_w_mm, intrinsic_h_mm,
        frame_w_mm, frame_h_mm, 
        fit,
        align=ctx.element.get('figure', {}).get('align'),
        valign=ctx.element.get('figure', {}).get('valign')
    )
)

if needs_clip:
    # Generate clipped output
    code = f'block(clip: true, width: {frame_w_mm}mm, height: {frame_h_mm}mm)['
    code += f'  place(dx: {offset_x_mm}mm, dy: {offset_y_mm}mm)['
    code += f'    image("{src}", width: {drawn_w_mm}mm, height: {drawn_h_mm}mm)'
    code += '  ]'
    code += ']'
else:
    # No clipping needed (contain mode or exact fit)
    code = f'place(dx: {offset_x_mm}mm, dy: {offset_y_mm}mm)['
    code += f'  image("{src}", width: {drawn_w_mm}mm, height: {drawn_h_mm}mm)'
    code += ']'
```

### Manual vs Simple Path Decision

All three strategies use the **manual rendering path** when cover mode is active or when alignment is specified:

- **Figure Strategy**: Always uses manual path with explicit dimensions for cover mode
- **SVG Strategy**: Uses manual path for cover mode (simple path for contain without alignment)
- **PDF Strategy**: Uses manual path for all modes when alignment is specified

This ensures consistent clipping behavior across all media types.

### Visual Example

For a 200mm × 100mm landscape image in a 100mm × 100mm square frame with `:FIT: cover` and `:ALIGN: left`:

1. **Scale**: `max(100/200, 100/100) = 1.0` → drawn: 200mm × 100mm
2. **Overflow**: Width 200mm > frame 100mm → `needs_clip = True`, overflow = 100mm
3. **Offset**: `:ALIGN: left` → `offset_x = 0` (show left edge, crop right)
4. **Result**: Left 100mm visible, right 100mm cropped

**Typst Output**:
```typst
block(clip: true, width: 100mm, height: 100mm)[
  place(dx: 0mm, dy: 0mm)[
    image("landscape.jpg", width: 200mm, height: 100mm)
  ]
]
```

---

## How to Add New Media Types

Follow these steps to add support for a new media type (e.g., video):

### Step 1: Create Size Provider

```python
# In media_sizing.py
class VideoSizeProvider(IntrinsicSizeProvider):
    """Provider for video frame dimensions."""
    
    def get_size_mm(self, src: str, **kwargs) -> Optional[Tuple[float, float]]:
        """Extract video resolution and convert to mm."""
        try:
            # Use ffprobe or similar to get resolution
            width_px, height_px = get_video_resolution(src)
            # Assume 96 DPI for screen media
            width_mm = width_px / 96 * 25.4
            height_mm = height_px / 96 * 25.4
            return (width_mm, height_mm)
        except Exception as e:
            warnings.warn(f"Could not determine video size for '{src}': {e}")
            return None
```

### Step 2: Create Render Strategy

```python
# In media_renderer.py
class VideoRenderStrategy(MediaRenderStrategy):
    """Strategy for rendering video embeds."""
    
    def __init__(self, size_provider: VideoSizeProvider):
        self.size_provider = size_provider
    
    def can_use_simple_path(self, ctx: RenderContext) -> bool:
        # Video might not have simple Typst support
        return False
    
    def render_simple(self, ctx: RenderContext) -> RenderedMedia:
        raise NotImplementedError("Video requires manual rendering")
    
    def render_manual(self, ctx: RenderContext) -> RenderedMedia:
        src = ctx.element.get('video', {}).get('src')
        intrinsic = self.size_provider.get_size_mm(src)
        
        # Generate poster frame or placeholder
        code = f'image("{src}.poster.png", width: {ctx.frame_w_mm}mm, ...)'
        return RenderedMedia(code, needs_wrapper=True)
```

### Step 3: Update Factory

```python
# In media_renderer.py
def get_media_renderer(element_type: str) -> MediaRenderStrategy:
    if element_type == 'figure':
        return FigureRenderStrategy(RasterSizeProvider())
    elif element_type == 'svg':
        return SvgRenderStrategy(SvgSizeProvider())
    elif element_type == 'pdf':
        return PdfRenderStrategy(PdfSizeProvider())
    elif element_type == 'video':  # NEW
        return VideoRenderStrategy(VideoSizeProvider())
    else:
        raise ValueError(f"Unknown media type: {element_type}")
```

### Step 4: Update Parser

```python
# In parser.py
if elem_type == 'video':  # NEW
    video_ir = {
        'src': props.get(':SRC:', ''),
        'fit': props.get(':FIT:', 'contain'),
        # ... other properties
    }
    el['video'] = video_ir
```

### Step 5: Add Tests

```python
# In tests/unit/test_media_renderer_strategies.py
class TestVideoStrategy:
    def test_render_with_poster(self):
        strategy = VideoRenderStrategy(VideoSizeProvider())
        ctx = RenderContext(...)
        result = strategy.render(ctx)
        assert 'poster.png' in result.typst_code
```

---

## Testing Strategy

### Unit Tests

**Size Providers** (`tests/unit/test_media_sizing_providers.py`, 32 tests):
- Valid file formats
- Unit conversions (px/pt/cm/mm/in → mm)
- Malformed files (graceful failure)
- Missing files (return None)
- Edge cases (zero dimensions, negative viewBox)

**Render Strategies** (`tests/unit/test_media_renderer_strategies.py`, 20 tests):
- Simple path selection logic
- Cover/contain/stretch output correctness
- Alignment offset calculations
- Caption rendering with/without alignment
- Clipping block generation

### Integration Tests

**End-to-End Compilation** (`tests/integration/`):
- Compile actual org files to PDF
- Verify Typst output structure
- Visual regression testing (manual review)
- Test all fit modes with real assets

### Test Coverage

- **media_sizing.py**: 100% coverage (32 tests)
- **media_renderer.py**: 100% coverage (20 tests)
- **Full suite**: 231 tests passing, 0 failing

---

## Performance Considerations

### Size Provider Caching

Size detection is called once per render pass per asset. For documents with repeated assets, consider caching at the generator level:

```python
# Not currently implemented, but possible future optimization
_size_cache = {}

def get_cached_size(provider, src):
    if src not in _size_cache:
        _size_cache[src] = provider.get_size_mm(src)
    return _size_cache[src]
```

### Strategy Instance Reuse

The factory creates new strategy instances per call. For high-volume rendering, consider singleton pattern:

```python
_strategy_cache = {}

def get_media_renderer(element_type: str) -> MediaRenderStrategy:
    if element_type not in _strategy_cache:
        _strategy_cache[element_type] = _create_strategy(element_type)
    return _strategy_cache[element_type]
```

### Measured Overhead

Current implementation adds <5% overhead compared to direct if/elif branching. This is acceptable given the code maintainability improvements.

---

## Common Pitfalls & Solutions

### Pitfall 1: Frame Size vs Intrinsic Size
**Problem**: Using frame dimensions as fallback for intrinsic size causes incorrect aspect ratios.

**Solution**: Always return `None` from providers when size cannot be determined. Let strategies handle fallback behavior explicitly.

### Pitfall 2: Caption Space Estimation
**Problem**: Fixed 5mm caption space may be too much/little for varying font sizes.

**Solution**: Current approach is pragmatic. For precision, would need Typst layout query capabilities (not currently exposed).

### Pitfall 3: Clipping Overflow
**Problem**: Forgetting `clip: true` on block causes content to overflow visibly.

**Solution**: Always use `block(clip: true)` wrapper when `needs_clip == True` from compute function.

### Pitfall 4: Alignment Without Intrinsic Size
**Problem**: Cannot compute offsets without knowing media dimensions.

**Solution**: Strategies should fall back to centered no-clip rendering when provider returns `None`.

---

## Future Enhancements

### Potential Improvements

1. **Dynamic Caption Sizing**: Query Typst for actual caption height instead of estimating
2. **Size Provider Caching**: Memoize intrinsic size detection per render pass
3. **Strategy Registry**: Plugin-based system for third-party media types
4. **Lazy Loading**: Defer provider instantiation until first use
5. **Validation Layer**: Pre-render checks for missing assets, invalid fit modes
6. **Performance Profiling**: Track time spent in each strategy per document

### Backward Compatibility

The new architecture maintains 100% backward compatibility:
- All existing org-mode documents render identically
- No breaking changes to `:PROPERTIES:` syntax
- Legacy `:PDF:` and `:SVG:` still supported (with deprecation warnings)
- Zero test regressions (231/231 passing)

---

## References

### Key Code Locations
- `src/pagemaker/generation/media_sizing.py` (355 lines) - Size providers
- `src/pagemaker/generation/media_renderer.py` (800+ lines) - Render strategies
- `src/pagemaker/generation/core.py` (lines 1022-1069) - Factory integration
- `src/pagemaker/generator.py` (lines 850-900) - Layout math functions

### Related Documentation
- [Master Styles Guide](../master_styles.md) - Element property syntax
- [Update Plan](../update_plan.md) - Development roadmap
- [README](../../README.md) - User-facing documentation

### External Resources
- [Typst Documentation](https://typst.app/docs) - Typst language reference
- [SVG Specification](https://www.w3.org/TR/SVG2/) - SVG viewBox and units
- [PDF Reference](https://www.adobe.com/content/dam/acom/en/devnet/pdf/pdfs/PDF32000_2008.pdf) - PDF box types

---

**Document Version**: 1.0  
**Reviewed By**: Development Team  
**Last Updated**: 2025-11-09
