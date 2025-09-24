from dataclasses import dataclass
from typing import List, Optional, Any, Dict

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


def validate_ir(ir: Dict[str, Any]) -> ValidationResult:
    issues: List[ValidationIssue] = []
    if not isinstance(ir, dict):
        return ValidationResult([ValidationIssue(path="/", message="IR root not a dict")])
    pages = ir.get("pages")
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
            els = page.get("elements", [])
            if not isinstance(els, list):
                issues.append(ValidationIssue(path=f"{ppath}/elements", message="Elements not a list"))
                continue
            for eidx, el in enumerate(els):
                epath = f"{ppath}/elements/{eidx}"
                if not isinstance(el, dict):
                    issues.append(ValidationIssue(path=epath, message="Element not an object"))
                    continue
                if 'type' not in el:
                    issues.append(ValidationIssue(path=epath, message="Element missing type"))
                else:
                    et = el['type']
                    if et not in ("header","subheader","body","figure","pdf","rectangle"):
                        issues.append(ValidationIssue(path=epath, message=f"Unknown element type '{et}'", severity='warn'))
                if el.get('type') == 'figure':
                    fig = el.get('figure')
                    if not fig or not fig.get('src'):
                        issues.append(ValidationIssue(path=f"{epath}/figure", message="Figure element missing src"))
                if el.get('type') == 'pdf':
                    pdf = el.get('pdf')
                    if not pdf or not pdf.get('src'):
                        issues.append(ValidationIssue(path=f"{epath}/pdf", message="PDF element missing src"))
    return ValidationResult(issues)
