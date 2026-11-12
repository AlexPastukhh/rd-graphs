# RDG — действующий операционный регламент

> **СТАТУС: ДЕЙСТВУЮЩАЯ ИНСТРУКЦИЯ.** [Карта актуальных правил](RDG-CURRENT-STATE.md). Все команды выполняются из **корня проекта**, с уже установленными зависимостями. Не выполнять стирающие или grant-административные операции автоматически от имени пользователя.

## Быстрый выбор режима

Основной рабочий профиль — серверный `rdg-decision-v1`. [Функции и проверки](RDG-FUNCTIONS-AND-TESTS.md) · [интерфейс](VIEWER-EXPLORER.md).

| Задача | Раздел |
| --- | --- |
| Проверить исходники и выпустить ZIP | [CI и обновление](#разработка-и-обновление-серверного-runtime) |
| Работать ИИ с теми же данными | [Private API](#private-api-для-ии) |
| Проверить весь продукт в браузере | [Браузерные сценарии](../../tests/visual/README.md) |
| Прежний candidate-v6/core Helper | [Локальный Helper](#локальный-helper); его команды не являются серверным API |

Вспомогательные legacy-команды ниже сохраняются для своих owners. Они не определяют основной Decision UI и не дают разрешения на миграцию/сброс живых данных.

## Порядок работы нового чата

Для выполнения прикладной задачи используется [bootstrap оператора](RDG-AGENT-BOOTSTRAP.md): doctor, open, schema/command, receipt. Дальнейшие пункты — регламент разработки и обслуживания RDG.

Порядок работы описан графами линз: orient — проверка контекста и выбор инструкций, operate — эксплуатация, develop — изменения RDG, review — проверка, handoff — прерванные операции и продолжение. Каталог: tools/rdg-agent.py lenses; определения и границы — [RDG-LENSES](RDG-LENSES.md). Этот регламент остаётся справочным источником точных команд, предпосылок и транспортов.

Технические границы: запись только штатным writer с реальными owner/identity, bearer/grant, CAS и transactionId; журнал и receipt определяют факт принятия. Публикация частных owners не происходит автоматически. Plan placement и Gendocen review не подтверждают исполнение.

## Безопасные команды проверки

```sh
# Действующая версия Viewer (не установленная у пользователя):
head -n 5 tools/rd-graph-viewer.user.js
# Проверить документацию и актуальные owner/links, без записей:
python3 -B tools/rdg-docs-audit.py --check
node --test tests/rdg-documentation.test.cjs
# Разбор пользовательского интерфейса/Graph/Plan — без удаления историй:
node --test tests/rdg-active-example.test.cjs tests/rdg-teaching-reset.test.cjs
```

Браузерные сценарии запускаются в отдельно подготовленном изолированном Chromium. Наличие тестов или бинарника в Repo не означает, что текущая среда готова к запуску. Предпосылки, выбор сценария и команда — в [инструкции браузерных проверок](../../tests/visual/README.md). Основную оценку удобства UI проводит пользователь в своём окружении.

## Подключение Viewer в подготовленном браузере

Этот маршрут предполагает установленный Tampermonkey и доступную локальную копию файлов проекта. Подготовка ОС, установка расширения и выдача новых grants сюда не входят.

1. Обновите в реальном локальном каталоге пользователя `tools/rd-graph-data.js`, `tools/rd-graph-viewer.user.js` и `tools/rd-graph-viewer-local-loader.user.js`. Первый файл — уже опубликованный bundle; его публикация описана ниже и не требуется повторно для подключения неизменённых данных.
2. Установите **Local Loader** в Tampermonkey. В двух его `@require` укажите фактические `file:///` URL локальных файлов: сначала `rd-graph-data.js`, затем `rd-graph-viewer.user.js`. Пути Docker `/workspace/...` не являются автоматически путями браузера пользователя. Для локальных `@require` браузер и расширение должны иметь разрешённый доступ к этим файлам.
3. Оставьте один активный способ загрузки Viewer на странице: при использовании Loader отдельная установленная копия Viewer не нужна. Откройте или перезагрузите подходящую страницу из `@match` Loader. Сверьте показанную **версию Viewer** с `@version` его исходника; версия Loader — отдельная величина. Если осталась прежняя версия, проверьте файлы и обновление локальных `@require` средствами менеджера скриптов.
4. Откройте каталог и нужный Graph. Без Helper опубликованные Plan/Gendocen доступны только как явно помеченный исторический read-only snapshot. Наличие графа в каталоге не подтверждает живую сессию или право записи. При ошибке чтения сохраните её как ошибку, а не как пустой успешный Plan.

## Явная публикация read-only снимка

Только **после** принятых Graph/Plan/Gendocen изменений и с существующим реальным engine state:

```sh
python3 -B tools/rdg-publish-readonly-owners.py
python3 -B tools/graph-index.py
```

Это обновляет производные `tools/rdg-published-owners.json`, `graphs/index.json` и `tools/rd-graph-data.js`, не означает автоматическое подтверждение корректности бизнес-решения или установку Viewer на компьютере пользователя. Offline опубликованный Gendocen — прошлый snapshot, не online check.

## Публикация структурированных линз

Полные Markdown, source JSON и установленное определение — связанные версии с разными подтверждениями. Содержание и результат переноса принадлежат [плану линз](RDG-LENSES.md#rdg-lens-structured-publication). Изменение исходника само по себе не меняет live Graph.

Из корня Repo проверить соответствие подготовленных определений исходникам:

~~~sh
python3 -B tools/rdg-lens-content.py
~~~

`--write` пересобирает source definitions и source-map по полным текстам и авторскому плану; это локальная подготовка без публикации. Предварительный план работы с подготовленным API можно получить так:

~~~sh
python3 -B tools/rdg-lens-publish.py --context /workspace/repo/Workfiles/rdg-gateway-context.json --journal /workspace/repo/Workfiles/rdg-lens-structured-20261111/publication-19-v1.json
~~~

Флаг `--apply` исполняет именно подготовленный набор, а `--manage-existing-supplied` явно включает передачу прежних supplied owners под управление для этой авторской задачи. При этом сохраняются packageId, identitySpace, исходное происхождение и прежние Graph versions. Publisher не меняет working-процессы или общий supplied fundamental Registry; новые адресные советы принадлежат самим линзам.

Журнал связан с SHA256 набора и сохраняет request/transactionId/inputBinding до эффекта. Повтор с тем же набором проверяет receipts и готовые результаты; при неподтверждённом исходе — STOP по [UC-RDG-004](../use-cases/ai-work.md#uc-rdg-004). Для другого содержания нужен отдельно проверенный план и новый журнал. Для согласованной следующей редакции собственных authored-рекомендаций используется явный флаг `--revise-navigation`: только тот же ID/key, следующая версия, CAS, сохранение прежнего определения в journal и readback. Без него отличающееся существующее определение останавливает перенос; supplied/сторонние и произвольные будущие редакции автоматически не переписываются. Группы публикуются штатной атомарной командой decision_group, которая заменяет соответствующие DRIVES-участия без промежуточной потери оснований.

Publisher сохраняет package/graph revisions из проверенного inventory. Новая schema перед записью должна совпасть с этой базой; продвижение возможно только по собственным принятым receipts того же journal. Посторонняя ревизия даёт LENS_CHANGED_SINCE_REVIEW, в том числе после потери ответа: не принимать свежий read за новое разрешение перезаписи. Корневые основания проверяются по полному содержанию и публикуются через существующую root_cause; незамапленные прежние основания не удаляются автоматически. Описания узлов сохраняют устойчивую ссылку на раздел и LS-MAP, а точный полный текст, SHA256 и Git-редакция принадлежат существующим source Info/source-map. После фиксации изменённых Markdown в Git пересобрать определения и проверить отсутствие compiler drift перед CI: это связывает provenance с фактическим коммитом источника.

Reviewed inventory также сохраняет исходные собственные recommendation definitions до первого write. Revise-navigation не разрешает перезаписать постороннюю версию после этой проверки. При потере ответа создания с attachment resume читает receipt того же create request; новый ID не создаётся. Attachment использует ранее проверенные package/graph revisions. Старый journal без проверенной базы рекомендаций при необходимости их изменить останавливается с NAVIGATION_REVIEW_BASE_MISSING; нужен новый осознанно проверенный план. Publisher планирует graph_title отдельно и сверяет заголовок/rootRequirementId при readback; при отсутствии команды в live schema сначала требуется установка поддерживающей сборки.

Связанные линзы публиковать последовательно: консервативный read set установленного runtime может измениться даже при записи другого owner. Подтверждённый сервером `definite=true` отказ PREVIEW_INPUTS_CHANGED до acceptance сохраняется как rejection; осознанный повтор с тем же journal получает новый preflight для неизменного request/transactionId и прежнего CAS. Это не разрешает переписать постороннюю ревизию. При timeout, неизвестной ошибке или неподтверждённой acceptance остаётся STOP, receipt/recovery и exact-request путь UC-RDG-004; отсутствие receipt само по себе не доказывает отказ.

Пользователь читает опубликованные данные после «Обновить» в Viewer. Три кнопки «Граф», «Структура», «Markdown» показывают одну линзу. Полный исходник и source-map доступны в Info; техническая schema остаётся у установленного API. Для самой публикации этих данных обновление Windows-runtime не требуется.


## Локальный Helper

### Предпосылки и выбор режима

Helper работает с уже настроенным `RDG_AUTH_STORE` и существующим `RDG_AUTH_TOKEN`, переданными приватным способом. Для чтения нужны подходящие `graph.read`/`plan.read`, для изменения — отдельные `graph.write`/`plan.edit`; scopes и пути должны соответствовать выбранным owners. Store авторизации должен находиться вне корня, переданного через `--root`. Новые grants этот маршрут не выдаёт; токены, содержимое приватной сессии и session URL не помещать в документы, screenshots или общие логи.

Для зависимостей нужен доступный Gendocen runtime и явно выбранный persistent каталог `--gendocen-project`, отдельный от Graph/Plan owners. Подготовка движка не заменяется пустым успешным отчётом. Для `files` заранее нужен существующий родительский каталог на уже разрешённом общем расположении, доступном Helper и браузеру; сама папка сессии должна быть **новой**, заданной абсолютным путём и без symlinks. Не добавлять монтирования ради запуска автоматически.

| Выбор Graph/Plan | Транспорт | Эффект запуска |
| --- | --- | --- |
| `--auto-workspaces` | Только `files` | Обнаруживает рабочие графы в актуальном индексе; может создать отсутствующие Plan owners через авторизованный writer. |
| `--contexts-file` | Только `files` | Использует явное сопоставление owners; также инициализирует отсутствующие Plan перед файловой сессией. |
| `--graph` вместе с `--file` | `files` или `loopback` | Один явно выбранный Graph и Plan; автоматического создания отсутствующего Plan здесь нет. |

Выберите ровно один способ задания контекста. `--graph` — путь Graph относительно `graphs/`, `--file` — путь Plan относительно `--root`. Для обычного расположения проекта корнем служит каталог `rd-graphs`, а Plan находится под `plans/`. Сочетание `--auto-workspaces` или `--contexts-file` с `loopback` отклоняется как `MULTI_CONTEXT_FILES_ONLY`.

**Создание Plan при запуске — запись:** для каждого отсутствующего Plan требуются `plan.create` и `plan.read` на его путь, а также чтение исходных Graph. Проверка всех отсутствующих Plan предшествует созданию; существующие Plan проверяются по identity и не сбрасываются. Это не обещание атомарной операции на нескольких owners. Перед запуском убедитесь, что возможное создание входит в разрешённую задачу; команда с `--auto-workspaces` не является проверкой только для чтения.

### Форма запуска и проверка подключения

Пример для подготовленной файловой сессии. Замените параметры фактическими разрешёнными путями; запускать только после проверки перечисленных условий:

```sh
python3 -B tools/rdg-workflow-helper.py --manual-session \
  --root /ABSOLUTE/PATH/TO/rd-graphs --auto-workspaces \
  --transport files --session-dir /ABSOLUTE/PRIVATE/SESSION \
  --gendocen-project /ABSOLUTE/PATH/TO/rd-graphs/.rdg-gendocen-projects
```

1. После успешного запуска в Viewer откройте «План во времени» → настройки подключения → «Подключить папку сессии». Выберите **созданную Helper папку сессии**, разрешив браузеру чтение и запись для обмена запросами. Это не выбор корня проекта или папки Graph. Если выбор папки в браузере недоступен, файловый маршрут не подтверждён.
2. Проверьте сообщение подключения, соответствие выбранного Graph/Plan и чтение истории; затем вкладку «Зависимости», если движок подключён. Пометка опубликованного snapshot сама по себе не подтверждает живой Helper. Для проверки связи достаточно чтения: создавать Action или менять Plan не требуется.
3. Для `loopback` задайте одну существующую пару `--graph`/`--file` и откройте приватный локальный URL, напечатанный Helper, в браузере **того же компьютера**. Автоматический поиск нескольких workspaces для этого транспорта не поддержан. Сетевой адрес Docker/удалённой среды не становится доступным браузеру пользователя автоматически.
4. По окончании завершите Helper. Для файлового режима новая сессия использует новую папку; выбранная ранее папка не доказывает, что прежний процесс ещё работает. После ошибки или неопределённого исхода сначала перечитайте фактическое состояние, затем решайте вопрос повтора.

Отсутствие прав, owner или engine показывается как ошибка/недоступность, а не как пустой успешный результат. Точную реализацию режимов определяют `tools/rdg-workflow-helper.py` и `tools/rdg-workflow-ui.js`.

## Изолированная проверка Decision PR-6

```sh
python3 -B tests/rdg-decision-integration.test.py
bash tools/rdg-visual-test.sh tests/visual/rdg-decision-integration.cjs
python3 -B tools/build-rdg-layout.py
node --test tests/rdg-documentation.test.cjs
```

Browser fixture запускает обычные Application/PortableEditor/loopback/generated Viewer на новых temporary owners; private synthetic authority остаётся внутри fixture и не выводится в отчёт. Не запускать его над живым root. Проверяются первый order-only Plan v3, положение canonical блока и restart с пустым browser profile. В этом историческом fixture проверялась только main lane; текущие ветви описаны в [контракте](RDG-ACTIVE-CONTRACT.md#возможные-ветви-plan). Occurrences и cross-owner Plan не поддержаны. Общий key процесса используется Graph/WG/focus. Полный scope D3–D9 и Windows acceptance остаётся отдельным.

`python3 -B tools/rdg-agent.py lens --lens work --model-profile rdg-decision-v1` читает профильный вариант фундаментальной инструкции без доступа к частным owners. Portable `lenses/lens/open` читает реальные role=lens пакеты namespace; файл определения сам по себе не устанавливается в пользовательский каталог.

## Исключительная разрушительная процедура

**Полный reset разрешён только registered teaching Graph, и не запускается рядом с Helper/редактором.** Единственная инструкция/команда — [RDG-TEACHING-EXAMPLE-RESET](RDG-TEACHING-EXAMPLE-RESET.md). Не копировать её в остальные документы и не запускать без прямой необходимости. Сброс обычных рабочих графов запрещён.

## Что должно быть сказано пользователю

Различайте: реализовано в repo / проверено изолированными тестами / установлено у пользователя / формально принято Stage 4. Последние два статуса **не подтверждены** исходниками. Не утверждать commit/push, если нет `.git`; не трактовать отсутствие `action_executed` как результат выполнения. При изменении модели обновлять и [контракт](RDG-ACTIVE-CONTRACT.md), и аудит.

## Кодовые модули

Подключение и отключение: авторизованный Helper и панель «Модули»; права и границы протокола см. [RDG-MODULES](RDG-MODULES.md). Изолированная проверка с временным Helper и Chromium: python3 -B tests/rdg-modules.test.py -q. Она не подключает тестовый пакет к рабочим owners. После обновления кода/реестра перезапустите свой Helper; перезапуск общего Tunnel не требуется.

## Рабочий чат и создание workspace

Клиент tools/rdg-agent.py использует существующий доступ, пишет как assistant и не выдаёт grants. Приватные ссылки authStore/tokenFile позволяют запускаться из отдельных Repo shell-процессов без токена в аргументах; формат и рабочие команды — только в [bootstrap](RDG-AGENT-BOOTSTRAP.md). Подготовка токена/Plan выполняется владельцем или уже авторизованной средой в разрешённом охвате, не самим рабочим чатом.

tools/rdg-new-workspace.py теперь создаёт candidate-v6 через canonical Graph package writer с transactionId и существующим bearer, включая --dry-run с проверкой прав. Обхода через прямую запись JSON нет. Команда создаёт только Graph: Plan и grants автоматически не создаются. Укажите действительную цель пользователя; после создания приготовьте отдельный Plan owner штатным API или разрешённым Helper startup, прежде чем передавать контекст рабочему чату.


## Профиль уточнённой модели

Новый owner создаётся существующим авторизованным rdg-new-workspace.py с --core-model. Это выбор схемы для нового разрешённого scope, не миграция или reset. В готовом контексте используйте rdg-agent open/schema/command/receipt; core_* операции и data определены в RDG-ACTIVE-CONTRACT. Helper показывает собственные графы R/A/канонов и использует тот же package writer. Сохранять отдельные права Plan и факты его размещения. Установка пользователю, текущая версия Tampermonkey, удобство UI и Stage 4 acceptance подтверждаются отдельно. После функциональной правки выполнять необходимые регрессии и аудит затронутых активных документов; WIP-модули не расширять попутно.

## Контрактные fixtures Decision v1 — исторический этап 2026-10-27

Первый этап был зафиксирован в [техническом контракте](RDG-DECISION-V1-CONTRACT.md). Команды ниже проверяют schema/fixtures и сами по себе не тестируют runtime. Минимальный writer/Application-путь `rdg-decision-v1` после этого реализован в D1/D2; текущий статус и адресные runtime suites указаны в [состоянии](RDG-CURRENT-STATE.md) и [плане](RDG-DEVELOPMENT-PLAN.md).

```sh
node --test tests/rdg-decision-contract.test.cjs
node --test tests/rdg-documentation.test.cjs
python3 -B tests/rdg-lens-catalog.test.py
```

Нужен Ajv 8 Draft 2020; `RDG_AJV_PACKAGE` указывает существующий установленный модуль. В Fortis suite использует существующий `/opt/dc/node_modules/ajv/dist/2020`. Это dev/test dependency, не зависимость пользовательского Viewer. Новый профиль доступен через поддержанные маршруты Application/Agent/CLI/Helper для synthetic owners; это не означает, что все старые readers или интегрированный Viewer его поддерживают. `--core-model` и старые owner paths нельзя считать автоматической миграцией существующих R/A данных.

## Актуальный пример после изменения модели/UI

После каждого крупного изменения создавать новый полноценный учебный процесс через общий schema → preflight → apply → receipt. Он должен сохранять содержательную сложность предыдущего и демонстрировать текущие возможности; старые процессы не пересобирать и не удалять ради актуальности примера. Метки учебных результатов не выдаются за выполнение боевых работ.

Основной учебный рецепт и проверенный снимок указаны в [текущем состоянии](RDG-CURRENT-STATE.md#основной-учебный-рецепт-после-уточнения-2026-11-12). [Изолированная приёмка](../../tests/rdg-current-example.test.py) входит в CI; она не доказывает обновление Windows-runtime. Создавать либо обновлять пример только по предметному поручению после проверки совместимости schema. Команда запускает рецепт в Fortis-контейнере с `--context /workspace/repo/Workfiles/rdg-gateway-context.json`, постоянным `--journal` в Workfiles и `--expected-source` проверенного исходника. При обрыве повторять тот же journal: он сохраняет transactionId/request/inputBinding, а не создаёт второй процесс. Успех — EXAMPLE_READY и чтение созданного owner. Смена scope примера требует нового path/journal, не перезаписи существующего. Исторические owners сохраняются; новый пример на каждый этап автоматически не создаётся.

## Завершение этапа и очистка

**Очистка тестовых процессов (2026-10-31).** `tools/rdg-ci.py` запускает каждую Python/Node/визуальную проверку в своей POSIX session/process group, ограничивает время ожидания, посылает группе SIGTERM, даёт до 8 секунд на штатный выход и использует SIGKILL только для непокинувших группу тестовых процессов. На Linux CI-лаунчер становится *subreaper* для своих потомков и собирает их завершённые состояния (`waitpid`); это не изменение PID 1, не право на чужие PID и не перезапуск сервисов. `tests/visual/rdg-server.cjs` отдельно завершает Chrome и собственные группы Gunicorn/Caddy при ошибке, SIGTERM, SIGINT и обычном завершении, с ограничением ожидания. Запуск `node --test ... | tail -n ...` без контролируемого завершения не использовать: конвейер ранее оставил `node`/`tail`; вывод сохранять через лог-файл или запускать напрямую. При тесте RDG browser fixture PID/cgroup до и после должны быть стабильны. Существующие зомби, принятые PID 1 (`sleep infinity`) **до исправления**, из CI-лаунчера не собрать; для устранения корня на будущей доверенной пересборке контейнера рассмотреть Docker `init: true`, но не менять действующий контейнер без отдельного разрешения.

После каждого существенного этапа рабочее дерево должно показывать действующие правила и следующую работу. Предыдущие версии файлов сохраняет Git; обычное завершение не требует новой папки `before`, backup-копии, handoff или второго плана.

1. Сверьте результат с критериями этапа. В существующем рабочем плане укажите фактически выполненное, проверки, ограничения и оставшиеся находки. Приёмка и решения пользователя фиксируются только при наличии подтверждения; запись плана и PASS теста сами по себе их не заменяют.
2. Обновите применимые действующие документы у их владельцев: поведение — в контракте, команды — в этом регламенте, направление и остаток работы — в плане, навигацию — в карте текущего состояния и README. Файлы действующих инструкций зарегистрированы в `docs/DOCS-POLICY.json`. Кандидатный вариант должен сохранять свой статус.
3. Определите конкретные ненужные материалы: заменённые планы и отчёты, временные инструкции, дубли и исходные копии `before`. Сначала перенесите необходимые решения, ограничения и незакрытые находки в соответствующий рабочий источник. Сохранённые исторические байты не переписывайте ради новой модели.
4. До удаления убедитесь, что точная удаляемая версия доступна в Git. Проверьте `git status`, staged и unstaged diff, а также вложенные неотслеживаемые файлы. Новый файл или локальная правка ещё не сохранены только потому, что каталог является репозиторием. При необходимости сначала зафиксируйте выбранные файлы; если нужные байты уже есть в доступном коммите, дополнительная backup-копия не нужна.
5. Проверьте входящие ссылки и потребителей: импорты и fixtures тестов, build/helper scripts, пути документации, provenance и hash pins. Связанный с текущей задачей дизайн, необходимый первоисточник или используемую фикстуру сохраняйте до устранения зависимости. После этого удаляйте только выбранные пути через `git rm -- ...` и исправляйте затронутые редактируемые указатели. Размер, возраст и статус «архив» сами по себе не доказывают ненужность файла.
6. Просмотрите diff, выполните аудит документации и подходящие проверки потребителей, затем проверьте фактический Git status и зафиксируйте выбранные изменения. Для существенной очистки используйте отдельный коммит с причиной: его родитель сохраняет удалённые версии. Сообщите, что убрано, что оставлено из-за зависимости и какие проверки выполнены.

Минимальная проверка документации после обновления или очистки:

```sh
node --test tests/rdg-documentation.test.cjs
```

Список действующих документов без повторного ручного реестра:

```sh
python3 -B tools/rdg-docs-audit.py --list-active
```

Обычный `rg` использует `.ignore`, который скрывает архивные каталоги и `*-HISTORY.md` из результатов. Для конкретного исторического источника задайте его путь и `--no-ignore`; для полного inventory версионируемых файлов используйте `git ls-files`. Скрытая из поиска зависимость остаётся частью scope её потребителя. Аудит документации обходит файлы самостоятельно и проверяет сохранённые документы независимо от `.ignore`.

Для чтения удалённого файла найдите коммит через `git log --oneline -- path/to/file`, затем прочитайте `git show COMMIT:path/to/file`. Восстановление выбранной старой версии выполняйте после проверки текущих изменений. Не откатывайте весь проект ради одного файла.

Очистка документации не разрешает удалять живые Graph/Plan, их историю, journal/recovery payload, Gendocen state или evidence, необходимое для интерпретации текущих данных. Их удаление регулируется предметными writers и правами. Игнорируемые профили браузера, приватные сессии и секреты могли вообще не попасть в Git; возможность восстановления для них не предполагается. Git не является основанием публиковать приватные данные.


<!-- RDG SERVER PACKAGE BEGIN -->
# RDG — отдельный сервер на Fortis_M

RDG и private API gateway используют прежние Application/Authority/FileStore и generated Viewer. Обновление сохраняет существующий namespace, Graph/Plan и credentials. Новый namespace начинается пустым; первые supplied lenses устанавливаются при явном создании процесса. Живые owners из Windows preview автоматически не импортируются.

Вне Docker действия выполняет пользователь. Скрипт управляет Compose project `rdg-personal` и подключает явно выбранный рабочий контейнер к private network. Общий Tunnel и настройки Windows он не перезапускает.

## Запуск на Fortis_M

Нужны Docker с Linux containers, Compose v2 и свободное место на Windows-диске Docker. Распакуйте весь ZIP в новую папку кода. В PowerShell из каталога RDG-Server:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Start-RDG.ps1 -Mode Local -AgentContainer CONTAINER_ID
```

`CONTAINER_ID` замените ID существующего рабочего Fortis Repo Docker. Скрипт проверяет файлы по SHA256, выбранный контейнер и доступность записи в Workfiles, собирает image, запускает одноразовый setup и сервисы. При обновлении setup возвращает `alreadyInitialized: true`; прежний пароль сохраняется.

Local mode открывает `http://localhost:18880` на самом Fortis_M. Caddy публикует только loopback; RDG и gateway не публикуют собственные host ports. Логин браузера — `rdg`. Пароль прочитайте только в своей консоли:

```powershell
Get-Content "$env:LOCALAPPDATA\RDG-Server\secrets\browser-token.txt"
```

После запуска ожидаются `Private API check: OK`, `Unrelated container isolation check: OK`, `Windows HTTP check: OK` и `Browser ingress machine API check: blocked`. Сам Compose healthy не считается доказательством доступности из Windows.

Если входящий 18880 занят, namespace/ключи не пересоздавайте: сначала проверьте конфликт порта. При EROFS/EIO восстановите Docker storage до повторного запуска. `Stop-RDG.ps1` останавливает сервисы, сохраняя volumes.

## Где находятся ключи и данные

Данные RDG остаются в `rdg-personal_rdg_data`. Ключи оператора хранятся в `%LOCALAPPDATA%\RDG-Server\secrets`, вне папки сборки. Setup читает только существующие assistant token/namespace для отдельного закрытого volume `rdg-personal_rdg_gateway_secret`; его каталог имеет mode 0700, файл — 0600 и UID 10001. Serving gateway получает этот volume только для чтения по `/run/rdg-gateway`. RDG, Caddy и рабочий Docker этот volume не получают. Owner/browser credentials в gateway не копируются.

Setup — одноразовый операторский процесс с доступом к bootstrap данным; это не рабочий контейнер ИИ. Изоляция ключа достигается отдельным volume/контейнером, а не хранением bearer в файле рабочего Docker. Ключи не входят в image, ZIP, context клиента или вывод launcher.

## Private API для ИИ

Рабочий Docker обращается к `http://rdg-api-gateway:8081/api/command` по сети `rdg-personal_agents`. Шлюз принимает стандартный JSON Application message, проверяет namespace и сам добавляет свой scoped assistant bearer при передаче в фиксированный `rdg:8080`. Arbitrary URL/Host/Authorization, cookies/Origin, shell и файловые methods не принимаются. Application сохраняет attribution assistant, права, CAS, preflight, receipt и exact retry. Browser и AI имеют отдельные actor-owned view sessions.

Launcher подключает только явно выбранный рабочий контейнер, проверяет неожиданных участников agents network и не отключает их автоматически. Запрещены выбранный privileged container, shared PID namespace, Docker socket или mount, открывающий RDG data/credential files. Из отдельного временного контейнера на edge network проверяется отказ прямого TCP-доступа к private gateway IP. Негативная проверка не получает ключей/данных.

После успешной проверки gateway из рабочего Docker launcher создаёт **несекретный** context `/workspace/repo/Workfiles/rdg-gateway-context.json`:

```json
{
  "profile": "gateway",
  "origin": "http://rdg-api-gateway:8081",
  "namespaceId": "SERVER_NAMESPACE_UUID"
}
```

Никакой tokenFile для этого профиля не нужен и не разрешён. В Repo Docker:

```sh
python3 -B tools/rdg-agent.py doctor --context /workspace/repo/Workfiles/rdg-gateway-context.json
python3 -B tools/rdg-agent.py catalog --context /workspace/repo/Workfiles/rdg-gateway-context.json
```

Для стандартного message доступен `tools/rdg-remote-client.py --context FILE` с JSON на stdin. API команды идут через прежний coordinator/writer. После внешнего изменения нажмите «Обновить» в Viewer.

Browser ingress отклоняет `/api` и `/api/*` с 404 даже при наличии bearer. Browser `/session/*` продолжает требовать Basic credential, Origin и CSRF. `/healthz` содержит только состояние сервиса. Machine gateway не публикует host port и не заменяет браузерную аутентификацию.

Доступ разрешён **контейнеру, а не конкретному чату**: любой процесс в допущенном рабочем Docker может использовать выданные RDG API права. Gateway также связан с доверенным backend RDG/Caddy. Администратор Docker/Windows остаётся доверенным; агенту Docker socket и host tools для настройки не предоставляются. Скрытие ключа не уменьшает grant permissions само по себе. Отзыв действующего assistant grant проверяется RDG на каждом запросе.

При пересоздании рабочего Docker передайте новый ID через `-AgentContainer`. Состав сети проверяется повторно. Старые/неожиданные подключения оператор рассматривает отдельно.

## Внешний браузерный HTTPS

После настройки собственного DNS name и входящих 80/443 к Fortis_M:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Start-RDG.ps1 -Mode HTTPS -Domain rdg.example.com -AgentContainer CONTAINER_ID
```

Имя и ID замените своими. HTTPS mode запускает Caddy с постоянными certificate volumes. При занятом 80/443 не останавливайте чужой сервис; согласуйте отдельный маршрут. Machine API остаётся private и при HTTPS mode. DNS, firewall, port forwards и общий Tunnel автоматически не меняются.

## Границы проверки

Для **RDG Graph lock-set/remove** в этом RDG runtime нет native human approval: операции требуют `VERIFIED_APPROVAL_REQUIRED`, пароль не выдаёт human proof. Это ограничение RDG-local lock workflow, а не Fortis R7 Sonar Approvals: Fortis owner WebAuthn и live Sonar Approve уже работают. Нет управления чужой browser view_session. Полная RDG UX/Stage 4 acceptance не выводится из backend/API PASS.

Автотесты HTTP и extracted runtime выполняются на временных owners/credentials. Реальное подключение выбранного Docker, отрицательный network test, Windows PowerShell/HTTP и публичный TLS подтверждаются по запуску оператором. После проверки A0 тестовый Decision процесс и матрица A1–A17 создаются/исполняются через private API. Данные прежних процессов не используются как destructive fixtures.

Не выполняйте `docker compose down -v`, удаление volumes или Docker Clean/Purge/Factory reset для обычного обновления: это может удалить данные.

<!-- RDG SERVER PACKAGE END -->

**Fortis Approvals/Sonar — уже работающий контур для одного actor/project:** R7 Unified Gateway принимает typed READ/ASK, владелец подтверждает точную заявку через WebAuthn, затем Sonar Issue переходит в `ACCEPTED` с независимым readback. Это не означает, что защищённая доставка кода уже внедрена: GitHub PR/required checks, exact SHA admission, Windows Importer/AV и owner RUN остаются отдельными будущими D1–D4 gates. Ниже описан **существующий legacy RDG updater**, который может получить ZIP прямо из Fortis Repo Docker; он не обеспечивает эти D1–D4 guarantees. См. [Fortis current state](FORTIS-APPROVALS-SECURE-DEVELOPMENT.md). Credential и Docker admin не передавать AI. Принятые Graph/Plan/namespace/volumes сохранять.

## Разработка и обновление серверного runtime

1. Изменить source и подходящие тесты; сохранить чужой staged/dirty worktree.
2. Запустить `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 PYTHONWARNINGS=ignore python3 -B tools/rdg-ci.py`. Проверки используют временные owners. Во время прогона исходники не менять.
3. Проверить `status.json`, `ready.json`, SHA архива и совпадение source fingerprint. READY указывает на проверенный код, а не на установленный сервер.
4. ИИ выдаёт пользователю готовую команду PowerShell с фактическим ID рабочего Fortis Repo контейнера, точными `ExpectedBuildId` и `PinnedSha256` проверенного ZIP. Исходник bootstrap хранится в [Invoke-RDG-Ready-Once.ps1](../../deploy/rdg-server/Invoke-RDG-Ready-Once.ps1). Команда копирует его проверенную передаточную копию из новой task-папки `/workspace/repo/Workfiles/_fortis_windows_transfer_tmp/` и запускает установку. По общему регламенту Fortis сначала проверить running-контейнер, создать новый локальный каталог без перезаписи и сверить заранее вычисленный SHA256 самого bootstrap; только затем исполнять его с точными buildId и ZIP SHA256. Перед выдачей проверить исходник bootstrap, расположение копии и соответствие значений READY. Не оставлять пользователю подстановку этих значений вручную.
5. Пользователь выполняет команду в PowerShell на Windows, вне Docker. Setup сохраняет действующие данные и credentials. Сам READY не подтверждает этот шаг.
6. После успешного установщика проверить установленный `/healthz` buildId; пользователь нажимает F5 в RDG и проверяет нужный сценарий. Readback и пользовательская UX-приёмка остаются отдельными свидетельствами.

Файлы release gate: [CI](../../tools/rdg-ci.py), [packager](../../tools/rdg-server-package.py), [тесты CI](../../tests/rdg-ci.test.py) и [CD](../../tests/rdg-cd.test.py). Текущий outbox — `/workspace/repo/Workfiles/rdg-ci`; команда «обновить Windows» не исполняется в Linux Docker как будто это Windows host.


## Тестовый процесс A0–A17 через private API

На Fortis_M через gateway создан «RDG — сквозная проверка API», package `5ac9f3ec-2783-5b7e-802d-1b3518bbc371`, path `api-tests/rdg-acceptance-20261029`. Нажмите «Обновить» в Explorer, откройте процесс или одну из четырёх вложенных WG, затем Plan. В нём 18 проверок без назначенных дат; это план приёмки, не отметка об их выполнении. Ручная оценка Viewer и restart сервера выполняются отдельно от API readback.

Исходная opt-in фикстура находится в Repo, не в серверном ZIP. Она создаёт только свой новый тестовый процесс через общий API, сохраняет точные requests/inputBinding до отправки и возобновляет работу по тому же журналу. Контекст gateway не содержит bearer. В Repo Docker из корня проекта:

```sh
python3 -B tests/rdg-api-acceptance-seed.py seed --context /workspace/repo/Workfiles/rdg-gateway-context.json --state /workspace/repo/Workfiles/rdg-api-acceptance-20261029.json
```

Для повторного чтения и exact retry начального неизменённого seed:

```sh
python3 -B tests/rdg-api-acceptance-seed.py verify --context /workspace/repo/Workfiles/rdg-gateway-context.json --state /workspace/repo/Workfiles/rdg-api-acceptance-20261029.json
```

Не удаляйте журнал ради повторного запуска: его transactionIds предотвращают дубли. Удаление журнала не удаляет процесс; новая попытка с тем же path должна отказать при конфликте. После ручных изменений или выполнения task Actions первоначальные seed assertions могут уже не соответствовать данным; продолжайте проверку через schema/read/preflight/apply/receipt, а не пересоздавайте owner. Фикстура не является crash injection и не перезапускает сервер. Полный план A0–A17 — в [едином плане](RDG-DEVELOPMENT-PLAN.md#сквозная-проверка-через-api-и-граница-доступа-ии--2026-10-29).

## Переносимые пакеты: Agent и Helper

Этот маршрут использует уже разрешённый package root и существующий portable grant. Обычный запуск не включает grants, migration или запуск инфраструктуры; отдельный opt-in migration описан ниже.

Пример приватного Agent context без токена:

```json
{
  "profile": "portable",
  "packageRoot": "/ABSOLUTE/AUTHORIZED/PACKAGES",
  "namespaceId": "EXISTING-NAMESPACE-UUID",
  "coordinationRoot": "/ABSOLUTE/AUTHORIZED/COORDINATION",
  "packageId": "EXISTING-PACKAGE-UUID"
}
```

Credentials поступают через существующее окружение либо ранее описанные приватные authStore/tokenFile. Команды: `rdg-agent.py catalog/open/schema/preflight/command/receipt/history` с `--context FILE`; `schema --action copy|apply_ready|insert_copy|delete|place|unplace|plan_create|move|folder_create|folder_move|core_edit` выдаёт форму. Для `core_edit` используются действующие core data; `--source-package-id` выбирает шаблон/источник. Сохранённый request передают на stdin `preflight`, затем без изменения transactionId — `command`. После неопределённого исхода читают receipt и при необходимости повторяют тот же request.

**RDG-local pilot ожидающего запроса.** Следующие команды `approval_request`/`approval_read` относятся к RDG Portable Application и Graph/Plan intent, а не к Fortis Sonar Gateway. Для Fortis Sonar используйте `fortis_approvals.sonar_review_scenario` и [текущий Fortis runbook](FORTIS-APPROVALS-SECURE-DEVELOPMENT.md). В portable context команды вызывают тот же RDG Application. На stdin `approval_request` передают объект с двумя полями: `request` — точный штатный запрос с transactionId; `rationale` — содержательное объяснение. Команды из корня проекта:

```sh
python3 -B tools/rdg-agent.py approval_request --context FILE < proposal.json
python3 -B tools/rdg-agent.py approval_read --context FILE --transaction-id REQUEST_ID
```

`FILE`, `proposal.json` и `REQUEST_ID` обозначают фактические разрешённые context, тело предложения и ID. Прямой `rdg-portable.py` поддерживает те же команды с обычными packages/namespace/store аргументами. Создание предложения пишет pending metadata и unaccepted intent; Graph/Plan и grants не изменяет. Для create/copy допускается targetless request без targetPackageId: его prepared checks фиксируют destination/source read set, а exact executor может после native decision создать новый package. При чтении заново проверяются исходный bearer и scope. После timeout сначала прочитайте `approval_read` с прежним ID; точный retry сохраняет один запрос. Если тело или rationale нужно изменить, используйте новый ID.

Для явной проверки preview сохраните поле `inputBinding` из `preflight` как JSON и передайте его через `--expected-input-binding FILE` в portable `preflight/command` Agent либо `preflight/apply` прямого CLI. Тело запроса и transactionId сохраняются. При `PREVIEW_INPUTS_CHANGED` нужен новый preview; изменившееся тело/expected revisions получает новый request ID. Точный retry уже принятой операции завершает прежний accepted intent по действующему recovery contract.

Обычный CLI/Agent не предлагает approve/reject. Internal executor подключён к тому же Viewer только через явно настроенный opt-in host transport, описанный ниже. Pending preview остаётся снимком. `humanApprovalVerified=false` сохраняется, в том числе при `attribution=user`; hard lock и отсутствие Plan/scope не отменяются. В изолированном execution proof статус может стать `rejected`, `approved-awaiting-recovery` либо `executed-approved`; это не установка готового пользовательского контура. Для принятой записи recovery выполняет только сохранённый payload. После Reject нужен новый ID для нового действия. File move/folder/migration по-прежнему явно отклоняют pending/exact approval, но их обычные preflight/apply теперь возвращают adapter-specific inputBinding: filesystem tree/package heads/catalog для transfer и legacy source read-set/discovery/catalog для migration. Полные границы — в [контракте](RDG-ACTIVE-CONTRACT.md); проверки и остаток работы — в [плане](RDG-DEVELOPMENT-PLAN.md).

**Approval в основном Viewer.** Loopback Helper имеет opt-in Python API `make_server(editor, approval_factory=..., listen_port=...)`. Factory получает фактический localhost origin и возвращает настроенный `ApprovalSurface`/`ApprovalExecutor`. Фиксированный порт позволяет сохранить точный origin после restart; по умолчанию порт выбирается автоматически. Это вход доверенного host-кода. CLI flags, ordinary JSON messages и FileSession не задают factory/principal/grant/key binding. Для persistent mode тот же host передаёт `CredentialStore` существующего Authority и, только при регистрации, одноразовый `enrollment_permit`. Это API интеграции; он не устанавливает защищённый runtime.

При явно настроенной factory Helper обслуживает endpoint `approval` с session/Host/Origin проверками. Viewer показывает запросы и native WebAuthn Approve/Reject. В persistent mode приглашение владельца дополнительно включает регистрацию назначенного ключа в том же Viewer; bearer/permit в браузер не вводят. В verified host управление замками создаёт pending request и требует подтверждения; обычные unlocked writes сохраняют свой путь. Без factory capability отсутствует. После timeout/lost response сначала читается status. Recovery доступна только принятой версии 2 и не требует повторной подписи.

**Управление persistent credentials.** `tools/rdg-credentials.py` работает только в POSIX runtime с существующим Authority. Команды выполняет владелец в своей защищённой сессии из доверенной копии кода. Его существующий owner bearer поступает через `RDG_AUTH_TOKEN`; передавать его Agent, в аргументы, чат или логи не требуется. Delegated `grant.admin` недостаточно. `AUTH_FILE` ниже — абсолютный путь существующего Authority вне исходников; это не команда инициализации grants. `N` — текущая revision конкретного binding/credential из inspect, для нового binding — 0.

```sh
python3 -B tools/rdg-credentials.py inspect --store AUTH_FILE
python3 -B tools/rdg-credentials.py configure --store AUTH_FILE --expected-revision N < binding.json
python3 -B tools/rdg-credentials.py invite --store AUTH_FILE --principal PRINCIPAL --permit-file ABS_PRIVATE_NEW_FILE
python3 -B tools/rdg-credentials.py revoke --store AUTH_FILE --credential-id CREDENTIAL --expected-revision N
```

`binding.json` задаёт ровно `principalId`, `displayName`, `namespaceId`, `executorGrantId`, `authorityPrincipal`, `rpId`, `origin`, `active`. Grant должен уже существовать и для активной привязки иметь scope нужного namespace. Команды не создают grant и не расширяют права. Invite создаёт новый файл с mode 0600 вне исходников, не перезаписывает прежний и не печатает raw permit. Permit действует 120 секунд; доверенный host читает его приватно и передаёт настроенному surface. После прерванной регистрации или истечения срока владелец выдаёт новое приглашение. Зарегистрированный ключ и counter сохраняются; незавершённое подтверждение после restart начинается заново.

Для повторной криптографической проверки сохранённой подписи нужен Python с зависимостями `requirements-webauthn.txt`:

```sh
/workspace/repo/.rdg-webauthn-venv/bin/python -B tools/rdg-credentials.py audit --store AUTH_FILE --proof-sha SHA
```

`SHA` берётся из verifier receipt. Audit не исполняет Graph и возвращает `authorizesNewExecution=false`; подпись может быть сохранена и у операции, которую затем заблокировал final gate. Отзыв ключа запрещает новую acceptance, но не отменяет recovery уже принятого точного payload. Credential state имеет отдельную revision; grants/revision от этих команд не меняются.

**Проверка контекста принятия решения в основном RDG — 2026-11-03.** По явному запросу владельца через Application API в основном RDG создан *обычный процесс* «Пример процесса · выбор хранилища» (`examples/process-decision-context-postgresql`). Откройте в обычном Explorer `Графы → Пример процесса · выбор хранилища`, затем Decision «Использовать PostgreSQL». Связь `R1 → D-STORE` — родитель, `R-COST`, `D-HOST`, `C-HOST` — три ссылочных факта этого процесса, `CANON-STORE` — теоретическая справка. При обновлении списка используйте «Обновить» или F5; вид с разделом «Контекст принятия решения» требует соответствующей версии Viewer. Запись сделана однократно через `schema/preflight/apply` с подтверждённым readback, а не через seed в launcher. После отдельного пользовательского запроса тот же учебный процесс расширен до **18 сущностей, 15 типизированных связей, трёх рабочих областей**: «Выбор хранилища и требований к данным» (11 членов), «Развёртывание и изменение схемы» (8), «Надёжность и восстановление» (5). Все области ссылаются на объекты исходного process owner; `D-STORE` входит в две области, `C-HOST` в три. **Plan процесса** общий и содержит три запланированных Action из разных областей; History тоже принадлежит процессу. В Explorer раскрыть «Рабочие области и пакеты» под этим процессом и переключать их; `Весь процесс` показывает все сущности. В исходном проверочном процессе и 11 линзах ничего не менялось.

**Ручная проверка Decision — 2026-10-29, fix2.** На Windows запустите [Start-Decision-Preview.cmd](../../Start-Decision-Preview.cmd) из актуальной копии исходников либо полностью распакованной Decision-preview сборки. Нужны Python 3 (проверен 3.11) и Node.js 18+ в PATH. Launcher создаёт отдельный venv в `%LOCALAPPDATA%\RDG-DecisionPreview`, при необходимости устанавливает `requirements-decision-preview.txt` и открывает обычный браузер. Tampermonkey и регистрация WebAuthn-ключа этому режиму не нужны.

Данные сохраняются в `%LOCALAPPDATA%\RDG-DecisionPreview\data`, отдельно от исходников и старого preview; порт по умолчанию 8795. В новой песочнице создаётся один Decision-процесс и 11 supplied линз через настоящий Application. Для остановки — Ctrl+C в оставленной открытой консоли; повторный запуск продолжает тот же namespace и данные. URL сессии меняется, точный адрес появляется в консоли. Занятый порт автоматически не освобождается. Чужой непустой data-dir и marker другого режима отклоняются без удаления.

Обновление fix2: остановите прежнюю консоль, извлеките архив в `%LOCALAPPDATA%\RDG-DecisionPreview\build-20261029-fix2` и запустите вложенный `RDG-Decision-Preview\Start-Decision-Preview.cmd`. Data остаётся прежней. Метка — `Decision UI · 20261029-fix2`. Сразу открывается полноэкранный Explorer: выберите процесс «Ручная проверка Decision» либо его область. После закрытия последней вкладки снова показывается Explorer. Fix1 блокировки Windows сохранён; ошибки каталога видны здесь же. Каталоги больше не перечитываются на каждом открытии панели/фокуса.

Прямой запуск из подготовленного Python:

```sh
python -B tools/rdg-preview.py --test-preview --model-profile rdg-decision-v1 --data-dir ABS_NEW_DECISION_DATA --port 8795 --open-browser
```

`ABS_NEW_DECISION_DATA` — новый абсолютный каталог вне исходников. Этот режим использует общий Preview IO adapter/Application/Helper, без второго writer или подключения живых grants. Фиксированный loopback-порт включается только trusted host-параметром `manual_session_port`; поле HTTP/JSON не открывает этот режим. Native Windows directory durability и защищённая изоляция по-прежнему не доказаны.

Для переноса кода из Docker создайте источник-only архив:

```sh
python3 -B tools/rdg-preview-package.py --output /workspace/repo/Workfiles/RDG-Decision-Preview-20261029-fix2.zip
```

Packager использует явный allowlist runtime-файлов и lens/contract definitions; Graph/Plan/Authority/credentials исходной среды не включаются. BUILD.json содержит hashes исходников. `tests/rdg-decision-preview.test.py` проверяет host, scopes/origin, отказы, сериализованные чтения и restart (4/4); `tests/visual/rdg-decision-preview.cjs` запускает именно распакованный архив, реальный UI/Plan/drag и новый процесс с чистым browser profile и ошибку начальной загрузки (7/7 обычный + 7/7 serialized-read). Первый пользовательский запуск Windows остаётся отдельной ручной проверкой.

**Ранний ручной просмотр — указание пользователя 2026-10-25.** Старый маршрут ниже проверяет R/A и WebAuthn; для нового Decision desktop используйте отдельный launcher выше. В существующем Windows-репозитории запустите `Start-Preview.cmd`. Нужны Python через `py -3` и Node.js. Первый запуск создаёт отдельный venv в `%LOCALAPPDATA%\RDG-ManualPreview`, устанавливает `tools/requirements-preview.txt` и открывает браузер. Учебные данные находятся в подкаталоге `data`, вне исходников; неизвестный непустой каталог preview отказывается инициализировать. Закройте консоль процесса после работы.

Откроется тот же generated Viewer с четырьмя отдельными Graph: подтверждение изменения R1, отказ от другого изменения, свободная правка и shared `info → Requirement` dependency. В панели запросов зарегистрируйте ключ, сравните «Было / Станет» и выполните оба решения; в четвёртом Graph проверьте L2 preflight, Save и readback. Учебный host автоматически готовит короткое приглашение; реальная изолированная owner enrollment этим не доказывается. Повторный запуск сохраняет данные и credential на том же порту 8794; session URL меняется. Занятый порт не освобождается автоматически.

Прямой запуск из подготовленного Python:

```sh
python -B tools/rdg-preview.py --test-preview --data-dir ABS_NEW_PREVIEW_DATA --port 8794 --open-browser
```

`ABS_NEW_PREVIEW_DATA` — новый абсолютный каталог вне исходников. CLI создаёт только свои demo Authority/grants/packages; существующие проекты и реальные grants к preview не подключаются. На Windows выбран отдельный preview adapter: реальное исключение через byte-range locks, flush файлов и readback сохраняются, directory flush отсутствует. Ordinary CLI по умолчанию сохраняет POSIX IO; preview IO/factory задаются только trusted Python composition, не JSON сообщением.

**Известный отложенный риск защищённого запуска.** Изоляция активного кода/зависимостей/Authority/executor bearer/owners от Agent не доказана. В G2 Workspace гостя доступен для записи, общие Tools запрещают запись. Пользователь разрешил отложить этот риск ради раннего ручного просмотра. Это не выдаёт новых OS-прав или разрешения на смену ACL/mounts/tunnels и не доказывает production human approval. Windows power-loss/directory durability и installed user acceptance остаются непроверенными.

Архив тестовой сборки укладывался в лимит передачи: 247 835 байт, логический набор 904 688 байт. Automatic approval review отклонил его кодирование/вывод для передачи в G2: не было явного разрешения на приватный payload и destination. Архив не передан; подготовлен запуск прямо из существующего репозитория. Отдельный venv с публичными зависимостями подготовлен в разрешённом G2 Workspace, без переключения общих сервисов.

Техническая проверка полного Viewer на disposable synthetic owners:

```sh
RDG_WEBAUTHN_PYTHON=/workspace/repo/.rdg-webauthn-venv/bin/python \
  bash tools/rdg-visual-test.sh tests/visual/rdg-approval-viewer.cjs
```

Команда запускает временный Helper и изолированный Chromium, использует виртуальный ключ и завершает свою тестовую сессию. Для регистрации/restart/revoke тем же способом запустите `tests/visual/rdg-persistent-approval.cjs`; состав проверок — в [инструкции браузерных тестов](../../tests/visual/README.md). Эти сценарии не выдают реальных grants, не устанавливают Viewer и не создают доступный пользователю Windows endpoint.

Ручной Helper:

```sh
python3 -B tools/rdg-workflow-helper.py --manual-session \
  --portable-packages /ABSOLUTE/AUTHORIZED/PACKAGES \
  --namespace EXISTING-NAMESPACE-UUID \
  --coordination-root /ABSOLUTE/AUTHORIZED/COORDINATION \
  --transport files --session-dir /ABSOLUTE/NEW/PRIVATE/SESSION
```

В Viewer подключают именно новую session-папку. Portable descriptor выбирает каталог пакетов вместо legacy Plan editor. Loopback работает с теми же packages/namespace и `--transport loopback` в браузере того же компьютера; Docker loopback не является Windows-подключением автоматически. Helper не выдаёт grants и не мигрирует owners при старте. Границы сессии, закрытие, ошибки и отсутствие токена в браузере остаются прежними.


### Перемещение и сохранённые версии

Для пакета получите `schema --action move --package-id ID`, укажите конечный относительный `path`, прочитайте preflight и исполните тот же request. Для папки используйте `schema --action folder_move --source-folder RELATIVE`; схема содержит source tree pin. `folder_create` создаёт обычную папку. После timeout сначала запросите receipt; `recover --transaction-id UUID` завершает только уже принятую операцию исходного bearer actor, даже если тело запроса потеряно. Для непринятого запроса нужен точный retry с прежним transactionId. Новый UUID означает новую операцию, а не восстановление старой. При обнаружении неожиданных исходных bytes сохраняйте их и разбирайте recovery conflict.

Agent и portable CLI поддерживают `source_snapshot --package-id CONSUMER_ID` с Graph pin на stdin; у Agent `--node ID` выбирает focus сохранённой версии. Helper/Viewer используют тот же message contract. `history` возвращает собственные и унаследованные события, текущие/старые Plan versions и явные migration evidence gaps. Сохранённый Graph всегда открыт только для чтения. Если у копии нет Plan, `plan_create` создаёт его отдельно; копирование не выдумывает размещений.

### Явная миграция поддерживаемого owner

Настройка источников — отдельный приватный JSON-файл оператора, выбранный для конкретной задачи. Пример формы, без credentials:

```json
{
  "graphRoot": "/AUTHORIZED/COORDINATION/graphs",
  "planRoot": "/AUTHORIZED/COORDINATION/legacy-plan-root",
  "owners": {
    "selected-source": {
      "graphFile": "workspaces/selected/graph.json",
      "planFile": "plans/selected/plan.json",
      "role": "working",
      "layoutFiles": ["/AUTHORIZED/SAVED/layouts.json"]
    }
  }
}
```

`planFile/layoutFiles` необязательны; `lens` требует стабильный `lensKey`. Graph root должен использовать тот же coordination root, что и нынешние writers. Config не расширяет mount/ACL/grants. Для полноты входящих ссылок нужны уже существующие read scopes всех проверяемых Graph/Plan и права переключаемого owner; отсутствие права является блокером, а не пустым inventory.

1. Добавьте `migrationConfig` в приватный portable Agent context либо передайте Helper `--migration-config FILE`. Portable CLI имеет тот же флаг. Само подключение ничего не мигрирует.
2. Прочитайте `migration_sources`, затем `migration_inspect --source-key KEY`. Разберите blockers и evidence gaps. Неподдерживаемый current Plan нельзя обходить acknowledgement.
3. Перед switch остановите прежние writers/Helper и запись сохранённых раскладок. Включите все действительно используемые источники layouts; browser cache не доказывает их полноту.
4. Получите `schema --action migrate --source-key KEY`, выберите `path`. Только после фактической подготовки установите `confirmOwnerSwitch`, `legacyWritersQuiesced`, `presentationSourcesComplete`, `presentationWritersPaused` в `true`. При разрешимых исторических gaps отдельно установите `acknowledgeHistoricalGaps` после их просмотра.
5. Выполните preflight и тот же request через `command`. После принятия старые пути становятся read-only routes, рабочим становится packageId. При неопределённом исходе используйте receipt и точный retry; не создавайте второй перенос. Непринятый stage после конфликта не является завершённой миграцией и не удаляется автоматически. Если после обрыва до acceptance остались собственные `switching` routes, команда Agent `cancel_migration --context FILE --transaction-id UUID` (либо одноимённый метод Helper/CLI) может снять только этот непринятый switch. Требуется исходный bearer token; все journal/intent/stage/route witnesses должны согласовываться, иначе отмена блокируется. Отмена оставляет staged bytes и исходные факты, но делает прежний transactionId непригодным для retry. Для принятой операции используйте только `recover`, не `cancel_migration`.
6. Прочитайте новый пакет, историю/Plan/layouts и фактический старый route. Проверку Windows/установку Viewer выполняйте отдельно в разрешённом окружении. Ни подготовка кода, ни тесты fixtures не означают миграцию живых owners.

## Linux CI: PowerShell без системного ICU

В минимальном Repo container PowerShell 7 может завершаться до выполнения тестового updater с ошибкой `Couldn't find a valid ICU package`. Для изолированных CD fixtures, проверяющих ASCII manifests, SHA и отказные барьеры, запускать CI с `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1`. Флаг действует только в окружении этого Linux-прогона; он не меняет Windows updater или работающий RDG.

```sh
DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 PYTHONWARNINGS=ignore python3 -B tools/rdg-ci.py
```

Это не подтверждение установки на Windows. Проверка реального Windows runtime и UX остаётся отдельной.
