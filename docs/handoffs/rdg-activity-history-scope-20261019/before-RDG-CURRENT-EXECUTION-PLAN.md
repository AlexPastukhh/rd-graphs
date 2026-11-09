# RDG + Temporal Plan — актуальный порядок исполнения

**Последняя реализация:** [CPW-RDG-SHARED-ACTION-20261019/v1](../handoffs/rdg-shared-action-20261019/CHECKPOINT.md).
**Проверка плана и продвижения:** [R-RDG-PLAN-PROGRESS-20261019/v2](../handoffs/rdg-plan-progress-review-20261019-v2/REVIEW.md).
**Статус:** рабочий план
для Candidate-пилота. **Stage 4 NOT ACCEPTED.** Этот документ обновляет
порядок и фактические статусы после локальных проверок. Он не меняет
нормативные Need / FR / Desired Scenario / SRU, не принимает Proposals и не
переписывает [полный v4.1](../handoffs/rdg-prework-v4.1-final-20261018/HANDOFF.md)
или [историческую матрицу P2](../handoffs/rdg-p1-plan-contract-20261019/P2-ACCEPTANCE-MATRIX.md).

`Локальный PASS` ниже означает проверенный сценарий на временных синтетических
источниках. `PARTIAL` — проверена лишь часть условия. `OPEN` — требуемого
поведения или доказательства пока нет. Эти статусы не означают independent
acceptance, установку Windows или публикацию.

## Актуальное уточнение пользователя — 2026-10-19

Пользователь уточнил назначение: человек меняет план вручную, когда это нужно;
ИИ читает и меняет тот же план через API, как при работе с графами. План
может использовать сущности из графов и содержать ссылки. Это уточнение
имеет приоритет над прежними Candidate-предложениями о дополнительной
механике Temporal Plan.

Обязательный ближайший scope — ручная работа и API для ИИ над одним планом,
ссылки на сущности графов и другие материалы, корректность этих ссылок.
API должен проверять права на чтение/запись, сохранять историю и отклонять
запись по устаревшей версии, как существующий guarded writer графов.
Автоматический выбор принятого baseline по knownAt/effectiveAt, effective-
интервалы, отдельный lifecycle принятия/отзыва плана и event attestation
для этого пути не требуются. Их развитие снято с ближайшего маршрута.
Сроки, ветви и будущие события могут быть содержанием ручного плана;
автоматический исполнитель или выбор действующей версии из этого не следуют.

Ранее сделанные экспериментальные модули и доказательства сохраняются.
Они не становятся пользовательскими требованиями из-за наличия реализации.
Правка плана человеком или ИИ через API не должна менять решения, сущности
или историю RDG.
Прежние Candidate Proposals не повышаются до committed.

В локальном пилоте уже есть apply_request и CLI apply/read с Plan grants,
expectedRevision и историей. Это основа API, но завершённый пользовательский
интерфейс наравне с Graph API этим уточнением не объявляется реализованным.

## Ранее выполненные технические срезы

Таблица ниже — inventory прежней работы. Незавершённый экспериментальный
gate не означает обязательную работу для ручного Plan.


| Срез | Факт | Граница прежнего пилота |
|---|---|---|
| P0/P0.1 | Исправлены branch membership, независимая проверка полноты declaration/subscriptions и смысловых title для текущих проекций; scoped acceptance PASS. | Несколько событий, новый lifecycle и исторический контекст ещё не входят в coverage. |
| P1 | [Контракт owner/version/as-of](RDG-TEMPORAL-PLAN-OWNER-CONTRACT-P1.md) подготовлен как Candidate. | PR-P1-01..05 не committed; production owner и доверенный источник событий не выбраны. |
| P2 | [Совместный context v1](RDG-JOINT-CONTEXT-PILOT.md) связывает candidate applicability, точный baseline state, pinned Plan/RDG и один совместимый event claim по двум временам. Реальный Gendocen проверяет позднюю реконструкцию и сохранность раннего контекста. [Последнее evidence](../handoffs/rdg-joint-context-20261019/CHECKPOINT.md). | Scope — один Plan/branch/occurrence. Автоматический effective-time выбор принятых baseline, полнота остальных owners, trusted event source и проверка содержания evidence открыты. Старые journals без времени отклоняются. |
| P3 | Есть ограниченные F-R/F-U/F-O, F-P preflight, Canon context review и read-only Plan impact. | Полная семантика Finding/Proposal/Canon, независимое подтверждение F-P, несколько событий и различение позднего знания о T1 от изменения после T1. |
| P4 | Есть foundations рабочих/research-графов. | Сквозная передача между чатами, один смысловой owner при promotion/link, archive/retrieval и успешная проверка без искусственного Finding. |
| P5 | Есть исходники Viewer и синтетический Gendocen runtime proof. | Helper grants, Plan editor/timeline, читаемая Markdown-проекция, внешний consumer и отдельная проверка установки в Windows/G2. |
| P6–P7 | Удалённая запись и вывод legacy из эксплуатации не начинались. | Canonical GitHub owner/branch/writer, multi-file CAS/failure proof, проверка лицензии движка; затем доказанное замещение legacy. |

