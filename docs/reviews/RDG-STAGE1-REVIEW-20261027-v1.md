# Проверка первого этапа RDG — Final Review v1

> **СТАТУС: АРХИВ.** Review ID: `RDG-STAGE1-20261027/v1`. Срез: 2026-10-27, Asia/Bangkok. Target: технический результат первого этапа перехода к Decision-модели, до исправлений по этой проверке. Это отдельная проверка результата этапа, не новая версия прежнего обзора плана и не приёмка будущего приложения.

## Краткий результат

Первый этап подготовлен содержательно, но его полное завершение было заявлено преждевременно. Подтверждены **две проблемы технического контракта**: у Action принятия решения может отсутствовать исход, который невозможно передать при завершении; реестр типизированных ссылок не описывает привязку экземпляра пакета к процессу. Они требуют уточнения форм и правил до соответствующей реализации. Это не утверждение о дефекте уже работающего нового backend: его ещё нет.

Приоритет внимания HIGH — F-P-1/PR-1B и F-P-2/PR-2. Для обеих Intervention Priority NEXT: нет установленного дедлайна или немедленной необратимой потери, но нельзя передавать связанные неразрешённые правила в reducer/remap как уже закрытые. Решение техническое, Autonomy HIGH; нового смыслового ответа пользователя не требуется. Предложения остаются pending, их реализация этим review не выполнена.

| Finding | Тип, конкретное состояние и последствие | Оценка на этот срез / следующий шаг |
| --- | --- | --- |
| F-P-1 | Problem: decide_acceptance принимается без decisionOutcome; complete/edit не позволяют задать его позже. Действие не имеет однозначного эффекта | CURRENT; HIGH / NEXT; разработчик закрывает DTO/переход. PR-1B предпочтителен, PR-1A — альтернатива; pending, HIGH, CURRENT |
| F-P-2 | Problem: schema хранит graphPackageId/identitySpace экземпляра, а реестр перечисляет только его memberIds/rootIds. Следование единственному реестру недостаточно для переноса области | CURRENT; HIGH / NEXT; разработчик дополняет qualified refs/политику instance. PR-2 pending, HIGH, CURRENT |
| F-R-1 | Risk: API имеет add и link отдельно; будущая одна операция UI «обязательный Action» может оставить блок без связи при отказе второго запроса | CURRENT; NORMAL / NEXT; до обещания составного authoring определить атомарную границу. PR-3A/3B pending, HIGH/MEDIUM, CURRENT |
| F-O-1 | Opportunity: schema suite проходит даже с несуществующим ID в expected activeIds; пересечение групп пока описано текстом без конкретного setup | CURRENT; NORMAL / NEXT; усилить fixtures при подключении D1. PR-4 pending, HIGH, CURRENT; deferred до этого gate |

HIGH означает важность рассмотрения, а не требование немедленно писать код. CRITICAL не выявлено. Все Findings относятся к CURRENT относительно первого этапа; пересмотр пользовательской семантики/Need не предлагается.

Рекомендуемый кандидатный набор: **PR-1B + PR-2 + PR-4**. Сначала определить фактический исход Action и qualified refs экземпляров, затем согласовать schema/примеры/проверки. PR-3A/3B выбрать до составного authoring, сохранив независимую работу над selector/основными R/D состояниями. Не выдавать принятие или описание этого набора за его исполнение.

Что открыть в отчёте: «Подтверждённые проблемы» содержит точные формы и доказательства; «Риск и возможность улучшения» объясняет границу атомарного UI и силу тестов; «Предложения и совместимый маршрут» показывает альтернативы и gates; «Покрытие и ограничения» отделяет доказанное от будущих runtime проверок. Полный отчёт сохранён в существующем проектном месте `docs/reviews/`; отдельная копия в forfiles не требуется.

## Основание и версия

