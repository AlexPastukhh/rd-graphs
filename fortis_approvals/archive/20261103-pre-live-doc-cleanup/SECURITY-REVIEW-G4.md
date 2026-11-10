# G4 SonarCloud READ + ASK — security and owner-operation review

**Record date:** 2026-10-31. **Status:** owner-reported Windows G4 READ -> ASK Pending -> WebAuthn Reject -> History REJECTED -> exact-request GET readback PASS; Sonar WRITE NOT AUTHORIZED. This is a **review record**, not a declaration of production security certification. It describes the current G4 **candidate**, not future G4 WRITE or G3.

**Forward-looking WRITE security decision (reviewed 2026-10-31):**
[`G4-WRITE-SECURITY-REVIEW.md`](G4-WRITE-SECURITY-REVIEW.md) is the
separate, non-mutating B1-B8 threat assessment and G4-W0..W7 release gate
matrix. **NO-GO** for a POST-capable G4, regardless of the successful exact-ID
READ/Reject/get-readback. Existing candidate controls must not be removed.

## 1. What has actually been demonstrated

| Control / outcome | Evidence and limitation |
| --- | --- |
| READ from EU SonarCloud | Owner's prior GET-only issue probe returned `ISSUE_PREFLIGHT_READ_OK` for one `OPEN` Issue in `AlexPastukhh_gd-cap`, all ten fields and `accept` among transitions. That probe did not create a G4 ASK or verify POST authorization. |
| Separate storage from G2 | G4 uses project `fortis-approvals-g4`, localhost port `18991`, and named volumes `fortis-approvals-g4_state` and `fortis-approvals-g4_token`; owner reports G4 started. Running G2 uses port `18990` and separate state. No G2 restart or modification was requested. |
| Windows private directories | Owner reported `G4_PRIVATE_STATE_CREATED`, `G4_PRIVATE_STATE_WRITE_AND_LINK_OK`, `G4_PRIVATE_TOKEN_CREATED`, `G4_PRIVATE_TOKEN_WRITE_AND_LINK_OK` and `G4_PRIVATE_DIRECTORIES_READY`. Both volume roots had previously remained UID 0/mode 0755 despite successful `chown/chmod`. The protected *subdirectories*, not volume roots, now carry the private files. |
| Token provisioning | Owner's local PowerShell execution showed explicit `STORE`, hidden prompt, private-directory verification and `G4_TOKEN_PROVISIONED_PRIVATE_VOLUME`. The token value was not shared in conversation and was not independently inspected. The subsequent real G4 ASK is owner-reported evidence that a scoped Sonar GET worked; actual token expiry, privilege scope and any write permissions remain unverified. |
| Owner panel | `G4_CANDIDATE_READONLY_READY: http://localhost:18991/` printed on Windows; owner reports successful G4 invitation registration and sign-in. Do not equate owner report with independent security audit. |
| Compose warning | Docker printed that both named G4 volumes pre-existed and were not Compose-created, while the service still started. Source `compose-g4.yaml` now marks them `external: true`, but **the owner's running configuration has not been updated**. Warnings do not by themselves indicate a token leak. No redeploy needed solely to suppress them. |
| Tests | Latest repository synthetic suite: 133/133 Python, 3/3 JavaScript UI and RDG docs audit PASS before this record; a later edit must rerun these. They simulate Sonar and WebAuthn and do not assert real Sonar mutation or real-world adversarial certification. |
| Real G4 Issue ASK | **PASS (owner-reported):** the real scoped Sonar request appeared in G4 Pending; Approve was unavailable; the owner rejected it after a PIN prompt; the same decision was subsequently visible with state `REJECTED` in G4 History. This is owner-observed browser evidence, not an independent database readback. |
| Live Sonar WRITE | **DISABLED/UNTESTED**. Only Reject was actionable; portal and transport prohibit POST. Exact-ID owner-side local and upstream GET readback is now reported PASS, but this is not packet-level evidence that no POST occurred at any other time. `acceptOffered=true` does not authorize writes. |

