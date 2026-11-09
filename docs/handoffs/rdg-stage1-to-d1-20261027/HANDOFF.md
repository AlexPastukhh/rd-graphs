# RDG: передача после первого этапа, продолжение с D1

> **СТАТУС: АРХИВ.** Снимок передачи работы 2026-10-27 после исправления первого этапа контрактов. Это пояснение для следующего чата, не новый нормативный план. При расхождении с более свежими действующими guides следовать им. Пользователь прямо попросил отдельный handoff.

## Что пользователь хочет получить

Нужно собрать полноценное RDG-приложение, используя существующее приложение и согласованный UI-прототип. Не начинать проектирование заново. Прототип значительно опередил старый backend: он показывает принятую Decision-модель, а рабочее приложение пока обслуживает прежнюю R/A-модель. Задача — перенести принятую логику в существующий Application, сохранение, общий API для ИИ/UI и основной Viewer.

Приоритет сейчас — **логика, каркас приложения и фундаментальные графы линз**, через которые ИИ понимает сущности и реально пользуется API и Viewer. Тематические примеры «2D», «3D», «программирование», «разработка приложения» нужны как демонстрации. Не расходовать время на аудит их предметной правильности или наполнение. Графы линз — отдельный вид готовых графов, а не просто все заранее подготовленные графы.

Пользователь принимает технические исправления, которые однозначно следуют из требований. Открытых смысловых вопросов, требующих его ответа для D1/D2, сейчас нет. Перед изменениями сообщать короткий план, после — проверять относящийся результат и обновлять действующие документы. При изменении прототипа проверять его в браузере. Отдельную мобильную версию не разрабатывать: основной сценарий — desktop.

## Где работать и что читать

Фактический репозиторий: **`/workspace/repos/rd-graphs`**, доступен через Fortis Repo. `/workspace/repo` в этой среде — другой Docker volume, его использовали для временных synthetic-проверок и test outputs. Если локальная shell не видит пользовательский путь, сначала проверить доступ через Fortis Repo, а не создавать пустой проект или переносить работу в другой каталог.

На входе проверить `pwd`, mount и `git status --short`. Перед этим исправлением было 97 status entries: там накоплена существенная незакоммиченная работа пользователя/предыдущих этапов. Новое число может быть больше. Не применять reset/clean, не перезаписывать чужой WIP, не коммитить и не публиковать без соответствующей задачи.

Читать в таком порядке, не весь исторический архив подряд:

1. [AGENTS.md](../../../AGENTS.md), затем [RDG-CURRENT-STATE.md](../../guides/RDG-CURRENT-STATE.md). Это вход и фактический статус.
2. **Начало** [RDG-DEVELOPMENT-PLAN.md](../../guides/RDG-DEVELOPMENT-PLAN.md): актуальный приоритет, таблица D1–D9, результат первого этапа, последовательность из 14 шагов. Файл большой: более старые разделы ниже относятся к прежним этапам и моделям, а не к новой очереди.
3. [RDG-DECISION-V1-CONTRACT.md, редакция 2](../../guides/RDG-DECISION-V1-CONTRACT.md). Это единственный technical owner форматов, effects, owners, command/receipt/recovery, typed refs, copy/layout и refresh. Первый этап подготовил именно этот контракт, а не реализацию нового kernel.
4. [RDG-ACTIVE-CONTRACT.md](../../guides/RDG-ACTIVE-CONTRACT.md): актуальные пользовательские правила. [RDG-OPERATIONS.md](../../guides/RDG-OPERATIONS.md): writer, authority, сохранение и завершение этапа. При D2/D6/D7 также [VIEWER-EXPLORER.md](../../guides/VIEWER-EXPLORER.md).
5. [Schema](../../../tools/contracts/rdg-decision-v1.schema.json), [typed refs](../../../tools/contracts/rdg-decision-v1.refs.json), [fixtures](../../../tests/fixtures/rdg-decision-v1/contract-cases.json), [contract tests](../../../tests/rdg-decision-contract.test.cjs). Их нужно подключить к реальному reducer/Application, а не объявлять исполненными на основании проверки формы.
6. [RDG-LENSES.md](../../guides/RDG-LENSES.md), особенно матрица покрытия фундаментальных линз. [Прототип](../../../tests/visual/rdg-ui-prototype.html) и [browser suite](../../../tests/visual/rdg-ui-prototype.cjs) — ориентир UI и его проверенный срез.

Список действующих документов принадлежит [DOCS-POLICY.json](../../DOCS-POLICY.json). `rg` намеренно исключает архивы через `.ignore`; если нужна конкретная зависимость из handoff, искать в её явном пути с `--no-ignore`. Старые HANDOFF/STATE не заменяют последние guides. Особенно устарел прежний запрет всех Actions в Graph: пользователь позже разрешил явные обязательные Graph Actions.

