# RDG: живой учебный Graph и его реальная история

> **СТАТУС: ДЕЙСТВУЮЩИЙ УЧЕБНЫЙ ПРИМЕР.** Его старые этапы со сменой переключателей и искусственным `C-ASSURANCE` находятся [в архивной хронологии](RDG-LIVE-TEACHING-WORKSPACE-HISTORY.md) и **не применимы** к текущему Graph. Общие правила — [контракт RDG](RDG-ACTIVE-CONTRACT.md).

Область этой страницы — прежний `candidate-v6` owner в Repo. Для серверного Decision UI и доступного пользователю примера свежей инвалидации см. [текущее состояние](RDG-CURRENT-STATE.md#проверенные-исходники-и-работающий-сервер). Это разные процессы и владельцы.

## Где искать

В Viewer: **Папки → Примеры → `requirements-dependencies-demo`**. Каталог вправе показывать учебный Graph в «Примерах», но **канонический редактируемый Graph owner** физически находится в `graphs/workspaces/requirements-dependencies-demo/graph.json`, а Plan — в `plans/requirements-dependencies-demo/plan.json`. Это нормальный `candidate-v6` Graph и настоящий `temporalPlanOwner`, **не** `workflowExample`, не второй тип модели, не ручная копия storyboard.

У Graph базовые R `R0`, `R-CANON`, `R-VERIFY`; Actions `A-DESIGN`, `A-DESIGN-ALTERNATIVE`, `A-CANON`, `A-CANON-ALT`, `A-VERIFY`. Итого **Graph revision 10, 8 R/A узлов**, графовая история содержит **10 принятых Graph writer транзакций**, 3 настоящих выбора Action и 1 переформулировку Requirement `R-CANON`. Новый **Plan revision 4** содержит пустую исходную версию + 3 отдельные версии размещения. Журналы Graph writer, события Graph и версии Plan дают **18 первичных provenance-записей**, показанных Viewer в **14 смысловых карточках** (техническая запись одного выбора сгруппирована с соответствующим событием). Значения отражают **текущий пересобранный пример**, а не универсальный контракт формата.

## Что проверить на экране

В полном обзоре «ГРАФ R» означает вход в локальный граф одной R. В локальном виде все связи данной волны показываются сразу **без** переключателя «Основные/Все». Переход к дочерней R открывает следующую волну. Никаких `Context` или `C-ASSURANCE` в текущем учебном Graph **нет** — прежние события о нём полностью удалены специальной пересборкой примера, не скрыты на экране.

В «План во времени» видно реальные Graph/Plan API-операции и размещённые элементы `R-CANON`, `A-CANON`, `R-VERIFY`; `A-VERIFY` выбран, но не размещён. В «Зависимости» настоящий Gendocen project `.rdg-gendocen-projects/requirements-dependencies-demo/` отслеживает **7 dependency targets**, включая **3 `review_required`**: `A-CANON`, `A-CANON-ALT`, `A-VERIFY`. Это предупреждения к переоценке после реальной reformulation R, **не** утверждение неправильности Action. Пересборка Graph **не** создавала `action_executed` и `requirement_achieved`.

## Живые API против offline-read-only

Работа/изменения требуют Graph/Plan bearer grants и штатного Helper; о том, как запустить Helper, см. [операционный регламент](RDG-OPERATIONS.md), там **одна** поддерживаемая форма команды. Для редактирования нужны отдельные scopes от чтения; учебный builder не меняет credentials пользователя. В Viewer без Helper опубликованный Plan/Gendocen/история — **read-only снимок реальных владельцев**, не текущая проверка.

**Как пересоздать корректный пример:** специальная команда на полный сброс **только для allowlisted teaching owner** находится в [единственной инструкции reset](RDG-TEACHING-EXAMPLE-RESET.md). Это отдельный исключительный lifecycle; обычные рабочие Graph owners не допускают стирания истории. Не смешивать его с обновлением всего Graph API.

## Проверка воспроизводимости

`tests/rdg-active-example.test.cjs` проверяет реальный Graph writer journal, запрещённую старую модель и соответствие опубликованного владельца. `tests/rdg-teaching-reset.test.cjs` — разрешения сброса и физическую чистоту новой истории. `tests/visual/rdg-graph-scope.cjs` — полное/локальное представление. `tests/visual/rdg-active-example.cjs` — реальный Graph/Plan/Gendocen через файловую сессию и loopback; `rdg-offline-published-owners.cjs` — offline read-only. Проверки исходников не означают, что Viewer установлен в пользовательском браузере или что принята Stage 4.
