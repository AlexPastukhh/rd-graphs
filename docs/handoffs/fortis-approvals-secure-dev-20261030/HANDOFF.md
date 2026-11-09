# Fortis / RDG — HANDOFF новому чату: RDG, Docker, Approvals, безопасный GitHub CI/CD

> **СТАТУС: АРХИВНЫЙ HANDOFF 2026-10-30, НЕ новый нормативный контракт.** Действующие факты — в [RDG-CURRENT-STATE](../../guides/RDG-CURRENT-STATE.md), [контракте](../../guides/RDG-ACTIVE-CONTRACT.md), коде и тестах. **Новый полный принятый план:** [FORTIS-APPROVALS-SECURE-DEVELOPMENT](../../guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md). Это не одобрение живых writes, Docker/Windows/credential операций.

## 0. С чего начать в новом чате

Пользователь разрабатывает **RDG (Requirements–Decisions–Actions Graph)** через Fortis Repo Docker, с настоящим RDG server на доверенном Windows Fortis_M. Новая главная задача — **отдельный Fortis Action Gateway + Fortis Approvals** с политиками ALLOW/ASK/DENY, независимым owner UI, сохранением exact запросов, RDG и SonarCloud adapters и переходом из Approval UI к сущности в существующей вкладке RDG. Кроме того, нужен **защищённый цикл разработки**: AI редактирует код лишь в недоверенном Fortis Repo/разрешённой GitHub-ветке; PR → GitHub-hosted Actions build/tests/SonarScanner → чтение точного анализа Sonar через Gateway → owner review/merge → **отдельный Windows Git clone вне AI-доступа** получает **точный проверенный финальный commit SHA** → независимые AV/security checks → отдельное разрешение на локальный запуск.

**Не начинайте новый Sonar-only approval или Windows reporting Dispatcher.** Читайте полный план выше: G0–G4, D1–D4, gates, bypass checks, scope и реализацию RDG. Готового универсального Gateway **нет**. Существующий RDG approval pilot — **не** production trust boundary. Старый auto-update из Repo ZIP прямо в Windows противоречит новой целевой политике. **Перед новыми недоверенными AI-правками предложить владельцу временно остановить Windows auto-deploy, но не RDG server и не Repo CI watcher**; самостоятельные host действия не разрешены. Постоянный cutover — лишь после готового нового importer.

## 1. Порядок чтения и статус источников

1. 'AGENTS.md' — порядок разработки, запреты на потерю чужих файлов.
2. 'README.md', 'docs/README.md', 'docs/DOCS-POLICY.json' — обзор/реестр нормативных документов.
3. 'docs/guides/RDG-CURRENT-STATE.md' — последний status.
4. 'docs/guides/RDG-ACTIVE-CONTRACT.md' — принятый предметный контракт, авторизация, RDG approval pilot.
5. 'docs/guides/RDG-DECISION-V1-CONTRACT.md' — kernel/Application, Decision и Plan v3.
6. 'docs/guides/RDG-OPERATIONS.md' — Docker/Windows, gateway, CI, approvals, безопасный запуск.
7. 'docs/guides/RDG-DEVELOPMENT-PLAN.md' — **единая очередь RDG** и acceptance A0–A17.
8. 'docs/guides/VIEWER-EXPLORER.md' — принятый UX и оставшиеся несоответствия.
9. 'docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md' — **полный новый межпроектный план**, не конкурирует с RDG plan.
10. 'docs/handoffs/fortis-approvals-secure-dev-20261030/SOURCE-TRANSITION.md' — исходная запись пользователя о legacy→Sonar Gateway (если сохранена; также в архивном пакете для нового чата).
11. 'tests/visual/rdg-ui-prototype.html' — visual reference, не доменный API; последующие уточнения контракта имеют приоритет.
12. 'docs/handoffs/rdg-next-chat-20261029/HANDOFF.md' — очень подробный **исторический** снимок тестового процесса и частного API; нельзя автоматически считать его последним состоянием.

Действующие документы: 'python3 -B tools/rdg-docs-audit.py --list-active'. Поиск 'rg' исключает архивы через '.ignore'; для них используйте явный путь. Старые handoff snapshot не редактировать.

## 2. Предметная модель RDG для нового исполнителя

