# Fortis Approvals — R7 P2 candidate, A3 synthetic и исторический G4

**Постоянная матрица приёмки всей архитектуры:** [66 сценариев F/A/P/S/D/O и итоговые gates M0–M8](deploy/FORTIS-UNIVERSAL-GATEWAY-ACCEPTANCE-MATRIX-20261101.md). Включает четыре сочетания «секрет / ASK», Sonar, RDG, GitHub/CI, нескольких ИИ, owner UX, Windows import/RUN, отказ/обходы и честные статусы реальной/офлайн приёмки. Нормативная модель находится в [основном плане](../docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md) §0–1 и §12–14. **Текущий R7 P2 (2026-11-03): PACKAGE + IMAGE/AUDIT PASS / WEBAUTHN-HTTPS BLOCKED / NOT DEPLOYED / LIVE E2E OPEN.** Candidate разрешает только typed `sonarcloud.accept_issue` в одном owner-pinned project; каждая Issue требует отдельного ASK и fresh strong WebAuthn Approve. Это не bulk/arbitrary write и не rollout authorization. Production acceptance остаётся **OPEN**.

**Цель (решение владельца 2026-10-31):** **один** доверенный Fortis Approvals Server на Fortis_M: ограниченный Repo machine ingress, секреты, server-side `ALLOW/ASK/DENY`, owner WebAuthn и **один** `Core.execute`/typed adapter. Fortis Repo — недоверенный рабочий клиент, а не место размещения Approvals UI или owner token. Machine ingress может подать typed ASK, но не может Approve/execute. Для R7 P2 только точный `accept_issue` исполняется после отдельного strong WebAuthn решения владельца; остальные write operations не открыты. **Текущее состояние и очередь — в [основном плане §12–14](../docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md) и [R7 P2 source review](deploy/R7-P2-WEBAUTHN-EXECUTE-SOURCE-REVIEW-20261102.md)**; [handoff](../docs/handoffs/fortis-unified-gateway-20261101/HANDOFF.md) содержит owner evidence и continuation §27. Остальные абзацы сохраняют историю прототипов и не переопределяют текущий статус.

**Исторический baseline 2026-11-01 (не текущий R7 статус):** A4 на Windows (Repo→A3 pinned TLS1.3, owner WebAuthn, synthetic ALLOW/ASK/Reject/readback) PASS; Windows read-only ACL/status PASS. Старый независимый G4 Sonar EU GET/discovery/Issues sample PASS, **но он не соединён с новым A3**. Новый A3 Dockerfile содержит только synthetic, без Sonar token/private resolver. Текущий R7 P2 статус см. в основном плане и source review, указанных выше.

**Sonar READ R1/R2/R3 SOURCE PASS:** в Repo есть `validate_read_query`/`authorize_read`, строгий `sonar_read.py` (только GET, разрешённые организации/проекты, страницы Issues и Quality Gate) и **новый исходный** `POST /v1/reads` в том же `RepoIngress` с отдельным restricted machine grant/`ALLOW` и ограниченной выдачей JSON. `POST /v1/actions` не принимает READ; owner/admin/произвольные URL/POST не доступны. **247/247 Python + 3/3 UI, docs audit PASS**, в том числе HTTP-запрос через временный localhost test server. **Это не действующий READ в Windows Fortis и не реальный SonarCloud**: Sonar secret не вводили, Windows контейнеры не обновляли.

**R4 exact minimal source COPY / negative-security offline PASS (2026-11-01):** создан disposable `deploy/Dockerfile-R4-Sonar-Read-Check`, только 7 Fortis source modules и один fake-smoke test, **без token, owner volumes, портов и server deployment**. `tests/test_r4_image_manifest.py` сверяет буквальный allowlist/sha256 и запускает точные файлы из отдельного временного каталога через Python `-I -S -B`, `tests/test_r4_read_image_smoke.py` проверяет live in-process Core+R1/R2/R3 WSGI с fake Sonar. `R4_EXACT_COPY_STRIPPED_STDLIB_SMOKE_PASS`, все Fortis регрессии **254/254 Python, 3/3 UI, docs audit PASS**. **R4 Docker image build/run OPEN:** в Linux Fortis Repo **нет Docker CLI**; disposable Dockerfile **не собран и не запускался как контейнер**, base-image supply chain не принят. **R5 OPEN:** сначала owner-controlled production trust, реальная проверенная сборка/импорт и 2 отложенные процедуры TLS/grant, затем token в приватном Windows Fortis и реальный Sonar GET. Рабочий A3/G2/G4/RDG, реальные токены и Sonar POST не затронуты. До этого никакого real Sonar POST, нового production token или изменений G2/G4/A3/RDG.

**R5 SOURCE CANDIDATE PREPARED (2026-11-01), LIVE SONAR/OWNER DEPLOY OPEN:** `r5_read_candidate.py`/ `r5_read_server.py` объединяют read-only `Core`, существующий owner WebAuthn UI и machine HTTPS/TLS1.3 ingress, не регистрируя Sonar mutations. Независимые **новые** R5 owner volumes и порты `19103/19104`; Sonar token и machine bearer grant — отдельные RO/private files, только owner-provisioned, не AI. Только source/test Compose `deploy/compose-r5-sonar-read.yaml` и Dockerfile `deploy/Dockerfile-R5-Sonar-Read-Candidate` (SHA256 `91dac44f20ddc68a858e6d2d774c9bb83b6583bec9b6288f0eb7baae4efa2769`). Exact COPY stripped-import + real localhost TLS1.3 fake-Sonar tests PASS; **266/266 Python, 3/3 UI**, docs audit PASS. **Docker CLI отсутствует, образ не собирался, Windows A3/G2/G4/RDG не обновлялись, live Sonar GET и token provisioning не выполнялись.** До owner GO: independent image/TLS/secret admission, две отложенные TLS/grant production процедуры, безопасное создание пустых R5 volumes без A3 bootstrap. Никакого Sonar POST/ASK WRITE разрешения.

**R5 WINDOWS IMAGE CHECK (owner-reported, 2026-11-01):** точный обзорный образ `sha256:5fa986d7e532639c5461a87e4a2c34ea8176ec58371f418758d0cd5dfc38bd02` собран, изолированный `preflight-imports` PASS, 17 файлов SHA PASS, 4 pinned package versions PASS. Отдельный `pip check` вернул **exit code 0 / No broken requirements found**; старый аудит ошибочно показывал `R5_IMAGE_PIP_DEPENDENCY_GRAPH_FAILED` из-за предупреждения pip cache в stderr PowerShell 5.1. Исправлен только **source** `deploy/Audit-R5-Windows-ImageContents.ps1`, v1 неизменён, v2 в Workfiles подготовлен, но не запускался. **Никакой R5 с Sonar token не запущен; независимая provenance/CVE приёмка, доверенный TLS, ротация сертификата, machine grant revoke/issue, owner GO и live READ всё ещё OPEN.** Sonar WRITE запрещён.

