"""Centralized asset path resolution and rewriting.

This module defines AssetPathResolver, which handles converting asset source
strings inside the intermediate representation (IR) into paths relative to the
Typst export directory. It consolidates legacy duplicated logic from
`generator.adjust_asset_paths` and `generation.pdf_processor.adjust_asset_paths`.

Precedence (non-strict):
1. Absolute / protocol paths returned unchanged.
2. Invocation current working directory (CWD).
3. Source document directory (if provided to resolver).
4. Project root (auto-detected by searching upwards for pyproject.toml or .git).
5. Typst export directory (where .typ file will live).
6. Examples fallback: if path starts with `assets/`, also try `<project_root>/examples/<src>`.
7. Best-effort rewrite: if still unresolved and relative, map through project root.

Strict mode leaves non-existent relative paths unchanged rather than rewriting.

Debugging: Set env `PAGEMAKER_DEBUG_ASSET_PATHS=1` to log resolution decisions.
Caching: Resolutions cached per original src string for the lifetime of the resolver.
"""

from __future__ import annotations

import os
import pathlib

_DEBUG_FLAG = os.environ.get("PAGEMAKER_DEBUG_ASSET_PATHS") == "1"


class AssetPathResolver:
    def __init__(
        self,
        typst_dir: pathlib.Path,
        source_dir: pathlib.Path | None = None,
        project_root: pathlib.Path | None = None,
        strict: bool = False,
    ) -> None:
        try:
            self.typst_dir = typst_dir.resolve()
        except Exception:
            self.typst_dir = typst_dir
        self.source_dir = source_dir.resolve() if source_dir else None
        self.project_root = project_root or self._detect_project_root()
        self.strict = strict
        self._cache: dict[str, str] = {}

    def _detect_project_root(self) -> pathlib.Path:
        """Detect project root by searching upwards for pyproject.toml or .git."""
        cur = pathlib.Path(__file__).resolve()
        for parent in [cur] + list(cur.parents):
            if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
                return parent
        # Fallback to CWD if markers not found
        return pathlib.Path.cwd()

    def resolve(self, src: str) -> str:
        # Cache hit
        if src in self._cache:
            return self._cache[src]

        original = src
        # Absolute or protocol path
        if os.path.isabs(src) or _is_protocol(src):
            self._cache[src] = src
            return src

        candidates: list[pathlib.Path] = []
        cwd_path = pathlib.Path.cwd() / src
        candidates.append(cwd_path)
        if self.source_dir is not None:
            candidates.append(self.source_dir / src)
        candidates.append(self.project_root / src)
        candidates.append(self.typst_dir / src)

        # Examples fallback
        examples_alt: pathlib.Path | None = None
        if src.startswith("assets/"):
            examples_alt = self.project_root / "examples" / src
            candidates.append(examples_alt)

        chosen: pathlib.Path | None = None
        for cand in candidates:
            try:
                c = cand.resolve()
            except Exception:
                continue
            if c.exists():
                chosen = c
                break

        if chosen is None:
            # Best-effort rewrite mapping through project root unless strict
            if not self.strict and not os.path.isabs(src):
                try:
                    chosen = (self.project_root / src).resolve()
                except Exception:
                    pass
            else:
                # Leave unchanged
                self._cache[original] = original
                if _DEBUG_FLAG:
                    _debug_log(original, original, reason="unchanged-strict-or-absent")
                return original

        # Compute relative path to typst_dir
        # Use a cast to satisfy type checkers (chosen is guaranteed not None here)
        from typing import cast

        final_path = cast(pathlib.Path, chosen)
        rel: str
        try:
            rel = os.path.relpath(final_path, self.typst_dir)
        except Exception:
            rel = str(final_path)

        self._cache[original] = rel
        if _DEBUG_FLAG:
            _debug_log(original, rel, reason=f"resolved:{final_path}")
        return rel

    def adjust_ir_asset_paths(self, ir: dict) -> dict:
        for page in ir.get("pages", []):
            for el in page.get("elements", []):
                for key in ("figure", "pdf", "svg"):
                    obj = el.get(key)
                    if obj and obj.get("src"):
                        obj["src"] = self.resolve(obj["src"])
        return ir


def _is_protocol(src: str) -> bool:
    return bool(src and (":" in src and not src.startswith("./") and not src.startswith("../")))


def _debug_log(original: str, rewritten: str, reason: str) -> None:
    try:
        print(f"[asset-path-debug] src='{original}' -> '{rewritten}' ({reason})")
    except Exception:
        pass


__all__ = ["AssetPathResolver"]
