# RDG — полный handoff для продолжения работы в новом чате

> **Срез:** 2026-10-26, Asia/Bangkok. Это рабочая передача, а не заявление о production-ready или Stage 4 acceptance.

## Как использовать этот handoff

Новый чат должен сначала прочитать этот файл, затем проверить актуальный код в `tests/visual/rdg-ui-prototype.html` и последний correction handoff `rdg-group-context-navigation-20261026`. После этого продолжать работу с текущего прототипа, не возвращаясь к старой модели Action-as-Graph.

Все изменения делаются в Fortis Repo. Рабочий репозиторий:

`/workspace/repos/rd-graphs`

Основные источники:

- текущий UI-прототип: `tests/visual/rdg-ui-prototype.html`;
- текущая карта состояния: `docs/guides/RDG-CURRENT-STATE.md`;
- рабочий план дальнейшей разработки: `docs/guides/RDG-DEVELOPMENT-PLAN.md`;
- контракт предметной модели: `docs/guides/RDG-ACTIVE-CONTRACT.md`;
- операционный регламент: `docs/guides/RDG-OPERATIONS.md`;
- инструкция запуска рабочего чата: `docs/guides/RDG-AGENT-BOOTSTRAP.md`;
- инструкция браузерных проверок: `tests/visual/README.md`.

Последние handoff-срезы:

- `docs/handoffs/rdg-decision-model-transition-20261026/`;
- `docs/handoffs/rdg-decision-action-layer-20261026/` — исторический срез, его Action-узлы уже отменены;
- `docs/handoffs/rdg-action-projection-and-group-labels-20261026/`;
- `docs/handoffs/rdg-group-context-navigation-20261026/` — последний correction перед этим handoff.

## Зафиксированная целевая модель

Пользователь изменил фундаментальную модель: бывшие Actions как варианты теперь являются Decisions. Decision — это вариант решения, а реальный Action — отдельное действие человека/ИИ по работе с Graph.

Graph содержит:

- `Requirement` — требуемый результат или условие;
- `Decision` — возможный способ/вариант, который можно принять или оставить невыбранным;
- `Decision Group` — ограничение выбора, а не отдельный Graph-блок и не шаг Plan;
- `Canon` — свободные ориентиры качества решения;
- `Context` и другие справочные графовые сущности.

Decision имеет состояния:

- `discovered` — вариант найден;
- `unselected` — явно рассмотрен и оставлен непринятым;
- `selected` — принят как текущий выбор;
- `completed` — selected Decision выполнен, и все обязательные под-Requirements закрыты.

Наличие идеи, selected или placement не означает completion. Отдельно фиксируются выбор Decision, достижение Requirement и завершение реального Action.

Все Requirements, выходящие из выбранного Decision, считаются обязательными под-Requirements. Само решение о разбиении Requirement оформляется отдельным Decision; наличие D5 не создаёт под-Requirements автоматически.

## Группы решений и направление связей

Группы могут пересекаться. У группы сейчас два независимых свойства:

- `selectionRequired`: в группе обязательно выбрать хотя бы один Decision;
- `mutuallyExclusive`: одновременно можно выбрать не более одного Decision.

Например, D1 и D2 входят в G1 (`required=true`, `exclusive=true`), D2 и D3 могут входить в G2 (`required=false`, `exclusive=true`). Это позволяет иметь несколько групп с разными правилами для одного Decision.

Ключевой инвариант: стрелки `Decision → Decision` запрещены. Membership группы в прототипе всегда рисуется как связь `Requirement → Decision`. Выходы Decision — это отдельные связи `Decision → Requirement`. Сейчас демонстрационные membership-связи исходят от R0 или R2; D1 выводит R1 и R2.

На линии membership показывается только короткий идентификатор `G1` или объединённая подпись `G1 / G2`. Цветные точки рядом с ID означают свойства группы:

- amber — `selectionRequired` включён;
- violet — `mutuallyExclusive` включён;
- пустой серый кружок — свойство выключено.

Клик по `G#` должен открыть место использования группы в Graph и раскрыть её подробности. Для `G1 / G2` должны открываться обе группы. Навигация панорамирует Graph, но не меняет масштаб; локальный фокус показывает родителя и Decisions-участников, боковая панель показывает политику и участников.

## Реальные Actions, History и Plan

Actions не живут в Graph, не являются узлами `initialNodes`, не получают Graph-позицию и не имеют Graph edges. Они хранятся отдельно в `initialActions`/`actions` и показываются только в History и Plan.

Action имеет тип, свободное название/описание/контекст, `targetIds` для Requirements/Decisions, `groupIds` для контекстных ссылок на группы, состояние и флаг `lowLevel`. Примеры типов: обнаружить Decision/Requirement, решить принимать ли Decision, выбрать Decision в группе, переименовать блок, пересмотреть Canon, проверить закрытие Requirement.

Low-level Actions можно скрывать отдельной настройкой дороги. Скрытие меняет только проекцию UI, а не факты History.

Единая вертикальная дорога визуально соединяет `History → граница → Plan`. Исторические события могут быть запланированными или вне Plan. Завершённый плановый элемент уходит в History, но незапланированное событие тоже может сразу появиться в History.