**Owner security clarification 2026-10-31:** current credential is reported
to reach multiple/all *accessible* organizations, not one organization.
If it is a PAT it inherits its issuing user's permissions across those
organizations; token type has not been independently identified. The
current `FORTIS_G4_ORGANIZATIONS` restriction limits only **Fortis's own
API requests** and cannot limit a stolen token. Cross-organization exposure is a **known residual risk** in the owner-selected broad-token + Fortis ASK model, not a demand for a narrow token. Secure privileged-executor custody, independently enforceable ASK and explicit risk review remain WRITE prerequisites, described in [`G4-WRITE-PRIVILEGED-TOKEN-ADR.md`](G4-WRITE-PRIVILEGED-TOKEN-ADR.md).

## 2. Trust boundaries, files, locations

- **Human-owned local workstation:** Windows PowerShell, Docker Desktop and local browser are trusted operator surfaces. All G4 credential provisioning, invite handling and request submission originate here. The repository/AI execution environment has no authorized access to the Windows Docker token volume or the real token. Never copy tokens, Docker volume backups or passkey invitations into Repo/chat/files.
- **G4 owner UI:** `http://localhost:18991/` is an **HTTP loopback origin**, not HTTPS over a remote network. Compose publishes `127.0.0.1:18991:18991`, so no intended LAN/WAN listener. Browser extensions, localhost-capable malware, local users and host administrators are outside this isolation guarantee. Origin/Host checks, CSRF checks and HttpOnly/SameSite cookies reduce browser risks but are not substitutes for host security.
- **G2 boundary:** G2 remains the separately running synthetic-only panel on `18990`. Do not mount `g2_state`, reuse G2 enrollment invitations, build or restart G2 using G4 scripts, or make G2 dependent on G4. G4 has separate WebAuthn enrollment and a different origin.
- **Docker volume names:** `fortis-approvals-g4_state` and `fortis-approvals-g4_token`. The root of each named volume may appear as UID 0/mode 0755; this alone is **not** proof private children are wrong. Required private directories are `/state/private` and `/run/g4-token/private`, each **UID/GID 10001, mode 0700**, as checked in *distinct* root and UID-10001 containers. Do not run the old root `chown/chmod` repair; it did not persist in the owner's environment.
- **Token file:** `/run/g4-token/private/sonar_token` inside the G4 container, **mode 0600, owner UID 10001**. Backed by the dedicated persistent Docker Desktop volume. Mounted **read-only** in the long-running `owner` container, writable only in the temporary offline bootstrap. Its value is not in Compose environment, Docker CLI arguments, image layers or source files.
- **State volume:** `/state/private` stores `approvals.sqlite`, `owner.sqlite`, `synthetic.sqlite` (constructed by the shared runtime even though G4 does not expose the synthetic adapter), `g4-receipts.sqlite` and the G4 marker. Protected private directory mode 0700; individual SQLite/marker files use private permissions. The preview/snapshot and stored request **may contain sensitive Sonar Issue fields** including the issue `message`, rule, component path and assignee. Treat the entire G4 state volume and browser Pending/History as confidential; it is not just an opaque hash store.

## 3. Token lifecycle (current implementation, NOT an ideal secret manager)

