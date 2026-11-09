# Fortis Secure Gateway — полная матрица приёмки по ситуациям

**Версия:** 2026-11-03. Сохраняет 66 базовых acceptance cases и добавляет 8 критериев P1 pilot overlay. **СТАТУС: P2 image/audit/deployment PASS (owner-reported); GO-1/GO-2/GO-3 owner-reported PASS; GO-4/live acceptance OPEN.**

**Release status:** **OPEN** — source/offline checks do not close the unified live acceptance. P1 начинается с одного AI actor; multi-agent acceptance остаётся отдельным будущим gate.

**CURRENT RECONCILIATION (2026-11-03):** GO-1 trusted provisioning and GO-2 P1 R7 deployment/owner enrollment are **OWNER-REPORTED WINDOWS PASS**. GO-3 source/Guard release, read-only pre-cutover and current Repo inspect are **OWNER-REPORTED PASS**; current Repo has `fortis-r7-client` at `/run/fortis-client` with `RW=false`, preserved workspace mounts and expected networks. The stale script stopped before mutation due to an old Repo ID. P2 package, owner-reported Windows image build and installed-source/import audit are **PASS** for image `sha256:e751f6ca0cfe6ce290cf580de2f243071ee1f3e681baa8827c6cea41a16fa402`; P2 is **OWNER-REPORTED DEPLOYED/HEALTHY** on the exact audited image. Full pinned WebAuthn/HTTPS suite remains **BLOCKED** in the Linux Repo environment. GO-4/live R7 → Sonar E2E remains **OPEN / NOT STARTED**. Later dated evidence and the main plan supersede stale earlier rows below; historical rows remain for provenance.

**Нормативный источник:** [основной план Fortis](../../docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md), §0–1, §5–10, §12. Эта матрица — проверяемые **test cases/acceptance evidence**, а не новое решение о разделении контейнеров или изменении RDG-правил. Подробности Sonar E2E: [отдельная приёмка Sonar](REPO-SONAR-APPROVALS-E2E-ACCEPTANCE-20261101.md). Не заменять прежние нормы этой таблицей; при противоречии применять основной план.

## 0. Единая целевая схема и трактовка статусов

```text
Авторизованный ИИ / агент
         │
         ▼
    Fortis Repo (недоверенная среда)
         │  typed request, machine caller identity; БЕЗ service tokens
         ▼
┌──── ОДИН owner-controlled Fortis Docker на Windows Fortis_M ────┐
│ отдельный authenticated machine ingress                          │
│   → trusted scope / policy по actor+service+operation+target+params│
│   → DENY: STOP                                                    │
│   → ALLOW: typed adapter (при необходимости private service token)│
│   → ASK: durable frozen PENDING → owner-only Approvals/WebAuthn    │
│                      → Reject: STOP / Approve: тот же executor     │
│   → preflight → один dispatch → readback/receipt/audit/UNCERTAIN   │
└───────────────────┬──────────────────────────────────────────────┘
                    ▼
           SonarCloud / GitHub / RDG / разрешённое приложение
                    │
                    ▼
             ограниченный result / собственный request status → ИИ
```

**Ключевые определения.**
- *Сервисная авторизация* = пароль/API key/PAT/credential, принадлежащий только доверенному Fortis, применяемый им к разрешённому upstream API. Не путать с *machine client identity* для вызова самого Fortis: клиент Fortis аутентифицируется в любом случае при обращении к защищённому шлюзу.
- *ASK* = владелец одобряет **точную операцию**, а не передачу токена ИИ. Токен можно использовать до ASK только для разрешённого безопасного GET/preflight/preview; изменяющий вызов — лишь после подтверждения.
- *«Любой ИИ»* = любой поддерживаемый клиент с выданной машинной идентичностью и **разрешениями конкретного actor** через Fortis Repo. Это НЕ анонимный доступ, не автоматическая выдача токенов и не утверждение, что каждый внешний plugin имеет нужный инструмент.
- *Без токена и без ASK* — Fortis **можно** использовать, но прямое безопасное действие **не обязано** проходить через него. Любое действие, требующее токен **или** ASK, должно быть защищено и не иметь работающего обходного writer.
- **Не общий интернет-прокси:** Fortis выполняет только заранее зарегистрированные service/operation с фиксированными адаптерами/адресами/схемами. Никаких произвольных URL, curl, shell, HTTP headers, method или owner/approval flags от ИИ.
- GitHub-hosted Actions/SonarScanner — отдельная CI-среда, а не AI→upstream прямое обращение; их изоляция/временные права проверяются отдельно.

**Обозначения фактического статуса:** `WIN-A4` — проверено с Windows A3 **только synthetic** (со слов владельца); `G4-REAL` — отдельный G4 делал настоящие Sonar GET/ASK/Reject (со слов владельца); `IMAGE-R5` — образ на Windows собран, SHA/import/pip проверены, не установлен сервис; `OFFLINE` — тесты Python/WSGI/TLS на фейковых API, без реального Fortis Repo→Sonar; `SOURCE` — код/контракт есть, real E2E нет; `OPEN` — целевая проверка не выполнена; `BLOCKED` — намеренно запрещено до отдельного owner GO. **Ни один частный PASS не эквивалентен LIVE UNIFIED PASS.** Для полного приёма каждой строки требовать реальный согласованный E2E с отрицательным тестом и отдельным evidence.

