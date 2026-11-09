# Fortis Secure Gateway — handoff новому чистому чату

**Срез 2026-11-01 ПОСЛЕ Windows R7 v2 source SHA/pip audit и source/offline functional acceptance 17/17. Текущая точка входа; НЕ новый нормативный план.** Старый [handoff 2026-10-31](../fortis-next-chat-20261031/HANDOFF.md) — история, не актуальный статус. Цель нового чата: **довести задуманные сценарии до реальной работы и закрывать матрицу, НЕ повторяя уже принятые проверки**.

## Обязательно прочитать

1. [Основной нормативный план Fortis](../../guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md), §0–1, §7–10, §12–14 — целевая архитектура и политика; решения владельца имеют приоритет.
2. [Матрица приёмки: 66 сценариев, M0–M8](../../../fortis_approvals/deploy/FORTIS-UNIVERSAL-GATEWAY-ACCEPTANCE-MATRIX-20261101.md) — что должно работать, что значит PASS.
3. [R7 source / Windows evidence journal](../../../fortis_approvals/deploy/R7-UNIFIED-SONAR-READ-ASK-M2-SOURCE-GATE-20261101.md) — история ошибок и результаты PowerShell владельца. Внутри есть **хронологические устаревшие OPEN**: последнее owner evidence в этом handoff/срезе ниже приоритетнее старых промежуточных записей.
4. [Fortis README](../../../fortis_approvals/README.md), [R7 unified Core](../../../fortis_approvals/r7_unified_candidate.py), [R7 server](../../../fortis_approvals/r7_unified_server.py), [Repo typed client](../../../fortis_approvals/repo_sonar_tools.py), [Repo action contract](../../../fortis_approvals/repo_action_contract.py), [Repo machine ingress](../../../fortis_approvals/repo_ingress.py).
5. [AGENTS.md](../../../AGENTS.md). Подключённый Fortis Repo умеет читать/менять исходники, но **не гарантирует** доступ к Windows или регистрацию новых инструментов. MCP bridge не входит в текущий путь; другой checkout `/workspace/repo/Repos/tunnel/AGENTS.md` и `/workspace/repo/Repos/tunnel/runtime/repo-mode/fortis-mcp-bridge.mjs` читать только при отдельном задании на MCP.

## Windows owner-side execution и передача файлов — обязательный процесс

Если задача требует действий на Windows Fortis_M, **не проси владельца скачивать ZIP/attachment через ChatGPT и не используй sandbox download как основной канал**. Готовь и проверяй нужные файлы в Fortis Repo Docker, внутри `/workspace/repo/Workfiles/_fortis_windows_transfer_tmp/<unique-task-id>/`. Если файлов несколько — создай ZIP **там же внутри Docker**, проверь список содержимого, `ZipFile.testzip()` и SHA256. Затем дай владельцу PowerShell-команду, которая через `docker cp` копирует файл из `fortis-repo-test` в Windows, проверяет SHA256 и (если это ZIP) распаковывает в новый каталог. Для одного `.ps1` ZIP не нужен — копируй сам скрипт. Не перезаписывай существующие файлы.

Долговечные исходники остаются в `fortis_approvals/deploy/`/`tests/`; Workfiles task directory — только передаточная копия/пакет. Укажи точный remote path, SHA256, назначение, операции и STOP conditions. Не включай secrets, credentials, private keys/grants, private state или DB. Если `docker cp` недоступен, сначала согласуй альтернативу с владельцем; не переключайся молча на ChatGPT download. **Канонический порядок для всех задач:** `/workspace/repo/README.md` (корень Docker volume Fortis Repo, раздел «Разовая передача файлов на Windows из Fortis Repo»). Краткая ссылка также в [README проекта Approvals](../../../fortis_approvals/README.md).

## Архитектура — нормативные 4 случая

**Один** owner-controlled Fortis Secure Gateway Docker на Windows Fortis_M, внутри **один Core/typed executor** и policy `ALLOW/ASK/DENY`, приватные upstream tokens, audit/receipt/readback, одна owner WebAuthn Approvals UI/очередь и отдельный аутентифицированный TLS machine ingress. Fortis Repo и любой ИИ — недоверенные клиенты; «любой» = **любой отдельно авторизованный actor с разрешёнными typed operations**, а не анонимный пользователь.

| Требует upstream token | Требует ASK | Что реально обязано работать |
|---|---|---|
| Нет | Нет | Без лишнего ASK, безопасные FREE/ALLOW можно выполнять непосредственно через Repo |
| Да | Нет | Fortis делает разрешённый service GET/действие сразу, сам выбирает credential; token не виден ИИ |
| Нет | Да | Durable frozen PENDING; owner Approve/Reject, без service token |
| Да | Да | Frozen PENDING; после точного owner WebAuthn Approve **тот же Core** выполняет typed write с внутренним token + readback; Reject = 0 write |

Все операции, требующие **token ИЛИ owner ASK**, идут через Fortis; никаких generic HTTP proxy/AI-supplied URL/method/headers/policy/owner proof. DENY, отозванные права и отсутствие machine authentication перекрывают любой режим. **AI не может Approve за владельца, читать service token или управлять доверенным Docker.** Owner UI независим от RDG. RDG block protection строго **FREE/ASK, без block DENY**, действующие CAS/domain locks не отменяются. GitHub/CI green не разрешает автоматический Windows RUN, IMPORT или merge. Не заводить множество R5/G4/R7 production services.

