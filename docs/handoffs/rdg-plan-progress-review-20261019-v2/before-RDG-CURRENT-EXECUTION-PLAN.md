# RDG + Temporal Plan — актуальный порядок исполнения

**Актуальная контрольная точка:** CPW-RDG-JOINT-CONTEXT-20261019/v1.
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

## Где мы сейчас

| Срез | Факт | Открытый gate |
|---|---|---|
| P0/P0.1 | Исправлены branch membership, независимая проверка полноты declaration/subscriptions и смысловых title для текущих проекций; scoped acceptance PASS. | Несколько событий, новый lifecycle и исторический контекст ещё не входят в coverage. |
| P1 | [Контракт owner/version/as-of](RDG-TEMPORAL-PLAN-OWNER-CONTRACT-P1.md) подготовлен как Candidate. | PR-P1-01..05 не committed; production owner и доверенный источник событий не выбраны. |
| P2 | [Совместный context v1](RDG-JOINT-CONTEXT-PILOT.md) связывает candidate applicability, точный baseline state, pinned Plan/RDG и один совместимый event claim по двум временам. Реальный Gendocen проверяет позднюю реконструкцию и сохранность раннего контекста. [Последнее evidence](../handoffs/rdg-joint-context-20261019/CHECKPOINT.md). | Scope — один Plan/branch/occurrence. Автоматический effective-time выбор принятых baseline, полнота остальных owners, trusted event source и проверка содержания evidence открыты. Старые journals без времени отклоняются. |
| P3 | Есть ограниченные F-R/F-U/F-O, F-P preflight, Canon context review и read-only Plan impact. | Полная семантика Finding/Proposal/Canon, независимое подтверждение F-P, несколько событий и различение позднего знания о T1 от изменения после T1. |
| P4 | Есть foundations рабочих/research-графов. | Сквозная передача между чатами, один смысловой owner при promotion/link, archive/retrieval и успешная проверка без искусственного Finding. |
| P5 | Есть исходники Viewer и синтетический Gendocen runtime proof. | Helper grants, Plan editor/timeline, читаемая Markdown-проекция, внешний consumer и отдельная проверка установки в Windows/G2. |
| P6–P7 | Удалённая запись и вывод legacy из эксплуатации не начинались. | Canonical GitHub owner/branch/writer, multi-file CAS/failure proof, проверка лицензии движка; затем доказанное замещение legacy. |

В последнем срезе прошли 49 адресных тестов и совместный реальный Gendocen
smoke из 15 CLI-запусков со штатным Graph writer. Ранние candidate и точный
baseline context сохранились после поздних Plan/RDG/applicability/event
записей; новая реконструкция потребовала review. Проверены stale context,
отказ новому конфликтующему запросу и сохранность sources при чтении.
Прежние 88 тестов, event smoke 25 CLI и 405 Node относятся к предыдущим
срезам; полностью здесь не повторялись. Proof ограничен объявленным scope;
полная lifecycle applicability и фактический пользовательский T1 открыты.

## Следующие локальные срезы

1. **Применимость: локальная история готова, доказательство полноты открыто.**
   Отдельный candidate owner сохраняет версии утверждений, точные Plan/RDG
   pins, `recordedAt`, `effectiveAt` с исходной точностью и `supersedes`.
   Отдельное право, CAS, квитанция после записи и recovery проверены на
   tempfile. Ранний `knownAt` исключает позднюю поправку; поздний допускает
   её только как кандидатную реконструкцию. Несвязанные outcomes дают
   конфликт, а не автоматический выбор. **Следующий технический gate:**
   расширить полноту за пределы одного Plan/branch/occurrence. Совместный
   синтетический context v1 и Gendocen уже проверены в этом scope; accepted
   mode требует точную baseline state revision. Независимое подтверждение
   времени и trusted event source — предметный gate перед фактическим применением.
2. **Lifecycle: локальные записи есть, доверие и интеграция открыты.**
   Технический baseline сохраняет точную candidate-версию по `plan.accept`.
   Отдельный event owner сохраняет claim, attestation и review с разными
   grants, старой записью и конфликтом outcomes. Записи не подтверждают
   личность, содержание evidence или факт события; Action не выбирается.
   Старый current-only adapter отклоняет sidecars. Новый явный event consumer
   проверен реальным Gendocen для одного occurrence и фиксированного `knownAt`.
   **Предметный gate:** определить trusted actor/source и правила независимой
   проверки перед пользовательскими фактами. **Технический gate:** расширить
   проверенный joint context на автоматический baseline effective selection,
   несколько owners/событий и совместные concurrent write/recovery.
   Синтетическую реализацию можно продолжать до выбора реального источника.
   P2-AC-08/11/12/13/17/20 остаются PARTIAL для полного контура.
3. **Следующий технический срез — lifecycle applicability и полнота scope.**
   Joint context v1 уже проверяет candidate selection и exact baseline state,
   Plan/RDG/event pins, cutoff и semantic subscriptions. Сначала проверить
   оставшийся P2-AC-04 (два шага разных cases → один Action). Затем определить
   явную связь принятого baseline с applicability/effective-интервалом;
   автоматический выбор прежнего accepted state сейчас не реализован.
   Сохранить отказ при gap, withdrawn state, конфликте и несовместимой версии.
   Расширять scope с независимой coverage и проверкой concurrent
   write/revoke/recovery. **Gate:** P2-AC-08/13/14/15/16/17/18/19.
4. **Дальше P3 → P4 → P5 → P6 → P7.** Завершить семантику Finding/Canon/Proposal;
   затем двухчатный research workflow; затем пользовательский вертикальный
   сценарий и installed proof. Удалённый canonical owner и legacy retirement
   решать после соответствующих gates. Эти этапы не блокируют локальные
   read-only тесты первых трёх срезов.

## Сверка с P2-AC-01..20

Это текущая *исполнительная* сверка с исторической матрицей, а не правка её
исходного `PLANNED-NOT-EXECUTED`. Слово PASS относится только к указанной
части Candidate-пилота.

| ID | Сейчас | Основание или следующий недостающий proof |
|---|---|---|
| 01 | Локальный PASS | Конфликт writable owner отклоняется в тесте Plan owner. |
| 02 | Локальный PASS | Traversal и symlink отклоняются без записи. |
| 03 | Локальный PASS | Candidate Plan write и сквозной smoke не выбирают и не переписывают RDG Action. |
| 04 | OPEN | Нужен сценарий двух Plan steps с одним Action и разных cases. |
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
[joint context v1](../handoffs/rdg-joint-context-20261019/CHECKPOINT.json).
Полные статусы WR-01..53 сохраняются в [v4.1 ledger](../handoffs/rdg-prework-v4.1-final-20261018/WR-EVIDENCE-LEDGER.md);
новые checkpoints меняют только названный scope. При следующем срезе обновлять
эту таблицу вместе с доказательством, не повышая PARTIAL до общего PASS.
