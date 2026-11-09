# Fortis Repo → Fortis Approvals: typed action intent contract v1

> **Исторический срез 2026-10-31.** Утверждения ниже вида «Repo→Windows не работает», «только offline», «A3 не развернут» и старые числа тестов описывают состояние **на тот момент**, а не актуальный факт. **2026-11-01: A4 synthetic Repo→Windows A3 TLS/ASK/ALLOW/Reject и Windows ACL/status PASS; production admission и Sonar READ в едином Fortis OPEN.** Действующие статусы/задачи — в [основном плане §12–14](../../docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md). Owner решил **отложить** процедуры ручной замены TLS и выдачи/отзыва machine access до production admission; ближайшая работа Sonar READ offline без реального токена.


**OWNER DECISION updated 2026-10-31 (supersedes older split-container text):** **ONE owner-controlled Fortis Secure Gateway Docker container** handles typed caller intents, policy/ASK, owner WebAuthn, private token store, typed adapter execution and audit. Sonar tokens do **not** belong to Fortis Repo or the public caller/browser response; they ARE stored and used inside that SAME trusted Fortis container. A single trusted policy determines `DENY / ALLOW / ASK`. `ALLOW` and owner-approved `ASK` enter the **same Core execution/adapter route**. ASK is a pause and approval, not a second execution engine. Current running Windows G2 (`18990`) and G4 (`18991`) are legacy isolated **development candidates**; they are not the target container-role architecture.

**Stage 1 status: IMPLEMENTED AS SOURCE CONTRACT + OFFLINE TESTS ONLY.** This document describes `fortis_approvals/repo_action_contract.py`, `tests/test_repo_action_contract.py` and their integration with the existing offline `unified_lab.py`. **No Fortis Repo-to-Windows route, HTTP listener, gateway deployment, IPC endpoint, new Docker Compose project, token mount, external Sonar GET/POST or production executor is created.** Running G2/G4 and their token/SQLite/WebAuthn volumes remain untouched.

## R1 Sonar READ typed contract — текущий source checkpoint (2026-11-01)

**STATUS: SOURCE PASS, NOT A DEPLOYED READ ENDPOINT.** `repo_action_contract.py` поддерживает отдельную проверку `validate_read_query` и `RepoIntentBroker.authorize_read` для четырёх SonarCloud READ операций: `list_projects` (target organization, `page/pageSize`), `list_issues` (target project, `page/pageSize`), `get_issue` (target Issue, `projectKey`), `get_quality_gate` (target project, params `{}`). Общие обязательные поля `requestId/service/operation/target/params/reason`, UUID, формат ключей, ограниченные страницы, точные поля, запрет nested `token/method/url/transition` проверяются **до** доступа к адаптеру. Trusted grants для READ **отдельны** от grants на `submit`; нужно аутентифицировать машинный credential, проверить granted operation и **Core policy ALLOW**, включая возможные owner-controlled target/params predicates. R2 должен отдельно проверить фактическую принадлежность проекта разрешённой организации по доверенному Sonar API, а не опираться лишь на шаблон ключа.

**Никакой новый HTTP маршрут, GET к Sonar, токен, owner UI, adapter result и real READ не появились.** Действующий `POST /v1/actions` принимает **только actions**, попытка отправить туда READ возвращает 403, никакого `Core.execute` из READ не происходит. `accept_issue` остаётся прежним отдельным ASK proposal. Проверены новые negative/positive source tests вместе с общими регрессиями: **220/220 Python, 3/3 JS UI PASS, docs audit PASS**. R1 закрыт как **контракт**, R2–R5 OPEN; Windows A3 и G2/G4 не менялись. Старое описание ниже — историческая реализация stage 1, не актуальный запрет будущей разработки READ.

## R2 Sonar READ domain adapter — source acceptance 2026-11-01

