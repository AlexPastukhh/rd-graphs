> **СТАТУС: АРХИВ — ИСТОРИЧЕСКИЙ СНИМОК, НЕ ПРИМЕНЯТЬ К ТЕКУЩЕМУ RDG.** Новые чаты: см. [действующие правила](docs/guides/RDG-CURRENT-STATE.md). Ниже сохранены устаревшие описания прежних версий без переинтерпретации.

# Requirements–Decisions Graphs — папки и полные Requirements-графы

**АКТУАЛЬНО (source Viewer 2.4.8):** [Короткая карта действующих правил, владельцев и проверки](docs/guides/RDG-CURRENT-STATE.md). Далее — журнал изменений по версиям; **все разделы ниже про версии 2.4.6 и старше исторические**, а их инструкции по UI и снимки Graph не являются сегодняшним состоянием.

Текущий исходный Viewer **2.4.8** (на присланных пользователем скриншотах установлен **Viewer 2.4.2**; установка **2.4.8** пока не подтверждена), Local Loader **2.5.2**: папки → полные Requirements-графы от корневой R → локальный R-граф одной волны. Полный граф поддерживает независимые «Принятое/Все ветви» и «Графы Requirements/Графы + Actions и каноны»; «Обновить» перечитывает текущие файлы и индекс, при недоступности оставляет явно помеченную встроенную копию. Расположение сохраняется отдельно и только с разрешённым доступом. [Актуальная инструкция](docs/guides/VIEWER-EXPLORER.md) · [граница R-графа и общий слой координат](docs/guides/VIEWER-LAYOUT.md) · [план и порядок реализации](docs/guides/VIEWER-EXPLORER-PLAN.md). В заголовке Viewer постоянно видна его версия. «Граф» и «План во времени» открываются отдельными вкладками; подключение папки сессии явно объясняет доступ и показывает ошибки Helper. История и план образуют одну вертикальную ленту с кнопкой перехода к первому запланированному блоку; палитра типов общая с графом, выполненные блоки ведут к месту объявления. Выбранная папка запоминается в браузере; открытие плана после перезагрузки восстанавливает подключение с сохранённым разрешением, либо предлагает дать доступ кнопкой в настройках. Учебный пример теперь — полноценный редактируемый `workspaces/requirements-dependencies-demo/graph.json` с собственным настоящим `plans/requirements-dependencies-demo/plan.json`; для **живой** проверки и записи нужен Helper; опубликованный read-only снимок реальной истории и Gendocen доступен и без него. Прежние учебные `workflowExample` хранятся лишь как архивные источники вне активного Viewer и не открываются для работы. Каноны видны над способами в полной подробной карте; история новых результатов хранит собственные снимки канона/QRPE. Обновление исходника не подтверждает обновления установленного Tampermonkey.

**Source Viewer 2.4.8 — учебный пример очищается полностью и создаётся заново, типы узлов ограничены:** активный `requirements-dependencies-demo` показывается в папке Viewer **«Примеры»** через catalog folder override; физический owner остаётся в `workspaces/*` ради настоящего API. Добавлен guarded reset `tools/rdg-rebuild-teaching-example.py`: **только** точный граф из `tools/rdg-resettable-examples.json`, подтверждение точным slug, проверка его отдельного Plan/Gendocen/журнала и отсутствия чужих зависимостей. После полного обнуления rebuild выполняет обычные Graph/Plan API операции; это новый Graph r10, Plan r4, 10 новых Graph writer commits и 18 настоящих событий источников, 14 основных карточек. Старые события добавления искусственного `C-ASSURANCE` физически удалены из учебного owner. Для обычных рабочих графов reset **запрещён**. Базовые типы блоков `candidate-v6` — **Requirement и Action**; дополнительные (например, `Context`) только через явный owner-scoped `tools/rdg-node-type-registry.json` плюс opt-in `nodeTypeExtensions`, не свободный `kind`. Локальный граф одной R без переключателя («все отношения»), переключение сохраняется лишь у полного графа. [Правила сброса и регистрация расширений](docs/guides/RDG-TEACHING-EXAMPLE-RESET.md). Новая установленная версия Viewer 2.4.8 пользователем ещё не подтверждена.

---

## История предыдущих реализаций (не текущая инструкция)

**Source Viewer 2.4.6 — переключение «Основные связи / Все связи и контекст» стало проверяемым на настоящем рабочем примере:** в `requirements-dependencies-demo` через **4 отдельные авторизованные Graph API транзакции** сохранены узел `C-ASSURANCE` (основание выбора) и три действительные связи `CONTEXT_FOR` с выбранными Actions `A-DESIGN`, `A-CANON`, `A-VERIFY`. Граф теперь **r14**, Plan owner остаётся r4; все фактические изменения появились в неизменяемом Graph writer journal, а Gendocen обновлён. В локальных графах `R0`, `R-CANON`, `R-VERIFY` основной режим показывает R→Actions, а **«Все связи и контекст (+1)»** дополнительно показывает `C-ASSURANCE` и ровно одну релевантную контекстную стрелку. Исправлена ошибка выхода за одну волну через общий Context: чужие Actions не притягиваются в локальный граф. Snapshot Plan/Gendocen переопубликован после реальных транзакций, **22 события provenance → 18 смысловых карточек**; ничего не переписано фиктивно, completion не приписан. Опубликованный snapshot не блокирует последующие авторизованные Graph edits: устаревший snapshot не распространяется до явной публикации нового. Chromium `tests/visual/rdg-graph-scope.cjs` проверяет все три R и переключатель A/B; Graph/Plan/Gendocen regressions PASS. Для результата в своём Viewer нужна установка source 2.4.6 и обновлённый `rd-graph-data.js`; текущая пользовательская установка не подтверждена.

**Source Viewer 2.4.5 — чёткое разделение полного графа и локального графа одной R:** R-блоки **только в полном обзоре** отображаются как «ГРАФ R · корень/текущий/возможный» с двойным контуром и доступным объяснением: это входы в одноволновые графы соответствующих Requirements, **не** новые Graph owner-файлы и **не** превращение R в другой вид данных. Клик по любому R в полном обзоре открывает её локальный граф; из обычного R-блока внутри локального графа можно перейти к её следующей волне. Переключатель состава **только в полном обзоре** назван «Графы Requirements / Графы + Actions и каноны». В локальном графе он означает **только** «Основные связи / Все связи и контекст» и не скрывает Actions. На обеих страницах выводится компактная подсказка о масштабе. Реальный Graph/Plan, Gendocen и критерии completion не затронуты. `tests/visual/rdg-graph-scope.cjs` проверяет полный и детальный режим, две локальные волны, наличие Action после обоих значений переключателя, возвращение к обзору и ноль ошибок Chromium. Установленная версия 2.4.5 не подтверждена.

**Source Viewer 2.4.4 — точная история событий Graph/Plan:** после замечаний пользователя о трёх одинаковых «Изменён граф», `rdg-activity.py` определяет смысл технической записи из **подтверждённого before/after Graph writer**: создан Graph, добавлен кандидат Action, создана/подготовлена/активирована/деактивирована Requirement и т. д. В `action_selected` добавлен список **действительно введённых R** из той же транзакции (созданы либо активированы из `potential/candidate`, с ролью `subgoal` или `method_correctness`). Viewer группирует техническое сохранение с содержательным событием в одну карточку и показывает `transactionId`, ревизии и изменённые узлы в раскрываемых сведениях. В учебном графе **18 неизменных записей provenance → 14 основных карточек**, три отдельно выбранных Actions; выбор не является выполнением, появление R не является её достижением/размещением. Старые Graph/Plan owners, Gendocen receipts и критерии completion не изменялись. Опубликованная offline read-only история **пересобрана через штатный авторизованный reader**, а не отрисована вручную. Chromium E2E проверяет типы событий, вложенные R и ссылки. Installed 2.4.4 ещё не подтверждена.

**Source Viewer 2.4.3 — устранены недоступные Plan и «Зависимости» без Helper:** скриншоты установленного 2.4.2 показали `PLAN_FILE_NOT_FOUND_OR_ACCESS_DENIED` и отсутствие connected Helper у рабочего `requirements-dependencies-demo`. Хотя **настоящие** `plans/.../plan.json` и Gendocen receipts уже существовали в репозитории, старый Viewer не мог прочитать их в удалённом браузере: Graph доставлялся через встроенный JS, а Plan запрашивался отдельно с `file:///C:/...`, dependencies требовали действующую сессию Helper. 2.4.3 по **явному allowlist** `tools/rdg-published-owners.allowlist.json` публикует из действительных владельцев read-only данные Graph r10 / Plan r4 / Gendocen 7 dependency rows + 7 receipt histories и 18 исторических событий от настоящего авторизованного reader. Файлы `tools/rdg-published-owners.json` и встраиваемые `rd-graph-data.js` обновляются через `tools/rdg-publish-readonly-owners.py` → `tools/graph-index.py`, строго сверяют graph/plan SHA256 на этапе сборки. Viewer при ошибке доступа к Plan берёт **только опубликованный снимок совпадающей версии**, не создаёт Plan и не записывает в файл. «Зависимости» без Helper показывает `review_required` в явно помеченном **историческом опубликованном снимке**, ленивую историю receipts и ссылки в настоящий Graph; кнопка не называется «Проверить» без живого движка. При наличии авторизованного Helper он остаётся приоритетным live-источником. Изменённый Graph с несовпадающей ревизией не использует старый снимок. Изолированный Chromium тест `tests/visual/rdg-offline-published-owners.cjs` подтверждает 18 исторических карточек, 3 зависимости, работоспособность перехода, history lazy и запрет stale binding при недоступном `file://` и Helper. **Установленная 2.4.3 не подтверждена:** для эффекта нужно обновить и Viewer, и сгенерированный JS data bundle, затем перезагрузить страницу.

