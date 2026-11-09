> **СТАТУС: АРХИВ / ИСТОРИЧЕСКАЯ РАЗРАБОТКА — НЕ ДЕЙСТВУЮЩИЙ КОНТРАКТ.** Включая файлы с именами `CONTRACT`, `PLAN`, `STAGE`, `PILOT` и со словом «актуальный» в тексте. Новый чат должен использовать [единую текущую спецификацию](RDG-CURRENT-STATE.md); ниже сохранены прежние эксперименты, решения и протоколы.

# Gendocen dev25 runtime proof — RDG and Temporal Plan

**Status:** actual docengine 0.1.0.dev25 runtime confirmed in a separate isolated environment with synthetic Gendocen-shaped RDG/Plan resources. **Not** a fully deployed Stage 4 integration or production acceptance.

## New strongest evidence — co-located RDG + Gendocen runtime, 2026-10-18

**PASS:** the actual source checkout in /workspace/repos/gendocen ran docengine 0.1.0.dev25 from the **same authorized host** as the current RDG source in /workspace/repos/rd-graphs. The runner tools/rdg-gendocen-runtime-smoke.py executed its real rdg-gendocen-adapter.py for graph+Plan, created only synthetic files inside a temporary directory, and drove Gendocen CLI in separate Python processes.

All targeted invalidation cases passed: unrelated reordering no invalidation; A2-only constraint invalidates A2; shared deadline invalidates both A1+A2; A1-only canon invalidates A1; stale review_context_id is rejected. The stronger durability assertions also passed: a real dependency_state.json held both valid targets, **two persisted receipt files and two dependency events** were readable, another CLI check did not advance the state revision or duplicate receipts/events, and a rejected stale validation did not alter the state or create a receipt. Markdown remained byte-identical, and RDG Actions remained candidate.

Read the [machine-readable co-located checkpoint](../examples/RDG-GENDOCEN-COLOCATED-RUNTIME-CHECKPOINT-20261018.json) for exact SHA-256 of both codebases' version files and the runner source. Earlier sections below describe the **historical, less complete** separated-container proofs. The archive is no longer a blocker for synthetic co-located execution: the actual Gendocen source tree was discovered on the same host as RDG.

Still OPEN: trusted real data snapshots, user-authorized review, Gendocen transaction crash/recover on this specific RDG scenario, Plan write/event authorization, and owner deployment. This proof is not production acceptance.

## Source and environment

The user-supplied archive gendocen-main (1)(1).zip was available in an attachment-backed analysis container. Its source was used offline from a temporary directory. The mounted owner source at /workspace/repos/rd-graphs **does not contain the archive**, has no installed docengine and cannot assume attachment paths are available.

The actual runtime test used the real Gendocen CLI with a disposable project, synthetic RDG Action records and temporal-constraint resources in the shape of the RDG adapter projections, and two Markdown review targets (A1, A2). It registered two semantic_review rules against exact data fields and initialized fresh baselines with explicit synthetic still-valid validations. The test **did not run the actual owner adapter**; those projections were synthetically constructed.

A separate smoke runner for the stronger proof against **actual RDG adapter output** was added to the owner source:

    python3 tools/rdg-gendocen-runtime-smoke.py --engine-source /path/to/reviewed/gendocen-main

It prepares its own temporary RDG, candidate Temporal Plan, projections using rdg-gendocen-adapter.py, and trusted project-owned rules. This runner has passed Python syntax checks, but has **not yet been executed** with the engine source in the same owner environment. Do not conflate these two evidence levels.

## Actual runtime observations

| Input change after validated synthetic baseline | A1 review | A2 review |
|---|---|---|
| Initial explicit baseline | valid | valid |
| Reordering nonsemantic JSON and metadata revision | valid | valid |
| New constraint only on A2 branch | valid | review_required |
| A2 revalidated with a current review context | valid | valid |
| Shared delivery deadline changed | review_required | review_required |
| A1 validation using a stale review context after another change | rejected, validation_failed | — |
| After new baselines, only A1 Canon changed | review_required | valid |

