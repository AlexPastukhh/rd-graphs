# RDG — полный handoff для продолжения в новом чате

> **СТАТУС: HANDOFF / СНИМОК НА 2026-10-21, НЕ НОВЫЙ НОРМАТИВНЫЙ КОНТРАКТ.**
> Репозиторий: `rd-graphs`; проверенная версия исходного Tampermonkey Viewer **2.4.8**. Это исходный код, **не доказательство установки** пользователем. Формальная **Stage 4 NOT ACCEPTED**. Не считать старые handoff, `Decision/Option` и эксперименты рабочей моделью.
>
> **Новый чат обязан прочитать:** `README.md` → `docs/guides/RDG-CURRENT-STATE.md` → `docs/guides/RDG-ACTIVE-CONTRACT.md` → `docs/guides/RDG-OPERATIONS.md`; затем специализированную инструкцию своей задачи. **При расхождении этого handoff с ними и кодом доверять действующим контрактам + проверенному источнику, а не handoff.**

## 0. С чего начать новый чат

Цель: **продолжить разработку и реальные проверки локальной системы RDG Requirements/Actions, Temporal Plan, Gendocen и Viewer**. Работа ведётся на русском языке. Вносить реальные правки и прогонять реальные тесты; не выдавать предложения или сгенерированные демонстрационные данные за принятые операции API. Не предполагать установленную у пользователя версию Viewer, административные полномочия, git commit/push или Stage 4 acceptance без доказательств. **Ждать конкретной следующей задачи пользователя**, не запускать разрушительные процессы ради «проверки».

Рабочая директория в подключённом **Fortis Repo** при проверке: `/workspace/repos/rd-graphs` (в инструментальном окружении может быть подключена как `/workspace/repo`; сначала `pwd` и `ls`). Если connector ещё не подключён, не утверждать, что доступ к репозиторию есть. В текущей среде **`.git` отсутствует** — `git status`, commit/push нельзя обещать как выполненные действия. Для большого изменения сначала краткий план, затем результаты по мере выполнения.

Стартовые **недеструктивные** проверки из корня проекта:

```bash
head -n 8 tools/rd-graph-viewer.user.js
python3 -B tools/rdg-docs-audit.py --check
node --test tests/rdg-documentation.test.cjs \
  tests/rdg-active-example.test.cjs tests/rdg-teaching-reset.test.cjs
python3 -B tests/rdg-node-type-policy.test.py -q
python3 -B tools/rdg-rebuild-teaching-example.py   # ТОЛЬКО список, БЕЗ --reset
```

## 1. Документация: единая структура и DRY

**Нормативная точка входа:** `docs/guides/RDG-CURRENT-STATE.md`. В ней ссылки на **один основной источник каждого правила**. Источники:

| Назначение | Чтение / проверяемый источник |
| --- | --- |
| Смысл модели R/A, права, типы, events, owners | `docs/guides/RDG-ACTIVE-CONTRACT.md`; код `tools/graph-apply.py`, `tools/rdg-graph-api.py`, `tools/rdg-v7-model.py` |
| Эксплуатация, авторизация, Helper, публикация, QA | `docs/guides/RDG-OPERATIONS.md` |
| Полный и локальный граф, навигация, Plan/Dependencies tabs | `docs/guides/VIEWER-EXPLORER.md` |
| Dependencies, receipts, `review_required`, live vs offline | `docs/guides/RDG-GENDOCEN-REQUIREMENT-DEPENDENCIES.md` |
| Единственный активный учебный пример и его исходное состояние | `docs/guides/RDG-LIVE-TEACHING-WORKSPACE.md` |
| Исключительный reset и ограничения дополнительных типов | `docs/guides/RDG-TEACHING-EXAMPLE-RESET.md` |
| Индекс и классификация документации | `docs/README.md`, `docs/DOCS-POLICY.json` |

Аудит `tools/rdg-docs-audit.py --check [--json]` **read-only**: сверяет version, Graph/Plan/publication SHA и историю, catalogue folder, типы блоков, ссылки и классификацию. На момент handoff: **PASS**, 247 Markdown (11 нормативных, 61 явно архивный, 175 неизменяемых snapshot), 349 локальных ссылок без проблем. `tests/rdg-documentation.test.cjs`: **5 PASS**. Другие исторические файлы могут содержать слова «актуально», номера 1.x/2.x, несуществующие команды и старый R/D/Decision. Не использовать их в качестве API-спецификации.