User Need — продолжить существующее RDG и получить пригодный каркас приложения/Viewer/API для пользователя и ИИ. Текущий target уже ограничен первым этапом: подготовить технические контракты, а не реализовать ядро или все редакторы. Прямой запрос: «заверши первый этап», затем «проверь результат первого этапа». Условия gate находятся в `docs/guides/RDG-DEVELOPMENT-PLAN.md`, пункт 1 последовательности: схемы/identity; состояния и последствия; владельцы/durability; чтение/команды/receipts; refs/reuse/code map; refresh/drafts/conflicts. Минимальные inputs/effects должны быть однозначны; положительные/отрицательные fixtures могут существовать до исполняющего их kernel.

Сценарное основание — **B, requirement-derived**. Отдельный принятый Scenario-файл для первого этапа не установлен. Минимальный необходимый путь: разработчик читает согласованные контракты → понимает данные и допустимые команды → реализует D1/D2 без скрытого выбора политики → проверяет подготовленные ожидания. Обязательность этих переходов следует из явного задания первого этапа; конкретный выбор всех технических DTO не объявляется фундаментальным требованием пользователя.

Из чата действуют: отдельные R/Decision/реальные Actions; внешние low-level/free Actions; несколько оснований и общая identity; отказ отменяет зависимое продолжение без других причин, сохраняя данные; отменённый вариант равноправен невыбранному; скрытие при выборе существует только внутри mutuallyExclusive группы. Plan не требует selected; шаблон вставляется с remap, линза используется повторно; UI/ИИ работают через общий API. Поздний допуск явных Graph Actions заменяет ранний запрет Action-узлов из handoff. Тематическая правильность примеров исключена пользователем.

Результат первого этапа — технический guide и четыре machine/test artifacts, а также связанные указатели, policy и coverage каталога: 15 затронутых файлов. Проверены свежие hashes ключевых удалённых файлов и локальные копии тех же версий. Главный guide: `d4c8beaf5af6bad61760b81770aee0e73988715bbae227b56a8e3120569fb982`; schema: `61bb4ac35ad890ab5042ee83b98db134ad59fb1ffdde2a7be29284755059d97f`. Полный список версий дан в конце.

Срок, бюджет, число исполнителей и пользовательская календарная дата поставки не установлены. Не делаю выводов о выполнимости дедлайна или экономии часов. Стоимость вариантов сравнивается качественно: число команд/точек сбоя, расширение схем и будущая поддержка.

## Оси проверки, evidence и границы

Предварительные оси сформированы до предметного анализа результата, из задания и его окружения; затем дополнены конкретными Action outcome и registry instance bindings. Предыдущий PASS и список PR предыдущего review не использовались как доказательство полноты.

| Ось / критерий | Выполненная проверка | Вывод |
| --- | --- | --- |
| Шесть частей gate, полномочия и смысл target | Чат → пункт 1 плана → общий/технический контракт; сопоставление всех шести разделов | Все части представлены; наличие разделов не закрывает F-P-1/F-P-2. Будущий kernel не требовался |
| Согласованность schema и команд | Повтор Ajv suite; независимые запросы add/complete/edit и просмотр полей oneOf | Основные формы проходят, но отсутствующий исход acceptance не разрешён формами — F-P-1 |
| Identity/ref inventory и reuse | Сопоставление instance fields со slots, валидный registry instance, декларативный replay переноса qualifiers | Два текущих target qualifiers отсутствуют — F-P-2. Реальный новый copy не исполнялся |
| Отмена/несколько оснований/видимость | Независимый Python oracle по пользовательским правилам: 15 конкретных cases | Ожидания этих cases согласованы. Нет blanket-фильтра cancelled/unselected; другая причина сохраняет ветвь |
| Completion, guards, freshness и атомарность | Таблицы состояний/отказов, формы Action, существующие core guard/projection и Application entrypoints | Выбор/результат разделены; влияние F-P-1 важно для complete. Future storage/guard correctness не доказана schema tests |
| Client state, Plan и layout | Read-set/draft clauses, Plan examples, process key/UUIDv5 vectors, source API/codec | Выбранные базовые формы согласованы; динамические многоклиентные/восстановительные сценарии ещё относятся к реализации |
| Достаточность tests/fixtures | Прогон 51+6; read-only mutation expected ID; независимый oracle; чтение всех 55 expectation records | PASS подтверждён в ограниченном scope. F-O-1; не подменять им 55 runtime переходов |
| Integration и регрессия | Существующие portable/core/helper/profile gates, approval executor, catalog coverage, hashes неизменённого backend | Профиль не включён, старый не переименован. Гипотеза жёстко зашитой старой inputBinding в approval не подтвердилась: executor вызывает app.input_binding |
| Качество выполненной работы ИИ | Статусы «завершён», реальные записи, counts, ограничения, scope и согласованность владельцев | Создание артефактов/заявленные тесты подтверждены; безусловное закрытие gate требует коррекции. Никакой реализации Proposals не заявляется |