## 1. Матрица четырёх независимых комбинаций (обязательный функционал)

| ID | Нужен сервисный секрет? | Нужен owner ASK? | Целевое поведение / критерий PASS | Что уже доказано | Осталось до LIVE PASS |
|---|---|---|---|---|---|
| F-01 | Нет | Нет | При trusted ALLOW операция исполняется без Pending; обычное безопасное действие может идти прямо через Repo. Типизированный Fortis-адаптер, если использован, выдаёт status/readback. | WIN-A4 synthetic `set_free` | Не ломать существующие прямые безопасные операции; будущий RDG FREE — отдельная приёмка. |
| F-02 | Да | Нет | Fortis после auth/policy ALLOW сам подставляет *сервисный* секрет, делает только разрешённый upstream READ/action; получает ответ, редактирует поля; **никакого Pending**, токен не покидает Fortis. | G4-REAL Sonar GET отдельно; IMAGE-R5; OFFLINE R6 GET | Unified Fortis/Repo→реальный Sonar GET; проверка владельцем secret custody. |
| F-03 | Нет | Да | Fortis сохраняет неизменяемый `PENDING` **без service token**, owner Approve приводит к исполнению того же запроса; Reject → 0 write. | WIN-A4 synthetic `set_ask` и WebAuthn | P1 first proves Sonar ASK/Reject; RDG ASK — следующий этап G3 после P1, с собственным предметным writer/CAS и bypass tests. |
| F-04 | Да | Да | Fortis делает разрешённый read-only snapshot/preview, `PENDING`, owner exact Approve; **лишь затем** с внутренним service token выполняет одну разрешённую мутацию и проверяет readback. Reject → 0 write. | OFFLINE R6 Sonar PENDING/Reject; G4-REAL отдельный ASK/Reject | Unified Sonar ASK Windows + одобренный real WRITE gate, отдельная disposable Issue и owner GO. |

**Независимая политика:** даже при наличии секрета trusted policy может вернуть `ASK` или `DENY` вместо `ALLOW`; ИИ не выбирает политику. `DENY` и отсутствие grant — не пятая комбинация, а блокировка в **любой** строке F-01..F-04.

## 2. Сквозная авторизация и политика: позитивные и отрицательные тесты

| ID | Сценарий | Критерий PASS / отрицательная проверка | Сейчас |
|---|---|---|---|
| A-01 | Два и более различных ИИ через один Fortis Repo | Все видят один и тот же **каталог typed tools**, но каждый имеет собственную проверяемую actor-identity/scope, а не общий owner/admin token; лог/audit различает инициаторов. | OPEN / DEFERRED AFTER P1 + RDG; multi-agent не является условием первого пилота. |
| A-02 | Верный grant, разрешённая операция и объект | Authenticated ingress, policy `ALLOW` → один typed READ/dispatch. | WIN-A4 synthetic; OFFLINE R6. |
| A-03 | Нет grant / неверный / отозванный / чужой actor | 401/403 **до** service GET, Preview, Pending или исполнения; нет утечек. | WIN-A4 synthetic; OFFLINE R6; live Sonar OPEN. |
| A-04 | Actor имеет READ, но нет mutation grant | READ разрешён, `POST /v1/actions` denied, owner queue не меняется. | OFFLINE/source; Windows OPEN. |
| A-05 | Actor имеет одну организацию/проект, просит другой | DENY до Issues/Quality Gate/POST; никакого leakage, нельзя выбрать org/region в JSON. | OFFLINE R2/R6; live OPEN. |
| A-06 | Policy = DENY (даже если upstream token мог бы исполнить) | Нет write, нет Pending; ответ bounded/redacted, audit отказа по принятой политике. | WIN-A4 synthetic, OFFLINE; live сервис OPEN. |
| A-07 | Policy = ASK без owner proof | Только PENDING; до owner approval никаких POST или других side effects. | WIN-A4 synthetic; OFFLINE R6 Sonar. |
| A-08 | Входящие `approved=true`, `policy=ALLOW`, `actor=owner`, URL/method/headers/token/shell | Strict schema DENY; клиент не подменяет политику, пользователя, маршрут, сервисный токен и preview hash. | OFFLINE; live bypass review OPEN. |
| A-09 | Неизвестный service/operation и плохие параметры | Default deny, без fallback к generic HTTP, raw RPC или shell. | SOURCE/OFFLINE; будущие service grants OPEN. |
| A-10 | Повтор того же requestId и тех же bytes | Idempotent status; вторая мутация не выполняется. Изменённый payload с тем же ID → Conflict. | WIN-A4 synthetic; OFFLINE R6. |
| A-11 | Чтение статуса | Только собственный requestId: `PENDING/REJECTED/EXECUTED/STALE/UNCERTAIN`; чужая заявка не раскрывается; отсутствие service credential у ИИ. | WIN-A4 synthetic; OFFLINE R6; реальные Sonar statuses OPEN. |
| A-12 | Условия changed / revoked grant / policy changed до фактического исполнения | Server повторно проверяет доверенную версию, policy, entitlement и service precondition; старое Approve не даёт полномочия на новое состояние. | Core/unit SOURCE; runtime acceptance OPEN. |
| A-13 | Сетевые ошибки/лимиты/перегрузка | Таймаут, oversized ответ, rate limit, недоступный upstream дают ограниченный отказ/UNCERTAIN, без raw headers/секретов и без повторной записи. | OFFLINE частично; real chaos OPEN. |
| A-14 | Изоляция owner UI от machine клиента | Из Repo недоступны owner/admin/issue-token/policy settings, нет browser cookie/CSRF/SameSite bypass, разные namespaces/security controls. | WIN-A4 synthetic; OFFLINE R6; unified production OPEN. |