Архивы: `docs/guides/*-HISTORY.md`, старые `*PILOT*`, `*STAGE*`, `docs/examples/*`, `docs/2d/*`, `docs/handoffs/**`, `work-kit/`, `kit/`, `graphs/examples/`, `graphs/2d/`. Первичные `docs/handoffs/.../before*`, старые источники importable prompts и исходный `requirements-decisions-graph-examples-v0.2.source.md` **сохранены неизменными**, чтобы не переписывать доказательства. Этот файл — такой же **снимок**, не альтернативный текущий контракт. Изменения документировать в соответствующем нормативном файле, а не во всех исторических копиях; при изменении версии/схемы обновлять машинный аудит.

## 2. Активная модель, семантика и полномочия

**Только `candidate-v6`** в активном RDG. Базовые типы блоков:

- `requirement` (`R`) — цель и её критерии, активная/потенциальная R; введение R не равно достижению.
- `action` (`A`) — кандидат/выбранный способ; выбор A и запуск/исполнение A — разные события. Декомпозиционный Action может `INTRODUCES` дочерние R.

**Нет** второй активной модели `Decision/Option`; её файлы архивны. Не разрешать `kind` как свободную строку. Реестр `tools/rdg-node-type-registry.json` содержит базовые `requirement`,`action` и **опциональный** `context`, разрешённый только конкретному owner (`id`, `identitySpace`) при его явном `nodeTypeExtensions`. Не создавать `Context` для рабочего/учебного Graph лишь ради демонстрации UI. Регистрация расширения **не** предоставляет bearer/write permission.

Владельцы строго раздельны:

- **Graph owner** `graphs/workspaces/<slug>/graph.json`: реальные R/A, edges, `graph.events`, CAS `revision`.
- **Graph writer** `tools/graph-package.py`, `tools/graph-apply.py`, `tools/rdg-graph-api.py` и append-only accepted journals `graphs/workspaces/.transactions/*.json`. Только авторизованная запись (bearer/grants, transaction id, expectedRevision, trustedApproval где требуется); не править живой Graph JSON/журналы вручную.
- **Temporal Plan owner** `plans/<slug>/plan.json` и его отдельные версии placements; **не** создаёт новую R/A и **не** означает выполнение.
- **Gendocen project** `.rdg-gendocen-projects/<slug>/` и `tools/rdg-requirement-gendocen.py`: реальные baselines, differential review, receipts и history, **не** writer Graph/Plan.
- `graphs/index.json`, `tools/rd-graph-data.js`, `tools/rdg-published-owners.json`: **производные read-only** каталоги/снимки, не owners и не основание утверждать live completion.

**События**: `graph_saved` — технический успешный commit, `action_selected` — формально выбран A, `requirement_reformulated` — R с предыдущим и новым снимком, `action_executed` и `requirement_achieved` — **только по реальным самостоятельным доказательствам**. При выборе A в **одной** writer-транзакции появляется техническое сохранение и семантическое событие; Viewer объединяет их в **одну смысловую карточку**, техническая запись остаётся доступной внутри. Создание узла — отдельный writer commit, reader выводит `action_added`, `requirement_added` и т.п. `event.note` — свободная текстовая заметка с происхождением, не новый `type` и не удостоверение исполнения. Нет нужды придумывать событие `requirement_selected`: R вводится/активируется/изменяется, A выбирается.

## 3. Viewer 2.4.8 — действующее поведение

**Исходник** `tools/rd-graph-viewer.user.js`; части JS из `tools/rdg-workflow-ui.js`, `tools/rdg-catalog.js` в нём **встроены как GENERATED секции**. При изменении вынесенного источника обязательно синхронизировать его generated segment и проверить равенство; не ограничиваться правкой одного файла. Loader/данные устанавливаются в браузере пользователя **отдельно**. `tools/rd-graph-data.js` генерируется `tools/graph-index.py`, не хранить там ручные «события».

