# Viewer 2.2.7 — vertical history and plan

- Replaced the two-column future/history view with one timeline: published history in its existing order, then an explicit boundary, then the ordered explicit Plan placements.
- Added a sticky "Перейти к плану" button. It scrolls the Plan pane to the first placement card, accounts for toolbar height and focuses that card. Empty plans disable the button; reduced motion is respected.
- History uses framed cards, day dividers, known recorded timestamps and a separate unknown-time group. Execution/achievement/withdrawal notes remain visible.
- Historical cards expose an explicit "Открыть в графе" action. Projection references resolve to the canonical owner declaration and introducing parent wave, using the existing authorized sources. Missing targets retain their recorded title/note without inventing a route.
- Graph-change cards link to available changed Requirements/Actions.
- Shared CSS variables keep Requirements blue, Actions purple, canon teal and QRPE amber in the graph and timeline. Entity color stays stable across history/future; event status has a separate labeled badge. Nested Action badges keep their own palette.
- Action variants remain context unless explicitly placed; no node creation or optimistic completion facts were added to Plan.
- Historical canon and QRPE remain explicitly current graph material, not an asserted historical snapshot.
- Viewer/userscript version: 2.2.7. Local Loader 2.5.2, Helper protocol and remembered directory storage are unchanged.

Validation:
- Node regressions: 76 tests, 73 passed, 3 integration-gated skipped, 0 failed.
- Real HTTP + file UI/writer workflows: 2 passed; create/place/complete/withdraw/retry uses the existing writers.
- Chromium timeline: history-before-plan, true first-placement scroll, canonical historical-goal navigation, shared graph/card palette, nested badges, mobile layout and reduced-motion scroll, pageerrors=0.
- Full graph Chromium: 4 screenshots, version 2.2.7, passed.
- Desktop and mobile screenshots inspected. Browser picker and permission decisions are simulated; the user's installed Tampermonkey/Windows browser is not verified.

Sources and real user graph/plan data were not migrated. No grants, mounts, git commit or push were added.
Existing live synthetic file session remains ../rdg-windows-manual-session-20261019-150658/session; no new session is required for this UI change.