**Первый требуемый рабочий end-to-end:**
`авторизованный ИИ → Fortis Repo (typed sonar.list_issues/quality gate) → ОДИН Windows Fortis → настоящий Sonar EU READ (token только внутри Fortis) → bounded ответ ИИ → typed sonar.propose_accept_issue → durable PENDING в том же owner Approvals → владелец Reject/WebAuthn → ИИ читает REJECTED; 0 Sonar POST`.
Позднее: отдельный owner-approved Sonar WRITE, точная привязка PR/head SHA/CI/Sonar, RDG ASK и GitHub/Windows trusted import/run. Не считать успешным default-branch QG проверку конкретного PR.

## Точное состояние после последней работы — что уже доказано

| Этап/объект | Статус |
|---|---|
| **M0 A3 synthetic** | **Windows owner-reported PASS**, отдельный действующий `fortis-a3-synthetic-fortis-1`, pinned TLS1.3 Repo→A3, synthetic ALLOW/ASK/DENY, owner WebAuthn Approve/Reject, audit/SQLite/readback. Это **не** unified Sonar. |
| **G4 real Sonar** | Ранее **owner-reported real SonarCloud EU READ** через **отдельный** G4, не R7. Не повторять на G4 как доказательство R7. |
| **R5** | Отдельный READ-only source/image кандидат, частные Windows проверки PASS, но **не unified service**; не переносить его state/identity. |
| **R6/R7 SOURCE/OFFLINE** | Один Core, два actor grant, четыре Sonar READ через `repo_sonar_tools.py` по TLS/HTTP, fake Sonar, owner portal `PENDING → REJECTED`, actor-bound status, scoped denies, Sonar POST = 0; targeted suite **17/17 PASS**. **Это не live Sonar.** |
| **R7 v1** | Исторический Windows image был собран, но изолированный import **FAIL**, воспроизведён отсутствующий `g4_candidate` в минимальном пакете. Исправлен в R7 v2; **v1 не использовать, не повторять.** |
| **R7 v2 image build** | **OWNER-REPORTED Windows PASS**: точная SHA-verified сборка; образ **существует**, но **не развёрнут** как Fortis-service. |
| **R7 v2 isolated image import smoke** | **OWNER-REPORTED Windows PASS**: pinned image metadata, `preflight-imports`, отсутствие сети/томов/портов, disposable container auto-removed, Sonar POST disabled. |
| **R7 v2 exact image content/dependencies** | **OWNER-REPORTED Windows PASS**: все **19 installed source SHA256**, `fido2==2.2.1`, `cryptography==50.0.2`, `cffi==2.1.1`, `pycparser==3.12`, `pip check`, удалены три disposable containers. **Больше не проверять заново на неизменённом образе.** |
| **M2 Fortis Repo client path** | **SOURCE/OFFLINE PASS, LIVE DEFERRED TO FINAL PHASE:** `fortis_approvals/repo_sonar_tools.py` делает фиксированные typed TLS1.3 запросы к R7 Gateway contract; два actor grant проходят все четыре READ, owner portal получает `PENDING` и Reject возвращает `REJECTED`, scoped denies и actor-bound status проверены, Sonar POST = 0; targeted suite **17/17 PASS**. Live R7 service, grant/token provisioning и client mounts отложены до финальной фазы. Текущий шаг не требует изменений `tunnel` или MCP bridge. |
| **M3 live R7 Sonar READ / M4 live PENDING** | **DEFERRED TO FINAL LIVE PHASE:** R7 Windows service не запущен, token/TLS machine grant R7 не provisioned; настоящий Repo→R7→Sonar GET и owner Sonar PENDING/Reject выполняются после остальных функциональных сценариев. |
| **M5 Sonar WRITE** | **BLOCKED / NO-GO**: `OwnerPortal.blocked_approvals` и R7 `NoWriteTransport` оба запрещают POST. Отдельный owner GO необходим даже для одной disposable Sonar Issue. |
| **M6 PR SHA / M8 GitHub RDG/Windows release** | **OPEN**: точные CI SHA/analysis/run attest, protected writer/approval, RDG G3, Windows import/run D3/D4. |
| **M7 trusted operations** | **PARTIAL/OPEN**: source/hash/pip pass, но `FROM python:3.11-slim` — **изменяемый тег, не pinned digest**; независимый SBOM/CVE/provenance, TLS/grant rotation/revocation/backup, bypass review/trusted admission — OPEN. |

**PINNED R7 v2 OWNER IMAGE:**
`fortis-r7-unified-read-ask-candidate:review-20261101-f9791fd1`
`sha256:2a047aaa6ab74a0b3e47e3a02b3ac663301f8363515f0cd32ed3ad1a562d1b73`.

Owner-confirmed proof markers:
`FORTIS_R7_IMAGE_ONLY_BUILD_PASS`,
`FORTIS_R7_V2_REVIEW_IMAGE_IMPORT_SMOKE_PASS`,
`FORTIS_R7_V2_IMAGE_19_INSTALLED_SOURCE_SHA256_PASS`,
`FORTIS_R7_V2_IMAGE_FOUR_PINNED_PIP_VERSIONS_PASS`,
`FORTIS_R7_V2_IMAGE_PIP_CHECK_PASS`,
`FORTIS_R7_V2_AUDIT_DISPOSABLE_CONTAINERS_REMOVED_PASS`.
При этом `FORTIS_R7_V2_IMAGE_BASE_PROVENANCE_VULNERABILITY_ADMISSION=OPEN`,
`FORTIS_R7_V2_TLS_GRANT_LIFECYCLE=OPEN`,
`FORTIS_R7_V2_SONAR_TOKEN_PROVISIONED=NO`,
`FORTIS_R7_V2_TRUSTED_ADMISSION=OPEN`.
V2 ZIP `/workspace/repo/Workfiles/fortis-r7-unified-source-review-v2-20261101.zip` SHA256 `f9791fd1e5cee092092897825e7886fe040cc0d71d5ea43179c5593cb5ac9df7`; последний owner audit script SHA `fb729cf5b13bf1ae7545565f96bb96b20480d4dbf0fef5dc108b60c2fee06de3`. **Не просить снова выполнять эти скрипты.**