**R5 TLS/grant lifecycle offline подготовлен (2026-11-01):** `deploy/R5-TLS-GRANT-LIFECYCLE-OWNER-RUNBOOK.md`, `tests/test_r5_lifecycle_offline.py` (реальный локальный TLS1.3 и тестовая FIDO2 credential, fake Sonar; STOP R5/замена обоих ключей/START R5 на прежнем SQLite, старый machine grant 401, новый 200, старый certificate pin rejected; недопустимые права/ключи fail closed). В текущем source-кандидате нет hot-reload grant/cert: **ротация вступает в силу только после перезапуска R5**. А3 не перезапускался; его существующий сертификат истекает 2026-11-07T23:29:17Z и требует **своей** owner-side процедуры. R5 пока отдельно от A3: другой WebAuthn origin и volumes, без synthetic executor; план единого production Fortis и перенос owner identity ещё не приняты. Ни реальный R5 lifetime grant revoke, ни TLS renewal Windows, ни Sonar token/live GET, ни supply-chain/owner GO не выполнены.

**R6 E2E requirement (historical snapshot 2026-11-01; P1 supersession below):** Целевая цепочка для авторизованного AI клиента: Fortis Repo → Sonar quality/Issues READ → `accept_issue` mutation proposal → `202 PENDING` в одном Fortis Approvals/WebAuthn → owner reject/readback, **без Sonar POST** до отдельного GO. `tests/test_r6_repo_sonar_read_to_approvals_tls_offline.py` подтвердил в одном тестовом `Core` реальный localhost TLS1.3 READ+ASK и owner queue на mock Sonar, включая actor isolation, status, WebAuthn/reject и запрет всех approve routes. Подробная матрица `deploy/REPO-SONAR-APPROVALS-E2E-ACCEPTANCE-20261101.md`. **LIVE НЕ ГОТОВО**: сегодняшний Windows R5 image — только READ; нет установленного MCP `sonar.*` tool/host bridge, реального Repo→Windows Sonar через Fortis, и полной связи GitHub run/PR SHA ↔ Sonar analysis/Quality Gate (D2); `CURRENT_DEFAULT_BRANCH` нельзя называть проверками конкретного SHA. Sonar WRITE по-прежнему NO-GO.

**CURRENT — R7 status (2026-11-03):** GO-1 trusted provisioning and GO-2 P1 R7 deployment/owner enrollment are OWNER-REPORTED WINDOWS PASS. GO-3 current Repo inspect is OWNER-REPORTED PASS: current Repo ID `04fed7b726a8536d63c4d2533cfc7ee3072956ff0c3f571504d7f709f7909030`, `fortis-r7-client:/run/fortis-client` with `RW=false`, workspace mounts and expected networks preserved. The stale cutover script stopped before mutation and must not be rerun. P2 package, owner-reported image build and installed-source/import audit are PASS for image `sha256:e751f6ca0cfe6ce290cf580de2f243071ee1f3e681baa8827c6cea41a16fa402`; P2 is OWNER-REPORTED DEPLOYED/HEALTHY; live E2E remains OPEN. Full pinned WebAuthn/HTTPS remains BLOCKED in the Linux Repo environment. Live Repo→R7→Sonar E2E is OPEN. Historical P1/P1-scoped details below remain provenance only; do not repeat provisioning or old image/audit work.

## Windows: разовая передача скриптов и ZIP из Fortis Repo

**Общее обязательное правило всех проектов:** каноническая инструкция находится в **корневом README контейнера Fortis Repo** — `/workspace/repo/README.md`, раздел «Разовая передача файлов на Windows из Fortis Repo (все проекты)». Готовить ZIP/`.ps1` **внутри** Fortis Repo Docker в `/workspace/repo/Workfiles/_fortis_windows_transfer_tmp/<task-id>/`; владелец получает файл на Windows только по `docker cp`, сверяет SHA256, затем отдельно разрешает дальнейшие действия. **Не предлагать ChatGPT attachment/download** и не делать ZIP руками на Windows. Исторические передачи/Windows PASS не повторять на неизменённых артефактах. Данный проектный README не является источником общего порядка передачи.

Independent Python 3.11 package, developed in the RDG worktree. It **does not import RDG**; live Windows A3 synthetic and separate G4 Sonar GET were owner-verified, but the unified real Sonar read/write service is NOT deployed. Main requirements and phased roadmap remain in `docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md`.

One typed operation is dispatched by the same executor on ALLOW and after owner-approved ASK. DENY never dispatches. Pending requests, exact actor-bound payload + frozen snapshot hash, owner decision, transitions, audit and receipts are durable SQLite records. External application occurs only after durable DISPATCHED marker. After ambiguous failure/crash the state is UNCERTAIN/DISPATCHED; `reconcile` only reads adapter receipts and **never retries blindly**.

The G1 typed WSGI client surface is implemented but deliberately has **no listening server and no owner/admin endpoint**. No UI, live credentials, production owner verifier, host deployment or RDG/Sonar adapter is implemented in G1. `Core.owner_decide` fails closed without an injected trusted verifier. The HMAC verifier used by the tests is deliberately test-only and is **not** a deployable owner authentication method. The WSGI surface exposes only authenticated client submit/status operations. Its fixed Host/Origin guard is not a substitute for production TLS or owner authentication. Keep the policy configuration and owner verification outside AI-controlled inputs.

Run in Repo Docker:

```sh
python3 -B -m unittest discover -s fortis_approvals/tests -v
```

**Исторический G2-only срез до A3:** G2 code includes an independent owner UI and Docker configuration; в тот момент next были Windows browser acceptance и G4. **Сейчас** A3 synthetic real Windows browser WebAuthn + Repo ingress PASS, следующий этап Sonar READ в одном Fortis, затем ASK → D1–D4 → G3. Before claiming trusted production deployment, verify OS/secret boundaries and perform an owner-controlled manual bootstrap.

## G2 owner UI — current scope

`owner_auth.py` verifies real WebAuthn/FIDO2 signatures (requires `fido2==2.2.1`, installed in `/workspace/repo/.rdg-webauthn-venv` for isolated tests). It stores only public credential material/counters, uses one-use operator-issued enrollment invitations, demands UV for registration, login and every **requestId + fingerprint + approve/reject** decision, checks RP/origin and signature/counter, and uses ephemeral HttpOnly/SameSite owner sessions and CSRF tokens. Pending/History/preview UI is in `static/` served through separate `OwnerPortal`. No owner/admin API exists on `ClientGateway`; credentials, invitations and policies must not be reachable to AI.

