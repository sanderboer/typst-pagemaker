from dataclasses import dataclass
from typing import List, Any, Dict
import os

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
                    issues.append(ValidationIssue(path=f"{ppath}/{k}", message="Missing required page key"))
            pid = page.get('id')
            if isinstance(pid, str):
                if pid in seen_page_ids:
                    issues.append(ValidationIssue(path=f"{ppath}/id", message=f"Duplicate page id '{pid}'"))
                else:
                    seen_page_ids.add(pid)
            els = page.get("elements", [])
            if not isinstance(els, list):
                issues.append(ValidationIssue(path=f"{ppath}/elements", message="Elements not a list"))
                continue
            grid = page.get('grid') or {}
            cols = grid.get('cols'); rows = grid.get('rows')
            for eidx, el in enumerate(els):
                epath = f"{ppath}/elements/{eidx}"
                if not isinstance(el, dict):
                    issues.append(ValidationIssue(path=epath, message="Element not an object"))
                    continue
                eid = el.get('id')
                if isinstance(eid, str):
                    if eid in seen_element_ids:
                        issues.append(ValidationIssue(path=f"{epath}/id", message=f"Duplicate element id '{eid}'"))
                    else:
                        seen_element_ids.add(eid)
                if 'type' not in el:
                    issues.append(ValidationIssue(path=epath, message="Element missing type"))
                else:
                    et = el['type']
                    if et not in ("header","subheader","body","figure","pdf","rectangle","svg","toc"):
                        issues.append(ValidationIssue(path=epath, message=f"Unknown element type '{et}'", severity='warn'))
                # Figure asset
                if el.get('type') == 'figure':
                    fig = el.get('figure')
                    if not fig or not fig.get('src'):
                        issues.append(ValidationIssue(path=f"{epath}/figure", message="Figure element missing src"))
                    else:
                        src = fig.get('src')
                        if src and not os.path.isabs(src) and not os.path.exists(src):
                            sev = 'error' if strict_assets else 'warn'
                            issues.append(ValidationIssue(path=f"{epath}/figure/src", message="Figure asset not found", severity=sev))
                # PDF asset
                if el.get('type') == 'pdf':
                    pdf = el.get('pdf')
                    if not pdf or not pdf.get('src'):
                        issues.append(ValidationIssue(path=f"{epath}/pdf", message="PDF element missing src"))
                    else:
                        psrc = pdf.get('src')
                        if psrc and not os.path.isabs(psrc) and not os.path.exists(psrc):
                            sev = 'error' if strict_assets else 'warn'
                            issues.append(ValidationIssue(path=f"{epath}/pdf/src", message="PDF asset not found", severity=sev))
                # SVG asset
                if el.get('type') == 'svg':
                    svg = el.get('svg')
                    if not svg or not svg.get('src'):
                        issues.append(ValidationIssue(path=f"{epath}/svg", message="SVG element missing src"))
                    else:
                        ssrc = svg.get('src')
                        if ssrc and not os.path.isabs(ssrc) and not os.path.exists(ssrc):
                            sev = 'error' if strict_assets else 'warn'
                            issues.append(ValidationIssue(path=f"{epath}/svg/src", message="SVG asset not found", severity=sev))
                # Rectangle alpha
                if el.get('type') == 'rectangle':
                    rect = el.get('rectangle') or {}
                    alpha = rect.get('alpha')
                    if isinstance(alpha, (int,float)):
                        if alpha < 0.0 or alpha > 1.0:
                            issues.append(ValidationIssue(path=f"{epath}/rectangle/alpha", message="Alpha out of range 0.0-1.0"))
                # Area bounds (respect COORDS: content|total)
                area = el.get('area')
                if isinstance(area, dict) and isinstance(cols, int) and isinstance(rows, int):
                    x = area.get('x'); y = area.get('y'); w = area.get('w'); h = area.get('h')
                    if all(isinstance(v, int) for v in (x, y, w, h)):
                        if x < 1 or y < 1 or w < 1 or h < 1:
                            issues.append(ValidationIssue(path=f"{epath}/area", message="Area has non-positive values"))
                        else:
                            coords_mode = (el.get('coords') or 'content').strip().lower()
                            if coords_mode == 'total':
                                gt = page.get('grid_total') or {}
                                tcols = gt.get('cols', cols); trows = gt.get('rows', rows)
                                if x + w - 1 > tcols or y + h - 1 > trows:
                                    issues.append(ValidationIssue(path=f"{epath}/area", message="Area exceeds total-grid bounds"))
                            else:
                                if x + w - 1 > cols or y + h - 1 > rows:
                                    issues.append(ValidationIssue(path=f"{epath}/area", message="Area exceeds grid bounds"))
    return ValidationResult(issues)