**Срочно отдельно от R7:** текущий A3 server TLS certificate истекает **2026-11-07T23:29:17Z**; прошлый read-only diagnostic PASS, но owner-only certificate rotation и machine grant server revoke в текущем A3 **ещё не реализованы** (ранее DEFERRED). Не менять действующий A3 без явного разрешения владельца. TLS verification не отключать, WebAuthn/SQLite не сбрасывать. До expiry нужен owner-safe план и отдельный GO, либо явное решение о прекращении доступа.

## Следующие задачи новому чату, без лишних кругов

**Приоритет = рабочие сценарии M2→M3→M4, а не новые фиктивные PASS по неизменённому образу.**

1. **M2 inter-container client — functional source/offline focus:** использовать существующий typed client `fortis_approvals/repo_sonar_tools.py` из Fortis Repo container для шести операций (`sonar.list_projects`, `sonar.list_issues`, `sonar.get_issue`, `sonar.get_quality_gate`, `sonar.propose_accept_issue`, `approvals.request_status`). Один Core source/offline проверен с двумя независимыми actor grants: оба проходят все четыре READ через Repo typed client по TLS/HTTP, proposal виден в owner portal как `PENDING`, owner Reject возвращает `REJECTED`, чужой project и неизвестный grant блокируются, cross-actor status denied, Sonar POST = 0; targeted R7 suite **17/17 PASS**. Не добавлять generic HTTP/Admin/Docker и не менять `tunnel`/MCP bridge. Live Repo→R7 READ/ASK отложен вместе с owner TLS identity, machine grant, Sonar token и client mounts.
2. **Pre-deploy security admission — ОТЛОЖЕНА ДО ФИНАЛЬНОЙ ФАЗЫ:** сначала реализуются и принимаются все доступные функциональные сценарии gateway. Только после этого, в самом конце, выполняются base image digest/provenance + SBOM/CVE/dependency admission на финальном неизменённом R7 digest. Текущий metadata/history и SBOM evidence сохраняются как справка; CVE scans, остановленные на Docker login, не считаются PASS. Docker Scout login не входит в текущий путь. Review запрета прямых Sonar/GitHub privileged обходов остаётся частью финальной admission.
3. **R7 live pilot — ФИНАЛЬНАЯ ОТЛОЖЕННАЯ ФАЗА:** owner TLS identity, machine grant, Sonar READ token и mounts `/run/fortis-client/grant` + `/run/fortis-client/server.crt` сознательно отложены до завершения всех функциональных сценариев. Volume/state preflight уже PASS и сохраняется; `Prepare-R7-Candidate.ps1` повторно не запускать. В финальной фазе потребуется отдельный GO, Guard Preview, credentials/mount provisioning, `Verify-R7-Candidate.ps1 -RequireCredentials`, затем R7 start. До этого не поднимать 19103/19104 и не запускать live Sonar.
4. **M3/M4 настоящая приёмка — ФИНАЛЬНЫЙ LIVE GATE:** после завершения остальных функциональных сценариев выполнить четыре реальных READ Sonar из Fortis Repo container через `repo_sonar_tools.py` в один R7 Gateway, negative wrong actor/org/project/no grant, без token leakage. Затем создать одну **настоящую** `PENDING` → owner Reject → REJECTED, 0 upstream POST; actor-bound status и readback.
5. **M6/M8 позже:** PR/commit SHA+GitHub checks/Sonar analysis, RDG FREE/ASK без обхода, Windows IMPORT/RUN owner authorization и rollback. Не терять остальные 66 сценариев.

**Параллельная срочная owner-operation:** A3 TLS expiry 7 ноября — готовить проверяемую безопасную процедуру отдельно от R7 с owner GO, без авто-ротации по воле ИИ.

## Не повторять — явно передать новому чату

**Уже выполнено, НЕТ причины требовать повторного выполнения от владельца:** Windows R7 v2 SHA-reviewed build; ZIP transfer; isolated image smoke; 19 exact source SHA; 4 pip pins; `pip check`; A3 synthetic WebAuthn/TLS owner acceptance; прежний отдельный G4 Sonar READ; R6/R7 fake TLS/Core E2E. R7 v1 FAIL/причина также закрыты, повторная отладка v1 не нужна. **Не начинать новый чат с повторного `docker build`, `docker run`, `pip check`, PowerShell блока или всей Python/JS suite.**

Принцип: **повторный тест только если изменился сам проверяемый artifact / image digest / runtime / credentials / TLS, есть инцидент или это новый ещё не закрытый live gate.** При source modification запускать прицельные связанные тесты, полный regression только при milestone/release или существенном перекрёстном риске. При простой документации — проверка ссылок/списков, не полные 300+ тестов.

**Без explicit owner GO не выполнять:** Sonar real POST, Docker start/stop/restart текущих A3/Repo/G2/G4/R5, live provision токенов и grants, TLS rotation, live MCP bridge update/restart, git push/merge, Windows trusted host changes. Результаты владельца считать evidence, не «хочу перепроверить всё». Отправка секретов в чат запрещена.

**Git/worktree:** root `/workspace/repos/rd-graphs` содержит параллельные staged/untracked RDG изменения; не `git reset/clean/add -A`, не делать общий commit. HEAD при предыдущем просмотре `176ce44c820757ecfb827ea881c0cac6613c8831`, staged diff SHA `75062676803bebde2f36c688ce965f81ebd3e9d4503dc8dcf7e61c59d829096e`; эти Fortis правки **не коммичены и не push**. При новом входе читать только targeted paths.

