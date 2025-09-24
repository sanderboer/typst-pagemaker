#!/bin/bash
# Debug overlay test script with custom fonts

echo "🎨 Debug Overlay Test with Custom Fonts"
echo "======================================="

# Clean up previous files
echo "🧹 Cleaning up previous files..."
rm -f debug_overlay_test.typ debug_overlay_test.pdf

# Generate Typst file
echo "📝 Generating Typst file..."
python gen_typst.py debug_overlay_test.org -o debug_overlay_test.typ

# Check if generation was successful
if [ $? -ne 0 ]; then
    echo "❌ Failed to generate Typst file"
    exit 1
fi

# Compile with custom fonts
echo "🔤 Compiling with custom Manrope fonts..."
typst compile --font-path assets/fonts --font-path assets/fonts/static debug_overlay_test.typ debug_overlay_test.pdf

# Check if compilation was successful
if [ $? -ne 0 ]; then
    echo "❌ Failed to compile PDF"
    exit 1
fi

# Show results
echo "✅ Debug overlay test complete!"
echo "📄 Generated: debug_overlay_test.pdf ($(du -h debug_overlay_test.pdf | cut -f1))"
echo "🎯 Font verification:"
grep -c "text(font: \"Manrope\"" debug_overlay_test.typ | xargs echo "   - Manrope font references:"

echo ""
echo "🚀 Open debug_overlay_test.pdf to see:"
echo "   - Grid debug overlay"
echo "   - Custom Manrope typography"
echo "   - Rectangle overlays with z-ordering"
echo "   - Background images with text overlays"