В предшествующем joint-срезе прошли 49 адресных тестов и совместный реальный Gendocen
smoke из 15 CLI-запусков со штатным Graph writer. Ранние candidate и точный
baseline context сохранились после поздних Plan/RDG/applicability/event
записей; новая реконструкция потребовала review. Проверены stale context,
отказ новому конфликтующему запросу и сохранность sources при чтении.
Прежние 88 тестов, event smoke 25 CLI и 405 Node относятся к предыдущим
срезам; полностью здесь не повторялись. Proof ограничен объявленным scope;
полная lifecycle applicability и фактический пользовательский T1 открыты.

При review v2 заново прошли 35 тестов: Plan owner, joint context,
branch acceptance и coverage guard. Последние source/dependency/evidence
хеши совпали с checkpoint до правки документации. Joint smoke 15 CLI
здесь не повторялся; его лог проверен. Наборы 35 и 49 пересекаются.

В последнем срезе закрыт P2-AC-04: два вхождения одного Action сохраняют
раздельный step/case context. Исправлена повторная регистрация review для
одного Action: регистратор объединяет зависимости всех его вхождений и
отклоняет неполный список. Прошёл 71 тест, включая новый acceptance из
21 CLI-запуска реального Gendocen. RDG не меняется; область — candidate
Plan и current-projection. Итог P2: 8 локальных PASS, 12 PARTIAL, 0 OPEN.

## Ближайший результат и порядок

Результат — один план с ручным редактированием и API для ИИ, со ссылками
на сущности графов и другие материалы. Новые слои baseline/applicability/event не являются предварительным
условием. Выбор редактора и формата представления пока не установлен:
отдельный timeline или новый UI автоматически не требуются.

1. Сопоставить существующий Plan create/edit/read с API графов и довести
   доступный ИИ структурированный интерфейс для тех же данных. Ручной путь
   и API используют одно хранение, одни проверки и права; новый owner
   и production root не назначаются автоматически.
2. На одном примере довести ручную правку, API-чтение/запись и ссылки. Проверенная
   структурированная модель сейчас содержит actionRef; поддержку других
   сущностей графа и обычных ссылок нужно проверить и при необходимости
   добавить в этот же пользовательский путь. Ссылки не создают копии сущностей.
3. Проверить поведение: ИИ через API создаёт, читает и меняет план; ручная
   правка видна через API. Нет права — нет доступа; устаревшая запись
   отклоняется. Правильная ссылка разрешает нужную сущность; отсутствующая
   или повреждённая ссылка явно видна. Plan edit не выбирает Action
   и не переписывает RDG.
   Обычная история сохранений допустима; два времени не являются условием
   обычного редактирования.

Дальнейшие P3/P4 и другие задачи RDG не отменены этим уточнением о Plan.
Их проверять по собственным Need / FR / Desired Scenario. Исторический
resolver, совместные sidecar recovery и immutable joint bundle exporter
не должны задерживать ручной Plan, если его путь эти модули не использует.
Stage 4 и установку Windows/G2 проверять отдельно.

Если потребуется использование фактических событий, trusted actor/source
или особое принятие будущего плана, сначала установить отдельную потребность.
Canonical remote owner, публикация и legacy retirement сохраняют свои
прежние gates; текущая работа их не запускает.

## Сверка с P2-AC-01..20

Это техническая сверка ранее исследованной матрицы, а не список обязательных
доработок ручного плана. После уточнения scope статусы 8 локальных PASS и
12 PARTIAL сохраняются как evidence; закрывать все PARTIAL ради ручного Plan
не требуется. Исходный `PLANNED-NOT-EXECUTED` не переписывается.

