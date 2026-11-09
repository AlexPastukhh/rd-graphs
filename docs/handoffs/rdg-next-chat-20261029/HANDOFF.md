# RDG — handoff новому чату: работающий private API и тестовый процесс

> **СТАТУС: АРХИВ — снимок передачи контекста.** Срез 2026-10-29, Asia/Bangkok. Создан по прямой просьбе пользователя. Это не новый контракт, второй план, commit или приёмка Stage 4. Актуальные факты впоследствии сверяются с кодом, API и действующими документами.

## С чего продолжать

Работаем над **rd-graphs через Fortis Repo**. Репозиторий: **`/workspace/repos/rd-graphs`**. На Fortis_M у пользователя уже работает отдельный RDG server, браузерный вход и private API gateway. Текущий Repo Docker подключён к gateway. ИИ уже создал настоящий тестовый процесс в серверном приложении через общий API, без получения bearer.

**Следующая работа:** продолжать матрицу **A1–A17** из единого плана на выделенных тестовых owners, добавлять реальные evidence и фиксировать результаты. Первые пути API проверены, но полная матрица не пройдена. Ручная проверка этого процесса в Viewer и restart/readback живого сервера ещё впереди. Независимые API-проверки можно выполнять, пока пользователь проверяет UI.

Не начинай повторную реализацию D1/D2, установку gateway или создание seed с нуля. Не возвращайся к handoff 2026-10-28 как к текущей очереди. Пользователь ранее попросил пройти D1–D9 до технического end-to-end, затем исправлять конкретные недостатки. Такой runtime-срез реализован и проверен изолированно; **полный D7 UX и Stage 4 не приняты**.

## Источники и порядок входа

Сначала проверь `git status --short`, `AGENTS.md` и фактический путь проекта. Затем:

1. Этот handoff: `docs/handoffs/rdg-next-chat-20261029/HANDOFF.md`.
2. [Текущее состояние](../../guides/RDG-CURRENT-STATE.md).
3. [Единый план](../../guides/RDG-DEVELOPMENT-PLAN.md), особенно раздел «Сквозная проверка через API и граница доступа ИИ — 2026-10-29» и матрица A0–A17.
4. [Принятый пользовательский контракт](../../guides/RDG-ACTIVE-CONTRACT.md).
5. [Decision v1: технический контракт](../../guides/RDG-DECISION-V1-CONTRACT.md).
6. Применимые разделы [операционного регламента](../../guides/RDG-OPERATIONS.md) и [фундаментальных линз](../../guides/RDG-LENSES.md).

Старые строки о минимальных D1/D2, выключенных capabilities и ожидающейся установке в нижних хронологических срезах не описывают этот работающий сервер. Реальные формы запросов запрашивай у его `schema`. Реестр действующих документов: `docs/DOCS-POLICY.json`; обычный `rg` исключает handoffs через `.ignore`, но по явному пути они доступны.

## Ограничения пользователя

- Вне Docker настройку выполняет **сам пользователь** по командам PowerShell/файлам. Не использовать Host/G2/Tunnel connectors для Windows/host setup и не перезапускать общий Tunnel.
- Не передавать bearer в чат, tool arguments, env или файлы рабочего Docker. Не читать ключи gateway/оператора. Нельзя строить изоляцию на обещании ИИ не выводить ключ.
- Не выполнять `git reset`, `git clean`, массовую уборку, commit или push без отдельного разрешения. Рабочее дерево сильно изменено чужой и незавершённой работой.
- Не менять рабочие процессы пользователя, реальные grants, supplied lens definitions или owners старых примеров. Разрешены дальнейшие проверки выделенного тестового процесса и необходимые новые тестовые owners через штатный API.
- Destructive/crash/revoke испытания проводить на отдельной изолированной test server копии. Живой сервер не останавливать и его grants не отзывать ради теста. Миграция требует отдельного synthetic opt-in.
- Пользователь предпочитает прямое скачивание ZIP из чата. Git-backed исходники не дублировать в Library. Новая сборка нужна при изменении runtime; изменение Docker source само по себе не обновляет установленный сервер.
- Не считать backend PASS доказательством Viewer UX или пользовательской приёмкой. В handoff не дано нового разрешения на host-действия.

