> **СТАТУС: АРХИВ / ИСТОРИЧЕСКАЯ РАЗРАБОТКА — НЕ ДЕЙСТВУЮЩИЙ КОНТРАКТ.** Включая файлы с именами `CONTRACT`, `PLAN`, `STAGE`, `PILOT` и со словом «актуальный» в тексте. Новый чат должен использовать [единую текущую спецификацию](RDG-CURRENT-STATE.md); ниже сохранены прежние эксперименты, решения и протоколы.

# RDG → Gendocen: покрытие зависимостей P0

Статус: Candidate, локальный синтетический пилот. Текущий контракт `rdg-temporal-review/v2`
применяется к текущим проекциям и не более чем одной условной ветви. Он проверяет
актуальность review, но не истинность Canon/Finding и не принятие Action.
Stage 4 остаётся NOT ACCEPTED.

## P0.1: дополнительный guard и смысловые title

Вычисляемые группы `identity/branches/steps/sequence/timeConstraints` сверяются
с declaration независимо от состава самого declaration, включая Plan без Actions.
Пропуск или неизвестная группа блокирует построение проекции до первого baseline.
`title` Action и шагов, включая ожидаемые события, входит в смысловую зависимость.
Отдельный display-only контракт пока не определён. Для versioned owner в identity
входит `sourcePath`; revision/digest сохраняются как provenance, но не превращают
локальное изменение A2 в глобальный review A1.
Точные snapshots Plan описаны в [пилоте P2](RDG-TEMPORAL-PLAN-OWNER-PILOT-P2.md).

## Что исправляет P0

В исходной v4.1 смена `positive → S-A1 / negative → S-A2` на обратное
соответствие не изменяла подписанные сроки, каноны и QRPE. Поэтому Gendocen
оставлял обе оценки в `valid`. Теперь адаптер выдаёт адресный контекст каждого
Action-step, а оба runtime runner используют один проверяемый регистратор.

Владельцами остаются RDG и Temporal Plan. `reviewInputsByStep`, `reviewNodesById`
и `reviewIdentity` — производные read-only поля, не второй источник записи.
После изменения исходников надо заново построить проекции. Engine не следит за
произвольными исходными JSON, которые не были перепроецированы.

## Источники, реально читаемые контрактом

| Область | Исходные поля проекции | Адресная подписка `exact` |
|---|---|---|
| Владелец RDG | identitySpace, graphFile, rootRequirementId, actionModel | graph#/reviewIdentity |
| Action | id, kind, title, status, canonBlock, qrpe, selectionBasis | graph#/reviewNodesById/{action} |
| Владелец Plan и ссылка | identitySpace, planId, planStatus, sourcePath, actionRefsByStep/{step}, включая observedGraphRevision | plan#/reviewInputsByStep/{step}/identity |
| Условие и принадлежность | branchesById/*/eventStepId, cases/outcome/stepIds; stepsById/*/state и outcomes | plan#/reviewInputsByStep/{step}/branches |
| Шаги контекста | id, kind, title, state, actionRef, outcomes у относящихся к оценке шагов | plan#/reviewInputsByStep/{step}/steps |
| Порядок и косвенные предпосылки | sequenceByPair/*/before/after/minDelayDays | plan#/reviewInputsByStep/{step}/sequence |
| Ограничения времени | timeConstraintsByStep/*/stepId/type/at/strength/basis | plan#/reviewInputsByStep/{step}/timeConstraints |
| Полнота | Версия контракта, scope, sourceReads, graphReads, complete | plan#/reviewCoverage |

Машинная матрица хранится в `READ_MATRIX` и `GRAPH_READS` модуля
`tools/rdg-gendocen-dependencies.py` и выводится в `reviewCoverage`.
Набор подписок содержит восемь адресов для одной оценки. Глобальный
`semanticSHA256` в подписках не используется.

## Как ограничивается контекст

Для каждого Action-step строятся сценарии, в которых он присутствует.
Активные шаги — общие шаги и шаги соответствующего case. В контекст входят
предшественники Action, его потомки, все активные deadlines и их предшественники,
а также условное событие. Это включает прежний общий delivery deadline.
Косвенные и впервые добавленные предпосылки обнаруживаются при новом построении
проекции; список зависимостей не замораживается по первоначальной топологии.

Поле `branches` содержит ID ветви/события, outcome и относящихся к контексту
участников case. `steps`, `sequence` и `timeConstraints` разделены по outcomes.
Изменение ограничения у исключённой альтернативы A2 не меняет контекст A1.
Общий deadline влияет на обе оценки. Все активные deadlines включены намеренно:
это консервативная граница текущего пилота, а не доказанная оптимальность области
влияния произвольного будущего semantic evaluator.

