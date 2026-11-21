# RDG Chat Commands — authoring and publication contract

**Status:** active RDG-owned chat command catalog, **schema v2**. These are ready-to-insert ChatGPT instructions, **not** RDG Graph definitions, server-side commands, or an authorization grant.

## Authority and files

- **Bundled seed and legacy clients:** [commands.json](commands.json) owns the shipped snapshot. The [live RDG catalog](../../docs/guides/RDG-DECISION-V1-CONTRACT.md#rdg-chat-command-catalog) is edited through Application after explicit initialization.
- **Published projection:** [catalog-v2.json](catalog-v2.json), generated deterministically by [build.py](build.py). Run **python3 -B kit/helper-commands/build.py** and then **python3 -B kit/helper-commands/build.py --check**. Both **catalog-v2.json** (new grouped v2) and the existing **catalog.json** (v1 direct-lens projection) are generated and byte-checked from the same author source. The v1 file deliberately stays byte-identical if the existing 21 launchers are unchanged, so installed v0.40.9 Helpers continue to work. Run **python3 -B tests/rdg-helper-commands.test.py** and **python3 -B tests/rdg-lens-catalog.test.py**.
- **Transport:** one public GET of the versioned V2 endpoint from RDG GitHub main, **https://raw.githubusercontent.com/AlexPastukhh/rd-graphs/main/kit/helper-commands/catalog-v2.json**. This is a static compatibility endpoint for the existing Helper. It updates after merge to main. The server package contains the same projection as its one-time seed. Old clients keep reading catalog.json (v1); new clients select catalog-v2.json (v2).

The manifest has **schemaVersion=2**, **kind=rdg-chat-commands**, **complete=true**, a SHA-256 **catalogRevision**, ordered presentation **groups[]**, and **commands[]** sorted by stable ID. Each group defines id, title and description. Each command defines id, kind, title, description, groupId, typed lensRefs array and **exact insertText**. The revision changes with group text, order, membership and command content.

Supported kinds:
- **lens-launcher:** exactly one typed lensRef, stable ID rdg.lens.{lensKey}. Exactly one launcher for every known published rdg-decision-v1 lens is mandatory (21 at this revision, including operate and develop).
- **workflow:** stable ID rdg.command.{slug} and one or more lensRefs; a standalone instruction can combine multiple existing lenses and add RDG-authored workflow text.
- **instruction:** stable ID rdg.command.{slug}, zero or more lensRefs, for a genuine non-lens instruction.

Each typed ref specifies role=lens, lensKey, modelProfile=rdg-decision-v1; the builder verifies all identities using the local **tools/rdg-agent-lenses/catalog.json**. It does not require freeform lens Markdown or generate command content from it. If a command lists lens refs, its insertText must explicitly request the authorized Agent lens read for each. IDs, duplicates, unknown groups, unknown lenses, unexpected fields, secret-shaped content and oversized fields fail closed. Other command kinds require a reviewed schema extension.

## Bootstrap for a real work session

The **Начало работы** group contains **rdg.command.bootstrap**, a composite **workflow** command. It invokes the existing **orient** and **work** lenses but also supplies explicit instructions to:
- identify the current user task, scope, authorized RDG access, owner/process and current sources;
- confirm identity and revision and read full **current structured** orient and work definitions via RDG Agent (not the button description);
- perform the mandatory first-entry bootstrap from the current RDG registry when needed; prefer targeted reading on continuation;
- find a bounded useful step and distinguish missing facts, user intent, and protected authorization.

**A bootstrap insertion is not a user authorization to create a Graph, Action or process.** Explicit user instructions to work inside RDG may authorize ordinary task steps under the current Agent/Gateway contracts; protected operations remain subject to their own authority. The command does not copy methodology into the UI and should report unavailable Agent access rather than fabricate lens content.

The **Структурированные линзы** group contains all 21 existing direct launchers. **Плейн-текст** contains standalone instructions for carrying out a whole task and shaping a textual lens. The Helper inserts each instruction in full. **Начало работы** contains Bootstrap.

Set each command's `groupId` explicitly in `commands.json`. A lens's runtime format marker and a Helper command's group are edited independently; changing one does not change the other. Prompt Modules belong to the separate OBS prompt library.

## Browser consumer and release sequence

OBS Planning Helper fetches the entire v2 JSON with **one anonymous Tampermonkey GET** when v2 GM cache is absent or the user chooses **Обновить RDG**. It validates a complete manifest and atomically retains the last known good cache on any failure. Group navigation, search, copy, insertion and display are local-only. Insertion never submits the chat or writes to Graph. Old v1 cache and existing OBS prompts, modules and Planning Commands remain separate.

**Release order: RDG v2 PR + merge → public catalog-v2.json readback (while catalog.json remains valid for V1) → OBS v2 PR + CI + owner merge → Windows Mirror pull (if required) → local-loader browser smoke/full-workflow acceptance.** Until RDG v2 exists on public main, a v2 consumer must report unavailability, not synthesize command lists.

For full-workflow testing, start a fresh ChatGPT task with Bootstrap, confirm full live orient/work read or a precise access failure, continue with a fitting direct lens only when useful, and verify no unapproved Graph changes. Test cold-cache, warm-cache, failed Refresh, group display and exact insertion separately. See OBS Helper manual acceptance for UI expectations.

**--init is a one-time initializer** that refuses to overwrite a published source; do not use it to update the established catalog.