1. **Source of credential and privilege:** token is entered by the owner into a local hidden `Read-Host -AsSecureString` prompt. The requested Sonar account/token permissions and expiry are **not captured or independently verified** here. The owner has chosen broad-token authority with Fortis enforcing request-level ASK; narrow credentials would be optional defense in depth, not a mandatory part of that architecture. Availability of `accept` in `additionalFields=transitions` does not authorize WRITE; a broad token may be used under the owner-selected model only after independently verified Fortis ASK enforcement and explicit live-POST authorization.
2. **Explicit consent:** `Provision-G4-Token.ps1` prints that the token persists **UNENCRYPTED** in a Docker volume and accepts the exact `STORE` phrase before requesting the secret. Consent is scoped to this local storage operation, **not** consent to any Sonar POST.
3. **Short plaintext exposure during provisioning:** script converts SecureString with `SecureStringToBSTR`, then `PtrToStringBSTR` into a **temporary managed plaintext string** and pipes that string through stdin to Docker (`docker run -i --network none ... python -m fortis_approvals.g4_secret_bootstrap`). `ZeroFreeBSTR` clears the unmanaged BSTR after use, but **cannot guarantee clearing copies** in PowerShell/.NET managed memory, pipeline buffers, Docker stdin or Python memory. Hidden input avoids console echo; it does not establish end-to-end secure memory or protect a compromised host. A console transcript may record prompts/status and the typed `STORE`, but not the masked token as shown in the owner's log.
4. **Bootstrap controls:** temporary container uses `--network none`, UID 10001, dropped capabilities, no-new-privileges and private token volume. Bootstrap accepts up to 4096 characters, rejects whitespace/invalid length and refuses existing target/symlink rather than overwriting. It creates a temporary file, fsyncs and atomically hardlinks to its final name. Success prints only `G4_TOKEN_PROVISIONED_PRIVATE_VOLUME`.
5. **At rest:** no application-level encryption. Mode 0600 and private parent 0700 restrict unprivileged processes *inside the Linux VM*, **not** Windows host administrators, Docker admins, Docker daemon access, backups/snapshots, malware with equivalent privilege, or host full-disk access when unlocked. Docker volumes persist across normal container restarts and `compose stop`. There is no automatic expiry, token rotation, revocation or destruction policy in this release.
6. **Use in running G4:** each process reads the private token file, validates owner/permission and sends it as a Bearer header over TLS to fixed EU `https://sonarcloud.io` (US host exists in source but this deployment uses EU). Transport has a fixed method/route allowlist, system CA validation, no redirects, no arbitrary proxy and request timeout. The long-running G4 owner container mounts the token volume `:ro`; its process memory necessarily contains a copy of the token while running. G4's `NoWriteTransport` permits GET only, despite the underlying general Sonar adapter having a POST route for a future distinct release.
7. **Failure, rotation and revocation:** provision refuses overwrite and should not be retried until the exact failure is understood. Replacing/revoking the token requires a separate audited owner operation, revocation on SonarCloud and careful update of G4 secret storage. **Do not** print the file, run `docker exec cat`, paste its bytes, remove either named volume, or use `docker compose down --volumes` as troubleshooting. No automatic credential rotation or verified deletion workflow is shipped.

## 4. WebAuthn invitation, login, ASK and WRITE firewall

- `Invite-G4-Candidate.ps1` generates a **G4-only**, single-use enrollment invitation valid for **5 minutes**, and the application persists its **hash**, not its plaintext. The user reported an invitation **in this chat** after already using it to register; the exact invitation string is intentionally not reproduced in this record. Used invitations cannot enroll again; unused invitations expire after 5 minutes. Treat any unexpectedly still-valid invitation as exposed. Do not paste future invite values into chat or the repository.
- G4 owns its independent `owner.sqlite`, WebAuthn RP/origin `http://localhost:18991`, verified browser session and CSRF. The same physical authenticator may be enrolled in G4, but G2 and G4 credential stores are not shared. Authenticated browser sessions are ephemeral and may be invalidated by a restart; enrollment persists in the G4 state volume. The configured session TTL is 43,200 seconds (12 hours). The invite expiration is separate from this TTL.
- **Real Windows owner observation (2026-10-31):** a scoped Issue appeared as a G4 Pending request; Approve was disabled; Reject succeeded after the user was prompted for a PIN. This is consistent with the configured strong WebAuthn decision proof: `user_verification=REQUIRED`, verification of the signed assertion's user-verified flag, and binding of request ID, fingerprint and decision. In normal WebAuthn the PIN is handled locally by the authenticator or OS and is not sent to Fortis; the app receives an assertion, not PIN digits. The exact system dialog was not independently inspected. The PIN itself must not be recorded. The owner additionally reports the request visible as `REJECTED` in G4 History. At that earlier observation, exact-ID SQLite and Sonar GET readback had not yet been performed. The later owner-operated readback is recorded as PASS in §5A.
- G4 operator CLI `Propose-G4-Issue.ps1`/`g4_operator.py` is the **only intended submission path**. It reads the current Issue via Sonar GET, validates membership in the owner-selected organization, checks exact status, normalized issue SHA-256 and availability of `accept`, and creates a local `PENDING` with a frozen before/after preview and required ASK policy. It is **not** an AI-facing API and cannot choose arbitrary HTTP endpoints, actions or transition names.
- Browser G4 shows **READ ONLY**; UI sets `approvalAllowed=false` and disables Approve. The owner portal separately blocks `approve` in session, WebAuthn-begin and WebAuthn-finish endpoints for the Sonar operation. Owner WebAuthn **Reject** is allowed and recorded. A third independent transport backstop prevents **any POST** from the candidate even if the Core is called directly. These are **code-level controls**, not a network egress firewall blocking all outgoing HTTPS.
- Future G4 WRITE is out of scope: it requires a separately reviewed build, minimum Sonar permission review, exact test Issue and fresh explicit human authorization, with WebAuthn and readback. The Sonar API does not supply a conditional version/CAS mutation guarantee; a race can exist between pre-write GET and POST. After an ambiguous POST, retries must not be automatic. **None of these WRITE claims are established by this G4 candidate.**