- В **полном** графе требования отображаются как навигационные **«ГРАФ R»**, с двойным контуром; это вход в локальный граф R, **не** файл Graph на каждую R. Только здесь переключатель **«Графы Requirements» / «Графы + Actions и каноны»**.
- В **локальном одноволновом R-графе** реальные R/Actions и **все** относящиеся к волне связи видны **сразу**. **Нет** переключателя «Основные / Все связи»; второстепенные связи различаются оформлением. Дочерняя R открывает свою локальную волну, breadcrumbs возвращают назад. Не подтягивать чужие Actions через общие контексты.
- «План во времени» читает настоящий отдельный Plan и историю принятых транзакций. Placement, selection, completion показывать по разным фактам, никакой выдуманной «успешной работы».
- «Зависимости» — только истинные Gendocen данные. **`review_required` значит требуется повторная проверка**, не «Action неправильный» и не «Action выполнен».
- При отсутствии Helper допустим только ранее **явно опубликованный исторический read-only** Plan/Gendocen snapshot, привязанный к реальному Graph owner/hash/revision. Он не является online refresh. При доступном авторизованном Helper live имеет приоритет. Ошибку отсутствия прав или файла нельзя превращать в пустой успешный Plan/0 зависимостей.

## 4. Точный текущий активный учебный пример (проверено кодом)

`requirements-dependencies-demo` **отображается в каталожной папке «Примеры»**, но **физически** canonical Graph `graphs/workspaces/requirements-dependencies-demo/graph.json` (Graph writer принимает `workspaces/*`), Plan `plans/requirements-dependencies-demo/plan.json`, движок `.rdg-gendocen-projects/requirements-dependencies-demo/`. Значение folder задаётся `graphs/catalog.json`, не создаёт другой owner.

**Graph `candidate-v6`, revision 10**, `identitySpace=rdg-working-requirements-dependencies-demo`, root `R0`, 8 узлов:

| R | A |
| --- | --- |
| `R0`, `R-CANON`, `R-VERIFY` | `A-DESIGN` (selected), `A-DESIGN-ALTERNATIVE` (candidate), `A-CANON` (selected), `A-CANON-ALT` (candidate), `A-VERIFY` (selected) |

Только **7** структурных edges типов `DRIVES`/`INTRODUCES`. **Нет** искусственного `C-ASSURANCE`, `CONTEXT_FOR`, `Context` и старой истории его создания/удаления. Graph содержит **4** семантических события: 3 `action_selected` + 1 `requirement_reformulated`; **10** принятых Graph writer транзакций от **новой сборки с нуля**, не старые журналы.

**Plan `temporalPlanOwner`, revision 4**: первоначально пустой Plan + 3 CAS-размещения `R-CANON`, `A-CANON`, `R-VERIFY`. `A-VERIFY` выбран, **не** размещён. Graph/Plan reader даёт **18** реальных provenance-записей, Viewer группирует их в **14** основных карточек. План и событие выбора A не являются записью фактического выполнения.

**Gendocen**: 7 dependency rows и три `review_required`: `A-CANON`, `A-CANON-ALT`, `A-VERIFY`. Причина — настоящая переформулировка `R-CANON` и сохранённые зависимости; это review, не доказательство ошибки или completion. Реальных `action_executed` и `requirement_achieved` в этом примере не создавалось.

**Опубликованный снимок** `tools/rdg-published-owners.json` проверен: Graph **r10**, Plan **r4**, история **18**, SHA256 владельцев совпадают с источниками, `tools/rd-graph-data.js` содержит тот же snapshot. Любая дальнейшая авторизованная правка может сделать опубликованный снимок **устаревшим** — обновлять его только после принятой операции и успешного реального engine readback, не использовать stale как текущий.

## 5. Исключительная пересборка **только** учебных примеров

Пользователь потребовал разрешить учебным графам из «Примеров» **полностью начинать с нуля**, а не архивировать искусственно добавленные блоки/события. Выполнено через `tools/rdg-rebuild-teaching-example.py` и allowlist `tools/rdg-resettable-examples.json` **только** для `requirements-dependencies-demo`; `tools/rdg-build-working-example.py` заново вызывает реальные Graph/Plan API, Gendocen и writer journals. Старый учебный Graph/Plan/engine history физически удаляется после успешного и проверенного rebuild.

Это **разрушительная** операция: допустима **только по явному запросу пользователя**, не при запуске тестов/проверке состояния. Нужны slug дважды, соответствие owner `id`/`identitySpace`/`purpose`, отдельного Plan, каталожной папки `examples`, собственных journals и отсутствие внешних зависимостей. Обычный рабочий Graph не имеет API для стирания истории. **Не выполнять параллельно с Helper / другим редактором**. Создаётся постоянная скрытая recovery backup `.rdg-example-reset-*`; после аварии резерв сохраняется и блокирует повтор до восстановления. Ранее обнаруженный дефект rollback исправлен: удалять разрешено только уже резервированные owners, не затрагивая чужие.