| ID | Сейчас | Основание или следующий недостающий proof |
|---|---|---|
| 01 | Локальный PASS | Конфликт writable owner отклоняется в тесте Plan owner. |
| 02 | Локальный PASS | Traversal и symlink отклоняются без записи. |
| 03 | Локальный PASS | Candidate Plan write и сквозной smoke не выбирают и не переписывают RDG Action. |
| 04 | Локальный PASS | Два разных steps разных cases ссылаются на один Action; writer/reader сохраняют RDG bytes/status/events. Один Action review покрывает оба вхождения; срок каждого и смена membership требуют review A1, контрольный A2 остаётся valid; пропуск вхождения отклоняется. |
| 05 | Локальный PASS | Два процесса: один победитель CAS. |
| 06 | Локальный PASS | Revoke до durable prepared journal отклоняет запись. |
| 07 | Локальный PASS | Подстановка `accepted` или вызов `accept` через edit отклоняется; само принятие относится к 08. |
| 08 | PARTIAL | Joint context сохраняет точный baseline state после нового candidate; автоматическая lifecycle applicability, human acceptance и фактический T1 открыты. |
| 09 | PARTIAL | Candidate hard и технический будущий baseline не создают FR/F-P; независимый owner обязательства и applicability не доказаны. |
| 10 | PARTIAL | Date/instant/relative subset проверен; новые precision, units и выполнимость окна не доказаны. |
| 11 | PARTIAL | Клиентские actual fields в Plan отклоняются; отдельный event owner сохраняет unverified claim/attestation/review, но trusted source отсутствует. |
| 12 | PARTIAL | Plan editor и отдельный event-attest bearer не получают graph.select_action; сквозной пользовательский путь не проверен. |
| 13 | PARTIAL | Candidate applicability и event history сохраняют исходный claim, correction link и конфликт outcomes; нет trusted attestation и полноты контекста. |
| 14 | Локальный PASS | Точные Plan/RDG revision+digest обязательны, missing/mismatch/current fallback отклоняются. |
| 15 | PARTIAL | Ранний joint Plan/RDG/applicability/event bundle и Gendocen review сохраняются после поздних записей; полнота остальных owners и effective truth не доказаны. |
| 16 | PARTIAL | Поздняя joint-реконструкция требует review; ранний bundle и exact baseline сохраняются. Фактический T1 и автоматический accepted lifecycle as-of не подтверждены. |
| 17 | PARTIAL | Candidate, baseline и staged event journals/failpoints/recovery проверены; общий lifecycle и фактический T1 не испытаны. |
| 18 | PARTIAL | Старый adapter отклоняет sidecars. Joint-контракт проверяет snapshots, assessment и producer/declaration/subscriptions реальным движком в одном scope; расширенная coverage открыта. |
| 19 | PARTIAL | Exact Plan pin проверяется; bearer grant IDs и opaque evidence refs не считаются доказательством человека, содержимого или факта. |
| 20 | PARTIAL | Schema v1 и старый adapter сохраняют отказ; явные event/joint consumers v1 работают отдельно. Полная lifecycle-интеграция ещё открыта. |

Локальные основания: [P0/P0.1](../handoffs/rdg-p0-dependencies-20261018/CHECKPOINT.json),
[candidate owner и P2](../handoffs/rdg-vertical-slice-20261019/CHECKPOINT.json),
[точные snapshots](../handoffs/rdg-exact-history-20261019/CHECKPOINT.json),
[Graph knownAt](../handoffs/rdg-known-at-20261019/CHECKPOINT.json),
[Plan availableBy](../handoffs/rdg-plan-availability-20261019/CHECKPOINT.json),
[двухвременной rule probe](../handoffs/rdg-two-time-scenario-20261019/CHECKPOINT.json),
[owner history применимости](../handoffs/rdg-applicability-owner-20261019/CHECKPOINT.json),
[технический будущий baseline](../handoffs/rdg-future-baseline-20261019/CHECKPOINT.json),
[технические стадии события](../handoffs/rdg-event-lifecycle-20261019/CHECKPOINT.json),
[event context → Gendocen v1](../handoffs/rdg-event-gendocen-20261019/CHECKPOINT.json),
[joint context v1](../handoffs/rdg-joint-context-20261019/CHECKPOINT.json),
[два вхождения одного Action](../handoffs/rdg-shared-action-20261019/CHECKPOINT.json).
Полные статусы WR-01..53 сохраняются в [v4.1 ledger](../handoffs/rdg-prework-v4.1-final-20261018/WR-EVIDENCE-LEDGER.md);
новые checkpoints меняют только названный scope. При следующем срезе обновлять
эту таблицу вместе с доказательством, не повышая PARTIAL до общего PASS.
