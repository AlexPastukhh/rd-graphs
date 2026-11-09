> **СТАТУС: АРХИВ / ИСТОРИЧЕСКАЯ РАЗРАБОТКА — НЕ ДЕЙСТВУЮЩИЙ КОНТРАКТ.** Включая файлы с именами `CONTRACT`, `PLAN`, `STAGE`, `PILOT` и со словом «актуальный» в тексте. Новый чат должен использовать [единую текущую спецификацию](RDG-CURRENT-STATE.md); ниже сохранены прежние эксперименты, решения и протоколы.

# Temporal Plan — отдельный временной объект (Stage 2P, эксперимент)

**Статус:** кандидатная read-only модель; не committed RDG schema, не установленный Helper/Viewer и не плановый исполнитель. Источник: Candidate Pre-work v3, S-TEMP, SRU-11/12, WR-45..53, EA-30..36; пользователь явно отделил Plan от RDG и отверг `preselected`.

## Следующий контракт P1 — Candidate

[Owner/version/as-of](RDG-TEMPORAL-PLAN-OWNER-CONTRACT-P1.md) уточняет будущий
lifecycle и границы исторического знания. Этот документ P1 не расширяет
реализованную ниже schemaVersion=1: accepted future, Plan writer, фактические
события и исторические snapshots пока не реализованы. Результаты P0 находятся
в `../handoffs/rdg-p0-dependencies-20261018/`.

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

## Текущая граница записи будущего плана

Пустая будущая часть допустима: steps/sequence/branches/timeConstraints могут
быть пустыми. Наличие Actions в исходном графе не добавляет сюда шаги.
Plan owner при новой create/edit/branch записи вызывает validate_future_write:
каждый Action-шаг должен иметь явное timeConstraints либо участвовать в sequence.
Без этого возвращается TEMPORAL_PLAN_ACTION_STEP_NOT_PLACED без записи.
Только порядок достаточен; дата не выдумывается.

Структурное чтение старых schema-v1 snapshots сохраняется; уже принятый
transactionId повторяется идемпотентно с прежними правами. Новую версию
проверяет новое правило размещения. Общая история выполнения и размещение R
этим исправлением не реализованы. CLI inspect остаётся структурным reader,
а не доказательством, что старый snapshot прошёл текущее правило записи.

## Использование и проверка

Файл-пример: `docs/examples/temporal-plan-candidate-v1.json`. Он **иллюстративный**, его `actionRef` направлены в **синтетический** `workspaces/temporal-fixture/graph.json`, который создаётся только во временной директории тестов; в реальных графах проекта никаких обязательств нет.

```bash
python3 tools/rdg-temporal-plan.py --plan docs/examples/temporal-plan-candidate-v1.json
python3 tools/rdg-temporal-plan.py --plan /path/to/plan.json --graphs-root /path/to/graphs
python3 tests/rdg-temporal-plan.test.py -v
```

Без `--graphs-root` ссылки получают `verification: not-checked`. С указанным каталогом проверяются RDG `identitySpace`, ID и `kind: action`. Отсутствующий граф маркируется `missing-graph`, несовпавшая identity/тип — ошибка. Ответ содержит read-only `actionReferences`, `sequence`, `branches`, `timeConstraints` и `reviewLeads` с `requiresAssessment: true`, `findingType: null`. Это основания для будущей оценки канонов/Findings **относительно ветви и срока**, а не автоматически созданные F-P/F-R.

## Ограничения пилота и отложенные расширения

Исходный read-only пилот описан ниже исторически. Локальный guarded Plan
writer уже существует отдельно: [пилот P2](RDG-TEMPORAL-PLAN-OWNER-PILOT-P2.md).
Этот список не является обязательной очередью для текущего пользовательского
пути; актуальный scope и порядок — в [рабочем плане](RDG-CURRENT-EXECUTION-PLAN.md).

- Plan как полноценный отдельный **canonical owner**, writer с авторизацией и version/transaction history, доверенное подтверждение реального события и пересмотр временного плана.
- Конкретное вычисление календарной осуществимости/критического пути с effort, ресурсами, hard/soft constraints и conditional branches. Текущий валидатор проверяет структуру, но **не доказывает выполнимость графика**.
- Проверка всех межфайловых семантических связей R/C/Action, их истинности и полного происхождения; пока читаются только `Action` links и сигнал изменения revision.
- Взаимное обновление Plan↔RDG оценок Canon/Finding и адресные зависимости Gendocen; read-only output готовит основания, но не подменяет авторитетный review.
- Timeline/branch Viewer и автоматическое исполнение остаются отдельными кандидатными решениями; **никакой scheduler не запускается**.