Единственная инструкция с destructive CLI: `docs/guides/RDG-TEACHING-EXAMPLE-RESET.md`; не дублировать её команду в новых документах. **Не запускать сброс просто ради проверки handoff.** Недеструктивный вызов `python3 -B tools/rdg-rebuild-teaching-example.py` только перечисляет разрешённые примеры. Текущая проверка показывает **нет** оставшихся `.rdg-example-reset-*` каталогов.

## 6. Запуск, публикация, тестирование

**Не размещать токены/секреты в репозитории.** Реальный Helper `tools/rdg-workflow-helper.py --manual-session` требует явных `RDG_AUTH_STORE`, `RDG_AUTH_TOKEN`, разрешённой локальной сессии и engine state. Точная команда и параметры живут **только в** `docs/guides/RDG-OPERATIONS.md`. Для записи нужны отдельные полномочия `graph.write`, `plan.edit` и проверка CAS. HTTP loopback и file-transport проверяются независимо. Встроенный браузерный тест **не доказывает** разрешения на компьютере пользователя.

После изменения настоящего Graph/Plan/Gendocen (только если это реально нужно):

```bash
python3 -B tools/rdg-publish-readonly-owners.py
python3 -B tools/graph-index.py
python3 -B tools/rdg-docs-audit.py --check
```

Публикация может занимать значительное время, потому что читает **настоящие** Gendocen receipt history; не повторять её на каждый незатронутый Viewer CSS/текстовый патч. Перед публикацией удостовериться в валидности новых owner refs и том, что нет незафиксированного Graph writer состояния. После публикации проверить SHA, актуальные `revision`, историю и что offline Viewer явно показывает историчность.

Основная **неразрушительная** регрессия:

```bash
node --test tests/rdg-documentation.test.cjs \
  tests/rdg-active-example.test.cjs tests/rdg-teaching-reset.test.cjs \
  tests/rdg-workflow-ui.test.cjs tests/rdg-catalog-sources.test.cjs
python3 -B tests/rdg-node-type-policy.test.py -q
python3 -B tests/rdg-deep-action.acceptance.test.py -q
python3 -B tests/rdg-workflow.acceptance.test.py -q
python3 -B tests/rdg-workflow-helper.test.py -q
python3 -B tests/rdg-temporal-plan-owner.test.py -q
python3 -B tests/rdg-requirement-gendocen.test.py -q
```

Изолированный Chromium при наличии настроенного `puppeteer-core` и headless-shell: `tests/visual/rdg-graph-scope.cjs`, `rdg-active-example.cjs`, `rdg-offline-published-owners.cjs`, `rdg-viewer-controls.cjs`, `rdg-workspace-plans.cjs`, `rdg-always-on-plan.cjs`. Настройка бинарника/библиотек — в среде проекта; не полагаться на выдуманный Chrome executable. Полная проверка может быть медленной. Отдельные browser tests проверяли file Plan, offline published Plan, helper file/loopback, мобильные controls и переходы волн.

Последние подтверждённые наборы:

- После обновления docs: **56 Node PASS, 3 SKIP, 0 FAIL** для пакета docs/Graph/Viewer/catalog; Python node-type policy **6 PASS**.
- Отдельная поздняя проверка handoff перед записью: **12 Node PASS** (`rdg-documentation`, `rdg-active-example`, `rdg-teaching-reset`), отсутствие остатков reset.
- Более широкий прогон до документационного рефакторинга: **69 Node PASS, 4 SKIP**, Python deep-action **26 PASS**, Helper **17 PASS**, Plan **18 PASS**, Gendocen **6 PASS**, workflow **14 PASS**, визуальные сценарии PASS. **Не переносить этот статус на новые правки без повторного запуска**.
- `rdg-docs-audit.py`: **PASS**, актуальные Markdown и owner checks. После добавления **этого** handoff immutable snapshot count на 1 больше; тест не должен трактовать handoff как нормативный документ.

## 7. Выполненная хронология и причины решений