**Source Viewer 2.4.2 — единая активная модель и живой учебный Graph:** только `candidate-v6` доступна из папок, upload, full-graph navigation и авторизованного writer; старые `Decision/Option`, `readOnly` и `exampleOnly` сохранены для отдельной офлайн-миграции, **ни один архивный граф не активен**. `requirements-dependencies-demo` построен последовательными штатными Graph/Plan API-транзакциями: Graph **r10**, 8 узлов, 4 фактических Graph events (3 выбора Action, 1 переформулировка R) и 10 принятых Graph writer commits; Plan **r4** с тремя настоящими размещениями; Gendocen хранит **7 receipts** и `review_required` у `A-CANON`, `A-CANON-ALT`, `A-VERIFY`. История Plan объединяет графовые операции/выбор, immutable версии размещений и «R было → стало», без фиктивного выполнения. Изолированный браузерный тест открывает обе вкладки и фактические Gendocen статусы; отдельный браузерный тест проверяет A→B→A для двух независимых `candidate-v6` Graph owners. [Как работать с учебным Graph/Plan](docs/guides/RDG-LIVE-TEACHING-WORKSPACE.md). **Исходники проверены; установка 2.4.2 пользователем не подтверждена.**

**Source Viewer 2.4.1 — Gendocen freshness:** на изменение Requirement через штатный writer пишется отдельный `requirement_reformulated` с предыдущим и новым снимком для History/Plan. Подключение Gendocen (`--gendocen-project`) добавляет третью вкладку **«Зависимости»**: точные real-engine subscriptions через каноны, Actions и подцели; `review_required` не выполняет автоматический пересмотр. Весь граф/одна R, навигация к R/Action, история receipts только по раскрытию; обновление после подтверждённого Graph write через Helper и при открытии вкладки. Без движка явная ошибка, без прав fail closed; другие Graph owners не переписываются. [Контракт](docs/guides/RDG-GENDOCEN-REQUIREMENT-DEPENDENCIES.md). Source-only, installed 2.4.1 ещё не подтверждена.

**Source Viewer 2.4.0 — упрощение управления:** сверху **ровно две главные вкладки**: «Граф» и «План во времени». Отдельный «Учебный план» удалён вместе со вторым путём его монтирования; для учебного графа та же вкладка автоматически показывает авторскую read-only ленту. «Назад» и «К полному графу» больше не дублируют breadcrumbs (продвижение внутрь/вверх остаётся через «Уровень выше»), «Основные связи» и «Связи и контекст» сведены в **«Связи: Основные / Все и контекст»**, видимость альтернатив переименована в **«Варианты: Все / Только выбранные»**. «Поиск», «Вместить в экран» и «Свернуть группы» — инструменты Graph; сведения о контексте, справка и **расположение блоков** внутри «Вид ⚙». Импорт/обновление/исходный модуль в **«⋯»** только при просмотре Graph; в Plan файловое меню скрыто. Черновики расположения называются координатами, а не черновиками Graph. Удалена устаревшая подсказка про «предварительный план». Регрессия: `tests/visual/rdg-viewer-controls.cjs` desktop/mobile (включая dropdown, overflow и viewport), прежние E2E Plan/Helper, autosave и Node Graph. **Исходники проверены; installed 2.4.0 не подтверждена.** [UX-контракт](docs/guides/VIEWER-EXPLORER.md).

**Source 2.3.9:** на всех запланированных и исторических карточках R/Action есть **«Открыть блок в графе ↗»**, переход к реальному объявлению Graph owner с выделением; из истории изменения Graph доступны точные ссылки на затронутые узлы (включая archived R), из `action_reconsidered` — на old/review/replacement/compensation. Исторический snapshot остаётся историческим; текущий Graph показывается отдельно. Возврат в Plan учебного графа больше не теряет `workflowExample`. [Навигация](docs/guides/RDG-LOCAL-GRAPH-PLAN-BINDING.md). Installed 2.3.9 не проверена.

**Source 2.3.8:** для смены Action опционально записывается целостная пара `A-old → A-new` и отмена последствий старого: оценено «без допдействий» или завершённый ранее компенсирующий Graph Action с подтверждением `action_executed`. Старый A, новый A, Action пересмотра и Action компенсации — разные роли; Plan не создаёт их. Reader/View истории показывает пару и результат, не маскирует пересмотр как простой отзыв. [Контракт](docs/guides/RDG-DEEP-ACTION-AND-HISTORY.md). Real writer/UI тесты, установленная 2.3.8 не подтверждена.

**Source 2.3.7:** события истории разделены на видимые категории **Результат / Состояние / Выбор / Изменение графа**, без смешения выбора с выполнением. У каждой R видны Option или Action-альтернативы с собственными канонами и QRPE; у размещённых Actions также видны другие способы этой цели. Архивный `reference-mixed-active-work` сохраняет модель Decision и ссылкой открывает отдельный Action-пример `reference-action-time-plan` (уже два запланированных Action с канонами). Plan не создаёт Graph R/Actions, UI блокирует размещение Action-кандидата до Graph selection, fake educational refs отвергаются. [Ограничения](docs/guides/RDG-LOCAL-GRAPH-PLAN-BINDING.md). Installed 2.3.7 не проверена.

**Source 2.3.6:** в «План во времени» три группы: история изменений/результатов (не смешивать правку графа с выполнением), явно размещённые во времени R/Actions и **«Без места во времени»** для актуальных сущностей, ещё не размещённых. Completion остаётся за Graph writer: `complete`, `currentScopeComplete`, зависимость выбранных Actions, `subgoal` и `method_correctness`, и `historyPending` не подменяются датой. Архивный **`reference-mixed-active-work`** теперь содержит учебный пример 5 событий изменений, 3 размещений R и неразмещённые цели — без выдуманных исполнений Action. [Пример и ограничения](docs/guides/RDG-LOCAL-GRAPH-PLAN-BINDING.md). Установленная 2.3.6 не проверена.

**Source 2.3.5 (точечное исправление UI):** архивные `exampleOnly/readOnly` full graphs, включая «Рабочий пример разбиения функциональности» (`reference-feature-root`), теперь показывают **«Учебный пример: запланированных шагов нет»**, а не вводящую в заблуждение надпись «Предварительный план». Такие архивные примеры не являются writable рабочими Graph owners; их авторская история/учебные размещения сохраняются, а реальный Plan для `workspaces/*` по-прежнему обязателен (нет файла → ошибка). Проверено browser E2E. Пользователь подтвердил установленную 2.3.4; 2.3.5 только source.

**Source 2.3.4:** один настоящий Plan owner `plans/<slug>/plan.json` на рабочий Graph. На авторизованном запуске Helper (`--auto-workspaces`) или однократном `--initialize-plans-only` отсутствующие Plans создаются штатным Plan writer **до первого планирования**, включая legacy `try-it` (для него записи размещений read-only до миграции Graph). Viewer для рабочих графов читает файл и отказывает, если owner отсутствует или неправильный; никакой «предварительный» Plan не выдаётся за сохранённый. [Инструкция](docs/guides/RDG-LOCAL-GRAPH-PLAN-BINDING.md). Installed 2.3.4 не подтверждён, реальные owner-файлы не создавались без grants.

**Новый source 2.3.3 (2026-10-20):** при выборе любого рабочего графа из «Папок» сразу показываются «История» и «План во времени» (возможен пустой будущий план), без требования Helper для просмотра. История предварительного режима ограничена доступными graph events; полные журнал и сохраняемые размещения — через Helper. `--auto-workspaces` для candidate-v6 рабочих корней сам связывает Plan и создаёт отсутствующие owner-файлы лишь через авторизованный writer; legacy try-it не мигрируется скрытно. [Граница и запуск](docs/guides/RDG-LOCAL-GRAPH-PLAN-BINDING.md).

**Новый source 2.3.2 (2026-10-20):** для нескольких больших рабочих графов предусмотрено явное сопоставление каждого полного Graph root с собственным Plan через `--contexts-file` Helper; Viewer переключает контексты вместе, не показывает чужой план при ошибке. Автоматических размещений не создаёт. [Настройка и доказательства](docs/guides/RDG-LOCAL-GRAPH-PLAN-BINDING.md). Installed 2.3.2 не подтверждён.

**Локальная доработка 2.3.1 (2026-10-20):** в явно включённой доверенной Helper-сессии добавлена панель просмотра, выдачи, изменения и отзыва bearer grants через существующий Authority API. По умолчанию панель выключена; Helper требует отдельный owner-admin токен в окружении при явном `--grant-admin`. Интерфейс не делегирует `grant.admin` другим клиентам. Токен новой выдачи показывается только в административном интерфейсе; штатный Graph/Plan writer и права не изменены. Отдельно добавлен консервативный opt-in Gendocen workflow contract для текущих Action/Requirement placements, двух ролей R, выполнения и отзыва; это **не** доказательство исторической истины или принятия Stage 4. Эти изменения пока **локально проверены на синтетических данных**, не установлены на пользовательском Windows Viewer 2.3.0. См. [текущий execution plan](docs/guides/RDG-CURRENT-EXECUTION-PLAN.md).

**Локальный контроль прав чатов (дополнение 2026-10-20):** штатный Graph/Plan writer выполняет запись по bearer и разрешённому scope чата. Режим административной сессии Helper включается отдельно и не предназначен для общего доступа обычных чатов. Исправлен показ результата успешной выдачи при сбое обновления списка. Gendocen `rdg-workflow-review/v1` теперь явно отслеживает `readOnly`/`expansionOf` через `graph_resource(..., workflow_context=True)` и отказывает для пока неподдержанного межфайлового контекста. Эти изменения не установлены на пользовательский Windows Viewer, Stage 4 не принят. Детали и реальные границы — в [текущем execution plan](docs/guides/RDG-CURRENT-EXECUTION-PLAN.md).

