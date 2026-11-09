# G4 SonarCloud read-only ASK candidate — Windows operator installation

**CURRENT OWNER DECISION — ONE FORTIS CONTAINER (2026-10-31):** The permanent target is a single owner-controlled Fortis Secure Gateway container combining secret vault, trusted ALLOW/ASK/DENY, owner WebAuthn and typed execution. Machine ingress and owner UI have separate authorizations but NOT required separate containers; a standalone token-bearing executor/IPC is superseded. This file describes only an existing G4 experimental READ/ASK/Reject deployment, not permission to POST or migrate its token. Read [`G4-WRITE-PRIVILEGED-TOKEN-ADR.md`](G4-WRITE-PRIVILEGED-TOKEN-ADR.md), [`UNIFIED-APPROVALS-CUTOVER-PLAN.md`](UNIFIED-APPROVALS-CUTOVER-PLAN.md) and [master plan](../../docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md).


**READ-ONLY SONAR TOKEN PERMISSIONS INVENTORY:** [G4-WRITE-OWNER-INVENTORY.md](G4-WRITE-OWNER-INVENTORY.md) lists only browser metadata checks. No token creation/copy, no change.

**OFFLINE WRITE EXECUTOR LAB (NOT INSTALLABLE):** [G4-WRITE-LAB-ACCEPTANCE.md](G4-WRITE-LAB-ACCEPTANCE.md) describes a synthetic-only ASK-bound, one-shot request gate, three spawned worker-process boundary tests, 173 Python tests and remaining production blockers. Do not copy lab code into running G4.

**FORTIS REPO → APPROVALS INGRESS (STEP 2, SOURCE/LOOPBACK ONLY):**
[FORTIS-REPO-INGRESS-GATE-V1.md](FORTIS-REPO-INGRESS-GATE-V1.md)
reviews strict WSGI submit/status with a distinct ingress grant and 204
offline Python tests. It has **not** been connected to Windows G2/G4, and
no new credential mount, owner API route or Sonar POST has been added.

**FORTIS REPO → APPROVALS REQUEST CONTRACT (STEP 1, SOURCE-ONLY):**
[FORTIS-REPO-ACTION-CONTRACT-V1.md](FORTIS-REPO-ACTION-CONTRACT-V1.md)
records the six-field typed intent, per-actor grant and restricted server-
derived Sonar digest. The future Repo ingress and token-isolated Executor
are separate engineering steps; **do not use the existing G4 container as
a new generic public executor** or copy the contract into its running image.

**UNIFIED UI / CORE FUTURE CUTOVER (NOT DEPLOYED):**
[UNIFIED-APPROVALS-CUTOVER-PLAN.md](UNIFIED-APPROVALS-CUTOVER-PLAN.md)
explains why G2:18990 and G4:18991 are currently separate candidate
containers, and outlines one future owner panel, one queue/WebAuthn origin,
typed adapters and a common ALLOW/ASK execution path. No existing
volumes, token or passkeys are migrated automatically. Offline source
[`unified_lab.py`](../unified_lab.py) is only a FakeSonar demonstration.
Do **not** copy the lab module into this running G4.

**OWNER-SELECTED WRITE TRUST MODEL:** [G4-WRITE-PRIVILEGED-TOKEN-ADR.md](G4-WRITE-PRIVILEGED-TOKEN-ADR.md) records broad Sonar token + mandatory Fortis ASK; it does not authorize an actual POST. Token confinement and independent policy enforcement remain required.

**FUTURE WRITE RELEASE REVIEW (NOT APPROVED):** [G4-WRITE-SECURITY-REVIEW.md](G4-WRITE-SECURITY-REVIEW.md) defines token privilege, permission/Quality Gate impact, exact owner authorization, race/UNCERTAIN handling, test matrix and mandatory sign-off. It is a NO-GO review; do not enable POST in this deployed candidate.

