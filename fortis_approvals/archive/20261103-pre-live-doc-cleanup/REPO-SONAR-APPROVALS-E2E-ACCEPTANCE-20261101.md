# Fortis Repo → SonarCloud READ → mutation ASK → Fortis Approvals

**Дата:** 2026-11-01. **Статус на дату документа: объединённая HTTPS/TLS 1.3 OFFLINE-цепочка PASS; реальный полный E2E OPEN.**

**CURRENT RECONCILIATION (2026-11-03):** This document remains a historical acceptance/design snapshot. GO-1 and GO-2 are owner-reported PASS; GO-3 Repo cutover is not executed/authorized; P2 package/image/audit are owner-reported PASS for image `sha256:e751f6ca0cfe6ce290cf580de2f243071ee1f3e681baa8827c6cea41a16fa402`; P2 is not deployed; live unified E2E remains OPEN. The exact current sequence is defined by the main plan and P2 source review.

**Актуальность на 2026-11-02:** это исторический acceptance/design snapshot. Его предположение о необходимости двух AI-клиентов или отдельной регистрации `sonar.*` MCP tools superseded решением P1: сначала один actor и один project через существующий Fortis Repo process tool/CLI `repo_sonar_tools.py`; новый MCP bridge/tool registry не нужен. Текущая очередь и минимальный live путь — [основной план §12–14](../../docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md) и [R7 P1 provisioning runbook](R7-P1-MINIMAL-TRUSTED-PROVISIONING-20261102.md). Реальный Repo→R7→Sonar E2E всё ещё OPEN.

Этот документ фиксирует исходные достижения и непроверенные части, чтобы не спутать отдельные G4/Sonar, A3/Approvals и R5/READ с единой рабочей системой.

## Требуемое поведение

Любой **авторизованный** ИИ, работающий через подключённый Fortis Repo и имеющий
назначенные владельцем конкретные полномочия, должен иметь доступ к ограниченным
типизированным инструментам:

- `sonar.list_projects` — проекты разрешённой организации;
- `sonar.list_issues`, `sonar.get_issue` — Issues с пагинацией;
- `sonar.get_quality_gate` — Quality Gate по проекту с честным указанием области;
- `sonar.propose_accept_issue` — **запросить** изменение одной Issue, а не выполнить;
- `approvals.request_status` — получить безопасный статус собственной заявки.

Эти имена — **требуемый будущий typed AI-интерфейс**, они не являются сейчас
live-инструментами. На текущем шаге реализация находится в `repo_sonar_tools.py`
внутри Fortis Repo container и обращается к отдельному R7 Gateway; `tunnel` и
MCP bridge не являются частью этого deployment gate. У пользователя могут быть и другие
ИИ/коннекторы: универсальная работоспособность зависит от выдачи доступа и
того, что они реально используют этот же ограниченный шлюз. Без машинной
аутентификации или за пределами owner allowlist — **DENY**, а не «любой без ограничений».

**Поток:** ИИ → Fortis Repo typed client → TLS1.3 machine ingress
`POST /v1/reads` для чтения или `POST /v1/actions` для предложения →
trusted Core policy `ALLOW` для READ / обязательный `ASK` для Sonar
`accept_issue` → durable `PENDING` → owner WebAuthn Approvals
Pending/History → `REJECTED` либо отдельный **в будущем разрешённый**
одноразовый `APPROVED → DISPATCHED → EXECUTED / UNCERTAIN` с проверяемым
remote readback. Машинный клиент получает только `requestId,state`
для ASK и типизированную ограниченную проекцию READ; не получает Sonar token,
WebAuthn proof, preview snapshot или право самому устанавливать `ALLOW/ASK`.

## Что действительно проверено (на 2026-11-01)

| Gate | Результат | Доказательство и граница |
|---|---|---|
| G4 отдельный реальный SonarCloud GET проектов и Issues | **OWNER-REPORTED PASS** | Старый G4 самостоятельно читал реальные данные; он не связан с R5 или единым Approvals. |
| A4 реальный Repo→Windows A3 TLS1.3, synthetic ASK/WebAuthn approve/reject/readback | **OWNER-REPORTED PASS** | A3 содержит только synthetic, не Sonar reader. |
| R5 image собран/хэши/временный import smoke/pip check | **OWNER-REPORTED PASS** | `sha256:5fa986d7e532639c5461a87e4a2c34ea8176ec58371f418758d0cd5dfc38bd02`. Но R5 намеренно `Core.adapters={}` и `actor_operations={}`. |
| Единый Core + TLS machine для 4 Sonar READ + `accept_issue` ASK | **OFFLINE SOURCE PASS** | `tests/test_r6_repo_sonar_read_to_approvals_tls_offline.py`: один Core/WSGI/TLS1.3, sandbox FakeSonar, одна owner queue, 4/4 targeted tests. |
| ASK `PENDING` виден в реальном owner WSGI после WebAuthn login; reject → status | **OFFLINE SOURCE PASS** | Virtual FIDO2 credential и live localhost HTTP. `accept_issue` не выполняется. |
| Нельзя отправить READ как mutation, обойти owner routes, подменить токен/policy/HTTP-параметры или получить чужой status | **OFFLINE SOURCE PASS** | Negative auth/scope/schema/replay/status tests. |
| Реальный unified Windows R5 READ с настоящим Sonar GET | **OPEN** | R5 trusted deployment, TLS/grant, owner-managed Sonar READ token и согласованный доступ ещё не выполнены. |
| Реальный unified Windows Fortis Sonar ASK через Repo→Approvals Pending | **OPEN** | Текущий R5 image **не содержит регистрации Sonar ASK**. Offline смешанная композиция **не упакована и не установлена**; нельзя выдавать fake PASS за Windows. |
| Вызов одного специализированного Sonar-инструмента с произвольного авторизованного AI-клиента | **OPEN** | У зарегистрированных Fortis Repo tools сейчас file/process/workspace operations; отдельные `sonar.*` tools/bridge и provisioned client identity не обнаружены. |
| Отчёт «проверки этого PR/коммита пройдены» с доказательством GitHub run/head SHA ↔ Sonar analysis | **OPEN — D1/D2** | Сегодня `get_quality_gate` возвращает `scope=CURRENT_DEFAULT_BRANCH`, `prShaBinding=NOT_VERIFIED_D2`. **Нельзя** интерпретировать `OK` для default branch как статус проверок нужного PR/SHA. GitHub Actions, Sonar analysis/CE task, покрытие scanner, skipped jobs, свежесть и чужой SHA — отдельный контроль. |
| Выполнение реального Sonar WRITE после owner Approve | **NO-GO / OPEN** | Исторический G4 блокирует `Approve` и исходящий POST; то же fail-closed продемонстрировано offline. Позже только owner-authorized одноразовая тестовая Issue, signed WebAuthn, stale/replay/UNCERTAIN/readback. |

