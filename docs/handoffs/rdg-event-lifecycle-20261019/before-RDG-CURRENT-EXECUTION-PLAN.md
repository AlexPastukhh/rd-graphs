# RDG + Temporal Plan — актуальный порядок исполнения

**Срез:** CPW-RDG-PLAN-RECONCILE-20261019/v1. **Статус:** рабочий план
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
| P2 | Candidate Plan owner, точные Plan/RDG snapshots, ограниченный `knownAt` и [история применимости](RDG-APPLICABILITY-OWNER-PILOT.md). Отдельный [технический будущий baseline](RDG-FUTURE-BASELINE-PILOT.md) закрепляет точную Plan revision, сохраняет прежнюю версию при новом candidate и проверяет CAS/recovery. [Последнее evidence](../handoffs/rdg-future-baseline-20261019/CHECKPOINT.md). | Нет подтверждения пользователя, trusted event source и выбора полного контекста; `effectiveAt` в candidate history не аттестовано. Старые Graph journals без времени и старый последний Plan без квитанции не проходят `knownAt`. |
| P3 | Есть ограниченные F-R/F-U/F-O, F-P preflight, Canon context review и read-only Plan impact. | Полная семантика Finding/Proposal/Canon, независимое подтверждение F-P, несколько событий и различение позднего знания о T1 от изменения после T1. |
| P4 | Есть foundations рабочих/research-графов. | Сквозная передача между чатами, один смысловой owner при promotion/link, archive/retrieval и успешная проверка без искусственного Finding. |
| P5 | Есть исходники Viewer и синтетический Gendocen runtime proof. | Helper grants, Plan editor/timeline, читаемая Markdown-проекция, внешний consumer и отдельная проверка установки в Windows/G2. |
| P6–P7 | Удалённая запись и вывод legacy из эксплуатации не начинались. | Canonical GitHub owner/branch/writer, multi-file CAS/failure proof, проверка лицензии движка; затем доказанное замещение legacy. |

В последнем кодовом срезе проверен отдельный технический будущий baseline
на временных Plan; адресные тесты и их scope указаны в checkpoint. Ранее прошли
49 адресных тестов для истории применимости и связанных компонентов, а перед ними 32 Python-теста
и синтетический Gendocen smoke для Plan availability, а после изменения
Graph writer — 405 Node-тестов.
Gendocen проверял **текущие** проекции, а resolver отдельно разрешал точные
старые снимки. Ни один из этих PASS не подтверждает полный historical as-of
или фактический пользовательский T1.

## Следующие локальные срезы

1. **Применимость: локальная история готова, доказательство полноты открыто.**
   Отдельный candidate owner сохраняет версии утверждений, точные Plan/RDG
   pins, `recordedAt`, `effectiveAt` с исходной точностью и `supersedes`.
   Отдельное право, CAS, квитанция после записи и recovery проверены на
   tempfile. Ранний `knownAt` исключает позднюю поправку; поздний допускает
   её только как кандидатную реконструкцию. Несвязанные outcomes дают
   конфликт, а не автоматический выбор. **Следующий gate:** определить
   полноту применимых owners/событий и независимое подтверждение времени
   применимости; испытать P2-AC-13/15/16 на таком полном контексте вместе
   с историческим Gendocen. До trusted event source результат Candidate.
2. **Lifecycle и права: технический baseline есть, события открыты.**
   Отдельный owner принимает, заменяет и отзывает точную candidate-версию
   по `plan.accept`, сохраняя историю; новый candidate не заменяет baseline.
   CAS, revoke и три точки recovery проверены на tempfile. Запись bearer не
   доказывает решение человека. Следом разделить заявление о событии,
   attestation и verification; сохранить исправления и конфликты без
   выбора Action. Выбрать доверенный пользовательский actor/source перед
   применением к данным пользователя. **Gate:** P2-AC-08/11/12/13/17/20;
   старый current-only consumer отклоняет новый lifecycle или требует review.
3. **Полный исторический resolver и Gendocen coverage.** Выбрать lifecycle и
   branch context, затем применимую версию Plan и все нужные RDG/event
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
| 09 | PARTIAL | Candidate hard не создаёт FR/F-P; accepted baseline отсутствует. |
| 10 | PARTIAL | Date/instant/relative subset проверен; новые precision, units и выполнимость окна не доказаны. |
| 11 | PARTIAL | Клиентские actual fields отклоняются; доверенный event source отсутствует. |
| 12 | PARTIAL | Plan editor не получает graph.select_action; event-attest actor ещё отсутствует. |
| 13 | PARTIAL | Локальная owner history сохраняет исходную запись и correction link; конфликт outcomes отклоняется при чтении. Нет trusted attestation и полноты контекста. |
| 14 | Локальный PASS | Точные Plan/RDG revision+digest обязательны, missing/mismatch/current fallback отклоняются. |
| 15 | PARTIAL | По квитанциям Plan и отдельного журнала ранний knownAt исключает позднюю r2; само effectiveAt заявлено без независимой проверки. |
| 16 | PARTIAL | После долговечной записи поздний knownAt допускает r2 как кандидатную реконструкцию; фактический T1 и полный as-of не подтверждены. |
| 17 | PARTIAL | Candidate и отдельный baseline journal/failpoints/recovery проверены; factual events и общий lifecycle не реализованы. |
| 18 | OPEN | Coverage для нового lifecycle/event и historical runtime ещё не проверен. |
| 19 | PARTIAL | Hash и технический bearer не принимаются за источник без snapshot; независимая human/event attestation отсутствует. |
| 20 | PARTIAL | Schema v1 и owner отклоняют accepted/actual; поведение старого consumer при новых версионированных records ещё нужно проверить. |

Локальные основания: [P0/P0.1](../handoffs/rdg-p0-dependencies-20261018/CHECKPOINT.json),
[candidate owner и P2](../handoffs/rdg-vertical-slice-20261019/CHECKPOINT.json),
[точные snapshots](../handoffs/rdg-exact-history-20261019/CHECKPOINT.json),
[Graph knownAt](../handoffs/rdg-known-at-20261019/CHECKPOINT.json),
[Plan availableBy](../handoffs/rdg-plan-availability-20261019/CHECKPOINT.json),
[двухвременной rule probe](../handoffs/rdg-two-time-scenario-20261019/CHECKPOINT.json),
[owner history применимости](../handoffs/rdg-applicability-owner-20261019/CHECKPOINT.json),
[технический будущий baseline](../handoffs/rdg-future-baseline-20261019/CHECKPOINT.json).
Полные статусы WR-01..53 сохраняются в [v4.1 ledger](../handoffs/rdg-prework-v4.1-final-20261018/WR-EVIDENCE-LEDGER.md);
новые checkpoints меняют только названный scope. При следующем срезе обновлять
эту таблицу вместе с доказательством, не повышая PARTIAL до общего PASS.