## 5. Docker configuration, secrets and logs

- Compose project: `fortis-approvals-g4`. Service exposes only loopback `18991`, runs non-root UID/GID 10001, drops capabilities, denies privilege escalation, sets a read-only root filesystem, uses a small temporary `tmpfs` and separate state and token volumes, and has `restart: unless-stopped` plus a localhost-only health check.
- Current owner-host Docker printed pre-existing-volume warnings during `Start` and `Invite`. Both commands completed and owner entered G4 successfully. As **source-only remediation**, `compose-g4.yaml` now marks *both* manually pre-created volumes `external: true` with exact names. This tells Compose **not to create or own** the volumes and should prevent the ownership warnings when that configuration is later installed. The source edit does not update the already-running Windows Compose file/container; no G4 restart is required to continue the current READ-only test.
- Store non-secret diagnostics only: exit code, `G4_TOKEN_PROVISIONED_PRIVATE_VOLUME`, `G4_CANDIDATE_READONLY_READY`, volume UID/mode status, `PENDING` request state (optionally redacting Issue key). **Do not** log raw Bearer headers, token, WebAuthn invitation, auth cookies, PIN, Issue messages, full request preview, detailed exception bodies or Docker volume archive contents. Repo source inspection and code/unit tests do not need real tokens.
- `docker compose run` may print generated container IDs and harmless Compose warnings. Those are not tokens. Do not publish `docker inspect` outputs indiscriminately, especially environment variables or mounts, even though this deployment passes only the token *path* as environment.

## 5A. GET-only exact post-Reject readback (owner Windows run PASS)

**A live exact-request result is now owner-reported PASS.** The source-only, operator-controlled readback procedure is in
`Verify-G4-Rejected-Readback.ps1` and `G4-Readback-Probe.py`.

- Uses the already-reviewed local G4 image, does **not** rebuild/restart G2 or G4, and creates a transient non-root container without ports. Both existing G4 named volumes are mounted `readonly`; the container root filesystem is read-only. It does **not** mount G2 or the Docker daemon socket, and it does not write owner SQLite, request state or the token.
- The local source is piped to `python -` over standard input, avoiding PowerShell quoting problems; an exact project+Issue key is passed as arguments, not credentials. The G4 Bearer token is read only inside the transient container from `/run/g4-token/private/sonar_token` and never sent to the terminal, source ZIP, process arguments or Repo environment.
- The script opens `/state/private/approvals.sqlite` in SQLite URI `mode=ro` plus `PRAGMA query_only=ON`; requires an explicit, canonical `-RequestId` supplied by the owner; selects **only that exact UUID** (not the most recent by a potentially ambiguous timestamp/UUID order), verifies project/Issue, typed `sonarcloud/accept_issue`, `REJECTED` decision `reject`/owner, a single `REJECTED` event, and compares `expectedIssueSha256` with its stored `before.sha256`. Failure does not trigger a new ASK.
- After the local check, one exact SonarCloud EU HTTPS **GET** `/api/issues/search` retrieves the current scoped Issue. The transport uses source-enforced route and method allowlists, no arbitrary URL and no redirects, and `NoWriteTransport` refuses any non-GET call. Successful comparison requires remote status `OPEN` and equal normalized projection digest (includes key, project, status, updateDate, message, rule, severity, component, assignee and type). Merely remaining `OPEN` while the digest changed is **REVIEW_REQUIRED**, not a pass. This is a point-in-time comparison; unrelated writers might mutate Sonar after the check.
- Outputs only aggregate statuses: local `REJECTED`, remote `OPEN`, digest match YES/NO, `PASS`/`REVIEW_REQUIRED`, and a static `G4_PROBE_GET_ONLY: YES` indication of the source guard (not actual network telemetry). It never displays the token, owner identity, PIN, invitation, Issue message, file paths from remote errors or complete private snapshots. If remote data are missing, changed, malformed or unavailable, report fail-closed, and do **not** attempt POST or automatically retry.
- **Limitations:** outbound network access still exists for HTTPS GET; the protection against POST is source-level, not an egress firewall. Windows Docker Desktop may need suitable external network access. The old local candidate source/image stays unchanged; the verifier is streamed as trusted operator-reviewed source, not deployed inside the running image. The readback is independent of the G4 UI but not an external audit of the Docker daemon, host or token privileges.