Свежий обычный прогон: **57/57 = 51 contract + 6 documentation**, завершён с exit code 0. Каталог линз: **5/5**, exit code 0. Это не новые UI или Decision writer tests. Последний известный prototype PASS 65/65 относится к предыдущему неизменённому UI-срезу; он не повторялся и не доказывает новые cascade/filter эффекты.

## Подтверждённые проблемы

### F-P-1 — исход decide_acceptance нельзя выразить при завершении

**Type:** Problem. **Semantic target:** первый этап / D1–D2 / Action completion DTO и эффекты. **scenarioBasis:** B. **Level:** CURRENT. **Disposition:** unresolved. **Confidence:** HIGH. **User Review Priority:** HIGH. **Intervention Priority:** NEXT. **Next gate:** разработчик фиксирует один способ передачи фактического исхода и примеры; blocked scope — этот вид Action completion, не все операции R/D и чтения.

Основание: gate первого этапа требует однозначных inputs/effects; действие принятия решения должно отражать фактический выбор и не смешиваться с планированием. Новый Action type включён в минимальную schema/таблицу completion, поэтому это не исключительно отложенная форма позднего редактора.

В schema `#/$defs/action` поле `decisionOutcome` существует, но не входит в required и не имеет default. `command_add` принимает external decide_acceptance с target D1 без этого поля. `command_complete.data` разрешает только nodeId/basis/evidenceIds, а `command_edit.data.changes` — title/description/tags.

Независимая Ajv-проба дала:

```json
{
  "creationWithoutOutcomeAccepted": true,
  "completionWithoutOutcomeAccepted": true,
  "completionWithOutcomeAccepted": false,
  "editingOutcomeAccepted": false
}
```

Конкретный путь: D1 selected и имеет зависимые R → пользователь заранее планирует «решить, принимать ли D1» как decide_acceptance без известного исхода → при исполнении выясняет actual selected/unselected → имеющиеся формы не дают передать этот результат. Если будущий writer угадает unselected, он может запустить каскад без выраженного исхода; если отклонит, ни complete, ни edit не дают исправить Action с прежней identity. Это описание недоопределённого контракта, **не наблюдавшаяся отмена в новом приложении**.

Schema вправе пропускать межобъектные проверки к kernel, но в этом случае и prose не устанавливает обязательность/момент/ошибку отсутствующего исхода. Разработчику пришлось бы придумать policy при написании reducer. Недостаток не устранён тем, что можно создать другой Action заранее с известным результатом: планируемое решение может быть ещё не принято.

**Связанные PR:** PR-1B — предпочтительный вариант: фактический исход задаётся при complete и атомарно фиксируется вместе с выбором/Action result/history. PR-1A — оставить поле на Action, разрешить отдельное защищённое задание/изменение до complete и требовать его наличия. Оба pending, Autonomy HIGH, impact CURRENT; альтернатива меняет число writes/точек конфликта, не пользовательскую цель. Не требуется новый смысловой ответ пользователя.