## 3. Approval lifecycle, UX, аутентификация владельца

| ID | Сценарий | Критерий PASS / отрицательная проверка | Сейчас |
|---|---|---|---|
| P-01 | ASK создаётся, когда вкладка Approvals закрыта | Durable `PENDING`, сервис продолжает принимать заявки и после повторного открытия UI показывает их. | G2/A4 WIN synthetic частично; unified/live OPEN. |
| P-02 | UI Pending/History | Качество карточки: проверенные actor/service/object/reason/before/after, статус и время; auto-poll, индикатор новых заявок. | WIN owner UI + JS tests; live Sonar OPEN. |
| P-03 | Обычный ASK в активной owner WebAuthn session | Явный Approve/Reject с origin/CSRF/exact fingerprint, без принудительного PIN на каждую обычную заявку; strong proof при risk-policy. | WIN synthetic + SOURCE; production UX OPEN. |
| P-04 | Опасная/strong операция | Owner WebAuthn UV/сигнатура на точные requestId, fingerprint, decision, а не на абстрактный action; AI не вправе подписать за владельца. | OFFLINE R6 strong Reject; Windows Sonar OPEN. |
| P-05 | Owner Reject | `PENDING→REJECTED`, нет dispatch/upstream mutation, status/readback отражают отказ. | WIN-A4 synthetic; G4-REAL отдельный Reject; OFFLINE R6 unified. |
| P-06 | Owner Approve | `PENDING→APPROVED→DISPATCHED→EXECUTED` **тем же executor**, только после повторного preflight; ИИ не присылает действие заново. | WIN-A4 synthetic; real Sonar WRITE BLOCKED. |
| P-07 | Повторная подпись/смена decision/подмена preview | Reject replay, неправильный owner, истёкшая session, CSRF/origin и другой target/digest; нет исполнения. | SOURCE/WIN synthetic; live unified OPEN. |
| P-08 | Изменившийся Issue/граф перед Approve | `STALE`, нет записи; fresh preview/новый запрос нужны, старое подтверждение не переносится. | WIN-A4 synthetic stale; Sonar/RDG real OPEN. |
| P-09 | Crash/restart/браузерный reboot | SQLite сохраняет PENDING/History/receipts и WebAuthn credentials; временные sessions/challenges инвалидируются; UI может снова залогиниться. | WIN G2/A4 synthetic + OFFLINE R5; unified cutover/Windows reboot OPEN. |
| P-10 | Нотификация о новой заявке | UI polling счётчика и Notification после browser permission даже на фоновой вкладке; при полностью закрытом браузере push не обещан в V1. | JS SOURCE; real Windows UX acceptance OPEN. |
| P-11 | Переход из Approvals в RDG | Verified resource descriptor, существующая вкладка RDG/точный объект, безопасное возвращение; навигация **не является** Approve или write. | OPEN — G3 Navigation Bridge. |
| P-12 | Завершение с timeout/UNCERTAIN | ИИ видит финальный статус/аудит, reconciliation без слепого повторного POST; expiration/revocation отражены в UI. | Core SOURCE/synthetic; real service OPEN. |

## 4. SonarCloud — READ, Issue ASK и подтверждение **конкретных проверок**

