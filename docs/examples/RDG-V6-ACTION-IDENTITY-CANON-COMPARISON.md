> **СТАТУС: АРХИВНЫЙ ПРИМЕР — НЕ АКТИВНАЯ МОДЕЛЬ.** `Decision/Option`, старые каталоги и команды ниже относятся к историческому корпусу, их нельзя выполнять как текущий `candidate-v6`. Новый чат: [текущая спецификация](../guides/RDG-CURRENT-STATE.md).

# Candidate v6 · Этап 3 — проверенное сравнение Action identity и оценки канонов

**Статус:** CANDIDATE / read-only technical pilot / **not canonical, not committed**.
**Источник:** [Candidate Pre-work v6](https://github.com/AlexPastukhh/forfiles/blob/main/artifacts/2026-10-16/candidate-prework-rdg-executable-lenses-no-extra-dependencies-20261016-v6.md), разделы 7–10; варианты `PR-02A/B` и `PR-03A/B`.
**Затронуты только:** `tools/rdg-v6-stage3-comparison.py` и `tests/rdg-v6-stage3-comparison.test.cjs`; настоящий writer, graph.json, Viewer, Work Kit и Helper не мигрированы. Это **техническое сравнение**, не новое обязательное действие для каждого Lens-run.

## 1. Известное действующее состояние

В v7 действующий `tools/rdg-v7-model.py` содержит `kind=option` и отдельный `kind=decision`; выбор через `select_option` создаёт новый D-ID, `selectedOptionId` и `selectionBasis` (T1 snapshots). Его каноны имеют текстовые `recommended/contraindicated` cases, часто с `checkCategories`, `checkRequirements`, `checkCollections`; QRPE может быть у Option и у Decision. `INTRODUCES` исходит из выбранного D. При этом старые графы без новых Option-node обязательств сохраняют собственную семантику и не должны превращаться в мнимые новые Actions.

Проверены существующие данные **без записи**:
- `graphs/examples/reference-mixed-active-work/graph.json`: 13 Options, 2 Decisions, 6 `INTRODUCES` edges, 30 canon cases; одна Decision `D-A` подтверждённо ссылается на `O-A`, другая `D-OTHER` не имеет `selectedOptionId`, но имеет собственные 3 дочерние R и событие выбора учебного примера. Последнюю нельзя автоматически связать с конкретным Action.
- `graphs/examples/reference-prepared-planning-tree/graph.json`: 12 Options, 0 Decisions; источник подготовленных вариантов, 28 canon cases.
- `graphs/examples/reference-complete-availability/graph.json`: 0 Options, 4 Decisions; нет надёжного основания придумывать связь с несуществующим Option.
- `graphs/examples/reference-mixed-feature-availability/graph.json`: 2 Options и примеры `checkRequirements`/qualified `checkCollections`. Ссылки на граф, ветвь и версию — существенная часть данных.

Из 30 canon cases в первом примере **28 содержат `checkCategories`**, но наличие категории не задаёт формальную истину канона. `text` присутствует во всех 30. **Ни один** из существующих текстов не превращён автоматически в произвольный вычислимый predicate.

## 2. Сравнение PR-02A / PR-02B: идентичность

| Свойство | PR-02A — сохранить исходный Option ID как Action ID | PR-02B — ввести новый ID Action + alias |
|---|---|---|
| Стабильность ID существующего варианта | **O-A остаётся ID Action** в новой кандидатной проекции | Создаётся `action:O-A`, исходный `O-A` сохраняется как `legacyOptionId` |
| Выбор и исполнение | Старый D представлен как **исторический selection occurrence**, не новая семантическая Action | Аналогично, но D/edges и все callers требуют ещё одну карту ID |
| QRPE / каноны / preparedSource | Сохраняются без переименования ссылки на Option; pinned canonHash остаётся source field | Сохраняются в ссылке/alias; больше read/write compatibility surface |
| T1 / selectionBasis / D-ID | Полный старый snapshot/event сохраняется отдельно для provenance; D не считается performed | То же, но новая ID поверх старого owner |
| Не имеющее ссылки D (например, D-OTHER) | **Не переводится автоматически**, сохраняется со snapshot/event/edge evidence; отдельный migration gate | Так же; новый Action ID не решает отсутствующую связь |
| Новые Actions без старого Option | В будущем допускаются новые ID, без обязательного O-префикса; здесь не реализовано | Дополнительная namespace/schema policy для каждого |
| Цена / обратимость | Меньше переименований и ссылочной миграции; всё равно нужны semantic-kind reader, writer и safeguards | Больше alias/read-side logic; может давать более чистую новую namespace, но требует доказать пользу |

**Кандидатная рекомендация:** `PR-02A` — предпочтительный *путь исследования*, не коммит. Сохранять Action identity при переходе от `candidate` к `selected` и `performed`, но **не** выдавать старый `D-ID` за второе Action; его snapshot и событие остаются источником факта прежнего выбора. New ID для Action, у которого не было Option, может иметь обычный новый ID: `PR-02A` **не требует имени с префиксом O**.

**Scope-guard:** Action ID локален для source owner, поэтому проекция содержит `qualifiedActionRef={graphIdentitySpace,graphId,localActionId}`. `preparedSource` остаётся отдельной pinned ссылкой на template definition; source Lens/Action и целевое применение нельзя смешивать.

**Что фактически доказано:** read-only projections PR-02A/B проходят проверку происхождения Option, T1, QRPE, eventSnapshots, `INTRODUCES`, shared-source identity; не теряют данные старых D без Option. **Что НЕ доказано:** lossless round-trip через будущий writer/Viewer, что все historical D возможно пересемантизировать, истинность ссылок на внешний prepared-library при будущем version change, влияние на live workspaces. `traceVerified=true` **не равно** `migrationFullyResolved=true`.

## 3. Сравнение PR-03A / PR-03B: каноны

| Свойство | PR-03A — аргументированная AI-оценка | PR-03B — ограниченный вычислимый DSL |
|---|---|---|
| Существующие гибкие `text` cases | AI/человек оценивают смысл, с записью `rationale`, `evidenceRefs`, `contextVersion` | Автоматическая обработка **не доказана**; свободный текст не конвертировать в `predicate` |
| Объективный тест известных фактов | Требуется обоснование источником | Простой `requirement_present` или `context_equals` может вычисляться без AI |
| Неполные/устаревшие данные | `unknown/stale` — допустимые результаты; positive без evidenceRefs запрещён | `unknown/stale` возвращаются только если источники versioned/flagged; неподдерживаемое правило отвергается |
| Evidence / реальные факты | Прототип проверяет **форму** сообщения и наличие refs, **не** истинность вывода или существование внешних evidenceRefs | Прототип вычисляет только явно описанные технические предикаты над уже переданными данными |
| Затраты / риск | Меньше преждевременной реализации DSL; потребует модель источников и проверку качества оценок | Предсказуемость для ограниченных фактов, но быстрорастущая сложность, если объявить все каноны machine-executable |

**Кандидатная рекомендация:** использовать `PR-03A` как базовую strategy для смысловых канонов, с typed refs и evidence/unknown/stale; узкий вычислимый набор из `PR-03B` может дополнять объективные проверки **без обязательной полной конверсии**. Это кандидатная совместимая архитектура — её точный контракт и отношения PR должны быть согласованы до физического `graph-apply` change. **Отсутствие канона у простого Action допускается.**

**Чего нельзя заключать:** `record_ai_assessment` сейчас *не вызывает ИИ*, *не проверяет, что evidenceRef существует*, не определяет истинность доказательства и не выдаёт permission на Action. Его поле `verifiedByEngine:false` обязательно понимать буквально. `evaluate_typed_predicate` поддерживает только два строго заданных предиката, **не** пользовательский natural-language canon.

## 4. Исполнение / Verification Evidence

Запуск на репозитории:
```bash
cd /workspace/repos/rd-graphs
node --test tests/rdg-v6-stage3-comparison.test.cjs
python3 tools/rdg-v6-stage3-comparison.py \
  --graph graphs/examples/reference-mixed-active-work/graph.json
```
Скрипт читает существующий файл, выводит два вариантных *candidate projections* в stdout. Не меняет исходник и не сохраняет новый граф. Test suite охватывает: оба подхода идентичности; T1/QRPE/canon/source pin; event + 1:M R; unattached D со всеми event/edge snapshots; отдельный prepared graph; старый D-only graph; недопустимое изменение source и collision; ошибочный T1; ambiguous source; versioned assessments, evidence и unknown/stale; строго ограниченный DSL без фальшивой поддержки текстовых канонов.

**Фактические тесты и конкретное количество pass указать по последнему test output**, не переносить прошедшие ранее тесты в будущие утверждения.

## 5. Решения и gate следующего этапа

**Для работы можно продолжать без ответа пользователя:** выбрать `PR-02A` как рекомендованный candidate mapping, формально определить `Action definition / selection occurrence / execution result` и сохранить старый D-history по owner. До миграции провести ещё один pilot на frozen **event-backed**, не только illustrative source, и показать обратную проекцию с preserved fields.

**Не выполнять автоматически:** создание/перезапись `kind=action` в graph.json и замена `Option/Decision` в текущем writer, Reviewer, Viewer, Helper; автоматическое разрешение старых D без Option; массовая конверсия free-text canons в DSL; automatic selection/revocation или запись каждого LensRun. Они требуют отдельной композиции с compatibility, authority и E2E gates.

**Применение к Candidate v6:** этап 3 стал технически проверяемым, но он **не закрывает все риски будущего writer**. Надлежащий следующий шаг — pilot writer/reader design на копиях + атомарное решение schema/permissions, а не запустить массовое исправление графов. Optional External Dependencies block/view по-прежнему **не нужен**.