### F-P-2 — qualified привязка instance отсутствует в единственном реестре refs

**Type:** Problem. **Semantic target:** первый этап / typed refs / scope экземпляра рекомендации. **scenarioBasis:** B. **Level:** CURRENT. **Disposition:** unresolved. **Confidence:** HIGH. **User Review Priority:** HIGH. **Intervention Priority:** NEXT. **Next gate:** разработчик согласует namespace/политику qualifiers и пример переноса; blocked scope — объявление полного typed traversal/remap, особенно D4/D5. Базовый Graph-only kernel можно разрабатывать независимо.

Основание: пункт 1 требует определить slots typed traversal; technical guide называет refs.json единственным списком и требует запись для каждого нового ref-bearing поля. Область template-instance обязана оставаться в правильном процессе после insertion/copy.

Schema `recommendationPackage.instance` имеет sourcePackageId/sourceRevision, **graphPackageId/identitySpace**, memberIds/rootIds. В inventory для instance присутствуют только memberIds/rootIds. Target package/space — ссылка на процесс, не identity самого namespace registry; пара определяет, в каком Graph допустимы эти members.

Валидный по schema instance из пробы:

```json
{
  "graphPackageId": "22222222-2222-4222-8222-222222222222",
  "identitySpace": "11111111-1111-4111-8111-111111111111",
  "memberIds": ["R1"],
  "rootIds": ["R1"]
}
```

Декларативный replay только перечисленных slots меняет members/roots на R1-copy, но оставляет старую пару package/space. Сопоставление с target `77777777-7777-4777-8777-777777777777 / 88888888-8888-4888-8888-888888888888` даёт ownerMatches=false. Следовательно, **одного заявленного списка недостаточно**: нужен неописанный special case вне inventory либо явный qualified slot. Это не тест фактического нового copy, которого ещё нет.

Политика `graph.recommendationPackageIds[].copy=preserve-definition-id` приемлема для обычного общего определения и сама по себе не объявляется ошибкой. Но для переносимого локального instance контракт должен явно различить сохранение общего definition ID и создание/remap независимого instance ID. Также следует определить namespace sourcePackageId/sourceRevision: источник definition или Graph template; имя без записи в provenance/typed policy не отвечает на этот вопрос.

**Связанный PR-2:** дополнить qualified binding/provenance в единственном реестре, определить operation-specific политику общего определения и локального instance, добавить действительный пример source→target с новыми package/space IDs. Status pending, Autonomy HIGH, impact CURRENT; техническая правка обратима до появления сохранённых данных нового профиля. Нужна согласованная policy, не новая пользовательская модель рекомендаций.

## Риск и возможность улучшения

### F-R-1 — составное создание обязательного блока может распасться на два commit

**Type:** Risk. **Target:** API authoring → будущий Viewer. **scenarioBasis:** C для предположения «одна команда обязана создавать и связь»; B для сохранения согласованности заявленной операции. **Level:** CURRENT. **Disposition:** unresolved. **Confidence:** HIGH в ограничении формы, MEDIUM в будущем ущербе. **User Review Priority:** NORMAL. **Intervention Priority:** NEXT, до составного authoring D2/D6.

Наблюдаемое: add.data содержит только entity/location/workGraphId. Добавление relation либо parentId отклоняется additionalProperties=false; link требует уже существующие endpoints. Формы позволяют две отдельные команды. Проба не доказывает, что такой primitive API сам по себе нарушает требования первого этапа.

Условие риска: UI/ИИ трактует «добавить обязательный Action от R0» как одну завершённую операцию, выполняя add(A-new), затем link(R0,A-new). При сбое/конфликте/guard отказе второго запроса первый блок и его discovery уже сохранены без обязательной связи. Если экран объявит полное действие успешным или после restart потеряет промежуточное состояние, результат расходится с намерением.