## Что важно в предметной модели и UI

**Process Graph — весь процесс** с общими сущностями, Plan и History. **Working Graph — явно созданная рабочая область по ссылкам на блоки процесса.** Области пересекаются по тем же IDs; это не копии и не отдельные процессы. Фокус, вкладка и camera — виды.

Requirement задаёт требуемую истинность. Decision — способ/вариант; его выбор не означает completion. Graph Action — конкретное действие с identity; внешний Action существует в процессе вне Graph. Планирование не исполняет Action; завершение Decision не объявляет автоматически достижение R. Completion требует действительных оснований/evidence и свежих pins.

Группы имеют независимые `selectionRequired`/`mutuallyExclusive`. Фильтр показа исключённых альтернатив меняет только вид. D→D запрещён. Первая WG нового процесса не создаётся автоматически; добавление в полный Process не включает блок в первую WG без явно указанной области.

Пользователь отклонил прежний экран «Graph · пакеты» и несоответствие визуальному прототипу. Сейчас вход — **полноэкранный Explorer**, пока граф не выбран; процессы содержат вложенные WG. Закрытие последней вкладки возвращает Explorer. Пакеты/линзы — отдельное представление. Старый экран с «Подключение…» и неработающими кнопками не является принятой UX-нормой.

Убраны лишние catalog/recommendation/read/history при открытии панелей и фокусе; изолированный desktop suite 12/12, тестовый focus 224 ms. Это не замер задержки Windows. Исходный прототип: `tests/visual/rdg-ui-prototype.html`; актуальные UI sources и generated bundle проверять по реальному коду, не создавать второй предметный JS-state.

## Среда и действующее соединение

Fortis Repo — удалённая среда разработки Linux, не локальный scratch ChatGPT. Нужны инструменты **Fortis Repo**. Указанный репозиторий доступен в `/workspace/repos/rd-graphs`; рабочие результаты — `/workspace/repo/Workfiles`. `/workspace/repos` и `/workspace/repo` имеют разное назначение. Windows-каталоги не считать автоматически смонтированными.

В Repo: UID/GID 1000, Python 3.11.2, Node 22.23.3, лимит памяти около 1 GiB. Docker CLI/socket в рабочий контейнер не передаются; Chromium suites запускать по одной. Есть подготовленные зависимости и браузерный wrapper, не устанавливай их заново без причины.

Фактический допущенный контейнер на момент передачи: **`7b8c66352643`**, compose group **`fortis-flattened`**. Полный backing ID: `7b8c663526432cba1db33388c3de01d1f29b61af92cac4fb7650ec3255cc6225`.

**Hostname/MCP metadata `c6d7be9fe6eb` устарели и не равны Docker ID.** Пользователь проверил этот старый контейнер: `Running=false`, `Privileged=false`, `PidMode=""`. Рабочий ID подтверждён Docker Desktop и шестью mountinfo entries `/etc/hostname`, `/etc/hosts`, `/etc/resolv.conf`. Не запускать старый контейнер и не обходить admission guards. При пересоздании Docker актуальный ID заново подтверждает пользователь; перенос подключения выполняется launcher, без передачи ключа.

### Серверная топология

| Сущность | Назначение и граница |
| --- | --- |
| Compose project `rdg-personal` | Отдельное приложение на Fortis_M |
| `rdg` | Прежние Application/Authority/FileStore/coordinator, без host port, internal backend |
| `proxy` (Caddy) | Browser вход `http://localhost:18880`, publish только `127.0.0.1:18880:8080`, backend + edge |
| `rdg-api-gateway` | Private `http://rdg-api-gateway:8081`, backend + agents; host ports отсутствуют |
| `rdg-personal_agents` | Private internal network с gateway и явно допущенным Repo Docker |
| `rdg-personal_rdg_data` | Существующие данные приложения; не удалять и не монтировать в рабочий Docker |
| `rdg-personal_rdg_gateway_secret` | Только assistant credential + namespace; setup пишет, gateway читает RO, UID 10001, 0700/0600 |

Gateway не получает owner/browser credential, app data volume или Docker socket. Он добавляет scoped assistant bearer к фиксированному upstream `http://rdg:8080`. Публичный Caddy закрывает `/api` и `/api/*`; пользователь работает через Basic + `/session/*` с Origin/CSRF.