**SECURITY REVIEW FIRST:** [SECURITY-REVIEW-G4.md](SECURITY-REVIEW-G4.md)
records the threat model, plaintext token lifecycle and privilege, Docker
volume permissions, WebAuthn invitations, ASK/POST boundaries, live owner
reports, open audit gates and all known Windows repair incidents. Read and
review that document before expanding G4 credentials or capabilities.


**Status:** owner-review candidate; not a replacement for the running G2 and
not a production/WRITE SonarCloud release. Tested synthetically in Fortis Repo;
Windows Docker image build/volumes/UI interaction still need operator acceptance.

## Separation from G2

- Existing **G2** keeps project `fortis-approvals-g2`, port `18990`, its own
  owner credentials and database. **Do not stop, rebuild, reset, remove its
  volume, or re-enroll it.** No G2 command is invoked here.
- New **G4** candidate uses project `fortis-approvals-g4`, port `18991`,
  Docker volumes `fortis-approvals-g4_state` (requests + separate WebAuthn
  credential) and `fortis-approvals-g4_token` (Sonar token only).
- The G4 UI is local on `http://localhost:18991/` and has its **own owner
  enrollment invitation and passkey session**. The same physical security key
  can be registered again; the credentials/database are logically separate.
- G4 has no client-facing submit endpoint and no REST route to configure
  policies, tokens, or a Sonar project. Proposals are made via an owner-side
  Docker CLI after authenticated READ. Sonar **Approve is disabled** in the
  browser and server, while the low-level adapter refuses any POST.

## Operator procedure — run from a reviewed, independently extracted ZIP

Use Windows PowerShell with Docker Desktop running and enough free disk. The
archive has no real Sonar token or owner data. Review Dockerfile, compose and
PowerShell files, including volume names and port mapping, before executing.

```powershell
$g4 = 'C:\FortisReview\G4-Candidate-20261031\fortis_approvals\deploy'
& (Join-Path $g4 'Prepare-G4-Candidate.ps1')
```

**Windows PowerShell 5.1 fix (2026-10-31):** A prior `Prepare-G4-Candidate.ps1` used `docker volume inspect` on absent volumes; with `$ErrorActionPreference='Stop'` the expected stderr was treated as a terminating `NativeCommandError`. The updated Prepare and Provision scripts check exact names via successful `docker volume ls` and `docker image ls` instead. If you have the earlier reviewed archive, apply the separately SHA-verified two-script patch before running Prepare; do not re-extract the original ZIP after applying the fix. This is a script-handling bug, not a G2 failure.

**Windows G4 volume permission regression, owner-confirmed 2026-10-31:**
Both named G4 volume roots reported UID 0, mode 0755. The previous separate
`docker run --entrypoint chown/chmod` commands returned success, but a later
container still reported `0:755`. The token file was absent and uid-10001
write/link test failed with `EACCES`. Do not repeat chmod/chown on the volume
root, erase volumes or retry the token until private directories pass.

**Existing-volume repair:** use the independently SHA-verified G4 *private
subdirectory* patch and run `Repair-G4-Existing-Volumes.ps1` on Windows,
**not** `Prepare-G4-Candidate.ps1`. The repair rebuilds ONLY the local G4
image, refuses to run if G4 is active, and creates `/state/private` and
`/run/g4-token/private` within the two exact existing G4 volumes, using
uid/gid 10001 and mode 0700. It fails closed if a volume contains unknown
files or if a private directory already exists with unexpected permissions.
A separate container verifies uid-10001 write/hardlink and removes only its
own scratch files. The volume *roots* may remain root:755 by design; only
the G4 private children must be 10001:700. G2 is never inspected or changed.
Updated `compose-g4.yaml` points runtime state to `/state/private`, and the
token path to `/run/g4-token/private/sonar_token`. The bootstrap also uses
that path; do not run an older image against the updated Compose. No token
is read or written by the repair. Windows runtime acceptance remains OPEN.