## Что уже готово и что ещё отсутствует

**Первый этап контрактов завершён после исправлений редакции 2.** Подготовлены шесть частей: schemas/identity/refs; таблицы состояний/effects/completion/guards; ownership/revisions/durability; read/schema/preflight/command/receipt/errors/CAS/retry; copy/template/layout/code map; refresh и сохранение draft/camera при конфликте.

Реальная программа пока использует **`rdg-core-v1`**, где A — прежняя роль. Новый **`rdg-decision-v1`** не включён в runtime. Нельзя механически переименовать старые A в реальные Actions или включить архивные Decision/Option через общий allowlist. Предусмотрен selector профиля и отдельный Decision kernel с переиспользованием существующих механизмов записи/authority. Схема и `$id` — спецификация, а не объявление runtime capability.

Source Viewer — **2.7.0**; пользовательская установка не подтверждена. Старые формальные Stage 4/security/deployment ограничения не закрываются завершением этого нового первого этапа. Это разные gates. Никакие реальные Graph/Plan owners, grants, credentials или installed Viewer этим исправлением не менялись.

Есть 11 настоящих фундаментальных R/A-линз старого профиля. Их не объявлять инструкциями Decision-приложения. Пересобирать и проходить их по мере появления поддержанных API, с фактической schema и temporary process. Нужен настоящий граф линзы с корректной логикой работы, а не только текст с обещаниями будущих команд.

## Что исправлено в последнем шаге

Исходная [проверка первого этапа RDG-STAGE1-20261027/v1](../../reviews/RDG-STAGE1-REVIEW-20261027-v1.md) остаётся неизменным снимком до исправлений. Её pending Proposals не означают, что нынешние формы всё ещё pending. Текущие решения приняты по разрешению пользователя и записаны в техническом контракте/плане:

| Находка | Исправление контрактов | Что проверить в реализации |
| --- | --- | --- |
| F-P-1 / PR-1B | У decide_acceptance нет заранее сохранённого outcome. Реальный selected/unselected обязателен в complete.data.decisionOutcome; есть внутренний completionContext и исторический actionResult | Actual snapshot/target checks, все группы/guards, один commit исполнения/выбора/каскада, exact retry |
| F-P-2 / PR-2 | instance имеет typed sourceDefinition version/hash и graphBinding packageId+identitySpace; members/roots qualified; shared/owned/foreign copy policy различаются | Общий resolver/remap/incoming inventory, две независимые вставки, отсутствие захвата чужого short ID, Graph+registry recovery |
| F-R-1 / PR-3A | core/add может атомарно создать entity и initialRelations; внешние Actions не принимают этот массив | Проверка всех связей/guards до mutation, одна Graph revision; отсутствие частичной entity/event/membership при отказе; recovery после prepared |
| F-O-1 / PR-4 | Expected IDs проверяются, есть реальный overlapping seed, per-group masks и test-only oracles | Подключить expectations к настоящему kernel/Application/UI, а не ограничиваться schema/test oracle |

Форма экземпляра: `instance:{sourceDefinition:{packageId,revision,sha256},graphBinding:{packageId,identitySpace},memberIds,rootIds}`. Первый packageId — ID определения рекомендаций; второй — Graph package. Старые плоские sourcePackageId/sourceRevision/graphPackageId не принимаются. Runtime нового формата ещё не существует, поэтому это не миграция пользовательских данных.

У обычной copy общий reusable definition сохраняет identity. Локальный instance, принадлежащий копируемому Graph, получает новый definition ID и remap binding/member/root/локальных anchors; sourceDefinition pin указывает на immediate source definition. Чужой instance обычная copy сохраняет чужим и неактивным относительно новой identity. Вставка шаблона создаёт независимые локальные instances; foreign anchor переносимого local instance отклоняется, не подменяется по короткому ID. Полная реализация этих операций — D4/D5, не текущие test-only golden vectors.

## Правила, которые нельзя потерять

**Модель и фокусы.** Requirement, Decision и реальный Action различаются. Явный Action в Graph обязателен от R/D через REQUIRES_ACTION. Low-level discovery/rename и произвольные плановые Actions остаются вне canvas, но принадлежат тому же Graph owner и общему пространству entity IDs. Выбор D, исполнение Action, completion D и достижение R — разные вещи. D→D запрещён, включая DEPENDS_ON. Decision Group не Graph-узел; отдельный реестр групп в Plan не нужен. Её состав хранится один раз в members, реальные R→D membership relations выводятся оттуда.

R-focus содержит сам R, непосредственные родительские R и D, для которых этот R обязателен, его прямые обязательные R/Actions и собственные варианты D, плюс применимый Canon/Context. Не добавлять транзитивных предков или все связи между соседями. D-focus содержит D, его R-источники, обязательные R/Action-выходы и Canon/Context. У внешнего Action — details, без позиции в Graph.