**При каждом новом шаге обновить:** [матрицу](../../../fortis_approvals/deploy/FORTIS-UNIVERSAL-GATEWAY-ACCEPTANCE-MATRIX-20261101.md), этот текущий handoff и основной план, но не копировать бесконечные промежуточные OPEN в начало README. Для owner evidence различать `OFFLINE`, `WINDOWS IMAGE`, `WINDOWS LIVE`, `REAL SONAR`, `MCP LIVE`; проставлять Case ID и точный gate.

**Общий вердикт:** `FORTIS_UNIVERSAL_GATEWAY_PRODUCTION_ACCEPTANCE=OPEN`. Source/offline функциональный путь принят; реальные Sonar READ/ASK через один Fortis и финальная admission выполняются после завершения остальных сценариев матрицы.

## Продолжение 2026-11-01 — ограниченный R7 Repo client hardening

Добавлен `fortis_approvals/tests/test_repo_sonar_tools.py`; в
`repo_sonar_tools.py` усилены ответы/status, non-finite JSON и redirect boundary.
Первый целевой тест прогнал 4 случая и показал реальный TypeError для
нестрокового `state`; исправление внесено. После исправления тестовый процесс
не завершился успешно/не выдал итоговый PASS из-за проблем с process sessions.
**Текущий статус: SOURCE EDITED / VERIFICATION PENDING**, не новый acceptance PASS.

Следующее действие: из корня `/workspace/repos/rd-graphs` выполнить только
`python3 -B -m unittest discover -s fortis_approvals/tests -p 'test_repo_sonar_tools.py' -v`,
затем адресные R7 tests `test_r7_unified_candidate.py` и
`test_r6_repo_sonar_read_to_approvals_tls_offline.py`. Не повторять Windows build,
image import, 19 SHA, pip pins/check. Не выполнять live deployment, provision,
MCP bridge, Docker, Sonar WRITE или Git actions.

## Продолжение 2026-11-01 — M2 client hardening: проверено

Этот раздел **заменяет прежний статус SOURCE EDITED / VERIFICATION PENDING** в
хронологическом дополнении выше. `repo_sonar_tools.py` теперь:
- отклоняет non-string `state` до set membership (без TypeError);
- отвергает duplicate JSON keys, NaN/Infinity и float exponent overflow;
- redacted-deny для слишком глубокой JSON nesting (без утечки RecursionError);
- сохраняет жёсткий response byte cap и требует HTTP 200 для READ;
- не следует HTTP redirects; отдельный local HTTP 307 test проверяет, что
  Authorization не достигает redirect target ни через GET, ни через POST.

**Targeted M2 client regression: 8/8 PASS.** Дополнительный повторный
source/offline regression: **89/89 PASS** по наборам Repo typed READ contract (8),
Repo READ ingress (14), Sonar READ adapter (13), Sonar inventory (13), gateway (5),
Core lifecycle (23), matrix invariants (5) и Repo client (8). Отдельный
`test_sonar.py`: 21 тест PASS; owner WebAuthn case не стартовал из-за отсутствия
`fido2`. R6/R7 candidate, action-contract и Repo ingress suites не импортируются
в этом контейнере из-за отсутствия `cryptography`; зависимости не переустанавливать
и не повторять ранее принятый Windows pinned-dependency audit.

Matrix doc assertion **OPEN** исправлен явной release-status строкой; matrix
test теперь **5/5 PASS**. План и матрица обновлены. Новый 8/8 — отдельное
M2 source/offline evidence, не замена принятому R7 17/17 и не live evidence.

Никаких real Sonar requests/POST, tokens/grants, Windows containers, Docker
deployment, MCP bridge или Git операций не выполнялось. M2 live, M3/M4,
TLS identity, machine grant, Sonar READ token, client mounts, base image
provenance/SBOM/CVE и Docker Scout остаются в согласованной финальной фазе.

## Продолжение 2026-11-01 — дополнительный read-only regression

`test_sonar_preflight.py` завершился **15/15 PASS**: bounded org/project sample,
exact Issue re-read, stale/project mismatch deny, GET-only, no mutation и
token/message redaction. Это standalone source/offline preflight, не unified R7
live evidence и не изменение статуса M2/M3/M4.

`test_runtime.py`: private-state-directory test PASS; два localhost runtime tests
blocked при старте сервера из-за отсутствующего `fido2`. Один WebAuthn case в
`test_sonar.py` также blocked by missing `fido2`; R6/R7 candidate и action-contract
suites blocked by missing `cryptography`. Не устанавливать эти зависимости заново:
это не причина повторять Windows image dependency audit.

Текущие подтверждённые дополнительные source/offline результаты: M2 client 8/8,
сводный набор 89/89, standalone preflight 15/15, matrix docs 5/5. Принятое
R7 source/offline 17/17 остаётся отдельным прежним evidence; никакого live
Sonar/Windows/credential activity не было.

## Продолжение 2026-11-01 — HTTP error redaction regression

Добавлен local HTTP 401 test: dummy machine grant присутствует в diagnostic
header и upstream body, но Repo client наружу выдаёт только
`FORTIS_HTTP_401`; grant/body не раскрываются. Проверка redirect 307 также
проверяет оба метода на redirect sink и подтверждает отсутствие Authorization.