1. **2.4.3**: публикация authentic read-only Graph/Plan/Gendocen snapshots для Viewer без Helper, с проверкой SHA и приоритетом живого авторизованного чтения.
2. **2.4.4**: различение технических Graph writer saves и семантических событий, группировка одной транзакции в истории; создание R/A не выдумывать как выбор/достижение.
3. **2.4.5**: «ГРАФ R» в полном обзоре отличается от обычной R локальной волны; запрещать путаницу «весь граф» vs «одна волна».
4. **2.4.6** (только исторический эпизод): ради показа переключателя был добавлен искусственный Context `C-ASSURANCE` с `CONTEXT_FOR`; пользователь справедливо отверг бессодержательный контекст и сам локальный переключатель.
5. **2.4.7–2.4.8**: локальный граф **всегда** показывает все отношения своей волны; локальный переключатель удалён. Полный граф сохраняет обзор/детали.
6. **2.4.8**: специальный allowlisted full teaching reset с реальным новым Graph/Plan/Gendocen и новой историей, без `C-ASSURANCE`. Базовые типы R/A закрыты, расширения scoped по owner.
7. **2.4.8 docs**: нормативные docs отделены от архивов, исходные handoffs/`before` сохранены без переписывания, старые Planning Helper prompts `work-kit/`/`kit/` помечены legacy. `docs/DOCS-POLICY.json` и `tools/rdg-docs-audit.py` валидируют структуру и DRY.

## 8. Нерешённое / что **не** обещать пользователю

- **Installed Viewer 2.4.8 не подтверждён**: пользователь мог всё ещё видеть старые версии в Tampermonkey, если не обновил и JS userscript, и `tools/rd-graph-data.js`; нет доказательства установки на Windows, user acceptance или независимого deployment.
- **Stage 4 NOT ACCEPTED**. Пройденные тесты исходников / Chromium ≠ бизнес-приёмка / проверка настоящего пользовательского окружения / работоспособность всех будущих Graph owners.
- **Нет подтверждённых фактов выполнения/достижения** в учебном Graph. `review_required` ≠ ошибка и ≠ правильность, Plan placement ≠ исполнение.
- **Нет `.git` в доступной копии**; не обещать commit, branch, PR, push.
- **Старые `Decision/Option` и Planning Helper imports не мигрированы** в новую модель; предложения миграции требуют отдельного решения и тестов.
- **Обычные Graph owner histories не очищать**. Дополнительные виды узлов не включать автоматически. Destructive teaching reset — только с явным разрешением пользователя и отдельным подходящим scope.
- **Следующая задача от пользователя пока не сформулирована.** После чтения handoff и текущих контрактов спросить, что именно продолжать, вместо самовольной реализации «следующего этапа».

## 9. Контрольная проверка перед новым изменением

1. `pwd`; убедиться, что это верный `rd-graphs` и файлы owners не подменены.
2. Прочитать текущие три normative документа; архивы только для истории, никаких API-операций по старой документации.
3. Сверить `@version` userscript, Graph `revision`, Plan `revision`, SHA snapshot и policy extras; если значения изменились — handoff устарел, не «исправлять» live owner под handoff.
4. Для конкретной задачи открыть **авторитетный source** (`tools/...`), сделать минимальный патч, выполнить подходящие regression tests, документационный audit и (если затронуты owner) publication.
5. Отчёт пользователю: что реально изменилось, какие tests прошли/не прошли, что **не** подтверждено, что нужно установить у пользователя. Не присваивать Stage 4 acceptance без явной приёмки.

---

### Короткий промпт для нового чата

> Продолжай проект **RDG** из подключённого репозитория `rd-graphs`. Сначала прочитай **`docs/handoffs/rdg-continuation-20261021/HANDOFF.md`**, затем обязательные действующие `README.md`, `docs/guides/RDG-CURRENT-STATE.md`, `RDG-ACTIVE-CONTRACT.md`, `RDG-OPERATIONS.md`. Не используй старые handoff/pilot/Decision/Option как актуальную модель. Проверь `tools/rd-graph-viewer.user.js` и owners на диске. Активная модель — `candidate-v6` (R/A), Viewer source 2.4.8, учебный пример в «Примерах» и reset только allowlisted. Не выдумывай события completion, grants, UI installation и Stage 4 acceptance; не выполняй destructive reset. После проверки скажи кратко, что готов продолжать и какие текущие ограничения подтверждены. Следующую задачу я дам отдельно.
