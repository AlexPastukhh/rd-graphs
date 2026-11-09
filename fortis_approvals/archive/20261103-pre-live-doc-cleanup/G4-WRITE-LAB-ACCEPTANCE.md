# G4 WRITE trusted-executor LAB — offline acceptance and remaining blockers

> **OWNER SUPERSESSION 2026-10-31: ONE CONTAINER** — this is a historical **fake split-worker laboratory report**, NOT a requirement to build a second token-bearing executor container/process/IPC. The active design is ONE owner-controlled Fortis Docker containing private tokens, trusted policy/ASK/WebAuthn, a shared Core.execute and typed adapters. Replay/UNCERTAIN and security tests documented below remain valuable; process separation is optional later only after a new owner decision. Real Sonar POST remains NO-GO. [Current architecture](G4-WRITE-PRIVILEGED-TOKEN-ADR.md) · [master plan](../../docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md).


**Date:** 2026-10-31. **Status:** synthetic-only lab PASS, **production WRITE NOT IMPLEMENTED and NOT AUTHORIZED**. This record implements part of [`G4-WRITE-PRIVILEGED-TOKEN-ADR.md`](G4-WRITE-PRIVILEGED-TOKEN-ADR.md) with a **broad Sonar token in a future trusted executor + non-bypassable Fortis ASK** as the owner-selected design. No SonarCloud token exists inside this lab and no remote network API can be reached by its transport.

## Owner architectural correction: ALLOW and ASK share one executor

The owner clarified that G1/Approvals is **not** a separate ASK execution engine:
`Core.submit()` allows trusted `ALLOW` policies to enter `Core.execute()`
directly; `ASK` persists `PENDING` until the owner verifies and approves, then
enters the **identical `Core.execute()` / adapter path**. `DENY`/Reject do not
execute. A previous lab gate wrongly accepted **only** the ASK event chain,
effectively rejecting valid `ALLOW` actions. The new lab gate has a trusted
constructor-side policy selector (`trusted_policy='ASK'` or `'ALLOW'`) which
checks exact Core event evidence for each *before the same immutable request
fingerprint, durable reservation and fake adapter POST*. **Only trusted
composition sets the policy**; an AI/client payload cannot override it.
The two new tests prove (1) trusted synthetic `ALLOW` skips owner review but
uses the **same executor** and exactly one fake POST; (2) a mismatched ASK
request cannot sneak through an `ALLOW` gate. The deployed SonarCloud
`accept_issue` operation remains **ASK**. No real WRITE release is authorized.

## What was actually implemented

- `fortis_approvals/g4_write_lab.py` is a test/lab-only Python module. `LabSonar` is a **typed in-memory fake** for exactly one synthetic project (`g4-lab-project`) and Issue (`G4-LAB-1`), with fixed GET/POST route simulation. It has **no HTTP client, URL, socket, token argument, generic API method or CLI**. `LabPostGate` explicitly refuses every source whose concrete type is not `LabSonar`. This is not a Sonar WRITE integration.
- `LabGuardedSonarAdapter` composes the existing `SonarIssueAdapter` with `LabPostGate`. Only a trusted `Core` can produce the durable `APPROVED -> DISPATCHED` state through either policy `ALLOW` or a WebAuthn-approved `ASK`; the gate verifies the corresponding immutable event chain. Before even the fake POST, the guard reopens the owner-controlled SQLite database, selects the **exact** request UUID, requires `DISPATCHED`, the exact serialized request, unexpired request, matching actor/policy-version/preview-derived SHA fingerprint, and **one of two trusted-policy-specific chains**: `ASK` requires verified owner + decision `approve` with `PENDING, APPROVED, DISPATCHED` and the decision event's matching owner/request digest and proof SHA; `ALLOW` requires no owner/no decision, a trusted `ALLOW` event and `APPROVED, DISPATCHED`. A mismatch denies the fake POST. The guarded fake POST accepts **only** `POST /api/issues/do_transition` with `issue=G4-LAB-1` and `transition=accept`.
- The guard writes a **unique durable reservation** in `g4_lab_post_attempts` before the fake POST (SQLite `BEGIN IMMEDIATE`, `PRAGMA synchronous=FULL`). A second attempt for the same request, even from a competitor or new `LabPostGate` instance, fails. This deliberately favors `UNCERTAIN` / no retry after crash over risking duplicate remote writes.
- The existing `Core` still enforces server-side ASK; `OwnerPortal` uses genuine local test WebAuthn assertion verification and required User Verification (UV), not a simulated boolean `approved=true`. In this lab the test identity and virtual P-256 key are **disposable**, and owner session origin is a test-only `http://localhost:18992` string, **not a bound TCP listener**. It does not touch existing G2 (18990) or G4 (18991).
- Code was added only in repository source/tests. **The G4 candidate Dockerfile explicitly lists modules and does NOT include `g4_write_lab.py`**. No Compose edit, token, new container, persistent volume, auth key registration, new SonarCloud ASK or real POST was performed.