**M2 client: 9/9 PASS.** Полный выбранный source/offline набор: **90/90 PASS**
(client 9, READ contract 8, READ ingress 14, Sonar READ adapter 13,
Sonar inventory 13, gateway 5, Core 23, acceptance matrix 5).
Standalone `test_sonar_preflight.py`: **15/15 PASS**. Все локальные HTTP тесты
использовали disposable localhost servers и dummy credential, не живой Fortis.

Matrix обновлена с error-redaction case; предыдущие R7 17/17 и Windows image
evidence не пересчитываются. Live M2/M3/M4 остаются deferred; Sonar POST NO-GO.

## Продолжение 2026-11-01 — проверен весь Repo typed-tool каталог

`test_repo_sonar_tools.py` теперь покрывает все шесть клиентских инструментов:
четыре typed READ на `/v1/reads`; `sonar.propose_accept_issue` — только
stable-UUID typed POST на Fortis `/v1/actions`; `approvals.request_status` —
bodyless GET по собственному requestId. Также unknown tool и proposal без
stable requestId должны быть denied.

**M2 Repo typed-client: 12/12 PASS.** Выбранный source/offline набор повторно
завершился **93/93 PASS** (client 12, READ contract 8, READ ingress 14,
Sonar READ adapter 13, Sonar inventory 13, gateway 5, Core 23, matrix 5).
Standalone Sonar preflight — **15/15 PASS**. Proposal 202 — fake local opener,
не настоящая Fortis заявка; live Sonar не вызывался.

Matrix и основной план обновлены. Это не меняет R7 17/17 и не закрывает live
M2/M3/M4. Все actor grants, TLS identity, Sonar token, client mounts,
Windows deployment и Sonar WRITE остаются нетронутыми/отложенными.

**2026-11-01 strict-input regression:** Core 28/28, Gateway 6/6, owner input 7/7, isolated WebAuthn implementation 18/18, R7 unified source/offline 17/17 PASS. The virtual WebAuthn authenticator is test-only; no Windows human-key acceptance or live deployment was performed. `core.py` and `owner_portal.py` now differ from the frozen R7 v2 package, so that image remains historical evidence and does not contain these changes. Do not rebuild v2; a future image requires a new versioned package and owner review. Live M2/M3/M4 remain deferred; Sonar WRITE remains NO-GO.


## Продолжение 2026-11-02 — R7 scoped volumes: прежняя подготовка подтверждена, первый preflight исправлен

Owner supplied metadata-only Windows output for all four existing R7 volumes:

- `fortis-r7-state|local|local|2026-11-01T08:15:45Z` — `ATTACHED_CONTAINERS=NONE`
- `fortis-r7-identity|local|local|2026-11-01T08:15:46Z` — `ATTACHED_CONTAINERS=NONE`
- `fortis-r7-grant|local|local|2026-11-01T08:15:46Z` — `ATTACHED_CONTAINERS=NONE`
- `fortis-r7-sonar-token|local|local|2026-11-01T08:15:46Z` — `ATTACHED_CONTAINERS=NONE`

This corroborates the pre-existing HANDOFF statement that the R7 volume/state preflight had already PASSed and that `Prepare-R7-Candidate.ps1` must not be rerun. The creation times are consistent with the preparer's sequential four-volume creation loop; metadata alone does not attest contents. Preserve all four; do not create, delete, rename, mount or inspect contents. Do not rerun `Prepare-R7-Candidate.ps1` or old `Verify-R7-Candidate.ps1` (the latter is pinned to the historical unscoped image).

The first new scoped runtime preflight (`Preflight-R7-P1-Scoped-Windows-ReadOnly-20261102.ps1`, SHA256 `d201a062…1355dc`) incorrectly required those volumes to be absent. Its stop was a **preflight logic error**, not a volume conflict or R7 container. The owner had already passed Linux Engine, exact scoped image pin, Repo/A3 health and mount isolation. Its port checks were not reached.

A corrected strictly read-only continuation is prepared: `fortis_approvals/deploy/Preflight-R7-P1-Scoped-Windows-ReadOnly-Resume-20261102.ps1`, SHA256 `07315249b5e7dade0aec85599dc9948fc7d64e31b3c68434d609c1222d33d8b9`; static tests **3/3 PASS**; byte-exact transfer copy at `/workspace/repo/Workfiles/_fortis_windows_transfer_tmp/20261102-r7-p1-scoped-runtime-preflight-resume/`. It pins the scoped image ID, checks only the four exact owner-reported volume metadata tuples and no attached containers, rechecks Repo/A3/mount isolation and ports 19103/19104. It does not read volume contents, mount volumes, start/stop containers, create/delete volumes, provision credentials, execute Guard Preview, or deploy R7. **Windows run still OPEN.**

After corrected preflight PASS: separately perform Repo1/Repo2 Guard Preview and obtain explicit owner GO before any TLS1.3 identity, machine grant, Sonar READ token, client mount or R7 start. No real Sonar request yet; Sonar POST remains blocked. This is a dated continuation note; preceding 2026-11-01 handoff evidence remains historical.


## Продолжение 2026-11-02 — corrected R7 scoped runtime preflight OWNER-REPORTED PASS

Owner returned the complete output from `Preflight-R7-P1-Scoped-Windows-ReadOnly-Resume-20261102.ps1` (SHA256 `07315249b5e7dade0aec85599dc9948fc7d64e31b3c68434d609c1222d33d8b9`). Reported PASS markers: Linux Docker Engine; exact scoped image pin; existing Repo running; A3 healthy; Repo workspace/trusted mount isolation; exact four existing R7 volume metadata; all four volumes unattached; previous volume/state acceptance reused; Docker-published ports and Windows TCP ports 19103/19104 available; final read-only preflight PASS.