**SOURCE PASS, NOT LIVE SONAR:** новый `fortis_approvals/sonar_read.py` принимает **только уже авторизованный** R1 query, предназначен для trusted in-process composition **после** `RepoIntentBroker.authorize_read`, и **не** создаёт machine HTTP READ endpoint. Owner задаёт 1–20 допустимых организаций; `list_projects` использует существующий строгий `sonar_inventory.discover` (до 100 страниц × 100 проектов с явным fail-closed), `list_issues` получает отдельные страницы Issues с `total/page/nextPage/coverage`, `get_issue` проверяет точный Issue key/project, `get_quality_gate` выдаёт фиксированные поля статуса/условий. READ транспорт **самостоятельно блокирует POST**, произвольные paths/params; `SonarHTTPTransport` поддерживает новый конкретный `GET /api/qualitygates/project_status` только с `projectKey`. Вызовы чужого проекта отвергаются после проверяемого текущего membership в owner-allowed org **до** Issues/QualityGate GET; `allowlisted` поля исключают raw API/token/owner snapshots. При Sonar search >10k Issues явно `coverage=CAPPED_AT_10000`, не объявлять список полным. Пагинация между отдельными GET **не** является атомарным snapshot; точное PR/run/SHA доказательство — D2.

**Принципиально НЕ завершено:** R3 связывает R1 auth и R2 reader в одном machine ingress с безопасной публикацией результата, контролем размера ответа и redacted errors; R4 проверяет exact minimal image assembly; R5 требует отдельной доверенной owner-приёмки Windows + token provisioning после отложенных TLS/grant production gates. Настоящий Sonar POST NO-GO. Тесты **233/233 Python + 3/3 UI PASS**, docs audit PASS, без Windows/секретов/сети Sonar.

## R3 Repo machine READ ingress — source acceptance 2026-11-01

**R3 SOURCE PASS / WINDOWS DEPLOYMENT NOT DONE.** Существующий `RepoIngress` поддерживает **`POST /v1/reads`** (отдельно от `POST /v1/actions` и actor-only `GET /v1/requests/<uuid>`), но маршрут доступен только при доверенном `RepoIntentBroker(read_adapter=SonarReadAdapter(...), actor_read_operations={...})`; по умолчанию reader отсутствует и READ закрыт. Выполняются HTTPS/host-header/origin/body strict checks, bearer-machine auth, actor rate limit, source R1 validation + independent read grants + `Core._policy == ALLOW` **до Sonar GET**. READ result не пересекает `Core.submit/Core.execute`, не создаёт owner Pending и не включает `accept_issue`. `sonar_read.py` проверяет owner-approved org/project membership и фильтрует поля Issues/Quality Gate; broker блокирует неожиданные top-level/nested поля; ingress возвращает `{requestId,service,operation,data}` с cap 65536 bytes (иначе HTTP 413). Bad credential/policy/route/error — без сырых upstream body/headers, токенов, owner snapshots и произвольного proxy. Временный loopback HTTP test с фиктивной машинной авторизацией — PASS. **247/247 Python, 3/3 JS UI, docs audit PASS.**

**R3 ещё НЕ означает live Sonar:** работающий A3 image synthetic-only, Sonar reader/owner token в него НЕ установлен. R4 — точная minimal-image сборка/import и расширенная security/release регрессия; R5 — отдельно одобренный владельцем trusted Windows import/review/token input и реальные GET после закрытия отложенных TLS/manual replacement и machine grant issue/revoke. Реальный Sonar POST — NO-GO.

## R4 exact source isolation — result 2026-11-01

**SOURCE COPY/ISOLATION PASS, DOCKER BUILD NOT TESTED.** Только временная R4 test-сборка `Dockerfile-R4-Sonar-Read-Check` с allowlist из семи source modules + одного smoke test; тест `test_r4_image_manifest.py` проверяет этот же exact COPY в чистом каталоге через isolated `python -I -S -B`, не импортируя остальную копию Repo и site-packages. Настоящий Core, auth/policy/typed ingress/GET-only Sonar Fake проходят позитивные и negative security tests, без secrets, POST и owner state mutation. `R4_COPIED_SHA256_MANIFEST=774baad40ded4eb1aa4cea9755bcf1efa9dcf2aecd7adf1c8c7b5b9253d6a9bc`. Full regressions **254/254 Python + 3/3 JS UI PASS**, docs audit PASS. **Docker CLI в Repo нет, real Docker image НЕ собирался и НЕ запускался.** Не считать это production image admission; R5 требует независимого owner-controlled exact source/base review и двух deferred TLS/grant procedures до реального Sonar token. Исполняемый текущий Windows A3 всё ещё synthetic-only; Sonar POST NO-GO.

## R5 unified Sonar READ source candidate — prepared, not deployed (2026-11-01)

