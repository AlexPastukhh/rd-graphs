> **СТАТУС: АРХИВ — ИСТОРИЧЕСКИЙ СНИМОК, НЕ ПРИМЕНЯТЬ К ТЕКУЩЕМУ RDG.** Новые чаты: см. [действующие правила](RDG-CURRENT-STATE.md). Ниже сохранены устаревшие описания прежних версий без переинтерпретации.

# RDG Requirements → Gendocen dependencies (актуальная модель source Viewer 2.4.8)

**Состояние для пользователя:** действующий контракт зависимостей описан ниже; комментарии «source 2.4.2/2.4.3» — записи о времени внедрения, не актуальные требования к установленной версии. Актуальный учебный пример: Graph r10, Plan r4, 7 Gendocen targets, 3 `review_required`. [Карта действующих правил](RDG-CURRENT-STATE.md).


## Источник истины и смысл предупреждения

**RDG Graph owner** хранит Requirement, Action, канон, авторизованные операции и фактическую историю Graph. **Gendocen** хранит *отдельные* dependency baseline, receipt, diff и журнал пересчётов. Plan остаётся собственным owner с независимыми placement и историей; никаких Requirements или Actions из Gendocen или Plan не создаётся.

Если R изменилась, Gendocen регистрирует `review_required` у тех проверяемых зависимых объектов, чьи **явные источники** изменились относительно принятого baseline. Это **не** автоматическое признание Action неверным, отмена выполнения, новый выбор Action или достижение цели. Владелец должен пересмотреть применимость, каноны и связанные R, затем дать отдельный review/подтверждение; движок сам не принимает semantic truth.

Переформулировка R выполняется в **том Graph, который владеет объявлением** (не в произвольном Plan). Новая штатная операция `graph_edit.action=reformulate_requirement` и прежний `edit_node` при действительном изменении узла Requirement формируют подписанное `requirement_reformulated` с `previousRequirementSnapshot`, `newRequirementSnapshot`, атрибуцией, revision и журналом транзакции. **История временного плана** показывает «Было / Стало» и переход к объявлению R. Предыдущие R и их архивные смысловые определения не исчезают из истории. Само изменение старшей R **не переписывает** автоматически уже выбранные Actions и подцели — они попадают на пересмотр по зависимостям.

У дочернего графа связь `projectionOf` указывает на **тот же canonical R owner**. Viewer уже может показывать актуальное объявление владельца поверх проекции при просмотре. Отдельный исторический файл проекции **не переписывается автоматически**: физическая синхронизация другого Graph owner должна проходить авторизованный writer и cannot bypass bearer. Подмена файла копией без проверенного cross-owner lineage не допускается. Недоступный owner/несовпадающая scope closure → ошибка, не «0 зависимостей».

## Подписки Gendocen

`tools/rdg-requirement-gendocen.py` преобразует *текущий авторизованный набор* `workspaces/**/graph.json` через `rdg-gendocen-adapter.py` в Gendocen resources (`rdg.graph.workflow-v1` — отдельный opt-in ресурс, старые resource IDs не меняются). Правила `semantic_review` регистрируются **в самом Gendocen**, по exact JSON pointers `resource://…#/nodesById/<R>`.

Покрываются текущие явно типизированные `DRIVES`, `DERIVES`, связанные `INTRODUCES`/`OUTCOME_OF`, `projectionOf` и ссылки в `canonBlock`, `contextChecks`, `selectionBasis`, `qrpe`/`contextUses`: `graph-node:<R>@<sha256>`, `checkRequirements`, `dependsOnRequirements`, `requirementId` и owner-qualified `{graphFile,identitySpace,nodeId}`. По отношению к downstream R/Action вычисляется достижимость. Простое вхождение букв `R0` в описании/тексте канона **не** является подпиской. Новые зависимости создают новый review target, который не может считаться «уже подтверждённым» только потому, что предыдущий target был valid.

**Граница охвата:** текущие Graph owners *одного* identitySpace из опубликованного локального `graphs/index.json`, прочитанные с теми же bearer rights. Нет автоматического сканирования чужих Gendocen projects/внешних приложений/недоступных владельцев или произвольного естественного языка. При неполной closure, неподтверждённом/двусмысленном owner или отсутствии Gendocen — **fail closed**. Выводы UI не доказывают отсутствия ссылок вне данного набора; `externalEvidenceCoverage=not-attested` и `completionTruthAttested=false`.

## Эксплуатация