- **Process Graph** — общий процесс, единственные Graph/Plan/History owner. **Working Graph** — явно созданный scope по memberIds/rootIds в том же процессе, **НЕ** копия сущностей и не второй Plan. WG пересекаются общими ID. Новый процесс не получает 'Main work' автоматически. Новые блоки из WG входят в неё, из полного Graph не входят автоматически ни в одну WG.
- **Requirement** — требуемый результат, **Decision** — вариант решения ('selected' ≠ 'completed'), **Graph Action** — самостоятельное конкретное обязательное действие от R/D; **external/low-level Action** — операция или Plan task вне Graph. **Canon/Context/Info/Evidence** — отдельные справочные/обосновывающие объекты. D→D запрещено.
- **Decision Group** — настоящий R→D membership, 'selectionRequired' и 'mutuallyExclusive' независимы. Отмена ветви не удаляет факты, history или placements. Общие сущности сохраняют актуальность через другие действительные основания. 'Показать исключённые' не выбирает Decision.
- **Plan v3** — последовательность размещений, forks/cases, необязательные anchors/deadlines; планирование не исполняет Action и не выбирает Decision. 'shownCases', 'historyWindow', 'planWindow' — view, не owner. History содержит реальные события и pinned snapshots.
- Готовые Graph templates и lens graphs, recommendation packages: просмотр/рекомендация ≠ применение/исполнение, insert переносит identities через remap. Gendocen dependencies/review ≠ completion.

Предметные writers, CAS/grants, evidence, transactionId, preflight/receipt/recover и actualness не переносить в универсальный Approvals Core. Он проверяет **полномочие выполнить действие**, не его предметную правильность.

## 3. Код и каталоги

| Где | Что |
| --- | --- |
| '/workspace/repos/rd-graphs' | Git рабочее дерево **в Fortis Repo Linux Docker**, НЕ Windows-клон |
| '/workspace/repo/Workfiles' | отдельные данные/артефакты Docker |
| 'tools/rdg-portable-service.py', 'tools/rdg-portable-model.py', 'tools/rdg-decision-model.py' | общий Application, view/Plan, Decision kernel |
| 'tools/rdg-agent.py' | Agent API client, включая pilot approval_request/read |
| 'tools/rdg-decision-ui.js', 'tools/rdg-visual-projection.js' | runtime Viewer/Graph layout |
| 'tools/build-rdg-layout.py' → 'tools/rd-graph-viewer.user.js' | сборка generated browser bundle |
| 'tests/visual/rdg-ui-prototype.html' | прототип визуальной логики |
| 'tools/rdg-approval-executor.py', 'tools/rdg-approval-surface.py' | exact RDG approval executor/Viewer transport |
| 'tools/rdg-webauthn.py', 'tools/rdg-credential-store.py' | WebAuthn verifier и credential persistence |
| 'tests/rdg-approval*.test.py', 'tests/visual/rdg-approval-viewer.cjs', 'rdg-persistent-approval.cjs' | acceptance технического RDG pilot |
| 'tools/rdg-gateway.py', 'tools/rdg_gateway_entry.py' | существующий **RDG-only** private gateway |
| 'deploy/rdg-server/' | RDG Caddy/Docker compose, Windows scripts и updater |
| 'tools/rdg-ci.py' | source fingerprint + tests + CI zip + watcher |
| '/workspace/repo/Workfiles/rdg-ci/' | 'ready.json', 'status.json', build ZIP, watch.log/pid |
| '/workspace/repo/Workfiles/rdg-gateway-context.json' | **несекретный** profile='gateway', origin, namespaceId |
| '/workspace/repo/Workfiles/rdg-ci-pwsh-7.6.9/pwsh' | PowerShell для Linux CD tests |

**Важно:** точные пути Repo внутри контейнера **не** являются автоматическим Windows bind mount; data/grants/secret volumes доверенного сервера не выдавать AI.

## 4. Docker на доверенном Fortis_M

В предыдущих реальных проверках Compose project 'rdg-personal' включал:
- 'rdg': Application/Authority/FileStore/writer, internal only (не host port).
- 'proxy' (Caddy): браузерный вход 'http://localhost:18880', loopback only '127.0.0.1:18880:8080' в Local mode; Basic + '/session/*' Origin/CSRF; machine '/api/*' не публикуется.
- 'rdg-api-gateway': private RDG-only API 'http://rdg-api-gateway:8081' по Docker network 'rdg-personal_agents', без host port; fixed upstream 'rdg:8080', scoped assistant bearer **только внутри gateway**, никаких arbitrary URL/shell/admin.
- 'rdg-personal_rdg_data': живые owners, не трогать.
- 'rdg-personal_rdg_gateway_secret': отдельный private RO volume с assistant credential, **не монтировать** в Repo Docker.
- Обязательный operator '-AgentContainer ТЕКУЩИЙ_ID' подключает допущенный Repo container в agents network и проверяет nonprivileged/no-socket/no-secret mounts. У **Fortis Repo контейнера был старый ID '7b8c66352643'**, который был удалён/восстановлен: больше НЕ подставлять его без актуальной Docker проверки. Имя Compose 'fortis-flattened' относится к прежнему состоянию. Уточнить сейчас реальные Docker names/IDs/network membership у владельца. Сам 'proxy' не обязательно ссылается на конкретный ID Repo; private gateway network routing отдельно.

