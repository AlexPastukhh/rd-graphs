# Fortis Repo → Approvals ingress v1 — verified offline, NOT deployed

> **Исторический срез 2026-10-31.** Утверждения ниже вида «Repo→Windows не работает», «только offline», «A3 не развернут» и старые числа тестов описывают состояние **на тот момент**, а не актуальный факт. **2026-11-01: A4 synthetic Repo→Windows A3 TLS/ASK/ALLOW/Reject и Windows ACL/status PASS; production admission и Sonar READ в едином Fortis OPEN.** Действующие статусы/задачи — в [основном плане §12–14](../../docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md). Owner решил **отложить** процедуры ручной замены TLS и выдачи/отзыва machine access до production admission; ближайшая работа Sonar READ offline без реального токена.


**Date:** 2026-10-31. **Stage 2 status:** WSGI source/API and *one ephemeral loopback wire test* implemented. **No production Fortis Repo ↔ Windows connectivity, no route exposed on G2/G4, no new persistent listener/Compose service, no Sonar credential usage or remote write.** Do not install this package over an owner-side container.

## Roles and endpoint contract

**TARGET UPDATED 2026-10-31:** ONE Fortis Secure Gateway on Fortis_M contains BOTH private token store and Approvals/owner UI and typed execution. The `RepoIngress` code is the machine-facing **route** of that single container, not a separate service/container; owner WebAuthn uses separate authorization paths. A secret-needed `ALLOW` action is executed immediately, and a secret-free `ASK` action waits for owner approval; token necessity and ASK necessity are independent. Previous split-executor recommendations are superseded. **Source tests still use fake tokens only.**

Fortis Repo is an **untrusted requester**. It owns no SonarCloud/RDG token and no owner WebAuthn proof. A restricted Fortis Repo ingress credential, independently issued/managed by the *trusted Approvals host*, authenticates the principal. Core/`RepoIntentBroker` then apply independently trusted per-actor service/operation grants and `DENY/ALLOW/ASK`. There is **one** `Core.execute()` path after trusted `ALLOW` or WebAuthn-approved `ASK`; `DENY` and `Reject` never dispatch. The privileged service token belongs in a **private vault in the SAME trusted Fortis container**. Repo actor and owner web routes cannot retrieve token bytes. Separate actor authorization is a route constraint, **not** a mandatory second container.

The new module [`repo_ingress.py`](../repo_ingress.py) provides a **WSGI application only** with exactly two routes:

| Route | Input | Success output | Never exposes |
| --- | --- | --- | --- |
| `POST /v1/actions` | Closed six-field intent, `Content-Type: application/json`, independent `Authorization: Bearer <ingress grant>`; 8 KiB max | `200 {requestId,state}` on non-PENDING or `202 {requestId,state}` for ASK `PENDING` | Sonar token, private Issue projection, Core fingerprint, policy internals, owner cookies |
| `GET /v1/requests/<canonical-uuid>` | Same distinct ingress grant; no request body | `200 {requestId,state}` for actor-owned requests only | Other actors' requests, owner history, remote Issue details |

There are **no** `owner`, `approve`, `reject`, `token`, `execute`, arbitrary URL/method, proxy, shell, generic REST forwarding or direct Sonar endpoints. Unknown routes and methods return `404`. The owner panel remains an independently authenticated browser interface (not mounted into this ingress).

Use the strictly defined intent in [`FORTIS-REPO-ACTION-CONTRACT-V1.md`](FORTIS-REPO-ACTION-CONTRACT-V1.md). The Repo caller **does not** send Sonar digest/transition or a flag `approved=true`; the trusted broker obtains the current digest from a typed adapter and Core selects policy. For Sonar `accept_issue`, policy **MUST remain ASK**; the current G4 candidate additionally blocks Approve and `NoWriteTransport` blocks POST. The current lab contains no external Sonar token or network transport.

## Source-side defenses, with precise limits