Права предоставлены **контейнеру, не конкретной модели/чату**: любой процесс допущенного рабочего контейнера имеет тот же API-доступ. Docker/Windows admin доверенный. Отсутствие ключа у ИИ не уменьшает автоматически выданные API-права; сохраняются scopes, отзыв, guards, attribution и журнал.

Предметные команды Viewer и ИИ проходят через один Application/writer. API не даёт shell, Windows filesystem или произвольный URL proxy. Чужая browser `view_session` actor-owned; действовать от имени пользователя и создавать human proof из JSON нельзя.

### Несекретный клиентский context

Уже существует **`/workspace/repo/Workfiles/rdg-gateway-context.json`**:

```json
{
  "profile": "gateway",
  "origin": "http://rdg-api-gateway:8081",
  "namespaceId": "fd3777f9-5aec-44a0-82d6-36d0c526b847"
}
```

`tokenFile` для этого профиля запрещён. `rdg-remote-client.Client.token is None`; Authorization из рабочего Docker не отправляется. Ключ не получался ИИ. Если context/network недоступны после пересоздания среды, диагностировать соединение и дать пользователю точную команду launcher, а не просить прислать ключ.

Первые безопасные команды в Repo:

```sh
cd /workspace/repos/rd-graphs
git status --short
python3 -B tools/rdg-agent.py doctor --context /workspace/repo/Workfiles/rdg-gateway-context.json
python3 -B tools/rdg-agent.py catalog --context /workspace/repo/Workfiles/rdg-gateway-context.json
python3 -B tools/rdg-remote-client.py --context /workspace/repo/Workfiles/rdg-gateway-context.json <<'JSON'
{"method":"read","packageId":"5ac9f3ec-2783-5b7e-802d-1b3518bbc371","includePlan":true}
JSON
```

После API-изменений пользователь нажимает **«Обновить» в Explorer** на `http://localhost:18880`, открывает процесс и Plan. Нет автоматического управления его вкладкой или гарантии немедленного push-обновления.

## Уже созданный тестовый процесс — не создавать заново

| Поле | Значение на передаче |
| --- | --- |
| Название | **RDG — сквозная проверка API** |
| Namespace | `fd3777f9-5aec-44a0-82d6-36d0c526b847` |
| packageId | **`5ac9f3ec-2783-5b7e-802d-1b3518bbc371`** |
| Path | `api-tests/rdg-acceptance-20261029` |
| Role / profile | `working` / `rdg-decision-v1` |
| Graph | revision **33**, **25** Graph-блоков |
| Plan | revision **19**, **18** order-only placements, timeConstraints `[]` |
| Layout | revision **1**, **25** сохранённых позиций |
| Task Actions | **A0–A17**, все **18 открыты** |
| Снимок Graph/Plan/layout SHA256 | `8ab95832c27d6a47521a2e900b9e5fd2c1fd57457f27a608517fd05762e86376` |

Перед записью handoff выполнено новое read-only чтение живого API: ревизии и SHA256 совпали с seed. Это снимок, не постоянный CAS для будущих изменений; новые expected revisions брать из свежей schema/read.

R1 — общая цель. D1 «Вести проверку в отдельном тестовом процессе» выбран; D2 «Проверять одноразовыми сценариями без общего графа» — не выбран. В exclusive G1 D2 может быть скрыт обычным view filter. D1 вводит R2–R5; конкретные Actions связаны с разделами `REQUIRES_ACTION`.

| Working Graph | Requirement | Общие блоки и пересечение |
| --- | --- | --- |
| WG1 «API и модель» | R2 | R1/D1; A1–A5, A13 |
| WG2 «Viewer и Plan» | R3 | R1/D1; A5–A9, A17 |
| WG3 «Пакеты и линзы» | R4 | R1/D1; A10–A14 |
| WG4 «Надёжность» | R5 | R1/D1; A0, A15–A17 |

A5, A13, A17 имеют общие identities в двух областях. WG возвращают тот же Process Graph, Plan и canonical layout key. Все Graph events при seed атрибутированы assistant. Автоматические low-level operation records — факты выполненных add/review/etc.; они не означают завершения task Actions A0–A17.