| ID | Сценарий | Критерий PASS / отрицательная проверка | Сейчас |
|---|---|---|---|
| S-01 | READ список проектов одной/нескольких разрешённых организаций | GET-only, все страницы/область явно заданы; чужие org и неполный список не выдаются за «все проекты». | G4-REAL отдельно; R2/R6 OFFLINE; unified OPEN. |
| S-02 | READ Issues | `list_issues`, точное количество/пагинация/coverage, без скрытых 10k truncation, без сырого upstream и token. | R2/R6 OFFLINE; unified real OPEN. |
| S-03 | READ отдельной Issue | Проверенный project membership, правильный issue key, severity/message/file/line в ограниченной проекции. | OFFLINE; G4-REAL отдельный issue GET; unified OPEN. |
| S-04 | READ Quality Gate проекта | Точный project/org, статус и условия; явно `CURRENT_DEFAULT_BRANCH`, пока нет verified PR binding. | OFFLINE; unified real OPEN. |
| S-05 | Проверки конкретного PR/commit | В отчёте есть GitHub PR/head SHA, checkout SHA, runId/attempt/conclusions, Sonar branch/PR/CE task/analysis ID, время, paths/coverage, проверка **одного и того же SHA**. Любой mismatch/stale/skipped → `UNKNOWN/BLOCK`, не PASS. | OPEN — D1/D2, **get_quality_gate ≠ этот отчёт**. |
| S-06 | Создание Sonar `accept_issue` proposal через Fortis Repo | ИИ передаёт строгий typed envelope: `service=sonarcloud`, `operation=accept_issue`, `target=issueKey`, `params={projectKey}`, `reason` и UUID; Fortis сам делает trusted current GET/digest и сохраняет owner `PENDING`; ИИ получает requestId. | G4-REAL отдельно; R6 OFFLINE unified; real unified OPEN. |
| S-07 | Просмотр Sonar ASK и Reject | Owner видит exact Issue/preview, Reject→REJECTED, readback без mutation. | G4-REAL отдельно; R6 OFFLINE unified; real unified OPEN. |
| S-08 | Approve разрешённой Sonar Issue | Только отдельный owner GO на disposable Issue: strong proof, revalidate status/digest/available transition, **один POST**, readback/receipt, `UNCERTAIN` без blind retry. | **OPEN / NOT EXECUTED:** P2 source permits the exact typed transition, but no P2 deployment or live Sonar WRITE has occurred. |
| S-09 | READ-only token и запрет произвольных Sonar mutations | Никаких доп. action `resolve/falsepositive/close`, raw POST/URL, personal/project escalation; 0 upstream write при отказах. | R5/R6 OFFLINE, G4 safety; production OPEN. |
| S-10 | Sonar Cloud region/org и секреты | Регион/host pinned владельцем; отдельный token не находится в Repo, chat, logs, браузере; независимая проверка прав и secret rotation. | IMAGE-R5/private file checks SOURCE; trusted deployment OPEN. |

## 4A. P1 — Single AI SonarCloud Pilot (приоритет 2026-11-02)

**Область первого ручного теста:** один авторизованный AI actor, один выбранный владельцем GitHub repository, одна разрешённая SonarCloud organization/project и один Fortis Core/Owner Approvals. Второй AI actor, общий multi-agent routing и полный GitHub PR/SHA attestation не требуются для P1. Эти восемь критериев — pilot overlay поверх 66 базовых cases, они не заменяют M0–M8.

| ID | Сценарий | Критерий PASS / отрицательная проверка | Сейчас |
|---|---|---|---|
| P1-01 | Выбранный GitHub/SonarCloud target | Владелец выбирает один репозиторий, существующий SonarCloud project/org и действующий GitHub Actions workflow; region/repo/ref/project allowlist фиксируются вне AI JSON. | **TARGET CHOSEN / SOURCE VERIFIED:** `AlexPastukhh/obs-planning-docs`, `main`, `.github/workflows/sonarqube.yml` (workflow_dispatch enabled), `sonar.organization=alexpastukhh`, `sonar.projectKey=AlexPastukhh_obs-planning-docs`. В файлах GitHub подтверждено, live R7 scope ещё не provisioned. Sonar scan ограничен Planning Helper JavaScript, не всем Markdown. |
| P1-02 | Запуск Sonar analysis одним ИИ | AI запускает только заранее разрешённый workflow через bounded typed dispatch, привязанный к exact repo/workflow/ref и allowlisted inputs; первый dispatch по умолчанию ASK с frozen target, Reject не запускает workflow; последующий ALLOW возможен только по owner policy. Никакого arbitrary workflow/YAML edit/shell/admin PAT. Owner manual run может дать baseline для READ smoke, но не закрывает AI-trigger PASS. | OPEN — bounded GitHub workflow-dispatch operation и owner decision flow не реализованы/не приняты. |
| P1-03 | Реальный Sonar READ через один Fortis | Один actor из Fortis Repo через существующий process tool/фиксированный CLI или HTTPS вызывает четыре Sonar READ через Gateway; **новые MCP tools не требуются**. На стороне R7 destination/service + operation + actor + **exact owner-pinned project key** задают `ALLOW/ASK/DENY`; unknown destination/route/operation/project DENY до чужого Sonar read, token только в private Fortis. | SOURCE/OFFLINE new exact-project deny PASS (15/15 adapter + 19/19 R7 HTTPS/Owner Reject); live Repo HTTPS→Windows R7→Sonar OPEN. Old P1 image DOES NOT include scoped hardening; new scoped image-only Windows build **OWNER-REPORTED PASS** (`sha256:23667619…a18ce4`); exact-ID offline image audit **OWNER-REPORTED PASS** (metadata, 19 SHA, imports, no POST, cleanup). |
| P1-04 | Подробный отчёт по анализу | Отчёт содержит Issue count, severity/type/status, rule, message, component/file/line/updateDate, Quality Gate и conditions, paging/total/hasMore/coverage, timestamp и явные partial/10k caps. `CURRENT_DEFAULT_BRANCH` не выдаётся за PR/SHA attestation. | Projection SOURCE/OFFLINE; реальный report OPEN. |
| P1-05 | AI предлагает точное действие | `sonar.propose_accept_issue` создаёт stable requestId; Fortis сам делает current GET/digest и замораживает точный project/Issue/operation/preview; AI не задаёт URL/method/token/policy/owner proof. | SOURCE/OFFLINE proposal contract PASS; live PENDING OPEN. |
| P1-06 | Owner Reject без изменения Sonar | Owner видит exact PENDING и отклоняет; `approvals.request_status` возвращает REJECTED; independent remote GET подтверждает прежнее Issue state; upstream Sonar POST = 0. | OFFLINE R6/R7 PASS; live owner UI/remote readback OPEN. Это первый реальный ASK acceptance. |
| P1-07 | Отдельный настоящий Approve одной мутации | Только после отдельного exact owner GO: одна disposable Issue, одна поддерживаемая transition, strong WebAuthn, повторный preflight, ровно один POST, receipt/readback; timeout → UNCERTAIN без blind retry. | **SOURCE/PACKAGE/IMAGE-AUDIT PASS; LIVE OPEN:** P2 removed the candidate-only `NoWriteTransport`/`blocked_approvals` stops. Текущий `accept_issue` = transition `accept`, не универсальное close/resolve. |
| P1-08 | Минимальная live trust boundary | Новый P2 image соответствует текущему source; TLS1.3 identity, server/client grants, private Sonar token custody, five provisioned R7 volumes and owner WebAuthn state are preserved. Repo client получает только client-only RO material after the separate GO-3 recreate; no Sonar token/private key/state/socket. | **GO-1 DONE / GO-2 DONE — OWNER-REPORTED WINDOWS PASS.** P2 image/audit PASS for `sha256:e751f6ca0cfe6ce290cf580de2f243071ee1f3e681baa8827c6cea41a16fa402`. GO-3 client mount/recreate **NOT EXECUTED / NOT AUTHORIZED**; P2 deployment and live E2E remain OPEN. |

