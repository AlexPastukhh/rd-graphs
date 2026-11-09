# RDG + Temporal Plan — актуальный порядок исполнения

**Актуальная контрольная точка:** CPW-RDG-EVENT-GENDOCEN-20261019/v1.
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
| P2 | Candidate Plan owner, точные Plan/RDG snapshots, история применимости, технический baseline и event owner. Отдельный [event-контракт Gendocen v1](RDG-EVENT-GENDOCEN-PILOT.md) проверяет свежесть текущего и фиксированного раннего event context; correction/conflict требуют review. [Последнее evidence](../handoffs/rdg-event-gendocen-20261019/CHECKPOINT.md). | Нет подтверждения пользователя, trusted event source, проверки содержания evidence и выбора полного Plan/RDG/lifecycle контекста; `effectiveAt` не аттестовано. Старые journals без времени не проходят `knownAt`. |
| P3 | Есть ограниченные F-R/F-U/F-O, F-P preflight, Canon context review и read-only Plan impact. | Полная семантика Finding/Proposal/Canon, независимое подтверждение F-P, несколько событий и различение позднего знания о T1 от изменения после T1. |
| P4 | Есть foundations рабочих/research-графов. | Сквозная передача между чатами, один смысловой owner при promotion/link, archive/retrieval и успешная проверка без искусственного Finding. |
| P5 | Есть исходники Viewer и синтетический Gendocen runtime proof. | Helper grants, Plan editor/timeline, читаемая Markdown-проекция, внешний consumer и отдельная проверка установки в Windows/G2. |
| P6–P7 | Удалённая запись и вывод legacy из эксплуатации не начинались. | Canonical GitHub owner/branch/writer, multi-file CAS/failure proof, проверка лицензии движка; затем доказанное замещение legacy. |

В последнем срезе прошли 22 адресных теста и новый реальный Gendocen smoke
из 25 CLI-запусков: текущая event-проекция требует review после поздних
записей, ранняя проекция с фиксированным `knownAt` сохраняется. Проверены
stale context, адресность другого occurrence и сохранность source bytes.
Прежние 88 тестов и 405 Node PASS относятся к предыдущим срезам и здесь
полностью не повторялись. Новый proof ограничен event context; полный
исторический Plan/RDG/lifecycle и фактический пользовательский T1 не подтверждены.

## Следующие локальные срезы

1. **Применимость: локальная история готова, доказательство полноты открыто.**
   Отдельный candidate owner сохраняет версии утверждений, точные Plan/RDG
   pins, `recordedAt`, `effectiveAt` с исходной точностью и `supersedes`.
   Отдельное право, CAS, квитанция после записи и recovery проверены на
   tempfile. Ранний `knownAt` исключает позднюю поправку; поздний допускает
   её только как кандидатную реконструкцию. Несвязанные outcomes дают
   конфликт, а не автоматический выбор. **Следующий технический gate:**
   определить полноту применимых owners/событий и испытать P2-AC-13/15/16
   на совместном синтетическом контексте вместе с Gendocen. Независимое
   подтверждение времени и trusted event source — отдельный предметный
   gate перед фактическим применением.
2. **Lifecycle: локальные записи есть, доверие и интеграция открыты.**
   Технический baseline сохраняет точную candidate-версию по `plan.accept`.
   Отдельный event owner сохраняет claim, attestation и review с разными
   grants, старой записью и конфликтом outcomes. Записи не подтверждают
   личность, содержание evidence или факт события; Action не выбирается.
   Старый current-only adapter отклоняет sidecars. Новый явный event consumer
   проверен реальным Gendocen для одного occurrence и фиксированного `knownAt`.
   **Предметный gate:** определить trusted actor/source и правила независимой
   проверки перед пользовательскими фактами. **Технический gate:** объединить
   baseline/applicability/Plan/RDG/event context в версионном consumer;
   синтетическую реализацию можно продолжать до выбора реального источника.
   Проверить P2-AC-08/11/12/13/17/20 на совместном контуре.