Preparation builds the candidate image and creates **two new G4-only volumes**.
If either exists, it refuses to reuse or modify the existing contents. G2 and
live Sonar are untouched. It does not start any service or ask for a token.

**Credential storage is an explicit additional decision.** The next script
prompts for the exact uppercase word `STORE` before asking for a token. It
then asks for your existing SonarCloud token via a local hidden PowerShell
prompt and sends it via stdin into a temporary, `--network none` container.
The token is stored **unencrypted** in a private file (uid 10001, mode 0600)
in the `fortis-approvals-g4_token` Docker volume. It does not enter command
arguments, environment, source archive, the G2 volume, or stdout. Docker/host
administrators can access this volume. If you do not accept persistent local
storage, **do not run this script**; no token is needed to review sources.

```powershell
& (Join-Path $g4 'Provision-G4-Token.ps1')
& (Join-Path $g4 'Start-G4-Candidate.ps1')
& (Join-Path $g4 'Invite-G4-Candidate.ps1')
```

Copy the invitation only into the **G4** registration page at
`http://localhost:18991/` (not G2). Register a credential and sign into G4.
Do not paste the invitation or token into chat. `Invite` creates one temporary
invite, independent of the existing G2 passkey.

Prepare a real Sonar Issue **READ-only ASK** in the G4 owner panel:

```powershell
& (Join-Path $g4 'Propose-G4-Issue.ps1') `
    -ProjectKey 'AlexPastukhh_gd-cap' `
    -IssueKey 'AaDX-EdYT7YShyBpAy0r'
```

The Issue is read live, and its `OPEN` state/digest and the offered `accept`
transition are rechecked. The operator supplies the reason at a PowerShell
prompt. A `PENDING` request should appear in G4 Pending within five seconds.
The owner can inspect the exact before/after preview or **Reject** the request
using WebAuthn. **Approve remains disabled**, even if Sonar offers `accept`.
The Issue status may have changed since the earlier probe; a failure is normal
and must not be bypassed or followed by a direct Sonar write.

### Post-rejection GET-only verification (independent owner review gate)

**Exact-ID readback acceptance (owner-reported 2026-10-31):** owner
verified the hotfix ZIP SHA-256
`dbea47de750361711391294bd51b68e8691355f36f7fdbfcff2b35dc558f0fdd`
and ran `Verify-G4-Rejected-Readback.ps1` with project
`AlexPastukhh_gd-cap`, Issue `AaDX-EdYT7YShyBpAy0r`, request
`69898cab-809d-468a-aaeb-be64dde1295e`. Result: exact local
`REJECTED`, remote Sonar `OPEN`, normalized projection SHA match `YES`,
`G4_READBACK_AFTER_REJECT: PASS`, `G4_PROBE_GET_ONLY: YES`. This corrects
the previous request-selection ambiguity and closes the owner-observed
functional READ→ASK→Reject→readback milestone. GET-only is a source-level
property, NOT a measured network packet count; no WRITE permission is
inferred. See `SECURITY-REVIEW-G4.md` for the owner-acceptance evidence and
remaining threat model work.



**Request-ID binding update (2026-10-31):** Owner created another request on
the same Issue, `69898cab-809d-468a-aaeb-be64dde1295e` (initial state
`PENDING`). The earlier GET-only script printed matching rejected snapshot,
`OPEN` remote status and digest `YES`, but did **not** bind its result to
that new request ID. The old script was vulnerable to selecting an earlier
rejected request by ambiguous timestamp/UUID ordering. **Do not assume** the
new request was rejected. The updated script requires `-RequestId` and
refuses a selected `PENDING` request before querying Sonar. Use only the
separately SHA-verified *request-id-binding* patch, not the original readback
ZIP. For an unchanged Issue, exact rejected ID plus digest match yields PASS.
The old printed POST counter was a hardcoded string, not network telemetry;
the corrected `G4_PROBE_GET_ONLY: YES` is a source-level GET-only property.