**Исторический статус G2 source-only:** owner authentication was originally tested with an isolated P-256 synthetic authenticator. **Позднее A3 на Windows принят с реальным owner browser WebAuthn Approve и Reject (A4 synthetic PASS); отдельная production identity/source admission ещё OPEN.** Credentials persist, sessions/challenges intentionally expire on restart. Run:

```sh
/workspace/repo/.rdg-webauthn-venv/bin/python -B -m unittest discover -s fortis_approvals/tests -v
node --check fortis_approvals/static/app.js
```

Manual **local demo only** (run in an operator-controlled environment, not as a public service):

```sh
python -m fortis_approvals.demo_server --state-dir /private/outside-repository/fortis-demo --port 18990
```

Open `http://localhost:18990`, register a security key with the invitation printed in the local operator terminal, sign in, then approve/reject a synthetic R3 change. This sample uses single-process Python stdlib WSGI, no TLS outside the localhost WebAuthn exception, no restart-surviving sessions and no access to RDG/Sonar. It must **not** be treated as production deployment or a credential bootstrap for live services. For the trusted installation, copy reviewed bytes outside AI-writable paths and have the owner configure TLS/origin, secure storage, trusted secret provisioning and runtime isolation. Live owner acceptance and service adapters remain open.

## G2 always-on owner service (owner-managed Docker Desktop, synthetic only)

**Stability/performance review (2026-10-31):** the original stdlib WSGI
server handled one HTTP request at a time. The reviewed candidate now uses
**up to 16 bounded worker threads** with a 10-second socket timeout, so a
half-sent HTTP request cannot freeze the owner's queue. Routine HTTP 200
polling requests do not grow Docker access logs; HTTP 4xx/5xx remain logged.
The initial Compose `cap_drop: ALL` also prevented `chown` during bootstrap;
`Start-G2.ps1` now initializes the volume via one-off no-network `docker run`
with default CAP_CHOWN, matching the workaround tested by the owner.
Local synthetic HTTP benchmark prior to the fix observed 1.6–2.0 ms median
for HTML/JS/CSS, 48 concurrent unauthenticated requests peaking near 61 ms.
**These are Repo Docker/Linux results, not measurements of Windows Docker.**
The browser error `HOST_DENIED` observed with ChatGPT-generated
`?utm_source=chatgpt.com` is expected strict query-string rejection;
without the appended query, an unsigned `/v1/owner/pending` should return
`OWNER_SESSION_REQUIRED`. Use the unmodified address for auth testing.


This implements the user-approved primary UX: a **persistent owner service**, an
**automatically updating** Pending/History tab (5-second polling), a tab-title
pending count and opt-in browser desktop notifications for *new* requests. The
service continues while the browser is closed; notifications require a
supported browser with this page running and owner session active. Browser
session is valid for 12 hours by default; reauthentication uses WebAuthn. An
ordinary approval is a single explicit click on the exact preview
within the authenticated owner session; extra WebAuthn per decision remains
available for high-risk operations configured by a trusted operator later.

The runtime and portal intentionally expose **no general AI/client request
port**. At G2, requests can only be seeded by the owner-only CLI; real Sonar
integration belongs to G4, and RDG FREE/ASK belongs to G3. DO NOT connect
live credentials or expose port 18990 publicly.

After independent code/image/dependency review, in a **trusted copy outside
Fortis Repo** (e.g. `C:\FortisReview\g2\fortis_approvals`), owner runs these
PowerShell scripts (Docker Desktop with `docker compose` installed):

```powershell
& .\fortis_approvals\deploy\Start-G2.ps1
& .\fortis_approvals\deploy\Invite-G2.ps1
& .\fortis_approvals\deploy\Seed-G2.ps1
```

The start script builds a separate local image, prepares a private named volume,
starts a distinct Compose project with `restart: unless-stopped`, and opens
`http://localhost:18990/` in Windows browser. It does **not** modify RDG,
Sonar, or the legacy Windows updater. Docker Desktop must be configured to start
on login for automatic service recovery after Windows reboot. The first
invitation prints in the **operator's terminal**, is single-use and expires in
5 minutes; paste it only into the owner enrollment form. Seed creates one
synthetic ASK R3 request; the tab should update within ~5 seconds, and
browser notifications can be enabled with the **Включить уведомления** button.
Try both Approve and Reject (seed a second request for the latter), check
History/readback and restart recovery. The owner credential store and pending
SQLite DB live in the named Docker volume, not in the image; login sessions
and unfinished WebAuthn challenges intentionally do not survive a restart.

Operational check: `docker compose --project-name fortis-approvals-g2 -f
fortis_approvals/deploy/compose.yaml ps`. To stop this service only: `docker
compose --project-name fortis-approvals-g2 -f
fortis_approvals/deploy/compose.yaml down`; **do not add `--volumes`**, which
would erase owner keys, requests and audit. The image is built from reviewed
local sources, but exact digest/SBOM/dependency provenance, Windows browser
acceptance and actual Windows Docker lifecycle have **not** been verified.
The implementation uses a single-process WSGI server; no production
availability, host isolation, or deployment approval is claimed.

Tests (in isolated Repo `fido2` environment):

```sh
/workspace/repo/.rdg-webauthn-venv/bin/python -B -m unittest discover -s fortis_approvals/tests -v
node --test fortis_approvals/tests/ui.test.cjs
node --check fortis_approvals/static/app.js
```

## G4 SonarQube Cloud adapter — хронология synthetic → отдельный owner-only live GET; НЕ новый A3

`sonar.py` adds a strict typed SonarQube Cloud (formerly SonarCloud) Web API V1
adapter. Read: `SonarIssueAdapter.list_issues(project_key)` (bounded pagination)
and `read_issue(project_key, issue_key)` (exact issue key + SHA-256 of relevant
issue fields). Write: **one** operation `service=sonarcloud`,
`operation=accept_issue` through existing G1 `ASK` policies and trusted G2
owner session. The operator provides an explicit project allowlist; no generic
URL/method/rule/admin/token routes exist. No live Sonar is contacted by the
module's import, by the tests, or by the current Windows G2 runtime.

Request payload for a project that is **already in the trusted allowlist**:

```json
{
  "requestId": "00000000-0000-4000-8000-000000000001",
  "service": "sonarcloud",
  "operation": "accept_issue",
  "target": "S1",
  "params": {
    "projectKey": "gd-cap",
    "transition": "accept",
    "expectedIssueSha256": "<64 lowercase hex from read_issue>"
  },
  "expectedVersion": 0,
  "reason": "Owner reviews this issue before accepting it"
}
```