The owner output explicitly confirms: Guard Preview NOT EXECUTED; credential provisioning NOT EXECUTED; live deployment NOT AUTHORIZED; containers started NONE; volume contents read NO; volume mutations NONE. This closes the corrected **read-only runtime preflight** only. It does not authorize R7 start, TLS/grant/token provisioning, client mounts, MCP registration or Sonar requests.

Guard sequencing: the project matrix records Repo1 Guard Preview as previously PASS; do not repeat it absent source/config change. Repo2 Guard Preview is a separate outstanding read-only check. The canonical `script-control-center` Git source has `Repo2DirectGuard.ps1` SHA256 `08ab2a7b3051e6899a47af8cd09fc2ffe6e560cd7638b8160d1b2c3a40402241`, pinned by the Repo2 quiet launcher; source documentation identifies it as the Repo2 Preview entrypoint and requires non-elevated Windows PowerShell. This is source-only until owner runs `-Mode Preview`; it must not be invoked with `-Mode Run`. The current `script-control-center` checkout is on `main` at `51498cd6dd955667b15d54299045f10f5b432346`; unrelated worktree changes exist, but the relevant guard/launcher/docs paths are clean. Do not pull, stage, commit, or alter those unrelated files as part of this R7 gate.

Next: perform only the separate Repo2 read-only Guard Preview against the owner's current Windows Git clone after verifying the clone/source and pinned SHA. If PASS, request a distinct explicit owner GO before any TLS1.3 identity, one machine grant, private Sonar READ token, client mounts or R7 start. Repo1 preview remains previously accepted. Real Sonar GET, live PENDING/Reject and Sonar POST remain OPEN/blocked.


## Продолжение 2026-11-02 — Repo2 read-only Guard Preview OWNER-REPORTED PASS

Owner executed the exact Repo2 source-pin + read-only Preview sequence from `C:\Users\alexa\Repos\script-control-center`. Reported markers: `REPO2_GUARD_SOURCE_PIN_PASS`; `FORTIS_REPO2_GUARD_PREVIEW_PASS`. The two target source/launcher paths were clean; guard SHA256 matched `08ab2a7b3051e6899a47af8cd09fc2ffe6e560cd7638b8160d1b2c3a40402241`; launcher contained the exact uppercase pin. Guard JSON: `Mode=Preview`, `Preflight=PASS`, `ConfigState=Pinned`, `ContainerIdMatched=True`, `LinuxUid=1000`, `DirectModuleHashVerified=True`, `NoWindowsProfileEdits=True`.

This closes the separate Repo2 read-only Preview gate. Together with the previously accepted Repo1 Preview, **Repo1 + Repo2 Guard Preview = OWNER-REPORTED PASS**. Repo2 was not restarted; no Windows profile edits or Docker/volume/config mutations were reported. This is not `-Mode Run`, not a deployment/cutover, and does not authorize R7 start or provisioning.

Next: obtain a separate explicit owner GO for the exact proposed minimal R7 trust provisioning (TLS1.3 server identity, one scoped machine grant, private Sonar READ token, and read-only client mounts), then review each action against the preserved four existing R7 volumes and existing Repo/A3 isolation. No provisioning or live deployment until that GO. Sonar GET/ASK and live Repo→R7 integration remain OPEN; Sonar POST remains blocked.


## Продолжение 2026-11-02 — минимальный R7 trusted provisioning design подготовлен (SOURCE-ONLY)

После owner-reported PASS corrected runtime preflight и Repo1/Repo2 Guard Preview подготовлены два source-only артефакта: fortis_approvals/deploy/compose-r7-p1-scoped.yaml (exact scoped image tag, pull_policy: never, no build/pull, fixed non-secret org/project, loopback-only ports, four existing external volumes) и R7-P1-MINIMAL-TRUSTED-PROVISIONING-20261102.md (owner GO gates, TLS/grant/token/client mount and live READ/ASK sequence). Static design tests test_r7_p1_trusted_provisioning_static.py 7/7 PASS.

Source review found a real UID contract: R7 server private grant must be UID 10001/mode 0600; repo_sonar_tools._grant_from_file() requires the client grant owner to be Repo UID 1000/mode 0600. Therefore do not mount one server grant file into both. Proposed new fortis-r7-client volume (NOT CREATED) will contain only the client grant-copy + public CA certificate; no Sonar token, server private key, R7 state or owner DB. The four existing prepared volumes remain unchanged.

Adding the client mount to the already-running fortis-repo-test requires owner-reviewed recreation with exact configuration preservation and proven rollback; separate explicit GO is mandatory. No second Repo/Tunnel/MCP architecture. The shared Repo UID 1000 means this one machine grant is usable by any process in that container; it is a single-actor pilot boundary, not per-AI identity or multi-agent isolation.

The existing unpinned compose-r7-unified-read-ask.yaml uses :local + build and must not be used for this pilot. The new Compose is source-only and not executed. Owner WebAuthn invitation must be issued only after first R7 start because pre-creating owner.sqlite before _fresh_r7_state() marks the state root would make the strict fresh-state check fail.

No fifth volume created, no credentials/TLS provisioned, no R7/Repo container started or changed, no Sonar request, no Compose deployment. Separate GO-1 (secret provisioning), GO-2 (R7 start + owner enrollment), GO-3 (Repo recreate/client mount), GO-4 (live READ + ASK/Reject) are defined. Sonar POST and Approve remain blocked; P1-02 AI workflow dispatch and P1-C actual Issue mutation remain separate OPEN/NO-GO gates.


## Продолжение 2026-11-02 — pinned Compose review handoff / remaining pre-provision checks

