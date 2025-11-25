"""
HTML post-processing for grid layout.

This module implements CSS Grid-based positioning for HTML exports, converting
AREA coordinates from the IR into CSS Grid properties. It also adds navigation
UI for page-based presentation mode.

Features:
- CSS Grid layout for element positioning (:AREA: properties)
- Page-based rendering (full-viewport slides)
- Navigation UI (keyboard shortcuts, page controls)
- Custom styles for presentation mode
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

try:
    from bs4 import BeautifulSoup

    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


def area_to_grid_css(area: Dict[str, int]) -> str:
    """
    Convert AREA coordinates to CSS Grid positioning.

    Args:
        area: Dict with keys {x, y, w, h} (1-based grid coordinates)

    Returns:
        CSS string like "grid-column: 2 / 6; grid-row: 3 / 5;"

    Example:
        area = {x: 2, y: 3, w: 4, h: 2}
        → "grid-column: 2 / 6; grid-row: 3 / 5;"
    """
    x = area['x']
    y = area['y']
    w = area['w']
    h = area['h']

    # CSS Grid uses start/end notation (end is exclusive)
    col_start = x
    col_end = x + w
    row_start = y
    row_end = y + h

    return f"grid-column: {col_start} / {col_end}; grid-row: {row_start} / {row_end};"


def _export_ir_positioning_json(ir: Dict[str, Any]) -> str:
    """
    Export IR positioning data as JSON for client-side processing.

    Returns:
        JSON string containing page and element positioning data
    """
    # Extract only the positioning data we need
    pages_data = []

    for page in ir.get('pages', []):
        if page.get('master_def'):
            continue  # Skip master pages

        page_data = {
            'id': page.get('id', ''),
            'grid': page.get('grid', {'cols': 12, 'rows': 8}),
            'elements': [],
        }

        for elem in page.get('elements', []):
            # Skip rectangles (decorative only)
            if elem.get('type') == 'rectangle':
                continue

            elem_data = {
                'id': elem.get('id', ''),
                'type': elem.get('type', 'body'),
                'area': elem.get('area'),
                'align': elem.get('align'),
                'valign': elem.get('valign'),
                'z': elem.get('z', 10),
            }

            # Add text content for matching (first 100 chars)
            text_blocks = elem.get('text_blocks', [])
            if text_blocks:
                text_preview = ''.join(b.get('content', '') for b in text_blocks)[:100]
                elem_data['text_preview'] = text_preview

            # For media elements (SVG, images, PDFs), use caption or title for matching
            # This allows matching <figure> elements with captions to IR elements
            caption = None
            elem_type = elem.get('type')
            if elem_type == 'svg' and elem.get('svg'):
                caption = elem.get('svg', {}).get('caption')
            elif elem_type == 'image' and elem.get('figure'):
                caption = elem.get('figure', {}).get('caption')
            elif elem_type == 'pdf' and elem.get('pdf'):
                caption = elem.get('pdf', {}).get('caption')

            # If no caption found, fall back to element title for media elements
            if not caption and elem_type in ('svg', 'image', 'pdf'):
                caption = elem.get('title')

            if caption:
                elem_data['text_preview'] = caption[:100]

            page_data['elements'].append(elem_data)

        pages_data.append(page_data)

    return json.dumps({'pages': pages_data}, indent=2)


def _generate_grid_application_js(ir: Dict[str, Any]) -> str:
    """
    Generate JavaScript that matches HTML elements to IR and applies grid positioning.

    This script:
    1. Reads IR positioning data from the embedded JSON
    2. Matches HTML elements (h1-h6, p, figure) to IR elements sequentially
    3. Wraps matched elements in positioned divs
    4. Creates page containers with CSS Grid
    5. Adds navigation controls
    """
    pages = [p for p in ir.get('pages', []) if not p.get('master_def')]
    page_count = len(pages)

    # JavaScript code (will be prettified in actual implementation)
    js = """
