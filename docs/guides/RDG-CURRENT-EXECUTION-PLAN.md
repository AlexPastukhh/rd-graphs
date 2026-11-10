> **СТАТУС: АРХИВ / ИСТОРИЧЕСКАЯ РАЗРАБОТКА — НЕ ДЕЙСТВУЮЩИЙ КОНТРАКТ.** Включая файлы с именами `CONTRACT`, `PLAN`, `STAGE`, `PILOT` и со словом «актуальный» в тексте. Новый чат должен использовать [единую текущую спецификацию](RDG-CURRENT-STATE.md); ниже сохранены прежние эксперименты, решения и протоколы.

# RDG + Temporal Plan — журнал исполнения по версиям

**Читать как хронику, а не как текущую инструкцию:** для действующего состояния Viewer 2.4.8, Graph/Plan/Gendocen и учебного примера используйте [карту актуальной документации](RDG-CURRENT-STATE.md). На этой странице каждый предыдущий этап оставлен в первоначальных формулировках, включая временные механизмы, которые позднее отменены.

## Полная пересборка учебного примера и закрытый набор типов — source Viewer 2.4.8 (2026-10-21)

Последующее решение пользователя отменяет промежуточную демонстрацию `C-ASSURANCE` (2.4.6): во всех локальных графах R показаны все связи одной волны, а искусственный контекст ради кнопки не нужен. Для **специально зарегистрированного учебного** Graph вместо архивирования прежних блоков применяется **полный reset и новая сборка через реальные авторизованные API**, что удаляет Graph/Plan/Gendocen историю прежнего экземпляра. Обычный рабочий Graph такой операции не имеет. Реестр `tools/rdg-resettable-examples.json` и точное подтверждение slug связывают reset с единственным учебным owner. В Viewer он находится в папке **«Примеры»**; из-за writer API физическая каноническая ссылка остаётся в `workspaces/requirements-dependencies-demo/graph.json`. Новый Graph r10, 8 R/Action блоков, 10 Graph API транзакций, Plan r4, 18 первичных записей (14 карточек) и настоящие Gendocen reviews. Старые журналы о `C-ASSURANCE`, старые Plan/engine receipts удалены, а не показаны как новые события. Отдельный `tests/rdg-node-type-policy.test.py` проверяет, что `candidate-v6` принимает только `requirement`, `action`; дополнительные `context` требуют owner-level grant и декларацию `nodeTypeExtensions`.

При пересборке промежуточный производный опубликованный snapshot не блокирует Graph API и не выдаётся за актуальные данные. Нельзя запускать reset одновременно с Helper. Если сброс прерывается, он восстанавливает только файлы, **уже находящиеся в резервной копии**, и не трогает неуспевшие зарезервироваться оригиналы (исправлен ранее выявленный дефект отката). Исторические исходники старой модели в `graphs/examples/**` не переписываются. [Пошаговая процедура](RDG-TEACHING-EXAMPLE-RESET.md). Viewer source 2.4.8, пользовательская установка не подтверждена.

---

## Архивные этапы 2.4.6 и ранее — **не действующие инструкции**

Следующие разделы сохраняют доказательства прошлых реализаций, в том числе уже удалённый `C-ASSURANCE` и локальный переключатель связей. Проверенный текущий источник — 2.4.8; учебный Graph снова r10.

### Контекст ранее менял локальный граф — Viewer source 2.4.6 (2026-10-21)

**Баг, обнаруженный пользователем:** в активном учебном Graph вообще не было ни одного дополнительного отношения `CONTEXT_FOR`, `APPLIES_TO` и т. п.; семь связей `DRIVES`/`INTRODUCES` были базовыми. Поэтому оба значения переключателя локального графа действительно показывали одно и то же. Это противоречило смыслу демонстрации.

**Реальный API fix:** `tools/rdg-extend-teaching-context.py` через bearer + signed local manual session последовательно принял четыре CAS Graph writer транзакции с note: `create_context C-ASSURANCE`, затем три `add_edge CONTEXT_FOR` к `A-DESIGN`, `A-CANON`, `A-VERIFY`. Рабочий Graph r10→r14, Plan owner всё ещё r4, Gendocen real refresh без фиктивных `action_executed`/`requirement_achieved`. Reader истории определяет `context_added` и `context_link_added` из before/after. Публикация real API event history + Gendocen обновлена: **22 факта provenance → 18 основных карточек**, живых dependency targets 7 с тремя `review_required`.

**UI fix:** `localLevelSource` раньше транзитивно расширял локальную волну через общий Context и незаметно подтягивал чужие Actions. Теперь дополнительные узлы включаются **одним шагом** от структурной волны. `edges-mode=core` сохраняет только основной путь, `all` добавляет реальный `C-ASSURANCE` и одну релевантную `CONTEXT_FOR` стрелку. В селекторе локальной волны показывается **«Все связи и контекст (+1)»**, чтобы было видно, что переключение что-то откроет. Проверено отдельно на `R0`, `R-CANON` и `R-VERIFY`: context arcs соответственно `→ A-DESIGN`, `→ A-CANON`, `→ A-VERIFY`; не происходит вытекания соседних Actions. **Offline owner cache** теперь не может блокировать новые авторизованные записи: stale snapshot не поставляется в bundle до явного refresh, с неизменными protections и bearer.

**QA:** `tests/visual/rdg-graph-scope.cjs` проверяет DOM пути, группы связей, реальное появление Context и трёх arrows, исчезновение в core, scope isolation и pageerrors=0. `tests/rdg-active-example.test.cjs` проверяет сохранённые Graph writer receipts и snapshot parity; `tests/visual/rdg-active-example.cjs` и `rdg-offline-published-owners.cjs` проверяют историю/Plan/Gendocen live+offline. Source 2.4.6, установленный Viewer 2.4.6 не подтверждён. [Подробности](RDG-LIVE-TEACHING-WORKSPACE.md).

---

## Графы Requirements в общем обзоре и обычные R в локальном графе — source Viewer 2.4.5 (2026-10-21)

**Запрос:** перестать смешивать R-блок как отдельное объявление цели и R-блок в полном графе, который фактически является **входом в граф этой R**; убрать двусмысленность «только Requirements» у ограниченного одной волной локального графа.

**Реализация:** в полном режиме у каждой R отдельное визуальное оформление **`requirement-graph`** (двойная рамка, `ГРАФ R · корень/текущий/возможный`, явный role/aria/title и пояснение масштаба). Исходный `kind=requirement` **не меняется** и не создаётся фиктивный Graph owner для каждого узла. По нажатию используется существующий `openFullRequirement` для перехода к реальному локальному одноволновому графу R (может быть slice исходного owner, а не собственный файл). В локальном режиме возвращаются обычные `R · id` с одинарной рамкой и все реальные `Action`/каноны, а выбор `edges-mode=core|all` там **меняет только перечень показываемых отношений**, а не исключает Actions. UI локального переключателя теперь назван «Основные связи / Все связи и контекст», полный переключатель — «Графы Requirements / Графы + Actions и каноны». На обоих уровнях выводится пояснение текущего масштаба, breadcrumbs сохранены. Обновление не затрагивает Graph writer, Temporal Plan, Gendocen, события истории и критерии достижения.

**QA:** Chromium `tests/visual/rdg-graph-scope.cjs` открывает настоящий full `requirements-dependencies-demo`, проверяет три граф-блока `R0/R-CANON/R-VERIFY`, detail с Actions, навигацию full → one-wave `R-CANON`, обе настройки связей с двумя Actions, возврат в full, локальный `R0` → дочерняя R → локальный `R-CANON`. Ноль pageerrors; также проверены desktop/mobile controls, Plan/Dependencies и Node UI suite. Viewer source **2.4.5**, установленный пользовательский Viewer 2.4.5 не подтверждён.

---

## Семантика событий, подцели при выборе Action — source Viewer 2.4.4 (2026-10-21)

При реальном API авторинге три первых Graph writer транзакции учебного Graph различаются: создание рабочего Graph r1, добавление кандидата `A-DESIGN` r2 и добавление `A-DESIGN-ALTERNATIVE` r3. Старый Viewer показывал всем один технический тип `graph_saved`: «Изменён граф», несмотря на достоверный before/after в принятых журналах. Пользователь также заметил дублирование `graph_saved` и `action_selected` в истории и отсутствие явно показанных введённых подцелей.

**Реализация:** `rdg-activity.py` не меняет persisted `event.type`, а **дополняет** факт принятой транзакции `changeKind` (`graph_created`,`action_added`,`requirement_added`,`requirement_prepared`,`requirement_activated`,`requirement_deactivated`, отдельные удаления). Наличие общего `graph_changed` не превращает реальное создание R в generic change. Reader для `action_selected` вычисляет `introducedRequirements` **только из того же journal before/after**: новые R имеют `introductionMode=created`, существовавшие `potential/candidate`, ставшие `active`, — `activated`, ранее активные связанные — `linked`, с реальным `childRole` и Graph owner. Отсутствующий журнал не реконструируется из сегодняшних узлов. `rdg-workflow-ui.js` показывает эти R под карточкой выбора с переходами в Graph, различает event families и сливает однопарное техническое сохранение с содержательным событием в основную карточку; `transactionId`/revision/changed nodes скрыты только визуально в раскрывающемся блоке, а источник остаётся неизменным. На нынешнем учебном Graph это **18 первичных provenance записей, 14 видимых основных карточек**, без вымышленных `action_executed`/`requirement_achieved`. Отдельно создаваемая R **не** требует `requirement_selected`: её создание, подготовка/активация, планирование и достижение — независимые события.

**Evidence:** `tests/rdg-active-example.test.cjs` проверяет реальные журналы/подцели, `tests/rdg-deep-action.acceptance.test.py` отдельно проверяет самостоятельное `create_requirement` и активацию *подготовленных* R при `select_action`, `tests/rdg-workflow-ui.test.cjs` проверяет группировку технического события в одну карточку и переходы к введённым R, Chromium `tests/visual/rdg-active-example.cjs` проверяет 14 карточек, пять добавленных candidate Actions, раскрываемые технические данные и отсутствие page errors. Реальный Graph r10, Plan r4, Gendocen 7 receipts и все authorizations **без изменений**. [Подробности](RDG-LIVE-TEACHING-WORKSPACE.md). User-installed 2.4.4 пока не подтверждён.

---

## Исправление недоступных вкладок при реальном Viewer 2.4.2 — исходник 2.4.3 (2026-10-21)

Скриншоты установленного у пользователя **2.4.2** подтверждают два дефекта доставки: `PLAN_FILE_NOT_FOUND_OR_ACCESS_DENIED` при попытке локального file:// Plan owner, и `Выберите рабочий граф, который подключён к Helper` при открытии Gendocen. Владельцы реально существовали, но **браузер не мог обратиться к ним через одно лишь опубликованное содержимое Graph**. Исправление **source 2.4.3**: после явного opt-in слепка настоящих Graph/Plan owners + реального Gendocen и настоящего authorизованного Graph/Plan workflow reader, `graph-index.py` проверяет источники SHA256 и встраивает immutable read-only transport в `rd-graph-data.js`. Viewer использует его только при отсутствии live доступа и точном соответствии рабочего Graph r10 / identitySpace. История 18 реальных записей, три Plan placements, семь Gendocen dependency rows и семь engine histories доступны offline; статус Snapshot явно не является текущей валидацией. Без live grant редактирование запрещено. Ревизия Graph не совпадает → fail closed. Chromium offline-without-file/Helper, offline navigation, lazy engine history, stale-snapshot refusal: **PASS**. `tests/visual/rdg-always-on-plan.cjs` проверяет приоритет доступного локального owner. Последняя **установленная подтверждённая** версия — 2.4.2 по скриншотам; установленная 2.4.3/Stage4 не подтверждена. [Детали](RDG-LIVE-TEACHING-WORKSPACE.md).

---

## Рабочий учебный граф как обычный Graph owner — source Viewer 2.4.2 (2026-10-21)

**Запрос пользователя:** исторические события учебного графа должны быть результатом реальной последовательной работы через API, а не `workflowExample` или заранее нарисованных «выполнений»; старая модель `Decision/Option` не может оставаться активной. Примеру достаточно показать актуальные зависимости Gendocen и подлинный Plan/Graph history; не требуется иллюстрировать весь функционал RDG одним графом.

