#!/usr/bin/env bash
set -euo pipefail

# Build all .org files under examples/ into PDFs.
# Each example outputs to examples/out/<basename>/<basename>.pdf
# Tries to use `pagemaker` CLI if available, otherwise falls back to `python -m pagemaker.cli`.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."
EXAMPLES_DIR="${REPO_ROOT}/examples"
OUT_ROOT="${EXAMPLES_DIR}/out"

run_cli() {
  if command -v pagemaker >/dev/null 2>&1; then
    pagemaker "$@"
  else
    PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}" python3 -m pagemaker.cli "$@"
  fi
}

mkdir -p "${OUT_ROOT}"

built_any=0
ok_count=0
fail_count=0

pushd $EXAMPLES_DIR
# Find all .org files recursively in examples/ (stable sort)
# Use NUL delimiter to handle spaces/newlines in filenames
while IFS= read -r -d '' org; do
  built_any=1
  base="$(basename "$org" .org)"
  out_dir="${OUT_ROOT}/${base}"
  out_pdf="${base}.pdf"
  mkdir -p "$out_dir"
  echo "Building: ${org} -> ${out_dir}/${out_pdf}"
  if run_cli pdf "$org" --export-dir "$out_dir" --pdf-output "$out_pdf" --sanitize-pdfs; then
    echo "Done: ${out_dir}/${out_pdf}"
    echo
    ok_count=$((ok_count+1))
  else
    echo "FAILED: ${org}" >&2
    echo
    fail_count=$((fail_count+1))
    # continue-on-error: proceed to next example
  fi

done < <(find "${EXAMPLES_DIR}" -type f -name '*.org' -print0 | sort -z)

popd

if [ "$built_any" -eq 0 ]; then
  echo "No .org files found under ${EXAMPLES_DIR}" >&2
  exit 1
fi

echo "All examples processed under ${OUT_ROOT}" 
echo "Success: ${ok_count}  Failed: ${fail_count}"

# Exit non-zero if any failed
if [ "$fail_count" -gt 0 ]; then
  exit 1
fi