// Pagemaker M7.5: Client-side grid layout application
(function() {
    'use strict';
    
    // Read IR positioning data
    const irDataEl = document.getElementById('pagemaker-ir-data');
    if (!irDataEl) {
        console.warn('Pagemaker: No IR data found');
        return;
    }
    
    let irData;
    try {
        irData = JSON.parse(irDataEl.textContent);
    } catch (e) {
        console.error('Pagemaker: Failed to parse IR data', e);
        return;
    }
    
    const pages = irData.pages || [];
    if (pages.length === 0) {
        return;
    }
    
    // State
    let currentPage = 0;
    
    // Match HTML elements to IR elements
    function matchElements() {
        const body = document.body;
        const htmlElements = Array.from(body.querySelectorAll('h1, h2, h3, h4, h5, h6, p, figure'));
        
        // Build list of all IR elements with their page context
        const allIRElements = pages.flatMap(p => p.elements.map((e, idx) => ({
            pageIdx: pages.indexOf(p),
            element: e,
            elemIdx: idx
        })));
        
        const matches = [];
        const usedIRIndices = new Set();
        
        // Match each HTML element to an IR element by text content
        for (const htmlEl of htmlElements) {
            const htmlText = htmlEl.textContent.trim();
            if (!htmlText) continue;
            
            // Find best matching IR element
            let bestMatch = null;
            let bestScore = 0;
            
            for (let i = 0; i < allIRElements.length; i++) {
                if (usedIRIndices.has(i)) continue;
                
                const irItem = allIRElements[i];
                const irEl = irItem.element;
                const irText = (irEl.text_preview || '').trim();
                
                if (!irText) continue;
                
                // Calculate match score (simple substring matching)
                // Use first 200 chars for matching to handle longer content
                const htmlSample = htmlText.substring(0, 200);
                const irSample = irText.substring(0, 200);
                
                // Check if texts match (either direction)
                if (htmlSample.includes(irSample) || irSample.includes(htmlSample)) {
                    const score = Math.min(htmlSample.length, irSample.length);
                    if (score > bestScore) {
                        bestScore = score;
                        bestMatch = { irItem, irIndex: i };
                    }
                }
            }
            
            if (bestMatch) {
                matches.push({
                    htmlElement: htmlEl,
                    pageIdx: bestMatch.irItem.pageIdx,
                    element: bestMatch.irItem.element
                });
                usedIRIndices.add(bestMatch.irIndex);
            } else {
                console.warn('Pagemaker: Could not match HTML element to IR:', htmlText.substring(0, 50));
            }
        }
        
        return matches;
    }
    
    // Apply grid layout
    function applyGridLayout(matches) {
        const body = document.body;
        
        // Clear existing body content
        const originalContent = Array.from(body.children);
        body.innerHTML = '';
        
        // Create page containers
        pages.forEach((page, pageIdx) => {
            const pageDiv = document.createElement('div');
            pageDiv.className = 'pagemaker-page';
            pageDiv.setAttribute('data-page-id', page.id);
            pageDiv.setAttribute('data-page-num', pageIdx + 1);
            
            // Apply grid configuration
            const gridCols = page.grid?.cols || 12;
            const gridRows = page.grid?.rows || 8;
            pageDiv.style.gridTemplateColumns = `repeat(${gridCols}, 1fr)`;
            pageDiv.style.gridTemplateRows = `repeat(${gridRows}, 1fr)`;
            
            body.appendChild(pageDiv);
        });
        
        // Place matched elements into pages
        matches.forEach(match => {
            const pageDiv = body.children[match.pageIdx];
            if (!pageDiv) return;
            
            const elem = match.element;
            const htmlEl = match.htmlElement;
            
            // Create positioned wrapper
            const wrapper = document.createElement('div');
            wrapper.className = 'pagemaker-element';
            wrapper.setAttribute('data-element-id', elem.id);
            wrapper.setAttribute('data-type', elem.type);
            
            // Apply grid positioning
            if (elem.area) {
                const area = elem.area;
                const colStart = area.x;
                const colEnd = area.x + area.w;
                const rowStart = area.y;
                const rowEnd = area.y + area.h;
                wrapper.style.gridColumn = `${colStart} / ${colEnd}`;
                wrapper.style.gridRow = `${rowStart} / ${rowEnd}`;
            }
            
            // Apply alignment
            if (elem.align) {
                wrapper.style.textAlign = elem.align;
            }
            if (elem.valign) {
                wrapper.style.alignSelf = elem.valign === 'middle' ? 'center' : elem.valign;
            }
            
            // Apply z-index
            wrapper.style.zIndex = elem.z || 10;
            
            // Move HTML element into wrapper
            wrapper.appendChild(htmlEl.cloneNode(true));
            pageDiv.appendChild(wrapper);
        });
    }
    
    // Navigation functions
    function showPage(n) {
        const pageElements = document.querySelectorAll('.pagemaker-page');
        pageElements.forEach((el, idx) => {
            el.classList.toggle('active', idx === n);
        });
        currentPage = n;
        updateNav();
        window.location.hash = `page-${n + 1}`;
    }
    
    function updateNav() {
        const prevBtn = document.getElementById('pagemaker-prev');
        const nextBtn = document.getElementById('pagemaker-next');
        const counter = document.getElementById('pagemaker-counter');
        
        if (prevBtn) prevBtn.disabled = currentPage === 0;
        if (nextBtn) nextBtn.disabled = currentPage === pages.length - 1;
        if (counter) counter.textContent = `${currentPage + 1} / ${pages.length}`;
    }
    
    function nextPage() {
        if (currentPage < pages.length - 1) {
            showPage(currentPage + 1);
        }
    }
    
    function prevPage() {
        if (currentPage > 0) {
            showPage(currentPage - 1);
        }
    }
    
    // Keyboard navigation
    document.addEventListener('keydown', function(e) {
        if (e.key === 'ArrowRight' || e.key === ' ') {
            e.preventDefault();
            nextPage();
        } else if (e.key === 'ArrowLeft') {
            e.preventDefault();
            prevPage();
        }
    });
    
    // Initialize
    window.addEventListener('DOMContentLoaded', function() {
        // Match and apply grid layout
        const matches = matchElements();
        console.log('Pagemaker: Matched', matches.length, 'elements');
        matches.forEach(m => {
            console.log('  -', m.element.id, ':', m.htmlElement.textContent.substring(0, 30));
        });
        applyGridLayout(matches);
        
        // Add navigation controls
        const nav = document.createElement('div');
        nav.id = 'pagemaker-nav';
        nav.innerHTML = `
            <button id="pagemaker-prev">← Previous</button>
            <button id="pagemaker-next">Next →</button>
        `;
        document.body.appendChild(nav);
        
        // Add page counter
        const counter = document.createElement('div');
        counter.id = 'pagemaker-counter';
        document.body.appendChild(counter);
        
        // Wire up buttons
        document.getElementById('pagemaker-prev').onclick = prevPage;
        document.getElementById('pagemaker-next').onclick = nextPage;
        
        // Check URL hash for initial page
        const hash = window.location.hash;
        const match = hash.match(/page-(\\d+)/);
        if (match) {
            const pageNum = parseInt(match[1]) - 1;
            showPage(pageNum);
        } else {
            showPage(0);
        }
    });
    
    // Export navigation API
    window.pagemakerNav = {
        next: nextPage,
        prev: prevPage,
        goto: showPage
    };
})();
"""

    return js


def postprocess_html(html_path: Path, ir: Dict[str, Any]) -> None:
    """
    Post-process HTML output to add grid layout and navigation.

    NEW APPROACH (M7.5):
    - Preserves Typst's semantic HTML structure (M7 compatibility)
    - Exports IR positioning data as JSON
    - Uses JavaScript to match elements and apply grid positioning
    - Progressive enhancement: works with/without JavaScript

    Args:
        html_path: Path to the HTML file to post-process
        ir: Intermediate representation with page and element data

    Raises:
        ImportError: If BeautifulSoup4 is not installed
    """
    if not HAS_BS4:
        raise ImportError(
            "BeautifulSoup4 is required for HTML grid layout. "
            "Install with: pip install beautifulsoup4"
        )

    if not html_path.exists():
        return

    html_content = html_path.read_text(encoding='utf-8')
    soup = BeautifulSoup(html_content, 'html.parser')

    # Generate CSS for grid layout
    css = _generate_grid_css(ir)

    # Export IR positioning data as JSON
    ir_json = _export_ir_positioning_json(ir)

    # Generate JavaScript that matches HTML elements to IR and applies positioning
    js = _generate_grid_application_js(ir)

    # Insert CSS, JSON data, and JS into <head>
    head = soup.find('head')
    if not head:
        head = soup.new_tag('head')
        if soup.html:
            soup.html.insert(0, head)
        else:
            # Create html tag if needed
            html_tag = soup.new_tag('html')
            html_tag.append(head)
            soup.append(html_tag)

    # Add CSS
    style_tag = soup.new_tag('style')
    style_tag.string = css
    head.append(style_tag)

    # Add IR positioning data as JSON in a script tag
    script_data = soup.new_tag('script', type='application/json', id='pagemaker-ir-data')
    script_data.string = ir_json
    head.append(script_data)

    # Add JavaScript for grid application
    script_tag = soup.new_tag('script')
    script_tag.string = js
    head.append(script_tag)

    # Write back
    html_path.write_text(str(soup), encoding='utf-8')


def _generate_grid_css(ir: Dict[str, Any]) -> str:
    """Generate CSS for grid layout and presentation mode."""
    # Get first page grid configuration as default
    pages = ir.get('pages', [])
    if not pages:
        return ''

    # Use first non-master page grid config
    grid_cols = 12
    grid_rows = 8
    for page in pages:
        if not page.get('master_def'):
            grid = page.get('grid', {})
            grid_cols = grid.get('cols', 12)
            grid_rows = grid.get('rows', 8)
            break

    css = f"""/* Reset and base styles */
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    overflow: hidden;
}}