**Реализовано:** новый полный `candidate-v6` Graph owner `graphs/workspaces/requirements-dependencies-demo/graph.json` построен через `tools/rdg-build-working-example.py` с настоящими Graph writer-коммитами (r10, 8 R/Action узлов, 3 выбора Actions и `requirement_reformulated`). Его независимый `plans/requirements-dependencies-demo/plan.json` создан и обновлён через `rdg-temporal-plan-owner.py` (r4, три размещения). Реальные Gendocen receipts/accepted baselines/`review_required` живут отдельно: `.rdg-gendocen-projects/requirements-dependencies-demo` (7 receipts; три зависимых Action на пересмотр). **Нет событий `action_executed` или `requirement_achieved`, поскольку в ходе этой работы действия и цель действительно не завершались.**

**Единственная активная модель:** `tools/rdg-catalog.py` и `tools/graph-index.py` оставляют старые источники в архивном каталоге, но Viewer app и встраиваемый bundle экспортируют только неархивные `candidate-v6`; загрузка отдельного старого JSON блокируется. `graph-package.py` отклоняет write старой модели, auto-workspaces Helper не выбирает старые источники, старый LegacyPlanReader удалён. Исторические файлы физически не переписывались. Реальные Graph events (включая выбор), Graph writer journal и независимые версии Plan owner читаются единым workflow reader. Plan не меняет completion truth от размещения/выбора. При недоступном Helper вкладка Plan показывает только подлинные доступные file-источники с предупреждением о непроверенном полном журнале; Gendocen без Helper — недоступен, не «0 предупреждений».

**Evidence:** `tests/rdg-active-example.test.cjs`, `tests/rdg-active-example-fixture.py` (real authorized readers + Gendocen), `tests/visual/rdg-active-example.cjs` (Graph/Plan/Gendocen в Chrome **через files и loopback HTTP**, включая устранённый дефект отложенного запуска каталога), `tests/visual/rdg-workspace-plans.cjs` (две independent candidate-v6 scope A→B→A), `tests/visual/rdg-always-on-plan.cjs` (saved owner vs missing file), `tests/rdg-workflow.acceptance.test.py` и `tests/rdg-temporal-plan-owner.test.py` (source history and schedule changes). [Рабочая инструкция и ограничения](RDG-LIVE-TEACHING-WORKSPACE.md). Установленная версия Viewer 2.4.2 и formal Stage 4 acceptance **не подтверждены**.

---

## Переформулировка Requirement и Gendocen dependencies — source Viewer 2.4.1 (2026-10-21)

**Запрос:** изменение существующего Requirement, включая главную R, должно оставить её старую/новую формулировку в истории Plan и автоматически выявлять dependency impacts у Actions, подцелей, проекций и канонов с **настоящими ссылками** на изменившуюся R. Просмотр — по всему Graph или одной R, из каждой записи переход к исходному блоку, журнал автоматического пересчёта по раскрытию. **Пользователь выбрал существующий Gendocen как engine**, без второго самодельного stale-хранилища.

**Сделано:** `tools/rdg-graph-api.py` + `graph-apply.py` сохраняют на каждую действительную правку R авторизованное событие `requirement_reformulated`, снимки «было/стало» и CAS, включая generic `edit_node` R. `rdg-activity.py` читает отдельный event kind, RDGWorkflowUI показывает разницу в истории Plan. `tools/rdg-requirement-gendocen.py` создаёт opt-in projections старого RDG Adapter и регистрирует **real Gendocen semantic_review subscriptions**, scoped по bearer и published identitySpace owner closure; `checkRequirements`, `graph-node` evidence, `DRIVES/DERIVES/INTRODUCES/OUTCOME_OF` и `projectionOf` не заменяются текстовым поиском. Receipt/changed inputs/historical events остаются только в Gendocen. `rdg-workflow-helper.py` с явным `--gendocen-project` запускает пересчёт **после принятого Graph write**, на каждом чтении вкладки «Зависимости» и по кнопке «Проверить зависимости», сохраняя принятую запись при недоступности engine; для нескольких рабочих графов — отдельное project-хранилище каждого. Viewer source **2.4.1** добавляет третью **«Зависимости»** с выбором всей scope/одной R, переходами к существующим Graph nodes, статусами и ленивым раскрытием журнала receipts; в «Сведениях» R/Action ссылка в зависимости. Новых Graph/Plan/grants или автоматической оценки correctness не создаётся.

**Граница:** синхронизация проекций происходит при чтении *канонического owner* через существующий `projectionOf`, а не несанкционированной перезаписью чужих Graph; внешний runtime/другие Gendocen projects вне зарегистрированной scope не сканируются. Без Helper/Gendocen, без полного `graphs/index.json` closure или полномочий — явная ошибка, а не «всё актуально». Правка напрямую другим writer требует последующего refresh на вкладке (без файлового демона). Gendocen `review_required` значит «нужно пересмотреть», не «Action точно неверен» и не событие достижения R. Подробный [контракт, запуск и ограничения](RDG-GENDOCEN-REQUIREMENT-DEPENDENCIES.md).

**Evidence:** real Gendocen tests `rdg-requirement-gendocen.test.py`, authorized writer `rdg-general-graph-api.test.cjs`, Plan/history UI `rdg-workflow-ui.test.cjs`, браузер `rdg-viewer-controls.cjs`, full E2E Helper file/loopback, Graph/Plan switch tests. Последняя подтверждённая пользовательская установка **2.3.9**, 2.4.1 source-only. Stage 4 NOT ACCEPTED.

---

## Единая навигация и контролы Viewer — исходник 2.4.0 (2026-10-20)

**Подтверждённая потребность пользователя:** прежние кнопки смешивали переходы между Graph/Plan, режимы визуализации, файлы и layout writer. На скриншоте установленного **2.3.9** особенно заметны «Назад» + «К полному графу», «Учебный план» + «План во времени», отдельные кнопки «Основные связи» + «Связи и контекст», смешение координат с отношениями, и черновик расположения без ясного типа. **Пользователь прямо разрешил переработку и повторную проверку.**

**Сделано только в source Viewer 2.4.0:** 2 главных tabs Graph/Plan; третий «Учебный план» удалён не только визуально, но и его отдельный controller path. Пример открывается автоматически в штатном Plan с `workflowExample`, рабочий граф — из настоящего Plan owner; никакой «предварительный Plan» не появляется. Навигация по breadcrumbs вместо верхнего дублирующего Back/full, отдельный «Уровень выше» только для nested graph traversal. Фильтр отношений объединён в один dropdown `#edges-mode`, но прежние внутренние handlers `#edges-core/#edges-all` оставлены для совместимости существующих тестов/проекций; видимость альтернатив остаётся независима, названа текущим состоянием. `#search`, `#fit` («Вместить в экран»), `#collections-collapse` — быстрые Graph controls. В «Вид ⚙» помещены поля контекста, режим просмотра контекста, **управление layout-файлом**, помощь по стрелкам и граф-редактор при авторизации. «⋯» хранит ручной JSON, актуальное обновление файла и Markdown source; при просмотре Plan файловый dropdown скрыт. Смена вкладки закрывает раскрытые меню. Статусы черновика и сохранения координат явно называют **расположение блоков**, а не Graph/Plan content. Внутренняя schema Graph и Plan, writer, grants, user Graph/Plan files, planned Action IDs не менялись.

**Исправлено по итогам E2E:** скрытый redundant educational path, устаревшие UI-copy про предварительный Plan, файловое меню поверх Plan, выпадение мобильного popup «Вид ⚙» за край окна; поправлены ожидания legacy tests, которые проверяли именно удалённые имена кнопок, и их проверка заменена тестом нового явного UX. После переключения Graph/Plan связь полного графа и просмотра отдельного уровня остаётся через breadcrumbs/level-up; никаких write в скрытых маршрутах нет.

**Evidence:** `tests/visual/rdg-viewer-controls.cjs` — браузер 1460×920 и 400×850, tab count, связь фильтра с legacy handler, меню Graph/Plan, состояние альтернатив, контекст, layout, ограничения viewport. `tests/visual/rdg-workflow-tabs.cjs`, `rdg-always-on-plan.cjs`, `rdg-workspace-plans.cjs`, `rdg-action-example.cjs` — fallback learning, Helper and navigation; expanded Node regression: **125 PASS / 4 SKIP**, WorkspaceEditors integration **6 PASS**, browser scenarios **PASS**. Source-only: installed Viewer 2.4.0 пока не подтверждён; последняя user screenshot установлена 2.3.9; Stage 4 NOT ACCEPTED. Технические ограничения canonical local writer, bearer/cross-owner protections сохраняются.

---

## Переход Plan/History → исходный блок Graph — Viewer source 2.3.9 (2026-10-20)

**Требование:** из каждой карточки R/Action в **плане во времени** и в **истории** должен быть явный переход в Graph — к **месту объявления** исходного узла, с выбранным/центрированным узлом и раскрытым контекстом. В Plan нет дублирующих сущностей, и навигация **не изменяет** Graph, Plan, history или grant. Исторический снимок канона/QRPE остаётся в карточке истории (не пересчитывается по нынешнему Graph); переход показывает текущее сохранённое объявление, в том числе superseded/архивный узел, а не стирает историю.

**Реализовано:** для запланированных R и Actions и для подтверждённых исторических R/Action одинаковая явная кнопка **«Открыть блок в графе ↗»**; заголовки существующих карточек сохраняют прежний переход. У событий изменения графа каждая существующая затронутая R/Action имеет отдельную кнопку. У `action_reconsidered` доступны ссылки на **старый Action**, **Action пересмотра**, **выбранный новый Action** и **компенсирующий Action** (если объявлен). Все ссылки разрешаются через `RDGWorkflowUI.declarationFor` по `graphFile / identitySpace / nodeId` и `projectionOf` с проверкой owner; если авторизованное объявление отсутствует, ссылка не выполняется/отключается вместо создания фиктивного узла. Вложенные исторические archived `INTRODUCES` можно использовать лишь для восстановления контекста просмотра; если текущий локальный уровень не показывает исторический узел, Viewer раскрывает **тот же целый Graph owner**, выделяет конкретный node ID. Целостность и модель прав сохранены.

**Критичный восстановленный сценарий:** после перехода из исторической учебной карточки к Graph повторное открытие Plan раньше могло терять `workflowExample`: Graph перехода содержал очищенную copy без авторского educational snapshot. Исправлено: на read-only teaching roots Plan восстанавливается из опубликованного графа, а не из промежуточной очищенной копии. Текущий рабочий `workspaces/*` по-прежнему читает настоящий Plan owner; пустой/отсутствующий файл не превращается в placeholder. Существующий пример `reference-mixed-active-work` дополнен точными **реальными** `targetId` из исходных `requirement_deactivated`, `requirement_reparented`, `context_discovered`, и symbolicTime, а каталог пересобран штатно. Нет новых выдуманных событий выполнения.

**Evidence:** `tests/rdg-workflow-ui.test.cjs` — явные 4 ссылки и переходы R/Action/planned/history, связанные ссылки switch, архивная R; `tests/visual/rdg-always-on-plan.cjs` — настоящий Chromium, переходы из учебных запланированных Action, исторических Action и R, а также `R-RELINK`/`R-INACTIVE` с archive, возврат к timeline без потерь; `tests/visual/rdg-workflow-tabs.cjs` — старый Helper E2E. **Source 2.3.9 ≠ installed** (последняя подтверждённая установка 2.3.4). Stage 4 original NOT ACCEPTED.

---

## Связанное событие смены Action и устранения последствий — source Viewer 2.3.8 (2026-10-20)

**Пользовательское уточнение:** после отказа от старого Action нужно видеть **что выбрали вместо него** и **как устранили последствия старого**. Это пара, не просто `superseded`. Новая структурированная ветвь `reconsider_action.event.transition` фиксирует `replacementActionId` (реально выбранный Graph Action; **не** `reviewActionId`, который только Action пересмотра) и `cancellation`: `no_additional_action` с причиной и hash-bound оценкой Graph либо `compensating_action` со ссылкой на существующий выбранный Action и **ранее записанный** `action_executed` ID. Signature/approval/canon QRPE, Graph owner, child dispositions, protections и recovery остаются как прежде. Компенсация не является новой сущностью из Plan. Отсутствие дополнительной работы — **явное документированное решение**, не вывод из пустой истории.