**PR-3A:** ограниченно расширить add начальными отношениями/parent binding, заранее проверить весь эффект и опубликовать одним coordinator commit. **PR-3B:** оставить primitives, но явно задать двухшаговый протокол, промежуточный статус и восстановление составного UI-действия. Оба pending, impact CURRENT; Autonomy HIGH для A, MEDIUM для B из-за цены согласования/error UX. A требует нового входного поля и теста; B экономит изменение формы, но добавляет промежуточные состояния и readbacks. Выбор не считается сделанным этим review. Next gate: определить/проверить boundary до обещания атомарности этого UX, не блокируя независимую работу над ядром.

### F-O-1 — усилить доказательность fixtures без преждевременного написания kernel

**Type:** Improvement Opportunity. **Target:** contract validation → D1 test harness. **scenarioBasis:** B для будущей проверки инвариантов, C для предложенного способа усиления. **Level:** CURRENT. **Disposition:** deferred до подключения D1 expectations. **User Review Priority:** NORMAL. **Intervention Priority:** NEXT при этом gate. **Confidence:** HIGH.

Текущий путь приемлем как schema/structure validation и честно так назван. Он не обязан исполнять будущий kernel. Но есть дешёвое усиление: expected IDs сверять с seed/заданной allocation, а важные пересечения групп задавать конкретными данными.

Read-only preload заменил только `cancel-chain.expect.activeIds` на `["D-does-not-exist"]`. Marker подтвердил применение подмены; штатный contract suite всё равно дал **51/51**. Файл fixtures сохранил исходный hash. Независимый oracle отверг ту же подмену на cancel-chain: фактическое множество поддержки `{R0}`. Это показывает предел тестов, а не наличие неверного ID в исходных fixtures.

Ни один из трёх положительных Graph seeds не содержит D, состоящий в нескольких группах. Case visibility-overlap описывает условие строкой, но не имеет setup/request или конкретного visible/hidden результата. Technical guide допускает текстовые ожидаемые проверки для будущих UI/protocol cases; поэтому не объявляю отсутствие исполняющего этот case kernel нарушением этапа.

**PR-4:** добавить статические проверки допустимости expected IDs, конкретный overlapping seed и outcomes, а также cases отсутствующего/переданного Action outcome и qualified instance remap. Pending, Autonomy HIGH, impact CURRENT; RECOMMENDED_WITH PR-1B и PR-2. Не нужен второй runtime reducer для всех 55 cases: статическая целостность и малый независимый oracle достаточны сейчас, реальные переходы — через D1/D2.

## Предложения и совместимый маршрут

Canonical PR записи находятся рядом с Findings. Все предложения `origin=review`, status pending; выполнение не заявляется. HIGH Autonomy означает допустимость технического выбора в разрешённой задаче, не автоматический commit этого review.

| Набор / шаг | Решение и зависимость | Gate и проверяемый результат |
| --- | --- | --- |
| PG-1 ALTERNATIVE_GROUP | PR-1B либо PR-1A; при разных authoritative местах фактического исхода варианты CONFLICTS_WITH без отдельного правила приоритета | До реализации decide_acceptance выбрать один источник actual outcome; неизвестный исход не превращается в неявный отказ |
| Основной рекомендованный набор | PR-1B + PR-2 + PR-4, SOFT_BUNDLE | Сначала DTO/refs policy, затем согласованные fixtures/tests. Исправления проверены, только когда есть однозначные формы/эффекты и адресные positive/negative tests |
| PG-2 ALTERNATIVE_GROUP | PR-3A либо PR-3B; отдельно от основного набора | До составного authoring подтвердить поведение при отказе после создания блока. Не требуют заранее менять user Need |
| После локальных corrections | Реализация D1/D2 по исправленным контрактам | Подключить ожидаемые сценарии к фактическому reducer/Application, повторить профиль/permission/CAS/retry/focus checks |

