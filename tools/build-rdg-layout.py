#!/usr/bin/env python3
"""Embed shared data helpers into the userscript without new @require files."""
from pathlib import Path
root=Path(__file__).resolve().parent
viewer=root/'rd-graph-viewer.user.js'
text=viewer.read_text()
for label,source in [('DECISION UI','rdg-decision-ui.js'),('VISUAL PROJECTION','rdg-visual-projection.js'),('PORTABLE UI','rdg-portable-ui.js'),('WORKFLOW UI','rdg-workflow-ui.js'),('LAYOUT CORE','rdg-layout-core.js'),('CATALOG','rdg-catalog.js'),('ROOT PROJECTION','rdg-root-projection.js'),('VIEW GEOMETRY','rdg-view-geometry.js'),('STATE','rdg-state.js')]:
    start=f'// BEGIN GENERATED RDG {label}\n'
    end=f'// END GENERATED RDG {label}\n'
    block=start+(root/source).read_text()+end
    if start in text:
        a=text.index(start);b=text.index(end,a)+len(end);text=text[:a]+block+text[b:]
    else:
        marker='// END GENERATED RDG CATALOG\n' if label=='STATE' else '// ==/UserScript==\n';assert text.count(marker)==1;text=text.replace(marker,marker+block)
viewer.write_text(text)