No review Markdown was automatically rewritten. No RDG Action was selected, no confirmed F-P written and no Plan action executed.

Proof files generated in the attachment-backed container: rdg-gendocen-real-runtime-proof.py and rdg-gendocen-runtime-result.json. These are separate from owner-local source and cannot be used as its local file paths.

## Technical findings

Gendocen resource:// URI comes from the actual $docengine.resource_id, not from the descriptor file path. For example, rdg.plan.<hash> is exposed as resource://rdg/plan.<hash>.

The RDG adapter's timeConstraintsByStep now contains a stable field for **every** step, including an empty array before constraints exist. This supports registration of a precise dependency on a future constraint; previously a subscription to a step with no constraints was not reliably addressable.

For targeted invalidation, register semantic_review rules against precise source fields, such as timeConstraintsByStep/S-A2 and nodesById/A1/canonBlock. A whole-resource digest makes unrelated changes look significant. This is a field-level source-path contract, **not** proof that arbitrary semantic meaning has been evaluated.

Gendocen can require explicit fresh review_context_id after relevant changes; it cannot infer truth, accept an Action, or provide user identity and factual attestation. Synthetic validate still-valid is only a test baseline, not a user decision.

## Follow-up 2026-10-18 — owner adapter output + genuine Gendocen runtime

PASS: 5/5 scenarios across 25 independent Gendocen CLI processes. The current owner RDG adapter generated six synthetic RDG/Plan resource snapshots. The exact output JSON was transmitted to the isolated archive-backed runtime with SHA-256 verification. In this real engine test, an A2-only constraint invalidated A2; a common deadline invalidated both A1 and A2; an A1 canon change invalidated only A1; a stale review_context_id was rejected; cosmetic reordering was ignored; review Markdown never changed.

[Machine proof and exact owner code hashes](../examples/RDG-GENDOCEN-OWNER-PROJECTIONS-REAL-RUNTIME-20261018.json).

Boundary: adapter executed in the owner environment, engine executed in a distinct isolation environment on its exact outputs. They were **not co-located**, and no real owner graph, Helper or production workflow was changed. The owner-local smoke runner remains unexecuted with the engine present in the same process. Stage 4 is still partial and candidate.

## New Stage 4 checkpoint — crash recovery on actual synthetic RDG/Plan adapter outputs

The co-located runner now injects a real test-only Gendocen hard crash (exit 91) in the middle of semantic validation. Explicit recover restores old receipts, dependency_state.json and dependency_events.jsonl byte-for-byte. A separate rollback audit record is created, recover is idempotent, public history returns the same A1 receipts/events after rollback, and a fresh synthetic review adds exactly one new receipt and event. Canonical source bytes and Markdown reviews are unchanged. For precise machine evidence and limits, see [Stage 4 crash/history checkpoint](RDG-GENDOCEN-CRASH-HISTORY-STAGE4.md).

**Genuine historical RDG T1 was not exercised:** these sources are candidates without an accepted Action event. Crash recovery on real versioned owner snapshots and F-P factual trust remain distinct open gates.

## Open gates

- COMPLETED for synthetic test: actual RDG adapter and Gendocen co-located, runner executed successfully with SHA-256 evidence; production owner deployment still open.
- Register real, authorized owner-specific rules, reliable historical snapshots and persistent dependency receipts for RDG↔Plan. Test recovery and revalidation against actual owner data.
- Keep Plan authoring, actual event attestation, Action selection, and real verified F-P separate in grants and review.
- Do not claim installed Helper/Viewer, canonical GitHub graph writes, docengine package installation in RDG, or Stage 4 complete.

**Conclusion:** genuine co-located RDG-adapter/Gendocen integration and durable synthetic dependency receipts are demonstrated. Production canonical owner integration, actual Plan writer, crash recovery on RDG inputs and human trust gates remain pending.