### 2026-10-31 Windows GET readback: partial PASS and exact-request ambiguity

Owner re-ran `Propose-G4-Issue.ps1` for the same Issue and obtained a **new**
request ID `69898cab-809d-468a-aaeb-be64dde1295e`, state `PENDING`.
Owner then executed the first post-Reject probe. It reported
`G4_LOCAL_HISTORY: REJECTED`, `G4_REMOTE_STATUS: OPEN`,
`G4_REMOTE_PROJECTION_MATCH: YES` and `G4_READBACK_AFTER_REJECT: PASS`.
This is **owner-reported evidence that a rejected G4 request snapshot matched
Sonar GET at that time**, but NOT proof that the newly created request ID was
rejected. The original probe searched by project/Issue and sorted records by
`created_at DESC,id DESC`; on ties, UUID ordering is not request chronology.
The operator did not report any second Reject, so do not infer it happened.

**Corrective safety change:** the amended verifier makes `-RequestId` mandatory
and performs one `SELECT ... FROM requests WHERE id=?` with exact project,
Issue, `REJECTED`/`reject` state, owner, digest and event checks. An exact
new-PENDING request **fails before remote GET** rather than silently using
an earlier rejected row. The operator must explicitly choose the request ID
whose rejection is being audited. No POST, local DB write or Docker restart.
`G4_CHECK_SONAR_POST_REQUESTS: 0` in the earlier output was a **hardcoded
source claim**, not a measurement of Docker or remote Sonar traffic. The
amended output is `G4_PROBE_GET_ONLY: YES`, a transparent statement about the
source path's GET-only enforcement, not a packet capture. The amended verifier
was subsequently executed successfully for the exact request ID; see the
acceptance record immediately below. The earlier
project/Issue-only result remains historical, limited evidence.

### 2026-10-31 owner acceptance: exact request-ID readback PASS

The owner copied `fortis-g4-exact-request-readback-hotfix-20261031.zip` from
Fortis Repo, checked the entire SHA-256 against
`dbea47de750361711391294bd51b68e8691355f36f7fdbfcff2b35dc558f0fdd`,
and installed it in their separate Windows G4 operator folder. They executed
`Verify-G4-Rejected-Readback.ps1` on **exact** project
`AlexPastukhh_gd-cap`, issue `AaDX-EdYT7YShyBpAy0r` and request
`69898cab-809d-468a-aaeb-be64dde1295e`. The reported output was:

```text
G4_LOCAL_HISTORY: REJECTED
G4_REMOTE_STATUS: OPEN
G4_REMOTE_PROJECTION_MATCH: YES
G4_READBACK_AFTER_REJECT: PASS
G4_PROBE_GET_ONLY: YES
```