Первое создание Decision-процесса штатно установило **11 fundamental lens packages** этого профиля. Каталог теперь содержит тестовый процесс и эти линзы (12 packages). Supplied definitions не редактировались. Линзы искать свежим catalog по lensKey; чтение инструкции не считать `lens_apply`.

### Seed и журнал

- Исходная opt-in фикстура: **`tests/rdg-api-acceptance-seed.py`**. Использует только HTTP client и общий API, не читает owner files/credentials.
- Журнал точных requests/inputBinding/result/receipt: **`/workspace/repo/Workfiles/rdg-api-acceptance-20261029.json`**.
- Перед отправкой записываются request и binding с fsync. Возобновление использует прежние intents; журнал нельзя удалять ради повтора.
- Seed создаёт план проверки, **не выполняет всю матрицу**. Полный критерий принадлежит единому плану, не этой фикстуре.
- Повторный seed уже проверен: Graph/Plan/layout/package не изменились, второй процесс не появился.
- После последующих ручных/API изменений начальные assertions фикстуры (включая 0 complete) могут перестать соответствовать данным. Это не повод пересоздавать процесс или сбрасывать его. Продолжать через обычные API-команды.

В первом запросе `plan_create` сама фикстура добавила лишний `note`; сервер правильно вернул `PORTABLE_APP_PLAN_CREATE_FIELDS` до acceptance, Plan оставался отсутствующим. Исправлен только builder фикстуры: заполнять note, если он есть в schema. Отклонённый request сохранён в журнале; исправленный request имеет новый transactionId. Не «чинить» сервер ослаблением закрытых полей.

## Что фактически проверено

### На пользовательском Docker/Windows и живом API

Пользователь дважды успешно выполнил `Start-RDG.ps1 -Mode Local -AgentContainer 7b8c66352643`. Оба запуска вернули:

```text
Unrelated container isolation check: OK
Private API check: OK; client context contains no credential
Windows HTTP check: OK
Browser ingress machine API check: blocked
```

Setup сохранил namespace (`alreadyInitialized:true`), gateway healthy. Негативная TCP probe была отдельным посторонним контейнером на edge network. Из Repo отдельно проверены gateway health 200 с совпадающим namespace, browser ingress health 200, machine API 404 и browser login 401.

Для seed получены **53 успешных schema/preflight/apply/receipt**. Наблюдаемые catalog/Graph/Plan/layout до и после каждого preflight совпали; это не утверждение о побайтной проверке скрытой server metadata. Проверены отсутствие неявной WG/Plan после create, явные memberships и общие owners, создание Plan без дат, сохранение позиций, новый клиентский процесс и шесть exact retries: create, work_graph, select, plan_create, place, layout_edit. Повторы не изменили owners. **Новый клиентский процесс не является перезапуском сервера.**

Это начальные пути A0 и части A1/A2/A3/A5/A7/A9. Не отмечать всю матрицу пройденной и не завершать Actions по факту seed.

### Изолированные regression/browser suites до установки

| Проверка | Результат | Evidence в `/workspace/repo/Workfiles` |
| --- | --- | --- |
| Gateway HTTP, namespace/headers, revoke, uncertain result, actual tokenless Agent CLI, setup upgrade | **8/8** | `rdg-gateway-unit-final2.log` |
| Server regression | **7/7** | `rdg-gateway-server-regression.log` |
| Legacy Agent | **14/14** | `rdg-gateway-agent-regression.log` |
| Extracted runtime + настоящий Caddy/Gunicorn/gateway + generated Viewer | **7/7** | `rdg-gateway-browser-final.log`, `rdg-server-browser-V43an0/` |
| Документация перед handoff | **6/6** | `rdg-gateway-live-docs-final.log` |
| Git integrity после сбоя диска | `git fsck --full` exit 0 | `rdg-gateway-git-fsck.log` |

Browser 7/7 проверял общий Graph через browser/private API, Plan/drag и новый PID backend/gateway с clean-browser readback на временных owners. Runtime итогового архива совпадает с проверенным candidate2; после него изменён только admission explicit private PID mode в launcher + manifest. Эти тесты не доказывают UX живого пользовательского процесса, public HTTPS или Stage 4.