Plan размещает существующие Graph-блоки и реальные Actions, задаёт ветви, локальный порядок и необязательные временные характеристики: только порядок, ориентир, начало работы, дедлайн или начало+дедлайн. План не создаёт новые Graph-сущности.

В Plan/History причинный контекст должен быть компактным: у Action показываются его Graph targets и контекстные группы; у Decision — происхождение, обязательные выходы и контекст групп; у Requirement — родитель/происхождение и выходы. Контекстные `G#` должны быть интерактивными ссылками в Graph, а не самостоятельными карточками дороги.

## Что уже есть в прототипе

Файл `tests/visual/rdg-ui-prototype.html` — standalone HTML/JS-preview, не интеграция backend и не установленный Tampermonkey Viewer.

Внутри файла важные участки:

- `initialNodes` — только R/D/Canon/Context Graph-блоки;
- `initialActions` и `actions` — отдельный Action layer;
- `initialEdges` — Graph edges, включая membership;
- `decisionGroups` — G1–G4 с независимыми свойствами и перекрывающимися участниками;
- `groupedDecisionEdges` и `groupLabelMarkup` — короткие G-подписи на линиях;
- `groupRefButton`, `openGroupInGraph`, `centerGraphOn` — навигация из контекста группы;
- `renderGraph` — Graph с цветами R/D и без Action-узлов;
- `renderRoad`, `roadCauseHtml`, `causalSummary` — History/Plan и боковые причинные ссылки;
- `renderPane` — inspector, Action details и group details;
- `roadSettings` — расстояние, размеры и шрифты центральных/боковых блоков, размер индикатора, режим подписей/точек и low-level filter.

В UI также сохранены проводник Graph в стиле VS Code, старый Viewer-style toolbar, локальный фокус, двунаправленное разделение Graph/Plan и переход по History/Plan без автоматического изменения масштаба Graph.

Не возвращать в Graph Action nodes, `OPERATES_ON` или Decision→Decision стрелки. Не возвращать в Plan отдельную секцию/реестр групп.

## Как открыть и проверять

Для визуального просмотра standalone-прототипа из Fortis Repo:

```sh
cd /workspace/repos/rd-graphs
python3 -m http.server 4173 --directory tests/visual
```

Затем открыть в браузере:

`http://127.0.0.1:4173/rdg-ui-prototype.html`

Если нужен пользовательский Windows preview основного Viewer, это другой маршрут: `Start-Preview.cmd` запускает `tools/rdg-preview.py` на порту 8794. Этот preview не является текущим standalone Decision/Group prototype; не путать их.

Для синтаксической проверки HTML извлечь содержимое `<script>` и проверить Node:

```sh
python3 -c "from pathlib import Path; s=Path('tests/visual/rdg-ui-prototype.html').read_text(); Path('/tmp/rdg-ui-prototype.js').write_text(s.split('<script>',1)[1].split('</script>',1)[0])"
node --check /tmp/rdg-ui-prototype.js
```

Минимальный smoke должен проверять: отсутствие `OPERATES_ON`, отсутствие `decisionGroupsMarkup`, отсутствие membership edge с источником Decision, наличие `openGroupInGraph`, `data-group-ref` и цветных group indicators. Текущий результат: `RDG_GROUP_CONTEXT_SMOKE PASS`.

Документационная проверка:

```sh
node --test tests/rdg-documentation.test.cjs
git diff --check
```

Последний результат документационного теста: 5/5. Browser manual pass именно для нового standalone-прототипа пока не выполнен.

## Что осталось делать

1. Провести ручной browser pass по текущему прототипу: открыть Graph, Plan/History, Action details, causal group links, комбинированную подпись `G1 / G2`, проверить панорамирование без изменения масштаба и раскрытие панели.
2. Проверить, что при клике на History/Plan Action открывается Action details, а при клике на его target или group context — Graph; не смешать эти два перехода.
3. Проверить плотность UI на узком окне и корректность resizable split между Graph и дорогой.
4. После согласования UX решить, какие части standalone-прототипа переносить в настоящий Viewer. Не считать prototype автоматически реализованным backend.
5. При изменении предметной модели синхронно обновлять `RDG-ACTIVE-CONTRACT.md`, `RDG-CURRENT-STATE.md`, рабочий план и новый handoff; старые handoff-срезы не переписывать, а явно supersede их последующим срезом.
6. Только после отдельного решения о backend scope проектировать writer/schema/API. Текущий действующий backend R/A контракт не мигрирован под Decision Groups.

Открытые UX-вопросы: точная ширина/плотность causal side chips, способ редактирования нескольких групп, будущие свойства групп, порядок/время Plan и представление completion Requirement/Decision в реальном Viewer.

## Ограничения и правила продолжения

- Не трогать live owners, grants, credentials, Windows installation или установленный Tampermonkey без отдельной авторизации и штатного регламента.
- Не считать static prototype, isolated tests или старые handoff доказательством пользовательской приёмки, production rollout или Stage 4.
- Не смешивать старый активный R/A backend с новой Decision-моделью без явного плана миграции.
- Все команды выполнять из `/workspace/repos/rd-graphs` через Fortis Repo; не использовать прямую запись JSON в обход writer для живых данных.
- Не коммитить и не публиковать изменения автоматически. Сначала показать проверяемый результат и статус тестов.