After the owner confirms `History: REJECTED`, obtain the *separately
SHA-256-verified* readback patch (not the earlier deployment ZIP). The patch
adds `Verify-G4-Rejected-Readback.ps1` plus `G4-Readback-Probe.py` to this
folder. Run the PowerShell script with the exact project, Issue and explicitly selected
G4 request UUID (`-RequestId`). Choose the previously rejected request
ID, or reject the newest `PENDING` in the G4 browser before verifying it. It starts a **separate one-off uid-10001 Docker container**
with the G4 state and token volumes mounted `readonly`, checks the local
`REJECTED` decision snapshot via SQLite `mode=ro`, then sends exactly one
scoped Sonar HTTPS GET through `NoWriteTransport`. Neither the running G4 nor
G2 service is changed. The output must contain
`G4_READBACK_AFTER_REJECT: PASS` only when remote status remains `OPEN` and
all normalized Issue fields match the frozen G4 snapshot digest. Differences
produce `REVIEW_REQUIRED` and no POST. See
[`SECURITY-REVIEW-G4.md`](SECURITY-REVIEW-G4.md) §5A for the security
properties and limitations. This step is **owner-reported executed and PASS for the exact request above**; the general procedure remains usable for subsequent explicitly chosen requests.

For G4-only stop, preserving both volumes and credentials:

```powershell
& (Join-Path $g4 'Stop-G4-Candidate.ps1')
```

Never use `docker compose down --volumes` on either G2 or G4. On a fresh
Docker Desktop instance, start the G4 container only after checking it has
been prepared and provisioned; G4 has `restart: unless-stopped`.

**Owner-reported Windows acceptance 2026-10-31:** G4 private-state and
private-token directories were both created and verified WRITE_AND_LINK_OK;
local `Provision-G4-Token.ps1` returned `G4_TOKEN_PROVISIONED_PRIVATE_VOLUME`
after explicit `STORE` and a masked prompt; G4 owner service returned
`G4_CANDIDATE_READONLY_READY` and the owner reports WebAuthn enrollment and
login in the G4 panel. The Sonar token value was not captured, and neither
G4 real Issue `PENDING` nor a Sonar write is yet verified. During startup
Docker warned that both pre-existing named volumes were not Compose-created.
They are now declared `external: true` in repo source for future owner review;
**the running Windows instance has not been updated**. Do not restart the
existing G4 merely to suppress these warnings.

**Owner-reported first real G4 ASK success (2026-10-31):** after local
Sonar READ the chosen Issue appeared in G4 Pending. Approve was disabled;
the owner used Reject and was prompted for PIN verification. This matches
the required WebAuthn user verification for a strong operation. The app
verifies signed assertion and UV flag; the PIN is handled by the authenticator
or Windows, not by the G4 server. Owner subsequently confirmed the rejected request
in G4 History as `REJECTED`. Independent remote Sonar GET readback was subsequently captured as owner-reported PASS with exact request ID; see the updated acceptance record above. See `SECURITY-REVIEW-G4.md` for
sensitive-data logging rules and source-vs-owner-evidence distinctions.

**Review note:** the candidate must be built from the checked, isolated source ZIP (no arbitrary project files or tokens in the Docker build context). The operator owns the Docker context and should verify it points to the intended local Docker Desktop daemon before copying or launching the archive.

## Acceptance boundary

The synthetic suite checks Sonar GET/readback, scoped ASK, WebAuthn
Pending/Reject/History, denial of all approval routes, disabled UI button,
receipt state, protected token bootstrap and separation from G2. It does
**not** prove Windows Docker runtime, real owner registration, token rights
for a future mutation, or any Sonar WRITE. No G4 POST is permitted by this
candidate. Production G4 WRITE would need a separate approved release,
permission check, known test Issue and explicit owner approval.