3. **Ближайший срез — совместный исторический resolver.** На синтетических
   данных выбрать lifecycle и условный branch context, затем применимую
   версию Plan и все нужные RDG/event
   snapshots по двум временам. Если хотя бы одного источника нет, не выдавать
   `valid` и не брать текущий graph. Расширить независимую матрицу semantic
   reads → declaration → subscriptions на новые поля; испытать свежесть,
   correction, concurrent write/revoke/recovery. **Gate:** P2-AC-14/15/16/18/19
   и настоящий historical Gendocen review на синтетической истории.
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
| 08 | PARTIAL | Отдельный технический baseline доступен по точной ссылке после нового candidate; независимое подтверждение пользователя и T1 не проверены. |
| 09 | PARTIAL | Candidate hard и технический будущий baseline не создают FR/F-P; независимый owner обязательства и applicability не доказаны. |
| 10 | PARTIAL | Date/instant/relative subset проверен; новые precision, units и выполнимость окна не доказаны. |
| 11 | PARTIAL | Клиентские actual fields в Plan отклоняются; отдельный event owner сохраняет unverified claim/attestation/review, но trusted source отсутствует. |
| 12 | PARTIAL | Plan editor и отдельный event-attest bearer не получают graph.select_action; сквозной пользовательский путь не проверен. |
| 13 | PARTIAL | Candidate applicability и event history сохраняют исходный claim, correction link и конфликт outcomes; нет trusted attestation и полноты контекста. |
| 14 | Локальный PASS | Точные Plan/RDG revision+digest обязательны, missing/mismatch/current fallback отклоняются. |
| 15 | PARTIAL | Ранний knownAt исключает поздние records; фиксированная event-проекция и её Gendocen review сохраняются. Полный applicability/Plan/RDG контекст не разрешён. |
| 16 | PARTIAL | Поздние event records меняют текущий review и не переписывают ранний event context; фактический T1 и полный as-of не подтверждены. |
| 17 | PARTIAL | Candidate, baseline и staged event journals/failpoints/recovery проверены; общий lifecycle и фактический T1 не испытаны. |
| 18 | PARTIAL | Старый adapter отклоняет sidecars. Новый event-контракт проверяет producer/declaration/subscriptions и реальный Gendocen; совместный Plan/RDG/lifecycle runtime ещё открыт. |
| 19 | PARTIAL | Exact Plan pin проверяется; bearer grant IDs и opaque evidence refs не считаются доказательством человека, содержимого или факта. |
| 20 | PARTIAL | Schema v1 и старый adapter отклоняют неподдержанный lifecycle; явный event consumer v1 работает отдельно, полная версионная интеграция ещё открыта. |

Локальные основания: [P0/P0.1](../handoffs/rdg-p0-dependencies-20261018/CHECKPOINT.json),
[candidate owner и P2](../handoffs/rdg-vertical-slice-20261019/CHECKPOINT.json),
[точные snapshots](../handoffs/rdg-exact-history-20261019/CHECKPOINT.json),
[Graph knownAt](../handoffs/rdg-known-at-20261019/CHECKPOINT.json),
[Plan availableBy](../handoffs/rdg-plan-availability-20261019/CHECKPOINT.json),
[двухвременной rule probe](../handoffs/rdg-two-time-scenario-20261019/CHECKPOINT.json),
[owner history применимости](../handoffs/rdg-applicability-owner-20261019/CHECKPOINT.json),
[технический будущий baseline](../handoffs/rdg-future-baseline-20261019/CHECKPOINT.json),
[технические стадии события](../handoffs/rdg-event-lifecycle-20261019/CHECKPOINT.json),
[event context → Gendocen v1](../handoffs/rdg-event-gendocen-20261019/CHECKPOINT.json).
Полные статусы WR-01..53 сохраняются в [v4.1 ledger](../handoffs/rdg-prework-v4.1-final-20261018/WR-EVIDENCE-LEDGER.md);
новые checkpoints меняют только названный scope. При следующем срезе обновлять
эту таблицу вместе с доказательством, не повышая PARTIAL до общего PASS.
