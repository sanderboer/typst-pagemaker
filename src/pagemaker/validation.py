import os
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ValidationIssue:
    path: str
    message: str
    severity: str = "error"  # 'error' | 'warn'


@dataclass
class ValidationResult:
    issues: List[ValidationIssue]

    def ok(self) -> bool:
        return all(i.severity != 'error' for i in self.issues)


REQUIRED_PAGE_KEYS = ["id", "title", "page_size", "grid", "elements"]


def validate_ir(ir: Dict[str, Any], strict_assets: bool = False) -> ValidationResult:
    """Validate the intermediate representation.

    strict_assets: when True missing figure/pdf assets are upgraded from warn to error.
    """
    issues: List[ValidationIssue] = []
    if not isinstance(ir, dict):
        return ValidationResult([ValidationIssue(path="/", message="IR root not a dict")])
    pages = ir.get("pages")
    seen_page_ids = set()
    seen_element_ids = set()
    render_pages: List[Dict[str, Any]] = []
    if pages is None:
        issues.append(ValidationIssue(path="/pages", message="Missing pages array"))
    elif not isinstance(pages, list) or len(pages) == 0:
        issues.append(ValidationIssue(path="/pages", message="Pages empty or not a list"))
    else:
        for idx, page in enumerate(pages):
            ppath = f"/pages/{idx}"
            if not isinstance(page, dict):
                issues.append(ValidationIssue(path=ppath, message="Page not an object"))
                continue
            for k in REQUIRED_PAGE_KEYS:
                if k not in page:
                    issues.append(
                        ValidationIssue(path=f"{ppath}/{k}", message="Missing required page key")
                    )
            pid = page.get('id')
            if isinstance(pid, str):
                if pid in seen_page_ids:
                    issues.append(
                        ValidationIssue(path=f"{ppath}/id", message=f"Duplicate page id '{pid}'")
                    )
                else:
                    seen_page_ids.add(pid)
            # Track render pages (exclude master definitions)
            if not str(page.get('master_def', '') or '').strip():
                render_pages.append(page)
            # Warn when per-page overrides are present but ignored
            ignored = page.get('ignored_overrides')
            if isinstance(ignored, list) and ignored:
                issues.append(
                    ValidationIssue(
                        path=f"{ppath}/ignored_overrides",
                        message=f"Per-page overrides ignored: {', '.join(ignored)}",
                        severity='warn',
                    )
                )
            els = page.get("elements", [])
            if not isinstance(els, list):
                issues.append(
                    ValidationIssue(path=f"{ppath}/elements", message="Elements not a list")
                )
                continue
            grid = page.get('grid') or {}
            cols = grid.get('cols')
            rows = grid.get('rows')
            for eidx, el in enumerate(els):
                epath = f"{ppath}/elements/{eidx}"
                if not isinstance(el, dict):
                    issues.append(ValidationIssue(path=epath, message="Element not an object"))
                    continue
                eid = el.get('id')
                if isinstance(eid, str):
                    if eid in seen_element_ids:
                        issues.append(
                            ValidationIssue(
                                path=f"{epath}/id", message=f"Duplicate element id '{eid}'"
                            )
                        )
                    else:
                        seen_element_ids.add(eid)
                if 'type' not in el:
                    issues.append(ValidationIssue(path=epath, message="Element missing type"))
                else:
                    et = el['type']
                    if et not in (
                        "header",
                        "subheader",
                        "body",
                        "figure",
                        "pdf",
                        "rectangle",
                        "svg",
                        "toc",
                    ):
                        issues.append(
                            ValidationIssue(
                                path=epath, message=f"Unknown element type '{et}'", severity='warn'
                            )
                        )
                # Figure asset
                if el.get('type') == 'figure':
                    fig = el.get('figure')
                    if not fig or not fig.get('src'):
                        issues.append(
                            ValidationIssue(
                                path=f"{epath}/figure", message="Figure element missing src"
                            )
                        )
                    else:
                        src = fig.get('src')
                        if src and not os.path.isabs(src) and not os.path.exists(src):
                            sev = 'error' if strict_assets else 'warn'
                            issues.append(
                                ValidationIssue(
                                    path=f"{epath}/figure/src",
                                    message="Figure asset not found",
                                    severity=sev,
                                )
                            )
                # PDF asset
                if el.get('type') == 'pdf':
                    pdf = el.get('pdf')
                    if not pdf or not pdf.get('src'):
                        issues.append(
                            ValidationIssue(path=f"{epath}/pdf", message="PDF element missing src")
                        )
                    else:
                        psrc = pdf.get('src')
                        if psrc and not os.path.isabs(psrc) and not os.path.exists(psrc):
                            sev = 'error' if strict_assets else 'warn'
                            issues.append(
                                ValidationIssue(
                                    path=f"{epath}/pdf/src",
                                    message="PDF asset not found",
                                    severity=sev,
                                )
                            )
                        # Enforce positive PDF scale when provided
                        scale = pdf.get('scale')
                        if scale is not None:
                            if not isinstance(scale, (int, float)):
                                issues.append(
                                    ValidationIssue(
                                        path=f"{epath}/pdf/scale",
                                        message="PDF scale must be a number",
                                    )
                                )
                            else:
                                if scale <= 0:
                                    issues.append(
                                        ValidationIssue(
                                            path=f"{epath}/pdf/scale",
                                            message="PDF scale must be > 0",
                                        )
                                    )
                # SVG asset
                if el.get('type') == 'svg':
                    svg = el.get('svg')
                    if not svg or not svg.get('src'):
                        issues.append(
                            ValidationIssue(path=f"{epath}/svg", message="SVG element missing src")
                        )
                    else:
                        ssrc = svg.get('src')
                        if ssrc and not os.path.isabs(ssrc) and not os.path.exists(ssrc):
                            sev = 'error' if strict_assets else 'warn'
                            issues.append(
                                ValidationIssue(
                                    path=f"{epath}/svg/src",
                                    message="SVG asset not found",
                                    severity=sev,
                                )
                            )
                # Rectangle alpha
                if el.get('type') == 'rectangle':
                    rect = el.get('rectangle') or {}
                    alpha = rect.get('alpha')
                    if isinstance(alpha, (int, float)):
                        if alpha < 0.0 or alpha > 1.0:
                            issues.append(
                                ValidationIssue(
                                    path=f"{epath}/rectangle/alpha",
                                    message="Alpha out of range 0.0-1.0",
                                )
                            )
                # Deprecation warning: element-level MARGIN was declared
                if el.get('had_margin_decl') is True:
                    issues.append(
                        ValidationIssue(
                            path=f"{epath}",
                            message="Element-level MARGIN is deprecated; use PADDING instead",
                            severity='warn',
                        )
                    )
                # Legacy IR support: margin_mm present on element
                if isinstance(el.get('margin_mm'), dict):
                    issues.append(
                        ValidationIssue(
                            path=f"{epath}/margin_mm",
                            message="Legacy margin_mm detected on element; element-level margins are deprecated",
                            severity='warn',
                        )
                    )
                # Area bounds: AREA is interpreted in the total grid.
                # When margins are declared, validate against grid_total; otherwise, use content grid.
                area = el.get('area')
                if isinstance(area, dict) and isinstance(cols, int) and isinstance(rows, int):
                    x = area.get('x')
                    y = area.get('y')
                    w = area.get('w')
                    h = area.get('h')
                    if all(isinstance(v, int) for v in (x, y, w, h)):
                        if x < 1 or y < 1 or w < 1 or h < 1:
                            issues.append(
                                ValidationIssue(
                                    path=f"{epath}/area", message="Area has non-positive values"
                                )
                            )
                        else:
                            margins_declared = bool(page.get('margins_declared'))
                            if margins_declared:
                                gt = page.get('grid_total') or {}
                                tcols_val = gt.get('cols')
                                trows_val = gt.get('rows')
                                tcols = tcols_val if isinstance(tcols_val, int) else cols
                                trows = trows_val if isinstance(trows_val, int) else rows
                                if x + w - 1 > tcols or y + h - 1 > trows:
                                    issues.append(
                                        ValidationIssue(
                                            path=f"{epath}/area",
                                            message="Area exceeds total-grid bounds",
                                        )
                                    )
                            else:
                                if x + w - 1 > cols or y + h - 1 > rows:
                                    issues.append(
                                        ValidationIssue(
                                            path=f"{epath}/area", message="Area exceeds grid bounds"
                                        )
                                    )
        # Enforce uniform page size across render pages (Typst limitation)
        first_render = None
        first_idx = -1
        for i, rp in enumerate(render_pages):
            ps = rp.get('page_size') or {}
            w = ps.get('w_mm')
            h = ps.get('h_mm')
            if isinstance(w, (int, float)) and isinstance(h, (int, float)):
                first_render = (w, h)
                first_idx = i
                break
        if first_render is not None:
            fw, fh = first_render
            for j, rp in enumerate(render_pages):
                ps = rp.get('page_size') or {}
                w = ps.get('w_mm')
                h = ps.get('h_mm')
                if not (isinstance(w, (int, float)) and isinstance(h, (int, float))):
                    continue
                if (w, h) != (fw, fh):
                    # Map back to absolute page index for precise path when possible
                    try:
                        abs_idx = pages.index(rp)
                    except Exception:
                        abs_idx = j
                    issues.append(
                        ValidationIssue(
                            path=f"/pages/{abs_idx}/page_size",
                            message=f"Uniform page size required: page differs from first render page ({fw}x{fh}mm)",
                        )
                    )
    return ValidationResult(issues)