**Совместимость Gendocen (локальная правка 2026-10-20):** `rdg-gendocen-adapter.py --graph ... --workflow-context` создаёт отдельный ресурс `rdg.graph.workflow-v1.*`, а CLI без флага сохраняет прежний `rdg.graph.*`. Тест с реальным движком подтвердил одновременное использование и независимые receipts. Это не изменение версии/установки Viewer 2.3.1. Детали — в [плане](docs/guides/RDG-CURRENT-EXECUTION-PLAN.md).

Отдельное экспериментальное хранилище графов. Не является канонической методологией OBS и не заменяет действующие документы.

## Граф-модель и план во времени — актуальное назначение

Граф позволяет заранее проработать цели, Requirements и варианты Actions
без принятия предыдущих шагов. **План во времени** задаёт явное время и/или
порядок выполнения выбранных для размещения сущностей, в том числе предварительных.
Создание Action само по себе не добавляет его в будущую часть плана во времени.
Пустое будущее теперь допустимо; новый Action-шаг сохраняется только с явным
временем или порядком. Старые версии и принятые повторы запросов читаются.
[Исправление и проверка](docs/handoffs/rdg-temporal-review-fix-20261019/CHECKPOINT.md).

Человек работает вручную, ИИ — через API над теми же данными. Выполнение без
предварительного размещения попадает прямо в историю выполнения; фиктивный
будущий шаг не создаётся. Изменения графа тоже имеют историю, с отдельным
смыслом записи правки и записи выполнения.

В candidate-v6 реализованы глубокие предварительные ветви с канонами/QRPE,
тип Action `decomposition`, разные роли `subgoal` и `method_correctness`, запись
результатов и расчёт завершённости внутри файла-владельца. Action без подцелей
допустим, когда разбиение не оправдано действующими тремя критериями. Общая
история сохранений и результатов читается через CLI; Viewer показывает историю
результатов узла. Однофайловой сквозной путь дополнен: один Action — один
экземпляр; доступны явный отзыв, place/unplace R и Actions, единые будущее/история
в JSON, Markdown и HTML. Выполненное исчезает из будущего при чтении без новой
записи Plan; исходные ID и история сохраняются. В исходнике Viewer 2.2.1 доступен ручной редактор и общая лента через явно
подключаемый локальный Helper: выбранная папка сессии на существующем mount,
те же Graph/Plan writers, права и история. Контроллер прошёл сквозные тесты с
реальными writers; браузерный DOM имитируется. Установленный Windows/G2 путь,
native picker ещё не проверены. Межфайловой resolver candidate-v6 реализован:
общая обязательная композиция по projectionOf/expansionOf, права каждого owner,
история производных результатов в исходных файлах, общий lock/journal/recovery.
Проверен дочерний результат → достижение родительских R, без нового исполнения
через проекции. Scope — опубликованный identitySpace внутри одного Graph root;
для него нужны read scopes всех источников и права внешних производных записей.
[API и границы](docs/guides/RDG-DEEP-ACTION-AND-HISTORY.md).

[Определения и границы реализации](docs/guides/RDG-V7-WORKING-GRAPHS.md) ·
[Актуальный порядок работ](docs/guides/RDG-CURRENT-EXECUTION-PLAN.md).
Автоматический выбор baseline по двум временам и три стадии подтверждения
внешних событий не входят в обязательный scope. Скрытие/приоритет истории —
второстепенная функция показа. Прежние эксперименты ниже сохранены как evidence.

## Прежние технические эксперименты — Candidate

[Актуальный порядок исполнения и статусы P2-AC](docs/guides/RDG-CURRENT-EXECUTION-PLAN.md).
Исходный v4.1 остаётся владельцем определений и WR-ledger; актуальный план
показывает проверенное локальное продвижение и следующие gates.
[Двухвременное правило](docs/guides/RDG-TWO-TIME-SCENARIO-PILOT.md)
и [локальная история применимости](docs/guides/RDG-APPLICABILITY-OWNER-PILOT.md)
проверены на временных источниках: отдельный candidate owner сохраняет
утверждение об `effectiveAt`, его исправления и время доступности. Истинность
утверждения и полнота всех применимых источников ещё не доказаны.
[Контрольная точка](docs/handoffs/rdg-applicability-owner-20261019/CHECKPOINT.md).
[Отдельный технический будущий baseline](docs/guides/RDG-FUTURE-BASELINE-PILOT.md)
может закрепить точную candidate-версию без изменения Plan и выбора RDG Action;
самостоятельного подтверждения пользователя ещё нет.
[Новый checkpoint](docs/handoffs/rdg-future-baseline-20261019/CHECKPOINT.md).
[Три технические стадии события](docs/guides/RDG-EVENT-LIFECYCLE-PILOT.md)
сохраняют claim, attestation и review раздельно. Даже review-supported
не устанавливает фактическую ветвь или выбор Action. Старый Gendocen
adapter явно отклоняет такие sidecars до их семантической интеграции.
[Контрольная точка событий](docs/handoffs/rdg-event-lifecycle-20261019/CHECKPOINT.md).
[Явный event-контракт Gendocen v1](docs/guides/RDG-EVENT-GENDOCEN-PILOT.md)
проверен реальным движком: поздние записи требуют review текущего контекста,
а проекция с ранним `knownAt` сохраняется. Это scoped event review;
полный исторический Plan/RDG resolver остаётся открытым.
[Новая контрольная точка](docs/handoffs/rdg-event-gendocen-20261019/CHECKPOINT.md).
[Совместный context v1](docs/guides/RDG-JOINT-CONTEXT-PILOT.md) связывает
applicability, точный baseline, Plan/RDG snapshots и совместимый event claim.
Реальный Gendocen проверяет позднюю реконструкцию и сохранность раннего
контекста. Scope — один Plan/branch/occurrence; полный автоматический
lifecycle as-of и достоверность факта остаются открытыми.
[Совместный checkpoint](docs/handoffs/rdg-joint-context-20261019/CHECKPOINT.md).

Исправлены пропуск вычисляемой группы зависимостей из declaration и потеря
смысловых `title`: контракт `rdg-temporal-review/v2` отклоняет неполное покрытие.
Добавлен локальный guarded writer для candidate Plan с отдельными правами,
CAS, неизменной историей версий и восстановлением подготовленной транзакции.
Сквозной синтетический прогон с реальным Gendocen проверяет Plan → review → T1/F-R.
[Реализация и границы P2](docs/guides/RDG-TEMPORAL-PLAN-OWNER-PILOT-P2.md) ·
[P0.1/P2 контрольная точка](docs/handoffs/rdg-vertical-slice-20261019/CHECKPOINT.md).

**Предшествующий локальный срез:** [точные Plan + RDG и ограниченный `knownAt`](docs/guides/RDG-EXACT-HISTORY-PILOT-P2.md).
Точный candidate Plan и образы RDG разрешаются по закреплённым SHA и
завершённым журналам writer. Новый Plan owner сохраняет отдельную квитанцию
доступности после долговечной записи; для прежних Plan без неё остаётся
свидетельство следующей версии. Graph writer фиксирует время после сохранения
графа. [Контрольная точка доступности Plan](docs/handoffs/rdg-plan-availability-20261019/CHECKPOINT.md) ·
[предыдущая](docs/handoffs/rdg-known-at-20261019/CHECKPOINT.md).
Последующий joint context добавил candidate-выбор по `effectiveAt` и
исторический Gendocen в одном scope. Автоматический выбор accepted baseline
по effective-интервалам и фактический T1-as-of остаются открытыми.

[Review P0/P1](docs/handoffs/rdg-progress-review-20261019-v1/REVIEW.md)
сохранён как основание исправлений. Его F-P-PROGRESS-01 закрыт в локальном пилоте;
для F-R-PROGRESS-02 принята консервативная граница: каждый title входит в смысловую
зависимость. Технический будущий baseline реализован отдельно; человеческое
принятие, доверенные события и полный исторический as-of остаются открытыми.
**Stage 4 NOT ACCEPTED**.

[Проверка плана и продвижения v2](docs/handoffs/rdg-plan-progress-review-20261019-v2/REVIEW.md)
подтвердила сохранность последних исходников и evidence. P2-AC-04 теперь закрыт локально: один Action review объединяет зависимости
разных Plan steps и отклоняет пропуск вхождения. Новый acceptance прошёл
21 CLI-запуск реального Gendocen; общая адресная регрессия — 71 тест.
[Контрольная точка](docs/handoffs/rdg-shared-action-20261019/CHECKPOINT.md).
Эти результаты относятся к прежнему экспериментальному scope.
После уточнения пользователя ближайшая работа — ручной Plan, API для ИИ и ссылки.
P3/P4 и установленный Windows rollout сохраняют отдельные задачи и gates.

## P0 — зависимости условных ветвей (локальное исправление)

Текущий общий контракт `rdg-temporal-review/v2` (P0.1 после исходного v1): оба Gendocen runtime runner
используют адресные зависимости от ветвей, шагов, ActionRefs, последовательности,
косвенных предпосылок, сроков и данных Action. Пропущенная подписка блокирует
подтверждение. Контракт ограничен текущими проекциями и одной условной ветвью;
исторические snapshots полного RDG-контекста и production acceptance остаются открытыми.
Точные snapshots самого candidate Plan доступны в отдельном пилоте P2.
[Матрица источников, границы и команды](docs/guides/RDG-GENDOCEN-DEPENDENCY-COVERAGE-P0.md).
Результаты и WR-ledger P0: `docs/handoffs/rdg-p0-dependencies-20261018/`.
**Stage 4 NOT ACCEPTED**; старый v4.1 и его ZIP сохранены без изменений.

## P1 — Candidate-контракт Temporal Plan owner/version/as-of

