# Temporal Plan — отдельный временной объект (Stage 2P, эксперимент)

**Статус:** кандидатная read-only модель; не committed RDG schema, не установленный Helper/Viewer и не плановый исполнитель. Источник: Candidate Pre-work v3, S-TEMP, SRU-11/12, WR-45..53, EA-30..36; пользователь явно отделил Plan от RDG и отверг `preselected`.

## Граница и польза

RDG хранит Requirements/Actions, каноны, Findings, принятые решения и T1/T2/T3. **Temporal Plan** хранит будущие действия и события **во времени**: условные ветви, календарные ограничения и относительный порядок. Plan лишь **ссылается** на Action из RDG: составление Plan **не выбирает Action**, не создаёт событие `action_selected`, не исполняет его и не меняет исходный `graph.json`.

Stage 2P сознательно содержит только `status: "candidate"`. У него нет доверенного канала подтверждения фактического события, авторизации Plan write или движения accepted plans. Это не означает, что Plan в конечной архитектуре обязательно должен всегда быть кандидатом: принятие временного плана и подтверждение наступившего события требуют отдельного контракта Stage 3P/4. Временные ограничения из **кандидатного** Plan, даже с `strength: "hard"`, не становятся автоматически committed FR проекта.

## Минимальная схема

В отдельном файле JSON с `kind: "temporalPlan"`, `schemaVersion: 1`, `id`, `title`, `identitySpace`, `revision`, `status: "candidate"`:

- `steps[]`: стабильный `id`, `title`, `kind` (`action`, `event`, `decision_gate`, `milestone`), `state` (`planned`, `possible`, `expected`). В этом пилоте `event` **только** `expected`, с непустыми уникальными `outcomes[]`. Запрещены `preselected`, `performed`, `observedAt` и фиктивное подтверждение события.
- У `kind: "action"` есть `actionRef: {graphFile, identitySpace, nodeId, observedGraphRevision?}`. `graphFile` — нормализованный путь `workspaces/.../graph.json` **от каталога `graphs`**. Чужие или отсутствующие графы не подменяются новым смысловым владельцем. `observedGraphRevision` — только сигнал о возможном дрейфе, не транзакционный snapshot.
- `sequence[]`: `before`, `after`, необязательный `minDelayDays`; ацикличность обязательна. Относительная задержка после события не превращается в конкретную дату без фактического момента.
- `branches[]`: `eventStepId`, `cases: [{outcome, stepIds}]`. Каждый исход ожидаемого события покрыт ровно одним case; conditional `possible` step расположен после своего события и не принуждает исполнение другого взаимоисключающего case. Это **не** выбор активной ветви.
- `timeConstraints[]`: `stepId`, `type: deadline|notBefore`, `at`, `strength: hard|soft|hypothetical`, `basis`. Дата `YYYY-MM-DD` — календарный день, не момент времени; момент `YYYY-MM-DDTHH:MM:SS+02:00` требует явного смещения. `basis` — источник или пояснение заданного ограничения, **не** доказательство его принятия.

Реализация отклоняет неизвестные поля вместо молчаливого приёма якобы `selectedCase`, `actualEvents` или исполнения. Синтаксическая проверка `basis`, `state` и `actionRef` не равна проверке реальных обстоятельств.

## Использование и проверка

Файл-пример: `docs/examples/temporal-plan-candidate-v1.json`. Он **иллюстративный**, его `actionRef` направлены в **синтетический** `workspaces/temporal-fixture/graph.json`, который создаётся только во временной директории тестов; в реальных графах проекта никаких обязательств нет.

```bash
python3 tools/rdg-temporal-plan.py --plan docs/examples/temporal-plan-candidate-v1.json
python3 tools/rdg-temporal-plan.py --plan /path/to/plan.json --graphs-root /path/to/graphs
python3 tests/rdg-temporal-plan.test.py -v
```

Без `--graphs-root` ссылки получают `verification: not-checked`. С указанным каталогом проверяются RDG `identitySpace`, ID и `kind: action`. Отсутствующий граф маркируется `missing-graph`, несовпавшая identity/тип — ошибка. Ответ содержит read-only `actionReferences`, `sequence`, `branches`, `timeConstraints` и `reviewLeads` с `requiresAssessment: true`, `findingType: null`. Это основания для будущей оценки канонов/Findings **относительно ветви и срока**, а не автоматически созданные F-P/F-R.

## Оставшиеся этапы (не заявлять реализованными)

- Plan как полноценный отдельный **canonical owner**, writer с авторизацией и version/transaction history, доверенное подтверждение реального события и пересмотр временного плана.
- Конкретное вычисление календарной осуществимости/критического пути с effort, ресурсами, hard/soft constraints и conditional branches. Текущий валидатор проверяет структуру, но **не доказывает выполнимость графика**.
- Проверка всех межфайловых семантических связей R/C/Action, их истинности и полного происхождения; пока читаются только `Action` links и сигнал изменения revision.
- Взаимное обновление Plan↔RDG оценок Canon/Finding и адресные зависимости Gendocen; read-only output готовит основания, но не подменяет авторитетный review.
- Timeline/branch Viewer и автоматическое исполнение остаются отдельными кандидатными решениями; **никакой scheduler не запускается**.
