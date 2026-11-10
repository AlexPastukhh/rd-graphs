# Fortis live Sonar E2E evidence — 2026-11-03

> **СТАТУС: LIVE EVIDENCE SNAPSHOT.** Секреты, machine grant, token, WebAuthn proof и private volume contents не включены.

## Environment and scope

- Caller: Fortis Repo process execution in the active `fortis-repo-test` container (owner-reported ID `04fed7b726a8536d63c4d2533cfc7ee3072956ff0c3f571504d7f709f7909030`).
- Client: `fortis_approvals.repo_sonar_tools` (typed client, not a direct Sonar token client).
- Repo client mount: `fortis-r7-client` → `/run/fortis-client`, `RW=false`; it contains the machine grant and public R7 certificate only.
- Gateway: R7 machine ingress at fixed `https://host.docker.internal:19104`, TLS 1.3; Owner UI at `http://localhost:19103`.
- Organization: `alexpastukhh`.
- Project: `AlexPastukhh_obs-planning-docs`.
- R7 server volumes: `fortis-r7-state` (`/state`, RW), `fortis-r7-identity` (`/run/r7-identity`, RO), `fortis-r7-grant` (`/run/r7-grant`, RO), `fortis-r7-sonar-token` (`/run/r7-sonar-token`, RO).
- Repo→R7 routes: `POST /v1/reads`, `POST /v1/actions`, `GET /v1/requests/{requestId}`. Sonar READ routes are GET-only inside R7.

## Live READ

The typed client successfully called project listing, issue listing, Quality Gate and exact issue read:

- One pinned project was visible.
- Sonar reported 275 Issues; page 1 returned 100 and `hasMore=true`.
- Quality Gate: `OK`.
- Scope: `CURRENT_DEFAULT_BRANCH`.
- PR/SHA binding: `NOT_VERIFIED_D2`.

The result is a live page, not a cross-page point-in-time snapshot. It does not claim that all 275 issues were read or that the Quality Gate is bound to a specific PR/commit SHA.

## Live ASK, owner Reject and owner Approve

### Reject path

Request `67eaccd8-24dc-4eeb-a7da-547b334bcdc5` was created through the typed `sonar.propose_accept_issue` path for Issue `AaGC4d7SJxEkuf26a_Wg`.

- Immediately after creation, Fortis request state was `PENDING`.
- Owner reviewed the exact request in the R7 Owner Portal and selected Reject.
- A subsequent typed Fortis request-status read returned `REJECTED`.
- Reject returns without adapter dispatch; no Sonar mutation is expected.

### Approve path

Request `2b1e6b0f-7c4e-4dd2-bc4b-81c93e6c0d2f` was created through the same typed path for Issue `AaGC4d7SJxEkuf26a_Wh`.

- Immediately after creation, Fortis request state was `PENDING`.
- Owner confirmed the exact frozen request with the registered WebAuthn flow.
- Fortis request status became `EXECUTED`.
- The independent typed Sonar GET returned status `ACCEPTED`.

## What this proves

- Fortis Repo can obtain real Sonar data through R7 without receiving the Sonar token.
- The typed Repo client can create a real owner approval request.
- Owner approval is connected to the execution path; after owner confirmation the request becomes `EXECUTED` and Sonar readback is `ACCEPTED`.
- Reject is a separate terminal path: the request becomes `REJECTED` and the adapter is not dispatched.
- The Approve result is a real Sonar status transition, not an offline fixture.

`ACCEPTED` is a Sonar Issue status transition. It does not fix source code or prove the reported code smell has been corrected.

## Evidence limits

- This report records request-state and remote readback results. It does not include owner DB rows, private receipts, token material, or raw network traces.
- The implementation's approved execution path performs a final issue re-read, one typed `accept` POST, independent GET readback and durable result recording. This report itself does not independently count packets/POSTs.
- The Reject Request ID is retained here (`67eaccd8-24dc-4eeb-a7da-547b334bcdc5`); the `REJECTED` status was read back, while no packet trace was captured. Reject must remain no-dispatch/no-POST by implementation contract.
- The scenario reads the latest available Sonar data; it does not dispatch a new GitHub Actions workflow or trigger a new Sonar analysis.
- The report covers one actor and one pinned project. It is not multi-agent or full production supply-chain acceptance.