Подготовлен [минимальный контракт](docs/guides/RDG-TEMPORAL-PLAN-OWNER-CONTRACT-P1.md):
owner/path binding, candidate и принятый будущий baseline, точность времени,
происхождение событий и исторический as-of. Это Candidate-дизайн для P2;
схема v1 остаётся candidate-only. Guarded writer реализован в пилоте P2;
future acceptance и event-attest ещё не реализованы.
Историческая передача P1: `docs/handoffs/rdg-p1-plan-contract-20261019/`.

## Экспериментальный bearer guard (2026-10-18, opt-in)

Добавлен `tools/rdg-authority.py` — отдельный **локальный эксперимент** по токенам для Graph API.
Токены выдаются через команды `init / issue / amend / revoke / list`; секрет возвращается только при выдаче, в grant-store сохраняется его SHA-256.
При явной настройке `RDG_AUTH_STORE` и `RDG_AUTH_TOKEN` пакетный writer дополнительно проверяет bearer-grant, scope и каждую операцию.
Без `RDG_AUTH_STORE` старый writer остаётся совместимым; это **не production enforcement**.
**Stage 1C (opt-in bearer):** клиенту нужен только `RDG_AUTH_TOKEN`; для material Action/legacy Option selection writer после проверки grant сам формирует `verifiedTrustReceipt` с principal вида `bearer:<grantId>` и SHA изменений. Клиентский HMAC-ключ не нужен. В старом режиме **без** `RDG_AUTH_STORE` прежняя проверка `trustedApproval`/HMAC для candidate-v6 остаётся обязательной и неизменённой. Bearer не доказывает личность человека или истинность evidence; материал с `by: "user"` обычным bearer отклоняется. Отдельный явно запущенный локальный Helper допускает ручное авторство только с точным process-local MAC и тем же grant; это не verified human identity и не protected approval. [Границы ручной сессии](docs/guides/RDG-DEEP-ACTION-AND-HISTORY.md).

`graph.create` теперь разрешает **только граф с кандидатами**: нельзя при создании сохранить `Decision.committed`, `Action.selected`, события принятия или неканонический импорт истории. Принятие требует отдельной операции (`graph.select_action` либо legacy `graph.select_option`) и отдельного grant; общие `add_node/update_node/append_event` не должны служить обходом. Работа по подготовке кандидатов, канонов и Finding не даёт права выбора.

**Точка отзыва:** Graph API удерживает grant-lock после финальной проверки до завершения записи. Долговечный журнал транзакции со state=`prepared` — **commit/acceptance point**: если отзыв прошёл раньше, новый пакет не сохраняется; если журнал уже записан, recovery завершает принятую транзакцию и после отзыва. Синхронизация охватывает локальные вызовы, использующие общий writer + authority store, а не raw filesystem/GitHub writes. Проверить сценарий можно `python3 tests/rdg-bearer-package.integration.test.py -v`, включая конкуренцию двух процессов.

Для безопасного локального эксперимента grant-store следует хранить **вне графов и синхронизируемых директорий** с ограниченным доступом.
`init` — локальный bootstrap доверенного оператора, не пользовательская кнопка Helper.
Локальный ручной UI не администрирует grants. Пока **нет** доверенного подтверждения личности пользователя, сетевого admin API, независимой полной проверки crash-recovery на всех fail-points, remote authorization и изоляции прямой записи в JSON. Protected approval через обычный bearer и новый локальный Helper недоступен; локальное ручное авторство не заменяет доверенную проверку реального пользователя.
Не используйте экспериментальный режим как защиту пользовательских или production-графов.
Применимость для нескольких чатов ограничена одинаково настроенным writer; это не механизм делегирования ОС или GitHub-полномочий.

## Temporal Plan — Stage 2P (самостоятельный временной план, read-only пилот)

Добавлена отдельная **кандидатная** модель `kind: temporalPlan` для шагов, ожидаемых событий, временного порядка, относительных задержек, условных ветвей и дедлайнов. План ссылается на существующие `Action` по `graphFile/identitySpace/nodeId` без копирования их смысла или изменения `Action.status`. Никакого `preselected`, автоматического `action_selected` и исполнителя здесь нет.

- Описание схемы/ограничений: [Temporal Plan — Stage 2P](docs/guides/RDG-TEMPORAL-PLAN-STAGE2P.md).
- Отдельный **иллюстративный** JSON, не пользовательский Plan: `docs/examples/temporal-plan-candidate-v1.json`.
- Только чтение и проверка: `python3 tools/rdg-temporal-plan.py --plan docs/examples/temporal-plan-candidate-v1.json`; с `--graphs-root /path/to/graphs` — разрешение ссылок. `not-checked`/ `missing-graph` не означают подтверждённую корректность ссылок.
- Тесты в синтетическом каталоге: `python3 tests/rdg-temporal-plan.test.py -v`.

Модель v1 содержит только candidate Plan и ожидаемые события. Она не утверждает временной план и не создаёт каноны/Findings автоматически. Подключение к Gendocen выполняет отдельный адаптер; запись версий — пилот P2. Даты и `hard` здесь являются предположениями для оценки. Ограниченный расчёт временных конфликтов реализован в Stage 3P ниже.

## Temporal Plan → RDG: Stage 3P (read-only impact pilot)

Есть отдельный проверочный `tools/rdg-temporal-impact.py`: для **кандидатного** Temporal Plan сопоставляет временные ограничения, одну условную развилку и существующие Actions из RDG. Для каждого выбранного *сценария расчёта* (не принятого Action) даёт основания для проверки сроков и `canonBlock`; допускает `--before-plan` и показывает **адресное изменение** в предпосылках A1/A2. Это **не** принятие ветви, не подтверждение исполнения, не автоматическое создание F-P/F-R/F-U, не полная оценка канонов и не production Gendocen dependency runtime.

Подробный scope/ограничения: [Stage 3P — Temporal Plan → RDG review signals](docs/guides/RDG-TEMPORAL-IMPACT-STAGE3P.md). Проверка: `PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-temporal-impact.test.py -v` — синтетические Plan+RDG файлы создаются только во временном каталоге. Текущий `Plan.status=candidate` и даже `strength=hard` отражают **предположения для оценки**, а не реальные обязательства проекта. При нескольких независимых условиях/событиях анализ пока явно отклоняется.

## Stage 2 — типизированные Findings (локальный пилот, не полный semantic contract)

В существующем `node.qrpe[]` теперь допускаются типизированные **Finding F-R/F-U/F-O** с областью `CURRENT/UPSTREAM`, вопросами, provenance и необязательной ссылкой на кандидатный Temporal Plan. Это **не** второй глобальный реестр и не Proposal или принятие Action. Для записи через пакетный writer служит отдельная операция `append_finding` и grant `graph.append_finding`; прав `graph.append_qrpe` недостаточно. Существующий `transition_qrpe` ведёт историю смены статуса. **F-P (подтверждённая текущая проблема) не создаётся** до независимого механизма проверяемой factual confirmation: само описание или дедлайн не доказывают реальную проблему.

Из Stage 3P можно только **подготовить на чтение** черновик F-R по конфликтующему кандидатному временному сценарию:
`python3 tools/rdg-finding-drafts.py --impact-report /tmp/temporal-impact.json`. Конвертер не вызывает Graph API и не создаёт Finding автоматически. [Контракт и ограничения](docs/guides/RDG-TYPED-FINDINGS-STAGE2-PILOT.md). Синтетические проверки: `python3 tests/rdg-bearer-package.integration.test.py -v` и `python3 tests/rdg-temporal-impact.test.py -v`. Полная semantic evaluation канонов, verified F-P, Gendocen runtime и installed Helper/Viewer остаются отдельными этапами.

## Stage 2 — проверка оснований положительных и отрицательных канонов (read-only)

Добавлен `tools/rdg-canon-context-review.py` — **проверка источников и актуальности явно заявленной оценки** отдельных канонов Action/Option. Она сверяет scope, `asOf`, `recordedAt` vs `effectiveAt` (T1/T2), сохранённые Context records с hash, revision исходного графа и content hash канона. Положительные и отрицательные случаи не усредняются; результат **`needs-semantic-assessment`**, он не утверждает истинность канонов и не создаёт F-P/Action selection. Кандидатный Temporal Plan подключается только как контекст конкретной ветви, без автоматического принятия.

Описание формата и запуска: [Stage 2 — Canon Context Review](docs/guides/RDG-CANON-CONTEXT-REVIEW-STAGE2.md). Тесты полностью на синтетических источниках: `PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-canon-context-review.test.py -v`. Полная семантическая истинностная проверка, verified F-P и реальный Gendocen runtime остаются открытыми.

## Следующий эксперимент: F-P evidence preflight (Stage 2)

Новый **строго read-only** `tools/rdg-problem-evidence-preflight.py` проверяет, что заявленные локальные контекстные данные для возможного **F-P** действительно найдены по `graph-node:ID@SHA`, актуальны по датам `recordedAt/effectiveAt`, scope и revision графа. Даже при полностью совпавших проверках результат **`mayAppendFP:false`**: независимое подтверждение реальности и доверенная пользовательская attestation ещё не реализованы, а bearer grant/hash не заменяют их. Прямая запись `F-P` в Graph API остаётся запрещённой. Документация: [F-P evidence preflight](docs/guides/RDG-PROBLEM-EVIDENCE-PREFLIGHT-STAGE2.md). Тесты: `python3 tests/rdg-problem-evidence-preflight.test.py -v`.

## Stage 1B — read-only Gendocen resource projections (RDG + Temporal Plan)