`r5_read_candidate.py` строит **один** Core + owner WebAuthn portal + machine ingress с Sonar READ; `Core.adapters={}`, `actor_operations={}`, only `SONAR_READ_OPERATIONS` with trusted `ALLOW` — нет регистрации `accept_issue` или POST. Trusted runtime `r5_read_server.py` использует separate owner console (port 19103) и TLS1.3 machine (port 19104), считывает R5 machine grant и Sonar API token **только из разных приватных 0600 файлов**. R5 не перенимает существующие A3/G2/G4 volumes; marker от нового пустого R5 state отдельно проверяется. Исходный Dockerfile/Compose — **кандидаты, ни разу не собраны/не запущены**, и оба требуют независимого owner source/image/secret/TLS admission. Тесты exact allowlist stripped import, настоящего localhost TLS и fake Sonar read без remote POST — PASS (**266/266 Python, 3/3 UI**); это **НЕ live Sonar READ PASS**. Отложенные процедуры TLS replacement и machine grant revoke/issue должны быть закрыты перед production token. Прежний A3 bootstrap не запускать на существующих volumes.

## 1. Trust boundaries and intended roles

**Single-container architecture takes precedence over any older text below that mentions an isolated second executor.** Machine request and owner browser remain separately authorized **routes**, but secrets, policy and execution live in **one** owner-trusted container. Secrets and ASK are independent conditions; four cases are defined in master plan §0.

```text
Fortis Repo — untrusted requester, no service tokens, no owner API
    |
    | typed intent v1 + independent restricted ingress credential
    v
Approvals ingress / trusted Core policy / owner review
    | - authenticate caller to server-issued actor (never actor from JSON)
    | - enforce per-actor operation grants + DENY/ALLOW/ASK
    | - persist exact immutable request + preview/fingerprint/history
    | - for ASK: PENDING, owner WebAuthn decision, no dispatch until approve
    | - do NOT expose external SonarCloud/RDG credential to caller/browser
    v
One authorized dispatch path (ALLOW or approved ASK)
    | - exact request identity and durable one-use dispatch protection
    | - fixed internal Core.execute -> typed adapter (same container)
    v
Typed Executor module INSIDE the SAME Fortis container (future production integration)
    | - holds privileged service credential; no public arbitrary HTTP proxy
    | - resolves necessary upstream read/snapshot and performs typed action
    | - remote readback, receipt, UNCERTAIN on ambiguous attempt
    v
SonarCloud / later RDG or other protected services
```

**Current owner decision:** one owner-controlled Fortis Docker contains the machine ingress, owner UI/WebAuthn, restricted server policies, private token store and typed executor. Distinct machine/owner **authorization routes** do not imply separate services or containers. A later split requires a new owner decision; the current contract does not require a second Executor or IPC.

## 2. Untrusted request: closed envelope, JSON only

**Scope of current code:** the stage-1 intent catalog implements only fake `synthetic` test actions and proposal of Sonar `accept_issue` in ASK mode. **It does not yet provide Sonar `READ` as a Repo-callable ALLOW operation, any RDG/GitHub adapter, a generalized secret resolver or a trusted Windows deployment.** These are target capabilities, not working production routes.

Exact top-level keys (required, no extras): `requestId`, `service`, `operation`, `target`, `params`, `reason`.

- `requestId`: canonical lowercase UUID supplied by requester for tracking/idempotency; reuse for the same action only. Do not generate a new UUID automatically after a remote outcome is `UNCERTAIN`.
- `service` + `operation`: **exactly typed** in a trusted allowlist; the caller cannot inject a new operation, REST method, URL, path, credentials, owner, actor, `approved`, `policy`, or proof.
- `target`: typed name/key, nonempty and bounded; service adapter must still verify live identity/scope.
- `params`: **per-operation strict schema**, not arbitrary executor parameters. Reject unknown nested fields and wrong types.
- `reason`: human-readable rationale, 1–1500 characters; **never include secrets or private credentials**. Owner preview can retain this text; don't treat it as authorization.
- **External service tokens and owner WebAuthn credentials are never caller fields.** A separately provisioned restricted ingress grant authenticates caller transport; it is NOT the SonarCloud bearer token and does not grant `owner_decide` or an executor command endpoint.

### SonarCloud `accept_issue` proposal

The requester supplies only the **intent** to accept one Issue, without a Sonar POST or a claimed Issue snapshot:

```json
{
  "requestId": "00000000-0000-4000-8000-000000000001",
  "service": "sonarcloud",
  "operation": "accept_issue",
  "target": "LAB-1",
  "params": { "projectKey": "lab_project" },
  "reason": "Review whether this test Issue should be accepted"
}
```

**Trusted internal conversion** calls the Sonar adapter's strictly scoped `read_issue(projectKey, target)` to retrieve a current normalized SHA-256 projection. The resulting internal Core payload has `expectedVersion=0`, `params={projectKey, transition:"accept", expectedIssueSha256:<server-derived digest>}`, exactly one `requestId`, and the original reason. The requester **cannot** provide `transition`, `expectedIssueSha256`, HTTP method, Sonar organization override, token or arbitrary URL. The API adapter independently validates project/Issue membership and frozen preview again. The broker additionally refuses Sonar intents unless the trusted Core policy resolves to **ASK** (first checked **before any upstream GET**, then rechecked with the trusted server-derived digest). This is defense in depth; in the final executor it must be independently enforced, not merely accepted as a broker assertion.

### Synthetic operations — tests only

`service=synthetic`, operations `set_free`, `set_ask`, `set_deny` with exactly `{value: string, expectedVersion: nonnegative int}`. They exist to prove the common `ALLOW → Core.execute()` and `ASK → owner → Core.execute()` semantics and default-deny policies. They are **not a route to arbitrary tools or external API access**. The final Fortis Repo permission catalog must list only explicitly reviewed operations.

## 3. Trusted in-process stage-1 implementation

`validate_intent(intent)` rejects unknown fields, operations, bad UUIDs, invalid scopes/types, malformed UTF-8 and attempts to supply Sonar executor parameters. `RepoIntentBroker(core, actor_operations=<trusted mapping>)` is a **source-level broker**, not a deployed service. It authenticates a *separate ingress grant* through `Core.auth.authenticate()`, checks an independently trusted **per-actor operation allowlist before remote reads**, then generates a strictly typed Core request and delegates to the existing `Core.client(grant, 'submit', typed_payload)`.

**Current result limitation:** the existing Repo-facing API returns only `{requestId,state}`. Real Sonar READ without ASK requires a **per-actor, operation-scoped, allowlisted result projection** (Issue information where authorized), not just a status. Approved or automatic mutations may need a similarly redacted completion receipt/status. The current v1 source **does not implement safe Repo READ result delivery**. Extend this exact typed broker/ingress after A4; never return raw service bearer, owner preview, upstream headers, full generic HTTP response, or arbitrary URL output.

The broker sends callers only `{requestId, state}`. It does **not** return raw Core owner views, Issue messages, preview snapshots, Sonar URLs, actor/owner identity, WebAuthn session, fingerprints or remote result bodies. `status(grant, requestId)` uses the existing `Core.client(grant, 'status', requestId)` **actor isolation**, again returning only ID and state. No `/owner/approve` or generic `execute(method,url)` endpoint is introduced.

**Critical isolation caveat:** for the present **offline tests**, the broker and Core are in one Python process with `UnifiedFakeSonar` and no credential. In the final **single trusted Fortis container**, the GET that creates the frozen Sonar preview must use the in-container typed adapter and owner-only service credential; neither request nor token should cross to untrusted Repo or public owner browser routes. **Do not expose the token to the machine ingress or browser routes even though all these components live in one trusted Fortis container.** Owner-only provisioning and the single-container secret resolver/typed adapter, route authorization, secure network ingress and source-hardening remain FUTURE integration work; **no Approvals→Executor IPC is required**.

## 4. Decision and execution contract

| Trusted policy | Core state path | External effect |
| --- | --- | --- |
| `DENY` (or unknown operation/actor/target) | no request may be dispatched | none |
| `ALLOW` | `APPROVED → DISPATCHED → EXECUTED/STALE/UNCERTAIN` | authorized typed adapter, *same executor route* as ASK |
| `ASK` | `PENDING → owner WebAuthn/session proof → APPROVED → DISPATCHED → ...` | **same executor route** only after exact owner approval |
| `ASK` + `Reject` | `PENDING → REJECTED` | none |
| `UNCERTAIN` / already `DISPATCHED` | no automatic repeat | manual read-only reconciliation; never blindly resend |