This closes the **functional exact-request G4 read/ASK/reject/readback** gate:
the local rejected request and its recorded event were checked by exact UUID
in read-only SQLite, and a live Sonar GET returned `OPEN` with an identical
normalized SHA-256 projection to the request's original `before` snapshot.
It resolves the previous new-PENDING-vs-old-REJECTED ambiguity; the exact
newer request is now reported `REJECTED`. The output does not reveal whether
the owner pressed Reject after the earlier report, but the local persisted
state and event were verified by the new probe. No database mutation occurred
inside the readback probe; no real Sonar WRITE was authorized.

**Security boundaries:** `G4_PROBE_GET_ONLY: YES` documents code-level method
enforcement, not live packet capture. Equality of a point-in-time projected
hash does not prove absence of any intermediate mutation subsequently
reverted, or full Issue history/remote authorization, or Sonar token
least-privilege. A separate production G4 WRITE release still needs explicit
owner authorization, least-privilege token audit, threat-model review,
CAS/race handling, exact test Issue selection and one-shot readback design.
The live G2 and G4 services were not restarted or changed by Repo.

## 6. Incidents, recovery and required next review gates

- **Windows preparation issue #1:** `docker volume inspect` for a nonexistent volume generated a `NativeCommandError` under Windows PowerShell `ErrorActionPreference=Stop`. The hotfix uses `docker volume ls --format '{{.Name}}'` and exact-name comparison instead. The first failed run did not build a service.
- **Windows preparation issue #2:** initial `Prepare-G4-Candidate.ps1` printed `G4_CANDIDATE_PREPARED` despite both volume roots being root:755. `Provision` failed safely before token creation, `TOKEN_FILE_EXISTS=False`, UID-10001 `EACCES`. Root `chown/chmod` commands returned success but changed permissions were not visible across invocations. The revised G4 repair uses protected subdirectories, verifies UID-10001 write/link and refuses unknown earlier contents. Owner subsequently reported all four private-directory checks PASS.
- **Credential provisioning after repair:** owner typed `STORE` and provided hidden local token; bootstrap printed `G4_TOKEN_PROVISIONED_PRIVATE_VOLUME`. The token value was not shown. Treat success as evidence of successful local write, **not** proof of token validity, scope, Sonar authorization or expiry.
- **Local G4 start and registration:** owner reported `G4_CANDIDATE_READONLY_READY` and successful registration/login. G4's actual identity-bound authentication is enforced by the program; independent Windows/browser penetration review is still open.
- **Owner-reported live READ/ASK/Reject PASS (2026-10-31):** the chosen Sonar Issue appeared in Pending in the Windows G4 panel, Approve was disabled, and Reject succeeded after a PIN challenge. This demonstrates local G4 candidate functionality, not Sonar WRITE authorization or a third-party security audit.
- **Owner History follow-up (2026-10-31):** owner confirms that the rejected request appears in the G4 History tab with state `REJECTED`. Local terminal decision and browser history persistence are therefore owner-reported PASS.
- **Owner exact-ID GET-only acceptance (2026-10-31):** after the earlier ambiguous result, owner verified the ZIP SHA-256 and ran the corrected `-RequestId 69898cab-809d-468a-aaeb-be64dde1295e` probe. Local `REJECTED`, remote `OPEN`, exact frozen normalized digest match YES, and `G4_READBACK_AFTER_REJECT: PASS` were reported. The functional no-write readback gate is now owner-reported PASS. The code-level GET guard was not independently network-captured.
- **Future audit backlog:** verify actual token permissions and expiry; design least-privilege dedicated token and audited renewal/revocation; restrict backups and retention of state/token volumes; verify real browser WebAuthn session security and localhost exposure; review Docker volume admin trust and protection at rest; review `external: true` Compose change before applying to owner host; reproduce private-subdirectory repair on a clean installation; examine local service/daemon logging policy; design safe test of WRITE only after explicit owner sign-off.

**Security acceptance checkpoint:** G4 local infrastructure, private token storage, login and real Sonar READ -> local ASK Pending -> owner WebAuthn Reject (PIN prompt) are **owner-reported PASS** on Windows. Exact-ID local SQLite readback and Sonar GET status/digest match are owner-reported PASS; broader security review, independent packet audit and token privilege/expiry audit remain OPEN. Live Sonar mutation remains **DISABLED**. The G2 service, Docker volumes and active passkey registrations must remain untouched during this phase.