Адаптер `tools/rdg-gendocen-adapter.py` теперь выдаёт **различающиеся** ID ресурсов двух графов с одинаковым локальным `id`, отдельный ID для `Temporal Plan`, поля `nodesById` / `stepsById` / `timeConstraintsByStep` и смысловой hash, независимый от порядка JSON-массивов, когда порядок семантически не значим. Пример: `python3 tools/rdg-gendocen-adapter.py --plan docs/examples/temporal-plan-candidate-v1.json`. [Описание ресурсов и открытых ограничений](docs/guides/RDG-GENDOCEN-RESOURCES-STAGE1B.md). Проверки: `python3 tests/rdg-gendocen-resources.test.py -v`. **В owner environment пакет docengine не установлен.** Реальный Gendocen отдельно проверен на точных синтетических выходах текущего RDG-адаптера; установленный production runtime и Viewer пока не подтверждены.

## Gendocen 0.1.0.dev25 — real runtime proof (synthetic, isolated)

В изолированной среде с ранее приложенным архивом Gendocen подтверждено реальное адресное semantic_review: изменение только A2 затронуло A2, общий дедлайн — A1 и A2, изменение канона A1 — A1, устаревший review-context отклонён. Это выполнено **с синтетическими Gendocen-shaped ресурсами**, а не с рабочими графами. В tools/rdg-gendocen-runtime-smoke.py добавлен сценарий с выходами **реального RDG адаптера**. Этот абзац описывает ранний раздельный запуск; более поздний **co-located** запуск и проверка сохранённых receipts описаны ниже. Полная Stage 4 не принята.

[Детали и фактические ограничения](docs/guides/RDG-GENDOCEN-RUNTIME-SMOKE-STAGE1B.md).

**Усиленный тест Stage 4:** шесть состояний синтетических RDG/Plan сгенерированы текущим адаптером; реальный Gendocen проверил их в отдельном окружении (25 запусков, 5/5 сценариев). Обнаруживается адресное устаревание A1/A2, отбрасывается stale review context. Это **не** co-located deployment и **не** изменение рабочих графов. [Машинный протокол](docs/examples/RDG-GENDOCEN-OWNER-PROJECTIONS-REAL-RUNTIME-20261018.json).

## Stage 4 — совместный runtime RDG + Gendocen, проверено

В одном окружении /workspace/repos/rd-graphs и /workspace/repos/gendocen выполнен **реальный Gendocen 0.1.0.dev25** через tools/rdg-gendocen-runtime-smoke.py на синтетическом RDG и Temporal Plan. Пройдены адресные сценарии A2-only, общего дедлайна и канона A1, отклонён старый review_context_id. Проверено **сохранение двух dependency receipts, двух dependency events и dependency_state.json между запусками CLI**: повторный read-only check не меняет состояние, отклонённое stale-подтверждение не создаёт receipt и не снимает review_required. Фиксация результата: [Stage 4 co-located checkpoint](docs/examples/RDG-GENDOCEN-COLOCATED-RUNTIME-CHECKPOINT-20261018.json) и [подробные границы](docs/guides/RDG-GENDOCEN-RUNTIME-SMOKE-STAGE1B.md).

**Scope:** весь проект синтетический и временный; это НЕ установка Gendocen в RDG и НЕ production Stage 4 acceptance. User identity, factual F-P, авторизация Plan writes, аварийное восстановление и обработка реальных графов этим smoke **не проверены**. История T1, statuses Actions, пользовательские графы и установленный Helper/Viewer не менялись.

## Stage 4 — аварийное восстановление и история Gendocen (synthetic)

Расширен co-located runner tools/rdg-gendocen-runtime-smoke.py. Он прерывает Gendocen во время синтетической валидации (специальный код **91**), подтверждает блокировку чтений до recover, побайтовое восстановление state/receipts/events, отдельное событие аудита rollback, идемпотентный повтор recover и сохранение старой истории через публичный CLI history. Новое явное тестовое подтверждение добавляет ровно один receipt и одно событие. Синтетические RDG/Plan source-файлы не меняются. Это **не доказательство исторического T1**: в тесте ещё нет настоящего owner-created события T1. Машинный checkpoint: [Stage 4 crash/history](docs/examples/RDG-GENDOCEN-CRASH-HISTORY-CHECKPOINT-20261018.json); [подробный scope](docs/guides/RDG-GENDOCEN-CRASH-HISTORY-STAGE4.md).

## Stage 4 — T1 через штатный writer, QRPE after-T1 и реальный Gendocen

В изолированном synthetic workspace граф записан **штатным package writer** и bearer authority: отдельный grant создаёт Actions A1/A2, другой grant выполняет select_action и фиксирует event EV-T1, original candidate snapshot и selectionBasis. После этого два разрешённых обновления QRPE (F-R Risk, затем его status=resolved) вызывают **только A1 review_required**, не переписывая T1. Candidate Temporal Plan остаётся отдельным owner: гипотетическое ограничение A2 вызывает review только A2, общий deadline — обоих. Даже после специально вызванного Gendocen hard-crash (код 91) и recover исходные EV-T1, selectionBasis, состояние графа и история до сбоя неизменны; устаревшие review_context_id отклоняются. Это техническое test T1 от assistant bearer, **не подтверждённый human T1** и **не attested external T2/T3**. Пользовательские графы не изменялись.

Воспроизведение: PYTHONDONTWRITEBYTECODE=1 python3 tools/rdg-gendocen-t1-history-smoke.py --engine-source /workspace/repos/gendocen. [Документация Stage 4 T1/QRPE/Plan](docs/guides/RDG-GENDOCEN-T1-QRPE-PLAN-STAGE4.md); [машинный checkpoint](docs/examples/RDG-GENDOCEN-T1-QRPE-PLAN-STAGE4-20261018.json). Production acceptance Stage 4 ещё открыта: реальные user-authorized owners, production Plan lifecycle, доверенная factual attestation F-P и межграфовые жизненные циклы не реализованы.

## Полный handoff + исправленный Candidate Pre-work v4 (18.10.2026)

**Исторический execution срез v4 и передача:** [Handoff](docs/handoffs/rdg-prework-v4-20261018/HANDOFF.md), [полный Pre-work v4 с исторической v3](docs/handoffs/rdg-prework-v4-20261018/candidate-prework-v4-execution-reconciled.md), [короткая инструкция](docs/handoffs/rdg-prework-v4-20261018/README-NEXT-CHAT.md). Все документы и репродуктор открытого **Gendocen branch dependency bug** собраны в docs/handoffs/rdg-prework-v4-20261018.zip (18 файлов, включая исходный Final Review v1 и машинные checkpoints). ZIP — локальный артефакт, не Git commit и не GitHub publication.

**Историческое состояние до P0 (теперь исправлено локальным контрактом):** реальный Gendocen 0.1.0.dev25 оставляет A1/A2 review valid при перестановке stepIds между исходами условного Temporal Plan, если не меняются дедлайны или QRPE; это исходный P0 defect семантического dependency coverage. Stage 4 **не production accepted** несмотря на previous 405 Node PASS и успешные synthetic crash/receipt/T1-тесты. После P0 — Plan owner/writer, затем полная семантика Findings/Canons, S-WORK, Helper/Viewer.

## Окончательный handoff Candidate Pre-work v4.1 для другого чата

**Неизменный полный baseline v4.1 (2026-10-18); текущий execution delta — в контрольной точке выше:** docs/handoffs/rdg-prework-v4.1-final-20261018.zip. Новый чат читает сначала [HANDOFF.md](docs/handoffs/rdg-prework-v4.1-final-20261018/HANDOFF.md), потом [полный v4.1 + неизменную v3](docs/handoffs/rdg-prework-v4.1-final-20261018/candidate-prework-v4.1-execution-reconciled.md), затем [evidence ledger по WR-01..53](docs/handoffs/rdg-prework-v4.1-final-20261018/WR-EVIDENCE-LEDGER.md). Соседняя папка с прежним v4 — **исторический драфт, не текущий маршрут**.

**Исторический главный P0:** Gendocen branch-membership false valid. В v4.1 сохранён fail-first acceptance-test: на исходной версии = 1 PASS (cosmetic) + 1 **ожидаемый FAIL** (meaningful branch reassignment), и независимый diagnostic repro. Ни 405 Node PASS, ни прежние crash/receipt tests не закрывают этот семантический дефект. После P0 — жизненный цикл и guarded writer отдельного Temporal Plan; потом complete Findings/Canons, S-WORK и Helper/Viewer. Package **не** содержит Gendocen engine (его distribution license не подтверждена) и **не** содержит пользовательские графы, токены или live GitHub writes.

## Рабочие промпты и практическая проверка (актуальный набор)

Рабочий комплект: `work-kit/planning-helper-import.txt` — **1 bootstrap + 3 специализированных промпта + 9 общих модулей**. Инструкция: `work-kit/README.md`. Старт проверки в отдельном новом чате (без тестового промпта в Helper): `work-kit/START-TEST-CHAT.md`.

## Предыдущий экспериментальный комплект

Пилотный комплект: `kit/planning-helper-import.txt` (6 Prompts + 3 Modules). Его содержимое вставляют в текстовое поле **Import from ChatGPT → Import local**.
Пошаговая проверка в новом чате: `docs/guides/TRY-IT-WORKFLOW.md`.
Отдельный начальный граф: `graphs/workspaces/try-it/graph.json` (не путать с иллюстративным `graphs/examples/example/graph.json`).
Сохранение после явного выбора пользователя: `tools/graph-apply.py` с revision guard, dry-run и read-back.
Автотесты CLI: `node --test tests/graph-apply.test.cjs`.


**Два актуальных примера Viewer 2.0:** папка `Примеры` содержит один готовый и один рабочий полноразмерный root-R граф со встроенными Context/канонами. Шесть прежних маленьких context-файлов сохранены в отдельном архиве, пустые каталоги удалены. Подробности: [два цельных учебных примера](docs/examples/GRAPH-OF-GRAPHS-V7.md).