`expectedVersion=0` is a *schema placeholder*, not a Sonar version. The
required `expectedIssueSha256` binds status, project, key, update date, rule,
message and a bounded set of other fields. Owner preview includes current
issue and requested `ACCEPTED` status. Core re-preflights before setting its
`DISPATCHED` marker; adapter re-reads before sending the one
`POST /api/issues/do_transition` with `application/x-www-form-urlencoded`.
Then the adapter independently reads the issue again, checks status, persists
an authoritative local receipt and reports `EXECUTED`. A lost response after
upstream commit but before local receipt leaves `UNCERTAIN`; it MUST NOT be
retried without human investigation. Sonar has no conditional CAS for this
transition, so a concurrent editor can still change the issue after the
last preflight. **Do not claim atomic Sonar CAS.**

The optional `SonarHTTPTransport` supports only `https://sonarcloud.io` (EU)
and `https://sonarqube.us` (US) and exactly four V1 endpoint-method pairs:
GET components/show, GET issues/search, GET issues/transitions,
POST issues/do_transition. It blocks redirects, proxies, HTTP, custom hosts, and arbitrary parameters; it
uses standard TLS validation, short timeouts and bounded JSON responses. Real
Bearer tokens MUST be injected at an independently owner-controlled trusted
G4 deployment, never from Fortis Repo, an AI-provided request or the existing
G2 demo. Keep secrets out of CLI args, files in AI-writable mounts and logs.

```sh
/workspace/repo/.rdg-webauthn-venv/bin/python -B -m unittest discover -s fortis_approvals/tests -q
```

The synthetic suite includes a fake remote Sonar transport, origin/route/token
HTTP serialization checks, a cryptographic **test-only** virtual WebAuthn owner
ceremony through G2 portal, negative project allowlists, stale Issue data,
reject, replay, simulated lost POST and readback failure, and receipt-only
read reconciliation. This is not evidence of real Sonar permissions, API
compatibility, trusted credential provisioning or a real test Issue accept.
Before G4 acceptance, an owner must independently confirm the cloud region,
project keys and permissions, provision a scoped token in a trusted isolated
runtime, then run **read-first** integration and an explicitly approved test
Issue mutation with readback. No Sonar credentials or live mutations in Repo.

Source: SonarQube Cloud Web API documentation
`https://docs.sonarsource.com/sonarqube-cloud/appendices/web-api`;
SonarQube Cloud issue editing docs
`https://docs.sonarsource.com/sonarqube-cloud/managing-your-projects/issues/editing`.

## G4 operator READ probe — no changes to running G2

**Status: packaged for owner review; live Sonar read not yet tested.** The one-shot
`sonar_probe.py` permits only `GET /api/components/show` (verifies exact
project key and `TRK` qualifier) and `GET /api/issues/search` (up to five
issues). All POSTs are blocked, and the result contains status counts but no
issue keys, messages or credentials. Even a project with zero issues can be
verified for Browse access.

`deploy/Dockerfile-G4-ReadOnly` copies only four Python modules. It does not
include G2 owner auth or mount the G2 state volume. `deploy/Probe-G4-ReadOnly.ps1`
creates a separate, temporary Docker container with a read-only filesystem,
UID 10001, all Linux capabilities dropped, no-new-privileges, no mounts, no
published ports and bounded PIDs/memory. It needs outgoing HTTPS for the
fixed EU/US SonarQube Cloud API endpoints.

After copying **reviewed sources into an owner-controlled Windows directory**, run:

```powershell
& .\fortis_approvals\deploy\Probe-G4-ReadOnly.ps1 -Region eu -ProjectKey gd-cap
```

The values above are only examples: choose your actual region (`eu` or `us`)
and approved project key. The script asks for the SonarCloud token in a local
hidden prompt and sends it to the temporary container via **stdin**, not via
CLI args, environment variables or a file. A short-lived plaintext copy
necessarily exists in PowerShell/.NET memory; this does not protect against
host administrators or compromised Windows/Docker. Do not share your token
in chat or place it in Fortis Repo. Do not upload the terminal transcript if
it contains sensitive project details.

Expected output is a JSON record with `status=READ_OK`,
`projectVerified=true`, `mutationRequests=0`, `tokenPersisted=false`.
401/403 or wrong region/project fails closed. The token is **not** saved for
future G4 WRITE actions. This probe has no ability to modify SonarCloud.

The installed Fortis Repo workspace does not have Docker CLI or Windows
PowerShell; only the Python probe logic and static Docker/PowerShell build
contracts have been tested there. Actual operator container execution remains
an independent acceptance check.

### G4 all-project discovery (organization-scoped)

**Owner-specified organizations, automatic projects.** Do NOT pass example
project keys such as `gd-cap`. A personal token may cover multiple projects
and organizations, but SonarQube Cloud's supported project listing needs an
organization filter. There is currently no stable public API to discover all
organizations belonging to a token. The owner enters their trusted organization
key(s) **once**, from SonarCloud's organization page (not the project name).

`sonar_inventory.py` calls only `GET /api/components/search` for each
owner-selected organization, pages over **all** results (100/page, max 10,000
projects per organization), verifies the returned project key, type and
organization when present, and fails rather than silently reporting a partial
inventory. It outputs counts and up to 12 project keys; no credentials, issue
messages or names. New projects are found on the next scan. The list is not
permission escalation: only projects visible to the given token are returned.

On the owner's Windows machine, **after installing a reviewed, updated G4
archive** (not the previous single-project probe package), run:

```powershell
& "C:\FortisReview\G4-AllProjects-20261031\fortis_approvals\deploy\Probe-G4-AllProjects.ps1"
```

For multiple organizations, use `@('org-one','org-two')`; substitute actual
organization identifiers from the SonarCloud UI. EU uses `sonarcloud.io`, US
uses `sonarqube.us`. The local PowerShell prompt supplies the personal token
to a separate **temporary** read-only Docker container via stdin; do not paste
the token into chat. The disposable container has no G2 volume or open ports.

The core `SonarIssueAdapter` also supports an `organization_keys` trusted
constructor option instead of a fixed `project_keys` allowlist. Each read and
owner-approved write re-checks project membership with an exact-key search in
SonarCloud; a project added to the owner's organization becomes eligible
without restarting. **This source is NOT installed in the currently running
Windows G2**, and project discovery grants no authorization to mutate an Issue:
G1 policy must still require `ASK`, G2 owner must approve the frozen request,
and SonarCloud must grant `Administer Issues` to perform Accept.

Only the Python synthetic tests have verified dynamic discovery and owner
scope; actual Sonar API compatibility, Windows Docker build and read-only
inventory are independent acceptance checks.

