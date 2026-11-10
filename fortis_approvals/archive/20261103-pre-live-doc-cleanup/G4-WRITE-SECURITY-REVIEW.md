# G4 SonarCloud WRITE — architectural security review and release gates

> **STATUS NOTE (2026-10-31 OWNER SUPERSESSION):** This file retains the original threat review and synthetic lab observations, **not the active deployment architecture**. The owner now requires **ONE trusted Fortis container** containing ingress/policy, owner ASK/WebAuthn, private secrets and typed execution. Any recommendation here for a *mandatory* separate executor container/IPC, separate privileged account or narrowly scoped Sonar token is **SUPERSEDED**. Security risks, source tests and real Sonar POST prohibition remain valid; see [`G4-WRITE-PRIVILEGED-TOKEN-ADR.md`](G4-WRITE-PRIVILEGED-TOKEN-ADR.md) and the main Fortis plan §0–1.


**Review date:** 2026-10-31. **Review basis:** checked `fortis_approvals` source/tests and current SonarQube Cloud public documentation. **Decision: NO-GO for production or real POST.** This is a *review and future design*, NOT an approved WRITE build, credential request, permission elevation or operator runbook for live mutations.

**Architecture decision (owner clarification):** [`G4-WRITE-PRIVILEGED-TOKEN-ADR.md`](G4-WRITE-PRIVILEGED-TOKEN-ADR.md) is authoritative for credential trust: **broad Sonar token by design; Fortis policy/ASK is the intended restriction**. A dedicated low-privilege Sonar user/token is an optional additional mitigation, **not a required architecture gate**. Token theft bypasses Fortis ASK, so independent secret custody, strong executor isolation and explicit blast-radius risk review remain mandatory. Real Sonar POST remains NO-GO until the new WRITE implementation and authorization gates pass.

**Existing accepted baseline:** owner on Windows confirmed real Sonar EU READ -> Fortis G4 ASK Pending -> owner WebAuthn Reject (PIN user verification) -> local History `REJECTED` -> exact request-ID read-only SQLite/Sonar GET readback (`OPEN`, same normalized Issue SHA). See [`SECURITY-REVIEW-G4.md`](SECURITY-REVIEW-G4.md). **The deployed `fortis-approvals-g4` port 18991 is READ/ASK/Reject ONLY. G2 on 18990 must not be modified.** An earlier readback bug choosing by issue rather than exact request ID was fixed; this remains part of the negative test baseline.

## Owner clarification — credential spans organizations (2026-10-31)

**Owner-reported fact:** the current Sonar credential is **not restricted to one
organization**; it reaches the owner's accessible organizations. This is
consistent with a *Personal Access Token (PAT)*, which authenticates as the
issuing user and receives their permissions across all organizations/projects
where that user has access. **The exact token type has not been independently
inspected**, so this is not proof that the installed credential is a PAT.
A *Scoped Organization Token (SOT)* is a distinct organization-attached token;
Cloud currently documents only `Execute analysis` for its permission scope,
not Issue Accept. Do not describe the existing token as an SOT, or as
organization-scoped, without owner-side proof.

**Two independent scopes:** the deployed G4 Compose config restricts app
queries to `FORTIS_G4_ORGANIZATIONS: alexpastukhh`, but this is only a
**software allowlist**. It cannot attenuate or revoke permissions embodied
by an account-wide user credential: anyone extracting the token from the
unencrypted Docker volume, process memory, host backups or privileged Docker
access can use the credential **outside Fortis** against any other accessible
organization/project, consistent with that user's rights. Likewise, adding
new authorized organization keys to Fortis READ discovery does not broaden
or narrow the underlying token rights. Never conflate application query
scope with credential authorization or a network firewall.