Используйте существующие `RDG_AUTH_STORE`/`RDG_AUTH_TOKEN` (их значения никогда не передаются Viewer) и установленный код Gendocen из `RDG_GENDOCEN_SOURCE`. Запускайте тот же локальный Helper, что и для Graph/Plan, но с **явным дополнительным параметром** `--gendocen-project /путь/к/отдельному/gendocen-state`. При `--auto-workspaces` у каждого полного графа отдельный Gendocen project `<gendocen-state>/<rootSlug>`; при одиночном `--graph` используется указанный проект. Выбирайте **отдельный приватный каталог**, не Graph/Plan owner и не чужой Gendocen project. Helper записывает в Gendocen проект projections, зарегистрированные semantic rules, receipts, accepted baselines и события; Graph/Plan от этого не изменяются.

Каждая принятая через Helper операция изменения Graph запускает refresh Gendocen **после** подтверждённого writer commit; при ошибке движка Graph остаётся сохранённым, UI показывает отдельное предупреждение и требует повторной синхронизации. Вкладка **«Зависимости»** также пересчитывает текущий набор **по запросу/открытию** и позволяет выбрать весь граф или одну Requirement. Там видны статус, конкретная зависимая R/Action, использованный source R, причины/типы ссылок, changed input pointer и переходы в Graph. **История обновлений зависимостей** раскрывается по каждой карточке только по запросу, из настоящих Gendocen receipts/events; она не открыта по умолчанию. Сведения выбранной R/Action содержат переход в этот раздел и предупреждение, когда ранее прочитанный Gendocen результат содержит `review_required`.

Если Graph изменён вне Helper (через другой авторизованный writer), Gendocen не получает filesystem notification в этот момент; для этого случая нажмите **«Проверить зависимости»**. Это важная граница текущего автоматизма: **post-commit Helper + refresh on read**, не безусловный daemon/watch всех файлов/внешних Gendocen проектов. Прежний Gendocen `review_context_id` из `explain` используется при отдельном `validate --result still-valid` с причиной (в текущей реализации это операция движка, не кнопка с молчаливым подтверждением). Новые grants не выдаются, старые права не расширяются. Из окна Viewer невозможно «победить» stale простой сменой отображения.

## Проверки и статус

`tests/rdg-requirement-gendocen.test.py` запускает **реальный** `docengine.cli`: регистрация, validation с review context, изменение исходной R, `review_required` только у подписанного Action/подцели, сохранение прежних receipts, выявление explicit canon refs, отклонение incomplete catalog, отсутствие fabricated empty status, и изоляция принятой записи Graph от ошибки engine. `tests/rdg-general-graph-api.test.cjs` подтверждает подписанное событие «было → стало» в реальном Graph writer; `tests/rdg-workflow-ui.test.cjs` — историю временного плана. Браузерные tests/visual проверяют доступность третьей вкладки, явную ошибку без Helper и отсутствие регрессий Graph/Plan.

**Source 2.4.2 (2026-10-21); установленный Viewer 2.4.2 не подтверждён.** Это работа с кодом в локальном repo, а не миграция реальных рабочих Graph/Plan/grants. Формальная Stage 4 acceptance не заявлена.

## История введения offline read-only Gendocen — 2.4.3 (функция сохранена в 2.4.8)

Скриншоты **установленного 2.4.2** показали отсутствие и Plan, и Dependencies в браузере, хотя владельцы были созданы. В **source 2.4.3** добавлен **явный экспорт** (allowlist) только для активного `requirements-dependencies-demo`: canonical Graph и Plan SHA256 проверяются сборкой; Gendocen `report` и истории receipts берутся напрямую из движка; 18 событий истории — через штатный авторизованный workflow reader. Эти данные попадут в `tools/rd-graph-data.js` и откроются без доступа к `file://` и без Helper **строго для просмотра**. UI сообщает «ОПУБЛИКОВАННЫЙ СНИМОК, НЕ текущая проверка»; изменение R требует живого Helper для нового расчёта, подтверждения или записи. Переходы к существующим узлам Graph и раскрываемая история receipts доступны даже offline. Опубликованный снимок со старой ревизией Graph не подставляется в текущую версию. Версия **2.4.3 должна быть установлена отдельно** вместе с обновлённым встроенным graph-data bundle; пользовательская установка пока не подтверждена. [Полная инструкция](RDG-LIVE-TEACHING-WORKSPACE.md).

## Настоящий активный учебный Graph (2.4.2)

`graphs/workspaces/requirements-dependencies-demo/graph.json` и `plans/requirements-dependencies-demo/plan.json` — **обычные активные owners** с раздельными реальными CAS-журналами. [Последовательность операций через API, проверенная история, самостоятельный Plan и воспроизводимые Gendocen receipts](RDG-LIVE-TEACHING-WORKSPACE.md). Впервые подсистемы зафиксированы на одном persistent рабочем примере, а не только в отдельных unit fixtures. Старые `Decision/Option` остаются только offline архивами.