**Реализовано:** `tools/rdg-v6-action-reconsider.py` проверяет пару и компенсирующий результат; `tools/rdg-v6-action-trust.py` проверяет `assessmentEvidenceRefs` против реальной ревизии Graph вместе с прежним материалом подписанного пакета; `tools/rdg-activity.py` возвращает отдельный `action_reconsidered` и `transition`, не маскируя его как `action_withdrawn`; Viewer source 2.3.8 показывает «A-old → A-new» и «дополнительно ничего не потребовалось» или «выполнен компенсирующий A» с event ID. Исторический reconsider без `transition` отображает **неизвестный механизм**, не синтезирует его. **Никаких фактических удалений пользовательского кода это событие не выполняет** — удостоверение внешних изменений требует отдельной evidence-проверки.

**Evidence:** новые synthetic real-writer tests и read-back в `tests/rdg-v6-action-reconsider-writer.test.cjs`, UI unit test `tests/rdg-workflow-ui.test.cjs`. [Контракт и примеры](RDG-DEEP-ACTION-AND-HISTORY.md). **Source-only:** installed Viewer 2.3.8 не подтверждён, live Graph/Plan/authority grants не менялись, original Stage 4 NOT ACCEPTED. Прежние архивные `Option/Decision` read-only примеры сохранены только как исторические образцы, не реанимируются в новой модели.

---

## Типы истории, альтернативы и инвариант Graph → Plan — Viewer source 2.3.7 (2026-10-20)

**Прямое уточнение пользователя:** в истории надо визуально отличать активацию/деактивацию, выбор, изменение определения работы, подтверждённое выполнение Action и достижение Requirement. В план нельзя добавлять новую сущность, которой нет в Graph: Plan **только размещает** уже существующий Action/Requirement, не создаёт их, не выбирает Action вместо Graph и не доказывает выполнение.

**Implemented in UI:** `tools/rdg-workflow-ui.js::historyKind` помечает четыре категории: **РЕЗУЛЬТАТ** (`action_executed`, `requirement_achieved`), **СОСТОЯНИЕ** (`requirement_deactivated`, поддерживаемое отображение activation-типов, `action_withdrawn`), **ВЫБОР** (`decision_selected`, `action_selected`) и **ИЗМЕНЕНИЕ ГРАФА** (`graph_saved`, `context_discovered`, `requirement_reparented`). Видимое слово и цвет/обводка — одновременно, не только цвет. Event type `requirement_activated` есть как отображаемый тип, но никакое несуществующее событие **не добавлялось** в Graph или writer. Учебная история остаётся помечена как учебная, а события выбора/деактивации **не** отмечаются результатом выполнения. Прежние проверенные event snapshots использованы без подмены исторического канона текущим.

**Alternatives + canon:** при показе **Requirement**, в том числе в новой группе «Без места во времени», раскрываются варианты Graph (`DRIVES` Action и `OPTION_FOR` Option) с **отдельным полным каноном** и QRPE каждого. Для размещённого **Action** можно увидеть другие Action-способы той же цели, в том числе кандидат и пересмотренный исторический вариант, со статусом; выбор Action не приравнивается к исполнению. Новая графовая сущность из Plan не создаётся. Кнопка размещения Action-кандидата заблокирована до штатного Graph selection; настоящий writer всё равно проводит независимую валидацию.

**Почему два учебных примера:** `reference-mixed-active-work` — старый учебный Graph *Option/Decision*, каноны его вариантов показаны рядом с неразмещённой R; его 5 Graph edit/history events + 3 учебных размещения существующих R остаются без фальшивого Action. В этот старый Graph **нельзя** без нарушения контракта добавить `Action`: реальный валидатор отвергает смешение `Option/Decision` и `Action` в `candidate-v6`. Поэтому `workflowExample.relatedActionExampleSlug` добавляет **навигационную ссылку**, не Plan step, к существующему отдельному `reference-action-time-plan`: в том Graph реально объявлены Actions с канонами и `DRIVES`, в образовательной ленте два выбранных Action **A-IDEMPOTENT, A-SERVER** имеют placements; кандидат `A-QUERY` и пересмотренный `A-LOCAL` видны рядом со своими канонами, но не размещаются автоматически. Исторические `action_executed`, `requirement_achieved`, `action_withdrawn`, `graph_saved` отличаются по категории. Привязка каждого учебного Plan step/`future` проверяется по существующему Graph node id, file, identitySpace, kind, а Actions в future только `status=selected`; сломанные ссылки отвергаются. Учебные refs `examples/*` **не** выдаются за реальные записываемые Plan owners `workspaces/*`.

**Local Evidence:** `tests/visual/rdg-always-on-plan.cjs`: два реально разные архивные модели, каноны Option и Action alternatives, типы истории, переход отдельным примером, отсутствие ошибок UI; `tests/rdg-workflow-ui.test.cjs`: классификация события, снимок канона на момент исполнения, модель-обособление, fail-closed при фиктивных Plan-step/actionRef; регрессии Stage 4. Код + synthetic fixtures **не** означают installed 2.3.7 или принятие Stage 4. Исторические Graph facts, пользовательские grants/Plan owners, Graph writer/Plan writer completion logic не менялись.

---

## Три группы временной ленты и критерии completion — Viewer source 2.3.6 (2026-10-20)

**Уточнение пользователя:** граф содержит актуальные R/Actions до их размещения; отсутствие размещений **не означает** отсутствие планируемой работы и **не означает** выполнение. Временная лента показывает: 1) историю **записанных событий** (включая изменения графа, отличимые от результатов); 2) явно размещённые во времени ещё актуальные R/Actions; 3) **«Без места во времени»** — актуальные доступные R и выбранные Actions без размещения. Потенциальные и непринятые ветви нельзя выдавать за обязательное текущее исполнение. Одна сущность не создаётся в отдельном owner при перемещении между группами.

**Нормативные критерии НЕ изменены:** `rdg-v7-model.py::completion_state` + `rdg-completion-context.py`: Action `complete` относится к факту исполнения экземпляра (историческое `action_executed`; повторное исполнение того же ID отклоняется), `currentScopeComplete` относится к **текущему** составу. Requirement достигается по выбранным Actions и обязательным `subgoal`, Action — по собственным `method_correctness`; листовые случаи требуют явной записи результата, не завершаются пустой зависимостью. Выбор, создание, placement и графовое событие изменения сами по себе НЕ доказывают выполнение. `historyPending`, недоступный owner или отсутствующая journal provenance НЕ превращаются в «выполнено». Исторически выполненный Action не возвращается в будущее после отзыва; parent Requirement не становится достигнутой на неподтверждённой изменённой композиции.

**Viewer source implementation:** `tools/rdg-workflow-ui.js::planningInventory` разделяет completion / Plan placement / applicability и рисует третью секцию; для доступной completion-state делает консервативную классификацию, при отсутствии completion данные помечает как **не проверенные по writer**. Никаких новых семантических полей в Graph writer/Plan owner не добавлено. `tests/rdg-workflow-ui.test.cjs` покрывает уже размещённую R, выполненные R/Action, scope drift, `historyPending`, невыбранные ветви и отсутствие подтверждения. Browser E2E проверяет три секции и switch без смешивания данных.

**Наглядный архивный пример:** `graphs/examples/reference-mixed-active-work/graph.json` (ранее ошибочно назван в обзоре `reference-feature-root`; **на скриншоте именно `reference-mixed-active-work`**) теперь включает **образовательный `workflowExample`**: 5 исходных исторических событий **изменения модели** (0 подтверждённых исполнений Action, 0 достижений R), 3 **учебных размещения Requirements** (одно с гипотетической датой, два с порядком) и отдельную группу актуальных R без размещения. Это не persisted Plan: refs на `examples/*` предназначены для read-only демонстрации, а нормативный Plan writer принимает `workspaces/*` owner refs. В живые user Graph/Plan, grants и writer completion-критерии изменений нет. История решений/редактирования не называется «выполненная работа».

**Evidence:** `tests/visual/rdg-always-on-plan.cjs` (точный пример, группы 5+3+unplaced, отсутствие ложного `action_executed`), `tests/visual/rdg-workflow-tabs.cjs` (три секции, полнота прежних сценариев), `tests/rdg-workflow-ui.test.cjs` (completion/placement независимы), Graph index regenerated штатно. **Source 2.3.6 не подтверждён как installed; local Stage 4 NOT ACCEPTED.**

---

## Исправление маркировки архивного рабочего примера — source Viewer 2.3.5 (2026-10-20)

**Installed observation:** пользователь показал Viewer **v2.3.4** на «Рабочий пример разбиения функциональности» с надписью «Предварительный план». **Уточнено позднее:** на пользовательском скриншоте — `reference-mixed-active-work`; ранняя идентификация `reference-feature-root` была ошибочной. Этот архивный `examples/...` graph имеет `readOnly=true`, `exampleOnly=true`, `presentation.exampleOnly=true`, хотя исторический catalog `presentation.usage='working'`. В версии 2.3.4 он попал в ветку education без `workflowExample`, но общий UI использовал текст о предварительном Plan. **Problem: вводящее в заблуждение состояние UI**, не доказательство некорректной записи пользовательского Plan.

**Resolved source 2.3.5:** `localPlanPreview` теперь явно обозначает educational-only graph с `examplePreview` даже если `workflowExample` отсутствует; в блоке Plan — **«Учебный пример: запланированных шагов нет. Это пример графа, не сохранённый пользовательский Plan»**. Никакие Plan owner не синтезируются или не создаются в каталогах архивных read-only примеров. Имеющиеся образовательные `workflowExample` с историей/размещениями не теряются. Для настоящих writable `workspaces/*` действует прежнее правило source 2.3.4 — только реальный сохранённый Plan, при отсутствии файла ошибка, без UI подмены. Регрессия: `tests/visual/rdg-always-on-plan.cjs`, `tests/visual/rdg-workspace-plans.cjs`, `tests/rdg-workflow-ui.test.cjs`. User-installed **2.3.5 ещё не подтверждена**; local-only acceptance всё ещё pending.

---

## Local Graph → один реальный пустой Plan по умолчанию (source Viewer 2.3.4, 2026-10-20)

**Последний прямой выбор пользователя:** нельзя иметь «предварительный» и «постоянный» планы: **у каждого рабочего графа должен быть один настоящий Plan owner** ещё до первого размещения Action. Если будущего и истории нет — это **пустой сохранённый Plan**, не поддельная проекция. **Implementation source-only**: `WorkspaceEditors.initialize_missing_plans()` готовит все отсутствующие `plans/<rootSlug>/plan.json` **на старте авторизованного Helper** (до session folder); альтернатива `--auto-workspaces --initialize-plans-only` без сессии. Использует существующий Plan writer, `plan.create + plan.read`, Graph read scopes и catalog root evidence; никакого write при отказе, existing Plans не трогает. Legacy `try-it` получает такой же **настоящий пустой Plan**, но read-only до явной Graph migration: небезопасно выдумывать identity Graph и записывать placement. В каталоге учебные графы не объявлены рабочими владельцами.

**Viewer source 2.3.4:** для рабочего Graph читает persisted `temporalPlanOwner` из `plans/<slug>/plan.json` относительно RDG-root через локальную read-capability; identity/owner/revision mismatch и отсутствие файла = ошибка, **не placeholder**. После подключения Helper читает тот же owner, включая полные authorised historical receipts. У учебных примеров сохраняются прежние встроенные учебные snapshots. Планы физически не созданы на живом RDG в этом ходе: пользовательские bearer/grants недоступны; установленная у владельца 2.3.2 не обновлена. [Точный порядок setup и ограничения](RDG-LOCAL-GRAPH-PLAN-BINDING.md). Автоматический init на графовом writer вне разрешённой Helper-сессии **не добавлен**: это отдельная требующая авторизации связь owners, а не безусловное побочное действие существующей Graph записи.

