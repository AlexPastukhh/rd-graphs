# RDG — карта документации

> **СТАТУС: АКТУАЛЬНЫЙ УКАЗАТЕЛЬ.** Реестр действующих документов — [DOCS-POLICY.json](DOCS-POLICY.json). Начните с нужной задачи, затем переходите к коду и проверкам.

| Задача | Документ |
| --- | --- |
| Функционал, реализация, проверяемые сценарии | [Функции и тесты](guides/RDG-FUNCTIONS-AND-TESTS.md) |
| Текущий статус / оставшаяся работа | [Состояние](guides/RDG-CURRENT-STATE.md) · [План](guides/RDG-DEVELOPMENT-PLAN.md) · [Backlog](../BACKLOG-IMPROVEMENTS.md) |
| Практика: первый запуск Viewer, работа с решениями, ИИ, recovery и разработка | [Реестр Use Cases](use-cases/README.md) |
| Смысл R/Decision/Action, зависимости и история | [Контракт](guides/RDG-ACTIVE-CONTRACT.md) |
| Схемы, API и владельцы данных | [Технический контракт](guides/RDG-DECISION-V1-CONTRACT.md) |
| Интерфейс | [Viewer](guides/VIEWER-EXPLORER.md) |
| Запуск, API, тесты, обновление | [Регламент](guides/RDG-OPERATIONS.md) · [Браузерные проверки](../tests/visual/README.md) |
| Работа ИИ через Graph | [Bootstrap](guides/RDG-AGENT-BOOTSTRAP.md) · [Линзы](guides/RDG-LENSES.md) |
| Отдельные подсистемы | [Модули](guides/RDG-MODULES.md) · [Gendocen](guides/RDG-GENDOCEN-REQUIREMENT-DEPENDENCIES.md) |
| Прежний учебный R/A owner | [Состояние примера](guides/RDG-LIVE-TEACHING-WORKSPACE.md) · [Исключительный reset](guides/RDG-TEACHING-EXAMPLE-RESET.md) |
| Fortis Approvals | [Состояние](guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md) · [Код и evidence](../fortis_approvals/README.md) |

## История

Датированные планы и прежние описания интерфейса не определяют текущий функционал. [Архивный указатель](archive/README.md), [handoffs](handoffs/README.md), [история README](../README-HISTORY.md).

Точные байты действующих страниц до этой сверки сохранены в Git, без изменения рабочего HEAD или staged index:

```sh
git show refs/rdg/docs-pre-audit-20261105T162600Z:docs/guides/RDG-DEVELOPMENT-PLAN.md
```

Принятые требования из прежних срезов сохраняются; незавершённые направления перечислены в [текущем плане](guides/RDG-DEVELOPMENT-PLAN.md). [Кандидатные улучшения](../POTENTIAL-IMPROVEMENTS.md) не становятся выполненными задачами автоматически.

Реестр: `python3 -B tools/rdg-docs-audit.py --list-active`. Порядок изменения документации — в [AGENTS](../AGENTS.md) и [регламенте](guides/RDG-OPERATIONS.md#завершение-этапа-и-очистка).