**Только чтение, Repo:**

~~~sh
cd /workspace/repos/rd-graphs
git status --short
python3 -B tools/rdg-docs-audit.py --list-active
python3 -B tools/rdg-agent.py doctor --context /workspace/repo/Workfiles/rdg-gateway-context.json
python3 -B tools/rdg-agent.py catalog --context /workspace/repo/Workfiles/rdg-gateway-context.json
~~~

**Только чтение, Windows оператор:**

~~~powershell
docker ps -a --format 'table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}'
(Invoke-RestMethod 'http://localhost:18880/healthz').buildId
~~~

Не делать 'docker compose down -v', сброс/migrate/revoke для живого процесса, не читать и не переносить в чат bearer, не переустанавливать gateway ради простого доклада. Windows host действия — только владелец.

## 5. Уже сделано: состояние RDG, CI/CD и UX

- RDG runtime Decision D1–D9 реализован на common Application: Plan v3, registry/packages, ready/lenses/templates/copies, focus/WG, occurrence layout, Explorer, view tabs, отдельные read sets и тесты. **Полный UX и Stage 4 NOT ACCEPTED**.
- В Viewer обновлены полноэкранный Explorer, Process→WG tree, compact Graph, устранены оторванные aliases A5/A17 в WG, focus drag/Back, регрессионные tests. Временная дорога History→Now→Plan; inline «Границы показа» (два календаря, включительные периоды) и ⚙ «Настройки дороги» (девять регуляторов), индикатор Plan. Browser desktop **16/16**, system **23/23** PASS на изолированных тестах (не Windows UX acceptance).
- **Известный смысловой UX gap:** History не полностью воспроизводит исторический контекст на момент события в основной карточке; недостаточно очевидны различия selected/completed, группы, обязательные Graph Actions, типы связей и причинность Plan forks. Поздний контракт важнее буквальной demo картинке.
- Repo watcher 'python3 -B tools/rdg-ci.py --watch' создает status/ready и immutable ZIP; Windows updater 'deploy/rdg-server/Update-RDG.ps1 -Mode Local -AgentContainer NEW_ID -Watch' через host 'docker cp' проверяет ZIP и обновляет frozen RDG server. Работающий Repo source не является running server. При изменении самого updater нужен **целый проверенный bootstrap**, не править старый PS1 вручную.
- Факт при подготовке handoff: HEAD **'176ce44c820757ecfb827ea881c0cac6613c8831'**, staged index diff sha256 **'75062676803bebde2f36c688ce965f81ebd3e9d4503dc8dcf7e61c59d829096e'**; дерево сильно dirty/untracked — не выполнять clean/reset/commit/push без отдельной задачи.
- Repo CI status был 'ready' для **'ci-20261029t094658360326-e7fcb63d63'**, ZIP sha256 **'a1253537fb228171f27dbef1b770b806071a0f71d5e5440d23b0cf2b8fea2000'**; watcher PID **302** был жив при readback. PID/версии — снимок, нужно повторно проверить.
- **Не подтверждено:** что именно этот build развернут на Windows (требуется '/healthz'). Периодически private gateway не отвечал ('RDG_REMOTE_UNAVAILABLE'); это не доказательство порчи данных.

**Новая цель** запрещает прямой Repo ZIP→Windows automatic deployment как постоянную доверенную схему. Перед работой AI с недоверенными ветками **предложить владельцу временную паузу именно Windows Update-RDG.ps1 -Watch**, чтобы новое тестирование не приводило к самоустановке. Рабочий RDG server и Repo CI build watcher продолжат работу. Ничего не выключать самостоятельно. После проверенного нового importer — окончательный cutover и закрытие обхода.

## 6. RDG approvals — уже есть технический pilot, не готовый универсальный сервис

