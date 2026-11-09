# Fortis deployment artifacts — current index

> **СТАТУС: ДЕЙСТВУЮЩИЙ УКАЗАТЕЛЬ.** R7 P2 is already deployed and live E2E has been exercised. This directory contains both current references and historical scripts.

## Current runtime

- Current runtime: one R7 Unified Gateway container with Owner Portal, machine ingress, Core and typed Sonar adapter.
- P2 image ID: `sha256:e751f6ca0cfe6ce290cf580de2f243071ee1f3e681baa8827c6cea41a16fa402` (Windows build/audit and deployment/health owner-reported; live Repo→R7→Sonar E2E independently exercised).
- Existing GO-1 provisioning, GO-2 R7 startup/owner enrollment and GO-3 Repo read-only client mount are complete. Do not rerun them.
- No additional volume is needed for the current single-actor pilot.

## Current evidence and design references

- `compose-r7-p2-20261103.yaml` — versioned P2 runtime configuration reference; not a routine command to rerun.
- `Audit-R7-P2-Windows-ImageOffline-20261103.ps1` and `Build-R7-Windows-ImageOnly-p2-20261103.ps1` — historical build/audit scripts for the already built image; rerun only after a new source package/image is intentionally prepared.
- `R7-P2-WEBAUTHN-EXECUTE-SOURCE-REVIEW-20261102.md` — archived source review, superseded by live evidence.
- Current operational status and limits: `../../docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md`.
- Live request/readback evidence: `../evidence/FORTIS-SONAR-LIVE-E2E-20261103.md`.

## Historical only — do not use as current deployment instructions

G2, G4, R4, R5, A3, old R7 P1/v2 candidates, old provisioning/preflight/cutover/rollback scripts and their dated runbooks are retained for provenance. They are not parallel production services and must not be started, reprovisioned or rolled back as part of ordinary Sonar work.

Old cutover/provisioning docs and source reviews are byte-preserved in `../archive/20261103-pre-live-doc-cleanup/`. Dated handoffs under `docs/handoffs/` are immutable history; their next-step text is superseded by the current-state document.

## Runtime map (reference only)

| Container role | Volumes | Exposure |
| --- | --- | --- |
| R7 Unified Gateway (Compose service `fortis`; current generated name owner-reported as `fortis-r7-p1-fortis-1`) | `fortis-r7-state` → `/state` RW; `fortis-r7-identity` → `/run/r7-identity` RO; `fortis-r7-grant` → `/run/r7-grant` RO; `fortis-r7-sonar-token` → `/run/r7-sonar-token` RO | `127.0.0.1:19103` Owner Portal; `127.0.0.1:19104` TLS machine ingress |
| Fortis Repo (`fortis-repo-test`) | `fortis-r7-client` → `/run/fortis-client` RO; `fortis-repo-workspace` → `/workspace/files`, `/workspace/repo`, `/workspace/repos` RW | Calls R7 through `https://host.docker.internal:19104`; never receives Sonar token |

The Repo client sends typed envelopes to `/v1/reads` and `/v1/actions`; R7 itself performs the allowlisted Sonar GETs. Only the owner portal can complete WebAuthn decisions. Do not infer current runtime from historical compose files: `compose-r7-p2-20261103.yaml` is the exact P2 reference, while `compose.yaml`, `compose-r7-unified-read-ask.yaml` and older candidates are historical.

For the source-level flow and state machine, use [`fortis_approvals/README.md`](../README.md).