At the trusted executor boundary, enforce exact request ID, fingerprint, policy version, actor/scope, dispatch state and single-use execution authority. Sonar mutation `accept_issue` must remain `ASK` irrespective of broader permissions held by the external token. These controls are not proven against an actual remote worker by this stage-1 contract; the fake one-shot worker lab provides only partial synthetic evidence. WebAuthn PIN is never handed to the Repo client or this contract.

## 5. Stage-1 negative tests and acceptance

`tests/test_repo_action_contract.py` includes **12 tests** covering:

- `ALLOW` immediate and `ASK` delayed execution through the existing shared `Core.execute`, and `DENY` refusing a write.
- Real virtual-WebAuthn owner decision on offline synthetic requests; Sonar READ/ASK and owner Reject with zero fake POST.
- Fixed Sonar typed intent, automatic trusted issue digest and mandatory ASK; no caller-supplied `transition`, URL, method or token.
- Unknown/excess caller fields and malformed nested params, bad UUID/field types fail before any Sonar read.
- Source grant authentication and per-actor operation separation, including denial of client-controlled `actor/approved/policy`.
- Public status/submit output limited to ID and state, actor-scoped status, duplicate ID cannot change a stored request.
- No listener/real transport added to the current G4 Docker image or to the contract module.

**Test result (2026-10-31): 193/193 Python PASS, 3/3 JavaScript UI PASS, documentation audit PASS.** These prove only the controlled offline composition, not the production network/IPC boundary. The running owner G2/G4 have not been updated.

## Stage 2 implementation checkpoint — test-only authenticated HTTP ingress

The separate, narrow [`repo_ingress.py`](../repo_ingress.py) now exposes
**only** `POST /v1/actions` and actor-owned `GET /v1/requests/<uuid>` through
WSGI, wrapping this exact `RepoIntentBroker`. A restricted ingress grant
(not SonarCloud token) is mandatory, non-HTTPS requests are denied by default,
unknown owner/admin/executor/proxy routes are not mounted, and caller
responses remain `{requestId,state}`. Invalid headers, forged Origin/cookies,
unknown fields, duplicate JSON keys, invalid length/UTF-8 and oversized
bodies are denied. It includes a **per-process test-only** authenticated
actor rate limiter; production must put a persistent/perimeter limiter and
credential lifecycle outside the process. In
[`test_repo_ingress.py`](../tests/test_repo_ingress.py) one actual HTTP
round-trip is executed to a **temporary `127.0.0.1` port in the Fortis Repo
Linux environment** with a fake synthetic grant, then the socket is closed.
**There is no deployed Repo→Windows connection and no TLS credentials.**
The full updated regression suite has **204/204 Python tests** PASS, and
3/3 UI tests PASS. The exact threat model and further requirements are in
[`FORTIS-REPO-INGRESS-GATE-V1.md`](FORTIS-REPO-INGRESS-GATE-V1.md).

## 6. Next implementation step and release gates (NOT completed)

1. **SOURCE/LOOPBACK LAB COMPLETE, NOT DEPLOYED:** a restrictive Repo→Approvals WSGI ingress with exact routes, separate synthetic ingress grant, host/scheme checks, schema/size limits and in-memory actor limiter. **Still needed:** trusted production TLS/identity provisioning, network allowlist, externally enforced rate limits and actual owner-controlled Repo→Windows connectivity.
2. **Same-container trusted typed execution:** secure owner-only private token store, server-side credential selection, scoped current-state GET/snapshot, one-use dispatch and GET readback. No arbitrary token-bearing proxy and no second executor container/IPC. Machine and owner HTTP routes must not expose token bytes or allow bypass of trusted policy.
3. One shared trusted durable Core queue/history, one owner WebAuthn identity/origin, no automatic G2/G4 SQLite or passkey merge.
4. Real Sonar READ-only acceptance in an isolated owner-controlled new build, still blocking Approve/POST; separate owner sign-off for any real credential mount.
5. Production WRITE threat review and explicit permission for one nominated disposable Issue. Sonar GET→POST has no atomic server CAS; preserve `UNCERTAIN` without blind retry and disclose broad-token compromise blast radius.

**Decision at this checkpoint:** **STEPS 1 AND 2 COMPLETE AS SOURCE / OFFLINE LOOPBACK TESTS; live integration NOT STARTED.** Current G2 (`18990`) and G4 (`18991`) must not be restarted, deleted, merged or stopped as a consequence of this record. No git commit is requested by this review.