A new source-only P1 Compose file was prepared and transferred to the Windows handoff area byte-for-byte: SHA256 115e283aaee3a6771f0a879008f4048c03150a7422f6b03757fb5105f6c4a5be. It pins the scoped owner-audited image tag, sets pull_policy never, contains no build stanza or secret environment, pins only EU + alexpastukhh + AlexPastukhh_obs-planning-docs, publishes only 19103/19104 on host loopback, and mounts only the four existing external server volumes (state RW; identity/grant/token RO). It does not include the proposed Repo-only client volume.

The Linux Fortis Repo environment has no Docker CLI, Ruby/YAML parser or yq, so Compose parser validation was not performed there. The next safe owner-side check is only `docker compose --project-name fortis-r7-p1 -f compose-r7-p1-scoped.yaml config --quiet` after SHA-verified docker cp to Windows, plus local image tag→full ID check. This config-only check does not start containers or create networks/volumes. Do not run `up`.

Additional source review caveats recorded in the provisioning runbook: (1) after GO-1 creates the fifth `fortis-r7-client` volume, do not rerun the previous four-volume preflight (it intentionally rejects unexpected R7 volume names); a separate five-volume metadata verifier is required. (2) The current audited image's shared OwnerPortal hardcodes the `G4 READ ONLY` heading when read_only_banner=True, and R7 enables that flag. This is cosmetic and does not alter auth/ASK/Reject enforcement, but it mislabels the R7 portal; disclose/accept it or request a source fix and new image digest/build/audit before owner enrollment.

No secret, certificate, grant, token or fifth volume was created. No existing volume content was read or changed. No container was started/recreated, no Sonar request made, no Docker deployment executed. Current status remains NOT AUTHORIZED.


Validation after the source-only Compose/runbook update (2026-11-02): `test_r7_p1_trusted_provisioning_static.py` **7/7 PASS**; `tools/rdg-docs-audit.py` **PASS** (`285` Markdown files, `18` normative, `64` archived, `203` immutable snapshots, `594` checked links); pinned Compose source and Workfiles copy byte-identical at SHA256 `115e283aaee3a6771f0a879008f4048c03150a7422f6b03757fb5105f6c4a5be`. Docker CLI and YAML parser are unavailable in Linux Repo container, so owner-side Windows `docker compose config --quiet` remains OPEN. No Docker/volume/container/secret/network/Sonar mutation was performed.


## Windows Compose validation evidence — owner-reported PASS (2026-11-02)

Owner supplied the full PowerShell transcript for the exact file `compose-r7-p1-scoped-20261102.yaml`: `docker inspect fortis-repo-test` reported running; `docker cp` succeeded from the prepared Repo Workfiles path; local SHA256 matched `115e283aaee3a6771f0a879008f4048c03150a7422f6b03757fb5105f6c4a5be`; local tag resolved to exact expected image ID `sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024f2c062bac0a18ce4`; and `docker compose --project-name fortis-r7-p1 -f <file> config --quiet` exited 0 and printed `FORTIS_R7_P1_COMPOSE_CONFIG_PASS`. Owner explicitly printed `FORTIS_R7_P1_DEPLOYMENT=NOT_AUTHORIZED`.

This closes the Windows Compose syntax/configuration check only. It does not authorize or evidence `compose up`, container/network/volume creation, secret provisioning, WebAuthn enrollment, Repo recreate/mount, or Sonar requests. No GO-1/GO-2/GO-3/GO-4 has been granted by this transcript. The next irreversible boundary remains separate explicit owner GO-1 for trusted secret provisioning; until then all four existing volumes remain untouched and the proposed fifth client volume remains uncreated.

## Продолжение 2026-11-02 — GO-1 owner transfer + Windows PowerShell parser OWNER-REPORTED PASS (NOT EXECUTED)

Owner transferred only the versioned GO-1 source from the Fortis Repo container to Windows with docker cp. Local SHA256 matched exactly: 7c2873c880ed1ed8858ed105b1ea606c428c70f0a7bef549a6604581a0b50332. Owner then ran System.Management.Automation.Language.Parser.ParseFile under Windows PowerShell 5.1; parser returned zero errors. Markers: FORTIS_R7_P1_GO1_TRANSFER_SHA256_PASS; FORTIS_R7_P1_GO1_WINDOWS_PS_PARSER_PASS; FORTIS_R7_P1_GO1_SCRIPT_EXECUTED=NO; FORTIS_R7_P1_GO1_DEPLOYMENT=NOT_AUTHORIZED.

Canonical source: fortis_approvals/deploy/Provision-R7-P1-Trusted-20261102.ps1. Canonical transfer: /workspace/repo/Workfiles/_fortis_windows_transfer_tmp/20261102-r7-p1-go1-owner-review-02/Provision-R7-P1-Trusted-20261102.ps1. Exact SHA256: 7c2873c880ed1ed8858ed105b1ea606c428c70f0a7bef549a6604581a0b50332. The earlier owner-review-01 copy is superseded and must not be used.

Offline source evidence remains 10/10 provisioning static + 7/7 trusted Compose/provisioning static PASS; embedded Python compile, real cryptography 50.0.2 ECDSA CA/leaf + SAN/EKU/chain validation and temporary-directory provision/verify smoke PASS; docs audit PASS (594 links). Windows parser evidence is owner-reported. No Docker helper container ran; no fifth volume, TLS identity, grant or Sonar token was created; no existing volume content was read or changed; no R7/Repo container was started or recreated; no Sonar HTTP request or POST occurred.

Next: owner independently checks the actual new SonarCloud token permission model in the UI: exact project AlexPastukhh_obs-planning-docs, Browse/READ only; prefer SOT Selected projects + Browse if available, otherwise a restricted service-user PAT with no admin/write privilege. The script's typed SONAR-READ-ONLY acknowledgement is an owner assertion, not a technical privilege check. If this scope cannot be verified, STOP and do not enter a token.