## 5. RDG, GitHub, CI и доверенная доставка кода

| ID | Сценарий | Критерий PASS / отрицательная проверка | Сейчас |
|---|---|---|---|
| D-01 | RDG обычная операция по FREE-блоку | Проходит старый штатный `graph.write/apply`, без новых ASK-подтверждений по умолчанию; существующие rights/locks/CAS сохраняются. | Действующий RDG отдельно; Fortis G3 OPEN. |
| D-02 | RDG операция затрагивает ASK-блок | Immutable `PENDING`, отсутствие write до owner Approve, затем тот же штатный RDG writer и повторная CAS-проверка; прямой RDG API/Agent/Gateway не обходит ASK. | OPEN — G3. |
| D-03 | RDG FREE→ASK / ASK→FREE | FREE→ASK разрешён по действующему договору; ASK→FREE для ИИ только с owner approval; owner UI route защищён. **Нет** третьего block-state DENY. | OPEN — G3. |
| D-04 | RDG semantic effects и layout | ASK на edit/link/remove/membership затрагиваемого ASK-блока; обычный layout/view, размещение в Plan и side-effect `review_required` не превращаются в ASK сами по себе. | OPEN — G3. |
| D-05 | RDG предметные constraints | Текущие grants, `policy`, `locks`, inputBinding/CAS/journal не заменяются Fortis approval; stale state blocked. | RDG domain guards есть; G3 integration OPEN. |
| D-06 | GitHub операции из ИИ, которым нужна авторизация/ASK | Branch/PR/comments/admin scopes через явно утверждённый typed adapter или **явное owner exception**; никакого широкого owner/admin connector как обход. | OPEN — D1, privilege review. |
| D-07 | Реальные CI/Sonar проверки PR | GitHub Actions required tests, scanner, security и Sonar analysis привязаны к действительному SHA и diff coverage, failures/skips не маскируются. | OPEN — D1/D2. |
| D-08 | Merge защищённой ветки | Owner review/required checks/ruleset без AI bypass; зелёный Sonar сам не даёт merge, import или run. | OPEN — D1/D2. |
| D-09 | Windows Importer | Только exact reviewed final merged SHA, trusted checkout, signed manifest/checks/AV/quarantine и нормализованный allowlist; иначе FAIL. | OPEN — D3. |
| D-10 | IMPORT_APPROVAL | После полной проверки импорт может быть `ALLOW` или `ASK` по политике владельца; fetch ≠ import ≠ execute; отказ не затрагивает running. | OPEN — D3. |
| D-11 | RUN_APPROVAL | Перед build/install/run недоверенного кода на Windows **обязателен** отдельный owner authorization; AV/CI/Sonar PASS недостаточны. | OPEN — D3. |
| D-12 | Запуск/rollback и миграция | Защитить Windows RDG/Fortis state/volumes, health/readback и возможность отката; legacy ZIP `Update-RDG.ps1 -Watch` выключать лишь после проверенного нового пути. | OPEN — D4. |
| D-13 | Обновление самого Fortis | Только через тот же owner-controlled secure development pipeline и supply-chain; AI не может сам заменить trusted code/image/policy. | OPEN — D4. |

## 6. Защита шлюза, эксплуатация и защита от обхода

