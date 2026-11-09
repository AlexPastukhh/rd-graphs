> **СТАТУС: АРХИВНЫЙ ПРИМЕР — НЕ АКТИВНАЯ МОДЕЛЬ.** `Decision/Option`, старые каталоги и команды ниже относятся к историческому корпусу, их нельзя выполнять как текущий `candidate-v6`. Новый чат: [текущая спецификация](../guides/RDG-CURRENT-STATE.md).

# RDG Candidate v6 — Action в настоящих writer и reader (изолированный opt-in)

**Статус:** CANDIDATE IMPLEMENTATION / LIMITED OPT-IN / NOT COMMITTED as project semantics.  
**Источник:** [Candidate Pre-work v6](https://github.com/AlexPastukhh/forfiles/blob/main/artifacts/2026-10-16/candidate-prework-rdg-executable-lenses-no-extra-dependencies-20261016-v6.md); [сравнение PR-02A/02B и PR-03A/03B](RDG-V6-ACTION-IDENTITY-CANON-COMPARISON.md).  
**Внутренняя реализация:** `tools/graph-apply.py`, `tools/rdg-v7-model.py` (QRPE), `tools/graph-index.py`, `tools/rdg-root-projection.js`.  
**Проверяемый образец graph.json:** `tests/fixtures/rdg-v6-action-optin/graph.json`; тесты `tests/rdg-v6-action-writer.test.cjs`.

**Продолжение:** [ограниченный пересмотр выбранного Action](RDG-V6-ACTION-RECONSIDERATION-WRITER.md) реализован более поздним этапом; перечисление незавершённого ниже описывает исходную стадию writer/reader.

**Позднее исправление:** [Integrity Remediation](RDG-V6-INTEGRITY-REMEDIATION-20261017.md) требует signed package для выбора/привязки material Action и запрещает произвольные изменения R/Context; bootstrap кандидата остаётся экспериментальным. Старые тестовые подписи — не подтверждение реальной личности пользователя.

## 1. Что действительно реализовано

Реальный writer `graph-apply.py` через `graph-package.py` разрешает новый `kind: "action"` **только** если сам граф явно содержит `"actionModel": "candidate-v6"`. При отсутствии признака действует прежняя модель schemaVersion 1 с `option` и `decision`. Наличие поля в настоящем пользовательском графе **не следует изменять автоматически**: для перехода нужен отдельный принятый контракт миграции.

**Action** — один узел с одним ID. Он начинается `candidate`, а после выбора через `select_action` становится `selected`; отдельный D-node не появляется. Writer сохраняет событие `action_selected` с actor, reason, driver-R и immutable `selectionBasis.driverSnapshot/actionSnapshot` (T1). В будущем Action не обязан начинать свой ID с `O-`, но **миграция старого Option-ID** в данном этапе ещё не производится.

**Реальные writer-операции этого ограниченного контракта:**

- `add_action` — создаёт кандидатное A и ребро `R → A` типа `DRIVES`; простому Action не требуется канон/QRPE.
- `select_action` — меняет статус **этого же** A на `selected`, фиксирует reason/event и может создать содержательно сгруппированные `A → R1..RM` через `INTRODUCES`. Дочерние Requirements действующие, имеют уникальные ID, а parent R подтверждён.
- Уже существующие `append_qrpe` и `transition_qrpe` могут теперь работать с A внутри opt-in-графа; QRPE не переносятся на второй D.

**Границы записи:** `graph-apply` использует существующий транзакционный `graph-package` и проверку `expectedRevision`, read-back, transactionId replay и catalog validation. Выбор не может быть проведён без отдельного event с действительным в терминах writer полем `by=user/assistant`; `update_node` не разрешает переписывать Action, принятые изменения R не могут скрыто подменять title/status. Изменение связей `INTRODUCES` от A через generic `add_edge` запрещено без отдельной операции, сохраняющей историю.

**Reader:** `rdg-root-projection.js` читает выбранные R от `Action`, если есть event, подходящий scope графа и явный R-driver. `graph-index.py` распознаёт межграфовые `INTRODUCES` от A как `introducedByActionId`, не подменяя это `introducedByDecisionId`; уже существующее legacy чтение D продолжается.

## 2. Полноценный учебный graph.json

Файл `tests/fixtures/rdg-v6-action-optin/graph.json` — **настоящая структура** schemaVersion 1, с opt-in. Он получен вызовом `graph-apply.apply`, а не вручную составленной псевдосхемой:

```text
R0: Подготовить часть приложения
  DRIVES
A1: Разделить работу на независимые части
  status: selected (один ID до и после выбора)
  selectionBasis: T1 snapshot
  canonBlock + QRPE
  event: action_selected (синтетический, не user project)
  INTRODUCES
    R1: Проработать первую часть
    R2: Проработать вторую часть
```

Это **учебная запись**, а не принятие способа пользователем. Папка `tests/fixtures` не входит в `graphs/index.json` и каталог Viewer. В реальных graph files ничего не переключено.

Проверки происходят на временном изолированном репозитории, где есть настоящий `graph-apply.py`, `graph-package.py`, `graph-index.py`. В тесте создаётся отдельный дочерний файл с `rootRequirementId=R1` и законной `projectionOf` на источник R1; каталог распознаёт переход из A1 и сохраняет единственного владельца R.

## 3. Результаты, границы и риски

**Проверяются положительные сценарии:** создание Action, selection без D, snapshot T1, QRPE на A, grouping 1:M, origin/actor event, read-only R-tree и межграфовая relation, idempotent replay.

**Проверяются отрицательные сценарии:** A без opt-in, фиктивный actor или неверный actionId, повторный выбор, скрытая перепись выбранного A/принятой R через `update_node`, подмена `INTRODUCES` через `add_edge`, недопустимый child-R, duplicate ID/canon, stale revision, имитация selected без события, отсутствие частичной записи при отклонении транзакции.

**Границы:** выбранность не означает выполненность или доказанную достижимость R. Каноны пока хранятся и структурно валидируются; `select_action` не выполняет их содержательную проверку. В событии `by` указан actor, но это **не** криптографическая проверка полномочий и не автоматическое делегирование на изменение пользовательской цели.

## 4. Что ещё НЕ сделано

1. **Миграция O/D в A.** `PR-02A` остаётся предпочтительным кандидатом. Исторические Decision без подтверждённой Option-связи требуют отдельного рассмотрения; старые данные не переписаны.
2. **Исполнение, отмена и компенсация Actions, изменение уже введённых R.** Реализованы только `add_action`, `select_action` и доступный на A QRPE. Действия типа «убрать R», «отменить выбранное A» со своими канонами/QRPE являются следующим отдельным контрактом.
3. **Вычисление канонов.** Семантическая AI-оценка и узкие typed predicates проверялись в предыдущем прототипе, но не подключены как универсальный evaluator к `graph-apply`. Для простой A каноны/QRPE по-прежнему необязательны.
4. **Lens-runner.** Применение подготовленной Lens, в том числе без записи рабочего графа, остаётся отдельным пилотом; навязывать постоянный `LensRun` не нужно.
5. **UI Viewer и Helper.** Обновлены **reader/index**, а не визуальные элементы Viewer и не рабочие инструкции. Пользовательский каталог не переключён на новую модель.
6. **External Dependencies.** Нового блока/проекции нет: сохраняется решение использовать обычные R/A/Context/каноны/QRPE.

## 5. Воспроизведение

```bash
cd /workspace/repos/rd-graphs
node --test tests/rdg-v6-action-writer.test.cjs
node --test tests/*.test.cjs
```

**Следующий gate:** UI/read-only Viewer adapter + сценарии пересмотра Action и конкретные полномочия на реальные изменения; подготовленные Lens source graphs/Helper parity — отдельный этап. Реальный cutover до выбора совместимой миграции и её доказательства запрещён. Ничего в `graphs/workspaces` этим этапом не мигрировалось.