Порядок cases, outcomes, stepIds, шагов, sequence и ограничений нормализуется
адаптером. `revision` и заголовки Plan — метаданные для этого контракта.
Изменение содержательного поля, в том числе `minDelayDays`, state, ActionRef,
Action.status или selectionBasis, участвует в проверке.

## Несколько вхождений одного Action

Разные Plan step IDs могут ссылаться на один RDG Action, в том числе в разных
cases. Membership принадлежит шагу. Action остаётся одним смысловым объектом
в RDG. Для одного Action review регистратор объединяет подписки всех его
вхождений в данном Plan/RDG scope и регистрирует ровно одно правило.

В targets указываются все пары, например
`[("A1", "S-A1"), ("A1", "S-A2"), ("A2", "S-CONTROL")]`.
`build_action_contract` сверяет полный набор step IDs с ActionRef этого
graph owner/path/Action. Пропуск вхождения даёт
`ACTION_OCCURRENCES_INCOMPLETE`; повтор одной пары отклоняется.
`build_contract` остаётся низкоуровневым контрактом одного вхождения.

Новый срок любого из двух вхождений и смена их case membership требуют review
общего Action. Косметическая перестановка не требует review. Контрольный
Action вне этих cases сохраняет valid. [Acceptance и границы](../handoffs/rdg-shared-action-20261019/CHECKPOINT.md).

## Полнота и отказ

Перед регистрацией модуль пересчитывает производные поля из исходных полей
проекции, проверяет их совпадение, версию/scope и принадлежность ActionRef
конкретному RDG owner/path/Action. `assert_coverage` сравнивает ожидаемый и
заявленный набор подписок. Пропущенный, лишний или дублированный адрес блокирует
регистрацию. Две и более условные ветви помечаются `complete=false`; guarded
регистратор не позволяет подтвердить review для такого контекста.

Это защита от ошибки конфигурации в доверенном локальном коде. Она не является
OS sandbox и не защищает от намеренного обхода Python-регистратора или прямой
записи файлов. Другие consumers обязаны использовать этот контракт отдельно;
наличие нового поля в JSON само по себе не обновляет старые подписки.

При намеренно удалённой подписке на косвенную последовательность Gendocen
возвращает `current_project_code_unavailable` на `check`, а `validate` отклоняется.
`check` может сохранить диагностическое состояние недоступного регистратора.
Отклонённый `validate` не меняет это состояние и не создаёт receipt. После
восстановления полного контракта проверка и необходимый новый review выполняются
явно. Старый technical receipt не становится подтверждением полноты.

## Owner, revision и as-of

Resource IDs и graphFile/identitySpace квалифицируют owner. `build_contract`
возвращает provenance с текущими graphRevision/planRevision и заявленным
observedGraphRevision. Смена самой ссылки или observedGraphRevision вызывает
пересмотр соответствующего Action-step.

Режим — `current-projection`; `historicalSnapshotAvailable=false`. Изменение
только номера текущей revision не вызывает review остальных Actions. Контракт
не утверждает, что текущие данные были известны на T1, и не подтверждает
достоверность заявленной исторической revision. Архивные RDG/Plan snapshots и
полный owner/version lifecycle остаются отдельной работой P1/P2/P3.

## Повторная проверка

Из `/workspace/repos/rd-graphs`:

```bash
RDG_GENDOCEN_SOURCE=/workspace/repos/gendocen PYTHONDONTWRITEBYTECODE=1 \
python3 tests/rdg-gendocen-dependencies.test.py -v

RDG_GENDOCEN_SOURCE=/workspace/repos/gendocen PYTHONDONTWRITEBYTECODE=1 \
python3 tests/rdg-shared-action-occurrences.acceptance.test.py -v

RDG_GENDOCEN_SOURCE=/workspace/repos/gendocen PYTHONDONTWRITEBYTECODE=1 \
python3 docs/handoffs/rdg-prework-v4.1-final-20261018/tests/rdg-gendocen-branch-membership.acceptance.test.py -v
```

Новые тесты проверяют реальный Gendocen: cosmetic reorder, смену ветви,
A2-only constraint, косвенную sequence, первое ограничение предпосылки,
нового предшественника, ActionRef revision, Action.status, Canon, QRPE, общий
deadline и блокировку пропущенной подписки. Отдельные unit cases проверяют
неполную/устаревшую проекцию, неизвестную версию, owner mismatch и multi-branch.
Тесты создают только временные синтетические графы, Plan и review-файлы.

Текущие результаты, хеши, выбранные изменения и обновлённый WR-ledger:
`docs/handoffs/rdg-p0-dependencies-20261018/`. Исходный пакет v4.1 и его ZIP
сохранены без изменений как историческая контрольная точка.