| ID | Сценарий | Критерий PASS / отрицательная проверка | Сейчас |
|---|---|---|---|
| O-01 | Один Fortis, один Core, одна owner queue | Не три параллельные production A3/G4/R5; оба режима READ+ASK видны в **одном** Owner Pending/History. Нет обязательного второго executor/IPC. | R6 OFFLINE; Windows unified OPEN. |
| O-02 | Trusted machine transport | TLS1.3 hostname/SAN/cert chain pinned, scoped machine identity, localhost-only publishing, wrong host/cert/grant denied. | WIN-A4 synthetic; R6 OFFLINE; Sonar trusted runtime OPEN. |
| O-03 | Отсутствие секретов и Docker-привилегий в Repo | Нет upstream Sonar token, GitHub/RDG credentials, owner DB/private key, server grant volume или Docker socket в `fortis-repo-test`; P1 допускает только ограниченный Fortis machine grant-copy + public CA cert в отдельном RO client volume. Этот grant доступен процессам UID 1000 в общем Repo container — остаточный риск только для single-actor pilot, не multi-agent isolation. | Owner-reported A3 Windows mount/ACL PASS; P1 client volume NOT CREATED / mount NOT AUTHORIZED; full connector/scope review OPEN. |
| O-04 | Допустимость привилегированного сервисного токена | Fortis может хранить сильный upstream credential по owner решению, но AI ограничен typed operations; компрометация Fortis/host остаётся существенным риском, его нельзя назвать устранённым. | Требование закреплено; production threat review OPEN. |
| O-05 | Выдача/ротация/отзыв service token и machine grant | Owner-only управление вне AI; старый client credential после revoke DENIED, новый PASS, state/credential isolation, нет записи в логи. | R5 lifecycle OFFLINE; Windows trusted gate OPEN. |
| O-06 | Ротация TLS и backup | Новый cert+key/SAN/cert pin, после R5-only restart старый pin denied; SQLite/owner enrollment сохраняются. Для действующего A3 собственная процедура. | R5 lifecycle OFFLINE; Windows owner acceptance OPEN. |
| O-07 | Долговременная работа | После перезапуска Docker/Windows Pending/History/credentials не теряются, browser session повторно аутентифицируется; Backup/restore без повреждения. | G2 WIN partial + OFFLINE; reboot/full restore OPEN. |
| O-08 | Логи, ошибки, наблюдаемость | RequestId/state/typed operation/decision/result и audit без token, private key, Authorization, owner proof, raw upstream body; audit-replay read-only. | SOURCE/часть WIN synthetic; real secrets OPEN. |
| O-09 | Устойчивость к prompt injection / untrusted data | Sonar Issue message, GitHub PR text, RDG content не становятся политикой, URI/method, authorizations или owner approval. | Строгий input SOURCE; cross-tool adversarial acceptance OPEN. |
| O-10 | Обход Fortis через Repo/GitHub/RDG/host | AI не получает параллельный privileged writer или admin connector; direct write к защищённому ресурсу блокируется **в авторитетной точке** сервиса/ruleset, даже если Fortis Approvals недоступен. | **OPEN — ключевой production blocker**. |
| O-11 | Нет доступа к доверенному Windows host | Repo не может управлять compose/run/stop/volume/daemon или secret provisioning. Защищённый Windows clone/Runner не является AI-shell. | WIN-A4 owner audit partial, future deployments OPEN. |
| O-12 | Не ломать существующие Repo1/Repo2 Guards и A3 | Перед воздействующими live Docker updates/launcher restart — Guard Preview обеих сторон и owner-safe cutover; не останавливать последний Fortis Repo access; A3 TLS истекает 2026-11-07 23:29:17 UTC. | **Repo1 + Repo2 read-only Guard Preview PASS.** Repo2 owner output: exact source/launcher pin PASS; `Mode=Preview`, `Preflight=PASS`, `ConfigState=Pinned`, `ContainerIdMatched=True`, `LinuxUid=1000`, `DirectModuleHashVerified=True`, `NoWindowsProfileEdits=True`. No Repo2 restart/config mutation. Any live cutover/update still requires separate owner GO and must preserve Repo access/A3. |
| O-13 | Никакой «успешной проверки» без доказательства | Разделять SOURCE/OFFLINE/OWNER-REPORTED Windows/live Sonar; фиксировать image ID, timestamp, actor/target scope, requestId, checked remote data, negative test, без передачи secret. | Правило введено, unified E2E OPEN. |

## 7. Итоговые milestone gates с обязательными доказательствами

