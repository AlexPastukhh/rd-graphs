# R7 P2 — WebAuthn-gated Sonar `accept_issue` source review

Date: 2026-11-03  
Status: **P2 PACKAGE + IMAGE/AUDIT PASS / WEBAUTHN-HTTPS BLOCKED / NOT DEPLOYED / LIVE E2E OPEN**  
Scope: one owner-pinned SonarCloud project; one typed operation, `sonarcloud.accept_issue`.

## Owner authorization

The owner explicitly authorized enabling real execution for this exact typed operation, provided each Issue remains a separate ASK and requires a separate strong WebAuthn Approve. This authorization is not a blanket approval of any Issue and does not authorize bulk changes, arbitrary Sonar writes, token changes, or a production rollout by itself.

## Source changes

- `r7_unified_candidate.py`: removed the R7 `NoWriteTransport` wrapper; the trusted adapter now uses the server-injected Sonar transport. Removed the R7-only `blocked_approvals` entry and READ ONLY banner. The machine actor remains restricted to typed READ and ASK proposal operations.
- `core.py`: includes durable `policyVersion` in the owner view. `owner_decide(approve)` now requires the row's stored policy version to match the current Core version and the current server-side rule to remain `ASK`; the check runs before proof verification and again after it. This closes the direct Core approval path for stale policy rows.
- `owner_portal.py`: Approve is exposed only when the request's stored policy version is current and the current server-side policy is still ASK. The existing `strong_operations` requirement still forces WebAuthn for `accept_issue`; the session-only decision route is rejected for this operation.
- `r7_unified_candidate.py`: pins `policy_version='r7-p1-sonar-accept-issue-write-v1'`. Old Pending rows from READ ONLY versions cannot be approved under the new portal policy.
- `r7_unified_server.py` and the R7 Dockerfile review header now describe WebAuthn-gated execution. The server still requires one exact project key at trusted startup.

## Execution boundary

1. Repo client submits one typed `accept_issue` ASK proposal; the Core stores a frozen preview and fingerprint. No Sonar POST occurs at submission.
2. Owner opens the private portal and performs a fresh WebAuthn assertion with user verification, bound to this request ID, fingerprint and `approve` decision.
3. Core rechecks policy version, ASK rule, initiator grant, expiry and the exact prepared Issue snapshot. It writes `DISPATCHED` durably before the remote effect.
4. The adapter performs one final Issue GET, one Sonar `accept` POST, then an independent GET readback. Only a confirmed `ACCEPTED` state with a durable receipt yields `EXECUTED`.
5. A stale preview stops before POST. A timeout or ambiguous outcome is `UNCERTAIN`; no blind POST retry is allowed. A later reconciliation is read-only.

## Residual risk and limits

SonarCloud's transition API does not provide an atomic conditional update/CAS for the Issue version. An external writer can race between the adapter's final GET and POST. The local fingerprint, final revalidation and readback reduce and detect many stale cases but cannot make the upstream transition atomic. The broad owner token's actual permissions and custody remain governed by the separate owner token ADR and host controls.

## Verification performed

- `test_core.py`: **28/28 PASS**, including revocation and policy-version change denial.
- Python `compileall` for the changed Core, portal, candidate, server and R7 test module: **PASS**.
- R7 WebAuthn/HTTPS integration tests: **BLOCKED** in this workspace because `cryptography` and `fido2` are not installed. Do not report them as passing.
- No P2 live Sonar GET or POST, no P2 deployment/start/recreate, no Repo/Tunnel changes and no live Issue modification. The owner-reported P2 Windows image-only build and installed-source/import audit passed for image `sha256:e751f6ca0cfe6ce290cf580de2f243071ee1f3e681baa8827c6cea41a16fa402`.

## Release gates

The P2 package, owner-reported image build and exact installed-source/import audit are complete. The full R7 WebAuthn/HTTPS suite is still BLOCKED in the current Linux Repo environment because pinned `cryptography` and `fido2` are unavailable. Before rollout, review the residual Sonar race/token scope, preserve the five provisioned R7 volumes and existing owner state, and obtain a separate explicit owner GO. Deployment and live use remain separate owner-controlled steps.

## 2026-11-03 continuation — immutable P2 package prepared

A new P2 package was generated from the current checkout using the dedicated
`package_r7_p2_20261103.py` builder. The allowlist contains exactly 20 source
files and the ZIP contains only those files plus `SOURCE-MANIFEST.sha256`.

- ZIP: `/workspace/repo/Workfiles/fortis-r7-unified-source-review-p2-20261103.zip`
- ZIP SHA256: `a3e87c0c8643e79db48655aae9e100029b6f0bd6683369e565e59ec995718748`
- Manifest SHA256: `d766c28b9d2ea52e40f613614d85962e8eeee61393bbf80d8acf7be6ae05c1db`
- Dockerfile SHA256: `0bb5f19ff8d40642946c64dbc46a7759607aa60bd9648cd48a605570ff908b86`

New owner-only transfer scripts are prepared: `Build-R7-Windows-ImageOnly-p2-20261103.ps1`
and `Audit-R7-P2-Windows-ImageOffline-20261103.ps1`. The build script is
image-only and pins the exact package, manifest and Dockerfile hashes. The
audit requires the owner-supplied post-build image digest and performs only
metadata, 19 installed-source hashes and isolated import smoke.

Offline verification in this workspace: P2 static/Core/typed-client batch
44/44 PASS and compileall PASS. The full WebAuthn/HTTPS suite remains BLOCKED:
`cryptography`/`fido2` are unavailable and this container has neither pip nor
`python3-venv`; no dependency installation, image build, deployment or Sonar
request was performed. Rollout and live E2E remain owner-controlled and open.


## 2026-11-03 continuation — owner-reported P2 image build and audit PASS

Owner ran the corrected image-only build and exact installed-source audit on
Windows Docker for the immutable P2 package.

- Image tag: `fortis-r7-unified-read-ask-candidate:review-p2-20261103-a3e87c0c`
- Image ID: `sha256:e751f6ca0cfe6ce290cf580de2f243071ee1f3e681baa8827c6cea41a16fa402`
- Image metadata: PASS
- 19 installed source SHA256 checks: PASS
- Exact image import smoke: PASS
- Disposable audit containers removed: PASS
- Sonar token provisioned: NO
- Sonar network requests: NONE
- Live deployment: NOT PERFORMED

This is owner-reported evidence for the exact P2 image and audit scripts. It
closes the source/package/image/audit gate. Trusted admission, rollout and live
READ/ASK/Reject/Approve E2E remain separate owner-controlled gates.
