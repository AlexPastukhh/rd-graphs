# Viewer 2.2.9 — fix canon overlap on existing layouts

Cause:
- 2.2.8 placed canon cards 96px above their owners but retained older saved/navigation owner rows 124px apart.
- The second canon could cover the first Action; edge routing then had no unobstructed endpoint and took a long detour.
- Reproduced before the fix: both new dense-layout tests failed with "overlap: A1 / __canon__A2".

Fix:
- Before each render, treat the owner, canon and connector gap as one 168px-high group.
- Detect actual intersecting groups, including saved coordinates and navigation caches, and move colliding groups down with a 28px gap.
- Alignment is deterministic and idempotent; unrelated graph-node pairs without a canon do not trigger this reflow.
- Reattach canon nodes after collision resolution, then route edges against the corrected geometry.
- On pointer release, capture every displayed coordinate shifted during the drag into the existing layout journal. Automatic save/reload retains the visible result.
- Reading a layout does not overwrite its stored original positions automatically. No source Graph or Plan data changes.
- Manual layout reset is no longer required to fix this overlap.

Validation:
- Before-fix reproduction log: repro-before.log.
- 6 focused canon tests passed, including dense saved coordinates, toggles, real owner refs and save/restore stability.
- Node regression: 103 tests, 100 passed, 3 live-integration-gated skipped, 0 failed.
- Native Chromium: dense saved-row reproduction, aligned pairs, no overlaps, real pointer drag, automatic save, actual page reload, canon inspector and legacy Decision; pageerrors=0.
- Full graph native browser: 4 screenshots, version 2.2.9, passed.
- Visually inspected browser/dense-layout-repaired.png: distinct pairs and short causal routes.

Userscript source 2.2.9; Local Loader and Helper protocol unchanged. User's installed Tampermonkey/browser is not verified.
No grants, mounts, real user graph edits, git commit or push.