**Актуальная навигация Viewer 2.0:** в папке находятся полные графы от корневых Requirements. Главный обзор по умолчанию содержит только Requirements на всю доказанную глубину, включая продолжения вне папки. Для рабочего проекта есть «Принятое/Все ветви», независимо от детализации «Только Requirements/Показать всё»; клик R открывает локальную одноволновую схему. Старые graph-set manifests заменены derived root entries. Исполняемый Git-runner экспериментальных ветвей не входит в текущую версию. См. [RDG-V7-WORKING-GRAPHS.md](docs/guides/RDG-V7-WORKING-GRAPHS.md) и [VIEWER-EXPLORER.md](docs/guides/VIEWER-EXPLORER.md).

## Структура репозитория

```text
graphs/
  workspaces/             Рабочие графы: проекты и try-it
    try-it/graph.json
  examples/               Учебные примеры и переходы между уровнями
    example/graph.json
    reference-*/graph.json
  2d/                     Непринятые готовые 2D Target Modules и Units
    template-tm-2d-*/graph.json
  index.json              Автоматически собранный каталог

docs/
  examples/               Исходный файл примеров и карта покрытия
  2d/                     Сопоставление 2D-моделей с графами
  guides/                 Планы и результаты тестирования

tools/                    Viewer, Local Loader, генераторы и writer
tests/                    Автоматические проверки
work-kit/                 Рабочие bootstrap, PLAN, COMMIT и модули
kit/                      Старый пилотный комплект, отдельно от рабочего
```

**Физический путь** задаётся каталогом: вложенные папки допустимы. У каждого графа сохранён стабильный `slug`, отдельный от пути в `graphs/index.json`. Пользовательская точка входа — **полный граф по корневой Requirement**, вычисляемый из проверяемых причинных отношений, а не состав `graph-set.json`. Старые `graph-set.json` удалены после проверенной резервной копии; шесть ранних файлов Context перемещены в `graphs/examples/archive/`, остальные владельцы сохранены. Имя папки организует показ, но не ограничивает связи полного графа. **Переходы между уровнями** выводятся через неизменную идентичность Requirement: R введён ребром `INTRODUCES` в одном файле, а в другом — тот же R задан как `rootRequirementId` в общем `identitySpace`. Ссылки `relations[]` в индексе производные; ручные `nextGraphSlug`/`parentGraphSlug` не нужны. В `graphs/workspaces/` можно записывать реальные решения через `graph-apply.py`; примеры и готовые 2D-модели доступны только для чтения. Никогда не считай заготовку принятым проектным решением.

- `schemaVersion: 1`, `revision` (целое число), `nodes[]`, `edges[]`, необязательный `events[]`.
- `nodes[]`: id, kind (requirement / decision / context / question / variant), title, необязательные description/status/source.
- `edges[]`: id, type, from, to; для INTRODUCES обязательно поле parent (ID родительского Requirement).
- `events[]` сохраняет только реальные значимые события принятия / пересмотра; не журнал каждого изменения.
- Все ID стабильные. Не создавайте копии делегированного Requirement. Не путайте пример с принятым решением.

## Читаемые отношения в графе

В Viewer каждая стрелка имеет **подпись по смыслу**: например, «задаёт условия выбора», «передаёт содержание в D», «выявляет требование», «использует готовый вариант», «ставит вопрос к R или D» или «предлагает пересмотр». Нажми на подпись/стрелку, чтобы увидеть точный тип, источник, получатель и пояснение `meaning`. Легенда группирует отношения; по умолчанию включён режим **«Основная цепочка»**: только связанная с основной целью цепочка, с R слева, D дальше и под-R справа. **«Связи и контекст»** раскрывает остальные записи текущего графа в отдельных областях: основания/контекст, готовые варианты/применения, вопросы/пересмотр. Переключение не меняет JSON. При выборе стрелки остальные связи приглушаются, а оба её конца остаются видны. Стрелки используют отдельные точки входа и выхода и обходят другие узлы; подпись/инспектор сохраняет точное направление. При открытии большой граф не сжимается до нечитаемого размера; «Показать всю схему» даёт общий обзор: колесо прокручивает вверх/вниз, Shift + колесо — влево/вправо, Ctrl + колесо меняет масштаб; перетаскивание перемещает схему. Подробно: `docs/examples/RELATION-SEMANTICS-AND-VIEW.md`.

## Готовые 2D Target Module / Unit разбиения (не принятые)

В `graphs/2d/template-tm-2d-*/graph.json` добавлены 10 read-only заготовок из активного профиля IDTSPE 2D Visual Production: **38 исходных Unit Definitions**. Они не выбраны для текущего проекта, имеют пустую историю принятия и содержат полный оригинальный Markdown каждого Target Module. В Viewer: каталог → «Заготовка 2D …» → Unit → «Исходный модуль» для полного текста. Источники, ограничения и пересборка: `docs/2d/2D-TEMPLATE-GRAPHS.md`. Оригинальные файлы OBS и рабочие промпты этим преобразованием не меняются.

## Примеры и проверка модели

Первоисточник — переданный пользователем `requirements-decisions-graph-examples-v0.1(2).md` (внутреннее содержимое v0.2), неизменённая копия: `docs/examples/requirements-decisions-graph-examples-v0.2.source.md`.

Карта покрытия и ограничения физической схемы: `docs/examples/EXAMPLE-COVERAGE.md`; принцип межфайловой идентичности R и визуализация папки — `docs/examples/GRAPH-IDENTITY-AND-FOLDER-MAP.md`. В Viewer доступны три **только для чтения** учебные проекции одного иллюстративного приложения: `graphs/examples/reference-app-definition/`, `graphs/examples/reference-delegation-status/`, `graphs/examples/reference-behavior-review/`. Их не использовать вместо рабочего проекта и не считать неподдерживаемые вспомогательные ребра утверждённой схемой хранения.

**Семь связанных графов, каждый по одному R:** `graphs/examples/reference-complete-app/graph.json` — точка входа в 7 связанных R-уровней единого условного приложения. В нём **73 записи узлов, 73 связи и все 17 типов отношений, отображаемых Viewer**, включая фактическую декомпозицию, готовые `1..N` разбиения, Target Module и два применения, APPLIES_TO, INFORMS, выявленные R, проверку/пересмотр, события условной истории. **Из исходных 17 типов writer поддерживал 5; теперь дополнительно поддерживает `OPTION_FOR` и `OUTCOME_OF` (всего 7).** Прочие связи остаются учебными. Как пройти все уровни и проверить значения: `docs/examples/COMPLETE-REFERENCE-GUIDE.md`. Исходный пользовательский Markdown не изменён.

**Отдельная ранняя многоуровневая учебная демонстрация** (не из оригинала v0.2): `graphs/examples/reference-feature-root/graph.json` — корень «Описать приложение» с дочерним НЕЙТРАЛЬНЫМ R «Расписать функционал». По клику R открывается `graphs/examples/reference-reusable-vs-concrete/graph.json`, где **только теперь** можно выбрать готовое `PER_ITEM 1..N` через Feature/TM-FEATURE или другой способ. Условное D «через Features» вводит ровно четыре дочерних R; каждый из них по клику открывает свой следующий уровень с тем же ID. Подграфы скрыты из каталога как отдельные карточки; кнопка «← Уровень выше» ведёт назад. Новые `DEMO-*` — **условные данные, ничего не принято в реальном проекте**. Подробности: `docs/examples/EXAMPLE-COVERAGE.md`.

`graphs/examples/example/` остаётся небольшим smoke-примером (9 узлов), `graphs/workspaces/try-it/` — отдельным рабочим пилотом (1 исходная R). Новый bootstrap и PLAN указывают на источник через модуль `rdg.work.examples`.

## Просмотр в браузере

Local Loader 2.5.2 подключает локальные tools/rd-graph-data.js и tools/rd-graph-viewer.user.js через @require. Обновите внешние зависимости в Tampermonkey и перезагрузите ChatGPT. Откройте «Граф R–D»: проводник показывает папки, внутри — карточки полных графов от корневых Requirements; для старых одиночных файлов остаётся прямой локальный просмотр. Названия и назначение берутся из данных, без специальных переключателей для примеров.

В «Примерах» выберите подготовленный или рабочий учебный **полный граф**, а не прежний набор файловых блоков. Полный обзор показывает все доказанно связанные R; по умолчанию рабочий пример ограничен выбранным путём. «Все ветви» добавляет потенциальные R, «Показать всё» раскрывает варианты и D на доступной глубине. Нажатие R открывает её отдельный одноволновый граф. Учебный выбор D явно подписан как учебный, а не как решение основного проекта. В папке 2D находятся десять готовых полных root-R графов; прежние мини-примеры доступны в архиве.

Один раз подключите общий graphs/layouts.json и разрешите запись. После перетаскивания координаты сохраняются автоматически; дождитесь «Сохранено». Меню «Расположение» содержит паузу, немедленную запись, выбор файла, сброс и экспорт. Без права на запись показывается черновик; экспорт не считается записью общего файла. Пользователь и ИИ используют один слой команд и один формат координат.

После правки источников каталога выполните python3 tools/graph-index.py, затем в полном графе нажмите «Обновить», чтобы перечитать индекс и исходные файлы. Если доступ заблокирован, сохраняется предыдущая копия с явным предупреждением. Полный формат, ограничения параллельной записи и проверка доставки: [VIEWER-EXPLORER.md](docs/guides/VIEWER-EXPLORER.md). Windows-путь Loader проверяется отдельно от доступности Docker mount. Запрошенная HOST G2 проверка пути получила PermissionDenied; установленная Windows-интеграция пока не подтверждена.

## Процесс обновления через Fortis Repo
1. Прочитать `graphs/workspaces/<slug>/graph.json` и запомнить revision.
2. Определить существенные изменения; не переводить предложенное решение в committed без реального принятия.
3. Проверить отсутствие дубликатов ID, существование концов рёбер, смысл parent и источник решений.
4. Внести узлы и связи как одну согласованную операцию, увеличить revision на 1, добавить событие **только** при реальном принятии / пересмотре.
5. Валидировать JSON, снова прочитать файл; сообщить новую ревизию и что сохранено. Если revision изменился между чтением и записью — перечитать, не перезаписывать чужие изменения.
6. В просмотрщике перечитать JSON.