PR-4 не заменяет решение по F-P-1/F-P-2. Само добавление ещё нескольких зелёных schema cases не устраняет недоопределённость. PR-3 может рассматриваться после основного набора; его предварительное принятие не является prerequisite выбора Action outcome.

Стоимостная оценка качественная. PR-1B сохраняет один commit результата против дополнительных writes у PR-1A. PR-2 добавляет явные descriptors/пример вместо будущего набора special cases. PR-3A расширяет узкую форму; PR-3B требует удерживать/восстанавливать промежуточный UI state. Денежный/календарный delta неизвестен. Смена scope на MVP, перенос пользовательского outcome или график работ не предлагаются.

## Что выдержало проверку и что не считается дефектом

Стандартная schema компилируется и согласована с 20 положительными/24 отрицательными формами. Обычный suite 51/51 и documentation 6/6 подтверждены заново; catalog 5/5 также подтверждён. Независимо проверены 15 объявленных случаев: каскад, сохранение общей R при другой причине, потеря последней причины, отсутствие самоподдержки цикла, явный primary goal, повторный выбор без автоматического выбора детей, отдельное переподключение, exclusive/nonexclusive/optional/без выбора/checkbox и конфликт выбора.

Профиль версионирован отдельно, старый backend не переименован. Группы не стали nodes/Plan steps, D→D запрещён и через DEPENDS_ON. Выбор, completion, исполнение и достижение R разделены. Состав WG и общий Plan/History не копируются в screens. Сохранение camera/draft и явный CAS конфликт определены. Первый order-only Plan и fork anchor представлены реальными примерами; process layout key и UUIDv5 vectors согласованы между Python и Node.

Отсутствие нового reducer, редакторов D4–D7, новой фундаментальной lens runtime и новой UI cascade/checkbox не является Problem этого этапа: граница была объявлена. Недостаточная полнота последующих runtime tests не выдаётся за текущую реализацию. Части full-copy lineage и поздних editors разрешено уточнить до их этапов; это не оправдывает F-P-1, уже включённый в минимальную командную модель.

Отказ редактировать guidance через текущий command_edit подтверждён пробой, но не объявлен отдельным Problem: формы поздних редакторов явно отложены. Неподдержка текущим package-only Store нового registry participant также известная задача D4/D5, не найденный runtime дефект готового D1. Гипотеза о hardcoded старом inputBinding в approval executor не подтвердилась по вызову Application; новая совместимость всё равно должна пройти implementation gate.

## Ограничения, полномочия и сохранение

Не исполнялись future writer/recovery/guards/multi-client integration на новом профиле: их нет, и эта проверка не подменяет реализацию тестовой моделью. Python oracle покрывает только ограниченные support/selection/group visibility правила, не всю domain semantics. Все 55 ожиданий прочитаны, но лишь 15 независимых логических cases исполнены oracle; 51 contract tests проверяют свой заявленный structural scope.

Не проверялись предметная правильность тематических примеров, реальные рабочие owners, Windows/установленный Viewer, human WebAuthn и конечная визуальная приёмка. UI-код этого этапа не менялся; полноценный browser replay не нужен для доказательства исправности нового контракта. Документационные и lens coverage проверки не равны семантической приёмке новых фундаментальных линз.

Был временный отказ remote connection. Первое сообщение о повторном 57/57 было преждевременным: процесс/лог не удалось подтвердить после сбоя. Сообщение исправлено; успешный повтор с отдельным сохранённым логом завершился exit 0. Текущие исходные hashes после восстановления совпали. Это ограничение процесса проверки устранено повтором и не переносится на неподтверждённые результаты.

