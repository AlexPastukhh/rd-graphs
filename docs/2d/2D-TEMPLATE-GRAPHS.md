> **СТАТУС: АРХИВНЫЙ ПРИМЕР — НЕ АКТИВНАЯ МОДЕЛЬ.** `Decision/Option`, старые каталоги и команды ниже относятся к историческому корпусу, их нельзя выполнять как текущий `candidate-v6`. Новый чат: [текущая спецификация](../guides/RDG-CURRENT-STATE.md).

# IDTSPE / 2D Visual Production — готовые (НЕ ПРИНЯТЫЕ) разбиения в R–D графах

## Назначение и границы

Это **отображение** действующих 2D Target Module Models и их Module-defined Unit Definitions из `obs-planning-docs` в виде пригодных для просмотра **заготовок графа**. Это не изменение методологии IDTSPE, не утверждённый граф требований проекта и не применение какого-либо Target Module к конкретному Target.

Канонический источник:
`/workspace/repos/obs-planning-docs/planning/documentation/idtspe-methodology/active/profiles/visual-production-2d/target-modules/`
Реестр:
`../registries/TARGET-MODULE-REGISTRY.md`.
Core semantics:
`idtspe-core/target-modules/TARGET-MODULE-MODEL.md`,
`idtspe-core/runtime/target-work/UNIT-AND-TARGET-STEP-RESULT-MODEL.md`.

**Четыре обязательных различия:**
- Target Module **Model** — заранее подготовленная переиспользуемая модель работы и полного набора Units.
- Конкретный **Target Module Instance** существует только при реальном применении Model к Target. Ни один такой Instance здесь не создаётся.
- **Unit Definition** — заранее определённая часть работы с ответственностью, содержанием и правилами. Не является уже выполненным/принятым Unit Resolution.
- В этом R–D **представлении** Unit показан как Requirement-узел, а его подготовленные правила проработки — как непринятое Decision-подобное предложение. Это перевод на язык R–D для изучения и будущего выбора, **не дословное утверждение, что любой Unit IDTSPE есть обычный проектный Requirement**.

## Перенесённые Target Modules

| Исходный TM | Исходных Units | Граф в `graphs/` |
| --- | ---: | --- |
| `TM-2D-10-VISUAL-REQUIREMENTS` | 3 | `template-tm-2d-10-visual-requirements/graph.json` |
| `TM-2D-15-PREPARED-VISUAL-MATERIAL-SET` | 3 | `template-tm-2d-15-prepared-visual-material-set/graph.json` |
| `TM-2D-20-WHOLE-VISUAL-DESIGN` | 3 | `template-tm-2d-20-whole-visual-design/graph.json` |
| `TM-2D-30-VISUAL-CONSTRUCTION` | 2 | `template-tm-2d-30-visual-construction/graph.json` |
| `TM-2D-31-PIXEL-ART-CONSTRUCTION` | 5 | `template-tm-2d-31-pixel-art-construction/graph.json` |
| `TM-2D-31-VECTOR-CONSTRUCTION` | 5 | `template-tm-2d-31-vector-construction/graph.json` |
| `TM-2D-31-EDITABLE-RASTER-CONSTRUCTION` | 5 | `template-tm-2d-31-editable-raster-construction/graph.json` |
| `TM-2D-31-PAINTERLY-RASTER-CONSTRUCTION` | 4 | `template-tm-2d-31-painterly-raster-construction/graph.json` |
| `TM-2D-31-PROCEDURAL-CONSTRUCTION` | 5 | `template-tm-2d-31-procedural-construction/graph.json` |
| `TM-2D-50-DELIVERY-ADAPTATION` | 3 | `template-tm-2d-50-delivery-adaptation/graph.json` |

**Итого: 10 Target Modules, 38 Module-defined Units.**

## Соглашение о графовой проекции

Каждый шаблон содержит:

```text
TEMPLATE-R-TARGET-RESULT [R, условная цель; ещё не проектная R]
    └── DRIVES → TM-2D-* [D-подобная готовая модель; status: reusable-unselected]
                    ├── INTRODUCES → RU-*-01 [R-подобная Unit Definition, not-instantiated]
                    │                       └── DRIVES → TEMPLATE-D-RU-*-01
                    │                                    [подготовленное руководство Unit, reusable-unselected]
                    ├── INTRODUCES → RU-*-02 ...
                    └── ...
```