## Separate owner and worker processes — additional offline milestone

`tests/test_g4_write_process_lab.py` adds **three** process-boundary tests.
The owner-side `ProcessOnlyOwnerCore` is a lab subclass whose `execute`
only returns the stored `APPROVED` request without dispatching it. Its
in-process Sonar adapter is wrapped in `NoWriteTransport`, so even manually
calling `Core.execute()` in the owner process cannot send a fake POST; it
will conservatively mark the request `UNCERTAIN`. The owner side uses a
virtual FIDO2 WebAuthn/PIN-equivalent UV assertion and persists the exact
request fingerprint and approval event to temporary SQLite.

A **separate Python process** started with `multiprocessing.spawn` runs
`lab_worker_once(core_database,receipt_database,request_uuid,queue)`.
The worker cannot receive a token, arbitrary URL/method or Issue body over
IPC; it constructs its **own** `LabSonar` in-memory fake and `LabPostGate`.
It reads the exact approved request from the owner-side SQLite, reserves
one dispatch attempt and simulates a readback. Its queue response exposes
only non-secret `state` and `fake_posts` count. The test runs the worker a
second time against the same database: no additional POST occurs.
Another test supplies `PENDING` and then `REJECTED` requests to the worker:
zero fake POST. The third deliberately bypasses the owner mixin and calls
base `Core.execute`; `NoWriteTransport` refuses any POST and prevents
subsequent replay. The full Python suite now has **173/173 PASS**.

**Process-boundary limitation:** this is a Python subprocess test, not an
OS sandbox or authentication/authorization of an IPC endpoint. The worker
has filesystem access to the test SQLite and only a fake credential-less
transport. It does **not** demonstrate that a separate real privileged
worker cannot have its executable, inputs, database or credential altered
by host/Docker administrators. Production must design trusted, authenticated
one-way owner→worker IPC and OS/container access isolation **before** a real
token is made available. The current Windows G4 Docker image was not
modified, and no worker process persists after the tests.

## Verification results

`tests/test_g4_write_lab.py` adds **14 tests**, plus **3** distinct subprocess integration tests in `tests/test_g4_write_process_lab.py`, all passing, integrated with `tests/test_g4_write_security.py`. The combined latest Python suite is **173/173 PASS**, existing UI tests **3/3 PASS**, RDG Markdown docs audit PASS. These are synthetic, not production assurance.

| Scenario | Verified synthetic outcome |
| --- | --- |
| Genuine virtual WebAuthn UV Approve, exact ASK and request SHA | `EXECUTED` with exactly one fake POST, one reservation and valid event chain |
| PENDING request without owner decision | No reservation; zero fake POST, even with direct gate access |
| Trusted synthetic `ALLOW` | Permitted by shared executor, using `APPROVED → DISPATCHED`, one fake POST and one durable reservation; no ASK or owner credential required for a policy-permitted operation |
| Untrusted policy mismatch (`ALLOW` in Core but gate expects `ASK`, or vice versa) | Denied: event chain and trusted gate policy disagree; zero fake POST |
| Real owner WebAuthn Reject | Local `REJECTED` without fake POST |
| Tampered local `APPROVED` state but missing valid approval event | No POST; `UNCERTAIN`, not a successful bypass |
| Changed Issue before dispatch | `STALE`; zero POST and no reservation |
| Lost response **after** simulated upstream commit | One reserved fake POST, request `UNCERTAIN`, repeated dispatch refused |
| HTTP 429 before confirmed write | Conservatively one reserved fake attempt, `UNCERTAIN`; no blind retry |
| Wrong WebAuthn decision or request ID | No authorized dispatch |
| Parallel second call during the same fake dispatch | Guard detects reserved request UUID and rejects second POST |
| Owner UI + separate spawned worker | Real virtual WebAuthn approval leaves request `APPROVED` without any owner process POST; spawned fake worker commits one reservation and executes exactly one fake POST |
| Worker on `PENDING` / `REJECTED` / repeated request | Refuses to send, no fake POST and no second dispatch after successful execution |
| Direct `Core.execute` bypass in the owner process | `NoWriteTransport` prevents write; request becomes conservative `UNCERTAIN`, no worker retry |
| Simulated crash between fake POST and recording `EXECUTED` | After restarting the gate using the same temp SQLite, duplicate reservation is refused |
| PUT/PATCH, arbitrary POST route or arbitrary source transport | Rejected before any fake request |
| Competing editor **after last GET but before POST** | **RESIDUAL RISK REPRODUCED:** fake transition still executes (no server CAS) |