**G4 READ live acceptance (owner report, 2026-10-31): PASS for project discovery and bounded Issues search.** The owner ran the updated `Probe-G4-AllProjects.ps1 -Region eu -Organizations @('alexpastukhh') -ReadIssues` in an isolated one-shot Windows Docker probe and returned `ISSUES_READ_OK`, `visibleProjectCount=3`, `issuesCheckedProjects=3`, `allProjectsChecked=true`, `mutations=0`, `tokenPersisted=false`. All three exact project keys (`AlexPastukhh_gd-cap`, `AlexPastukhh_obs-planning-docs`, `AlexPastukhh_study-tab-launcher`) returned `readOk=true`, five sampled Issues each, all 15 in `OPEN` state. This proves current token can read sample Issues in all currently discovered projects, **not** complete paging of every Issue or the adapter's full `read_issue` projection (`updateDate`, digest, transition eligibility). `tokenPersisted=false` is the probe's implementation/report, not proof of trusted persistent credential provisioning. No Sonar mutations, no G2 runtime changes. **Next**: offline/isolated owner-operated full issue projection/transition GET validation, secure G4 integration boundary and trusted credential provisioning; afterward separately authorized one-Issue ASK+WebAuthn+real transition/readback. No real Sonar WRITE yet.

**G4 live organization discovery, owner-reported 2026-10-31: PASS.** Region `eu`, organization
`alexpastukhh`: the owner ran `Probe-G4-AllProjects.ps1` and received
`DISCOVERY_OK`, `visibleProjectCount=3`, `mutations=0`. Actual Sonar project keys:
`AlexPastukhh_gd-cap`, `AlexPastukhh_obs-planning-docs`,
`AlexPastukhh_study-tab-launcher`. An earlier 404 used unqualified key
`gd-cap`; project list discovery does not yet prove the Issues endpoint or
Issue edit permission.

### G4 single-Issue READ-only preflight (2026-10-31)

After the owner reported live `ISSUES_READ_OK` for all three projects and 15
sampled OPEN Issues, `sonar_preflight.py` and `Probe-G4-IssuePreflight.ps1` add
an independently packaged **GET-only** check of the full `SonarIssueAdapter`
issue projection plus the available transition keys. The script discovers
projects in owner-supplied org(s), reads up to five Issues from each of the
first 30 discovered projects until it finds an `OPEN` issue, re-reads that
specific issue by exact key and project and rejects stale/invalid results,
then requests transition metadata via exact `GET /api/issues/search` with `additionalFields=transitions`. Output contains
only project and issue keys, status, updateDate, SHA-256 of the normalized
projection, field-presence names, transition keys and `acceptOffered`; it does
**not** print the message, file path, rule value, issue details or token.
`acceptOffered` is NOT proof of rights or permission to mutate. This is a
bounded sample (`allIssuesInspected=false`), not an exhaustive issue scan.

The minimal separate Docker image contains `__init__.py`, `core.py`,
`sonar.py`, `sonar_inventory.py`, `sonar_preflight.py` only; its CLI wrapper
permits exclusively three fixed Sonar GET routes. Windows PowerShell reads
token via hidden prompt and sends it to an ephemeral unprivileged container
via stdin, no G2 mounts/ports/state. Actual live single-Issue projection and
transition compatibility remain **unverified until owner-run**. Source has
12 synthetic preflight tests; full Approvals Python suite 98/98 PASS.

The newer inventory supports an **optional `-ReadIssues` switch**. In that
mode a single hidden token entry checks a bounded sample (up to five Issues)
for each of the first 30 discovered projects using only `GET /api/issues/search`.
It returns `ISSUES_READ_OK`, per-project status counts,
`issuesCheckedProjects`, and an explicit `allProjectsChecked` flag if there
are more than 30 projects. No Issue messages or token are printed; no POST is
allowed. The running G2 is still unmodified. This requires a **new reviewed
artifact** containing the updated files; do not assume the already copied
G4-AllProjects folder auto-updates when Repo source changes. Do not provision Sonar write
credentials until read-only discovery and later owner-provisioning gates pass.



**G4 Issue probe v2 after live 404 (2026-10-31):** the optional transition
route from the first prototype returned `SONAR_HTTP_404` after exact Issue
validation. The v2 probe uses search `additionalFields=transitions` instead;
missing metadata means NOT_RETURNED, HTTP 400 triggers plain exact-read
fallback and NOT_VERIFIED. In all cases `writeAuthorized=false`; live WRITE
through the existing Sonar adapter still needs separate compatibility work.

**Owner live G4 exact Issue proof, 2026-10-31 — READ PASS.** Region EU,
organization `alexpastukhh`, project `AlexPastukhh_gd-cap`: owner reported
`ISSUE_PREFLIGHT_READ_OK` with one OPEN Issue, all ten required projection
fields present, returned transitions `accept`, `confirm`, `falsepositive`,
`resolve`, `wontfix`; `transitionLookup=SEARCH_ADDITIONAL_FIELDS`,
`transitionState=RETURNED`, `acceptOffered=true`, `writeAuthorized=false`,
`mutations=0`, `tokenPersisted=false`. An exact Issue SHA-256 was returned
(no raw issue message or token in output). This proves compatibility of the
read and transitions endpoint for that issue, not permission to POST.

**G4 adapter compatibility fix after live READ (2026-10-31).**
`SonarIssueAdapter._before` now sends a single exact GET to
`/api/issues/search` with `additionalFields=transitions` and binds the
current Issue digest, status and available transitions to the same response.
The unsuccessful `GET /api/issues/transitions` was removed from the allowed
transport routes. Missing/malformed transition metadata, non-unique Issue,
changed digest or unavailable `accept` fail closed. Synthetic ASK/Approve
readback, replay, stale, loss and cryptographic G2 tests pass; no live G4
WRITE has happened. Actual POST, Administer Issues permission, trusted token
provisioning and G4/G2 deployment still need explicit owner-side acceptance.

## G4 ASK candidate — isolated owner portal, WRITE DISABLED (2026-10-31)

The owner-reported real SonarCloud single-Issue probe returned
`ISSUE_PREFLIGHT_READ_OK`, all expected normalized fields, and transitions
`accept/confirm/falsepositive/resolve/wontfix` for an OPEN Issue in
`AlexPastukhh_gd-cap`. This was a READ proof, **not write permission**.

`g4_candidate.py` now composes the existing G2 `OwnerPortal`/WebAuthn UI with
one `SonarIssueAdapter` and the trusted `ASK` policy. Its trusted local-only
`propose_issue(core, adapter, project_key, issue_key, reason)` obtains a fresh
Issue SHA-256 from the server, performs read-only preflight against project
membership and available transitions, and inserts `PENDING` into the same
candidate Core DB displayed by the portal. `g4_operator.py` is an in-process
CLI entry point (no new HTTP submit endpoints); the proposal reason is read
from stdin. G4 remains scoped to owner-selected organizations; it is not a
Sonar project administrator or an AI-controlled permission expansion.

