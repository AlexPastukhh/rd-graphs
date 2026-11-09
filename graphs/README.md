# Graph owners и каталог

> **СТАТУС: ДЕЙСТВУЮЩИЙ УКАЗАТЕЛЬ.** Правила типов и авторизации — только в [контракте RDG](../docs/guides/RDG-ACTIVE-CONTRACT.md). [Историческая модель Graph 2.0](README-HISTORY.md) не допускается к активной работе.

Ниже описаны файловые owners прежнего профиля в Repo. Основной серверный `rdg-decision-v1` хранит переносимые packages и читается через [Application API](../docs/guides/RDG-DECISION-V1-CONTRACT.md#владельцы-и-api). Новый серверный процесс не является файлом `graphs/workspaces/...` в этом Git checkout.

`graphs/workspaces/<slug>/graph.json` — владелец реальных `candidate-v6` Requirements/Actions, `graphs/workspaces/.transactions/` — журнал принятых API-записей. `plans/<slug>/plan.json` — **отдельный** Temporal Plan owner (рядом с `graphs/`, а не внутри), Gendocen — отдельный проект зависимостей. Редактировать их напрямую с обходом авторизованных writers нельзя.

`graphs/catalog.json` и `folder.json` задают организацию интерфейса, **не** онтологическую иерархию целей. Канонический учебный файл — `workspaces/requirements-dependencies-demo/graph.json`, в Viewer помещён в папку **«Примеры»** через каталог. `graphs/examples/` и `graphs/2d/` — физические архивные примеры старой модели, **не** активные владельцы.

`graphs/index.json` и `tools/rd-graph-data.js` — производные read-only источники для Viewer, **не** место записи Graph или истории; `layouts.json` — отдельная раскладка. Порядок пересборки bundle и прав см. в [операционном регламенте](../docs/guides/RDG-OPERATIONS.md), а полную пересборку учебного примера — в [исключительном reset](../docs/guides/RDG-TEACHING-EXAMPLE-RESET.md).