**WRITE effect (superseded credential policy):** Owner has clarified that a broadly privileged account token is the **intended model**; Fortis's *server-side* policy/ASK boundary is the enforcement layer for requests flowing through Fortis. **Do not require creation of a separate narrow Sonar identity/token as a prerequisite.** A token taken outside the trusted executor can bypass ASK, so B1/W1 are **OPEN for credential custody, host isolation, scope inventory, expiry/revocation procedures and an explicit review of residual cross-organization exposure**, not BLOCKED merely because token privileges are broad. The owner has not authorized a live POST or explicitly signed off all residual consequences.

**Official SonarCloud sources:** [PATs](https://docs.sonarsource.com/sonarqube-cloud/managing-your-account/managing-tokens),
[SOTs](https://docs.sonarsource.com/sonarqube-cloud/administering-sonarcloud/managing-organization/scoped-organization-tokens),
[project permissions](https://docs.sonarsource.com/sonarqube-cloud/managing-your-projects/administering-your-projects/setting-permissions).

## 1. Present controls (code evidence; not live WRITE acceptance)

| Boundary | Source | Present status and limits |
| --- | --- | --- |
| Sonar writer blocked in G4 | `g4_candidate.py`: `NoWriteTransport.call` | Only `GET` reaches underlying transport; every non-GET raises `SONAR_G4_CANDIDATE_WRITE_DISABLED`. Verified synthetically, not by independent egress capture. |
| Owner cannot approve Sonar | `g4_candidate.py` creates `OwnerPortal(...blocked_approvals={G4_OPERATION},strong_operations={G4_OPERATION},read_only_banner=True)`; `owner_portal.py` `_approval_allowed` | Approve refused on session, WebAuthn begin and finish paths and disabled in UI; Reject remains authorized after owner verification. Synthetic G4 test covers all three owner routes. |
| ASK server-side, exact payload | `core.py` `submit/owner_decide`, `g4_candidate.py` `propose_issue` | Fixed `sonarcloud/accept_issue`; checks fingerprint over actor, request, policy version and immutable preview; `PENDING` can become `REJECTED` or, in a *future* separately approved candidate, `APPROVED`. Browser/AI fields `approved=true` cannot be accepted as proof. |
| WebAuthn decision | `owner_auth.py` `_begin_assertion`, `_finish_assertion`, `verify`; `owner_portal.py` | Strong decision proof uses UV-required WebAuthn assertion bound to owner session, exact request ID/fingerprint and `approve` or `reject`; CSRF+Origin checked on owner POST. Local PIN is not sent to Fortis. Existing real verification tested **Reject**, not Approve. |
| Target and transport allowlist | `sonar.py` `SonarIssueAdapter._check_request/_before` and `SonarHTTPTransport.call` | Typed fixed EU/US HTTPS, path/params allowlist, no redirect/proxy, only `accept` transition in payload, organization discovery on every decision, digest and offered transition checked. The underlying general adapter **contains a POST implementation**, but the present G4 wrapper blocks it. |
| Preflight and no blind resend | `core.py` `execute/reconcile`; `sonar.py` `apply/receipt/confirm` | Frozen preview re-checked before `DISPATCHED`, adapter checks again before POST, `DISPATCHED` persisted before effect; only confirmed POST+GET readback gets receipt. Lost outcomes remain `UNCERTAIN`, no automatic retry; receipt-only reconciliation may not recover a lost upstream response. Tested with fake Sonar. |
| Host/credential separation | `deploy/compose-g4.yaml`, `g4_secret_bootstrap.py`, `g4_volume_repair.py` | G4 binds `127.0.0.1:18991`, non-root, read-only root FS, token volume mounted `:ro` in server; token stored unencrypted in private Docker volume with `0600`. Docker/Windows administrators or compromised local host can read it. Current Sonar token **type, expiry and actual grants unknown**. G2 volumes and identity remain independent. |

## 2. Findings and blocking decisions

**B1 — CRITICAL: broad token custody and blast radius, by owner-selected design.** The owner confirms Sonar credentials provide broad access across accessible organizations; Fortis is intended to enforce fine-grained policy with mandatory ASK. This is a legitimate **trust assumption**, not evidence that SonarCloud credentials are technically narrow. Any extracted token can be used directly against SonarCloud beyond Fortis, so ASK **cannot** prevent out-of-band misuse. A different PAT from the same account would have the same underlying rights; a dedicated narrower account could reduce risk but is **not mandatory** for this architecture. Before live WRITE, review who can read token bytes (Windows/Docker admins, volume backups, process memory, untrusted mounted code), prohibit AI-side token access and arbitrary HTTP operations, verify issuer/type/expiry for incident response, define fast revocation/rotation and require explicit owner acceptance of the remaining cross-organization exposure. Broad privileges are **not by themselves a policy violation**. Lack of strong privileged-executor isolation and recovery procedures **is a blocker**. A successful READ or offered `accept` transition is not proof of WRITE authority.

**B2 — CRITICAL: production WRITE trust boundary not designed.** The owner panel, token-holding process and Core in today's G4 must never be switched to write-capable by a browser flag, Compose environment variable, removed `blocked_approvals`, a modified `NoWriteTransport`, or an AI-delivered payload. Instead design a separately reviewed versioned owner-side executor: no public generic method/path endpoint; no browser-provided URL/token/actor; exact Sonar Issue action and scope from a trusted configuration; only a previously persisted, independently WebAuthn-approved request with matching request ID/fingerprint may dispatch. Its privileged credential must not be reachable by Repo/AI processes. Prefer separate named volumes/Compose project for synthetic trial, rather than migrating/overwriting the active G4 identity/DB/credentials.

**B3 — HIGH, residual by API design: GET → POST is not atomic.** `expectedIssueSha256` is a local snapshot digest, **not** a Sonar server-side compare-and-swap. Even the extra GET in `SonarIssueAdapter.apply` cannot exclude a concurrent Sonar writer between that GET and the transition POST. Treat any project where concurrent editors can change the target Issue as unacceptably risky without explicit owner acceptance of this residual race. The controlled first test must use a disposable Issue, coordinate no other editing, fail closed on any digest/transition difference and document that concurrency exclusion is **operational**, not a guaranteed API transaction. Never label this as strict CAS.

**B4 — HIGH: uncertain dispatch cannot be automatically reconciled from Sonar Issue state.** `Core.execute` persists `DISPATCHED` before the external effect and marks failures `UNCERTAIN`; `Core.reconcile` consults only the locally stored adapter receipt. A POST may succeed upstream but its response/confirmation could be lost before the receipt was saved. Sonar `ACCEPTED` alone cannot prove which writer caused it. No automatic retry, blind replay or silent `UNCERTAIN → EXECUTED` is authorized. A **human-owned manual incident runbook** must define GET-only inspection, Sonar audit attribution where available, pause/quarantine of the request, and explicit final outcome `unresolved` when attribution is impossible. Recovery must never issue a second POST for the same request.

**B5 — HIGH: accepting an Issue affects quality reporting, not just its label.** SonarQube Cloud documents that an accepted Issue is ignored in quality reports/ratings, and related metrics or quality gate can change. The approval preview must state exact `OPEN → ACCEPTED`, project, Issue, rule/severity/message, rationale, impact warning, frozen before digest, any relevant current Quality Gate, and the limits of the impact estimate. No issue selection by AI alone for first live test; owner must consciously nominate a disposable test Issue and understand the Quality Gate side effects. No automatic revert is safe or promised.

**B6 — HIGH: local token security and renewal need an owner runbook.** `Read-Host -AsSecureString` is converted into managed plaintext and piped into a temporary Docker container; token remains **unencrypted** at rest in Docker volumes and process memory while in use. File permissions do not protect against Docker/host admins, backups or malware with equivalent privileges. No shipped rotation, revocation, secure deletion, inventory of token expiry or host compromise response. A future WRITE version needs owner-approved rotation/revoke and retention policy, backup restrictions, redacted logs and a threat model of Windows Docker Desktop access; this is not a reason to request token material through chat or Repo.

**B7 — HIGH: read-only candidate must remain independently verifiable.** Current automated tests cover a synthetic POST adapter and a separate READ-only integration. They do not constitute a live WRITE approval, upstream token privilege proof, Browser/WebAuthn attack simulation against a write-capable release, or observed outbound HTTP method count. The exact-request-ID readback regression illustrated why request identity, not only Issue identity, is part of the authorization proof. Preserve current READ/Reject tests and require a new independent negative suite for any future WRITE artifact.

**B8 — MEDIUM: Sonar API compatibility and rate-limit assumptions.** Cloud documents V1 endpoints in-instance and gradual V2 migration; on release, verify the *specific* version of `/api/issues/do_transition`, response shape, transition eligibility, errors and API 429 semantics from authoritative instance docs without sending POST. Errors after an attempted POST remain `UNCERTAIN` until manually reconciled; rate limiting is not a reason to retry non-idempotent writes.

## 3. Proposed future architecture (design only; NO implementation or live change)

```text
Untrusted AI / caller
    -> trusted, typed proposal gateway (scope restrictions, no Sonar credential)
    -> separate owner-controlled immutable ASK store
    -> owner-only UI on loopback, exact preview + strong WebAuthn UV approval
    -> independently reviewed dispatch authority bound to request ID/fingerprint
    -> isolated WRITE executor (owner-held broadly privileged token)
    -> GET snapshot/transition preflight (may return STALE)
    -> durable DISPATCHED marker BEFORE effect
    -> at most one Sonar POST for exactly accept on exactly one test Issue
    -> GET readback, receipt, immutable audit evidence (or UNCERTAIN)
```

**Mandatory boundaries:** Core and transport policy must enforce a fixed action even if UI/CLI is bypassed; owner-side grant does not permit a generic writer, different Issue, project or transition. No token or Docker daemon socket accessible from Repo. No shared G2/G4 volume or credential. No automatic retries on ambiguous outcomes. The display/owner credential remains independently tied to the approved request; a PIN prompt is not itself authorization without verified WebAuthn assertion and exact fingerprint. A separate sign-off is required for each real mutating test.

## 4. Release and negative-test gates (all required before first real POST)

| Gate | Required evidence | Current assessment |
| --- | --- | --- |
| G4-W0 Preserve live environments | G2:18990 and G4:18991 unchanged; all current Reject/GET-only tests PASS; no new POST-capable route in their deployed images. | **PASS for current candidate; ongoing invariant** |
| G4-W1 Privileged token custody / blast radius | Owner-managed broadly privileged token is permitted by architecture. Verify true multi-organization authority, expiry/revocation, file/memory/backup/host access, isolated executor custody and owner review of residual risk. Separate narrow token is optional defense in depth. | **OPEN: isolation + risk sign-off** |
| G4-W2 Authorization and bypass isolation | No AI/HTTP direct write; exact immutable request fingerprint, separate WebAuthn Approve proof with UV, Origin/CSRF, replay/stale/foreign project/actor/boundary negative tests. | **BLOCKED for new WRITE artifact** |
| G4-W3 Race analysis | Explicit statement of missing server CAS; fail-closed stale/missing transition; controlled single test Issue and residual concurrency acceptance. | **BLOCKED** |
| G4-W4 Dispatch/uncertainty | One-shot durable marker, independent attempt counting in synthetic fault injection; crash before/after dispatch; POST success/lost response, 429/500/timeouts, process crash; no second POST; manual reconciliation runbook. | **BLOCKED** |
| G4-W5 Owner-visible change impact | Exact preview, expected status, quality-report/Quality Gate warning, constrained pilot target and audit evidence retention/redaction. | **BLOCKED** |
| G4-W6 Independent release | Reviewed source and dependency versions, SHA-256 verified separate package, dedicated isolation/rollback without touching live G4 or G2, no privilege-enabling environment switch. | **BLOCKED** |
| G4-W7 Explicit test permission | Fresh owner permission for **one** nominated disposable Issue and one exact operation, after security gates; no automatic POST authorized by this review. | **NOT GRANTED** |

### Synthetic negative matrix, before any real WRITE

- Forge `approve`, owner ID, CSRF, credential, session, fingerprint, request ID; replay WebAuthn assertion; change action, project, Issue, transition or organization after approval. **Expected: no POST**.
- Approve while request is rejected, expired, stale, pending with missing strong proof, or policy changed; `ALLOW` bypass or direct `Core.execute` call. **Expected: no unauthorized POST**.
- Change issue after proposal, during owner review, before dispatch, after final GET; remove `accept` transition; use duplicate/malformed/missing Issue API response. **Expected: fail closed** before dispatch when detectable; document unavoidable post-GET race.
- Crash before persist, after `DISPATCHED` before send, after upstream commit before response, after response before receipt, after receipt before local `EXECUTED`; concurrent owner clicks and retry requests. **Expected: max one dispatch attempt for that request**, no blind retry, unresolved outcomes remain `UNCERTAIN` unless durable receipt can prove it.
- Permission 401/403, rate limit 429, 5xx, TLS failures, timeout, redirect, unexpected response, bad readback. **Expected: no secret disclosure or credential echo; status reflects uncertainty if POST may have left host; never retry blindly**.
- Verify G2/G4 mounts/ports, disabled current READ-only Approve, secrets absent from logs/review snapshots, and independently inspect outbound request methods on a synthetic test network. **Expected: no real Sonar POST, no G2/G4 behavior change**.

## 4A. Isolated synthetic owner proof: results and reproducible limits

`tests/test_g4_write_security.py` composes the existing Core, Sonar adapter,
owner portal and `OwnerWebAuthn` with a **FakeSonar in-memory transport** and
a **virtual FIDO2/P-256 key**, using only ephemeral temporary SQLite files
and a test-only `http://localhost:18992` origin. No real container, token,
HTTP listener, Sonar network call, or deployable WRITE configuration exists.
The deployed G4 retains `NoWriteTransport` and blocked Approve.

The new negative/security cases cover: true strong WebAuthn Approve for a
single synthetic request; no session-only shortcut; no missing Origin/CSRF,
no anonymous/forged session; wrong request ID or wrong decision binding;
reject then approve refusal; missing UV flag; stale remote Issue; forged
client `approved`/`owner` and wrong scope/action; and after-dispatch timeout
or HTTP-429 with exactly one FakeSonar attempt followed by `UNCERTAIN` with
no retry/reconciliation claim. The complete Python suite now has **154/154
passing tests** as of this review update.

**Important reproduced blocker:** the test
`test_get_post_race_residual_risk_is_reproduced_with_fake_sonar`
changes the fake upstream Issue **after** the adapter's final GET but
**before** the fake POST. The existing generic adapter can still complete
the transition and return `EXECUTED`. This demonstrates the **absence of
atomic CAS** in the model; it is not a pass on concurrent-writer safety.
The first real WRITE remains NO-GO until the residual risk is explicitly
accepted for an isolated disposable test, or upstream conditional mutation
becomes available and is independently verified. These synthetic results
satisfy **part** of the negative-test design for W2/W3/W4, not the release
requirements for a separate production writer.

The next permitted external step is a *read-only metadata inventory*, not
credential creation. See [`G4-WRITE-OWNER-INVENTORY.md`](G4-WRITE-OWNER-INVENTORY.md)
for SonarCloud UI inspection and safely reportable categorical findings.

## 4B. Shared Core executor laboratory (173 Python PASS, offline only)

The next engineering iteration implements
[`g4_write_lab.py`](../g4_write_lab.py) and
[`tests/test_g4_write_lab.py`](../tests/test_g4_write_lab.py), with full
operator-facing evidence in
[`G4-WRITE-LAB-ACCEPTANCE.md`](G4-WRITE-LAB-ACCEPTANCE.md).
Owner architectural correction: **trusted ALLOW and approved ASK merge at
one `Core.execute()` dispatch path**. The initial gate accepted only ASK; it
now validates either trusted policy's distinct event chain, then uses the
same one-shot reservation and fake adapter. Two regression tests prove a
trusted synthetic ALLOW succeeds with no WebAuthn and a policy mismatch
fails closed. G4 Sonar `accept_issue` retains ASK as its required rule.

The in-memory-only `LabSonar`/`LabPostGate` authenticates the **exact durable
ASK and WebAuthn approval** before a strictly typed simulated POST, and
persists a one-shot attempt reservation before the fake side effect.
`tests/test_g4_write_process_lab.py` adds **three actual subprocess cases**:
the owner-side `ProcessOnlyOwnerCore` with a `NoWriteTransport` records
WebAuthn `APPROVED` without dispatch, a spawned synthetic worker validates
the stored exact request and performs one fake POST, and the process split
refuses pending/rejected/replayed work. This is not an authenticated IPC or
container credential boundary; no real HTTP/token is present.
Negative tests include `ALLOW` bypass, PENDING/REJECTED/stale state, forged
owner state missing approval events, concurrent second POST, process-restart
reservation replay, 429/lost response and wrong-method/route denial. **All
173/173 Python tests, 3/3 UI tests and docs audit PASS**. This is not
production isolation: privileged in-process code or host administrators
could bypass the lab guard, no real credential/socket/API client is present,
and the Sonar GET→POST race remains unprevented. The live G4 Docker image
does not include the lab module. The broad-token + Fortis ASK owner model
remains in force; WRITE release gates G4-W1, W3, W5, W6, W7 remain OPEN.

## 5. Next authorized action (non-mutating)

**Only a credential-trust-boundary and release-design review.** The owner-safe checklist [`G4-WRITE-OWNER-INVENTORY.md`](G4-WRITE-OWNER-INVENTORY.md) now focuses on the selected broad-token + Fortis ASK model. The owner may review token metadata, account permissions/expiry and the risks of storage and recovery **without** revealing a token or creating a new account. A narrowly privileged Sonar identity is optional, not a prerequisite. Fortis must protect the token and enforce ASK in the trusted executor. The existing token remains as-is and READ-only G4 continues running. The developer can separately model the synthetic WRITE threat cases in an isolated container and produce an audit package. **Do not enable Approve, request a real token, issue a Sonar POST, create a new passkey invitation, rotate/delete existing volumes, or change G2/G4.**

## Public documentation consulted (2026-10-31)

- SonarQube Cloud issues/Accept, quality reports: <https://docs.sonarsource.com/sonarqube-cloud/managing-your-projects/issues/editing>
- Cloud project permissions, `Administer Issues`: <https://docs.sonarsource.com/sonarqube-cloud/managing-your-projects/administering-your-projects/setting-permissions>
- Cloud scoped organization tokens and current `Execute analysis` limitation: <https://docs.sonarsource.com/sonarqube-cloud/administering-sonarcloud/managing-organization/scoped-organization-tokens>
- Cloud personal access tokens, token creation/revocation and issuer permission scope: <https://docs.sonarsource.com/sonarqube-cloud/managing-your-account/managing-tokens>
- Cloud Web API V1/V2, method/endpoint/HTTP status: <https://docs.sonarsource.com/sonarqube-cloud/appendices/web-api>

**Audit status: ARCHITECTURE CORRECTED TO OWNER MODEL / WRITE RELEASE STILL BLOCKED.** This document records a design assessment, not proof of a production-safe writer. Subsequent approval must be a separate, explicit owner decision with a new artifact and separately reviewed credentials.
