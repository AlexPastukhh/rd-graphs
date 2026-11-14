# RDG — быстрый старт рабочего чата

> **СТАТУС: ДЕЙСТВУЮЩАЯ ИНСТРУКЦИЯ ОПЕРАТОРА.** Для выполнения задач через Graph. Разработка самого RDG начинается с [карты системы](RDG-CURRENT-STATE.md).

Для основного серверного Decision-профиля используйте [private API](RDG-OPERATIONS.md#private-api-для-ии) и [карту функций/тестов](RDG-FUNCTIONS-AND-TESTS.md). Команды bare Graph/Plan ниже относятся к прежнему маршруту; `coreModel` читается из реального owner.

## Основной серверный маршрут

При продолжении после перерыва начать со [среза доставки и неподтверждённых шагов](RDG-CURRENT-STATE.md#theory-delivery-20261114): версия исходников, проверенный архив, установленный runtime и опубликованные определения линз — разные факты. Сверить реальные Git/PR и capabilities установленного сервера; не считать функции из source уже установленными.

Для теории Decision/Action новый runtime предоставляет `schema(op='theory_read')`; сначала проверить эту возможность на установленном сервере. Начать с `{method:'theory_read',packageId,theoryId,collection:'overview'}`; затем получить `collection:'canons'` или `'recommendations'`, при необходимости `itemIds:[ID]`. Пропущенный `itemIds` означает всю коллекцию с явными страницами. Agent `theory --package-id OWNER --theory-id K --collection canons --all-pages` собирает её на одном снимке; для конкретного инстанса добавить `--item-id ID`. `--expand-sources` загружает один уровень источников явно. Маленькую нужную коллекцию удобно читать целиком; большие материалы — адресно. «Общее» объясняет роль ссылок, оглавление не заменяет содержимое. [Точный контракт](RDG-DECISION-V1-CONTRACT.md#rdg-theory-addressable-items).

Новые рекомендательные записи находятся внутри теории, а прежние Registry rules читаются отдельным совместимым маршрутом. Для внешних материалов учитывать [контракт доступа](RDG-DECISION-V1-CONTRACT.md#theory-source-access): недоступный серверу HTTPS-источник не пуст; при необходимости читать его разрешённым внешним инструментом по точному адресу.

С подготовленным context сначала выполните `doctor` и `catalog`. [Матрица операций](RDG-DECISION-V1-CONTRACT.md#матрица-операций-api-для-ии) связывает задачу с формой, результатом и проверкой. Команды из корня Repo:

```sh
python3 -B tools/rdg-agent.py schema --context /workspace/repo/Workfiles/rdg-gateway-context.json --action create
python3 -B tools/rdg-agent.py schema --context /workspace/repo/Workfiles/rdg-gateway-context.json --package-id ID --action core --core-command add --node PARENT_ID --entity-kind decision
python3 -B tools/rdg-agent.py dependencies --context /workspace/repo/Workfiles/rdg-gateway-context.json --package-id ID
python3 -B tools/rdg-agent.py history --context /workspace/repo/Workfiles/rdg-gateway-context.json --package-id ID --history-mode important
```

Первая форма выбирает `rdg-decision-v1/working`; заполните path/title/scope/rootReason из задачи. `--model-profile rdg-core-v1` явно запрашивает legacy; `--role ready|lens` — определение. Для `add` доступны `--entity-kind requirement|decision|action|context|canon|info|finding`; форму Finding открывайте на Decision. Ответ сообщает обязательные inputs и варианты. Формы не записывают объекты: сохраните заполненный request, выполните `preflight`, затем `command` с возвращённым inputBinding и проверьте `receipt`/readback по общему контракту. TransactionId сохраняется до выяснения результата.

`dependencies` возвращает native edges/projections; полные применения политик и причины инвалидации доступны в `open --detail full` (dependencyCatalog). `locks` читает существующие operation locks. `history --history-mode important|meaningful|technical|all` обращается прямо к истории процесса. Фильтрация History по элементу ещё не поддержана; `history --node` возвращает явную ошибку. Компактные режимы и batch обнаруживаются через schema установленного runtime.

**Профили и доступные линзы, 2026-11-11.** Основной профиль — `rdg-decision-v1`. В приложении доступны 19 фундаментальных линз и сохранённые `operate`/`develop`; полные Markdown и карта соответствия находятся в обычных Info определений. Для первого входа изучается [весь обязательный бутстреп](../lenses/README.md#обязательный-бутстреп), затем методики выбираются по задаче. В source-каталоге новые фундаментальные определения по умолчанию используют Decision, прежние R/A-варианты доступны через явный `--model-profile rdg-core-v1`. Обычный `create working` не устанавливает и не мигрирует линзы. Публикация данных 2026-11-11 выполнена отдельно; [версии и проверки](RDG-LENSES.md#rdg-lens-structured-publication).

Для context с `profile:portable` используйте [общий package API и команды Agent/Helper](RDG-OPERATIONS.md#переносимые-пакеты-agent-и-helper). Ниже сохранён совместимый маршрут bare Graph/Plan; он не означает автоматическую миграцию владельцев.

**Исторический срез 2026-10-22:** десять графов линз и прежняя редакция модели описаны в [handoff](../handoffs/rdg-action-canon-model-20261022/PROPOSAL.md). Этот счёт и формулировки относятся к тому снимку. Сейчас используйте актуальный каталог `RDG-LENSES.md`, профиль `coreModel` из реального `open` и [технический контракт](RDG-ACTIVE-CONTRACT.md). Старые Graph не мигрируются автоматически; смешивание форматов и произвольные kinds запрещены.

### Адресное чтение фокуса и ветви

Для установленного B03A сначала проверить schema --action read: detail должен содержать focus/branch, а scoped — состав секций и supported root kinds. Обычный open --node остаётся карточкой item. Focus читает существующее ближайшее окружение RDG; branch от R/Decision — всё структурное продолжение, включая невыбранные варианты. Прямые родители — краткие ссылки, общие узлы/циклы не раскрываются повторно. Данные приходят как JSON с полными каноническими bodies и qualified refs; Markdown в описаниях остаётся текстом.

```sh
python3 -B tools/rdg-agent.py schema --context /workspace/repo/Workfiles/rdg-gateway-context.json --package-id ID --action read
python3 -B tools/rdg-agent.py open --context /workspace/repo/Workfiles/rdg-gateway-context.json --package-id ID --node NODE_ID --detail focus --limit 100 --all-pages
python3 -B tools/rdg-agent.py open --context /workspace/repo/Workfiles/rdg-gateway-context.json --package-id ID --node REQUIREMENT_OR_DECISION_ID --detail branch --limit 100 --all-pages
```

IDs выбирает оператор из реального catalog/summary, а не запрашивает внутренние поля у пользователя. Без --all-pages ответ показывает продолжения в reading.continuations; страницы одной секции запрашиваются с include этой секции и её cursor. loaded=false и bodyState=notRequested/pendingPage не означают отсутствия данных. --all-pages подтверждает pagesComplete только после сборки всех запрошенных записей одного снимка; при stale/conflict перечитать область с начала. --include выбирает секции из schema; Plan только по явному --include plan, History остаётся отдельным процессным чтением. Нет скрытого fallback к full. Подробности и приёмка — [B03A](RDG-DECISION-V1-CONTRACT.md#read-focus-branch-b03a).

### Структурный Markdown и поиск

Проверьте в `schema --action read` наличие формата `markdown`, а в `schema --action search` доступность поиска. Замените `ID` и `NODE_ID` на значения из каталога и `ref` совпадения.

~~~sh
python3 -B tools/rdg-agent.py open --context /workspace/repo/Workfiles/rdg-gateway-context.json --package-id ID --format markdown --all-pages
python3 -B tools/rdg-agent.py open --context /workspace/repo/Workfiles/rdg-gateway-context.json --package-id ID --node NODE_ID --detail focus --format markdown --all-pages
python3 -B tools/rdg-agent.py lens --context /workspace/repo/Workfiles/rdg-gateway-context.json --lens model --format markdown --all-pages
python3 -B tools/rdg-agent.py search --context /workspace/repo/Workfiles/rdg-gateway-context.json --package-id ID --query p95
python3 -B tools/rdg-agent.py search --context /workspace/repo/Workfiles/rdg-gateway-context.json --search-scope catalog --query p95
~~~

В Agent Markdown выводится обычным текстом. С `--all-pages` Agent собирает полный документ одного снимка. В API текст находится в поле `markdown`, состояние страниц в `reading`. Для чтения ветви используйте `--detail branch`, для области `--work-graph WORK_GRAPH_ID`, для явного добавления Plan `--include-plan`. Поиск возвращает JSON со ссылками `ref`, совпавшими полями и фрагментами. Совпадение открывается по `ref.packageId` и `ref.nodeId`. Запрос действует на открытый пакет или явно выбранный доступный каталог.

## Разговорное намерение и самостоятельное исполнение

**Операционное правило для ИИ при уже подготовленном доступе (не обещание автономного runner).** Пользователь может дать цель/контекст словами «начинаем работу», «исследуй», «выбери», «продолжай», «отчитайся». Целый граф выполнения работы называем **процесс-графом** (пакет `working`/`copy`), логическую область внутри него — **WorkGraph/воркграфом** (`workGraphs` в JSON). Фокусные графы R/A/Canon — представления этих же данных. ИИ самостоятельно выбирает подходящие существующие операции, линзы и разрешённые инструменты; не запрашивает у пользователя внутренние JSON, IDs, transactionId, ревизии или команды. Для нового проекта проверяет каталог и действующие разрешения на создание package/Graph и при наличии права создаёт working Graph через portable schema/preflight/apply. Подготовку grants, authStore и bearer это не заменяет; при отсутствии доступа возвращает точный blocker без фиктивного создания.

Для исследований сохранять потенциальные R, candidate A и основания оценки канонов без ложного выбора; выбор, Plan, исполнение и evidence подтверждаются независимо. Способ использования готового Graph или линзы выбирается по [семантическому контракту](RDG-ACTIVE-CONTRACT.md#готовые-графы-линзы-и-рекомендации): ознакомление/уточнение/использование принципа допускают работу без вставки методики и без обязательной записи каждого применения; что полезного получено в работе, зависит от линзы и задачи, а что из этого сохранить — от C1/C2/C3; фиксированный набор новых элементов не требуется. Отвечать пользователю о проверенных результатах, текущем Plan/блокировках и нерешённых вопросах по настоящим Graph/Plan/history/receipts, а не по догадкам из чата.

Текущий контур RDG — один ИИ и пользователь; взаимодействие ИИ–ИИ отложено. Для формального запроса ответов на [Questions](RDG-ACTIVE-CONTRACT.md#вопросы) сначала выполнить [checkpoint](RDG-ACTIVE-CONTRACT.md#checkpoint-перед-существенным-действием): проверить доступные сведения, попробовать ответить самостоятельно, отделить предположения и сформулировать, что действительно требуется узнать у пользователя. Можно спросить без попытки защищённого исполнения или сопроводить вопросами запрос разрешения. Обычное общение не требует checkpoint перед каждым сообщением; полезные вопросы/ответы сохраняются по критериям записи. Старые маршруты peer/higher AI не использовать как текущие возможности. Сквозной сценарий — в [плане](RDG-DEVELOPMENT-PLAN.md#удобство-api-для-ии).

## Старт без изучения реализации

Рабочий чат получает **задачу пользователя и путь к подготовленному приватному контексту**. Достаточно этой инструкции и ответов tools/rdg-agent.py. Исходники, старые handoff и архивные Decision/Option не являются обязательным вводным чтением оператора.

При выборе методики использовать каталог lenses и при необходимости открыть подходящее определение через lens --lens NAME. Усвоенные принципы можно использовать без обязательного повторного чтения всего графа; уточнять нужные места при неясности или изменении источника. Доступность линзы в каталоге не делает её рекомендацией каждому элементу. Явно названные пользователем линзы можно сочетать. Для начала построения графа на бумаге использовать orient, clarify, explore и shape; сам выбор линз не разрешает выбор Actions или исполнение. Порядок работы задают [графы линз](RDG-LENSES.md), а этот файл содержит форму вызовов и технические предпосылки клиента.

После doctor открыть выбранные линзы с привязкой к текущему Graph. Для реального выбора/исполнения при соответствующей задаче применить work, для проверки — review, для продолжения — handoff.

~~~sh
python3 -B tools/rdg-agent.py doctor --context /ABSOLUTE/PRIVATE/rdg-context.json
python3 -B tools/rdg-agent.py open --context /ABSOLUTE/PRIVATE/rdg-context.json --lens work
~~~

Все команды запускать из /workspace/repos/rd-graphs в подключённом Fortis Repo. Каждый вызов — отдельный процесс; состояние берётся из настоящих владельцев, а не из памяти прошлого чата.

**Если doctor не готов:** сообщить конкретную отсутствующую предпосылку. Владелец/подготовленная среда должны предоставить нужный Graph, Plan и доступ. Не искать токены по диску, не выдавать себе grants, не подставлять старый контекст. Токены не передавать в чат, аргументы команд или Git.

## Где читать правила работы

Порядок и основания действий находятся в графах линз: shape — выделение блоков, work — выбор/Plan/исполнение, handoff — прерванные транзакции, develop/operate — границы модулей и обслуживания. [Критерии сохранения и масштаб Action](RDG-ACTIVE-CONTRACT.md#ценность-сохранения-и-масштаб-описания), [глубина планирования](RDG-ACTIVE-CONTRACT.md#цена-работы-и-глубина-планирования) и [checkpoint](RDG-ACTIVE-CONTRACT.md#checkpoint-перед-существенным-действием) принадлежат контракту; [пробелы переноса в Decision definitions](RDG-LENSES.md#статус-принципа-сохранения) ещё предстоит устранить. Сохранение не означает выбор, выполнение или закрытие.

Инварианты и права проверяются настоящими writers независимо от выбранной линзы. Техническая семантика состояний — [контракт](RDG-ACTIVE-CONTRACT.md).

## Контекст и готовность среды

Приватный JSON содержит пути к выбранным owners и ожидаемую identitySpace. Пример для уже подготовленной пары:

~~~json
{
  "graphFile": "workspaces/PROJECT/graph.json",
  "planFile": "plans/PROJECT/plan.json",
  "identitySpace": "VERIFIED-OWNER-SPACE",
  "authStore": "/ABSOLUTE/PRIVATE/authority.json",
  "tokenFile": "/ABSOLUTE/PRIVATE/scoped-token"
}
~~~

PROJECT и identitySpace заменить проверенными значениями. В контексте **нет самого токена**. tokenFile — файл с уже выданным scoped bearer, без symlinks, доступный только владельцу (0600). Для обычного расположения Plan корнем служит репозиторий; для другого разрешённого расположения задаётся planRoot. Альтернативно подготовленная среда передаёт RDG_AUTH_STORE и RDG_AUTH_TOKEN приватно; тогда authStore/tokenFile в контексте не нужны.

Для работы требуются graph.read и plan.read; изменения требуют разрешений соответствующих Graph-операций и/или plan.edit. commandAccess в open показывает доступ по текущему grant, но не обещает допустимость любой операции над выбранным узлом: её смысловые условия проверяет writer.

Контекст можно задать через RDG_AGENT_CONTEXT, если среда его уже передала. В Fortis отдельные shell-вызовы не следует считать общей сессией: надёжный вариант — указывать --context в каждом вызове.

Отсутствующий Plan, ошибочная identity и недоступный engine не превращаются в пустой успешный результат. Этот старт рассчитан на подготовленную пару Graph/Plan; он не создаёт Plan или права автоматически. Подготовка и эксплуатация — [операционный регламент](RDG-OPERATIONS.md).

## Действия без сборки внутренних пакетов вручную

Получить шаблон команды с актуальными ревизиями и новым transactionId:

~~~sh
python3 -B tools/rdg-agent.py schema --context /ABSOLUTE/PRIVATE/rdg-context.json --action add_action --node ACTUAL-R-ID
~~~

Заполнить фактические поля шаблона и передать request через UTF-8 STDIN. Приватный файл запроса содержит только семантическую операцию, без токенов и копии чата:

~~~sh
python3 -B tools/rdg-agent.py command --context /ABSOLUTE/PRIVATE/rdg-context.json < /ABSOLUTE/PRIVATE/request.json
~~~

| Действие | Что задать |
| --- | --- |
| add_action | nodeId существующей R, title, recommended; при необходимости contraindicated и actionType |
| prepare_requirement | nodeId candidate Action, title, childRole; дочерняя R сначала потенциальна |
| select | nodeId Action; оценка канонов и причина выбора в note |
| place / unplace | nodeId или существующий stepId, явная дата at или afterStepId; это только Plan |
| edit_title / edit_canon | Содержательное изменение, без подмены истории; правка корневой R требует владельца |
| add_qrpe | nodeId, title вопроса; он появляется как open |
| resolve_qrpe | nodeId, issueId, проверенные evidenceRefs и фактический note |
| complete | nodeId, фактический результат в note и проверенные evidenceRefs; writer отдельно проверяет допустимость completion |
| withdraw | nodeId выбранного Action и явные dispositions для введённых дочерних R |

complete/resolve_qrpe требуют непустой список evidenceRefs: объекты path и sha256. path — путь **к результату работы внутри проекта**, без symlinks и приватных файлов авторизации; SHA256 должен соответствовать файлу. Клиент проверяет наличие и неизменность байтов, а содержательную проверку выполняет AI/пользователь. Не создавать фиктивный файл ради обхода проверки.

Если writer отказал, читать error и устранить конкретную причину. После CAS-конфликта перечитать open и осмысленно подготовить новую операцию; не заменять expectedRevision вслепую. Поле saved=null означает неопределённость или уже существующий transactionId, а не отказ.

## Прерывание, линзы и зависимости

~~~sh
python3 -B tools/rdg-agent.py receipt --context /ABSOLUTE/PRIVATE/rdg-context.json --transaction-id PREVIOUS-ID
python3 -B tools/rdg-agent.py open --context /ABSOLUTE/PRIVATE/rdg-context.json --lens review --node ACTUAL-ID
python3 -B tools/rdg-agent.py open --context /ABSOLUTE/PRIVATE/rdg-context.json --lens handoff --node ACTUAL-ID
~~~

Сопоставить receipt с фактической операцией и текущим состоянием. Prepared journal требует штатного recovery, а не новой команды. Клиент не повторяет автоматически вход с уже существующим ID: он не предполагает, что это тот же запрос.

Линзы — [готовые графы методик и принципов](RDG-LENSES.md) соответствующего профиля. Обращение к ним и вставка содержания имеют разный эффект по [контракту](RDG-ACTIVE-CONTRACT.md#готовые-графы-линзы-и-рекомендации); само открытие не исполняет задачу и не подтверждает результат.

dependencies без --refresh читает явно выбранный engine project и не доказывает актуальность к сегодняшним sources. --refresh явно обновляет engine state; Graph/Plan и бизнес-истину это не переписывает. Для него в контексте нужен разрешённый gendocenProject и полная доступная scope. Обычный open ничего не refresh-ит. review_required означает необходимость пересмотра.

Клиент не публикует owners наружу и не устанавливает пользовательский Viewer. Старые специализированные lens-apply/пилоты не являются обязательным рабочим маршрутом.

## Текст для передачи другому чату

~~~text
Работай над моей задачей через RDG в подключённом Fortis Repo.
Репозиторий: /workspace/repos/rd-graphs.
Приватный контекст: <переданный путь к подготовленному rdg-context.json>.
Сначала прочитай docs/guides/RDG-AGENT-BOOTSTRAP.md.
Через tools/rdg-agent.py получи lenses, прочитай подходящие определения командой lens и выполни doctor.
Открой нужные линзы через open --lens NAME; --lens можно повторять. Я могу указать линзы явно.
Уточняй цель и контекст, исследуй способы и потенциальные состояния в графе на бумаге.
Рисование ветвей не означает их выбор, временное размещение или исполнение.
Используй актуальные ID/ревизии из ответов. Не начинай с полного handoff или исследования устройства системы.
Выполняй реальную работу через разрешённые операции; выбор и Plan не считай исполнением.
После прерывания сначала receipt прежнего transactionId. Модули в разработке не трогай.
Если доступ не подготовлен, сообщи недостающую предпосылку, не ищи и не создавай полномочия самостоятельно.
Задачу дам отдельно.
~~~


## Продолжение в core-профиле

Если open показывает coreModel: rdg-core-v1, используйте core_* команды из commandAccess и точный data-контракт RDG-ACTIVE-CONTRACT. В focusedGraph видны реальный фокус, ситуация, происхождение, терминальные блоки и текущее подтверждение. Не отправлять IDs определений линзы в рабочие Graph команды. После изменения R/A/Context проверить затронутую цепочку; сохранять различие stale и доказанной потери истинности. Потеря результата допускает восстановление через прежний A. Plan place/unplace и receipt остаются общими командами с отдельными правами. Новый чат открывает тот же подготовленный context и читает реальные owners, не старую копию отчёта.


Выходную R через A связывайте INTRODUCES с origin: subgoal и явные requirementIds либо method_correctness. Для существующей связи используйте core_output_origin; schema возвращает её форму. Это не непосредственная DERIVES-подцель. Проверьте blockers нужных исходных R и originDetails в focusedGraph; собственный граф исходной R по-прежнему заканчивается на A. Если входящая DRIVES снята, пересмотрите объявленное происхождение до подтверждения A. Схема и пример принадлежат RDG-ACTIVE-CONTRACT.


## Decision runtime и открытый Viewer — 2026-10-28

Для `profile=portable` используйте текущие catalog/read/schema и capabilities. `lens --lens KEY --model-profile rdg-decision-v1` выбирает профильную definition: 11 существующих ключей имеют варианты core/decision, четыре дополнительных объясняющих графа доступны только в `rdg-decision-v1`. Это чтение source definition, не создание или подключение live package. `recommendation_catalog` принимает из stdin объект query/offset/limit/packageId/revision; mutation по-прежнему через schema → preflight → command с exact input binding и receipt/readback.

Чтобы настроить уже открытый Viewer, context может явно содержать `helperUrlFile`: абсолютный приватный файл с текущим loopback session URL. `rdg-agent.py view_session --context FILE` принимает из stdin сообщение `{method:"view_session",...}` для той же Application. Actor должен совпасть; Agent не ищет сессии и не печатает capability URL. Read без sessionId перечисляет доступные сессии; update требует sessionId/expectedRevision/value. При CAS-конфликте перечитайте сессию и сохраните независимые drafts. Камеры/вкладки — session state, Graph/Plan/registry/layout сохраняются штатным FileStore. Полная форма и ограничения находятся в [Decision v1](RDG-DECISION-V1-CONTRACT.md).