User Assistance сейчас не требуется: смысл отмены/видимости уже установлен, оставшиеся решения технические. Новые runtime/schemas/fixtures fixes в рамках этого review не вносились. В действующих указателях исправлена только фактическая оценка готовности и внесены ссылки на Findings, как требует AGENTS.md; это не принятие PR. Snapshot report зарегистрирован существующим DOCS-POLICY как архив. Работа сохраняется в согласованном repository owner; GitHub/forfiles reading copy не создавалась. Ни live data, ни grants, ни публикация приложения не затрагивались.

## Воспроизведение ключевых проб

Обычный набор:

```sh
node --test tests/rdg-decision-contract.test.cjs tests/rdg-documentation.test.cjs
python3 -B tests/rdg-lens-catalog.test.py
```

F-P-1: загрузить существующий request-add; заменить entity на task Action из graph-chain, дать новый ID, location=external, actionType=decide_acceptance, targetIds=[D1], удалить decisionOutcome. Проверить стандартным Ajv Draft 2020 `#/$defs/request`. Затем взять request-complete с nodeId нового Action. Оба проходят форму. Добавление decisionOutcome в complete.data и в edit.data.changes отклоняется. Эта проба не пишет Graph.

F-P-2: сопоставить keys `$defs.recommendationPackage.properties.instance.properties` с путями `registry.packages[].instance.*` в refs.json. Список qualifiers содержит graphPackageId/identitySpace, inventory содержит лишь memberIds/rootIds. К валидному registry-types добавить instance, remap только объявленных slots и сравнить scope pair с новым Graph. Source→target UUIDs и результат ownerMatches=false приведены в F-P-2.

F-O-1: read-only preload отдельного Node процесса перехватывает чтение только fixtures; исходные bytes не меняются:

```js
const fs=require('node:fs'),original=fs.readFileSync;
fs.readFileSync=function(file,options){
 const value=Reflect.apply(original,this,arguments);
 if(!String(file).endsWith('/tests/fixtures/rdg-decision-v1/contract-cases.json'))return value;
 const data=JSON.parse(value.toString());
 data.expectations.find(x=>x.id==='cancel-chain').expect.activeIds=['D-does-not-exist'];
 process.stderr.write('REVIEW_MUTATION_APPLIED\n');
 const json=JSON.stringify(data);
 return typeof options==='string'||options&&options.encoding?json:Buffer.from(json);
};
```

Запускать как `node --require ABS_PRELOAD_FILE --test tests/rdg-decision-contract.test.cjs`. Подтверждены marker и pass 51/fail 0. После пробы fixtures SHA осталась `4d222fb52ce346fe5e21a9f3a7e11f1edc8e3e0b3159815d3cb8de53cede1719`.

Независимый oracle строит ориентированные композиционные arcs из relations и group memberships, начинает с enabled root causes, включает D только при selected и повторяет reachability до неподвижной точки. После withdraw/unlink сбрасывает selected только у D, потерявших поддержку, и пересчитывает. Видимость считает отдельно по выбранным участникам G1 и mutuallyExclusive, учитывая showExcludedAlternatives. Проверены ожидаемые подмножества active/inactive/unselected/visible/hidden 15 случаев; мутант D-does-not-exist отвергнут. Это альтернативная проверка ограниченного логического результата, не новый production kernel.

## Версии источников

Таблица фиксирует bytes **до** добавления review-status notices в указатели. После notices технические schema/refs/fixtures и runtime не исправлялись; новые hashes указателей не являются проверенной исправленной версией форматов.

