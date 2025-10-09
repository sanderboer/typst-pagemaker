# Styles and Master Pages

This guide explains how text styles and master pages work in pagemaker, and how they interact with the grid, margins, and element rendering.

## Overview

- Styles: Define reusable typography and paragraph settings you can reference per element via `:STYLE:`.
- Master pages: Define reusable element sets (e.g., headers, footers, backgrounds) that are not rendered by themselves but applied to other pages.
- Grid semantics: `:AREA:` always addresses the total grid. With margins declared, the total grid includes a margin track on each side.

## Styles

### Declaring styles

Declare styles in document meta using `#+STYLE_<NAME>:`. Names are case-insensitive and are stored in lowercase.

Built-in defaults exist for `header`, `subheader`, and `body`:
- `header`: Inter, weight bold, size 24pt
- `subheader`: Inter, weight semibold, size 18pt
- `body`: Inter

Example:

```org
#+STYLE_HEADER: font: Inter, weight: bold, size: 30pt, color: #222
#+STYLE_BODY: font: Inter, color: rgb(50%,50%,50%), spacing: 0.8em
#+STYLE_HERO: font: Playfair Display, weight: 700, size: 36pt, color: #123456
```

Supported keys (case-insensitive; aliases in parentheses):
- font (font-family)
- weight (font-weight) — numeric (100..900) or names (thin..black)
- size (font-size) — Typst length (e.g., `pt`, `em`)
- color (fill, colour) — `#hex`, `rgb(...)`, `hsl(...)`, or named
- Paragraph options applied via Typst `par(...)`:
  - `leading`
  - `spacing`
  - `first-line-indent` (first_line_indent)
  - `hanging-indent` (hanging_indent)
  - `linebreaks` — tokens: `auto`, `loose`, `strict`
  - `justify` — boolean or token expression

Notes:
- A global `#+FONT:` meta overrides the default font for built-in styles unless explicitly set in a style.
- Commas inside parentheses or quotes are supported (e.g., `rgb(50%,50%,50%)`).

### Using styles on elements

Elements default to a style matching their type (`header`, `subheader`, `body`). You can override with `:STYLE:`:

```org
** Big Title
:PROPERTIES:
:TYPE: body
:STYLE: hero
:AREA: A1,L2
:END:
Big Title
```

Element-level `:JUSTIFY:` overrides the style’s `justify` field when provided. Paragraphs are split on blank lines or lines exactly `---`/`:::`; each paragraph gets a `par(...)` wrapper when any paragraph options apply or when there are multiple paragraphs. Single paragraphs without paragraph options render as plain `#text[...]` for compactness.

### Fonts

Fonts are discovered from:
1) Project fonts: `assets/fonts/`
2) Bundled fonts: Inter, Crimson Pro, JetBrains Mono
3) System fonts (via Typst)

The generator validates that fonts referenced in styles exist and emits warnings if not found. Use the CLI (`pagemaker fonts ...`) to inspect and install fonts.

## Master Pages

Master pages let you define reusable element sets and apply them to multiple slides. The page that defines them is not rendered; its elements are merged into each referenced slide at generation time.

### Defining a master page

Create a top-level page that marks itself as a master definition:

```org
#+DEFAULT_MASTER: Base

* Base Master (not rendered)
:PROPERTIES:
:MASTER_DEF: Base
:END:

** Header Bar
:PROPERTIES:
:TYPE: rectangle
:AREA: A1,A12
:COLOR: #000
:ALPHA: 0.08
:END:

** Footer Text
:PROPERTIES:
:TYPE: body
:AREA: H11,H12
:END:
Page #page_no / #page_total — #date_dd_mm_yy
```

- Any page with `:MASTER_DEF: Name` is treated as a master definition and is skipped during rendering.
- Its elements are stored under the master name.
- `#+DEFAULT_MASTER:` sets the fallback master name for pages that don’t explicitly set `:MASTER:`.

### Using a master page

On each rendered slide (a page without `:MASTER_DEF:`), master elements are merged before rendering. Pages can:
- Inherit the default master via `#+DEFAULT_MASTER:`; or
- Select a master explicitly via a page property `:MASTER:`.

```org
* Slide One
:PROPERTIES:
:ID: s1
:END:

** Title
:PROPERTIES:
:TYPE: header
:AREA: B2,C11
:END:
Slide Title

* Slide Two
:PROPERTIES:
:ID: s2
:MASTER: Base
:END:

** Body
:PROPERTIES:
:TYPE: body
:AREA: D2,G11
:END:
Body Text
```

Behavior:
- The master-def page is not rendered.
- Slides receive the master elements plus their own elements.
- Elements are z-ordered together by `:Z:` value during placement.

## Grid, AREA, and Margins