/* Page container - full viewport slides */
.pagemaker-page {{
    width: 100vw;
    height: 100vh;
    position: relative;
    display: none;
    overflow: hidden;
}}

.pagemaker-page.active {{
    display: grid;
    grid-template-columns: repeat({grid_cols}, 1fr);
    grid-template-rows: repeat({grid_rows}, 1fr);
    gap: 0;
}}

/* Element positioning using CSS Grid */
.pagemaker-element {{
    /* Grid positioning set via inline styles */
    padding: 10px;
    overflow: auto;
}}

/* Text alignment */
.pagemaker-element[data-align="left"] {{ text-align: left; }}
.pagemaker-element[data-align="right"] {{ text-align: right; }}
.pagemaker-element[data-align="center"] {{ text-align: center; }}
.pagemaker-element[data-align="justify"] {{ text-align: justify; }}

/* Vertical alignment */
.pagemaker-element[data-valign="top"] {{ align-self: start; }}
.pagemaker-element[data-valign="middle"] {{ align-self: center; }}
.pagemaker-element[data-valign="bottom"] {{ align-self: end; }}

/* Hide decorative rectangles in HTML */
.pagemaker-element[data-type="rectangle"] {{
    display: none;
}}

/* Navigation controls */
#pagemaker-nav {{
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 1000;
    display: flex;
    gap: 10px;
}}

#pagemaker-nav button {{
    background: rgba(0, 0, 0, 0.7);
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 5px;
    cursor: pointer;
    font-size: 16px;
}}

#pagemaker-nav button:hover {{
    background: rgba(0, 0, 0, 0.9);
}}

#pagemaker-nav button:disabled {{
    opacity: 0.3;
    cursor: not-allowed;
}}

#pagemaker-counter {{
    position: fixed;
    bottom: 20px;
    left: 20px;
    z-index: 1000;
    background: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 10px 20px;
    border-radius: 5px;
    font-size: 14px;
}}
"""
    return css
