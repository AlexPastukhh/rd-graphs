> **СТАТУС: АРХИВ / LEGACY PLANNING HELPER — НЕ ИМПОРТИРОВАТЬ КАК ТЕКУЩУЮ МОДЕЛЬ.** Этот комплект использует старые `Decision/Option`, старую схему R/D и прежние рабочие подсказки. Активный RDG работает только с `candidate-v6` (`Requirement`/`Action`). Новый чат: [действующий контракт](../docs/guides/RDG-CURRENT-STATE.md). Файлы `modules/*.module.md`, `prompts/*.prompt.md` и собранные импорты — **замороженные исходные данные прежнего Workflow**, их нельзя применять к текущим Graph owners без отдельной миграции.

# RDG — рабочий комплект Planning Helper

Этот комплект — **рабочие** промпты Requirements–Decisions, не тестовые промпты. Семантика следует выбранной модели R/D; изменения не опубликованы в OBS repository.

## Импорт (локально в Planning Helper)

1. Открой `work-kit/planning-helper-import.txt` в Windows (`C:\Users\alexa\Repos\rd-graphs\work-kit\planning-helper-import.txt`).
2. Скопируй файл **целиком**, включая `[PLANNING_HELPER_PATCH]` и закрывающий маркер.
3. В Planning Helper открой **Import from ChatGPT**, вставь текст; preview ожидаемо: **4 Prompt + 9 Module**, без Delete. Нажми **Import local**. Это только локальное хранилище браузера, не GitHub.
4. Убедись, что при Copy/Run промптов `[[module:...]]` раскрываются; не должно быть ошибок missing module или cycle.

## Рабочие промпты

| ID | Назначение |
| --- | --- |
| `rdg.work.bootstrap` | Полный bootstrap: модель, планирование, хранение, режимы, безопасная работа |
| `rdg.work.plan` | PLAN для R: способ достижения через D и нужные дочерние R |
| `rdg.work.commit` | Фиксация явно выбранного D и подцелей, проверенная запись JSON |
| `rdg.work.crosscut` | Создание одного сквозного Requirement и его применений |

Модули: `rdg.work.semantics`, `rdg.work.planning`, `rdg.work.crosscutting`, `rdg.work.storage`, `rdg.work.repository`, `rdg.work.examples`, `rdg.work.rste`, `rdg.work.value`, `rdg.work.output`.
Общие правила языка (R-STE), соразмерности (Work Value) и формата ответа разделены. R-STE в текущем `obs-planning-docs` существует как отдельный **Prompt**, поэтому его текст включён как отдельный **Module** для использования внутри RDG; Prompt напрямую в `[[module:...]]` подключать нельзя.

## Эталонные примеры в рабочем bootstrap

Оригинальный документ пользователя версии 0.2 сохранён **без изменений** в `docs/examples/requirements-decisions-graph-examples-v0.2.source.md`. Индекс и отличие от текущих простых примеров: `docs/examples/EXAMPLE-COVERAGE.md`.

В Viewer доступны три read-only графа: `reference-app-definition`, `reference-delegation-status`, `reference-behavior-review`. Они подключены к рабочему bootstrap через `rdg.work.examples` и доступны через тот же модуль в PLAN. Эти графы являются учебными проекциями **одного** условного приложения с EX-* ID, а не готовыми планами, принятыми пользователем. Подробные ограничения физического writer — в индексе. `try-it` остаётся пустым рабочим графом.

## Источник и редактирование

Editable исходники: `work-kit/prompts/*.prompt.md` и `work-kit/modules/*.module.md`.
После редактирования пересобери `planning-helper-import.txt` командой:

```bash
cd /workspace/repos/rd-graphs
node work-kit/build-import.cjs
```

Пересобранный patch обновит локальные записи с теми же ID — не создаст дубль. Работающий граф — отдельно в `graphs/workspaces/<slug>/graph.json`. Нельзя путать импорт инструкций и сохранение графа.

## Практика без тестового промпта в Helper

`work-kit/START-TEST-CHAT.md` — внешний **одноразовый стартовый текст** для нового чата (не импортировать). Он направляет чат читать настоящий bootstrap и работать с `graphs/workspaces/try-it/graph.json`. Запусти START, затем реальный рабочий PLAN, COMMIT и CROSSCUT, проверяя факт сохранения и STATUS/TRACE. Файл `graphs/workspaces/try-it/graph.json` изначально содержит только `R-001`, revision=1.
Для записи используется `tools/graph-apply.py` с проверкой expectedRevision, dry-run и read-back; Viewer только читает JSON.

## Границы v1

Схема поддерживает `APPLIES_TO` для одного crosscutting Requirement с несколькими R-target, не превращая их в копии R.
Текущий updater не поддерживает удаление рёбер/историческую реструктуризацию и не обеспечивает фоновую синхронизацию с другими чатами. Это не должно маскироваться словами промпта.

## Модуль и Unit — версия 2026-10-13

Авторские тексты: prompts/*.prompt.md и modules/*.module.md. Import и GitHub helper-library — производные копии. Правила целого TM/Unit находятся в rdg.work.semantics.

После node work-kit/build-import.cjs выполните Import local поверх прежних 13 IDs, проверьте UPDATE/UNCHANGED и раскрытый текст. Check GitHub и Sync missing не заменяют существующие локальные тексты.

Прямой/составной Unit: docs/examples/MODULE-UNIT-GUIDE.md. Пакет и история: docs/guides/GRAPH-PACKAGE-WRITER.md. Установленная версия и новый чат проверяются отдельно.

## v7 — реальный рабочий граф

[Рабочий workflow](../docs/guides/RDG-V7-WORKING-GRAPHS.md) описывает `rdg-new-workspace.py`, выбор вариантов через каноны, композит до D, QRPE и прозрачные коллекции. Оба новых examples read-only, в реальный проект не копируются.


## Контекстные поля — Viewer 1.8.0

Новые команды чтения и записи, общий owner и DRY: §15 [рабочего руководства](../docs/guides/RDG-V7-WORKING-GRAPHS.md). Обновлены planning/storage modules и пересобран локальный import. Факт установки в Helper проверяется отдельно.