### Дополнительные evidence

- `rdg-gateway-operator-20261029.log` — присланный пользователем успешный host log; 11943 bytes, SHA256 `7a46126c878e7153b687a6e3cc14e8c760f749469462e1f95306b730c2dfc07d`.
- `rdg-gateway-live-access-20261029.json` — отдельные текущие health/auth/ingress проверки.
- `rdg-api-acceptance-readback-20261029.log` — итоговый seed report и шесть retry видов.
- `rdg-api-acceptance-resume-check-20261029.log` — повторный seed; внешний harness сравнил package/Graph/Plan/layout до и после.
- `rdg-api-acceptance-seed-20261029.log` — первый seed, включая исправленный впоследствии отказ лишнему полю.
- `rdg-api-acceptance-seed-resume-20261029.log` — продолжение после исправления фикстуры.

## Следующий конкретный проход

1. Read-only doctor/catalog/read; проверить доступ и фактическое состояние существующего тестового процесса. Не использовать сохранённые ревизии из таблицы вместо свежих.
2. Продолжать **A1–A17 по действующему плану**, не создавать новую параллельную матрицу. Ближайшие API-сценарии: оставшиеся add/edit/link/unlink и objects; негативные схемы и CAS; группа/выбор/withdraw/root causes; реальный evidence → complete/reopen/review/history. destructive примеры отделять в новые тестовые owners, сохраняя основной план обозримым.
3. Каждый новый logical operation получает новый transactionId из schema. Заполнить реальные данные → preflight → apply **того же request** с `expectedInputBinding` → receipt → readback. После uncertain outcome сохранить intent и проверить receipt/recovery/exact retry; не выдавать новую транзакцию наугад.
4. Для `core` schema передаётся `command`; actual `data` заполняется осознанно. Для connected add явно задать entity/location/initialRelations/workGraphId; не наследовать случайно предлагаемые schema область или связь. `plan_create` и `plan_edit` не принимают универсальный note. Не менять actor/authority fields.
5. Статусы A0–A17 менять только по фактически выполненному сценарию, с реальными evidence bytes/pins и достаточным scope. Показанные блоки и импорт линз не являются доказательством применения/достижения.
6. Вручную в Viewer пользователь проверяет процесс, вложенные WG, пересечения, Plan и drag/layout; поправки сверяются с принятой семантикой и прототипом. Без его отзыва не объявлять UX принятой.
7. Restart живого сервера выполняет пользователь; после подтверждения нового PID проверить те же owners/план/layout. Crash injection и revoke — изолированный test server. Пока этого нет, A16/A17 не закрывать целиком.
8. После изменений обновлять действующие документы, выполнять подходящие API/browser tests, `node --test tests/rdg-documentation.test.cjs` и `git diff --check`; не повторять все suites без основания.

Native human approval на текущем сервере **не настроен**: lock-set/remove требуют `VERIFIED_APPROVAL_REQUIRED`. Пароль браузера, JSON actor и grant не заменяют human proof. Public DNS/HTTPS также не настроен и не проверен; сейчас Local mode на Fortis_M. Эти ограничения фиксировать как ожидаемые/открытые, не обходить.

## Код, который продолжать

- Предметная модель: `tools/rdg-decision-model.py`; profile dispatch `tools/rdg-model-profiles.py`; legacy `tools/rdg-core-model.py` сохраняет свою R/A-семантику.
- Общий Application и координатор: `tools/rdg-portable-service.py`, `rdg-portable-model.py`, `rdg-portable-store.py`, Authority и существующий transaction IO. **Второй writer, registry или доменную модель не создавать.**
- Host: `tools/rdg-server.py`, `rdg_server_entry.py`, `rdg-server-setup.py`.
- Gateway: `tools/rdg-gateway.py`, `rdg_gateway_entry.py`; transport `tools/rdg-remote-client.py`; Agent `tools/rdg-agent.py` понимает gateway profile.
- Deployment: `deploy/rdg-server/` — base/local/https Compose, Caddyfiles, Dockerfile, PowerShell launcher.
- UI: `tools/rdg-decision-ui.js`, `rdg-portable-ui.js`, общий projector `rdg-visual-projection.js`, layout codec; source → `tools/build-rdg-layout.py` → generated `tools/rd-graph-viewer.user.js`. Проверять parity при изменении UI.
- Tests: `tests/rdg-gateway.test.py`, `rdg-server.test.py`, `rdg-decision-integration.test.py`, `rdg-decision-system.test.py`, `tests/visual/rdg-server.cjs`, desktop/prototype suites; новая opt-in seed fixture выше.