Для одного файла обновление проще, чем синхронизация отдельных nodes/*.json, relations.jsonl и events.jsonl. При росте графов формат можно мигрировать.

Демонстрационный пример `graphs/examples/example/graph.json` — иллюстрация, не данные реального проекта.

## Исправления 2026-10-13

Viewer 1.2.1 / Loader 2.4.0: свежий reload не откатывается к bundle, события проверяются до загрузки, реальные и условные журналы различаются. Подписи не перекрывают узлы и друг друга в геометрических тестах. В связанных графах R появились адресные источники границ Feature, одно общее D формы Behavior, разные локальные State, передача того же R конкретному Scenario и связанный локальный ответ ошибок с частями/условиями достаточности. projectionOf открывает владельца записи с возвратом назад. Writer отклоняет переписывание смысловых полей принятого D через update_node; разрешены только evidenceStatus, achievement, verification, openQuestion. Пересмотр с сохранением прежнего D, связей и driver snapshots реализован через revise_decision.

## Модуль и Unit — версия 2026-10-13

Viewer 1.2.1 / Loader 2.4.0: широкая карта TM, отдельные Unit-графы и рекурсивные переходы по R; без режима всех графов. В 2D — 10 модулей и 38 Unit-графов с прежними IDs и общим источником.

Семантика: work-kit/modules/rdg.work.semantics.module.md. Маршрут прямого/составного Unit: docs/examples/MODULE-UNIT-GUIDE.md. Запись пакета и история D: docs/guides/GRAPH-PACKAGE-WRITER.md. Доставка промптов: work-kit/README.md.

## RDG v7 — реальный проект, варианты и QRPE

[Руководство по рабочему графу](docs/guides/RDG-V7-WORKING-GRAPHS.md) · [длинный подготовленный пример](graphs/examples/reference-prepared-planning-tree/graph.json) · [условный смешанный пример](graphs/examples/reference-mixed-active-work/graph.json).

**Исторический первый этап Candidate v6 (read-only на момент его создания):** [исполняемые Lens с собственной R, QRPE и изменяющими Actions](docs/examples/RDG-ACTION-LENS-SEMANTIC-PILOT.md). Два примера и чистые проверки: `node --test tests/rdg-action-lens-semantic-probe.test.cjs`. **Исторический последующий read-only этап:** [сравнение Action identity PR-02A/B и канонов PR-03A/B](docs/examples/RDG-V6-ACTION-IDENTITY-CANON-COMPARISON.md), тесты `node --test tests/rdg-v6-stage3-comparison.test.cjs`. Сами эти ранние исследования не меняли `graph.json` или Viewer; позднее добавлен отдельный опциональный writer/Viewer для Action, не заменяющий `Option → Decision` для legacy-графов. **Более поздняя экспериментальная стадия:** [опциональная Action-модель в настоящем writer и reader](docs/examples/RDG-V6-ACTION-WRITER-READER-OPTIN.md), [полный тестовый graph.json](tests/fixtures/rdg-v6-action-optin/graph.json), `node --test tests/rdg-v6-action-writer.test.cjs`. Она работает только с `actionModel: candidate-v6` и **не мигрирует** старые графы; встроенный Viewer 2.0.3 поддерживает opt-in просмотр Actions, установленный браузер не проверен.

`tools/rdg-new-workspace.py` создаёт реальный пустой workspace только из указанной задачи пользователя, без решений. Writer поддерживает options/canons, композит/QRPE до принятия, коллекции и авторизованный `select_option`; Viewer показывает варианты независимо от «Связи и контекст». Остальные v7 функции приведены в руководстве как ограничения текущего пилота.

**Candidate v6 / проверенный ремонт целостности:** [защита R/Context, материальных Actions и QRPE, согласованный вывод Lens](docs/examples/RDG-V6-INTEGRITY-REMEDIATION-20261017.md). `candidate-v6` по-прежнему opt-in; для `select_action`, `link_action_requirement`, `reconsider_action` и закрытия QRPE нужен подписанный пакет. Подпись не доказывает личность пользователя; issuer пока не установлен. Legacy O/D и установленные Helper/Viewer не мигрированы.

**Candidate v6 / общий Graph API и выборочный персист Lens (изолированный source pilot):** [реализованные операции, semantic Lens, GitHub transport и ограничения](docs/examples/RDG-V6-GENERAL-GRAPH-API-AND-SELECTIVE-LENS-20261017.md). `graph_edit` использует обычный подписанный package без Lens-specific mutation; исследование Lens по умолчанию read-only и не сохраняется; generic parser проходит writer validation, protected parent/edges имеют scoped guards, а GitHub metadata-only lookup и explicit open доступны по opt-in. Реальный GitHub owner, grants, установленный Helper и полностью проверенный Lens evaluator пока **не подключены**. Тесты: `rdg-general-graph-api`, `rdg-general-lens-research`, `rdg-lens-cli`, `rdg-github-store`.

**Candidate v6 / ремедиация cross-plan consistency:** [исправления protected-parent, Lens validation, ценного pending persistence и metadata-only Git lookup](docs/examples/RDG-V6-CROSSPLAN-REMEDIATION-20261017.md). Нормативные решения пользователя и live GitHub owner остаются открытыми; source pilot не заменяет установленный Helper.

**Candidate v6 / следующий gated pilot:** [проверяемый транзакционный допуск и применение DRY/Maintenance Lens к настоящим graph.json](docs/examples/RDG-V6-LENS-TRUSTED-PACKAGE-PILOT.md), [DRY target](tests/fixtures/rdg-v6-lens-dry-target/graph.json), [Maintenance target](tests/fixtures/rdg-v6-lens-maintenance-target/graph.json). Аналитический вызов — без записи; изменяющий вызов — только через подписанный пакет и с разрешённым `Q-MAINT-EFFECTS`/сохранённой Lens Action. Реальной аутентификации пользователя ещё нет.

**Candidate v6 / новый writer-переход:** [пересмотр Action через обычный Action с собственными канонами/QRPE](docs/examples/RDG-V6-ACTION-RECONSIDERATION-WRITER.md) и [реальный синтетический `graph.json`](tests/fixtures/rdg-v6-action-reconsidered/graph.json). В этой ограниченной opt-in реализации обрабатываются общие и эксклюзивные R; MAC-пакет и локальные SHA-ссылки проверяются; личность пользователя и истинность внешних evidence не устанавливаются. Старые графы не мигрировались.

**Candidate v6 / Viewer 2.0.3:** [отображение Actions и read-only проверка последствий отмены](docs/examples/RDG-V6-ACTION-VIEWER-RECONSIDER-PREFLIGHT.md); полноценный пример `graph.json` остаётся тестовым, новый интерфейс не исполняет и не отменяет Actions. Установленную браузерную копию нужно обновить отдельно.

## Подтверждение решений и изменения контекста

Штатная запись D со статусом committed и событием выбора означает принятие. Внешний ключ/подпись Ed25519 и параметры approval-request/approval-receipt больше не нужны. Проверки ревизии, авторства записи, T1/QRPE, связей, журнала, восстановления и readback остаются. Историческая схема подписи отменена; описание процедуры: docs/guides/RDG-V7-WORKING-GRAPHS.md. ProjectContexts.records — инвентарь R/D/C; прежний поиск канонов с `--option-id` по-прежнему оценивает дату и scope записей. Для **текущих готовых полей** используй отдельный `--fields` без дат: заполненность определяется `contextValue`. Строковое checkCollections указывает на локальную Collection, ссылка на другую — структурная graphSlug+collectionId.

Автор material события может быть user или assistant, согласно фактическому происхождению осмысленной записи. Отдельной человеческой подписи не требуется.


## Контекстные поля и источники — 1.8.0

«Поля контекста» показывает объяснения со ссылками, один текущий `contextValue` либо пустое поле, актуальные и условные вопросы — без датированной истории заполнения. На графе графов «Просмотр контекста» меняет клик с перехода на инспекцию полей; общий блок доступен всегда. Два действующих полноразмерных учебных графа — `reference-prepared-planning-tree` и `reference-mixed-active-work` — включают Context и каноны; старые отдельные `context-prepared-*` и `context-working-*` находятся в архиве. Единственный контракт, команды ИИ/writer и DRY: §15 [рабочего руководства](docs/guides/RDG-V7-WORKING-GRAPHS.md). Установленный браузер не считается обновлённым только по исходнику.

## README.md snapshot — 2026-11-03 (superseded)

> **СТАТУС: АРХИВ.** This snapshot is preserved as it appeared before the current-entry rewrite. Its operational claims are date-bound; current state is in `README.md` and `docs/guides/RDG-CURRENT-STATE.md`.

# RDG — рабочие Requirements и Actions

> **СТАТУС: АКТУАЛЬНАЯ ТОЧКА ВХОДА.** Реализация — исходный Viewer **2.7.0**; версия установленного пользовательского Tampermonkey неизвестна. **Stage 4 не принята**.

**Fortis (срез 2026-11-03):** R7 Unified Gateway развёрнут; GO-1 provisioning, GO-2 owner WebAuthn enrollment и GO-3 Repo client RO mount завершены. Live Fortis Repo → R7 → Sonar READ/report → ASK/PENDING → owner WebAuthn Approve → `EXECUTED` → independent Sonar GET `ACCEPTED` подтверждён на реальных Issues. Текущий пилот: один actor / один закреплённый project / только `sonarcloud.accept_issue`. Не завершены отдельные расширения: background scheduler/workflow dispatch, multi-agent, RDG G3 и D1–D4 secure delivery. [Единое текущее состояние и реальные evidence](docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md) · [Карта Fortis source](fortis_approvals/README.md).

**RDG server на Fortis_M (отдельно от Fortis R7 Approvals):** gateway1 развёрнут пользователем; реальные Docker/PowerShell positive/negative checks, Windows HTTP и блокировка browser machine API прошли. Repo Docker работает через private gateway без bearer. Общим API создан «RDG — сквозная проверка API»: 25 блоков, четыре пересекающиеся WG, Plan A0–A17 без дат и сохранённые позиции. Проверены 53 preflight/receipt, шесть видов exact retry и новый клиентский readback; полная матрица, ручной Viewer и restart живого сервера ещё впереди. Прежние owners/credentials не мигрировались. [Порядок запуска](docs/guides/RDG-OPERATIONS.md#rdg--отдельный-сервер-на-fortis_m), [точные границы](docs/guides/RDG-CURRENT-STATE.md).

**UI этап:** исправление Decision desktop после ручной проверки 2026-10-29. Пользователь отклонил соответствие интерфейса прежнего архива принятому визуальному прототипу. В текущем коде восстановлены структура основного экрана, вложенные рабочие области в Explorer и общая временная дорога; убраны автоматическая `Main work` нового процесса и включение блоков в первую WG без указанной области. **Process Graph — весь процесс; Working Graph — явно созданная область по ссылкам на его блоки.** Существующие области/Plan/History не переделываются. Полная пользовательская UX-приёмка D7 остаётся открытой.

**Ручная проверка Decision:** [Start-Decision-Preview.cmd](Start-Decision-Preview.cmd), отдельная сохраняемая песочница, обычный браузер. Актуальная сборка имеет подпись `Decision UI · 20261029-fix2`: сразу полноэкранный Explorer, затем явный выбор процесса, его рабочей области или готового графа. Убраны повторные чтения каталогов при открытии панелей и переходе в фокус. Архив распаковывается в новую папку кода и использует прежние тестовые данные; точный [порядок запуска](docs/guides/RDG-OPERATIONS.md). Старый `Start-Preview.cmd` ниже относится к R/A/WebAuthn. Windows fix1 также устраняет блокировку при открытии каталога рекомендаций, из-за которой оставалась незавершённая панель «Graph · пакеты».

**Runtime D1–D9, срез 2026-10-28:** новый `rdg-decision-v1` подключён к существующему kernel/Application/authority/CAS/writer и основному generated Viewer. Plan v3, registry, templates/copy, projector/layout, фундаментальные линзы и изолированный restart/readback реализованы и проверены в описанных сценариях. Эти результаты не подтверждают полный перенос прототипа, установленный Windows Viewer, UX acceptance или Stage 4. [Точное состояние и свежие исправления](docs/guides/RDG-CURRENT-STATE.md), [единый план](docs/guides/RDG-DEVELOPMENT-PLAN.md), [контракт Decision v1](docs/guides/RDG-DECISION-V1-CONTRACT.md). Handoff 2026-10-28 и минимальный PR-6 сохраняют предыдущий срез и не являются новой очередью.


**Уточнения модели 2026-10-22:** явный rdg-core-v1 поддерживает общие A, R как требуемую истинность, повторное открытие и транзитивный stale. [Контракт и совместимость owners](docs/guides/RDG-ACTIVE-CONTRACT.md). Десять линз пересобраны; чтение линзы не является её применением.
**Рабочий чат — выполнить задачу через Graph:** [короткий bootstrap оператора](docs/guides/RDG-AGENT-BOOTSTRAP.md), затем каталог графов инструкций lenses, нужные определения lens и doctor/open через tools/rdg-agent.py. Изучать внутреннюю реализацию для начала работы не требуется.

**Линзы и core:** десять определений пересобраны в явном core-профиле. [Смысловая модель и учебный пример](docs/handoffs/rdg-action-canon-model-20261022/PROPOSAL.md) поясняют требования; поддерживаемые API и границы совместимости заданы действующим контрактом. Чтение или валидация линзы не доказывают правильность её применения.

**Portable-пакеты, 2026-10-23:** общий API и контроллер ready/copy/apply/detached, Plan/history/layouts реализованы в Repo. [Подключение Agent/Helper](docs/guides/RDG-OPERATIONS.md#переносимые-пакеты-agent-и-helper). Move папок/пакетов, opt-in migration и просмотр сохранённых Graph реализованы и проверены на временных owners. Доступный backend — Linux/POSIX; визуальная проверка браузера, Windows-перенос и установленный Viewer не подтверждены.

**Ручная проверка — приоритет 2026-10-25:** запустите `Start-Preview.cmd` из корня существующего Windows-репозитория. Он подготовит отдельное окружение и откроет основной Viewer с четырьмя тестовыми Graph: подтверждение, отказ, свободная правка и shared `info → Requirement` dependency. Проверьте регистрацию ключа, подтверждение/отказ, свободную правку и preflight/readback зависимости. Данные сохраняются отдельно в `%LOCALAPPDATA%\RDG-ManualPreview\data`; живые owners не подключаются. Изоляция и Windows durability остаются известными отложенными рисками и не блокируют этот ручной просмотр. [Запуск и границы](docs/guides/RDG-OPERATIONS.md).

**Подтверждения, срез 2026-10-24:** исходный portable Viewer показывает запрос, before/after и WebAuthn Approve/Reject. Добавлены регистрация по приглашению, сохранение открытого ключа и счётчика, отзыв и audit. Технический путь проверен с временными Graph/Plan, виртуальным ключом и перезапуском процесса. Реальный пользовательский проход ещё не подтверждён; Stage 4 не объявляется принятой по тестам.

**Отложенные идеи:** [потенциальные улучшения, пока не выполняются](POTENTIAL-IMPROVEMENTS.md). Это кандидаты, не принятое изменение требований.

**Исторические Fortis G0–G4 / P1 rollout snapshots** сохранены в архиве и в `docs/handoffs/`; их прежние next-step инструкции не являются текущими. Текущий рабочий статус задаёт только [Fortis current state](docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md).

**Оставшиеся Fortis-направления:** bounded workflow dispatch / scheduler, multi-agent grants, RDG G3 и D1–D4 protected delivery. Они не блокируют уже работающий одноакторный Sonar READ/ASK/Approve сценарий. См. [текущее состояние и точные границы](docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md).

**Разработка самого RDG:** [инструкции разработчику](AGENTS.md) → [текущее состояние и владельцы правил](docs/guides/RDG-CURRENT-STATE.md) → применимый раздел [рабочего плана](docs/guides/RDG-DEVELOPMENT-PLAN.md). Исторические материалы собраны отдельно в [карте документации](docs/README.md).

Рабочая модель Graph: `candidate-v6`, базовые блоки **Requirement (R)** и **Action (A)**. В явном core-профиле context/canon/info/evidence входят в закрытую схему objects; прежний профиль допускает только собственные зарегистрированные расширения. WIP-модули этим не подключаются. Graph writer, Temporal Plan и Gendocen — разные источники истины. Выбор Action / размещение в Plan / событие выполнения нельзя отождествлять.

В Viewer прежний профиль использует полный обзор «ГРАФ R» и локальную волну со всеми её связями. Явный core имеет собственные фокусы R, A и канона; его границы и явное происхождение выходных R описаны в контракте. Выход A не раскрывается в графе исходной R как непосредственная под-R. Живое чтение/запись требует авторизованного Helper; опубликованный bundle — read-only snapshot.

Текущий учебный `requirements-dependencies-demo` виден в **«Примерах»**, но канонический owner находится в `graphs/workspaces/` для штатного API. Его разрешённая пересборка **с нуля** не является способом удалить историю обычного рабочего проекта.

**Модули — в разработке, контракт нестабилен.** В задачах вне модульной подсистемы её не расширять и не перестраивать попутно; [текущий охват и границы](docs/guides/RDG-MODULES.md).

**Куда переходить:** [план дальнейшей разработки](docs/guides/RDG-DEVELOPMENT-PLAN.md) · [контракт сущностей и ответственности](docs/guides/RDG-ACTIVE-CONTRACT.md) · [Viewer](docs/guides/VIEWER-EXPLORER.md) · [операции и диагностика](docs/guides/RDG-OPERATIONS.md) · [учебный Graph/Plan/Gendocen](docs/guides/RDG-LIVE-TEACHING-WORKSPACE.md) · [учебный reset](docs/guides/RDG-TEACHING-EXAMPLE-RESET.md) · [карта архивов](docs/README.md).

## Репозиторий разработки

Корень Git-репозитория — этот каталог `rd-graphs`. Здесь вместе хранятся приложение (`tools/`), тесты (`tests/`), документация (`docs/`), исторические наборы инструкций (`kit/`, `work-kit/`) и существующие Graph/Plan с журналами и состоянием Gendocen.

Правила `.gitignore` исключают кеши, файлы блокировок, временные профили браузера и приватные Helper-сессии. Секреты и store авторизации должны оставаться вне корня проекта. Правила `.gitattributes` сохраняют точные байты файлов без преобразования переводов строк: история и evidence используют хеши содержимого. Git сохраняет версии файлов; принятые операции Graph/Plan по-прежнему выполняются штатными writers с авторизацией и их собственными журналами.

После этапа выполняется [обновление действующих документов и очистка](docs/guides/RDG-OPERATIONS.md#завершение-этапа-и-очистка). `.ignore` убирает архивные каталоги из обычного поиска `rg`, сохраняя их в Git и по прямым ссылкам. Список действующих документов: `python3 -B tools/rdg-docs-audit.py --list-active`.

<details>
<summary>История проекта</summary>

[Полный handoff-снимок](docs/handoffs/rdg-system-onboarding-20261022/HANDOFF.md) и [хронология README](README-HISTORY.md) описывают прошлые срезы. Их сведения проверяются по действующим источникам; они не задают текущую реализацию.

</details>