- **Authentication:** Reject missing or malformed Authorization; `Core.auth.authenticate` checks a distinct test-only ingress grant. Production grant creation, secure distribution, rotation/revocation, hashed/secret-store handling and permissions are **not implemented**. Do **not** reuse a SonarCloud access token as the ingress grant or store it in Repo.
- **TLS / origin:** Reject non-HTTPS requests by default; special `allow_http_local_test=True` constructor flag is restricted to a `localhost` / `127.0.0.1` Host and loopback peer for *offline tests only*. **Production must not enable that flag.** In production, set up authenticated ingress/L4 isolation, correctly trusted TLS termination or mTLS, verify backend socket access and the actual WSGI scheme. `wsgi.url_scheme` alone does **not** prove a remote peer's identity. No production server or certificates are shipped.
- **No browser credentials:** Reject cookies, `Origin`, `Referer`, CSRF headers, method-override, forwarding/proxy headers, query strings, changed Host and `Transfer-Encoding`. This is a server-to-server API; no CORS/owner session access. Check the real reverse proxy for canonical Host, stripped forwarded headers, auth-log redaction and no public fallback route.
- **Payload:** Enforce POST-only JSON and exact content length, 8 KiB cap, strict UTF-8, duplicate key rejection (including nested), `NaN`/Infinity rejection and closed typed schema. Disallow unknown top-level or operation fields, arbitrary URL/method/token/owner/policy. The backend still checks replay UUID, actor grants, domain scope, snapshot and policy independently.
- **Response:** Return only `requestId` and `state`; use constant public error categories (unauthorized, denied, conflict, invalid, rate limited, uncertain) without upstream body, private Sonar Issue message, auth header, token bytes or event digest. No-store and nosniff response headers. A `202 PENDING` is **not** a successful Sonar mutation.
- **Rate limit:** Per-authenticated-actor in-memory sliding window (default 30 requests/60 seconds, configurable in **trusted source construction**, not caller JSON), denies excess with `429`. It is **not shared between processes** and is reset on restart; it does **not** throttle unauthenticated credential guessing. **Production requires an external per-source/per-actor ingress rate limiter, request timeouts, a secret rotation plan and durable metrics.** This is defense in depth only.
- **Idempotency:** Core is request-ID keyed. A repeated identical ID returns the existing request, while an altered request with the same ID returns conflict. No automatic reissue after Sonar `UNCERTAIN`; status remains actor-scoped.

## Verification: exact scope

`tests/test_repo_ingress.py` contains **11 new tests** in addition to the existing 12 type-contract tests. All tests use an ephemeral isolated SQLite directory and `UnifiedFakeSonar` (in-memory GET, POST disabled) with synthetic actor keys, never a real token. Test cases cover trusted synthetic `ALLOW` immediate, synthetic `ASK` delayed and then owner WebAuthn/session approval via the same Core; Sonar ASK pending/owner WebAuthn Reject and zero POST; rejection of owner/execute/proxy routes; missing/wrong actor token; cross-actor status; forged Origin/Cookie/Host/proxy/method override; HTTPS-only default and loopback test mode; duplicate/malformed JSON, oversized/invalid content length; in-memory rate limit; UUID idempotency/conflict and redacted output.

**One test opens an actual TCP socket at `127.0.0.1:<ephemeral>` INSIDE THE FORTIS REPO LINUX TEST ENVIRONMENT**, submits synthetic `ALLOW` over HTTP using a **fake ingress grant**, queries status, then closes the HTTP server and socket. This is **not** a Windows/G2/G4 network test; it does not bind `18990`/`18991`, make a SonarCloud request, copy owner data or persist any endpoint.

**Acceptance (2026-10-31): 204/204 Python PASS; 3/3 JavaScript UI PASS; RDG doc audit PASS.** These results prove test-only WSGI handling and in-memory authorization integration. They **do not** prove secure production TLS/mTLS, a provisioned client identity, actual Fortis Repo→Fortis_M connectivity, or owner-only secret custody and typed service execution inside the selected single Fortis container. A separate Approvals→Executor IPC is NOT an acceptance gate.

## Next release prerequisites (no owner action executed)

1. Design/authenticate an actual constrained **Repo→Approvals transport** (which host/network, TLS/mTLS or equivalent, inbound ACL, trusted origin, private ingress grant provisioning outside Repo source and logs, actor-specific access rules, no owner routes). Avoid guessing that the Fortis Repo plugin can reach Windows `localhost`; the Repo container's `localhost` is its **own** network namespace.
2. Add a typed secret-aware adapter **inside the same trusted Fortis container**: owner-only token volume, server-selected credential, read/snapshot, exact one-shot dispatch and readback; no machine/owner route for raw tokens or arbitrary HTTP. No additional container/IPC is currently required; stolen-token/host bypass remains an open risk.
3. Run a *new isolated* single-system Windows candidate with an owner-controlled origin, separately provisioned ingress identity and disposable test state, without changing active G2/G4 or mounting their token volumes. Perform explicit owner acceptance.
4. Only after separate security review and **specific owner authorization** consider one disposable real Sonar Issue WRITE. Preserve at-most-one attempt, human `UNCERTAIN` runbook and disclosed GET→POST non-atomic race.

**Current verdict: ingress SOURCE/EPHEMERAL LOOPBACK LAB PASS; operational Repo↔Windows route NOT BUILT; one owner-trusted Fortis with its internal secret store and typed executor NOT DEPLOYED; real SonarCloud WRITE NO-GO.** Source changes were not staged or committed, running G2/G4 untouched.
