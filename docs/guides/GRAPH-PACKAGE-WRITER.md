> **СТАТУС: АРХИВ / ИСТОРИЧЕСКАЯ РАЗРАБОТКА — НЕ ДЕЙСТВУЮЩИЙ КОНТРАКТ.** Включая файлы с именами `CONTRACT`, `PLAN`, `STAGE`, `PILOT` и со словом «актуальный» в тексте. Новый чат должен использовать [единую текущую спецификацию](RDG-CURRENT-STATE.md); ниже сохранены прежние эксперименты, решения и протоколы.

# Связанные R-графы: формат и восстановимая запись

Авторская семантика — work-kit/modules/rdg.work.semantics.module.md.
Target Module — целый план своей цели; Unit использует ту же механику меньшего масштаба.
Один graph.json раскрывает один основной R. R и D остаются разными узлами.

## Поля и владельцы

Новый рабочий граф: schemaVersion=1, revision, identitySpace, rootRequirementId,
planningScale=module|unit, nodes, edges, events.
В разных графах одно R/D имеет один ID. projectionOf={graphSlug,nodeId} указывает owner;
локальная подпись допустима, подмена requirementText/scope запрещена.
Создание Unit-файла не означает новый выбор и не создаёт decision_selected.

Готовое целое находится в read-only templateOnly графе.
preparedModule содержит id, version, goalRequirementId, methodDecisionId,
childRequirementIds, applicability, successCriteria.
D reusable-unselected; edges templateOnly; нет истории выбора проекта.
Полный источник хранится один раз; Unit ссылается через sourceOwnerGraphSlug/sourceAnchor.
Новая версия источника должна иметь отдельный owner/graphSlug: существующий binding сохраняет старую версию.

Конкретный выбранный D может иметь preparedModelRef:
graphSlug, id, version, goalRequirementId, methodDecisionId, sourceContentSHA256,
targetRequirementId, requirementBindings (source child ID → массив реальных child R IDs).
Цель применения должна реально drive этот D; child bindings соответствуют его INTRODUCES.
parameters могут уточнять конкретный случай, но их содержательная применимость проверяется отдельно.
Готовый модуль не обязателен для каждого D: собственный достаточный способ допустим.

## Формат package

Запуск:

    python3 tools/graph-apply.py --package --patch /absolute/path/package.json --dry-run
    python3 tools/graph-apply.py --package --patch /absolute/path/package.json

Пример формы, а не готовое принятое решение:

    {
      "schemaVersion": 1,
      "transactionId": "stable-choice-id",
      "changes": [
        {"file": "workspaces/project/graph.json",
         "patch": {"schemaVersion": 1, "expectedRevision": 3, "operations": []},
         "metadata": {"identitySpace": "project", "rootRequirementId": "R-ROOT", "planningScale": "module"}},
        {"file": "workspaces/project-unit/graph.json",
         "create": {"schemaVersion": 1, "id": "project-unit", "revision": 1,
                    "identitySpace": "project", "rootRequirementId": "R-CHILD", "planningScale": "unit",
                    "nodes": [{"id":"R-CHILD", "kind":"requirement", "title":"Узкая задача",
                               "projectionOf":{"graphSlug":"project","nodeId":"R-CHILD"}}],
                    "edges": [], "events": []}}
      ]
    }

Parent должен уже содержать тот же R-CHILD или вводить его в этом пакете.
При create файл должен отсутствовать; identity/root/scale обязательны.
Изменение уже установленной identity/scale не выполняется молча.
Новый committed D требует реальной санкции и decision_selected, а не только статуса в JSON.
Повтор использует тот же transactionId и тот же payload.

Обычный patch одного существующего файла сохраняет прежние --graph/--patch/--dry-run.
Поддержаны add_node, update_node, add_edge, append_event и revise_decision.
Произвольное удаление связей не поддержано.

## Пересмотр принятого D

Операция revise_decision:
id старого D; decision нового D с новым ID и status=committed;
edges новых INTRODUCES при необходимости; event с уникальным id,
type=decision_revised, decisionId нового D, previousDecisionId старого D,
by=user, note фактического принятого пересмотра.

Старый D становится superseded, его содержимое/scope/основания сохраняются.
Старые связи archived; новые DRIVES продолжают тех же драйверов.
Событие сохраняет previousDecisionSnapshot, previousEdges и driverSnapshots.
Новая версия готового модуля не переписывает принятое применение автоматически.
update_node по принятому D разрешает только verification/evidenceStatus/achievement/openQuestion;
DECISION_HISTORY_GUARD по-прежнему действует.

## Что гарантирует транзакция

До первого сохранения проверяются все revisions, графы, владельцы, версии и связи.
Writer-вызовы используют общую блокировку. После повторного чтения исходного состояния
сохраняется durable journal в graphs/workspaces/.transactions/.
Затем заменяются файлы, проверяется read-back и пересобираются index/bundle.
Журнал отмечается completed только после подтверждения.

Это восстановимая граница commit, не физически одновременный rename нескольких файлов.
При падении возможны частично обновлённые graph.json; опубликованный bundle остаётся прежним,
пока обновление не завершилось. Следующий apply сначала завершает подготовленный журнал.
Если чужая правка отличается от before и after, RECOVERY_CONFLICT блокирует перезапись.
Не обходите конфликт ручной заменой; установите фактическое состояние и согласуйте разрешение.
dry-run при подготовленном журнале сообщает RECOVERY_REQUIRED и не делает скрытых записей.

Повтор завершённого запроса возвращает ALREADY_APPLIED без дублирования R/D/events.
Тот же ID с другим payload — TRANSACTION_ID_CONFLICT.
Изменённый после commit результат — REPLAY_STATE_CHANGED, а не ложный успех старого запроса.

## Проверка результата

Прочитайте каждый затронутый graph.json: revision, реальные driver/child R, owners/bindings и историю.
Сопоставьте graphs/index.json и tools/rd-graph-data.js.
Для текущей версии обновите локальный Loader 2.5.2 / Viewer 1.8.0 и перезагрузите страницу ChatGPT. Это действие на пользовательском устройстве отдельно от проверок исходников.
Общая карта показывает TM; Unit-графы открываются из соответствующих R.
Проверка CLI/DOM не доказывает обновление установленного Tampermonkey или продолжение новым чатом.

При принятом применении requirementBindings покрывает весь declared childRequirementIds; изменения состава требуют явного собственного/адаптированного способа. Межфайловый цикл разбиения отклоняется до записи.

## Дополнение v7 — реализованные операции

В рабочих `graphs/workspaces` writer поддерживает `add_option`, `add_composite`, `append_composite_revision`, `append_qrpe`, `add_collection`, `select_option`. Принятие требует `decision_selected` с настоящим полномочием пользователя. Создание workspace: `rdg-new-workspace.py`; интерфейс Viewer не заменяет authoring. Подробная инструкция: [RDG v7](RDG-V7-WORKING-GRAPHS.md).