**Strict safety boundary:** `build_candidate()` refuses an existing G2 SQLite
state without its separate candidate marker, has its own owner enrollment
and state, and requires owner-specified trusted organization/token settings.
The optional `g4_server.py` is a separate server entry point, not installed
or started by the current Windows G2. No Docker operator installer or secret
provisioner is released yet. The candidate must use its own state/port/owner
credential. Do not repoint it at the running `fortis-approvals-g2` volume.
The token file must be a private owner-owned regular file outside AI mounts;
its contents are neither echoed nor written to DB or log. Do not supply a
Sonar token to Fortis Repo or ChatGPT.

**WRITE remains impossible in this candidate**: the OwnerPortal marks its G4
rows `approvalAllowed=false`, the UI disables the Approve button, and both
session and WebAuthn approval routes reject approval. Rejection remains
WebAuthn-verified and auditable. A second independent transport guard refuses
POST even from a direct Core execution attempt. No production G2 process or
existing state is modified by these code changes. A future separate
owner-approved deployment/provisioning and controlled transition to an actual
WRITE-enabled adapter are still needed.

Synthetic tests: `test_g4_candidate.py` verifies real portal enrollment/login,
G4 Pending/Reject/History, rejection of attempted Approve on every owner
route, exact preview, re-open after restart, isolation from existing G2 state,
project scope, missing accept, token file restrictions and zero outbound POST.
Full Approvals Python tests: 113/113 PASS; Node UI: 3/3 PASS. These tests
have no real Sonar credentials or real owner approval. The live owner G2
remains unchanged; this is not G4 deployment acceptance.

## G4 Windows owner-only read-only candidate package (2026-10-31)

Windows operator deployment source (review first):
`deploy/README-G4-Candidate.md`, `deploy/Dockerfile-G4-Candidate`,
`deploy/compose-g4.yaml`, `deploy/Prepare-G4-Candidate.ps1`,
`deploy/Provision-G4-Token.ps1`, `deploy/Start-G4-Candidate.ps1`,
`deploy/Invite-G4-Candidate.ps1`, `deploy/Propose-G4-Issue.ps1` and
`deploy/Stop-G4-Candidate.ps1`. G4 uses separate Docker Compose project,
port 18991, independent state and token volumes and separate WebAuthn
registration; the G2 service on 18990 is untouched. The local hidden
PowerShell prompt/one-shot offline bootstrap stores the token in a private
Docker volume only with explicit `STORE` confirmation. This is an unencrypted
volume accessible to Docker/host admins. The candidate permits real READ +
local ASK creation and WebAuthn rejection, but disables Sonar approval and
blocks POST at transport. Synthetic tests pass; Windows Docker owner
acceptance has not yet been performed. No G2 replacement, no automatic WRITE.

**G4 Windows token-volume failure and conservative repair (2026-10-31):**
The owner showed both G4 named-volume roots as UID 0/mode 0755 even after
separate chown and chmod commands returned success. No token file existed;
uid 10001 cannot write at the root (errno 13). The G4 storage layout now
uses *children* `/state/private` and `/run/g4-token/private`, uid/gid
10001/mode 0700. `g4_volume_repair.py` initializes/verifies those children
in an offline privileged initializer and a separate unprivileged check.
`deploy/Repair-G4-Existing-Volumes.ps1` upgrades the G4 image and repairs
ONLY the existing G4 volumes; the `Prepare` script is for new volumes and
must not be re-run against existing ones. Both scripts stop if private
folders/volumes contain unexpected earlier content. Token provisioning
checks the private token directory before soliciting a secret. The
Compose/runtime state and token path were updated together. No G2, no Sonar
WRITE and no credential operation until the owner-run repair passes.

## G4 security reviewer entry point (owner Windows logs 2026-10-31)

Read [`deploy/SECURITY-REVIEW-G4.md`](deploy/SECURITY-REVIEW-G4.md) before
token, Docker, owner authentication or future WRITE changes. It records the
actual Windows private-directory repair, local `STORE` + hidden-token
provisioning success, G4 owner service start at `localhost:18991`, reported
WebAuthn enrollment/login, the **unencrypted** Docker token volume and
its memory/host-admin exposure, protected state containing Sonar Issue
previews, G2 isolation and explicit open verification gates. In particular,
**At the time of that earlier note the live Issue ASK was unverified; the later owner milestone below reports Pending/Reject PASS.** Sonar POST remains
forbidden. Runtime Docker showed benign warnings for pre-created G4 volumes;
repo `compose-g4.yaml` now labels both `external: true` for a future reviewed
owner-side update **without redeploying the running container**.

**First real G4 ASK on Windows (owner-observed 2026-10-31):** local Sonar
READ resulted in a request visible in G4 Pending, only Reject was available,
and successful Reject required a PIN in the WebAuthn/OS verification flow.
The G4 server requires UV flag in signed WebAuthn assertions; it does not
receive the authenticator PIN. This does not certify WebAuthn device security.
The owner subsequently observed G4 History `REJECTED`, closing the owner-UI
history gate. At this earlier checkpoint, independent GET readback was OPEN;
real POST remains disabled. Detailed audit record:
`deploy/SECURITY-REVIEW-G4.md`.

**G4 post-Reject GET check ambiguity (2026-10-31 owner Windows):** after a
second G4 ASK for the same Issue returned request ID
`69898cab-809d-468a-aaeb-be64dde1295e`, `PENDING`, the first GET-only
readback reported local `REJECTED`, remote Sonar `OPEN`, SHA match `YES` and
`PASS`. That readback selected by project/Issue and timestamp+UUID ordering,
not by the second exact request ID; it proves only a snapshot of **some**
rejected request matched the remote Issue, not that the second `PENDING` was
rejected. The old output `G4_CHECK_SONAR_POST_REQUESTS: 0` was a hardcoded
source indicator, not observed network telemetry. Fixed readback requires a
canonical explicit `-RequestId` and exact SQLite ID lookup; a selected
`PENDING` request fails before remote GET. New output states
`G4_PROBE_GET_ONLY: YES` (code-property, not packet count). Synthetic
regression covers older REJECTED + newer PENDING on the same Issue.
At the earlier patch-release checkpoint, owner execution of the exact-ID readback was OPEN; the later owner-acceptance record below closes that gate.
Details: `deploy/SECURITY-REVIEW-G4.md`.