## Important limitations: why this is not yet a trusted production executor

1. **Trust in code, process launch and SQLite is assumed.** In the lab, anyone able to run arbitrary code in the worker or rewrite the local database can bypass the in-process guard. A separate spawned fake process does not by itself authenticate IPC or isolate host administrators. A production WRITE executor must have an independent OS/process/credential boundary and must not expose the underlying transport/token to untrusted code, AI, client gateway or generic admin endpoints. The lab does not claim physical prevention of POST by privileged malicious code.
2. **`LabSonar` is fake.** Its exact one-Issue behavior cannot establish actual Sonar permissions, request parsing, transport idempotency or remote audit. `LabPostGate` accepts only that concrete fake, so production integration **must not** be achieved by injecting a real transport into this lab. Future production code requires fresh architecture review and a **new artifact** without reusing the current G4 token volume or identity automatically.
3. **The Core controls authorization; the lab guard checks persisted evidence.** The event SHA is not a separate cryptographic signature verifiable outside the trusted host. The gate relies on the trusted owner-side SQLite's integrity and the real WebAuthn verifier having validated the decision. An external process or direct disk write by Docker/host admin is beyond this guard's security guarantee.
4. **The POST reservation gives at-most-one fake attempt, not exactly-once remote success.** After a crash between reservation and POST, the request can remain `UNCERTAIN` even if no write happened. Remote `ACCEPTED` status alone cannot attribute a POST to Fortis; no automatic retry and no silent reconciliation.
5. **Sonar has no atomic CAS for this transition.** A concurrent Sonar editor can change the Issue between preflight GET and POST. The synthetic test intentionally proves the current general adapter can still complete the transition in that race. This is an explicit residual WRITE risk, not closed by the extra lab gate.
6. **Owner-selected broad token permissions remain a conscious risk.** Fortis ASK limits actions inside the trusted pipeline only. Stolen tokens bypass ASK and could affect all accessible organizations. This lab has no real token. Production requires isolated token storage, host/backups risk review and revocation/runbook, not a mandatory narrow token.

## Release gate status after lab

| Gate | Current standing |
| --- | --- |
| G4-W0 Current G2/G4 unchanged | PASS in source work (no runtime operations performed) |
| G4-W1 Broad token custody + documented cross-org blast radius | OPEN (architecture accepted, host/executor risk still unreviewed) |
| G4-W2 ASK, WebAuthn exact authorization and bypass tests | PARTIAL LAB PASS; production boundary NOT IMPLEMENTED |
| G4-W3 No upstream atomic CAS; concurrency | OPEN / demonstrated residual risk |
| G4-W4 Durable one-shot attempts, uncertain response | PARTIAL LAB PASS; real executor and failure runbook OPEN |
| G4-W5 Owner preview and quality impact | OPEN for real WRITE version |
| G4-W6 Independent, reviewed production WRITE release | NOT IMPLEMENTED |
| G4-W7 Fresh owner authorization for a real test Issue/POST | NOT GRANTED |

**Next safe engineering step:** design a distinct trusted **process/container boundary and one-way exact-request execution interface**, with an owner-controlled token isolated from Repo/AI and from the current G4 state. Before any real SonarCloud POST, require a separate owner review and explicit authorization tied to a disposable test Issue. Do not copy or change the current live token, do not modify the G4 candidate, and do not touch G2.