| Источник | SHA-256 |
| --- | --- |
| `README.md` | `732d36079c48d19d019b8b604241e8d23a5a892c8826df800b4375c0335484f7` |
| `docs/DOCS-POLICY.json` | `e529ee2f85092030d53a61a3e579b5494d2234d1e00aa403e3634cd0af441987` |
| `docs/README.md` | `9625e231124f41cb41b0b1e1356786bef829165618746522057e009af6714163` |
| `docs/guides/RDG-ACTIVE-CONTRACT.md` | `3758fb15aca723c9269e54c8f12b77e9105875b9567cf90426da3fbe8bf5746c` |
| `docs/guides/RDG-CURRENT-STATE.md` | `a222d8bf80577051a6ade31b0dc67ef0c11e17edccead6a955aae1f945768f9c` |
| `docs/guides/RDG-DECISION-V1-CONTRACT.md` | `d4c8beaf5af6bad61760b81770aee0e73988715bbae227b56a8e3120569fb982` |
| `docs/guides/RDG-DEVELOPMENT-PLAN.md` | `4d716b88d892a505170a29809c1476865787b54f10f234065e2031285a2bfbae` |
| `docs/guides/RDG-LENSES.md` | `f74661651cca1012e374c1c3037f82be907675eee9fe80935a33f9d01395f56f` |
| `docs/guides/RDG-OPERATIONS.md` | `5448e34f9f4d018868543b12308852451d03444d255b3be05d6076a4d11415aa` |
| `docs/guides/VIEWER-EXPLORER.md` | `1daf5d02b61e3b92d7ddebc0c43a6bdb0764ef63c325503b079065199835a390` |
| `tests/fixtures/rdg-decision-v1/contract-cases.json` | `4d222fb52ce346fe5e21a9f3a7e11f1edc8e3e0b3159815d3cb8de53cede1719` |
| `tests/rdg-decision-contract.test.cjs` | `4b3aad4fb88df924fbafb16ea7c3439dc9a09ce3069c9a8b63d42139f83ab9f3` |
| `tools/contracts/rdg-decision-v1.refs.json` | `c6bf56d3f4d060b01bba137d4b1fea780b6d3fed79d4b4df8fb03d43e5271d70` |
| `tools/contracts/rdg-decision-v1.schema.json` | `61bb4ac35ad890ab5042ee83b98db134ad59fb1ffdde2a7be29284755059d97f` |
| `tools/rdg-agent-lenses/catalog.json` | `8fb158b1cfe8e1ff3df73e303b43c77263046b1a231e1499467fe96c52b62a77` |


Контекст реализации: `tools/rdg-core-model.py` SHA `0955571ee2e724e8844db5a99396dddc97cbba47c80516946ff39cfcfed2f9a3`; `tools/rdg-portable-service.py` SHA `a43b794fafb281f9e946a72e825650990d1db18ff02d09bba0d8c7ccca592276`. Инструкции разработки AGENTS.md SHA `dbe32b34364750e53dc4a29e70fe1aecfe2c7d3c7e7d94706654230a3bd7bb23`.

## Review Log

1. Сначала восстановлены target первого этапа и шесть критериев из пользовательского задания/плана; сформированы общие, ситуационные и мета-оси, без признания прежнего pre-work исчерпывающим.
2. Зафиксированы версии artifacts; сохранены чужие WIP. Сверены schema, typed inventory, все expectation records, tests и связанные code entrypoints. Подтверждены обычные прогоны 57/57 и 5/5 после устранённого сбоя соединения.
3. Независимые пробы дали F-P-1/F-P-2, conditional F-R-1 и F-O-1. Логический oracle подтвердил 15 случаев и отверг подменённое ожидание. Неподтверждённые гипотезы о guidance/editor completeness и approval binding не повышены до Problems.
4. Canonical Findings/PR записаны один раз в этом отчёте; recommended route остаётся candidate. P1/P2 unresolved, R1 unresolved до authoring boundary, O1 deferred до подключения D1 expectations. Пользовательская семантика не пересмотрена.
5. Исправлены фактические readiness notices в существующих owners; snapshot зарегистрирован в policy и проверен обратным чтением. Нет отдельного axis log/manifest/параллельного плана, новой публикации или коммита Proposals.
6. Завершающая проверка охвата отделила форму от реального поведения, actual proof от предположений, текущий дефект контракта от будущего риска. Значимые ограничения и следующий gate отражены в обзоре; повторная проверка исправленных форматов потребует нового target/hash.
