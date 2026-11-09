# Viewer 2.2.8 — canon above its Action

- Canon display nodes are excluded from the causal rank/column calculation.
- Automatic layout reserves vertical room for each owner+canon pair. Each canon is aligned above its Action, Option or selected Decision.
- The association is a short teal dotted line without an arrowhead or an outgoing causal label. Other R/Action/R arrows keep their meaning.
- Every render reattaches the canon to its visible owner, including restored navigation views and layout overrides. Dragging either part moves the owning pair.
- Legacy stored canon coordinates remain readable in the layout file but no longer detach the view decoration. Actual persisted node coordinates are retained; densely arranged old manual layouts can be rebuilt through "Расположение → Авторасположение".
- Fixed a legacy selected Decision whose canon source Option has no independent R->Option placement: its canon remains attached to the selected Decision when all variants are requested.
- A real placed Option still gets its own canon when all options are displayed.
- No source Graph/Plan model, completion events, identity, grants or Helper protocol changes.

Validation:
- 101 Node tests: 98 pass, 3 gated live integrations skipped, 0 fail.
- Includes all bundled graph route/node collision checks, Collections, layout save/reload, canon geometry, old saved canon coordinates, owner/canon drag and legacy option toggles.
- Native Chromium: two aligned Action canon pairs, no arrowheads, real pointer drag on owner and canon, canon inspector and selected Decision variant switches; pageerrors=0.
- Full graph native browser: version 2.2.8, 4 screenshots, pass.
- Screenshot actions-canons-above.png visually inspected.
- Tests operate on isolated fixtures; user's installed Tampermonkey/browser is not verified.

Userscript source version 2.2.8; Local Loader remains 2.5.2. Current live file session can be reused.
No git commit or push (this mounted project has no .git).