GO-1 remains NOT AUTHORIZED. A separate explicit owner GO-1 is required after scope verification before running the provisioner. The provisioner is not a harmless parser/preflight script: after two typed confirmations and hidden token input it creates fortis-r7-client and writes six trust files across the four existing server volumes plus the new client volume. GO-1 does not start R7, recreate Repo, or make Sonar requests. GO-2 R7 deployment/owner enrollment, GO-3 Repo client mount/recreate, and GO-4 live READ+ASK/Reject remain separate approvals. Sonar POST remains blocked.
### Token-permission documentation clarification (2026-11-02)

Do not assume the SOT Browse option exists solely from the September announcement. Current official SOT documentation still describes only Execute analysis, while the SonarSource announcement and an October 7 staff reply say Browse is available for Selected projects (not organization-wide). Treat the actual current organization UI as authoritative: choose SOT only if it explicitly offers Selected projects + Browse and allows Browse without extra permissions, scoped to AlexPastukhh_obs-planning-docs. If the UI offers only Execute analysis, STOP; do not substitute it. Fallback is a dedicated service-user PAT whose account has only Browse on that exact project and no Administer Issues, Execute Analysis, Administer or other excess privileges (PAT inherits the user's permissions). References: https://docs.sonarsource.com/sonarqube-cloud/administering-sonarcloud/managing-organization/scoped-organization-tokens ; https://community.sonarsource.com/t/new-expanded-scope-organization-tokens-for-automation-in-sonarqube-cloud/188067 ; https://docs.sonarsource.com/sonarqube-cloud/managing-your-projects/administering-your-projects/setting-permissions ; https://docs.sonarsource.com/sonarqube-cloud/managing-your-account/managing-tokens


## 2026-11-02 continuation — user asks to complete the scenario, not repeat permission tests

- Owner-selected Sonar credential model remains broad account token + trusted Fortis policy/ASK. Do not require Browse-only SOT, restricted PAT, token suffix inspection, or repeated permission experiments. G4 live Sonar GET → ASK/PENDING → WebAuthn Reject → exact GET readback evidence is accepted historical evidence; do not re-run it merely to reconfirm.
- Repo-side one-command scenario runner added: `fortis_approvals.sonar_review_scenario`. `review --issue-key ... --reason ...` performs the four pinned Sonar READs, emits bounded report, and submits one typed ASK; `status --request-id ...` reads the owner decision. The same stable request ID is idempotent. No Sonar POST, owner decision or token access occurs in Repo.
- Source/offline evidence: scenario runner 7/7, R7 TLS + typed Repo client + owner Reject 19/19, Repo typed client 12/12, provisioning static 10/10, trusted Compose/runbook 7/7. This proves source/test flow, not a live new R7 deployment.
- Runtime facts checked from the current Repo process: `/run/fortis-client` mount absent; R7 machine port 19104 unreachable; legacy G4 owner port 18991 reachable but is not the Repo machine ingress. This is the concrete reason the new Repo→R7 live scenario cannot yet run from this container. No Docker CLI/socket or PowerShell exists in this Repo container; Windows host deployment cannot be executed from here.
- Current GO-1 source: `Provision-R7-P1-Trusted-20261102.ps1`, SHA256 `0e41fc8ea14e9aabcc7aea8c0b3ea8f46b2f23be99f0423480c13b09d870cfea`, byte-exact Workfiles transfer `20261102-r7-p1-go1-owner-review-04`. One typed `PROVISION-R7-P1` confirmation followed by hidden local token entry; no second token-scope acknowledgement. Owner must verify this new SHA and PowerShell parse once; old owner-review-01/02/03 copies are superseded.
- Still not executed: GO-1 secret provisioning, GO-2 R7 start/owner enrollment, GO-3 Repo container recreate with client-only RO mount, GO-4 live Repo→R7→Sonar READ + ASK/Reject/readback. Existing four R7 volumes remain untouched. Sonar WRITE remains blocked.
- AI-triggered GitHub workflow-dispatch P1-02 is still not implemented. Existing `.github/workflows/sonarqube.yml` supports manual `workflow_dispatch`; last accessible manual run 40875491474 completed successfully on 2026-10-29. This can serve as scan baseline but is not AI-triggered dispatch acceptance.


## Current-status pointer — 2026-11-03

This handoff remains an immutable chronological snapshot. For current status,
use the main plan and the P2 source review. Later evidence supersedes earlier
next-step wording in this file:

- GO-1 trusted provisioning: **OWNER-REPORTED WINDOWS PASS / DONE**.
- GO-2 P1 R7 deployment and owner WebAuthn enrollment: **OWNER-REPORTED WINDOWS PASS / DONE** for the P1 image; this does not prove P2 deployment.
- GO-3 source/Guard release, revision-04 integrity and read-only pre-cutover: **PASS**; controlled Repo recreate and client RO mount: **NOT EXECUTED / NOT AUTHORIZED**.
- P2 package, Windows image build and installed-source/import audit: **OWNER-REPORTED PASS** for image `sha256:e751f6ca0cfe6ce290cf580de2f243071ee1f3e681baa8827c6cea41a16fa402`; P2 deployment: **NOT PERFORMED**.
- Full pinned WebAuthn/HTTPS suite: **BLOCKED** in the Linux Repo environment. GO-4/live Repo→R7→Sonar E2E: **OPEN / NOT STARTED**.

Do not repeat GO-1/GO-2 provisioning or old P1 image/audit work. Any runtime
mutation requires a separate explicit owner GO and must preserve rollback.
