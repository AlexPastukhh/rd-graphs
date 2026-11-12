# RDG — цели, решения и действия

> **СТАТУС: АКТУАЛЬНАЯ ТОЧКА ВХОДА.** Основной профиль — `rdg-decision-v1`. Userscript/bundle: **2.7.0**; серверная сборка определяется `buildId`, а не этим номером.

RDG хранит цели, варианты решений, действия и их историю. Graph, временной Plan и представление имеют отдельных владельцев; рисунок и размещение в Plan не подтверждают выполнение.

| Нужно | Открыть |
| --- | --- |
| Понять функции и найти их проверки | [Функции → код → тесты](docs/guides/RDG-FUNCTIONS-AND-TESTS.md) |
| Узнать, что реализовано и что остаётся | [Текущее состояние](docs/guides/RDG-CURRENT-STATE.md) · [План](docs/guides/RDG-DEVELOPMENT-PLAN.md) · [Backlog](BACKLOG-IMPROVEMENTS.md) |
| Начать пользоваться RDG, открыть Viewer, вести решение | [Практические Use Cases](docs/use-cases/README.md) |
| ИИ: работать через API и продолжать после обрыва | [UC-RDG-003/004](docs/use-cases/ai-work.md) |
| Понять смысл модели и зависимостей | [Контракт](docs/guides/RDG-ACTIVE-CONTRACT.md) |
| Пользоваться интерфейсом | [Viewer](docs/guides/VIEWER-EXPLORER.md) |
| Запустить, проверить или обновить | [Операционный регламент](docs/guides/RDG-OPERATIONS.md) |
| Менять код и схемы | [AGENTS](AGENTS.md) · [Технический контракт](docs/guides/RDG-DECISION-V1-CONTRACT.md) |

В интерфейсе есть общий процесс, рабочие области, фокус элемента, «Граф»/«Структура», Plan/History и «Зависимости → Инвалидация / Политики». В актуальной семантике теория относится к Decision или Action: «Каноны» включают подходящие, пограничные и плохие ситуации, в том числе известные ошибки; «Общее» содержит остальные сведения. Уточнение 2026-11-12 реализуется без потери старых записей; установленный runtime проверяется отдельно. Политики сохраняются и применяются к конкретным участникам; причины пересмотра и отключённые применения показаны разными карточками.

Проверка всего release gate:

```sh
DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 PYTHONWARNINGS=ignore python3 -B tools/rdg-ci.py
```

Состав запуска указан в [CI driver](tools/rdg-ci.py), результат — в `/workspace/repo/Workfiles/rdg-ci/status.json` и `ready.json`. PASS относится к точным исходникам и артефакту; пользовательскую UX-приёмку он не заменяет.

`Start-Decision-Preview.cmd` запускает отдельный preview. Рабочий сервер и его данные обновляются по [операционному регламенту](docs/guides/RDG-OPERATIONS.md#разработка-и-обновление-серверного-runtime). Прежние `candidate-v6`/`rdg-core-v1` сохраняют совместимость; их правила не следует переносить в Decision-модель.

[Все документы и история](docs/README.md). Fortis Approvals — отдельный сервис: [его состояние](docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md).