**Evidence:** реальный synthetic Plan-writer + legacy-copy integration, browser with fake directory/GM read of stored owner (включая missing-file fail-closed), адресные Node UI checks. Status: source candidate/локально проверено, installed 2.3.4 не подтверждено, original Stage 4 NOT ACCEPTED.

---

## Всегда видимый локальный Plan для выбранного графа — source Viewer 2.3.3 (2026-10-20)

**Уточнённая потребность пользователя:** в «Папках» можно выбрать любой рабочий граф для своих чатов; вкладка «План во времени» должна быть видима **сразу**, даже если будущих размещений нет; исторические блоки остаются **в прежней временной ленте**. Название `try-it` — существующий legacy-пилот; скриншот полного `reference-feature-root` — учебный read-only пример. Не требовать подключения Helper для отображения пустой ленты.

**Реализовано source:** `tools/rdg-workflow-ui.js::localPlanPreview` формирует read-only представление из выбранных доступных графов (история только из доступных `events`, без претензий на полноту writer journal; у published read-only примера с уже сохранённым в источнике `workflowExample` используется **авторский учебный snapshot с 15 историческими карточками и 4 учебными размещениями**, не настоящий Plan owner). Viewer 2.3.3 открывает тот же UI History → Plan, переключает предпросмотр вместе с графом, очищает прежний контекст; при отсутствии Helper не делает write. Для новых совместимых candidate-v6 working roots `tools/rdg-workflow-helper.py::automatic_working_contexts` + `WorkspaceEditors.ensure_plan` создают отсутствующий Plan **только штатным Plan owner API**, только при `graph.read + plan.create + plan.read`, revision/CAS сохранены; existing Plan не переписывается. Для legacy try-it, у которого нет identitySpace/actionModel, persisted Plan пока не создаётся без разрешённой миграции: он только preview. `--auto-workspaces` обнаруживает поддерживаемые roots из каталога на запуске Helper; config `--contexts-file` тоже остаётся. **Ни один пользовательский граф/грант не изменён.**

**Tests:** `tests/visual/rdg-always-on-plan.cjs` — реальный Chromium: try-it → пример с существующей историей → try-it → полный пример, без picker/Helper, история/пустое будущее видимы; `tests/visual/rdg-workspace-plans.cjs` — synthetic Helper A→B→A→нет mapping; `tests/rdg-workspace-switch.integration.test.py` — реальный writer и отказ без scope, auto-discovery. [Подробности и операторская настройка](RDG-LOCAL-GRAPH-PLAN-BINDING.md). **Установленный Viewer 2.3.2 подтверждён пользователем, но 2.3.3 пока только source candidate. Local-only acceptance pending. Stage 4 original full candidate NOT ACCEPTED.**

---

## Новый рабочий контекст: большой Graph → собственный Plan (source Viewer 2.3.2, 2026-10-20)

**Прямой пользовательский scope:** несколько полных рабочих графов в локальном каталоге; каждый имеет свой отдельный Plan, автоматически выбранный при открытии полного графа. Подграфы того же большого графа используют общий Plan. Это **новое требование после v4.1 Candidate**, не скрытое «старое Finding», не создание новых будущих steps автоматически. User authorised actual implementation.

**Реализация:** `tools/rdg-workflow-helper.py` получает opt-in owner-controlled `--contexts-file`: одна session-папка обслуживает явно сопоставленные `rootSlug + graphFile + identitySpace + rootRequirementId → planFile` с прежними отдельными Graph/Plan writers, CAS и bearer. `tools/rd-graph-viewer.user.js` **2.3.2 source** переключает Plan вместе с выбранным full root; `tools/rdg-workflow-ui.js` очищает прежний Plan до новой загрузки и не допускает запись/показ при missing/denied/mismatched контексте. Legacy single graph/file Helper остаётся. Локальный read closure подтягивает доступные Graph владельцы того же identitySpace, отсутствие обязательных прав даёт отказ. Не подключает и не создаёт ничего в пользовательских файлах автоматически.

**Proof:** `tests/rdg-workspace-switch.integration.test.py` + `tests/rdg-workspace-switch.test.cjs` — real writers/FileSession, Graph A/B, Plan A/B, автоматизированные записи и контекстные отказы; `tests/visual/rdg-workspace-plans.cjs` — Chromium A→B→A→unconfigured без pageerrors. [Полное объяснение и настройка](RDG-LOCAL-GRAPH-PLAN-BINDING.md). **У пользователя в браузере пока Viewer 2.3.1**, новая source 2.3.2 ещё не установлена; установленную операцию и acceptance не заявлять. Никаких ручных повторов уже покрытых E2E не требовать.

---

## Принятое ограничение следующей версии — локальный RDG (2026-10-20)

**Решение пользователя:** «пока локальное оставляем» — на ближайшую версию **локальные Graph/Plan owners и существующие файловые writers остаются каноническими**. GitHub не является обязательным backend, публикацией или условием локальной приёмки. Это **committed выбор scope текущей версии**, но **не acceptance Stage 4 или всего Candidate Pre-work v4.1**. Исходную Stage 4 композицию с условной отдельной GitHub-транзакцией не переписывать задним числом: её **remote-ветка отложена** до нового прямого решения пользователя о repo/branch/writer и разрешении отдельного безопасного remote-теста.

**Граница приёмки сейчас:** оценивать только локальную сохранность/восстановление и разграничение разрешённых Graph/Plan операций, вспомогательные semantic receipts Gendocen (без ложного утверждения исторической истины), а также уже наблюдавшееся установленное подключение Viewer 2.3.1 к тестовой Helper-сессии. Локальный E2E writer path доказан автоматическими тестами; по прямому указанию пользователя **не повторять его вручную в браузере**. Owner-admin установленный сценарий не проверен и остаётся **PARTIAL**, без необходимости выдавать настоящие токены только ради формального теста. Полный multi-owner Gendocen dependency closure не считать завершённым вне узкого opt-in single-owner контракта.

**Следующее техническое действие:** подготовить приёмочную границу именно **local-only validation slice** из существующих проверенных evidence и открыть только существенные непокрытые локальные требования. Remote/GitHub consistency, выбор нового хранилища, миграция, release push, лицензирование внешнего распространения **не блокируют этот local-only срез**, пока пользователь не расширит scope. Исторические Stage 2/3 остаются самостоятельными открытыми частями общего Candidate Pre-work; их состояние не меняется от выбора локального backend. **Статус local slice: implementation verified in stated scope / acceptance pending. Stage 4 (original full candidate): NOT ACCEPTED.**

---

## Сверка Stage 4 после установленного Viewer 2.3.1 — 2026-10-20 (последний срез)

**Вердикт:** техническая локальная композиция Graph/Plan + bearer writer + Viewer/Helper + opt-in Gendocen стала существенно полнее, но **Stage 4 целиком NOT ACCEPTED / не готов к безусловной приёмке**. Источник требований — [Candidate Pre-work v4.1](../handoffs/rdg-prework-v4.1-final-20261018/candidate-prework-v4.1-execution-reconciled.md), раздел Stage 4 (**CANDIDATE / NOT WHOLE-BASELINE COMMITTED**), а не автоматическое превращение всех WR/EA в принятые FR. Stage 4 там содержит **и** локальные journal/recovery, **и** вторичное состояние Gendocen, **и** отдельную **условную** транзакцию выбора canonical GitHub owner/branch/writer и remote-тестов. Нынешний смоук установленного Viewer частично относится к Stage 5; он сам по себе не принимает Stage 4.

**Новое пользовательское installed evidence (скриншоты в этом диалоге, 2026-10-20):** Viewer **v2.3.1** отображался в установленном браузере; выбранная в native folder picker тестовая папка `.rdg-viewer-smoke-session-bc2cfde795` была отмечена как **подключена**, а Viewer показал **«Данные перечитаны»**, синтетический `Root` и историю. Helper с файловым транспортом действительно был запущен на отдельном временном наборе Graph/Plan/grant store, `grant.admin` **выключен**. После проверки этот процесс остановлен, временная папка удалена. Это **подтверждение installation + picker + file-session read**, не доказательство установленного admin-grants режима, ручной write/revoke или production ACL. По позднему прямому указанию пользователя **не повторять в браузере** создание Action/запись/историю, уже покрытые настоящими E2E writers на синтетических данных. Показ картинки не заменяет реальный тест записи, но и не создаёт обязательства бессмысленно повторять его вручную.

### Evidence и текущая судьба проверенных Findings (разные review-линии сохраняют свои IDs)

| Предмет / source finding | Точное доказательство и disposition в текущем scope | Что остаётся |
| --- | --- | --- |
| `F-P-01` (grant UI, review Viewer 2.3.0) | `list/issue/amend/revoke` в Helper + Viewer **реализованы и локально E2E/Node проверены**; дефект отсутствия функции **resolved-local**. | Installed owner-admin-панель и её реальные grants **не проверены**; нельзя утверждать полный установленный scenario. |
| `F-P-NEW-03` (успешная выдача + неудачный `list`) | Разделены outcome изменения и ошибка refresh; тесты `tests/rdg-workflow-ui.test.cjs` для successful issue/failed list и uncertain retry — **resolved-local**. | Реальная административная сессия на устройстве владельца не исполнялась. |
| `F-R-NEW-02` (ошибочный admin-вызов чата) | Штатный bearer writer / обычная Helper session отказывают без `grant.admin` / `--grant-admin`; две роли/два scope проверены через `tests/rdg-bearer-package.integration.test.py`; **mitigated-local**. | Реальная доступность owner-admin session постороннему чату неизвестна; нет требования защищать от намеренного RW bypass в чужом инструменте. |
| `F-R-NEW-01` (полнота owner context Gendocen) | `readOnly`/`expansionOf` явно подписаны в opt-in Graph projection, `projectionOf`/`expansionOf` cross-owner дают fail-closed; **mitigated for current single-owner pilot**. | Полный multi-owner Gendocen dependency graph / historical completion truth не реализованы, не объявлять `complete=true` вне scope. |
| `F-R-POST-01` (дублированный `resource_id` при legacy + workflow) | Отдельный `rdg.graph.workflow-v1.*`, legacy ID неизменен; real-engine mixed resource sync и `valid→review_required` лишь для workflow — **resolved-local**. | Исторические экспериментальные workflow receipts с прежним ID не мигрировать молча. |
| `F-R-03` (перезапись старых тестовых логов, review 2.3.0) | По умолчанию старые handoff-логи не пишутся; вывод — только при `RDG_WORKFLOW_TEST_LOG_DIR`; проверено в адресных Helper/cross-file tests — **resolved-local**. | Не выдавать это за полноценную проверку внешних логов/OS. |
| `F-R-02` (установленный Viewer, review 2.3.0) | Показаны **версия + native folder picker + read** на устройстве пользователя — **частично закрыт / PARTIAL** вместо прежнего `OPEN` об отсутствии вообще installed proof. | Установленный owner-admin workflow и controlled installed write не проверены; повторять E2E write вручную без новой причины не запрашивать. |
| `F-R-04` (Git provenance, review 2.3.0) | В live `/workspace/repos/rd-graphs` по-прежнему нет `.git` — **deferred** с условием возврата перед versioned release/remote cutover. | Нет основания заявлять Git commit/diff/push RDG; `forfiles` — только копия отчёта для чтения. |

### Stage 4: покрытие условий Candidate Composition