В текущем RDG:
- 'approval_request' + 'approval_read' с frozen request+reason, pending metadata/unaccepted intent.
- 'preflight.inputBinding' pin, before/after preview, exact executor, transient/persistent credential, WebAuthn, signed approval/verifier status, retry/recover.
- Host-configured 'approval_factory' и Viewer transport 'list/open/choose/complete/status/recover'; ordinary Agent не approve/reject.
- Статусы 'rejected', 'approved-awaiting-recovery', 'executed-approved', 'executed-independently'.
- **Открытые риски:** 'humanApprovalVerified=false', 'osIsolationVerified=false' в исходном pilot; host admin/key-binding/revoke и protected code/owner/writer boundary непроверены. File move/migration approval не реализован. Работающий private RDG gateway может дать AI прямой write через scoped grant — это **обход будущей policy ASK**, если его не заблокировать.

Требуемая миграция: выделить общий **Fortis Approvals Core** (policy ALLOW/ASK/DENY, exact action bindings, signed owner decision, durable audit/recover), **НЕ** переносить туда предметные R/D/Action rules, RDG Graph/Plan/journal. RDG остаётся domain writer и typed adapter. Старые RDG approval_request/read и Viewer ApprovalSurface в конце должны быть только совместимыми клиентами внешнего модуля либо явно выведены из эксплуатации — не вторым approval authority. Нельзя объявлять внешнее approval успешно из-за virtual-key browser tests.

**Критический gap existing pilot:** RDG approval_request сейчас требует исходному bearer graph.read + **graph.write** даже для pending request. Пользователь хочет иной режим: AI может **предложить** ASK без права самостоятельно выполнить write; после независимого Approve записывает исключительно trusted executor через отдельный grant, связывающий original initiator, approver и точный action. Нельзя сохранить старое graph.write requirement на propose или просто дать AI write для нового approval: прямой bypass сломает модель. Обязательный отрицательный тест: AI без graph.write может предложить разрешённый request, но не может apply сам.

**Ключевой сценарий владельца — hold → ask → forward:** AI вызывает зарегистрированный метод/endpoint (через Docker-сеть) с конкретным объектом/параметрами; Gateway проверяет ALLOW/ASK/DENY. Для ASK **сохраняет первоначальный точный запрос**, просит независимое согласие владельца, затем **сам продолжает этот запрос** к RDG/Sonar. AI не должен посылать второй mutating запрос с approved=true: он читает статус и результат. Внешние HTTP endpoints фиксируются route registry с policy/validators; для многокомандного API используется typed adapter, а не произвольный web proxy.

## 7. Полный план — обязательное чтение, не сводить к Sonar-only

**Основной документ:** [FORTIS-APPROVALS-SECURE-DEVELOPMENT.md](../../guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md). Он включает подробно:

- G0: реальную модель Docker/host, gateway privileges, bypass rights, Sonar/GitHub/Windows инвентаризацию.
- G1: независимый Action Gateway, typed operations, durable Approvals Core, ALLOW/ASK/DENY, audit, idempotency, stale/revoke/recovery.
- G2: owner Approval UI на отдельном origin/порту, переход к открытому R3 в RDG через Navigation Bridge, без полномочий write у browser link.
- G3: RDG adapter, штатные schema/preflight/apply, строгий запрет прямого AI write, testing locked/unlocked owners.
- G4: Sonar adapter — private read/Quality Gate/Issues, privileged Gateway credential, ASK Issue transitions и отдельные Hotspots, stale/readback.
- D1: AI working branch/PR и независимые GitHub Actions build/tests/SonarScanner, branch protection, отдельный owner review.
- D2: exact PR head/checkout/run/attempt/analysis/merge SHA, проверенный scanner coverage, skipped=not verified.
- D3: Windows separate clone, exact merged SHA import, AV/security staging, обязательный SHA/import admission; IMPORT_APPROVAL опционален по политике, **RUN_APPROVAL обязателен** для локального выполнения кода.
- D4: безопасный RDG CI/CD cutover с блокировкой старого Repo ZIP обхода; self-development Fortis/Gateway тем же PR путем.

**Приоритет исполнения:** после G0 параллельно A1 — минимальный Gateway и Sonar READ, B1 — первый PR/Actions/Sonar fix-loop; затем A2 — Approvals UI, B2 — exact-SHA отчет. RDG/Sonar writes G3/G4 не должны задерживать первый полноценный PR. Windows Importer D3 и cutover D4 объединяют оба контура.

**Четыре end-to-end acceptance:** (A) RDG R3 изменяется через отдельное approval с навигацией к R3 во вкладке; (B) Sonar Issue меняет статус только по approve; (C) AI PR проходит Actions/Sonar + owner merge; (D) exact final SHA импортируется в отдельную Windows clone после AV/SHA admission (ручной import approval опционален по политике), запускается только после обязательного owner RUN approval.