- `:AREA:` always addresses the total grid. With margins declared (`#+MARGINS: top,right,bottom,left`), the total grid has an extra track on each side representing the absolute margin sizes.
- Without margins, total grid equals the content grid. With margins, a content cell’s physical size is computed from page size minus absolute margins.
- Debug overlays (`#+GRID_DEBUG: true`) draw the total grid when margins are present and the content grid when not.

Examples:

- No margins, `#+GRID: 6x6`:
  - `A1` -> `(x=1,y=1,w=1,h=1)`; `A2` -> `(x=2,y=1,...)`.
- With margins, `#+GRID: 3x3`, `#+MARGINS: 5,0,0,5`:
  - `A1` still maps to total `(1,1)`; the generator uses variable-track helpers to account for margin tracks when placing elements.

## Padding and Alignment

- `:PADDING:` uses CSS TRBL shorthand (mm). It applies to text, figure, svg, pdf, rectangle, and toc elements.
- Padding inheritance is cumulative: document meta `#+PADDING:` → page `:PADDING:` → ancestors’ `:PADDING:` → element `:PADDING:`. Negative values subtract. Zero-sum values are preserved as `0,0,0,0` and still result in padded placement calls in the generator.
- When `padding_mm` exists (even all zeros), the generator emits `#layer_grid_padded(...)` with the provided top/right/bottom/left values.
- `:ALIGN:` (left|center|right) applies to text, figure, svg, pdf, toc. `:VALIGN:` (top|middle|bottom) applies to text. If `:VALIGN:` is not set for text, `:FLOW:` can imply a vertical alignment (`bottom-up` → bottom, `center-out` → horizon).

## Rectangle Styles

Rectangle elements support additional style properties, either inline via element properties (`:COLOR:`, `:ALPHA:`, `:STROKE:`, `:STROKE_COLOR:`, `:RADIUS:`) or inherited from a referenced style (e.g. `#+STYLE_CALLOUT:`).

Supported rectangle style keys:
- color: fill color. Accepts `#hex`, `rgb(...)`, `hsl(...)`, named colors.
- alpha: 0.0–1.0; values outside range or non-numeric are clamped/defaulted at generation (warning issued during validation).
- stroke: length with unit (`pt|mm|cm|in`). Required unit; invalid or missing unit is an error.
- stroke_color (stroke-color): stroke color; if omitted but stroke present, the fill color is used as fallback silently.
- radius: corner radius length with unit (`pt|mm|cm|in`). Invalid or missing unit is an error.

Precedence & merging:
1. Style-level rectangle keys (if style referenced by element)
2. Element-level rectangle dict overrides style keys
3. Defaults: `color` defaults to `#3498db`, `alpha` defaults to `1.0` when unspecified or invalid.

Generation details:
- Output helper signature: `ColorRect(color, alpha, stroke: none|"<len>", stroke_color: none|"<color>", radius: none|"<len>")`.
- When only radius is provided (no stroke), generator still emits `stroke: none, stroke_color: none` to pass the radius.
- Alpha is applied through a transparentize call in Typst: `rgb(color).transparentize(100% - alpha*100%)`.

Validation behaviors:
- Out-of-range or non-numeric alpha: warning; generation clamps to 0.0 or 1.0 (non-numeric → 1.0).
- Invalid stroke or radius units: error (validation `ok()` becomes False).
- Stroke color format heuristic: warns if not hex/rgb()/hsl(); still emitted unchanged.

Examples:
```
#+STYLE_CALLOUT: color: #225588, alpha: 0.5, stroke: 1pt, stroke-color: #113344, radius: 3pt

** Callout Block
:PROPERTIES:
:TYPE: rectangle
:STYLE: callout
:AREA: A1,C4
:END:
```

Inline override example:
```
** Framed Panel
:PROPERTIES:
:TYPE: rectangle
:AREA: A5,C8
:COLOR: #ffeeaa
:ALPHA: 1.2    ; will clamp to 1.0 (warn)
:STROKE: 2pt
:RADIUS: 5mm
:END:
```

## Validation and Rendering Notes

- Per-page `PAGESIZE`/`ORIENTATION` overrides are ignored in Typst output; a single page size is set at the top of the document based on the first rendered page.
- AREA bounds are validated against the total grid when margins are present; otherwise against the content grid. Out-of-bounds areas emit a stderr warning during generation.
- Master pages combine elements by z-order, and their elements behave identically to normal page elements (padding, alignment, styles apply).

## Tips

- Use master pages for repeated structure: background rectangles, page headers/footers, watermarks.
- Keep master elements’ `:Z:` lower for background artwork (e.g., `-1`) and higher for foreground headers if needed.
- Prefer styles for typography consistency; adjust element-level properties sparingly.
- If you reference fonts outside the bundled set, run `pagemaker fonts validate "Family"` to confirm availability and avoid compile-time font substitutions.