## Критичные угрозы и требования перед live E2E

1. **Управляемость любой ИИ-модели.** Fortis Repo не должен хранить Sonar service
   token и host Docker socket; только trusted Fortis на Windows владеет service
   credentials и operator grant lifecycle. AI-initiated mutable capabilities
   следует выдавать через scoped protected API с owner policy. Наличие AI-доступа
   к обычной shell/GitHub/другим плагинам **не гарантирует**, что все изменения
   автоматически пройдут через Approvals. Прямые privileged GitHub API/PAT,
   Git push, CI changes, Sonar direct API, RDG direct writers требуют отдельной
   ревизии permissions и branch/ruleset protections, а не иллюзорного общего gate.
2. **Sonar CHECKS ≠ один Quality Gate.** Для каждого требуемого PR/commit —
   независимая проверка GitHub head/checkout SHA, CI runId/attempt/статусов,
   Sonar project/org/branch-or-PR, CE task/analysisId, времени анализа,
   coverage/new-code rules и пропущенных jobs. При отсутствии точной
   связи — `UNKNOWN/BLOCK`, не `PASS`. В текущем READ implementation
   нет доказанного PR-specific checks attestation.
3. **ASK не равен разрешению POST.** Клиент создаёт только proposal,
   trusted Core самостоятельно формирует Issue digest/preview, owner
   видит `PENDING`. Ни AI, ни HTTP-клиент не могут прислать
   `policy=ALLOW`, `approved=true`, `expectedIssueSha256`, arbitrary
   transition, raw token или upstream URL. Действующий кандидат должен
   сохранять `blocked_approvals` и `NoWriteTransport`, пока не будет
   отдельно разрешён Sonar WRITE.
4. **Один trusted Fortis.** R5 pilot отдельно от действующего A3, их
   WebAuthn origin/state различны. Нужно owner-approved решение по
   единому Core/очереди, а не параллельные несовместимые Approvals.
   Repo1/Repo2 Guards проверяются перед изменениями, влияющими на
   их следующий запуск; менять исходники Docker можно без остановки
   существующих подключений. При потенциально live-влияющих Docker
   действиях — отдельная осторожность.
5. **Сертификаты и жизненный цикл grants:** owner-controlled CA/pin
   verification, TLS1.3, scoped client identity, issue/replace/revoke
   old DENIED/new PASS, private volumes 0600 UID10001, secure backup/logging.
   Текущий TLS A3 истекает `2026-11-07T23:29:17Z`; R5 runbook
   его автоматически не продлевает.

## Реальная приёмка (ещё не выполнена)

**Фаза 1: безопасная READ-проверка** — owner-approved trusted image/credential
bootstrap; из реального Fortis Repo (не тестового Linux mock) два разных
авторизованных AI-клиента вызывают те же typed READ, получают проекты,
страницы Issues, Quality Gate; wrong actor/org/identity получает 401/403.
Публичные ответы не содержат secret tokens или owner state. Отдельно
D1/D2 позволяет понять, прошли ли проверки **конкретного SHA**.

**Фаза 2: ASK request/no-write** — в том же запущенном Fortis, уже содержащем
Sonar READ, через Repo создать proposal для одной разрешённой Issue.
Owner видит exact project/Issue/action/current snapshot/fingerprint,
WebAuthn sign-in; проверка `PENDING` / safe reject / `REJECTED`
из Repo и ни одного Sonar POST. Испытать invalid client,
duplicate UUID, stale Issue, foreign project и отсутствие bypass.

**Фаза 3: owner-controlled WRITE** — только после отдельной письменной
приёмки и выбора безвредной disposable Issue, scoped writable credential,
точного WebAuthn approval; проверить genuine Sonar POST, independent
readback, audit, atomicity caveat/no blind retry. **Сейчас запрещено**.

### Текущие данные исходников

`fortis_approvals/tests/test_r6_repo_sonar_read_to_approvals_tls_offline.py`
складывает действующие `Core`, `RepoIntentBroker`, `RepoIngress`,
`SonarReadAdapter`, `SonarIssueAdapter` (поверх `NoWriteTransport`),
`OwnerWebAuthn` и `OwnerPortal` в **только тестовой** среде.
Он создаёт реальные localhost TLS1.3/HTTP sockets и ephemeral SQLite,
но использует фейковый Sonar без реальной сети к SonarCloud.
Никакой образ/Compose, работающий A3/G4/R5, Fortis Repo, Sonar token
или owner WebAuthn credential в Windows не изменялся.