| Gate | Что означает закрытие | Сегодня |
|---|---|---|
| M0 — Core механика | Synthetic `ALLOW/ASK/DENY`, WebAuthn approve/reject, status, persistence, изоляция Repo→A3 TLS на Windows. | **WIN-A4 synthetic PASS** (owner-reported), без Sonar. |
| M1 — один Fortis READ+ASK source | Один Core/owner UI/TLS machine, все 4 Sonar READ и Sonar `accept_issue` proposal, strong reject, 0 POST. | **OFFLINE R6 + R7 SOURCE PASS** по ранее зафиксированной R7 suite 17/17; Repo typed-client 12/12 PASS. Новый P1 package exact source manifest/import PASS; новые targeted package/client/image-source suites 18/18 PASS. Windows R7 v2 build/import evidence относится только к старым байтам; unified live server OPEN. |
| M2 — рабочий AI→Repo→Gateway HTTP маршрут (P1: один actor) | Один авторизованный ИИ → Fortis Repo (существующий process tool, фиксированный CLI/HTTPS) → **один** R7 Gateway-прокси; server-side destination/operation ALLOW/ASK/DENY, четыре READ, ASK proposal, scoped status и unauthorized denies. | **SOURCE/OFFLINE PASS, LIVE OPEN — P1 FIRST:** клиент реализован, но ещё нет live R7 TLS/machine grant/private token/mounts. **Отдельная регистрация Sonar MCP tools не prerequisite.** Два actor grants в offline suite не означают принятый multi-agent. Live MCP bridge не менялся. |
| M3 — P1-A live Sonar analysis + READ/report | Один AI actor запускает разрешённый workflow и получает через Fortis настоящий SonarCloud project/issues/QG, без утечки токена/POST; подробный отчёт помечает coverage и default-branch scope. | **OPEN — P1-A FIRST LIVE GATE.** GO-1 trusted provisioning and GO-2 P1 R7 runtime/enrollment are owner-reported PASS; P2 image/audit is also owner-reported PASS. GO-3 Repo recreate/client RO mount remains NOT EXECUTED / NOT AUTHORIZED. After the pinned WebAuthn/HTTPS suite and separate owner GO, deploy the P2 image, complete the approved GO-3 cutover, then perform live Repo→R7 HTTPS/Sonar GET. AI-triggered bounded workflow-dispatch remains separately unimplemented (P1-02). |
| M4 — P1-B live Sonar ASK/Reject without POST | Та же Fortis owner queue получает настоящий proposal; owner Reject, actor status `REJECTED`, remote Issue unchanged, 0 Sonar POST. | **OPEN — P1-B immediately after P1-A**; OFFLINE R6/R7 PASS не заменяет live owner/remote evidence. |
| M5 — P1-C opt-in Sonar WRITE | Отдельный явный owner GO на одну disposable Issue/точную transition; один approved POST, revalidate, receipt/readback, no blind retry. | **OPEN / NOT EXECUTED:** P2 source/package/image/audit pass; deployment, owner GO and live WRITE remain separate gates. |
| M6 — PR/commit checks truth | Полные GitHub + Sonar SHA/run/analysis/scanner/coverage/required-check evidence, UNKNOWN/BLOCK при несоответствии. | **OPEN — D1/D2 future stage**, не prerequisite для P1 default-branch report. |
| M7 — trusted deployment lifecycle | Минимальные P1 prerequisites: exact scoped image ID, TLS1.3 server identity, one machine grant with server/client copies, private Sonar token store, four preserved server volumes + separate client-only RO volume, no Repo Sonar token/private key/state/socket. Full image/base provenance, SBOM/CVE, backup/restore and complete grant rotation/revocation lifecycle. | P2 image build/audit and GO-1/GO-2 trusted runtime evidence are OWNER-REPORTED PASS. **Still OPEN:** pinned WebAuthn/HTTPS suite, separate P2 rollout GO, GO-3 Repo recreate/client RO mount, and live READ/ASK/Reject/Approve E2E. The five R7 volumes and owner state must be preserved; no reprovisioning. No MCP bridge/tool registry is required. Full grant lifecycle and base digest/provenance/SBOM/CVE remain future/final gates. A3 cert deadline 2026-11-07T23:29:17Z is a separate owner operation. |
| M8 — protected GitHub/RDG & release | RDG FREE/ASK без второго writer/обхода; GitHub least privilege; approved Windows IMPORT/RUN и rollback; Fortis self-update. | **OPEN — G3 follows P1; D1–D4 secure delivery and production release remain later gates**. |

**HISTORICAL UN-SCOPED R7 P1 SOURCE EVIDENCE (2026-11-02; superseded for OBS P1):** exact ZIP `fortis-r7-unified-source-review-p1-20261102.zip`, 150781 bytes, SHA256 `7755e84ecb2a4abf23c66d97707a81838cadc2424c2c24700a499aa3b9a1d0d5`; manifest SHA256 `eeac1cb7847fb8c99f949b878d69968c311556fc5a27c91851db459f5e1db3cb`; owner build script SHA256 `409a8062ea6ed8cc4378ac2e7e7e2b73f1572036a39679741a564b23cf04734f`; target tag `fortis-r7-unified-read-ask-candidate:review-p1-20261102-7755e84e`. Exact archive isolated import PASS; package/client/image-source targeted suites 18/18 PASS. This is **source/build preparation only**: Windows image-only build OWNER-REPORTED PASS, image ID `sha256:2c634df43b988d05a83a5479aaf1d51fbea863da9a4e602aae7ce938815e4b78`; isolated image import/installed 19-source SHA256/metadata/disposable cleanup now OWNER-REPORTED PASS. Service not deployed, no TLS/grant/token and no registered AI tools or Sonar request; four previously prepared R7 private volumes do exist (see dated 2026-11-02 owner metadata evidence), unattached to any container. This historical unscoped image is not the current OBS P1 candidate. Historical v2 image `sha256:2a047aaa6ab74a0b3e47e3a02b3ac663301f8363515f0cd32ed3ad1a562d1b73` remains owner-reported PASS only for its old source; three files (`core.py`, `owner_portal.py`, `r7_unified_candidate.py`) drift from v2. **M2** one-actor live tool path OPEN; **M3** P1-A live analysis/READ OPEN; **M4** P1-B live ASK/Reject OPEN; **M5** P1-C mutation BLOCKED until exact owner GO; **M6/M7/M8** OPEN/partial. Minimum TLS/machine identity/private token admission is required before P1 live; full base provenance/SBOM/CVE remains final. A3 TLS deadline 2026-11-07T23:29:17Z is separate. **Next: one-actor Fortis Repo typed-tool exposure and owner-selected GitHub/SonarCloud project; minimal TLS1.3/grant/private Sonar token provisioning only after separate owner GO. No Windows build/audit repeat, no deployment implied.** [Immutable handoff snapshot 2026-11-01](../../docs/handoffs/fortis-unified-gateway-20261101/HANDOFF.md); [Windows evidence journal](R7-UNIFIED-SONAR-READ-ASK-M2-SOURCE-GATE-20261101.md).