**G4 exact-ID Sonar readback acceptance (owner report, 2026-10-31): PASS.**
After installing the hash-verified exact-request hotfix, owner executed
`Verify-G4-Rejected-Readback.ps1` with project
`AlexPastukhh_gd-cap`, Issue `AaDX-EdYT7YShyBpAy0r` and request
`69898cab-809d-468a-aaeb-be64dde1295e`. The script reported
`G4_LOCAL_HISTORY: REJECTED`, `G4_REMOTE_STATUS: OPEN`,
`G4_REMOTE_PROJECTION_MATCH: YES`, `G4_READBACK_AFTER_REJECT: PASS`,
`G4_PROBE_GET_ONLY: YES`. The earlier ambiguity is resolved for the exact
request. The command performs readonly local SQLite and upstream GET and
compares the issue projection; the GET-only indicator is a source code
property, NOT captured network telemetry. This closes functional G4
READ→ASK→Reject→GET-readback owner acceptance, NOT authorization to enable
Sonar POST/WRITE, or proof of token least privilege, revocation, or absence
of intermediate external changes. See `deploy/SECURITY-REVIEW-G4.md`.

**G4 WRITE security architecture review, 2026-10-31 (NO-GO for POST):**
[`deploy/G4-WRITE-SECURITY-REVIEW.md`](deploy/G4-WRITE-SECURITY-REVIEW.md)
is a review-only B1-B8 security assessment under the **owner-directed
broad-token + mandatory Fortis ASK model** (see
[`deploy/G4-WRITE-PRIVILEGED-TOKEN-ADR.md`](deploy/G4-WRITE-PRIVILEGED-TOKEN-ADR.md)).
It covers privileged token custody, non-bypassable owner WebAuthn proof, candidate bypass defense,
non-atomic Sonar GET→POST, `UNCERTAIN` manual reconciliation, quality-report
impact, and one-shot test release gates G4-W0..G4-W7. It contains source
pointers, synthetic negative test matrix and official Cloud references.
The real owner G4 remains READ/ASK/Reject on 18991; no G2/G4 changes, POST,
credential rotation or owner token disclosure were requested or performed.

**G4 WRITE next owner-safe step (2026-10-31):**
[`deploy/G4-WRITE-OWNER-INVENTORY.md`](deploy/G4-WRITE-OWNER-INVENTORY.md)
contains read-only SonarCloud UI checks for account PAT, expiry, project
Browse/Administer Issues and restricted scoped organization tokens, with
category-only reporting and NO token values. New isolated WebAuthn+FakeSonar
negative suite exercises strong approval, bypass/UV/CSRF, stale, timeout,
429 and races entirely offline; the synthetic GET→POST race reproduces the
missing atomic Sonar CAS. G4 remains NO-GO for real POST.

**G4 credential cross-organization scope clarification (owner 2026-10-31):**
owner reports the existing Sonar token is not linked to a single organization.
If account PAT, it inherits all issuer permissions in all accessible orgs;
current `FORTIS_G4_ORGANIZATIONS` is an application allowlist, not a
credential restriction. Compromise of a privileged token can therefore
bypass Fortis and affect other accessible organizations. Token type and
actual permissions remain unverified. The broad-token design is intentional:
Fortis enforces requests through server-side ASK, while preventing external
token theft remains a separate host/executor security requirement. W1 is
**OPEN for custody and explicit risk review**, not blocked by token breadth
alone. See `deploy/G4-WRITE-PRIVILEGED-TOKEN-ADR.md` and
`deploy/G4-WRITE-OWNER-INVENTORY.md`.

**Architectural decision for G4 WRITE (2026-10-31):** the owner explicitly
chooses a broadly privileged SonarCloud token; Fortis is responsible for
restricting all *Fortis-originated* changes via server-side ASK and verified
WebAuthn approval. A low-privilege Sonar token is not a required gate.
Credential exfiltration bypasses ASK; protect the owner-only executor, token
storage, trusted code and host, and document explicit residual exposure.
The real G4 read-only candidate remains unchanged. See
[`deploy/G4-WRITE-PRIVILEGED-TOKEN-ADR.md`](deploy/G4-WRITE-PRIVILEGED-TOKEN-ADR.md).

**G4 privileged-token + mandatory ASK executor LAB (2026-10-31):**
`g4_write_lab.py` and `tests/test_g4_write_lab.py` implement a pure offline
`LabSonar` in-memory fake and `LabPostGate`: exact approved request identity,
verified Core request fingerprint and PENDING→APPROVED→DISPATCHED events,
WebAuthn owner UV via the local synthetic browser, and durable SQLite
single-use reservation before any simulated POST. The lab tests direct
PENDING/ALLOW/forged owner bypass, reject/stale, wrong decision, lost response,
429, concurrent second dispatch and persisted replay after simulated crash.
Three additional tests verify a separate spawned Python worker that reads
an exact owner-WebAuthn-approved request, and cannot execute PENDING,
REJECTED or previously dispatched work. The owner-side test process has
`NoWriteTransport`; the worker has `LabSonar` only and no real credential.
All **173 Python tests PASS**; 3 JavaScript UI tests and docs audit PASS.
The fake still demonstrates the upstream GET→POST CAS race; real WRITE
process isolation, token custody and permission are NOT implemented.
**Do not install in G2/G4 or use real Sonar credentials.** Full findings:
[`deploy/G4-WRITE-LAB-ACCEPTANCE.md`](deploy/G4-WRITE-LAB-ACCEPTANCE.md).

**Shared ALLOW/ASK dispatcher correction (2026-10-31):** G1 Core executes
`ALLOW` immediately and `ASK` after owner approval through the **same**
`Core.execute()`. G4 lab gate now checks distinct, trusted policy-specific
ALLOW/ASK event chains before a common fake dispatch and durable reservation.
Two added regression tests confirm correct ALLOW behavior and denial of
policy mismatch. Real Sonar `accept_issue` stays ASK-only; no running G2/G4
Docker image or compose config was changed. The two deployed containers are
separate *test stages*, not different permanent Fortis architectures.

**Unified Fortis Approvals offline composition (2026-10-31):**
[`unified_lab.py`](unified_lab.py) and
[`tests/test_unified_approvals_lab.py`](tests/test_unified_approvals_lab.py)
prove **one** Core, owner UI, WebAuthn credential database, Pending/History
queue and unified `Core.execute` for two typed adapters. Synthetic policy
supports trusted actor-specific ALLOW/ASK/DENY; an in-memory fake Sonar
adapter uses READ + mandatory ASK with owner Approve and POST blocked, but
owner WebAuthn Reject works. Eight negative/integration tests bring the
synthetic suite to **181/181 Python**, 3/3 JS UI and docs audit PASS.
The fake has no token or network; lab state is created only in a fresh private
temporary folder and refuses unreviewed migration from either G2/G4 DB.
Existing G2 18990 and G4 18991 are **two isolated test deployments**, not
permanent logical services or separate policy/execution engines. A second WRITE container was an older option; **the selected target now is ONE trusted Fortis container with owner-only tokens and typed execution**. A different split would require a new owner decision.
All Windows owner environments/volumes/passkeys/credentials remain untouched.
Full detailed cutover gates and WebAuthn-origin/history risks:
[`deploy/UNIFIED-APPROVALS-CUTOVER-PLAN.md`](deploy/UNIFIED-APPROVALS-CUTOVER-PLAN.md).

