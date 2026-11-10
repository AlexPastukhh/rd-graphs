> **СТАТУС: АРХИВ — ИСТОРИЧЕСКИЙ СНИМОК, НЕ ПРИМЕНЯТЬ К ТЕКУЩЕМУ RDG.** Новые чаты: см. [действующие правила](../docs/guides/RDG-CURRENT-STATE.md). Ниже сохранены устаревшие описания прежних версий без переинтерпретации.

# Graph owners и каталог — текущее состояние (source Viewer 2.4.8)

**Актуальная активная модель — `candidate-v6`: `Requirement` и `Action`.** Старые `Decision`/`Option` и read-only JSON из `graphs/examples/` и `graphs/2d/` остаются архивами для отдельной миграции, **не** открываются как активные Graph/Plan owners. `Context` не является свободно доступным базовым типом: только отдельный owner-scoped opt-in из `tools/rdg-node-type-registry.json` и `nodeTypeExtensions` в Graph.

- `workspaces/<slug>/graph.json` — настоящий writable Graph owner, работа через авторизованный Graph writer. `identitySpace`, корневая R и `actionModel` определяют владеющую сущность.
- `workspaces/.transactions/*.json` — принятые журналы Graph writer, источник восстановления событий истории; `graph.events` хранит структурированные фактические события. Сохранение и выбор Action не означают выполнение.
- `../plans/<slug>/plan.json` — отдельный Temporal Plan owner, версии размещений. Нельзя вводить в Plan несуществующие Graph R/Actions.
- `catalog.json` и `*/folder.json` — **организация интерфейса**, не семантические parent/scope. Активный `requirements-dependencies-demo` физически находится в `workspaces/`, но **в каталоге отображается в «Примеры»**.
- `index.json` и `../tools/rd-graph-data.js` — **производные** данные, не источник для Graph writer. В `index.json` могут сохраняться архивные метаданные; **активный Viewer bundle содержит только допустимые candidate-v6 owners**. Собирать `python3 -B tools/graph-index.py` из корня проекта.
- `layouts.json` — сохранённая раскладка, отдельная от данных Graph/Plan; только с разрешённым доступом.

**Стирание истории не является API-операцией обычного рабочего Graph**. Для одного явно зарегистрированного учебного Graph в каталожной папке «Примеры» существует защищённая **полная пересборка** с новой историей Graph/Plan/Gendocen. Не запускать вместе с Helper. [Контракт, ограничения и команда](../docs/guides/RDG-TEACHING-EXAMPLE-RESET.md).

[Единая актуальная карта документации](../docs/guides/RDG-CURRENT-STATE.md) · [Viewer](../docs/guides/VIEWER-EXPLORER.md) · [Graph writer](../docs/guides/GRAPH-PACKAGE-WRITER.md). Исторический проектный план `RDG-V7-WORKING-GRAPHS.md` не должен интерпретироваться как разрешение запускать старую модель.