**Общий release-вердикт сегодня:** `FORTIS_UNIVERSAL_GATEWAY_PRODUCTION_ACCEPTANCE=OPEN`.
Не считать весь продукт принятым по локальным Python/UI регрессиям и частным PASS образа. Эти тесты доказывают корректность конкретного source/lab, но не текущий live Fortis Repo → R7 → SonarCloud E2E даже для одного actor; multi-agent/two-actor acceptance остаётся отдельным будущим gate.

**Формат каждого будущего acceptance evidence:** `Case ID; build/image/source digest; окружение (offline/Windows/live); actor scope (без секретов); target+operation; expected state; observed HTTP/status + owner UI/audit; remote readback если разрешён; негативный counterpart; timestamp; PASS/FAIL/OPEN; owner sign-off`. Нельзя помещать в evidence bearer, credential, WebAuthn secrets/private keys, Docker private volume content, либо owner DB.

## Дополнение 2026-11-01 — M2 typed-client hardening

| Case | Новое изменение | Evidence |
|---|---|---|
| M2 / client typed operations and response boundary | Four READ tools, stable-ID proposal, actor status GET; duplicate-key/non-finite/deep JSON rejection, bounded body and redacted errors | SOURCE/OFFLINE **PASS 12/12** in `test_repo_sonar_tools.py` |
| M2 / redirect boundary | No-redirect opener; HTTP 307 test verifies no follow and no Authorization reaches redirect target | SOURCE/OFFLINE **PASS** |
| M2 / status and method boundary | Read route accepts only HTTP 200; 202 is denied for READ; malformed state type denied without TypeError | SOURCE/OFFLINE **PASS** |
| M2 / upstream error redaction | HTTP 401 body and diagnostic Authorization header never appear in the caller-visible error | SOURCE/OFFLINE **PASS** |
| Supplemental / standalone Sonar preflight | Bounded organization/project sample, exact issue re-read, stale/mismatch denial, GET-only and no mutation | SOURCE/OFFLINE `test_sonar_preflight.py` **15/15 PASS**; standalone preflight, not unified R7 live evidence |

Эти изменения **не меняют** прежний R7 source/offline acceptance 17/17 и не расширяют
actor grants. Новый typed-client regression — отдельный **12/12 PASS**; это не live acceptance.
Решение 2026-11-02 переводит live one-actor M2/M3/M4 в первый P1 pilot; multi-agent A-01 остаётся deferred. Sonar POST remains zero/disabled до отдельного P1-C owner GO.

## Дополнение 2026-11-01 — G1/G2 strict-input and lifecycle regression

| Case | Изменение / проверяемая граница | Evidence |
|---|---|---|
| G1 Core serialization | UTF-8 canonical payload encoding; reject unpaired surrogates, over-deep objects and oversized serialized requests before persistence | SOURCE/OFFLINE `test_core.py` **28/28 PASS** |
| G1 typed client boundary | Strict JSON decoder rejects duplicate object names, non-finite numeric values and excessive nesting before Core; malformed input returns bounded 400 response | SOURCE/OFFLINE `test_gateway.py` **6/6 PASS** |
| G2 owner WSGI boundary | Strict JSON decoding, bounded ASCII Content-Length, truncated-body rejection; malformed bodies fail closed without decision | SOURCE/OFFLINE `test_owner_portal_input.py` **7/7 PASS**; fake verifier is test-only |
| G2 owner decision lifecycle | Exact request/fingerprint binding, stale preview after external version change, replay prevention, one-use proof, session/credential revocation and restart behavior | Isolated WebAuthn/FIDO2 venv `test_owner_portal.py` **18/18 PASS**; virtual authenticator is test-only, not Windows human-key acceptance |
| R7 unified functional regression | Existing single-Core/two-actor typed READ + ASK/owner Reject source/offline path remains functional after shared Core/OwnerPortal hardening | `test_r7_unified_candidate.py` **17/17 PASS**; no live Sonar/Windows activity |

**Artifact boundary:** these changes modify shared `core.py` and `owner_portal.py`, both present in the previously accepted R7 v2 image source allowlist. The pinned v2 ZIP, build script, image ID and Windows evidence remain historical and unchanged, but the v2 ZIP no longer represents the current checkout byte-for-byte. Its exact-source regression correctly reports drift. Do not rebuild or rerun v2; any future image containing these changes requires a separately versioned source package, manifest, build script and owner approval. This source/offline work does not close live M2/M3/M4 or change Sonar POST = 0 / NO-GO.