**Primary Fortis Repo integration contract, stage 1 (2026-10-31; NOT
DEPLOYED):** [`repo_action_contract.py`](repo_action_contract.py),
[`tests/test_repo_action_contract.py`](tests/test_repo_action_contract.py)
and [`deploy/FORTIS-REPO-ACTION-CONTRACT-V1.md`](deploy/FORTIS-REPO-ACTION-CONTRACT-V1.md)
implement the first owner-requested architecture step: Fortis Repo proposes
a restricted typed *intent* (`requestId,service,operation,target,params,reason`),
not a token-bearing arbitrary HTTP command or an owner `approved` field.
The contract authenticates a separate limited caller grant, checks a trusted
per-actor operation allowlist, derives Sonar Issue digest from the trusted
read adapter, and sends the exact internally constructed request through
the existing **single ALLOW/ASK Core**. The source broker returns only
`requestId` and `state` (no private Issue preview, fingerprint, actor or
service credential). Real Sonar `accept_issue` remains mandatory ASK and
its POST remains disabled in the existing G4 candidate. Source/tests
**193/193 Python**, **3/3 UI** PASS; no Repo→Windows listener or privileged
Executor IPC has been created. **This code is offline lab only** and must
not be installed in either running G2/G4. The future target has one Approvals
owner UI/queue and **ONE owner-trusted container** with private token store
and typed execution. A second executor container is no longer a prerequisite.

**Fortis Repo → Approvals API ingress, STEP 2 SOURCE ONLY (2026-10-31):**
[`repo_ingress.py`](repo_ingress.py) wraps the typed `RepoIntentBroker` in
a strict WSGI server-side application that exposes only authenticated
POST `/v1/actions` (submit) and GET `/v1/requests/<UUID>` (actor-owned
status). It rejects unknown owner/admin/executor routes, browser cookies,
Origin, forwarded headers, wrong Host/TLS scheme, oversized JSON, duplicate
keys, caller-supplied policy/token/HTTP method and status cross-access.
In-memory per-actor rate limits are **not** a production-wide rate-limit.
[`tests/test_repo_ingress.py`](tests/test_repo_ingress.py) covers the
security boundary and one ephemeral **Linux loopback HTTP** smoke test
using fake ingress credentials and synthetic ALLOW + status. **Historical
stage-2 snapshot:** 204 Python and 3 UI tests PASS at that checkpoint;
the current combined suite is checked separately, not inferred here. No actual Fortis Repo
network route to Windows Approvals, deployed WSGI service, real ingress
grant, TLS configuration, privileged token or owner-side Docker change.
Next is owner-reviewed production ingress networking/identity and an
**in-container** protected credential resolver/typed adapter (no extra
Executor process/container or IPC), **not** another Approvals panel.
See [`deploy/FORTIS-REPO-INGRESS-GATE-V1.md`](deploy/FORTIS-REPO-INGRESS-GATE-V1.md).

**Latest architecture supersession (2026-10-31):** old split-worker/proposal-only
ADR details are historical. Deploy exactly one owner-trusted Fortis runtime
with restricted machine/owner routes and a private secret resolver; do not
introduce a second executor container merely because a lab subprocess exists.
Sonar real POST remains NO-GO until specific new owner authorization.


**R7 P2 source change — owner-WebAuthn-gated Sonar execution (2026-11-02; SOURCE ONLY):**
The scoped R7 candidate now permits the single typed `sonarcloud.accept_issue`
operation to execute only after a strong owner WebAuthn Approve. The machine
actor still has only typed READ and ASK proposal routes; no owner decision,
transport selection, token access, or execute endpoint is exposed to it.
`Core.owner_decide` rejects approval when the durable request policy version
or current ASK rule no longer matches, both before and after proof verification.
`Core.execute` independently rechecks policy, expiry, active grant and the
frozen Sonar Issue preview; the adapter performs one `accept` POST followed by
an independent GET readback and durable receipt confirmation. Ambiguous remote
outcomes remain terminal/UNCERTAIN and are never blindly retried. Sonar's API
still has no atomic compare-and-set between the final GET and POST; this race
is an explicit residual risk, not a claim of transactional upstream locking.

A new policy version, `r7-p1-sonar-accept-issue-write-v1`, invalidates older
Pending requests for approval. The owner UI exposes approval only for requests
created under the current policy; reject remains available. Existing issues
are not bulk-modified. Selected regression batch: **64/64 PASS** (P2 static guardrails, Core,
Sonar READ adapter/inventory, and historical P1/v2 package-manifest checks);
changed Python sources compile. The R7 WebAuthn integration suite could not
run in this Linux workspace because pinned `cryptography` and `fido2` dependencies are absent.
No real Sonar request, POST, token provisioning, Docker build, or deployment
was performed. The existing P1 image/package is stale and must not be used for
this source revision; a new immutable review package and owner-side image audit
are required before any runtime rollout. See
[`deploy/R7-P2-WEBAUTHN-EXECUTE-SOURCE-REVIEW-20261102.md`](deploy/R7-P2-WEBAUTHN-EXECUTE-SOURCE-REVIEW-20261102.md).

## R7 P2 release preparation — 2026-11-03

The current P2 checkout is sealed in `/workspace/repo/Workfiles/fortis-r7-unified-source-review-p2-20261103.zip` (SHA256 `a3e87c0c8643e79db48655aae9e100029b6f0bd6683369e565e59ec995718748`; manifest SHA256 `d766c28b9d2ea52e40f613614d85962e8eeee61393bbf80d8acf7be6ae05c1db`). The package has exactly 20 allowlisted source files plus its manifest. Owner transfer copies are under `_fortis_windows_transfer_tmp/20261103-r7-p2-release/`.

`Build-R7-Windows-ImageOnly-p2-20261103.ps1` and `Audit-R7-P2-Windows-ImageOffline-20261103.ps1` are new P2-only scripts. The build performs no deployment; the audit requires the resulting exact image digest and performs only metadata, installed-source SHA256 and isolated import checks. Static/Core/typed-client verification is 44/44 and compileall passes. Full WebAuthn/HTTPS tests are blocked in this Linux workspace because pinned `cryptography`/`fido2` cannot be installed here; no image build, rollout or Sonar request has occurred.


## Owner-reported P2 image gate PASS — 2026-11-03

The exact P2 image-only Windows build and offline installed-source audit passed.
Image ID: `sha256:e751f6ca0cfe6ce290cf580de2f243071ee1f3e681baa8827c6cea41a16fa402`.
Metadata, 19 installed source hashes, exact import smoke and disposable
container cleanup all passed. No token, Sonar network request, live deployment
or container startup was performed. Rollout and live E2E remain separate owner
controlled gates.