**Отмена и несколько оснований.** Актуальность — наименьшая неподвижная точка от enabled rootCauses через обязательную композицию и selected Decisions. Отказ снимает выбор D и отменяет всё зависимое продолжение, потерявшее все основания; выбранные дочерние D становятся unselected. Если остаётся другое действующее основание, общая R/D и её продолжение сохраняют актуальность. Цикл без корня не поддерживает себя. Сами сущности, связи, история, исполненные факты/evidence, Plan placements и координаты сохраняются. Повторный выбор родителя не выбирает отменённых детей автоматически. Семантическое решение спасти/переподключить ветвь — отдельная явная работа, не скрытая часть withdraw.

**Скрытие — только по взаимоисключающей группе при выборе.** При наличии выбранного участника exclusive-группа скрывает остальные изображения своих альтернатив; checkbox показывает их без выбора и обхода ограничения. Без выбора все варианты видимы. В nonexclusive группе выбор ничего не скрывает. Отменённый и никогда не выбранный вариант находятся в одинаковом положении по отношению к текущему выбору. selectionRequired, unselected, факт отмены и отсутствие актуальности сами по себе не фильтры. Пересекающиеся группы проверяются независимо; общая entity может быть скрыта в одном изображении и видна в другом. Это не глобальное удаление entity.

**Процесс, Working Graph и экран.** Working Graph — область ссылок на часть одного process Graph, не другой процесс/копия. Области могут пересекаться. Новый R/D/Graph Action, созданный из активной WG, входит в неё вместе с созданием; старые соседи и external Actions не входят автоматически. Вторая полоса UI — вкладки экземпляров экрана, третья — controls активного экрана. У двух вкладок одного процесса общие Graph/Plan/History/layout и независимые WG/focus, camera, draft, expanded occurrences, shown branch и display windows. Отдельная логика синхронизации копий Plan не нужна: owner один.

**Plan/History.** В Plan планируется порядок либо порядок с необязательной привязкой ко времени. Первый недатированный шаг допустим. Selected не prerequisite: можно заранее планировать альтернативы, ничего не выбирая в Graph. У развилки есть явное начало и несколько сохранённых cases; показывается одно продолжение, переключаемое у начала, без изменения предметного выбора. Границы History и Plan настраиваются отдельной открываемой кнопкой, вводом или выбором дней. Это display filters; History основана на реальных событиях с прежними pins, а не достраивается задним числом по сегодняшним связям.

**Общие ветви и layout.** В полном Graph вторичный вход в общую R/D-ветку показывает локальный свёрнутый блок того же типа/цвета. Его раскрытие создаёт только изображения исходной identity и продолжения. Правка отражается везде; Plan не дублируется. Позиции canonical/occurrence изображений сохраняются независимо. Для нового профиля process layout key = graphKey(identitySpace,graph.id); automatic occurrence = согласованный UUIDv5 по semantic route. Copy/template должны remap route и пересоздать ключи, сохраняя координаты. Expand/collapse сохраняют zoom/pan; «Вписать» меняет камеру явно.

**Готовые области, шаблоны и линзы.** В тематической готовой области есть templates и lens graphs. Вставленный template становится полноценной частью процесса с новыми IDs, локальными ссылками и независимыми рекомендационными instances; рабочие selection/results/History/Plan/исполненное evidence не импортируются. Lens используется по ссылке в контексте рабочего процесса и не копирует его данные. Nested lens имеет собственный namespace; исходный working context и ручная цепочка возврата сохраняются. Цикл рекомендаций не запускает автоматическое исполнение/рекурсию.

**Рекомендации.** Пакеты подключаются к процессу, template и lens. Общая правка definition обновляет все подключения при согласованном чтении; прежние применения фиксируют exact version/hash и не переписываются. Фундаментальный пакет должен подключаться к процессам по умолчанию в целевом приложении; минимальный D1 может явно объявлять recommendations=false до D4. Правила могут быть общими по типам/состоянию/меткам и identity/children/descendants-bound. Missing/foreign anchor никогда не означает «все». Панель Graph показывает только подключения; Add открывает отдельный выбор/поиск, Explorer «Пакеты» — каталог/CRUD/details/обратное участие. Линза также может рекомендовать другую линзу.

## Что проверить следующим чатом в первую очередь