## Сборка, предыдущие ошибки и сохранность

Установлена **`RDG-Server-20261029-gateway1.zip`**. Канонический артефакт в `/workspace/repo/Workfiles/`, **414798 bytes**, SHA256 `c0e6d461257d6790d3381cfe519a221b5cabdcaf6cdcb8855c6acdf455198e1c`, 63 файла без пользовательских данных/ключей.

Windows code directory: `C:\Users\alexa\AppData\Local\RDG-Server\build-20261029-gateway1\RDG-Server`. Операторские secrets хранятся отдельно, прежний browser login/password сохраняется. Пользователь входит как `rdg`; пароль читает сам, в чат его не присылает.

До gateway1 были исправлены три независимые проблемы:

- Backend с published port только на internal network был healthy внутри, но Windows получал connection refused. Теперь Local ingress — отдельный Caddy на edge + backend.
- Caddy image с file capability при `cap_drop: ALL` выдавал `exec /usr/bin/caddy: operation not permitted`. Добавлен только `cap_add: NET_BIND_SERVICE`; остальные ограничения сохранены. Не убирать capability при случайной «чистке» Compose.
- В admission передали старый hostname как ID остановленного контейнера. Правильный 7b ID решил этот отказ; guards не ослаблялись.

Windows-диск переполнился во время разработки: EROFS/EIO, позднее spawn EIO. Пользователь освободил место, перезапустил Docker и Fortis Repo. После восстановления проверены create/write/fsync/readback/delete собственных temp files в repo/Workfiles, HEAD/index, `git fsck --full`, 47 прежних runtime files с прежней сборкой, live health. Не обещать универсальную сохранность всех незавершённых writes. WIP checkpoint и candidate ZIP не являются установочным актуальным пакетом.

HEAD при передаче: **`176ce44c820757ecfb827ea881c0cac6613c8831`**. Есть 31 ранее staged путь и много unstaged/untracked чужих изменений; значительная часть текущей реализации тоже ещё не committed. Guard **`/workspace/repo/Workfiles/rdg-server-guard.json`** содержит head и `indexSHA256` от `git diff --cached --binary`; при подготовке handoff оба совпали. Не stage/commit чужую работу и не очищать untracked fixtures/документы.

В последнем API-проходе добавлена seed fixture и актуализированы README/current state/development plan/operations. Модель, writer и установленный runtime в этом проходе не менялись. При подготовке этого handoff выполнялось только read-only API-чтение; Graph/Plan не изменялись.

## Стартовое сообщение для нового чата

```text
Продолжаем rd-graphs через Fortis Repo. Репозиторий: /workspace/repos/rd-graphs.

Сначала проверь git status --short и AGENTS.md, затем прочитай:
1. docs/handoffs/rdg-next-chat-20261029/HANDOFF.md
2. docs/guides/RDG-CURRENT-STATE.md
3. docs/guides/RDG-DEVELOPMENT-PLAN.md
4. docs/guides/RDG-ACTIVE-CONTRACT.md
5. docs/guides/RDG-DECISION-V1-CONTRACT.md

Gateway уже установлен и работает. Несекретный API context:
/workspace/repo/Workfiles/rdg-gateway-context.json
Тестовый процесс уже существует: 5ac9f3ec-2783-5b7e-802d-1b3518bbc371,
«RDG — сквозная проверка API», четыре WG, Plan A0–A17.

Продолжай матрицу API-проверок на тестовых owners с реальными evidence,
параллельно учитывай ручную проверку Viewer. Seed не повторять с нуля,
D1/D2 не реализовывать повторно, backend PASS не считать UX acceptance.
Без reset/clean/commit/push, изменений рабочих owners/grants и передачи ключа.
Host/Windows действия выполняю я по командам; Host/G2/Tunnel не использовать.
Сначала сверяй живой API и предложи следующий конкретный проход по коду.
```