| Условие из v4.1 / WR | Фактическое покрытие | Gate до широкого принятия |
| --- | --- | --- |
| **Local package-journal/catalog recovery, version/CAS, read-back, fault injection** — `WR-35`, authority `WR-04/07/43/44` | **DONE-LOCAL в отдельных синтетических Graph/Plan owners**: проверки с реальными writers, revoke-before-commit, replay/история, crash 91/recover, journal corruption/сохранность; см. `tests/rdg-bearer-package.integration.test.py`, `tests/rdg-workflow.acceptance.test.py`, `tests/rdg-temporal-plan-owner.test.py`, `tests/rdg-cross-file-completion.test.py`. Это не означает remote-atomicity. | Для remote backend ещё отсутствует доказательство единообразной транзакции/rollback после partial Git write. Не перезапускать те же E2E лишь ради таблицы. |
| **Gendocen secondary receipts/freshness + независимые legacy/workflow projections** — `WR-28/29/30/31/34/50`, `EA-18/34` | **PARTIAL + local real-engine PASS**: старый узкий контракт и opt-in `rdg-workflow-review/v1` с разными resource IDs, матрица существенных мутаций, fail-closed missing source; `tests/rdg-gendocen-dependencies.test.py`, `tests/rdg-workflow-gendocen.test.py`, `tests/rdg-gendocen-resources.test.py`. | Review receipts — вторичное техническое состояние, **не доказательство истины**; multi-owner closure/исторические as-of не реализованы; старые workflow receipts с общим ID требуют отдельной переоценки. Нормативную достаточность расширения для всей Stage 4 не считать доказанной. |
| **Установленный Viewer/Helper** — `WR-37/39`, `EA-25` (связанный Stage 5) | **PARTIAL INSTALLED**: версия v2.3.1, picker, file read подтверждены настоящим браузером; остальная функциональность — E2E через writers в synthetic fixture. | Admin-grants UI не тестировался на установленном owner окружении. Остальной уже покрытый сценарий не требовать повторять вручную. |
| **GitHub canonical repo/branch/writer, remote consistency, authorisation** — `WR-36`, `EA-24` | **NOT DONE / отдельная decision transaction**: отсутствует выбранный canonical remote owner для RDG и разрешённый безопасный remote-тест. `forfiles` не является им по умолчанию. | При переходе к **remote/persistent** Stage 4: сначала пользователь подтверждает repo/branch/writer и границы изолированного remote-теста; затем проверяется partial commit, ref conflicts, readback/recovery. Не менять GitHub или настоящий пользовательский Graph без этой границы. |
| **Deployment/dependency trust** — `WR-40` | Реальный co-located engine применялся в synthetic tests. | Лицензия/условия перераспространения и доверенность используемой Python-конфигурации не объявлены полностью закрытыми; проверить только при соответствующем distribution/deployment scope. |

**Смежные предварительные условия Candidate Composition:** в исходной последовательности v4.1 до полной сборки Stage 4 предусмотрены Stage 2 (typed Findings / Canon / guard coverage) и Stage 3 (independent research graphs, owner/provenance, promotion/archive). Их исходные `WR-13..27` имеют смешанные `PARTIAL/OPEN` в историческом [evidence ledger](../handoffs/rdg-prework-v4.1-final-20261018/WR-EVIDENCE-LEDGER.md). Данный Stage 4 срез **не перепроверяет и не объявляет их принятыми**; разрешённый локальный validation slice может существовать раньше завершения всей Candidate Composition. Поэтому даже завершение remote GitHub-теста само по себе не означает acceptance всей RDG. Поздние прямые ограничения на Action/Plan имеют приоритет над первоначальными предположениями Stage 2/3.

**Следующий реальный gate:** Stage 4 **локальный validation slice** можно считать технически продемонстрированным в перечисленном охвате, но **нельзя** принять удалённую/полную Stage 4 только по локальным тестам. Если следующая обещанная версия требует GitHub как canonical owner — необходим отдельный выбор пользователя `repo/branch/writer` и разрешение remote-теста; после него проверка удалённой консистентности. Если следующая версия остаётся строго **local-only**, это *отдельное уточнение обещанного scope/acceptance*, а не тихое понижение старого Candidate Stage 4. Не вводить неопределённый hard deadline: дата и ресурсы не установлены. Никаких новых grants, ACL или живых user-data writes для этой сверки не выполнялось.

---

## Исправление совместимости проекций Gendocen — 2026-10-20

**F-R-POST-01 / локально устранённая интеграционная ошибка:** воспроизведён реальным Gendocen 0.1.0.dev25: при наличии двух файлов проекции одного Graph, `legacy` и `workflow_context=True`, оба имели один `resource_id`, и `sync` возвращал ошибку дубликата (exit 4). Теперь исходный `rdg.graph.<digest>` **не меняется**, а отдельная opt-in проекция получает `rdg.graph.workflow-v1.<digest>`. Её `resource_ref` и подписки строятся по этому отдельному ID. CLI явно поддерживает `--graph ... --workflow-context`; флаг с `--plan` запрещён. Код legacy `graph_resource(...)` и hash старых входов остались неизменными.

**Verification:** в отдельном временном docengine project совместный `sync` обеих Graph-проекций проходит; обе semantic reviews подтверждаются как `valid`; изменение `readOnly` вызывает `review_required` **только** для workflow-оценки, а legacy review остаётся `valid`. Тест `tests/rdg-workflow-gendocen.test.py::test_real_engine_legacy_and_workflow_resources_coexist` исполняет real engine и не меняет ни настоящие графы, ни установленный Gendocen. `tests/rdg-gendocen-resources.test.py` независимо сверяет прежний ID, новый ID, CLI, неизменность legacy hash и ошибку выбора `--workflow-context` для Plan.

**Версионная граница:** новый ID — отдельный opt-in ресурс, не автоматическая миграция ранее сохранённых **workflow-v1** экспериментальных receipts, если они были созданы на старом общем ID. При переносе любого такого локального эксперимента нужно явно обновить путь ресурса и повторно подтвердить semantic review; не объявлять прежнюю receipt автоматически действительной. Старый legacy ID и его receipts остаются совместимыми. Installed Windows Viewer 2.3.1, пользовательские папки, настоящий Git owner и acceptance Stage 4 **не проверялись**.

## Уточнение после локальных правок — 2026-10-20, текущий исходник 2.3.1

**Пользовательская цель grants:** ограничивать случайные действия разных ИИ-чатов, а не строить инфраструктуру защиты от злоумышленников. Штатные `graph-apply.py`/Authority проверяют bearer каждого чата независимо от Helper; Helper остаётся только клиентским слоем Viewer. На двух временных chat-grants повторены отрицательные проверки: чтение вместо записи, другая папка, выбор Action без права, `grant.admin` без административного grant, отзыв до следующей записи — запреты без частичной записи. Обычно `--grant-admin` **не включён**; admin-файловая сессия, когда включена владельцем, является отдельной capability, её папку/URL не следует предоставлять обычному чату. Это организационная граница доступа к инструментам, **не гарантированная OS sandbox изоляция**: прямой RW mount Repo сам по себе не подчиняется bearer. Установленный Windows/G2 путь по-прежнему не проверен.

**UI исправлен:** после подтверждённого `issue/amend/revoke` неуспешное последующее `list` больше не считается неопределённым исходом мутации; до успешного перечитывания запрещена следующая mutation со старой revision. Точный replay доступен только при неизвестном исходе *самого* запроса. Регрессионные тесты проверяют оба случая.

**Gendocen:** `graph_resource(..., workflow_context=True)` — явное opt-in для `rdg-workflow-review/v1`. Он добавляет `readOnly`/`expansionOf` в semantic resource и subscriptions; старый `graph_resource(...)`/`rdg-temporal-review/v2` не расширены задним числом. Контракт отслеживает current single-owner Graph/Plan, Action/R steps, две дочерние роли R, события исполнения/достижения/отзыва. При `expansionOf` или любом node `projectionOf` теперь явный `WORKFLOW_CROSS_OWNER_CONTEXT_NOT_COVERED`, **не `complete=true`**; полноценный межфайловый owner closure не реализован и не заявлен. В real docengine `readOnly` изменение запросило review; `expansionOf` и omission subscriptions дали fail-closed. Историческая истина завершения не подтверждается.

**Граница результата:** локальный source 2.3.1, без установленного Tampermonkey/Windows acceptance, без Git commit или push, без расширения ACL; Stage 4 **NOT ACCEPTED**. Исторические срезы ниже остаются на своих версиях.

## Дополнение после независимого review — локальный кандидат 2026-10-20

**Что сделано в живом `/workspace/repos/rd-graphs`:** Viewer **2.3.1 (исходник)**, локальный Helper grant panel (`list / issue / amend / revoke`) через существующий Authority API; admin-режим opt-in `--grant-admin` и отдельный owner токен, без делегирования `grant.admin` из UI. ИИ продолжает обращаться к штатным Graph/Plan writer непосредственно: Helper — только пользовательский прикладной слой. Включение панели не создаёт grants автоматически и не повышает права обычных сеансов. Корректная граница администратора на реальных OS permissions/папке владельца **не проверена**.

**Gendocen:** опциональный `rdg-workflow-review/v1` читает полные существующие семантические группы Graph/Plan, включая R-steps, `subgoal`/`method_correctness`, события исполнения, достижения и отзыва. Этот способ специально консервативен: требует review при некоторых незначимых изменениях, но позволяет избежать false-valid из-за новых зависимостей; исходный `rdg-temporal-review/v2` оставлен без изменения области действия. Тесты с реальным `docengine` подтвердили шесть семантических изменений и отказ при пропущенной подписке. Известную прежнюю P0 узкую область не объявлять полным историческим Action context; `completionTruthAttested=false`.

**Локальное evidence этого дополнения:** новые UI/Helper тесты и real Gendocen smoke — PASS; общий Node 312 тестов: 309 PASS, 3 conditional SKIP, 0 FAIL (после адресного исправления устаревших *тестовых фикстур*). В тестах Helper/cross-file сохранение логов в старые handoff-каталоги по умолчанию выключено. Исходные writers/старые owners не мигрировались. Точные запускаемые тесты: `tests/rdg-workflow-helper.test.py`, `tests/rdg-workflow-ui.test.cjs`, `tests/rdg-workflow-gendocen.test.py`, `tests/rdg-gendocen-dependencies.test.py`, `tests/rdg-shared-action-occurrences.acceptance.test.py`.

**Следующее условие:** отдельно проверить установленную пользовательскую копию Viewer 2.3.1, доступ к выбранной сессионной папке и запись только на разрешённых синтетических Graph/Plan. Сам факт ранее показанного Viewer 2.3.0 не подтверждает установку 2.3.1. До этого `F-P-01` закрыт только как **локальная реализация**, а не полный установленный Scenario; `F-R-01` имеет проверенный opt-in pilot без полной семантической точности; `F-R-03` локально исправлен, `F-R-02` OPEN, `F-R-04` deferred. **Stage 4 NOT ACCEPTED.** Исторические срезы ниже сохраняют свои даты и утверждения, их не считать новой версией.

## Срез передачи новому чату — 2026-10-20, Asia/Bangkok

Полный текущий хендофф: [HANDOFF](../handoffs/rdg-next-chat-20261020/HANDOFF.md).
Редакция 2 перепроверена: в передаче дополнены связанные материалы и явные ограничения ручного Helper; для тестов задан отдельный каталог логов. Код приложения в этой перепроверке не менялся.
Последний код: **Viewer 2.3.0**, Local Loader 2.5.2.
[Исправления A-01–A-06 и доказательства](../handoffs/rdg-examples-remediation-20261019/FIXES.md).

| Результат | Фактический статус |
| --- | --- |
| Глубокие Actions, две роли R, экземпляр/отзыв/история и place/unplace | Локальный PASS в описанной авторизованной композиции одного Graph root; прежние границы сохраняются. |
| Ручной UI, вкладки, карточки, лента, canonical navigation, память папки | PASS в изолированном настоящем Chromium; picker/permissions/session fixtures не являются папкой пользователя. |
| Канон над способом, старые плотные layouts, ширина текста | PASS в локальной и полной подробной карте; 49 текстовых представлений без переполнений. |
| Примеры и исторический материал | A-01–A-06 исправлены. Каталог 101 граф, новый current Action-сюжет с учебным планом. Новые события хранят viewSnapshot материала. T1 и старые selectionBasis неизменны. |
| Проверки последнего пакета | Node 185: 182 PASS, 3 conditional SKIP; Python writers 72 PASS; 277 browser views без page/render errors и пересечений. |
| Установленный Windows/G2 и реальная пользовательская папка/запись | **OPEN**: исходники не равны установке; ближайший пользовательский результат. |
| Полный новый Gendocen context ролей R/результатов/workflow | **PARTIAL**: отдельная задача; новый real-engine smoke не выполнен. |
| Скрытие/приоритет истории | Не начато, второстепенная настройка представления. |
| Stage 4 / independent production acceptance | **NOT ACCEPTED**. |

