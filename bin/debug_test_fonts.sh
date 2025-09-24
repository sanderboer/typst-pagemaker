#!/bin/bash
# Debug overlay test script with custom fonts

echo "🎨 Debug Overlay Test with Custom Fonts"
echo "======================================="

# Clean up previous files
echo "🧹 Cleaning up previous files..."
rm -f debug_overlay.typ debug_overlay.pdf

# Build PDF using pagemaker CLI with custom fonts
echo "📝 Building PDF via pagemaker CLI..."
# Ensure we run from repo root for assets/fonts
cd "$(dirname "$0")/.."
PYTHONPATH=src python3 -m pagemaker.cli pdf examples/debug_overlay.org -o debug_overlay.typ --export-dir . --pdf-output debug_overlay.pdf --no-clean

if [ $? -ne 0 ]; then
    echo "❌ Failed to build PDF"
    exit 1
fi

# Show results
echo "✅ Debug overlay test complete!"
echo "📄 Generated: debug_overlay.pdf ($(du -h debug_overlay.pdf | cut -f1))"
echo "🎯 Font verification:"
grep -c "text(font: \"Manrope\"" debug_overlay.typ | xargs echo "   - Manrope font references:"

echo ""
echo "🚀 Open debug_overlay.pdf to see:"
echo "   - Grid debug overlay"
echo "   - Custom Manrope typography"
echo "   - Rectangle overlays with z-ordering"
echo "   - Background images with text overlays"