1. Сверить текущие bytes и dirty tree с этим снимком; перечитать начало плана и технический контракт. Не повторять общий аудит всех примеров или проектирование.
2. Начать **D1: profile selector и pure Decision kernel**. Предусмотрены новые `tools/rdg-model-profiles.py` и `tools/rdg-decision-model.py`; существующий `tools/rdg-core-model.py` сохраняет прежний профиль. Расширить нужные validation/definitions/graph_references в `tools/rdg-portable-model.py`. Выбрать профиль до legacy/module gates, не расширять глобальный baseKinds ради нового профиля.
3. Подключать concrete fixtures к реальному reducer: support OR/rootless cycle, каскад/повторный выбор, пересечения групп, complete с обязательными R/Actions, outcome acceptance, atomic connected add и полный affected/guard set. Test-only oracles оставить как независимые проверки формул, не использовать их как второй production kernel.
4. Проводить новые эффекты через существующий writer/coordinator. Нужны actual persistence, revisions, CAS, permissions/locks, exact retry/receipt и recovery. Чистый kernel PASS ещё не доказывает сохранение или готовность D1/D2 целиком.
5. Перейти к **D2**: `rdg-portable-service.py`, `rdg-workflow-commands.py`, `rdg-agent.py`, Helper/transport и строгие focus projections. Поддержанный путь должен дать create → schema → read → preflight → apply → receipt → focus. Legacy-only входы возвращают явную unsupported capability, а не обход через старый writer. ИИ/UI используют общий Application.

Полный путь уже записан в плане. Последовательность: **1** контракты (готово) → **2** D1 → **3** D2 → **4** ранний интеграционный проход минимальных D3/D6/D7/D8 → **5** Plan/History D3 → **6** projection/layout/view API D6 → **7** packages D4 → **8** reuse/templates/lenses D5 → **9** полный desktop Viewer D7 → **10** завершение fundamental lenses D8 → **11** end-to-end D9 → **12** пользовательская UX-проверка/исправления → **13** итоговая сверка/сборка → **14** фактический запуск и, только при необходимости и отдельном разрешённом намерении, миграция данных. Порядок номеров D не является календарным порядком: D6 намеренно идёт раньше D4/D5. Ранний рабочий проход нужен до массового переноса всех экранов.

Внутри этапа: модель → schema/API → общий writer → readback → проекция/UI → соответствующая фундаментальная линза → относящиеся тесты/документы. Не оставлять линзы обещающими неподдержанную операцию. Параллельные планы/новые журналы и дубли source/generated логики не нужны.

## Проверки на момент передачи и пределы доказательств

В исправленном срезе прошли **101/101 contract tests**, **6/6 documentation tests**, **5/5 lens-catalog tests**. Contract fixtures: 28 positive, 38 schema-negative, 66 expectations по 12 осям, 5 transfer vectors; внутри suite — 18 ограниченных support/visibility oracles. Read-only подмена expected active ID на D-does-not-exist теперь даёт ненулевой exit и ошибку целостности. Fixture bytes от этой мутации не меняются.

Команды из корня репозитория:

```sh
node --test tests/rdg-decision-contract.test.cjs tests/rdg-documentation.test.cjs
python3 -B tests/rdg-lens-catalog.test.py
git diff --check
```

Ajv 8 Draft 2020 уже есть в Fortis `/opt/dc/node_modules/ajv/dist/2020`; suite поддерживает RDG_AJV_PACKAGE. Не требуется устанавливать зависимости ради этих тестов. Проверки lens catalog относятся к существующим определениям, не доказывают их пригодность для нового Decision runtime.

HTML прототипа и browser test в этом исправлении не менялись. Последний полноценный standalone browser result — **65/65**; projection/layout — **18/18**, из предшествующей работы. Это исторические PASS того же UI-среза, не новый browser-прогон и не проверка нового backend. **Каскад отмены и рабочий group-local checkbox всё ещё отсутствуют в standalone**, несмотря на уже согласованные и проверяемые контрактные правила. Toolbar variants пока декоративный в этой части. При переносе их нужно реализовать в kernel/projection/UI, а не считать готовыми по старому PASS.

Prototype semantic authoring/packages остаются данными demo-сессии; layout и WG metadata имеют свои сохранённые данные. Reload прототипа не равен restart настоящего приложения. Прототип нужен для ориентира взаимодействий, не как второй источник предметного state или production writer.

## Короткий текст для запуска следующего чата

«Продолжай RDG из `/workspace/repos/rd-graphs`. Прочитай приложенный HANDOFF, затем AGENTS, CURRENT, начало DEVELOPMENT-PLAN и DECISION-V1-CONTRACT редакции 2. Первый этап контрактов завершён после исправлений, новый kernel ещё не реализован. Начни D1 и затем D2 по существующему плану, без нового проектирования. Сохрани dirty tree и прежний rdg-core-v1, используй общий Application/writer; проверяй реальные effects и persistence, не только schema. Приоритет — логика и фундаментальные графы линз; тематические examples не аудировать. Перед правками дай короткий план, после — проверь результат и обнови действующие документы».