Поздние уточнения сохраняют приоритет: только явное размещение существующих R/Actions; один Action — один экземпляр; нет второго lifecycle закрытия шага; выполненное сохраняет историю; подцели и correctness различаются; временной план не является содержанием создаваемого приложения.
Предыдущие knownAt/effectiveAt baseline, принятие Plan и claim/attestation/review эксперименты не возвращаются в обязательный маршрут.

Накопленные разделы ниже содержат исторические версии 2.1/2.2 и прежние фразы «native browser не проверен». Для текущего isolated-native статуса использовать эту сводку; installed Windows/G2 всё ещё открыт. Прежние checkpoints и их исторические матрицы не переписываются.


**Последний проверенный срез кода:** [безопасная ручная правка размещения](../handoffs/rdg-placement-edit-repair-20261019/CHECKPOINT.md).
**Предыдущий межфайловой срез:** [межфайловое выполнение и история владельцев](../handoffs/rdg-cross-file-completion-20261019/CHECKPOINT.md).
**Предыдущий ручной срез:** [Viewer/Helper и общая лента](../handoffs/rdg-manual-workflow-20261019/CHECKPOINT.md).
**Предыдущий сквозной API-пакет:** [Action-instance / Plan API / будущее и история](../handoffs/rdg-instance-temporal-workflow-20261019/CHECKPOINT.md).
**Предыдущая сверка:** [контрольная точка](../handoffs/rdg-plan-completion-review-20261019/CHECKPOINT.md).
**Предшествующий ремонт:** [исправление завершённости и истории](../handoffs/rdg-completion-repair-20261019/CHECKPOINT.md).
**Предшествующий срез:** [CPW-RDG-DEEP-ACTION-20261019/v1](../handoffs/rdg-deep-action-model-20261019/CHECKPOINT.md).
**Независимое review этого среза:** [R-RDG-DEEP-ACTION-20261019-01/v1](https://github.com/AlexPastukhh/forfiles/blob/10eb118bcf894d425210c1a08fb248cbb3677e3f/artifacts/2026-10-19/final-review-rdg-deep-action-r-rdg-deep-action-20261019-01-v1.md).
**Предыдущая проверка сообщения и плана:** [REVIEW](../handoffs/rdg-temporal-review-fix-20261019/REVIEW.md).
**Статус:** рабочий план
для Candidate-пилота. **Stage 4 NOT ACCEPTED.** Этот документ обновляет
порядок и фактические статусы после локальных проверок. Он не меняет
нормативные Need / FR / Desired Scenario / SRU, не принимает Proposals и не
переписывает [полный v4.1](../handoffs/rdg-prework-v4.1-final-20261018/HANDOFF.md)
или [историческую матрицу P2](../handoffs/rdg-p1-plan-contract-20261019/P2-ACCEPTANCE-MATRIX.md).

`Локальный PASS` ниже означает проверенный сценарий на временных синтетических
источниках. `PARTIAL` — проверена лишь часть условия. `OPEN` — требуемого
поведения или доказательства пока нет. Эти статусы не означают independent
acceptance, установку Windows или публикацию.

## Актуальное уточнение пользователя — 2026-10-19

План обновлён после уточнений 15:51–15:54 Asia/Bangkok. Один Action — один
экземпляр действия. Будущее содержит размещённые невыполненные сущности графа;
история сохраняет те же сущности после результата. Выполненный A1 остаётся
в истории. Для той же цели можно отозвать A1 и выполнить другой вариант A2;
прежнее выполнение, отзыв и новое выполнение сохраняются раздельно.
Повторные физические исполнения одного Action и отдельный жизненный цикл
закрытия шага расписания в текущую работу не входят. Эти уточнения реализованы
и проверены сквозным API-сценарием внутри одного владельца графа. Контроллер ручного
редактора теперь также проходит этот путь с настоящими writers через файловый
и loopback-транспорты. DOM имитируется; установленный браузер Windows/G2 и native
picker ещё не проверены. Межфайловой расчёт candidate-v6 теперь также реализован
и проверен внутри одного Graph root; это локальный API/controller proof, не
установка Windows или acceptance Stage 4.

Основные определения принадлежат [руководству граф-модели](RDG-V7-WORKING-GRAPHS.md),
разделу «Уточнение модели: граф, план во времени и выполнение — 2026-10-19».
Здесь задан порядок исполнения, а не второй владелец определений.

Граф уже является моделью планирования целей, предварительных Actions и
Requirements. Несколько ветвей можно проработать без принятия предыдущих
Actions. Новая вещь называется **планом во времени**: в ней явно задаются
время и/или порядок выполнения целей и Actions, в том числе предварительных.
Создание Action само по себе НЕ добавляет его в будущую часть этого плана.
Это отменяет предыдущее предположение ассистента об автоматическом включении.

Человек редактирует данные вручную; ИИ работает через API над теми же данными.
Права, защита от перезаписи чужой версии и один смысловой owner сохраняются.
Выполнение без предварительного размещения сразу попадает в историю выполнения.
Фиктивный будущий шаг или расписание для этого не создаются. История правок
графа также сохраняется; она не выдаётся за выполнение всех изменённых Actions.

Подцели-разбиение выделяются Actions типа decomposition — по одной или связанным
набором. Обычный Action тоже может выделять такой набор. Разные варианты набора
представлены разными Actions. У любого типа сохраняются две роли дочерних R:
subgoal для родительской цели и method_correctness для самого Action.
Requirements корректного
выполнения исходят от соответствующего способа Action. Варианты способов
реализации Action раскрываются через R «решить, как выполнить Action».
Листовые Actions допустимы по действующим трём критериям создания сущностей;
обязательная дополнительная цель результата не вводится.

Расчёт завершённости должен различать достижение R, выполнение Action,
принятие варианта и роли дочерних R. Будущая часть плана во времени исключает
выполненную работу по этому расчёту, сохраняя историю. Скрытие/понижение
приоритета записей истории — второстепенная настройка показа.

Автоматический выбор baseline по knownAt/effectiveAt, отдельный lifecycle
принятия Plan и три стадии claim/attestation/review не возвращаются в обязательный
маршрут. Прежние модули и proof остаются экспериментальными материалами.
Существование кода не превращает его в требование. Остальные Need / FR /
Desired Scenario / SRU не переписываются без сопоставления с новым уточнением.

PR-PLAN-COMPLETION-01 уточнён этим прямым указанием пользователя. Отменена
прежняя фраза ассистента об автоматическом включении Action; конкретные поля,
API-операции и сериализация остаются Candidate до реализации и проверки.
План во времени не является планом функциональности приложения: приложение
или любой иной артефакт может быть результатом работы по графу.

## Исправление ручной правки размещения — PR-01

После [Final Review R-RDG-LARGE-STEPS-20261019-01/v1](https://github.com/AlexPastukhh/forfiles/blob/813be44ebb626ac126c5c47813c1695664657e16/artifacts/2026-10-19/final-review-rdg-large-steps-r-rdg-large-steps-20261019-01-v1.md)
пользователь прямо поручил «исправь». PR-01 принят к исполнению этим указанием;
это не Git commit и не acceptance всей версии. F-P-01/F-P-02 относятся к ручному
адаптеру размещения, а не к модели выполнения графа.

Helper сохраняет исходящие связи других шагов, deadline, strength, basis,
минимальный интервал предшествования и прежний Graph ref размещения. Поля даты
начала и предшественника меняются явно; пустое поле снимает только своё условие.
Unplace остаётся отдельным удалением размещения с incident-связями. При нескольких
notBefore/предшественниках или точном времени простой GUI направляет к полному API,
сохраняя исходные данные. Смена выбранного размещения перечитывает его поля.
Точный прогон и хеши — в [checkpoint исправления](../handoffs/rdg-placement-edit-repair-20261019/CHECKPOINT.md).
Native Windows/G2 и весь новый Gendocen context этим не подтверждены.

## Следующий результат и зависимости

Ранний сквозной путь на одном владельце уже проверен; межфайловой пакет
также завершён в локальном Candidate scope ниже. Следующий пользовательский
результат — настоящий ручной путь в установленном браузере Windows/G2.
Проверка нового Gendocen context остаётся отдельной задачей. Этот порядок
не меняет Desired Scenario, принятие версии или остальной согласованный scope.

| Этап | Проверяемый результат | Условие перехода |
|---|---|---|
| Локальный PASS, Candidate: экземпляр Action и история | Выполнен A1 → отозван A1 → выполнен A2 для той же R. Старое выполнение и отдельный отзыв сохранены; повторное выполнение A1 после правки отклоняется. | Проверены отдельное право отзыва, политики защищённых R, судьба дочерних R, snapshots, retry/recovery и финальный состав одного пакета. Новый прямой отзыв относится к уже выполненному Action; прежний reconsider_action сохраняет свои review-условия. |
| Локальный PASS, Candidate: размещение R и API | В существующем Plan owner доступны R/Action refs и place/unplace по времени или порядку, в том числе для предварительной ветви. | Проверены CAS, права, replay/recovery и снятие incident sequence/timeConstraints без правки графа. Нет скрытого выбора Action. Старые snapshots остаются читаемыми. |
| Локальный PASS, Candidate: однофайловое будущее и история | Новый read-only workflow-reader объединяет будущие размещения и историю графа в JSON, Markdown и HTML. Выполненное исключается из будущего, Plan не переписывается. | Проверены оба пути — с размещением и без него, исходные ID и owner refs, отказ при неверной ссылке/недостатке прав и отсутствие ложного успеха предварительной ветви. HTML — снимок, не живой редактор. |
| Локальная интеграция, Candidate: ручной Viewer/Helper 2.2.1 | Кнопки создания/правки, глубоких предварительных R/Actions с каноном/QRPE, размещения, выбора, результата и отзыва; общее будущее и история из действующих owners. | Сквозной controller → файловый/HTTP transport → настоящие writers проходит на временных источниках. DOM имитируется; это не native browser proof. CAS, отказ, retry и recovery сохранены. |
| Следующий пользовательский gate: установленный Windows/G2 путь | В обновлённом Viewer выбрать доступную папку явно запущенной локальной сессии и повторить тот же сценарий в настоящем браузере. | Проверить эффективный доступ к той же папке, native picker, читаемость и фактическую запись. Без новых mounts/ACL/туннелей и предположения о Docker-loopback. Установку и реальную пользовательскую запись этим срезом не объявлять. |
| Локальный PASS, Candidate: несколько владельцев в одном Graph root | Общий resolver projectionOf/expansionOf, две роли R, единый расчёт writer/reader, производные результаты и история в настоящих owners. | Прошли 19 новых межфайловых проверок: нет успеха при missing/ambiguous/cyclic/denied owner; проекции не дублируют исполнение; частичный journal блокирует read; read lock и source pins защищают состав. Нужны read scopes всех workspace-файлов identitySpace и права внешних производных записей. |

Уточнение пользователя 2026-10-19: будущее и история выполнения основаны на
**тех же R и Actions графа**. В будущем показаны размещённые невыполненные
сущности; после достижения R или выполнения Action эта же сущность показана
в истории как выполненная и больше не находится в предстоящем. Её ID, ссылки
и состояние на момент результата сохраняются. Запись выполнения в графе является
основанием этого перехода. Выполнение без размещения сразу видно в истории.
Само создание сущности по-прежнему не размещает её во времени автоматически.

Один Action — один экземпляр действия. Выполненный Action остаётся в истории;
правка графа не возвращает его автоматически в будущее. При переходе к другому
варианту по той же цели история сохраняет выполнение старого Action, его отзыв
и выполнение другого Action со своим ID. Сам выбор другого варианта не является
его выполнением. Это прямое уточнение пользователя; вопрос об автоматическом
возвращении выполненного Action в будущее снят.

Прежняя развилка PR-PC-03 между проекцией и отдельным закрытием шага —
**superseded этим прямым уточнением**. В текущей задаче не требуется отдельный
жизненный цикл закрытия шагов. Повторные физические исполнения были предположением
ассистента и исключены из текущего scope и условий перехода. Новая модель
повторений не вводится.

### Что реализовано и проверено в этом пакете

- `rdg-v7-model.py` сохраняет факт выполнения экземпляра Action независимо от
  поздних правок. Повторный `action_executed` для того же ID запрещён. Отдельный
  `currentScopeComplete` не позволяет старому результату автоматически доказать
  новый обязательный состав родительской R. Первоначальный basis/выходной набор
  и старое событие остаются неизменными.
- `withdraw_action` записывает отдельный отзыв уже выполненного выбранного Action
  через действующий writer. Это не заявление о прохождении Canon review или
  отмене внешнего физического результата. Старый `reconsider_action` сохраняет
  прежние review-условия; политики, shared-child и catalog guards не обходятся.
- `rdg-temporal-plan-owner.py` принимает place/unplace в существующей edit-транзакции;
  поддерживает requirementRef, права Plan, CAS, историю и recovery. Время или
  sequence задаются явно. Создание сущности графа ничего не размещает.
- `rdg-workflow.py` читает Plan и разрешённые графы через их locks/права, проверяет
  ссылки и строит общее будущее/историю. Не выбирает Actions, не переписывает Plan
  и не создаёт отдельный owner выполнения. Выполненный A1 не возвращается в будущее.
- `rdg-activity.py` показывает отдельные отзывы и исходные выполнения, сохраняет
  порядок событий одного пакета и даёт простые описания сохранений. Есть JSON,
  Markdown и читаемый HTML-снимок. В исходнике Viewer 2.1.0 добавлена общая ручная
  GUI-лента; контроллер проверен с реальными writers, установленный GUI ещё нет.

Новые тесты проверяют полный путь и безопасность отказов. Старые deep-action tests
согласованы с последним уточнением, сохранив проверки истории, двух ролей дочерних R,
обязательного состава, непустого выбранного decomposition и отсутствия ложных
промежуточных результатов. Это реализация нового уточнения, а не изменение
исторического review задним числом.

PR-DA-03 выполнен **частично**: actionType включён в проекцию зависимостей Gendocen;
Plan с R steps явно даёт `REQUIREMENT_STEPS_NOT_COVERED` / incomplete вместо полного
valid. Полный Canon-контекст ролей, дочерних R и нового workflow не доказан. Реальный
engine smoke именно нового scope не выполнялся; старые engine-наборы прошли
регрессию. До расширения claims требуется отдельное покрытие поддержанного контекста.

PR-DA-04 частично выполнен простыми описаниями сохранений и общей лентой
ручного раздела. Полная смысловая детализация всех сохранений не заявлена. Скрытие/приоритет истории остаются второстепенными.
Старые knownAt/effectiveAt эксперименты, новый сервер и production owner не являются
условиями следующего ручного пути.

### Новый ручной пакет — фактический scope

Viewer 2.2.1 подключает общий `rdg-workflow-ui.js`, встроенный штатным builder.
Без явной сессии предметные факты Viewer остаются read-only. Для Docker/Windows
основной путь — **папка сессии на уже разрешённом mount**, которую пользователь
явно выбирает picker. Helper запускается отдельной явной командой, использует
указанные Plan/Graph и тот же grant. Необязательный loopback adapter нужен только
если браузер уже видит его loopback; новых пробросов портов/туннелей нет.

Проверены через контроллер: A1 → размещение → выполнение → отзыв → A2, будущая R,
новая глубокая непринятая ветвь с subgoal и каноном/QRPE, разделение выбора и
выполнения, потеря ответа без нового действия, старый CAS и отказ без перезаписи.
Отдельно проверены две роли дочерних R через API, grant revoke, неподдельный MAC,
защита session/Origin/Host, pending Graph journal и частичный Plan write/recovery.

Ручное `by:user` здесь означает origin локальной opt-in сессии, а не verified
human identity. Обычный bearer не получает это право по одному полю события;
нужен точный process-local MAC с тем же principal, а прежние grants проверяются
writer. Protected R через этот Helper не меняются; admin UI/выдачи grants нет.
Прямой write-файл редактора фиксирован при запуске, но зависимости и история
читаются через авторизованную композицию owners. Явный projection-root continuation
может владеть новыми Actions для этой R; результат самой R сохраняется в её owner.
Plan без старых event/gate steps и branches; предварительные ветви **графа** разрешены. Сложный canon metadata
не теряется: его GUI-правка отказывается и остаётся в полном API.

Дальше не нужен ещё один общий перепланировочный цикл. Готовы два независимых
направления: установленный browser/G2 proof при реальном доступе к выбранной
папке и обновлённому Viewer. Межфайловой resolver уже реализован в указанном scope.
Native browser/G2 не выдаётся за проверенный. Полный новый Gendocen context остаётся
отдельным scope перед расширением claims; скрытие/приоритет истории второстепенны.

### Межфайловой пакет — фактический scope

Один `rdg-completion-context.py` обслуживает package writer и activity/workflow.
Сущность имеет одного semantic owner; continuation раскрывает ту же R через
точные expansionOf/projectionOf. Материал, ID и исходные события не копируются
в нового владельца. При выборе в continuation writer закрепляет определение
настоящей R в driverOwnerSnapshot, сохраняя прежний локальный driverSnapshot.

После дочернего результата writer рассчитывает финальную композицию и добавляет
готовые производные события в их owners в одном recoverable package. Новые файлы
записи не обходят grants: нужны graph.read на каждый загруженный workspace-файл
identitySpace и graph.record_action_execution / graph.record_requirement_achievement
либо graph.write для каждого нового производного результата, в том числе у owner,
который уже указан в запросе с обычной правкой. Нет права — нет новой частичной записи.
Обычный bearer не становится user, а projected R не обходит политику своего owner.

Shared read lock охватывает весь набор; exclusive writer lock, source/catalog pins
и финальная проверка grants защищают acceptance. Prepared journal содержит всех
изменённых owners и блокирует частичный read до recovery. Само физическое сохранение
нескольких файлов не объявляется одним atomic rename. Порядок фактов в истории
сохраняется через writer-owned compositionOrder одного завершённого журнала.

19 новых tests проверили обе роли R, непринятых предков, локальное display title,
недоступные права/owners, обход result permission через обычную правку owner,
неоднозначность и циклы, корректность policy по проекции,
повторные представления без второго исполнения, отзыв C → другой C2, неизменность
Action-instance после правки, смену источника перед acceptance, реальный shared
read lock, частичный crash/recovery и revoke после durable acceptance. Отдельно
контроллер GUI записал дочерний результат и показал достижения родителей через
настоящие writers; DOM по-прежнему имитируется.

Ограничения: один Graph root и опубликованный writer/catalog protocol, candidate-v6
workspace owners. Читается весь затронутый identitySpace, не минимальная dependency
ветвь. Legacy/prepared/read-only/cross-project context не импортируется как реальная
композиция. Новая запись старых снимков без нужного result event не выдумывается:
reader показывает unresolved/historyPending; material writer может сохранить готовый
производный результат. События и нормативная база прошлого не мигрируются.
Прямая raw запись вне common lock не превращается в поддержанный distributed/OS sandbox.

## Ранее выполненные технические срезы

Таблица ниже — inventory прежней работы. Незавершённый экспериментальный
gate не означает обязательную работу для плана во времени.


| Срез | Факт | Граница прежнего пилота |
|---|---|---|
| P0/P0.1 | Исправлены branch membership, независимая проверка полноты declaration/subscriptions и смысловых title для текущих проекций; scoped acceptance PASS. | Несколько событий, новый lifecycle и исторический контекст ещё не входят в coverage. |
| P1 | [Контракт owner/version/as-of](RDG-TEMPORAL-PLAN-OWNER-CONTRACT-P1.md) подготовлен как Candidate. | PR-P1-01..05 не committed; production owner и доверенный источник событий не выбраны. |
| P2 | [Совместный context v1](RDG-JOINT-CONTEXT-PILOT.md) связывает candidate applicability, точный baseline state, pinned Plan/RDG и один совместимый event claim по двум временам. Реальный Gendocen проверяет позднюю реконструкцию и сохранность раннего контекста. [Последнее evidence](../handoffs/rdg-joint-context-20261019/CHECKPOINT.md). | Scope — один Plan/branch/occurrence. Автоматический effective-time выбор принятых baseline, полнота остальных owners, trusted event source и проверка содержания evidence открыты. Старые journals без времени отклоняются. |
| P3 | Есть ограниченные F-R/F-U/F-O, F-P preflight, Canon context review и read-only Plan impact. | Полная семантика Finding/Proposal/Canon, независимое подтверждение F-P, несколько событий и различение позднего знания о T1 от изменения после T1. |
| P4 | Есть foundations рабочих/research-графов. | Сквозная передача между чатами, один смысловой owner при promotion/link, archive/retrieval и успешная проверка без искусственного Finding. |
| P5 | Есть исходники Viewer и синтетический Gendocen runtime proof. | Helper grants, Plan editor/timeline, читаемая Markdown-проекция, внешний consumer и отдельная проверка установки в Windows/G2. |
| P6–P7 | Удалённая запись и вывод legacy из эксплуатации не начинались. | Canonical GitHub owner/branch/writer, multi-file CAS/failure proof, проверка лицензии движка; затем доказанное замещение legacy. |

В предшествующем joint-срезе прошли 49 адресных тестов и совместный реальный Gendocen
smoke из 15 CLI-запусков со штатным Graph writer. Ранние candidate и точный
baseline context сохранились после поздних Plan/RDG/applicability/event
записей; новая реконструкция потребовала review. Проверены stale context,
отказ новому конфликтующему запросу и сохранность sources при чтении.
Прежние 88 тестов, event smoke 25 CLI и 405 Node относятся к предыдущим
срезам; полностью здесь не повторялись. Proof ограничен объявленным scope;
полная lifecycle applicability и фактический пользовательский T1 открыты.

При review v2 заново прошли 35 тестов: Plan owner, joint context,
branch acceptance и coverage guard. Последние source/dependency/evidence
хеши совпали с checkpoint до правки документации. Joint smoke 15 CLI
здесь не повторялся; его лог проверен. Наборы 35 и 49 пересекаются.

В последнем срезе закрыт P2-AC-04: два вхождения одного Action сохраняют
раздельный step/case context. Исправлена повторная регистрация review для
одного Action: регистратор объединяет зависимости всех его вхождений и
отклоняет неполный список. Прошёл 71 тест, включая новый acceptance из
21 CLI-запуска реального Gendocen. RDG не меняется; область — candidate
Plan и current-projection. Итог P2: 8 локальных PASS, 12 PARTIAL, 0 OPEN.

## Ближайший результат и порядок

Результат — два допустимых пути с общей историей:

- граф-модель → выполнение без предварительного размещения → история;
- граф-модель → явное размещение по времени/порядку → выполнение → история.

Размещение не является обязательным этапом выполнения. Реализовать оба пути
через существующие writer/API и ручной интерфейс. Новый сервер, production root
или миграция графов автоматически не назначаются.

1. **Локальный PASS, Candidate:** операции глубокого графа и reader/projection acceptance:
   подцели через Actions их создания,
   Requirements корректности от Action, потенциальные R под непринятыми Actions.
   Сохранить смысл subgoal/method_correctness и отдельный challenge; DERIVES
   не использовать как подмену причинного разбиения. Нельзя просто разрешить
   INTRODUCES для candidate: это изменит смысл актуальных связей и проекций.
   Явный путь теперь реализован: prepare_action_requirement / OUTCOME_OF,
   сохранение канонов/QRPE в глубоких ветвях, групповое принятие тех же ID,
   пересмотр предварительного набора, поддержка проекции Viewer и явного
   межфайлового продолжения. PASS относится к построению/чтению, а не ко всему
   lifecycle Action. Выбранное разбиение сохраняет непустой активный выходной набор;
   атомарная замена разрешена. Исходные legacy-файлы не мигрированы.
2. **Локальный PASS, Candidate:** запись/расчёт выполнения Action и достижения R
   с правами и историей для опубликованной candidate-v6 композиции одного Graph root.
   Листовые сущности оцениваются по определению; составные — по обязательным
   зависимостям выбранной композиции. Не выбранные варианты не блокируют
   выполнение, пустой список не означает автоматический успех. Создание
   подцели и достижение созданной подцели проверяются раздельно.
   Реализованы обе записи результата и расчёт по двум ролям внутри одного
   файла-владельца. Производные события сохраняются в истории; неизвестные
   зависимости не дают успеха. По PR-DA-01/05 исправлены три Problems review:
   снимок результата различает выходные наборы подцелей; выбранный decomposition
   не теряет последнюю активную подцель; автоматические результаты рассчитываются
   только на финальном составе пакета. Прежние явные результаты сохраняют свой
   scope. Дополнительная проверка ограничила actionType правилами узлов Action:
   одноимённые данные Requirement не меняют его тип. По последним уточнениям
   выполнена адаптация Action как экземпляра: правка не создаёт новое исполнение
   того же ID; отзыв сохранён отдельно. Локальный API-путь проверен; общий resolver и история owners
   реализованы и проверены. Native browser/G2 proof остаётся отдельным шагом.
3. **PARTIAL; API — локальный PASS:** явное размещение R и Action во времени
   или по порядку, включая предварительные сущности. Удобные place/unplace
   работают через существующий Plan owner с CAS, правами, историей и recovery.
   Пустое будущее разрешено; новые записи требуют места; старые snapshots и
   принятые retries читаются. Ручной контроллер размещений реализован в Viewer;
   native File System Access и установленный Windows/G2 путь ещё открыты.
4. **Локальный PASS, Candidate, композиция владельцев одного Graph root:** предстоящее связано с
   результатами в графе через `rdg-workflow.py`. Выполненное исключается из
   предстоящего, ссылки и история сохраняются. Выполнение без размещения видно
   в истории без фиктивного future step. Проверены A1 → отзыв A1 → A2 и правка
   после выполнения без возврата A1. Отдельного lifecycle закрытия шага нет.
   Межфайловой расчёт реализован через точные owning refs. Недоступный owner
   даёт отказ; готовый расчёт без сохранённого результата не выдаётся за историю.
5. **PARTIAL; общий reader — локальный PASS:** история изменений, достижений R,
   выполнения и отзыва Actions доступна в JSON/Markdown/HTML. Простые описания
   сохранений и порядок событий одного пакета проверены. Повтор запроса, отказ,
   dry-run и recovery не создают дублирующих результатов; неизвестные старые
   даты/авторы остаются неизвестными. Общая GUI-лента реализована в подключаемом
   ручном разделе; фактический установленный браузерный путь ещё не проверен.
6. **Второстепенно, не начато:** скрытие и понижение приоритета записей как настройка показа
   с возвратом полного списка; исходная история не удаляется.

Независимые однозначные исправления делать сразу, не ожидая завершения
всех шагов. Пункт 3 не требует предварительно реализовать весь расчёт
пункта 2. Объединять изменения там, где у них общие семантические зависимости.

Первое сквозное API-доказательство выполнено на временных владельцах; покрытие включает: пустую будущую часть, непринятую будущую ветвь,
Action без размещения, размещение только по порядку, выполнение без
предварительного размещения, незавершённую обязательную подцель, выполненную
выбранную композицию и листовой Action без искусственной декомпозиции.
Также проверены выполнение A1, отзыв A1 и выполнение A2 для той же цели;
все факты видны в истории с исходными ID. Служебная правка графа после
выполнения не возвращает A1 в будущее и не создаёт новое выполнение A1.
Проверены явные и производные результаты, отказ, повтор запроса и recovery;
повтор запроса означает идемпотентность записи, а не новое исполнение действия.

Дальнейшие P3/P4 и остальные задачи RDG сохраняют свои предметные gates.
Исторический joint resolver и его sidecars не являются предварительным
условием этого пути. Installed Windows/G2 proof, remote owner, публикация
и legacy retirement остаются отдельными этапами.

## Доказательства по версиям

В CPW-RDG-DEEP-ACTION-20261019/v1 прошли 206 Python и 407 Node tests,
включая 16 deep-action и 3 Viewer-сценария. Это предшествующая версия.
В CPW-RDG-COMPLETION-REPAIR-20261019/v1 заново прошли 213 Python и 407 Node,
включая 23 deep-action tests. Полный прогон относится к его точным исходникам.
В новом пакете прошёл широкий прогон: **226 Python + 407 Node tests**. После
добавления проверки порядка событий одного пакета и сужения прямого отзыва до
выполненного экземпляра отдельно заново прошли **13 workflow tests**; перед
последним сужением также прошли **24 deep-action tests**. Эти наборы пересекаются;
их нельзя складывать или выдавать адресный повтор за повтор всего прогона.
Точные исходники, логи, before/diff и границы — в новой
[контрольной точке](../handoffs/rdg-instance-temporal-workflow-20261019/CHECKPOINT.md).
Наборы пересекаются и не суммируются. Это локальное proof в Repo, не установка
Windows и не принятие Stage 4.

В ручном срезе заново прошли **239 Python tests**, а общий Node run содержит
414 cases: **413 PASS, 0 FAIL, 1 SKIP**. Пропущенный в общем Node run случай требует
живого Helper и отдельно выполнен внутри Python acceptance через оба транспорта.
После дополнительной защиты частичного Plan write выполнен адресный повтор
ручного набора; его точный результат и финальные хеши — в
[новом checkpoint](../handoffs/rdg-manual-workflow-20261019/CHECKPOINT.md).
Наборы пересекаются; это не сумма уникальных проверок и не native browser proof.

В межфайловом срезе после исправления проверки производных permissions заново
прошли **259 Python tests** в 24 наборах и общий Node run: **415 cases,
413 PASS, 0 FAIL, 2 SKIP**. Оба пропуска требуют живого Helper и отдельно
выполнены Python acceptance: обычный ручной путь через оба транспорта и
межфайловой controller-путь. DOM имитируется. В 259 входят **19 новых
межфайловых tests**; эти числа не складываются. Проверены также Viewer smoke,
синтаксис выбранных Python/JS и идемпотентная сборка встроенных модулей.
Первый Node run выявил два неполных списка зависимостей изолированных fixtures;
они исправлены. Дополнительный контрпример выявил обход result permission,
если owner уже указан с обычной правкой; он воспроизведён и закрыт до финального
полного прогона. Логи, точные хеши и diff находятся в
[межфайловом checkpoint](../handoffs/rdg-cross-file-completion-20261019/CHECKPOINT.md).
Установленный браузер/Windows и полное новое Gendocen coverage этим не подтверждены.

После PR-01 ручного размещения прошли **74 Python tests** в шести относящихся
к изменению наборах; общий Node run: **417 cases, 414 PASS, 0 FAIL, 3 SKIP**.
Три live-Helper случая отдельно исполнены Python acceptance: обычный manual путь
через HTTP/файлы, межфайловой controller и безопасная правка даты/порядка.
После последнего уточнения UI-селектора заново прошли **7 Python placement tests**
с живым Helper/writer и UI **7 PASS, 3 SKIP**; общий широкий прогон после этого
уточнения не повторялся. Независимые counterexamples review дали ожидаемую
сохранность порядка, deadline и strength. F-P-01/F-P-02 **устранены и проверены
локально в source 2.2.1**. Исторический Final Review v1 не переписан.
Точные исходники и логи — в [checkpoint PR-01](../handoffs/rdg-placement-edit-repair-20261019/CHECKPOINT.md).
Установленный Windows/G2 и acceptance версии остаются открытыми.

## Сверка с P2-AC-01..20

Это техническая сверка ранее исследованной матрицы, а не список обязательных
доработок плана во времени. После уточнения scope статусы 8 локальных PASS и
12 PARTIAL сохраняются как evidence; закрывать все PARTIAL ради плана во времени
не требуется. Исходный `PLANNED-NOT-EXECUTED` не переписывается.

| ID | Сейчас | Основание или следующий недостающий proof |
|---|---|---|
| 01 | Локальный PASS | Конфликт writable owner отклоняется в тесте Plan owner. |
| 02 | Локальный PASS | Traversal и symlink отклоняются без записи. |
| 03 | Локальный PASS | Candidate Plan write и сквозной smoke не выбирают и не переписывают RDG Action. |
| 04 | Локальный PASS | Два разных steps разных cases ссылаются на один Action; writer/reader сохраняют RDG bytes/status/events. Один Action review покрывает оба вхождения; срок каждого и смена membership требуют review A1, контрольный A2 остаётся valid; пропуск вхождения отклоняется. |
| 05 | Локальный PASS | Два процесса: один победитель CAS. |
| 06 | Локальный PASS | Revoke до durable prepared journal отклоняет запись. |
| 07 | Локальный PASS | Подстановка `accepted` или вызов `accept` через edit отклоняется; само принятие относится к 08. |
| 08 | PARTIAL | Joint context сохраняет точный baseline state после нового candidate; автоматическая lifecycle applicability, human acceptance и фактический T1 открыты. |
| 09 | PARTIAL | Candidate hard и технический будущий baseline не создают FR/F-P; независимый owner обязательства и applicability не доказаны. |
| 10 | PARTIAL | Date/instant/relative subset проверен; новые precision, units и выполнимость окна не доказаны. |
| 11 | PARTIAL | Клиентские actual fields в Plan отклоняются; отдельный event owner сохраняет unverified claim/attestation/review, но trusted source отсутствует. |
| 12 | PARTIAL | Plan editor и отдельный event-attest bearer не получают graph.select_action; сквозной пользовательский путь не проверен. |
| 13 | PARTIAL | Candidate applicability и event history сохраняют исходный claim, correction link и конфликт outcomes; нет trusted attestation и полноты контекста. |
| 14 | Локальный PASS | Точные Plan/RDG revision+digest обязательны, missing/mismatch/current fallback отклоняются. |
| 15 | PARTIAL | Ранний joint Plan/RDG/applicability/event bundle и Gendocen review сохраняются после поздних записей; полнота остальных owners и effective truth не доказаны. |
| 16 | PARTIAL | Поздняя joint-реконструкция требует review; ранний bundle и exact baseline сохраняются. Фактический T1 и автоматический accepted lifecycle as-of не подтверждены. |
| 17 | PARTIAL | Candidate, baseline и staged event journals/failpoints/recovery проверены; общий lifecycle и фактический T1 не испытаны. |
| 18 | PARTIAL | Старый adapter отклоняет sidecars. Joint-контракт проверяет snapshots, assessment и producer/declaration/subscriptions реальным движком в одном scope; расширенная coverage открыта. |
| 19 | PARTIAL | Exact Plan pin проверяется; bearer grant IDs и opaque evidence refs не считаются доказательством человека, содержимого или факта. |
| 20 | PARTIAL | Schema v1 и старый adapter сохраняют отказ; явные event/joint consumers v1 работают отдельно. Полная lifecycle-интеграция ещё открыта. |

Локальные основания: [P0/P0.1](../handoffs/rdg-p0-dependencies-20261018/CHECKPOINT.json),
[candidate owner и P2](../handoffs/rdg-vertical-slice-20261019/CHECKPOINT.json),
[точные snapshots](../handoffs/rdg-exact-history-20261019/CHECKPOINT.json),
[Graph knownAt](../handoffs/rdg-known-at-20261019/CHECKPOINT.json),
[Plan availableBy](../handoffs/rdg-plan-availability-20261019/CHECKPOINT.json),
[двухвременной rule probe](../handoffs/rdg-two-time-scenario-20261019/CHECKPOINT.json),
[owner history применимости](../handoffs/rdg-applicability-owner-20261019/CHECKPOINT.json),
[технический будущий baseline](../handoffs/rdg-future-baseline-20261019/CHECKPOINT.json),
[технические стадии события](../handoffs/rdg-event-lifecycle-20261019/CHECKPOINT.json),
[event context → Gendocen v1](../handoffs/rdg-event-gendocen-20261019/CHECKPOINT.json),
[joint context v1](../handoffs/rdg-joint-context-20261019/CHECKPOINT.json),
[два вхождения одного Action](../handoffs/rdg-shared-action-20261019/CHECKPOINT.json).
Полные статусы WR-01..53 сохраняются в [v4.1 ledger](../handoffs/rdg-prework-v4.1-final-20261018/WR-EVIDENCE-LEDGER.md);
новые checkpoints меняют только названный scope. При следующем срезе обновлять
эту таблицу вместе с доказательством, не повышая PARTIAL до общего PASS.
