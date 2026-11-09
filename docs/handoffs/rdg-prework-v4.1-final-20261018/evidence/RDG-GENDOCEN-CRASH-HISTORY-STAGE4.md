# Stage 4 — co-located crash recovery / persisted review history

**Status: successful synthetic integration spike; not production acceptance.**
Owner tree: /workspace/repos/rd-graphs. Engine: /workspace/repos/gendocen, docengine 0.1.0.dev25. No installed Helper/Viewer, no working user graph changed, no Plan execution and no user decision accepted.

## What is actually executed

The real owner adapter creates two separate resources (synthetic RDG and candidate Temporal Plan) inside a temporary docengine project. The co-located tool tools/rdg-gendocen-runtime-smoke.py drives the genuine Gendocen CLI in multiple processes and checks branch-specific and shared-deadline dependencies.

After A1's Canon changes (A1 review_required; A2 valid), the smoke tool attempts a synthetic A1 semantic validation with a fresh review_context_id but injects DOCENGINE_TEST_CRASH_AFTER_WRITES=1. This test-only Gendocen hard-crash mode deliberately terminates the child process with code **91** just after its first protected write. The test does not execute a real RDG writer or simulate an actual Action selection.

The subsequent status CLI refuses to read with machine status recovery_required. The verify CLI returns machine status verification_failed and includes a **blocking recovery_required finding**; these are distinct machine status fields. The recover CLI rolls back the interrupted mutation from the Gendocen transaction journal. Test assertions compare dependency_state.json, dependency_events.jsonl and every receipt file byte-for-byte to their pre-crash values. They also compare both canonical synthetic RDG and Plan source bytes and both projected resource files. Gendocen does not modify them.

After recovery, A1 stays review_required and A2 stays valid. A1's historical receipt is still the active old receipt. The public history CLI returns exactly the pre-crash receipt IDs/events. The recovery writes a separate audit record with action rolled_back_interrupted_transaction. A second recover is idempotent and does not append another recovery audit record.

Finally the test obtains a **new** review_context_id and explicitly validates A1 in the synthetic project. A1 becomes valid; public A1 history contains all prior receipts/events and exactly one additional receipt/event. This does not approve any RDG Action and does not modify an actual T1.

## Reproduce

    PYTHONDONTWRITEBYTECODE=1 python3 tools/rdg-gendocen-runtime-smoke.py --engine-source /workspace/repos/gendocen

The runner creates only tempfile project state; its source is in the owner RDG tree. A machine evidence snapshot for this exact code and version is located at:

    docs/examples/RDG-GENDOCEN-CRASH-HISTORY-CHECKPOINT-20261018.json

## Evidence scope

Verified: Gendocen crash barrier, protected read refusal, explicit rollback, recovery audit, idempotency, exact persisted dependency history preservation, fresh post-recovery validation and read-only RDG/Plan source invariants.

**Not verified: real historical T1 immutability.** The synthetic RDG used by the smoke has only candidate Actions and no genuine owner-written T1 selection event. Its unchanged source bytes are a safety check for this fixture, not a proof of the full selected Action history contract. No human authentication, real-world F-P attestation, Plan writer authorization, reattachment of versioned real user snapshots or production multi-process orchestration is proven here.

Future Stage 4 acceptance gates: exercise the same crash/recovery with an authorized, actual T1-bearing versioned RDG snapshot and historical ownership/provenance; test unknown post-crash changes and malicious/corrupt recovery journals on the RDG integration path; prove all source snapshots and dependency receipts survive deployment restarts; authorize any real semantic review separately from technical engine receipts.