Это **структура потенциально применимого готового разбиения**, не принятый способ работы над конкретной целью. Поля `templateOnly=true`, `readOnly=true`, `selected=false`, `events=[]` на уровне графа и статусы узлов исключают трактовку как текущего committed Decision. `graph-apply.py` отклоняет попытки обновить этот reference/template graph.

**Важная граница Unit-глубины.** В исходных 2D Target Modules Unit Inventory задаёт Units, а раздел Unit-specific Guidance — инструкции по их выполнению. Во многих (фактически во всех 10 перенесённых TM) нет **отдельного объявленного под-Requirement Inventory внутри Unit**. Поэтому перенос НЕ придумывает под-R/таблицы/slots. Если в будущем появится готовое разбиение отдельного Unit на ещё более мелкие задачи, это будет отдельная явная проекция исходного определения, а не автоматически выведенная из запятых исходного описания.

`INTRODUCES` здесь означает *потенциальную структуру*, а не уже принятую декомпозицию; `DRIVES` к Unit-guidance — тоже **конверсионная связь** с меткой `templateOnly`, не историческая запись решения. Порядок Units и содержательные workflow dependencies по смыслу могут быть сложнее дерева. Их точные описания сохранены отдельно в оригинале, не заменены фиктивной последовательностью рёбер.

## Гарантия «ничего не потерять»

У каждого графа есть:
- `sourceMarkdown`: **полный оригинальный Markdown Target Module** как UTF-8, без нормализации переносов строк. Это includes Purpose, Formation/Scope Gates, Target Step Result, полную Unit Inventory, все таблицы, Unit Checkpoint Map, все Unit-specific Guidance, workflow, cross-Unit правила, Lens, validators, handoff, revalidation, artifact/file contract и исходные ссылки.
- `sourceContentSHA256`: SHA-256 оригинала для проверки идентичности.
- `originalSections`, `originalUnitInventory`, `sourceRegistryEntry` для проверки/просмотра.
- Для каждого `RU-*`: **оригинальный Unit ID**, точная ответственность из таблицы, якорь, полный Unit-specific Guidance и checkpoint (если есть).
- Нет `events` — исходные методологические определения не являются событием выбора в проекте.

В Viewer: «Граф R–D» → папка **«Готовые 2D-модели»** → «Заготовка 2D · …» → узел Unit → для полного оригинала **«Исходный модуль»**. Текст источника виден напрямую, граф не заменяет оригинал.

## Пересборка

```bash
cd /workspace/repos/rd-graphs
python3 tools/build-2d-template-graphs.py
python3 tools/graph-index.py
node --test tests/graph-2d-templates.test.cjs
```

Генератор обновляет только папки `graphs/2d/template-tm-2d-*/` и откажет, если целевой `graph.json` не помечен соответствующим templateOnly. Список каталога и `tools/rd-graph-data.js` пересобирает `graph-index.py`. Оригинальные `obs-planning-docs` файлы не изменяются. Файлы `work-kit/prompts`, `work-kit/modules` и `work-kit/planning-helper-import.txt` не меняются в рамках этого переноса.

## Что пока НЕ сделано

- Автоматическое сопоставление такой модели с реальным Requirement и её принятие/инстанцирование в рабочем графе.
- Семантическая миграция Unit Collections/Slots/таблиц в конкретные вложенные под-R без объявления такого разбиения в source.
- Унификация Target Module и Unit в единую reusable-node модель — возможная будущая архитектурная задача, не часть текущего точного переноса.
- Ручная проверка читаемости десяти графов в настоящем Edge (тесты браузерной модели — отдельно).

## Модуль и Unit — версия 2026-10-13

Десять широких graphs/2d/template-tm-2d-* имеют preparedModule и planningScale=module. Все 38 RU-* вынесены в *-unit-ru-* графы planningScale=unit с теми же IDs. Unit-корень ссылается на R в широком owner; готовый D находится в Unit-графе. Полный sourceMarkdown сохранён только в широком графе.

Исходные профильные документы не изменены; их старый Core — provenance, не нормативная основа этого формата. Новая версия источника сохраняется отдельно и не переписывает bindings применений.

Сборка: tools/build-2d-template-graphs.py, затем tools/graph-index.py. Современный контракт: docs/guides/GRAPH-PACKAGE-WRITER.md.