### Нельзя потерять в новом чате

- По желанию пользователя Gateway обладает **полными** полномочиями сервиса, но AI видит только allowlisted operations. Изоляцию проверять на admin boundary; broad token повышает риск компрометации.
- Sonar Windows CLI 'sonar auth status' ранее работал для приватного 'gd-cap', но новый контейнер требует отдельной авторизации; GitHub Actions scanner 'SONAR_TOKEN' — другая роль.
- 'gd-cap' Sonar проверяет Java часть, не весь Windows продукт; 'obs-planning-docs' JS ограничен paths filter. Sonar skipped/stale/не относящийся к SHA ≠ PASS.
- Sonar Issue ≠ GitHub Issue; Security Hotspots отдельные; изменения Issues могут изменить Quality Gate. Отчёт по PR не брать из main.
- Legacy 'fortis-security-reports' с Windows Collector и OBS hourly остаётся архивом/потоком до отдельного решения; PR #32/#33 не являются новым Gateway.
- Разные browser origins RDG и Approvals не могут напрямую общаться через BroadcastChannel; нужен owner-authenticated navigation channel / safe deep link. Переход к R3 не является approve.
- Owner UI/credential/public WebAuthn внутри изменяемого AI-приложения нельзя считать независимой доверенной авторизацией.
- Github merge SHA может отличаться от PR SHA; нужен final-SHA attestation или post-merge verification, иначе Windows importer нельзя считать безопасным. Если GitHub connector использует owner identity с admin/merge/bypass, branch protections могут не обеспечить независимый review: проверить actor/permissions и отделить их.
- Green Gate и Defender/AV — полезные проверки, **но не гарантия безопасности**; importer отдельно проверяет code/hooks/build scripts и требует owner RUN.
- Правки самого Fortis Approvals/Gateway не могут автоматически развёртываться из Fortis Repo — иначе AI изменит сам контроллер.

**Проверка границы: статус \`не подтвержден\` означает, что нужен свежий host readback, а не предположение по старому handoff.** Не делать никаких Windows/Docker admin изменений из недоверенного Repo. Текущий \`direct\` доступ AI к RDG Application writer через private gateway — потенциальный **bypass** будущих обязательных approval requests; G0 обязан подтвердить фактические grants и закрыть этот путь до включения ASK.

## 8. Первые действия нового чата

1. Прочитать AGENTS + нормативные docs и **весь Fortis plan**, а не только handoff.
2. Диагностировать Git worktree/HEAD/staged index (не менять), watcher/ready/status, live Docker ID по owner report, private gateway read-only.
3. Пройти по source/tests RDG approval pilot и составить таблицу **что переиспользовать / что оставить в RDG / чего не хватает для универсальной OS-boundary**.
4. Проверить **G0**: настоящий управляемый Fortis Repo Docker daemon/volumes и отдельную административную границу Gateway; доверенный Windows clone, GitHub branch protection, Sonar coverage; обозначить обнаруженные bypass.
5. Спроектировать минимальный typed Gateway API + policy + approvals + Navigation Bridge, независимые от RDG UI и GitHub Actions.
6. Прежде чем поднимать privileged Gateway или выдавать credentials — получить отдельный owner approval на инфраструктуру и безопасность; делать первичные synthetic tests. Из этого handoff разрешения на host изменения нет.
7. Реализовывать параллельно G1-minimal/G4-READ и D1/D2, затем G2/G3/G4-WRITE и D3/D4, документируя конкретные PASS/FAIL отдельно от планов. Первый read-only PR/Sonar fix-loop выполнить без ожидания полной интеграции write approvals.

## 9. Документация и осторожность

- 'docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md' — канонический **новый межпроектный** план, 'RDG-DEVELOPMENT-PLAN.md' — работа самого RDG; не превращать исторический handoff во второй план.
- 'RDG-CURRENT-STATE.md' — фактические проверки/ограничения; 'RDG-OPERATIONS.md' — подтверждённые команды и безопасные процедуры; 'RDG-ACTIVE-CONTRACT.md' — предметные правила.
- Исходный приложенный пользователем 'fortis-transition-record-legacy-to-sonar-gateway-2026-10-30(2).md' фиксирует переход от reporting к code-first; **новые уточнения** здесь и в Fortis plan добавляют универсальный Approvals Core, RDG adapter и Windows exact-SHA admission. Не переписывать оригинал будто Gateway уже создан.
- Документы регистрировать в 'docs/DOCS-POLICY.json' и прогонять 'tools/rdg-docs-audit.py'; прошлые handoffs immutable.
