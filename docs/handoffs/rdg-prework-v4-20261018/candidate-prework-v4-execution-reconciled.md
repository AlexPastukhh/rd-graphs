# RDG — Candidate Pre-work v4 / Execution Reconciliation

**Идентичность:** CPW-RDG-INTEGRATED-20261018-01/v4, подготовлено 18.10.2026 для передачи в другой чат.
**Статус:** CANDIDATE / NOT WHOLE-BASELINE COMMITTED / НЕ PRODUCTION ACCEPTANCE.
**Состав:** этот актуальный v4 execution contract + **полная историческая v3**, без сокращений, ниже в Приложении A. Установленные пользовательские решения из v3 сохраняются. Технические PR остаются кандидатами.
**Источник исходной версии:** https://github.com/AlexPastukhh/forfiles/blob/main/artifacts/2026-10-18/candidate-prework-rdg-integrated-temporal-plan-postreview-20261018-v3.md
**Навигация для исполнителя:** соседний HANDOFF.md. Подтверждённый локальный repo: /workspace/repos/rd-graphs. Реальный runtime Gendocen: /workspace/repos/gendocen, версия 0.1.0.dev25.
**Редакционная граница:** Приложение A воспроизводит v3 исторически; её разделы 11 и 13, включая PARTIAL/NEXT и исторические Finding statuses, **НЕ описывают текущее исполнение**. Актуальный статус только в разделах v4 ниже. v3 не была заменена или переписана на GitHub.

## V4-1. Вывод по плану и архитектурный контракт

Исходная архитектура **в целом правильна**. RDG — один semantic owner для Requirement, Action, Canon, Finding, выбранного решения и T1. Temporal Plan — самостоятельный temporal owner с шагами, событиями, альтернативными будущими ветвями, последовательностью и сроками; ссылки на RDG не становятся выбором Action. Gendocen — технический dependency/freshness overlay поверх read-only projections, receipts не подтверждают истину и не дают Authority. Authority — отдельный bearer grant/Graph API guard, не удостоверение личности и не компетенции.

**Ранее прямо установленные пользователем правила сохраняются:** создание графа даёт только кандидатов; Action.selected только через отдельное принятие и grant; revoke до durable commit прекращает запись; чату достаточно внешнего bearer, internal receipt создаёт доверенный writer; preselected/preferences в RDG не нужны; Temporal Plan именно во времени и отдельно от RDG, влияет на применимость Canon/Findings; Plan не исполняет и не удостоверяет реальные события автоматически. Повторно эти решения не спрашивать.

**Коррекция порядка:** Stage 4 технически развивался раньше, чем полностью определены семантические source dependencies и guarded Plan owner. На реальном runtime обнаружен пропуск зависимости от conditional-branch membership. Поэтому сначала полное минимальное dependency coverage, затем Plan lifecycle + permissions, затем full semantic Finding/Canon review и самостоятельные research graphs, после этого UI/production. Не выбрасывать сделанные runtime tests — они нужны как регрессия.

## V4-2. Текущий статус этапов (вывод основан на исходниках, тестах и ограничениях, не на количестве PASS)

| Stage | Фактическое исполнение | Что не принято/не сделано |
|---|---|---|
| 0 preflight | Repo writer, handoffs, исходный v3, отсутствие .git проверены | Нет canonical Git history/diff и production owner |
| 1A/1C authority | Local bearer grants/CLI, candidate-only create, separate select, internal receipt, revoke-before-commit/race/replay and denied unchanged тесты | Нет trusted Helper user bootstrap/installed UI; local remediation ещё не independent production acceptance |
| 1B Gendocen | Collision-safe IDs, stable indexed RDG+Plan projection; реальный co-located Gendocen 0.1.0.dev25 | **DEFECT** missing branch membership dependency; нет coverage matrix, реального production consumer/лицензионной ясности |
| 2 RDG semantic | Typed QRPE pilots F-R/F-U/F-O, separate F-P evidence preflight, Canon Context Review, штатный T1/selectionBasis/QRPE lifecycle | Полный typed Finding+Proposal/disposition, применимость канонов, доказанный F-P и semantic authoring contract — незавершены |
| 2P Temporal Plan | Отдельный candidate schema v1, steps/actions/events, один условный trigger, constraints/timezone/refs, read-only валидатор | Нет authorized Plan owner persistence, accepted/actual events, ветвления из нескольких событий, проверенной полной временной алгебры |
| 3 Research graphs | Наследуемые v7/full RDG/lens механизмы и отдельные тесты | Сценарий двух чатов, owner promotion/link, hide/detach/archive/delete, экономное сохранение verification без Finding не завершены |
| 3P Temporal impact | Read-only branch deadline propagation, distinct Finding drafts, targeted digest of known fields | Не полная semantics Canon/Finding; сравнение исторических RDG snapshots, multi-event, фактическое событие не поддержаны |
| 4 Persistence/freshness | RDG synthetic accepted T1 через штатный bearer writer; QRPE T2/T3 revisions, co-located Gendocen receipts, stale context, hard crash 91+recover/idempotency/history | **NOT ACCEPTED**: branch-dependency false valid, real Plan writer/owner/history, trusted user, multi-owner/source replay/corrupt journal/remote |
| 5 Integrations | Legacy Viewer/work-kit существуют, источники тестировались | Helper grant UI и доверенная выдача, Plan editor/timeline, narrative Markdown, external consumer и установленная версия отсутствуют |
| 6 Legacy retirement | Не делалось разрушительных миграций/удалений | Вернуться только после доказанной замены/отдельного согласования |

**Срез тестов:** ранее после нового synthetic T1 pilot — 405/405 Node regression; 13/13 bearer writer, 10/10 Gendocen resources, 12/12 Plan, 20/20 impact, 13/13 Canon Context Review. В последующем аудите отдельно 43/43 scoped PASS, **но** negative branch test выявил дефект. Эти PASS не означают, что весь FR/WR принят. Owner repo **без .git** — нельзя утверждать Git commit, installed Helper, remote push.

## V4-3. Выявленный DEFECT — первый обязательный следующий gate

**Observed reproduction (real co-located Gendocen 0.1.0.dev25):** на синтетическом Plan B-RESULT исход positive вёл к S-A1, negative к S-A2. После того как stepIds этих исходов обменяны (дедлайны, каноны, QRPE и actionRef не изменены), обе semantic_review-оценки остались **A1=valid, A2=valid**. Это существенная смена смыслового сценария, которую подписки не увидели.

**Причина:** текущий Gendocen smoke регистрирует canonBlock/qrpe/timeConstraintsByStep/общий deadline, но **не** branchesById/cases и ряд иных source reads (relevant steps/refs/sequence). Engine корректно реагирует лишь на объявленные dependencies. Это violation WR-31/WR-50 и осей EA-18/EA-34 исходной v3.

**Acceptance:** при смене branch membership или outcome-to-Action assignment оценка, чья применимость изменилась, должна стать review_required; при несемантической перестановке порядка cases — оставаться valid. Ввести scoped dependency coverage matrix, explicit completeness declaration, двухветвенную negative fixture, один intentionally omitted indirect prerequisite (fail closed/diagnostic), regression. Не подписывать всё на глобальный semanticSHA256 без оценки ложных invalidations.

**Repro:** docs/handoffs/rdg-prework-v4-20261018/repro-branch-membership-gap.py. Его exit 0 означает **GAP REPRODUCED**; после fix expected should change, then test updated to require correct invalidation. Не трактовать как success of product.

## V4-4. Исправленный маршрут (уровни P0–P7)

| Порядок | Scope | Выход и обязательный gate |
|---|---|---|
| **P0 NOW** | Полная coverage-contract карта RDG↔Plan→Gendocen, починка branch mismatch | Реальный Gendocen invalidates affected A1/A2 for changed branches, ignores cosmetic reorder, stable ID; новые негативные тесты |
| **P1 NEXT** | Семантический минимальный Temporal Plan owner | Plan ID+identitySpace+source path, branch/date/event status, as-of revision, adopted vs candidate plan и provenance; no implicit performed |
| **P2 NEXT** | Guarded Plan writer и события | Separate plan.create/edit/branch/event-attest permissions and graph.select; CAS/revoke-before-commit, append-only history, audit and recovery; no cross-owner escalation |
| **P3 NEXT** | Полный Finding/Canon semantic review | F-P/R/U/O evidence+questions+multi-Proposal/disposition, Canon applicability, upstream compositions; external truth attestation as separate gate; no F-P from candidate deadline |
| **P4 NEXT** | S-WORK lifecycle | Research graph two-chat resume; one-owner promotion/link; archive, hide/detach/delete, lazy retrieval, valuable success without Finding |
| **P5 LATER** | End-to-end S-AUTH/S-TEMP/S-DEP-REP UI | Trusted Helper grants, Plan authoring, Viewer timeline, narrative Markdown and external read consumer; separate installed test |
| **P6 LATER** | Production persistence/remote | User chooses canonical GitHub repo/branch/actor; multi-file transaction/ref CAS, failpoints/index/recovery; legal/runtime checks |
| **P7 CONDITIONAL** | Legacy retirement | Only with accepted replacement/coverage; keep O/D, stable/protected and Lens until proven otherwise |

Read-only work on P3/P4 can run in parallel after identity/owner alignment; guarded writes depend on Authority + Plan contract. No executor/scheduler in initial Plan release. The plan is not a literal calendar schedule and no RDG implementation deadline was agreed.

## V4-5. Acceptance gates and priority risks

**PG-AUTH:** local grants and semantic guards tested, but real Helper identity/trust bootstrap and user-facing grants pending. Bearer receipt ≠ human signature. Review F-P-RV-01/02/03 locally addressed with real writer tests; F-P-RV-04 UI denial partially, independent post-fix review still pending.

**PG-SEM:** legacy O/D preserved; typed Finding schema remains partial, verified F-P absent; negative Canon and upstream comparison require semantic design. T1 is immutable in synthetic writer, cannot be rewritten by later QRPE/T3 or Gendocen recover.

**PG-PLAN:** candidate model and refs work read-only; no plan.write/actual-event-attest authorizer, versioned acceptance, owner storage or actual event lifecycle. Read-only synthetic Plan strength=hard never becomes project committed fact.

**PG-DEP-REP:** real dependency engine works including receipts and recovery; conditional-branch membership gap reproduced; dynamic rule completeness and materialization Markdown/external app unproven.

**PG-WORK:** no accepted promotion/link/archive scenario across two chats. Keep one semantic owner when integrating research results. C1/C2 and C3 persistence criterion remains as v3.

**PG-PERSIST/ROLLOUT:** local writer journal and Gendocen state proof, no chosen canonical remote owner/installed Helper/Viewer; do not push, install or migrate without explicit scope. Gendocen source appears to lack discoverable LICENSE in inspected tree, check redistribution before distribution.

**Technical T1 ≠ user authorization:** newest smoke creates EV-T1 using real graph-apply bearer writer with by=assistant in **synthetic** temp graph; observed revisions 3→4→5 for selected A1 then F-R Finding then QRPE transition. It proves technical guard/history, not that a real user accepted an Action or that T2/T3 were externally observed facts.

**Commit/distribution gate:** the original v3 in GitHub is reading copy, not canonical work graph. This v4 remains local candidate. No Git commit exists in local RDG mount.

## V4-6. Work Requirements status ledger (WR-01…53)

This is an **execution** classification over the complete normative WR text in Appendix A. Status vocabulary: DONE-LOCAL (tested pilot, not production), PARTIAL, OPEN, DEFECT-REPRODUCED, DECISION-GATE.

| WR | Current | Remaining gate |
|---|---|---|
| WR-01 | PARTIAL | repo preflight done; no Git owner diff |
| WR-02 | PARTIAL | user decisions preserved, not all PR accepted |
| WR-03 | OPEN | trusted Helper grant UI |
| WR-04 | DONE-LOCAL | bearer for 2 test actors |
| WR-05 | DONE-LOCAL | admin issue/amend/revoke/list |
| WR-06 | PARTIAL | delegated admin scoped tested |
| WR-07 | DONE-LOCAL | revocation race/replay local |
| WR-08 | PARTIAL | user-facing useful denial UI |
| WR-09 | PARTIAL | full operation path matrix |
| WR-10 | PARTIAL | human trust and decision autonomy |
| WR-11 | PARTIAL | all redaction/secret logs |
| WR-12 | DONE-LOCAL | guard boundary explicit |
| WR-13 | PARTIAL | F-R/U/O typed; F-P blocked |
| WR-14 | PARTIAL | questions/evidence/PR multi-relations |
| WR-15 | PARTIAL | independent dispositions/status |
| WR-16 | PARTIAL | open canon authoring provenance |
| WR-17 | PARTIAL | upstream comparison end-to-end |
| WR-18 | PARTIAL | T1/prepared-to-working full lifecycle |
| WR-19 | PARTIAL | selected vs performed/verified |
| WR-20 | PARTIAL | full Graph API operation inventory |
| WR-21 | PARTIAL | legacy O/D compatibility not migration |
| WR-22 | OPEN | C1 OR C2 plus C3 applied scenario |
| WR-23 | PARTIAL | transient Lens yes, retirement later |
| WR-24 | PARTIAL | research two-chat demonstration |
| WR-25 | OPEN | hide/detach/archive/delete/lazy retrieval |
| WR-26 | OPEN | cross-graph promotion one owner |
| WR-27 | OPEN | valuable success without Finding |
| WR-28 | DONE-LOCAL | RDG JSON read-only Gendocen projection |
| WR-29 | PARTIAL | stable IDs yes; branch deps gap |
| WR-30 | DONE-LOCAL | real receipts and stale review in pilot |
| WR-31 | DEFECT-REPRODUCED | missing indirect branch dependency |
| WR-32 | OPEN | narrative Markdown representation |
| WR-33 | OPEN | external consumer read view |
| WR-34 | PARTIAL | no silent RDG write, real authorized review pending |
| WR-35 | PARTIAL | local recovery yes, remote no |
| WR-36 | DECISION-GATE | canonical GitHub repo/branch/writer |
| WR-37 | OPEN | Helper+Viewer new features installed |
| WR-38 | OPEN | no deprecation decision |
| WR-39 | PARTIAL | scope tests+full regression, no independent review |
| WR-40 | PARTIAL | runtime yes, license pending |
| WR-41 | DONE-LOCAL | candidate-only graph.create |
| WR-42 | DONE-LOCAL | separate selected Action |
| WR-43 | DONE-LOCAL | local revoke vs durable commit |
| WR-44 | DONE-LOCAL | bearer-only client + internal receipt |
| WR-45 | PARTIAL | standalone Plan read-only no writer |
| WR-46 | PARTIAL | temporal subset windows/relative dates |
| WR-47 | PARTIAL | single event hypothetical branching |
| WR-48 | PARTIAL | qualified actionRef not live owner writes |
| WR-49 | PARTIAL | deadline risk F-R pilot not full Canon |
| WR-50 | DEFECT-REPRODUCED | branch invalidation absent |
| WR-51 | OPEN | separate plan.write vs event.attest |
| WR-52 | PARTIAL | synthetic T1 yes, Plan history absent |
| WR-53 | PARTIAL | Plan read-only not timeline UI |

**EA assessment:** EA-18 and EA-34 have new confirmed manifestation: missing Plan branch dependency despite valid receipts. EA-28/29 locally guarded on candidate-create and revoke boundary. EA-30..36 partly tested as read-only, but real event-attest and Plan writes are absent. Other EA axes remain review targets; do not mark the whole EA table solved because Node suite passes.

## V4-7. Handoff/evidence for execution

- Original complete WR/EA/FR/PR wording and provenance: Appendix A below; unchanged v3 raw copy separately in this directory.
- Current code: tools/rdg-authority.py, tools/graph-apply.py, tools/rdg-v7-model.py, tools/rdg-temporal-plan.py, tools/rdg-temporal-impact.py, tools/rdg-finding-drafts.py, tools/rdg-gendocen-adapter.py, tools/rdg-gendocen-runtime-smoke.py, tools/rdg-gendocen-t1-history-smoke.py.
- Current stage docs in docs/guides, checkpoint JSON in docs/examples/RDG-GENDOCEN-*.json. The next chat should independently re-read code and test it rather than treating report PASS as product certification.
- Local scope evidence: bearer writer 13/13; Plan 12/12; Temporal impact 20/20; Canon Context Review 13/13; adapter 10/10; previous full Node 405/405. Post-audit 43/43 scope PASS but independently reproduced branch counterexample FAIL.
- No use of user graph.json, real tokens, GitHub canonical live push, installed Windows Helper/Viewer or automations/executor is authorized by this handoff.

---

# Приложение A. Полный исторический Candidate Pre-work v3

Этот исходный текст сохранён **полностью**, включая его тогдашние разделы 11/13 с устаревшими стадиями и статусами. Для фактического текущего состояния использовать V4-2…V4-7 выше. Исходный GitHub blob SHA: 6da1a3648528c01179bcc792b636f56d6b823901.

# RDG — Candidate Pre-work Composition v3: Authority, Findings, Temporal Plan, Gendocen и представления

**Идентичность линии:** CPW-RDG-INTEGRATED-20261018-01/v3 · редакция 2026-10-18.  
**Статус:** **CANDIDATE COMPOSITION / NOT WHOLE-BASELINE COMMITTED**. Пользователь утвердил отдельные смысловые правила поведения, но не коммитил все Proposals, migration или новый production релиз.  
**Роль:** **reading copy / not canonical**. Это полная пересмотренная редакция v2, а не замена исторической v2 и не отчёт о завершённой реализации.
**Изменение scope по отношению к v2:** включены результаты частичного исполнения и независимого Final Review v1; последующие прямые решения пользователя о создании/принятии Action, отзыве токена, внутреннем HMAC, отсутствии `preselected`; самостоятельная **Temporal Plan** — модель действий/событий **во времени**, условных ветвей и дедлайнов с взаимной смысловой связью с RDG.

**Срез фактического исполнения:** Stage 1A частично реализован (bearer grants, opt-in package guard, узкие tests); Stage 1B содержит read-only JSON projection adapter, но без подтверждённого полного Gendocen runtime. Независимое review обнаружило четыре подтверждённых Problems, два Risks и две Decision Uncertainties в ограниченном scope. **Не заявлять production readiness, установленный Helper/Viewer, полную интеграцию или устранение Findings.** Проверенный источник — [Final Review v1](https://github.com/AlexPastukhh/forfiles/blob/main/artifacts/2026-10-18/review-rdg-authority-gendocen-pilot-20261018-v1.md). Исторический [Candidate Pre-work v2](https://github.com/AlexPastukhh/forfiles/blob/main/artifacts/2026-10-18/candidate-prework-rdg-integrated-authority-gendocen-representations-20261018-v2.md) сохраняется без изменения.

**Как читать v3:** исходные `N/FR/WR/EA/H-PR` и прежние открытые вопросы сохранены с их IDs и статусами; новые `WR-41..53` и `EA-28..36` не переименовывают старые; разделы ниже определяют **актуальный v3 route**. Если исторический кандидатный текст v2 предполагает ещё не начатую Stage 1A/1B, пользоваться обновлённым factual status в `11 и `13, а не считать её невыполненной целиком.

## 1. Scope, история и иерархия оснований

### 1.1. Что именно вошло в проверку

1. Переданные семь файлов переписки `1 (2).txt` → `7.txt` (не независимые согласованные решения, а хронология вариантов). Последнее прямое пользовательское уточнение в них имеет больший вес относительно ранее предложенных чатом способов. 
2. `RDG-handoff-full-2026-10-17(1).zip`: `01-FULL-CONTEXT-AND-ARCHITECTURE.md`, `02-REPO-AND-HISTORY.md`, `03-OPEN-DECISIONS-AND-ROUTE.md`, оригинальный `04-REVIEW-PROMPT-ORIGINAL.txt`, `05-RECENT-DISCUSSION-CHRONOLOGY.md`. Девять H-PR — кандидаты, не baseline.
3. Полная предшествующая Candidate Pre-work v1 от 17.10: Authority + Findings + roadmap; все её существенные пункты восстановлены, включая UI, transport, compatibility, доказательные ограничения и полный цикл исследования.
4. Сообщения **этого чата** после v1: (a) пользователь управляет полномочиями в Helper и выдаёт bearer-токен любому чату; (b) RDG имеет дополнительные представления Markdown/других приложений; (c) Gendocen надо рассматривать как действующий JSON-based dependency engine поверх RDG, а не автоматически переписывать его механизм в RDG.
5. `gendocen-main (1)(1).zip`: README, dependency/semantic/materialization docs и `src/docengine/resources.py`. В архиве указаны runtime `0.1.0.dev25` и structured-resource contract `$docengine` + `data`. Runtime есть, но интеграция с RDG не тестировалась. В этом архиве не обнаружен файл LICENSE: перед заимствованием кода/дистрибуцией проверить правовые условия отдельно.
6. По предыдущей **адресной read-only проверке** RDG: `/workspace/repos/rd-graphs` в Windows RW mount, `/workspace/repo` — отдельный Docker volume; в дереве проекта **нет `.git`**. Проверенные ранее `tools/rdg-graph-api.py`, `tools/graph-apply.py`, `tools/graph-package.py`, `tools/graph-index.py`, `tools/rdg-github-store.py`, Viewer/Helper guides дают основание для плана, **не означают свежий полный аудит кода или исполнение тестов в этом этапе**.

**Дополнительные источники v3 (в хронологическом порядке):**
7. Частичное исполнение по команде пользователя: `tools/rdg-authority.py`, opt-in изменения `tools/graph-package.py`, `tools/rdg-gendocen-adapter.py`, тесты `tests/rdg-bearer-authority.test.cjs`, README; завершившийся тогда полный regression run 405/405 относится к тому срезу, не к исправлениям после review.
8. Независимая проверка **R-RDG-PILOT-20261018/v1**: изолированный разрешённый и запрещённый write, amend/revoke, воспроизведённые обход семантического `graph.create` и гонка revoke→commit; текущие локальные тесты 2/2 authority CLI и 7/7 legacy Graph API; установленного `docengine` в исследованном окружении не было.
9. Следующие пользовательские решения: (а) `graph.create` создаёт граф с кандидатами, **не принимает решения**; подготовка вариантов, канонов, Findings и принятие могут принадлежать разным чатам; (б) отзыв до фиксации транзакции запрещает её; (в) **одного bearer-токена достаточно для обращения к Graph API**, внутренние подписи/receipts обеспечивает доверенный API; (г) `Action.status=selected` — действительно принятый Action, не предпочтение; **не вводить `preselected` и не хранить обычные предпочтения**; (д) **Plan** — отдельный временной объект, куда входят Actions из графов, действия, события, условные ветви, сроки и будущие возможные варианты; RDG учитывает Plan при выработке Findings/Canon.
10. Прямые исходники про границу модели: `docs/guides/RDG-V7-WORKING-GRAPHS.md` («Планирование будущего на бумаге»); `work-kit/modules/rdg.work.semantics.module.md` (соседние R **не задают** очередность исполнения); `work-kit/modules/rdg.work.planning.module.md` (PLAN ≠ commit/исполнение). **Отдельной завершённой модели temporal Plan там не подтверждено**.

### 1.2. Сохранить статус каждого слоя

**Явные пользовательские ожидания/требования к цели:** возможность управлять правами в Helper; создавать токен с заданными полномочиями для **любого** чата, получившего токен; проверять токен Graph API до материального действия; предусмотреть API управления правами и понятный отказ с объяснением; не строить тяжёлую враждебную защиту, будто ИИ намеренно ищет обход; возможность представлять RDG как Markdown с абзацами и передавать в приложение для другого представления. **Это уже вход задачи**, но не утверждённый конкретный способ реализации.

**Поздние пользовательские направления, пока не committed architecture:** Authority Scope с учётом проекта/роли/операции; QRPE→типизированные Findings по review-промпту; открытые каноны и сравнение альтернатив upstream/downstream; `(C1 OR C2) AND C3`; transient Lens и отсутствие отдельного обязательного LensRun; самостоятельные долгие рабочие/исследовательские графы; hide/detach/archive/delete; сохранение ценного результата проверки без Finding; использование Gendocen поверх RDG JSON. Предложения были сформулированы как идеи/предпочтения; ни один общий design commit не найден.

**Существующие реализованные пилоты, не design baseline:** legacy v7 O/D, opt-in candidate-v6 Action; локальный пакетный writer/recovery; старый `ordinary/stable/protected` с частичными guards; HMAC issuer, который **не удостоверяет пользователя**; GitHub single-file SHA CAS + двухфайловый research sidecar без атомарности; persistent Lens research; read-only Viewer Action pilot. Их не удалять и не объявлять окончательными требованиями.

**Неприкосновенная граница данной работы:** не менять рабочие `graph.json`, код, Windows/Helper/Tampermonkey, доступы ОС и токены; не включать остановленный owner HOST/G2 и не расширять mounts; не выбирать канонический GitHub owner или не делать live push без отдельного решения. Не переносить приватные исходники/графы как публичные данные; `AlexPastukhh/forfiles` — **reading copy**, не semantic owner RDG.

**Уточнённые пользовательские ограничения v3:** само создание графа и планирование использования Action не утверждают Action; статус `selected` требует отдельного разрешённого акта. Возможно, один чат создаёт кандидаты/каноны/Findings, другой уполномоченный чат принимает Action. Преждевременный `preselected` не нужен: условные возможные действия и будущие решения выражает **отдельный Temporal Plan**. Пользователь требует, чтобы отзыв до фиксации исключал запись; выдаваемый чату bearer — достаточный внешний credential, HMAC/receipt является заботой API. Plan самостоятелен во времени, с ветвями и событиями; он может ссылаться на кандидатные и принятые RDG Actions, но не передаёт своему автору право их принимать или исполнять.

**Граница этого v3 обновления:** пишем только версионный Candidate документ в частный `forfiles` как reading copy. Не модифицируем настоящие исходники RDG/Plan/Gendocen, user graphs, токены, Windows-installed Helper/Viewer, canonical GitHub owner. В отличие от исторической v2, частичное изменение кода уже происходило **до** этой редакции; оно описано как текущая неполная реализация, а не исполнено данной публикацией.

## 2. User Needs / Fundamental Requirements / статус

| ID | Нужда / обязательное условие | Статус и provenance |
|---|---|---|
| **N-01** | Вести сложную работу по смысловым графам с понятными причинами решений, следами evidence и безопасным пересмотром. | Из пользовательского RDG-контекста/handoff; user need. |
| **N-02** | Делегировать чатам работу без постоянного ручного посредничества, сохранять пользовательское управление существенными правами и решениями. | User need, подтверждено последними сообщениями. |
| **N-03** | Исследования между чатами не должны засорять основной рабочий контекст; находки/проверки и полезная история не теряются. | User need, сообщения 6–7. |
| **N-04** | Использовать один смысловой граф в разных формах и приложениях вместо обязательного GUI «узлы/стрелки». | User need, последнее сообщение о представлениях. |
| **N-05** | Автоматически узнавать, когда изменение основания затрагивает старый вывод или производное представление, без разработки лишнего второго движка. | Candidate/inferred need из предложения пользователя использовать Gendocen. |
| **FR-01** | Пользователь имеет удобный способ **в Helper** создавать, просматривать, изменять и отзывать выданные полномочия. | Прямое user requirement; детали UX/хранилища pending. |
| **FR-02** | Пользователь может получить токен с выбранными полномочиями и передать его **любому** чату; предъявление токена разрешает операции по действующим правам, **без автоматической привязки к личности чата**. | Прямое user requirement. |
| **FR-03** | Graph API проверяет право **перед** записью; недопустимая операция не меняет граф и возвращает причину/путь получения разрешения. | Прямое user requirement + необходимая операционная семантика enforcement. |
| **FR-04** | Имеется административный API для выдачи/изменения/отзыва/инспекции полномочий; такие операции сами проходят проверку права. | User requirement; возможность делегировать администрирование в пределах прав — candidate. |
| **FR-05** | Объём технической защиты соразмерен задаче: Graph API guard реален, но абсолютная изоляция от доступа к исходникам/ОС **не** заявляется. | User preference/constraint; не означает право bypass или отключение проверки. |
| **FR-06** | Текущая смысловая запись, identity и история принятого решения (T1) не искажаются при расширении канонов, переоценке или передаче между графами. | Наследуемый RDG invariant; проверить точный committed owner до материального изменения. |
| **FR-07** | Существенные Finding, Proposal и состояния решений не смешиваются; происхождение новых критериев, evidence и отмен/пересмотров сохраняется. | Candidate/inferred как детальный инвариант новой семантики, из review/user direction. |
| **FR-08** | Представления Markdown и внешнего приложения **не требуют менять основной JSON формат RDG** и не становятся молча вторым semantic owner. | User direction + candidate/inferred technical invariant. |
| **FR-09** | Gendocen работает **поверх** канонических RDG JSON через совместимый адаптер либо непосредственную интеграцию; семантическая инвалидация не принимает решение за RDG. | Candidate/inferred из user proposal; способ интерфейса pending. |
| **FR-10** | Текущие legacy-графы, записи и установки нельзя ломать несанкционированной миграцией, скрытым cutover или необратимым удалением. | Ранее установленные ограничения проекта и user safety. |
| **N-06** | Иметь **отдельный план во времени**: последовательность, условные и возможные пути, будущие события, действия и дедлайны; видеть не только смысловые решения, но и возможное развитие работ. | **Explicit user**, последующие сообщения после review; принцип, не утверждение конкретного формата. |
| **N-07** | Использовать временной Plan для более точного исследования применимости Actions, новых канонов, Findings, рисков сроков и изменения будущего пути, сохраняя один смысловой owner RDG Action. | **Explicit user**, двусторонняя связь Plan↔RDG; техническая интеграция candidate. |
| **FR-11** | **Plan — самостоятельная сущность, отражающая время**, а не подвид Action, Requirement, Viewer или Gendocen projection; возможны действия, события, дедлайны, условия и ветвления. | **Direct user semantic requirement**; Plan owner/storage/schema pending. |
| **FR-12** | План может ссылаться на сущности RDG (включая кандидатные Actions), не изменяя их semantic owner, не принимая их автоматически и не приписывая будущим возможным событиям факт наступления. | Прямое user direction + сохранение FR-06/10; reference mechanism candidate. |
| **FR-13** | При оценке канонов и Findings RDG может учитывать Plan, его сроки/условия/ветви и доступность времени; гипотетический дедлайн не превращается автоматически в обязательный проектный constraint. | **Direct user goal** + inferred safety boundary; scope/acceptance provenance обязательны. |
| **FR-14** | `Action.selected` — действительное принятие; `graph.create` разрешает только candidate creation, а собственно принятие — отдельный разрешённый акт; предпочтение/`preselected` не хранить в RDG. | **Установлено пользователем после review**, заменяет прежний кандидат предварительного предпочтения. |
| **FR-15** | Если bearer отозван **до commit**, запись не происходит; чат предъявляет только bearer, доверенный Graph API сам выполняет внутренние подтверждения, без выдачи отдельного HMAC-ключа чату. | **Установлено пользователем после review**, реализация пока нарушает часть требований (см. R-RDG-PILOT). |

**Отделение FR от способов:** «использовать именно stateful opaque token с hash-реестром», «хранить Gendocen-миррор в `docs/_structured`», «ввести конкретный endpoint/таблицу ACL», «использовать Git Trees API» — всё это **PR**, а не FR. Вариант bearer-token как принцип передачи прав напрямую установлен пользователем; выбор внутреннего формата и storage — ещё нет.

## 3. Candidate Desired Real-Life Definition (DRLD): четыре сценария — включая Temporal Plan

В переданных материалах не найден подтверждённый **принятый** полный DRLD для новых capabilities. Описания ниже — **candidate/inferred**, каждое содержит три части **одного** сценария; они не образуют нового отдельного канонического владельца требований.

### S-AUTH — пользователь выдаёт и изменяет полномочия чатам

**Fundamental Benefit:** пользователь самостоятельно управляет, кто через токен может совершать конкретные изменения; чат с достаточными правами работает без ненужного согласования, а с недостаточными понимает ограничение и нужный следующий шаг.

**Concept:** пользователь управляет токенами и grants через Helper; любой получивший токен чат предъявляет его Graph API; trusted verifier проверяет действующий scope и Graph API invariants; пользователь изменяет/отзывает права, которые учитываются при следующей операции. Не путать API bearer authentication с компетентностью/правом принимать решения как семантической оценкой.

**Detailed path:** пользователь открывает права в Helper → выбирает область графов, классы операций и при необходимости ограничения → генерирует bearer-токен и передаёт чату → чат исследует граф и предъявляет токен для разрешённой операции → сервер/adapter проверяет актуальный grant + целевой объект + expected revision + инварианты; при успехе записывает и проверяет read-back → при отказе **до записи** выдаёт код, недостающее право, scope и понятный путь запроса → пользователь через Helper меняет или отзывает полномочия → последующая операция использует новое состояние; повтор/конкурентная запись не должны частично обойти отзыв/ревизию. Польза достигается в каждой успешной разрешённой самостоятельной операции и каждом понятном отказе; пользователь получает наблюдаемый контроль при выдаче и отзыве.

**Scope:** управление правами на изменения графов (а не автоматическое управление ОС, GitHub credentials или расходами на внешние эксперименты). Для административного bearer-токена — отдельный санкционированный grant; обычный токен изменения графа не даёт автоматически права раздавать права.

### S-WORK — многочатовое исследование и изменение RDG

**Fundamental Benefit:** работу можно передать другому чату, возвращаться к основаниям решений и сохранять только нужную долговременную информацию, не превращая главный граф в историю всех исследований.

**Concept:** обычный полный рабочий RDG-граф с собственной R/A/Canon/Finding/Context может существовать отдельно; подготовленные графы/Lens используются как методы; материальные результаты остаются в графе владельца, затем связываются с основным проектом и при необходимости архивируются.

**Detailed path:** основной граф содержит принятый Action; чат обнаруживает материальное противопоказание, исследует не только текущую альтернативу, но и возможную upstream-композицию (`U1+A2` против `U2+A1` и других существенных вариантов) → для большой работы создаёт отдельную root-R research graph, не обязательную Git branch → несколько чатов ведут R/A, typed Findings, вопросы, каноны, эксперименты → выбираются допустимые решения строго по Authority Scope; фиксируется результат и evidence, даже если отрицательных Findings нет → важные данные связываются или переносятся без двойного активного владельца → отдельная ветка/граф скрывается, отсоединяется, архивируется либо безопасно удаляется; архив находится через индекс или Viewer toggle без автоматической загрузки всего содержимого; T1 и ссылки сохраняются. Сохранение согласно `(C1 OR C2) AND C3`.

### S-DEP-REP — изменение данных, зависимые проверки и альтернативные представления

**Fundamental Benefit:** пользователь получает удобные документы/интерфейсы и своевременно узнаёт, что изменение существенного основания требует новой проверки, при этом не вынужден поддерживать ручные копии смысловой модели.

**Concept:** RDG `graph.json` остаётся canonical; тонкий адаптер раскрывает стабильные значения Gendocen для tracked reads/semantic rules. Gendocen фиксирует baselines, receipts и состояния `build_required/review_required/stale`, строит/проверяет производные представления. RDG-ИИ интерпретирует смысл и при необходимости пишет через token-guarded Graph API; Markdown и внешнее приложение только читают/представляют, если не утверждён отдельный write-back режим.

**Detailed path:** пользователь/чат берёт RDG-граф → выбирает полезную текстовую/графическую/табличную форму → адаптер адресует конкретные поля R/A/Finding/Context по стабильным ID, строит Markdown с абзацами или отдаёт typed data внешнему приложению → сохраняет provenance и source revision → после изменения несущественного поля не возникает ложного пересмотра → после изменения зарегистрированного существенного основания Gendocen сигнализирует `review_required/stale` с diff/baseline → ИИ получает свежий review packet, проверяет смысл в пределах полномочий, не объявляет автоматически Problem и не переписывает T1 → по необходимости создаёт Finding/Proposal или отмечает ценную успешную проверку через общий API → устаревшее Markdown-представление перестраивается; пользователь видит, что оно generated/as-of, и может перейти к семантическому owner. Технический `review_context_id` от Gendocen не заменяет токен полномочий RDG.

### S-TEMP — самостоятельный Temporal Plan и обратная связь с RDG

**Fundamental Benefit:** пользователь видит **развитие работы во времени**, не только варианты смысловых решений: что можно/предполагается сделать, при каких условиях, что ожидается, какие альтернативные будущие ветви существуют и где сроки угрожают достижению цели. Полученная польза — на этапе осмысления будущего пути, при изменении условий и при наблюдении реальных событий.

**Scenario Concept:** независимо существующий, версионный `Plan` имеет собственный owner/identity и временную структуру. Plan ссылается по устойчивым идентификаторам на RDG Actions/Requirements/Contexts (не копирует их как независимых смысловых владельцев), содержит запланированные и гипотетические шаги/события, временные связи, условия, альтернативы и дедлайны. RDG сопоставляет каноны/Findings с применимой ветвью, моментом и сроком Plan; Gendocen может обнаруживать изменения зарегистрированных зависимостей, но не принимает Action и не запускает исполнение.

**Detailed Desired Real-Life Scenario (candidate):** есть RDG с R и кандидатами A1/A2. Пользователь или ограниченный чат создаёт Plan P1 и указывает горизонт/временное начало, событие получения эксперимента, относительный срок принятия решения и внешний дедлайн. В Plan отражены: «проверить A1», «когда получен результат — при положительном исходе рассмотреть принятие A1; при отрицательном — исследовать A2», «выполнять принятую Action только после санкционированного выбора», «завершить проверку до даты/планового окна». Можно создать несколько возможных **ветвей будущего** без выбора одной, с явно разными правовыми/временными статусами; неизвестная дата не требует выдумать точное время. Пользователь с правом принятия позднее может отдельно выбрать Action через Graph API — это **не** побочный эффект Plan. Когда фактическое событие произошло, Plan регистрирует его как наблюдённое событие с provenance; это не задним числом делает прогноз фактом. После изменения дедлайна или порядка Plan система определяет, на какие evaluation/canons/Findings/Actions изменение **может** влиять, различает hard/soft/гипотетические ограничения и пересматривает вывод с evidence. Обратное изменение RDG Action/Canon может потребовать изменения будущей ветви Plan, но не выполняется автоматически. Польза достигается при составлении осмысленного графа будущего и повторной оценке изменившегося горизонта.

**Scope/границы:** это не календарь с обязательным UI, не cron-сервис, не motor автоматического выполнения и **не** новый Action status. Plan может описывать **возможное** действие по candidate Action без обязательств исполнить его; отдельные решения о принятии **Plan/ветви** и о принятии **RDG Action** сохраняют разные semantics. Реального accepted DRLD на Plan пока не установлено, детальная механика — Candidate.



## 4. Scenario Realization Composition и границы реализации

| SRU / parent context | Purpose и capability → output | Prerequisite / success criterion |
|---|---|---|
| **SRU-01: контракт RDG** (S-WORK/S-DEP-REP) | Согласовать существующий v7 O/D, opt-in Action, QRPE, Canon, T1–T3 и identity; получить точные независимые интерфейсы чтения/записи. | Актуальное чтение schema/API/instructions, compatibility fixtures; нет скрытой миграции. |
| **SRU-02: модель Authority** (S-AUTH) | Credential/grant/scope, read/research/experiment/recommend/select/mutate/admin права, project/role/operation context и failure semantics. | Пользователь как исходный управляющий в Helper; authority ≠ AI competence; permission taxonomy простая. |
| **SRU-03: административный API + Helper** (S-AUTH) | Выдать, просмотреть, изменить, отозвать и при явном праве делегировать токен; UI удобен пользователю. | Достоверный источник пользовательского управления; policy state хранится у verifier, не в редактируемой чатом подсказке. |
| **SRU-04: Graph API enforcement & writes** (S-AUTH/S-WORK) | Все material graph-edit операции атомарно guard до commit, с helpful denial, version/idempotency/read-back. | SRU-01/02, проверенный writer; denied не изменяет состояние. |
| **SRU-05: Finding/Canon/Action semantics** (S-WORK) | Typified Findings по review-prompt, открытый canon, upstream reasoning, однообразные операции. | SRU-01/04; backward compatibility и T1 invariants. |
| **SRU-06: independent graphs/lifecycle** (S-WORK) | Отдельные root-R graphs, owner/link/promotion, hide/detach/archive/delete, lazy retrieval, result of successful verification. | IdentitySpace/index + local cross-file transaction; нет двух активных canonical owners. |
| **SRU-07: Gendocen overlay** (S-DEP-REP) | Без изменения RDG JSON получить stable-resource adapter, dependency rules, receipts, semantic invalidation, exact results. | Исследовать package/root/JSON wrapper/state/side effects/license; narrow synthetic test. |
| **SRU-08: представления** (S-DEP-REP) | Читабельный Markdown с абзацами, внешние typed consumers, версия/происхождение представлений; write-back только отдельным PR. | SRU-01/07 в выбранном объёме; generated docs != semantic owner. |
| **SRU-09: сохранение/публикация** (все) | Multi-graph recovery/index and, позже, согласованный GitHub transport, concurrent access и ref checks. | User-selected canonical owner/branch перед live remote; тесты partial commit/recovery. |
| **SRU-10: Viewer/Helper integration + rollout** (все) | Реальный end-to-end S-AUTH/S-WORK/S-DEP-REP, миграционные инструкции, независимый контроль установленной версии. | Все необходимые SRU готовы; изолированный browser, затем отдельная санкция для установленного клиента. |
| **SRU-11: Temporal Plan model/owner** (S-TEMP) | Отдельные Plan identity/version, временные шаги/события, абсолютные/относительные ограничения, условные ветви, возможные/запланированные/произошедшие состояния, provenance. | Явное отсутствие `preselected`; минимальная версия до scheduler; формальные события не из текста чата. |
| **SRU-12: RDG↔Plan semantic references/evaluation** (S-TEMP + S-WORK) | Stable cross-owner refs к RDG Actions/Context/R, contextual findings/canon checks с deadline/scenario status, Plan permission guard и адресная dependency invalidation. | SRU-01/02/04/05/11; Plan authoring ≠ Action selection; chosen temporal context source/version известны. |

Только **реализация SRU рекурсивна**. DRLD — не техническое дерево. SRU-03 административный Helper можно прототипировать с моковым verifier; полноценный remote transport SRU-09 не нужен до доказательства первых сценариев. Gendocen overlay и часть semantic contract можно проверять параллельно с auth validation.

## 5. Work Value / стоимость / версия

**Историческая мотивация v2** остаётся: использовать имеющийся Gendocen поверх RDG JSON, не разрабатывать второй dependency engine без доказанной необходимости; локальный bearer token прежде installed Helper; независимые исследовательские графы без обязательного LensRun и без потери T1.

**Новый результат ранней работы:** Stage 1A и 1B уже дали информацию, а не acceptance. Подтверждены рабочие локальные выдача/изменение/отзыв и data projection, но Final Review v1 доказал semantic create bypass и revoke-before-commit race; CI тестовые 405/405 сами не закрывают эти дефекты. **Ценность ближайшей работы** — устранить два нарушения и добавить writer-path/конкурентные тесты *до* полномочного расширения scope/выпуска. Минимальная проверка полезнее, чем сразу строить UI/сложную ACL.

**Почему Temporal Plan нужен отдельно:** попытка хранить будущие шаги и условные дедлайны в `Action.preselected` создала бы смешение «осмысленное решение принято» с «возможно, что-то выполним позже». Собственный временной объект обеспечивает условные сценарии, сравнение длительности/дедлайнов и обратную связь с канонами/Findings, не меняя Action status. **Минимальный достаточный следующий scope** — синтетический Plan со стабильной ссылкой на 1–2 Actions, событием, deadline и двумя условными ветвями; сначала read-only evaluation, затем осторожные write operations. Не строить сразу job scheduler, executor, high-granularity календарь или повторяющийся Status Log без фактической нужды.

**Три поверхности затрат:** (1) *Plan operation* — при использовании обновлять нужные события/сроки, разбирать условные ветви, не тратить время на ручные копии RDG; (2) *delivery* — исправление authority, state machine минимального Plan, references, integration/checks, затем UI; (3) *lifecycle* — согласование двух semantic owners и технических receipts/версий, цена migration, возможное удаление устаревших путей отдельно. Основной риск full-now — неоправданный рост сложности/переделка; риск слишком малого pilot — ложный сигнал, что temporal versioning/branches/revoke уже безопасны.

**Сроки:** для **реализации RDG** пользователь не установил hard deadline, бюджет или выделенные ресурсы; effort, critical path и slack unknown. Напротив, дедлайны **конкретных Plan проектов** являются domain data с собственным статусом `hard/soft/candidate` и никак не создают дедлайн реализации самой системы.

**Кандидатные этапы поставки:** `V-validation` (изолированные разрешения/adapter/Plan branch proof), `V-local` (guarded writer + temporal Plan/read-only evaluation), `V-integrated` (installed Helper/Viewer + temporal representations), `V-remote` (отдельное разрешение canonical GitHub owner). Это **кандидатный route**, не уже принятый выпуск, не фактически завершённая функциональность.

## 6. Candidate Work Requirements (WR) к работе по реализации

**Все WR в этом документе — candidate baseline будущей работы.** Их provenance различает явное требование пользователя, действующий исторический инвариант и условную детализацию Proposal. Они не являются автоматически committed RDG nodes. Проверка «PASS» относится к будущему выполнению; настоящие тесты не запускались.

| WR | Проверяемый критерий результата | Provenance / trace / условие | Будущее evidence |
|---|---|---|---|
| **WR-01** | До записи установить действующие source paths, инструкцию проекта, права, отсутствие скрытого owner и фактическую версию. | Existing governance; FR-10, SRU-01 | Read-only preflight; `git status` только в подлинном Git tree; diff. |
| **WR-02** | Никакое user wording не повышает само себя из Proposal в committed implementation; фиксируются исходные ограничения и T1/T2/T3. | User review method; FR-06/07 | Schema/history tests и trace принятия. |
| **WR-03** | Пользователь видит в Helper права и может создать token с указанными scope/operations. | **Explicit user**; N-02, FR-01/02, S-AUTH | UI test: пользователь создаёт token; админ-состояние читается обратно. |
| **WR-04** | Один bearer-токен предъявляется **любым** чатом без требования отдельной chat identity и разрешает только scope токена. | **Explicit user**; FR-02 | Два независимых test-chat actors с одним credential имеют одинаковые grant permissions. |
| **WR-05** | Административный API поддерживает inspect/list, create/grant, amend, revoke; actor на этих действиях тоже проверяется. | **Explicit user**; FR-01/04 | Positive/negative admin tests; forbidden amend/revoke unchanged. |
| **WR-06** | Делегированное право создавать/редактировать чужие grants не возникает из обычного graph-edit token; если поддержано — строго ограничено grant ceiling. | Candidate interpretation; PR-AUTH-02 | Нет self-escalation и прав выше ceiling; root user control. |
| **WR-07** | Изменённые/отозванные права учитываются при следующем запросе, а при гонке проверки и записи — на соответствующей acceptance boundary. | FR-01/03, candidate technical contract | Revoke/amend/race tests, trace grant revision. |
| **WR-08** | Запрещённый Graph API вызов возвращает конкретный code, target/scope, missing permission и разрешённый следующий шаг, **не меняя граф**. | **Explicit user**; FR-03 | Before/after content, revision, events identical; denial response usable. |
| **WR-09** | Разделять право читать/исследовать/экспериментировать/предлагать/принимать/писать/публиковать; не устанавливать автоматически больший authority из глубины графа или «другого чата». | User chronology; N-02, SRU-02 | Permission matrix, кейсы specialist+reviewer, impact/upstream gate. |
| **WR-10** | Token/API permission отдельно от Decision Autonomy, достаточности evidence, GitHub права и прав ОС. | User chronology; FR-05 | Same actor: authorized but weak evidence → propose, not auto decide; forged `by:user` denied. |
| **WR-11** | Credential и права не являются каноническими секретными полями `graph.json`, stdout/log/UI не показывают token после безопасного первоначального получения. | Candidate sufficient security; PR-AUTH-01 | Secret-redaction tests; revocation; no stored plaintext in RDG. |
| **WR-12** | Не вводить обязательную виртуализацию/sandbox, чрезмерную ACL-DSL или контроль всех файлов вне API; честно описать границу guard. | **Explicit user preference**; FR-05 | Simple local route, no claims of raw filesystem enforcement. |
| **WR-13** | Расширить существующий QRPE-слой типами `F-P/F-R/F-U/F-O` из оригинального review-промпта, сохраняя legacy untyped. | User origin; H-PR-02; SRU-05 | Four typed fixtures; old QRPE readable, no keyword guessing. |
| **WR-14** | У Finding поддержать несколько вопросов, evidence refs, semantic target, provenance, disposition и связи с несколькими Proposal; Question не пятый тип. | User origin + review prompt | Validations for 1:N questions, M:N Finding↔Proposal, unknown evidence. |
| **WR-15** | Finding Type, proof, disposition, Proposal Status и actual execution/verified outcome не подменяют друг друга; относительные CURRENT/UPSTREAM, NOW/NEXT и Next Gate не обязаны стать хранимыми полями. | Review prompt / candidate schema decision | Tests: PR selected/committed ≠ Finding resolved; no new duplicate registry. |
| **WR-16** | Canon у Action расширяется во время исследования: новые positive/negative cases с условиями, provenance и evidence, отдельно от project facts и applicability assessments. | User origin; H-PR-03 | New canon case, scope, case history, different prepared/working graph. |
| **WR-17** | Контекст и каноны учитываются в composite R; отрицательный канон — не автоматически Problem/ban, может породить Proposal сравнения upstream/downstream compositions. | User origin; H-PR-03 | Comparison `U1+A2` vs `U2+A1` + альтернативы, no silent upstream mutation. |
| **WR-18** | Prepared graph/Lens — неполный источник; рабочий граф самостоятельно добавляет Actions/canon/Findings, не редактируя prepared source; T1 выбранного Action неизменен. | User origin; FR-06 | Prepared-source relation and T1 snapshot unaffected. |
| **WR-19** | Отдельные факты «Action выбран», «Action реализован», «R достигнута и проверена» не сливаются; R/A history сохраняется. | Action model user/handoff | Independent selection/execution/achievement test. |
| **WR-20** | Общий Graph API обеспечивает нужные CRUD/lifecycle/edge/canon/finding operations, независимо от Lens, с безопасной работой на локальном opt-in Action graph. | User request + existing pilot; SRU-04/05 | Trace operations list, negative guards, transactional read-back. |
| **WR-21** | Сохранить O/D ↔ Action semantics через совместимое чтение/адаптер и доказательства на legacy fixtures до принятия физической миграции. | Previous open decisions; FR-10 | Old ID, selected option, decision reason, T1, projection and current lifecycle preserved. |
| **WR-22** | Применять персист `(C1 OR C2) AND C3`: содержательное решение/причины или ценная декомпозиция; плюс оправданная будущая ценность против стоимости хранения/повторной работы/поддержки. | Direct user correction; H-PR-04 | No standalone C3 persistence; positive and negative scenarios. |
| **WR-23** | Lens может применяться transient в одном ответе; не требуется отдельный LensRun, archive либо writer. Долгая работа — обычный research graph. | User origin; H-PR-05/06 | Same meaningful outcomes recorded in owner graph without Lens-specific state. |
| **WR-24** | Отдельный исследовательский граф — полноценный RDG со своей root R/Actions/Findings; передача между чатами не требует Git branch. | User origin; H-PR-06 | Reopen research graph by second actor/chat and resume trace. |
| **WR-25** | Скрыть, отсоединить, архивировать и удалить — разные операции; архив можно найти адресно, без контекстной загрузки всех архивов. | User origin; H-PR-07 | Index/Viewer retrieval, hide, detach, archive, safe-delete cases. |
| **WR-26** | У материализованной смысловой записи один canonical owner; promote/associate research outcomes и shared R сохраняют ID/provenance и не создают второго независимо редактируемого owner. | Candidate/inferred; H-PR-08 | Cross-graph identity/projection/owner tests and broken-link guards. |
| **WR-27** | Полезный завершённый тест сохраняется с scope, датой, версией, коммитом/evidence даже когда не выявлена F-P/F-R/F-O; Finding не создаётся искусственно. | User origin; H-PR-09 | Verification record discoverable, no invented Finding. |
| **WR-28** | Исходный `graph.json` остаётся canonical неизменённой формы; Gendocen читает его через thin adapter/resource projection, **не требует переписать граф под `$docengine`**. | User proposal + source evidence; FR-08/09 | Input RDG byte-identical; adapter read, roots/IDs retained. |
| **WR-29** | Dependency projection адресует узлы/поля по стабильным RDG ID, не только по позициям `/nodes/5/...`, и различает существенные/несущественные поля и правила. | Candidate technical requirement; SRU-07 | Reorder nodes without spurious review; relevant field change triggers review. |
| **WR-30** | Использовать Gendocen receipts/baselines, `build_required`, `review_required/stale` и fresh semantic review context, не выдавая их за Finding, Authorization или verification of R. | Gendocen source; candidate integration | Rules/freshness tests; outdated review context refused; RDG token still required for graph write. |
| **WR-31** | Полнота dependency declaration отдельно проверяется: пропущенное фактическое основание не может считаться безопасным только из-за `valid` receipt. | Gendocen documented limitation | Changed indirect assumption triggers check in designed scenarios; unknown dependencies explicitly noted. |
| **WR-32** | Markdown генерируется как представление с абзацами/разделами и ссылками на source IDs; есть scope/version/as-of и различение generated vs hand-edited; не вторая каноническая история. | **Explicit user idea** + Gendocen materialization; FR-08 | Readable document, source trace, drift detection, no raw JSON dump requirement. |
| **WR-33** | Внешнее приложение может получить структурированное RDG-представление; его визуальный формат не диктует schema RDG. Запись обратно — отдельный guarded API и отдельный decision fork. | **Explicit user idea**; FR-08 | Read-only external consumer; no hidden write-back. |
| **WR-34** | Механизм Gendocen не изменяет граф напрямую без Graph API token, не устанавливает решения по `review_required`; runtime-owned dependency metadata не копирует всю RDG semantic truth. | FR-03/09; PR-DEP-01 | Separation of receipts and graph events, review cycle and deny tests. |
| **WR-35** | Local multi-graph package guards / recovery, remote concurrency and index consistency обеспечивают различение partial writes и устойчивый read-back. | Existing RDG architecture; SRU-09 | Failure injection, recovery, SHA/ref races, no false atomicity claims. |
| **WR-36** | GitHub canonical repo/branch/writer выбираются до live work-graph writes; `forfiles` reading copy не превращается в owner. | Handoff + explicit governance | No side-effect remote writes before approval; discovered owner recorded. |
| **WR-37** | Helper умеет управлять токенами и пользоваться Graph API; Viewer показывает Action/Findings/архив/links/представления; source build ≠ установленный браузер. | User direction + project docs; SRU-03/10 | Isolated browser, separate installed user acceptance, without unsupported claims. |
| **WR-38** | До замены старых stable/protected/Lens archive/O-D writer доказать, что новая композиция покрывает legacy, и оценить migration/retirement как отдельный PR. | Previous handoff; FR-10 | Negative/legacy tests, no deletions without approved scope. |
| **WR-39** | Для каждого material изменения выполнены diff, focused tests, relevant full regression, read-back и независимая оценка пользовательского пути. | Operational constraints + current pre-work method | Reports distinguish observed, passed, not run, installed, pushed, committed. |
| **WR-40** | Перед использованием Gendocen в коде оценить совместимость runtime/root/layout, доверие к выполняемому project Python, зависимости/лицензию и стоимость поддержки. | Source facts, candidate necessary check | Isolated experiment and distribution gate; no unstated legal rights. |

**Дополнение v3 — новые Work Requirements для утверждённых пользовательских границ и условной реализации Temporal Plan.** Эти WR принадлежат Candidate Composition до отдельного commit; происхождение «direct user» не превращает конкретную техническую схему в committed PR.

| WR | Проверяемый критерий результата | Provenance / trace | Verification |
|---|---|---|---|
| **WR-41** | `graph.create` создаёт graph только с кандидатами; packaged create с `Action.selected` или legacy `Decision.committed` не превращает creation scope в право выбора. | **Прямое user decision**, FR-14; R-RDG-PILOT/F-P-RV-01 | Positive empty candidate create; negative embedded selected/committed + byte-exact no write. |
| **WR-42** | `Action.selected` — результат отдельной проверяемой операции и полномочия; чат с правом разрабатывать варианты, каноны, Findings не может выбрать Action; предпочтение и `preselected` не записываются. | **Прямое user direction**, FR-14 | Two-actor limited/reviewer-select flow, denied hidden routes, T1 receipt; no preselected node/status. |
| **WR-43** | Если grant отозван **до фиксации транзакции**, writer не публикует её; admin revoke и writer имеют определённый согласованный commit boundary, включая recovery/replay. | **Прямое user decision**, FR-15; F-P-RV-02 | Deterministic revoke-in-flight, concurrent processes, crash injection, unchanged before commit. |
| **WR-44** | Чат предъявляет bearer **без отдельного HMAC issuer secret**; Graph API проверяет права и создаёт необходимое внутреннее техническое доказательство, не выдавая его за личность пользователя. | **Прямое user decision**, FR-15; F-U-RV-01 | Material Action selection with bearer-only client, internal trust provenance, forbidden self-approval. |
| **WR-45** | Plan — самостоятельный версионный temporal owner, **не** набор полей `preselected` на RDG Action и не просто сценарная Markdown-проекция. | **Прямое user requirement**, FR-11 | Synthetic Plan identity/persistence fixture; RDG Action byte-identical при добавлении Plan. |
| **WR-46** | Plan представляет относительное/абсолютное время, сроки, временные окна и предшествование, не придумывая дату там, где задана только зависимость/событие. | User semantic direction + inferred minimal precision; FR-11 | Time-window/after-event/no-date cases; deadline classification. |
| **WR-47** | Plan может содержать условные ветви, незавершённый выбор между будущими путями и возможные/запланированные действия, отличая их от наступивших событий. | **Direct user**, FR-11/12 | Two-branch trigger fixture: hypothetical branch ≠ actual event, abandoned alternative preserved for review. |
| **WR-48** | Plan ссылается на существующие RDG Actions/R/C по стабильной идентичности/owner/revision, не копирует их как второго semantic owner и не принимает Action ссылкой. | **Direct user** + existing FR-06/10; FR-12 | Same Action referenced by two branches, owner/cross-graph mismatch rejected, no selected on Plan change. |
| **WR-49** | RDG может оценивать Canon/Finding относительно Plan, его срока, состояния и конкретной ветви; соблюдать статус hard/soft/hypothetical deadline и source provenance. | **Direct user**, FR-13 | Plan-based F-R/F-U/F-O scenario with derived assumptions; no F-P solely from hypothetical missed deadline. |
| **WR-50** | При изменении Plan сроков/условий и RDG Canon/Action есть адресные сигналы пересмотра; Gendocen не переписывает решения/Plan сам и не притворяется полной доказанностью. | FR-09/13 + candidate adapter strategy | Field-level invalidation RDG↔Plan, irrelevant-change no-recheck, stale review refused. |
| **WR-51** | Право изменять Plan отделено от права принимать RDG Action, подтверждать фактическое событие и разрешать исполнение; AI authoring не создаёт authoritative event by string. | **Direct user delegation principle** + inferred FR-12/14 | Matrix Plan write/branch/event vs Action.select; negative attempts, no partial writes. |
| **WR-52** | Временное перепланирование не переписывает historical T1 выбранного Action, фактические события и предыдущие временные baselines; planned ≠ performed ≠ verified. | Existing FR-06/07 + new FR-11/12 | Before/after history/temporal-as-of, revise events, no silent retroactive changes. |
| **WR-53** | Plan доступен для чтения/передачи между чатами и позже для timeline/branch представлений, но не требует автоматического execution engine в первой версии. | User direction + work proportionality | Second-reader scenario, projection provenance, no scheduler side effects. |



## 7. Error Axes (EA) — потенциальные пути ошибочного результата

*EA — планируемая ось проверки, не утверждение о найденном дефекте. Значимые риски при необходимости связаны с F-R ниже.*

| EA | Механизм → возможное следствие | Связанные WR / planned verification |
|---|---|---|
| **EA-01** | Helper выдаёт token, но API не проверяет актуальные права → ложная «авторизация». | WR-03..08; allowed/denied before/after. |
| **EA-02** | Любой bearer-токен автоматически считается реальной личностью пользователя или higher-authority chat → необоснованный commit. | WR-04/09/10; credential attribution != identity/Decision Autonomy. |
| **EA-03** | Обычный editor token позволяет создать административный token с большими правами → эскалация. | WR-05/06; negative delegated grant, ceiling. |
| **EA-04** | Изменённый или отозванный grant остаётся действительным в cache/между проверкой и commit → запрещённая запись. | WR-07; race/fresh policy read. |
| **EA-05** | API сначала частично меняет граф, потом отказывает → нарушение целостности/прав. | WR-08/20/35; snapshot/hash before-after denied. |
| **EA-06** | Токен попадает в граф, ошибку, журнал либо исходники → третье лицо получает полномочия. | WR-11; log redact, token storage, revoke. |
| **EA-07** | Ограничение только `edit_node`, но не `add_edge`/`reparent`/`select_action` → обход семантического scope. | WR-09/20; full mutation path matrix. |
| **EA-08** | Права на эксперимент ошибочно трактуются как права на deployment / network / GitHub push. | WR-09/10/36; external operations separately gated. |
| **EA-09** | Старая QRPE автоматически классифицируется как Problem по слову → ложный F-P и потеря исторического смысла. | WR-13..15; legacy unknown type. |
| **EA-10** | Коммит Proposal автоматически закрывает Finding либо считается выполнением Action → ложное `resolved`. | WR-15/19; independent lifecycles. |
| **EA-11** | Новый отрицательный canon-case автоматически блокирует Action, отменяет upstream либо переписывает T1. | WR-16..18; provenance/history/original selection snapshot. |
| **EA-12** | Подготовленный граф превращается в закрытый каталог вариантов → потеря лучшей `U2+A1` композиции. | WR-17/18; new discovered cases and alternatives. |
| **EA-13** | Legacy O/D заменяют массово на Action без сохранения ID, decision reason и связей → повреждение старых данных. | WR-19/21/38; adapter tests, migration gate. |
| **EA-14** | Исследовательский и основной граф независимо редактируют одну Finding → расхождение доказательств/статуса. | WR-24/26; single owner/promotion tests. |
| **EA-15** | Архивирование/скрытие теряет обязательную ссылку или делает evidence недоступным → повторная работа и ложный вывод. | WR-25..27; lazy search, link integrity. |
| **EA-16** | Gendocen ожидает `$docengine` envelope, а RDG graph передан напрямую → интеграция не запускается; навязанная rewrite schema повреждает RDG. | WR-28/40; adapter no-change source. |
| **EA-17** | Указатель `/nodes/5/...` меняется после reorder → ложная инвалидация или привязка к чужому Action. | WR-29; ID-indexed projection comparison. |
| **EA-18** | Значимая непрямая предпосылка не зарегистрирована в Gendocen → stale semantic вывод выглядит `valid`. | WR-29/31; targeted semantic coverage and counterexample. |
| **EA-19** | `review_required` автоматически создаёт F-P либо `still-valid` считается пользовательским approval Action → смешение механического и семантического состояния. | WR-30/34; distinct status transitions. |
| **EA-20** | Просроченный review packet подтверждается после изменения источника; `review_context_id` ошибочно принимается за auth token. | WR-07/30/34; stale context and separate credential tests. |
| **EA-21** | Gendocen project Python запускается как «безопасное правило», хотя имеет побочные эффекты → неожиданные записи/доступы. | WR-40; trust preflight, isolated code execution. |
| **EA-22** | Markdown экспорт воспринимается как editable semantic owner и его ручная правка тихо перезаписывает RDG. | WR-32/33; generated drift/round-trip gating. |
| **EA-23** | Представление строится из устаревшего graph revision или смешивает независимые `identitySpace` → неправильный документ/Viewer. | WR-25/28/32/37; provenance and full-source guards. |
| **EA-24** | GitHub Contents сохраняет первый из нескольких файлов, затем сбой → архив невидим, связи/индекс расходятся. | WR-26/35/36; fail-point and recovery test. |
| **EA-25** | Реализованный в Repo код объявлен установленным в Helper/Windows или опубликованным GitHub без проверки. | WR-37/39; separate local/source/installed/published evidence. |
| **EA-26** | Удаление прежнего Lens archive/`protected` до proof of coverage → silent regression. | WR-22/23/38; legacy features compatibility run. |
| **EA-27** | Слишком большой mandatory ACL/metadata/сохранение LensRun ради гипотез → трудоёмкость и контекстный шум превышают пользу. | N-03, WR-12/22/23; minimum-sufficient alternative. |

**Положительные и дополнительные planned review axes, не дублируемые в EA:** работа реального Helper flow в пределах 2–3 естественных кликов; понимание chat actor scope без персональной идентификации; полнота источников и provenance review; успешный (без Finding) результат проверки; устойчивость отношений owner при архивировании; естественность Markdown с абзацами; истинность получаемой инвалидации; разграничение view и execution; покрытие сценариев S-AUTH/S-WORK/S-DEP-REP; цена обслуживания второго runtime, регрессия и наблюдаемый пользовательский outcome. После будущей реализации дополнить осями из фактического diff и вызовов API. Не утверждать уже пройденные тесты.

**Дополнение v3 — дополнительные возможные механизмы ошибок (candidate EA, не доказанные Problems).**

| EA | Механизм → возможное нежелательное следствие | Связь и проверка |
|---|---|---|
| **EA-28** | `graph.create` с precommitted/selected payload или вложенная Graph API операция обходят отдельное право принятия Action. | WR-41/42; allow/deny nested create, selection, legacy fixtures; review F-P-RV-01 — уже воспроизведённый частный случай. |
| **EA-29** | Отзыв между policy read и durable commit, либо recovery ранее подготовленной транзакции, публикует уже запрещённое изменение. | WR-43; concurrent revoke/commit/fault injection, review F-P-RV-02. |
| **EA-30** | Плановая ссылка на candidate A ошибочно превращает её в `selected` или обязательное выполнение, либо preference ошибочно требует `preselected`. | WR-42/47/48; status/history diff, not-selected branch. |
| **EA-31** | Условное/будущее событие отображается как фактически произошедшее; выбранная ветвь смешивается с альтернативой, неверные Findings. | WR-46/47/49; source status/time/provenance cases. |
| **EA-32** | Relative deadline или timezone конвертированы в выдуманную абсолютную дату, либо soft/candidate deadline объявлен hard FR. | WR-46/49; temporal cases, exact as-of, deadline provenance. |
| **EA-33** | Копия Action/Canon в Plan редактируется независимо, теряет owner/ID/revision и ломает cross-graph смысл. | WR-48/52; stable reference and broken link tests. |
| **EA-34** | Внесение нового срока в Plan без переоценки Canon/Finding приводит к устаревшему выбору; или технический сигнал Gendocen молча создаёт F-P/выбирает Action. | WR-49/50; material vs irrelevant dependency changes, no automatic decision. |
| **EA-35** | Токен Plan editor позволяет выбрать RDG Action или подтвердить реальное событие без отдельного права. | WR-42/51; role/operation matrix, denied unchanged. |
| **EA-36** | Полная temporal workflow/scheduler или persistent per-event archive преждевременно усложняет первую версию и создаёт конкурирующую систему истины. | WR-45/53, PR-PLAN-01/03; minimal proof first, lifecycle delta. |



## 8. Findings, независимое review и upstream feedback

### 8.1. Подтверждённые результаты независимого Final Review после исполнения v2

**Это source references чужого Final Review v1, не новые Findings этой Candidate Pre-work.** Полные canonical записи и reproduction остаются в [R-RDG-PILOT-20261018/v1](https://github.com/AlexPastukhh/forfiles/blob/main/artifacts/2026-10-18/review-rdg-authority-gendocen-pilot-20261018-v1.md). Ни одна проблема не считается устранённой одним решением пользователя.

| Review Finding | Реально установленное / статус | Следующая работа |
|---|---|---|
| **F-P-RV-01** | `graph.create` только с правом создания способен записать legacy `Decision.committed`; **unresolved**. | **Прямое пользовательское решение принято:** creation ≠ selection, nested historic accepted import отдельно. Реализовать и протестировать. |
| **F-P-RV-02** | Revoke между `prepare()` и commit не блокирует запись; **unresolved**. | **Решение принято:** если grant отозван до commit, публикации нет. Согласовать locks/check/recovery и доказать. |
| **F-P-RV-03** | Новый тест authority CLI не проходит writer integration; **unresolved**. | Повторяемый интеграционный harness для scope, semantic selection, in-flight revoke, denied unchanged. |
| **F-P-RV-04** | Отказ указывает missing operation, но не всегда target graph/scope; **unresolved**. | Структурированный отказ без leakage. |
| **F-R-RV-01** | Legacy opt-in fail-open способен остаться включённым при ошибочном rollout; **deferred до production gate**. | Явный protected-mode startup validation, keep legacy lane separated. |
| **F-R-RV-02** | Gendocen projection использует одинаковый resource ID; raw source SHA меняется при reorder; **unresolved risk** (полный runtime не был подтверждён). | Unique Plan/RDG resource naming, field-level tracking, runtime test. |
| **F-U-RV-01** | Bearer vs HMAC для material Action. **Пользователь решил внешний интерфейс:** токен достаточен, техническое подтверждение формирует API. **Implementation fork** internal receipt/legacy compatibility ещё исследовать. | Реализовать trusted API, не выдавая issuer key чату; тестировать. |
| **F-U-RV-02** | Creation vs import already-selected state. **Пользователь решил:** `graph.create` создаёт кандидатов, не принятые решения. | Специальный, полномочный исторический импорт — отдельный candidate API. |

**Новое архитектурное направление v3 — Temporal Plan:** не является доказательством дефекта уже выполненного stage 1A/B, поскольку пользователь уточнил отдельный временной Plan позднее. Для него необходимы новые WR/EA/SRU/PR и синтетические тесты.

### 8.2. Исторические candidate Findings pre-work v2

Ниже — **сохранённые исходные candidate findings pre-work v2**, зафиксированные до начала разработки. Их утверждения о стадии «продукт ещё не менялся» относятся только к историческому моменту v2, **не описывают новое фактическое состояние**. F-IDs ниже — внутри pre-work; F-P-RV-IDs выше — из отдельного Final Review, без переименования и дублирования owner.

| ID/type/target/level | Конкретная ситуация и последствия | Disposition; Intervention / User Review | Next Gate; PR и Autonomy |
|---|---|---|---|
| **F-U-01** · Decision Uncertainty · trusted token issuer · **UPSTREAM** | Пользователь определён как исходный управляющий полномочиями через Helper; **не определён проверяемый механизм**, которым Helper подтверждает именно санкционированную пользователем выдачу, если чат может вызвать admin API. A: локальный доверенный user-only control; B: authenticated admin service/owner credential. Это не повтор старого вопроса «A или B — кто владелец»: **он уже решён пользователем**. Разные способы различаются надёжностью, размещением и сложностью. | unresolved; **NEXT / HIGH** | Partially blocking реальный trust bootstrap, **не** моковый тест; исследовать существующий Helper/backend и выбрать simplest sufficient. `PR-AUTH-01/02/03`, Autonomy **MEDIUM** для техники, **USER_REQUIRED** если требуется новая trust boundary. |
| **F-R-01** · Risk · bearer token handling · **CURRENT** | Если токен вставляется в несколько чатов или в логи, любое его раскрытие даст указанное право третьему лицу. Это механизм риска, **не подтверждённая утечка**. | unresolved; **NEXT / HIGH** | До выдачи реальных токенов минимально проверить случайность, ограничение scope, redaction, amend/revoke. `PR-AUTH-01/02`, Autonomy HIGH для технических мер. |
| **F-U-02** · Decision Uncertainty · token state and distribution · **CURRENT** | Stateful opaque token с lookup и мгновенным отзывом проще для управляемых прав; self-contained signed token проще проверить автономно, но для amend/revoke нужен дополнительный механизм. Выбор влияет на Helper, хранение и guard. | unresolved; **NEXT / NORMAL** | В validation slice проверить stateful как preferred, не делать его FR; альтернативу сохранить. `PR-AUTH-01` vs `PR-AUTH-01B`, Autonomy MEDIUM. |
| **F-U-03** · Decision Uncertainty · Finding schema/legacy · **UPSTREAM** | Расширять прежний `qrpe[]` как записи с полями `type/questions/evidenceRefs/proposalRefs` или вводить общий reusable Finding record с projection к R/A? Два независимых активных реестра недопустимы; точная schema/ID migration пока не проверена на разных версиях. | unresolved; **NEXT / HIGH** | Partially blocking writer/schema change; провести sample conversion без потери origin/status. `PR-SEM-01`, Autonomy MEDIUM. |
| **F-R-02** · Risk · Change/authority paths · **CURRENT** | Операция canonic material edit может идти через R edit, edge, new child, action selection, cross-graph promotion; частичный guard только для одного пути даст обход. Старый pilot уже исправлял некоторые protected-parent paths, но новая token matrix не проверена. | unresolved; **NEXT / HIGH** | Full operation inventory + negative tests до пользовательского применения. `PR-AUTH-03/SEM-04`, Autonomy HIGH. |
| **F-U-04** · Decision Uncertainty · ownership of promoted graph objects · **UPSTREAM** | Исследование выявило Finding с evidence, которая должна влиять на основной Action. A: переносить владельца в main с историческим origin-link; B: сохранять owner в research graph и давать ссылку из main. Результат должен обновляться в одном месте, но выбор влияет на архивирование/удаление. | unresolved; **NEXT / HIGH** | Partially blocking cross-graph writes and delete; сравнить оба сценария и stable identity. `PR-WORK-02`, Autonomy MEDIUM. |
| **F-U-05** · Decision Uncertainty · GitHub graph owner · **UPSTREAM** | Не выбраны действительные repo, branch, writer principal для канонического рабочего состояния, включая multi-file commit. `forfiles` — reading copy. Влияние: нельзя приравнять экспериментальный single-file Contents API к безопасной публикации всего графа. | unresolved; **LATER** для local proof / **HIGH** | **Blocking real remote writes**. Пользователь выбирает destination/permissions при достижении этого gate. `PR-PERSIST-01/02`, Autonomy USER_REQUIRED по настоящему хранилищу. |
| **F-R-03** · Risk · multi-file updates · **CURRENT** | При sequential Contents PUT или необнаруженном сбое может сохраниться граф без index/metadata или развалиться межфайловая связь; это особенно опасно для promotion/archive. | unresolved; **NEXT** перед GitHub / HIGH | Check remote transaction options + injection/recovery; не распространять локальный recoverability claim на GitHub. `PR-PERSIST-01`, Autonomy HIGH для протокола при выбранном backend. |
| **F-U-06** · Decision Uncertainty · O/D vs Action · **CURRENT** | Немедленно физически мигрировать legacy Option+Decision к Action либо сначала построить точный read-only adapter? Массовая миграция увеличивает риск нарушения исторического T1 и viewer links. | unresolved; **LATER / HIGH** при миграции | Пока выбрать staged read adapter, reassess after evidence. `PR-SEM-05`, Autonomy MEDIUM; физическая миграция отдельный USER_REQUIRED impact gate. |
| **F-U-07** · Decision Uncertainty · Gendocen integration contract · **CURRENT** | Gendocen сейчас требует managed structured envelope `$docengine`+`data`; RDG — другой top-level JSON. A: временная ID-indexed projection/mirror без source writes; B: native ResourceAdapter. Выбор меняет объём работ/стоимость поддержки. | unresolved; **NEXT / NORMAL** | Validation test обоих или первого достаточного пути; не менять RDG graph format. `PR-DEP-01`, Autonomy HIGH для экспериментальной техники. |
| **F-R-04** · Risk · incomplete semantic dependencies · **CURRENT** | Если регистрация зависимостей основана только на явных структурных edge и не включает фактические критерии/дальние предпосылки, `valid` может ошибочно выглядеть достаточной гарантией актуальности. | unresolved; **NEXT / HIGH** | Counterexample с indirect source, dependency-coverage checklist, explicit residual uncertainty. `PR-DEP-01/02`, Autonomy HIGH для проверки. |
| **F-U-08** · Decision Uncertainty · Markdown write-back · **CURRENT** | Пользователь запросил возможность представления графа Markdown и внешнему приложению, **но не требовал двустороннего редактирования Markdown**. A: read-only generated representation; B: editable Markdown и обратная синхронизация, с конфликтами и ID mapping. Второй существенно дороже и меняет ownership. | unresolved; **LATER / NORMAL** | Не блокирует read-only representation; запросить решение только если действительно понадобится round-trip. `PR-REP-01` vs `PR-REP-03`, Autonomy USER_REQUIRED на изменение пользовательского процесса. |
| **F-O-01** · Improvement Opportunity · staged validation · **CURRENT** | Допустимо было бы сразу переписать writer/UI и делать свой dependency evaluator, но два узких validation slices через существующие API/Gendocen дают раньше evidence и уменьшают risk rework. Есть дополнительный тестовый gate, но он оправдан возможностью отказаться от неверной архитектуры. | unresolved; **NEXT / NORMAL** | Выбрать staged route; измерить integration friction до расширения. `PR-ROUTE-01`, Autonomy HIGH. |
| **F-R-05** · Risk · scope/compatibility retire · **CURRENT** | Если удалить старый Lens archive / stable/protected или поменять v7 storage только потому, что новый дизайн удобнее, часть legacy сценариев может сломаться. | unresolved; **LATER / NORMAL** | Compatibility test + explicit deprecation Proposal after replacement. `PR-ROUTE-02`, Autonomy MEDIUM. |

**Дополнительные Material Questions, не отдельные Finding types:**

- **Q-AUTH-01** (F-U-01, *partially blocking real admin writes*): как Helper подтверждает исходного пользователя? Закрывается анализом фактического доверенного API/локального хранилища и, если надо, санкционированным пользовательским действием. Уже известно **кто** управляет: пользователь. Не спрашивать об этом снова.
- **Q-AUTH-02** (F-U-02, *non-blocking mock*): какие scope по умолчанию даёт токен — проекты/графы/типы операций; как Helper показывает ограничения, не требуя длинного setup? Закрывается прототипом сценария и UX review; точное пользовательское preference спрашивать, только если trade-off останется.
- **Q-FIND-01** (F-U-03, *partially blocking migration*): есть ли в legacy QRPE поля/состояния, которые нельзя честно отобразить в 4 типа? Закрывается чтением fixtures и conversion tests; отсутствие type ≠ Problem.
- **Q-WORK-01** (F-U-04, *partially blocking promotion/archive*): владелец material shared Finding после move или link; что происходит при удалении исходной research graph? Закрывается ownership contract и tests.
- **Q-GIT-01** (F-U-05, *blocking live remote*): где и от чьего имени canonical graph writer? Закрывается конкретным решением пользователя **только перед** live remote.
- **Q-DEP-01** (F-U-07, *non-blocking semantic development*): нужен ли native adapter или достаточно controlled projection, кто владеет runtime receipts, как Gendocen получает свежую версию graph.json? Закрывается минимальным benchmark/test.
- **Q-REP-01** (F-U-08, *non-blocking read view*): требуется ли когда-либо двухсторонняя Markdown синхронизация, или только дополнительные представления? Пользователь этого пока не требовал.
- **Q-PERSIST-01** (*non-blocking now*): какой минимум метаданных оставлять у основного Action после archived valuable research — hidden anchor или только адресный index? Предварительно candidate: hidden anchor для существенного вклада, каталог для прочего; подтвердить после experience.
- **Q-DEP-02** (*non-blocking*): требуется ли специальная долговременная запись результатов Gendocen, если RDG уже хранит проверенную суть? Сначала использовать dependency receipts как техническое состояние, не копировать semantic owner.

**Evidence Gaps / ограничения проверки:** не подтверждён принятый полный DRLD новой функции и состояние установленного Windows Helper/Viewer; нет актуального global diff/status настоящего Git tree и разрешений на live cutover; интеграция Gendocen↔RDG не выполнялась; нет baseline по времени/ресурсам/дедлайнам; неизвестны точные лицензирование Gendocen и права его включения в дистрибутив; полнота существующих API mutation paths не подтверждена новым full audit. Эти пробелы **не объявлены Problems**. Файлы и комментарии из 2026-10-17 являются ограниченным срезом, не автоматически актуальным production состоянием.

## 9. Proposals — Candidate решения и альтернатива

Status всех перечисленных новых PR — **pending**, `origin` и Autonomy явно указаны. User-origin proposal не становится committed только из-за происхождения. ID локальны этой версии, старые H-PR и PR v1 не теряются — трассировка в §10.

| PR (origin / autonomy) | Изменение и причина | Trade-off, статус / relations |
|---|---|---|
| **PR-AUTH-01** (assistant по explicit user, MEDIUM) | Stateful opaque bearer token: scope, operation set, optional expiry, grant ID, mutable authority policy; секрет показывается при выдаче, затем проверка на серверной стороне; отзыв/изменение немедленно влияет на дальнейшие записи. | Дополнительное token/policy storage против удобного revoke и amendment. **pending**, `ALTERNATIVE_TO PR-AUTH-01B`; `REQUIRES PR-AUTH-02` для полного сценария. |
| **PR-AUTH-01B** (assistant alternative, MEDIUM) | Самодостаточный подписанный bearer token с ограниченным сроком жизни + revocation mechanism. | Меньше lookup, но более сложное изменение полномочий и revoke. **pending**, excluded из preferred до evidence. |
| **PR-AUTH-02** (assistant по explicit user, MEDIUM) | Admin API: issue, inspect/list, amend, revoke, effective-permissions/explain; user issuance via Helper, delegated admin только при явно выданном административном праве и grant ceiling. | Нужен user trust bootstrap; **pending**, `REQUIRES PR-AUTH-01 или PR-AUTH-01B`; `RECOMMENDED_WITH PR-AUTH-04`. |
| **PR-AUTH-03** (assistant по explicit user, HIGH) | Единственный Graph API authorization guard для всех material mutation paths; `DENIED` содержит scope/reason/request hint **до** записи; graph revision и история не изменены. | Не гарантирует запрет намеренных вне-API filesystem writes; именно такую границу хотел пользователь. **pending**, `REQUIRES PR-AUTH-01/01B + effective policy`. |
| **PR-AUTH-04** (user requirement → assistant design, MEDIUM) | Helper UI для выдачи, amendment, revocation и обзора grants; минимальный trusted owner control. | UI/credential UX; no implicit root trust from `by:user`. **pending**, `RECOMMENDED_WITH PR-AUTH-02/03`. |
| **PR-SEM-01** (user/review, MEDIUM) | Эволюция существующего QRPE в typed Findings (F-P/R/U/O), questions[], evidence, disposition и PR refs, без параллельного глобального канонического реестра. | Schema/compatibility; **pending**, `RECOMMENDED_WITH PR-SEM-04`. |
| **PR-SEM-02** (user, HIGH) | Открытые Canon cases и обычные API операции расширения с provenance; prepared source не ограничивает новые рабочие варианты; T1 immutable. | Нужен точный event contract; **pending**, `RECOMMENDED_WITH PR-SEM-03`. |
| **PR-SEM-03** (user, MEDIUM) | Отрицательный канон может запускать исследование upstream/downstream compositions; Finding/Proposal без автоматического отмены принятого U1. | Более широкий поиск стоит времени, ограничивать материальностью; **pending**. |
| **PR-SEM-04** (assistant по user model, MEDIUM) | Продолжить универсальный Graph API через existing package writer для Action/R/Context/Findings/Canon/links с разделёнными правами и сохранением T1. | Больше edge cases, но нет Lens-specific writer; **pending**, `REQUIRES PR-AUTH-03` для enforced mutations. |
| **PR-SEM-05** (assistant, MEDIUM) | Read-only O/D→Action compatibility adapter и targeted cases перед отдельным обсуждением физической миграции. | Temporary dual-model mapping, меньше риска history loss; **pending**, physical bulk migration **не включена**. |
| **PR-WORK-01** (user, MEDIUM) | Самостоятельные полные RDG research graphs для длительной/многочатовой работы, не LensRun и не обязательная Git branch. | Новые вопросы индекса/доступа; **pending**, `RECOMMENDED_WITH PR-WORK-02/03`. |
| **PR-WORK-02** (user+assistant, MEDIUM) | Shared record identity/one active canonical owner, promote or associate material R/A/Canon/Findings/evidence; оставлять проверяемое происхождение. | Нужно решить move vs link по use-case; **pending**, `RECOMMENDED_WITH PR-WORK-01/03`. |
| **PR-WORK-03** (user+assistant, MEDIUM) | Hide/detach/archive/delete как разные операции, AI lazy retrieval и Viewer toggle, broken link deletion guard. | Metadata/index maintenance; **pending**, `REQUIRES stable identity/owner contract`. |
| **PR-WORK-04** (user, HIGH) | Персист `(C1∨C2)∧C3`, значимая проверка без Finding, transient Lens; не сохранять per-run Lens archive как обязательную возможность. | Требует negative retention case; **pending**, `RECOMMENDED_WITH PR-WORK-01`. |
| **PR-DEP-01** (user origin + assistant implementation, MEDIUM) | Подключить **имеющийся Gendocen** к исходному RDG `graph.json` через read-only адаптер/projection; dependency receipts/rules сохраняются в Gendocen state, а RDG — canonical. | Runtime/config integration и trusted Python; **pending**, `RECOMMENDED_WITH PR-DEP-02/REP-01`. |
| **PR-DEP-02** (assistant, HIGH) | Stable-ID, fine-grained dependency mapping для Canon/Context/Action/Findings; invalidation semantics, baseline/receipt freshness и explicit coverage checks. | Нужно регистрировать реальные предпосылки — движок не выводит их полностью сам; **pending**. |
| **PR-DEP-03** (assistant alternative, MEDIUM) | Переписать свой RDG-specific dependency runtime, не использовать Gendocen. | Меньше внешних зависимостей, но дублируется уже имеющаяся существенная функция; **pending**, **not preferred / alternative to PR-DEP-01**, возвращаться только при доказанной несовместимости/цене. |
| **PR-REP-01** (user, HIGH) | Человекочитаемый Markdown с абзацами/разделами по R/A/Findings, selective views, source IDs/revision/as-of; generated/read-only по умолчанию. | Materialization templates; **pending**, `RECOMMENDED_WITH PR-DEP-01`. |
| **PR-REP-02** (user, HIGH) | Структурированный read-only consumer API/adapter для других приложений и их собственных визуализаций; Viewer — лишь один consumer. | Нужен versioned representation contract; **pending**. |
| **PR-REP-03** (assistant conditional, USER_REQUIRED) | Двустороннее изменение сгенерированного Markdown с обратным маппингом в RDG API. | Сложные merge/ownership/conflict и риск двойного owner; **pending и EXCLUDED**, не было explicit user request. |
| **PR-PERSIST-01** (previous pilot+assistant, MEDIUM) | Использовать локальный package writer/index/recovery; для GitHub проверить согласованный multi-file commit + branch/ref CAS, rollback/recovery semantics до cutover. | Отдельный remote протокол; **pending**, `REQUIRES user choice canonical owner before remote`. |
| **PR-PERSIST-02** (previous plan, USER_REQUIRED) | Выбрать canonical work-graph GitHub repo/branch/actor при подготовке remote deployment, **не `forfiles` по умолчанию**. | Потребуется решение пользователя; **pending**, future gate. |
| **PR-ROUTE-01** (assistant, HIGH) | Два коротких validation-first experiments (Authority + Gendocen projection), затем связанный семантический и межграфовый pilot без изменения пользовательских данных. | Добавляет ранние gates, но снижает expensive rework; **pending**. |
| **PR-ROUTE-02** (assistant, MEDIUM) | Legacy `stable/protected`, Lens archive, O/D migration и старые snapshot-коды deprecate/remove **только после** теста покрытия и отдельного принятия. | Сохранение временного legacy complexity; **pending**, not a deletion approval. |

**Почему не все PR являются одним atomic commit:** реализация полной системы зависит от новых evidence в staged experiments и от будущих решений GitHub owner/migration. Нельзя коммитить **условную** remote/cleanup работу одновременно с ранним локальным экспериментом. Но **внутри** конкретного принятого этапа связанные hard dependencies должны приниматься совместно; rollback/verification plan — отдельный маршрут исполнения, не подмена статуса композиции.

### 9.1. Новые Candidate Proposals v3 — Temporal Plan и принятые направления Authority

**Статус всех новых PR-PLAN — pending.** Источник самой нужды Temporal Plan — пользователь; указанный формат данных/операций — кандидатные технические способы (от assistant). Пользователь определил **поведение**, но не commit всей SRU composition.

| Proposal / origin / autonomy | Смысл и relations | Trade-off / status |
|---|---|---|
| **PR-PLAN-01** · user requirement → assistant design / MEDIUM | Самостоятельная Plan entity с versioned temporal data: steps/events, cause/trigger, dependencies, time windows/deadlines, hypothetical branches, event provenance; BUNDLE `PG-PLAN`. | Позволяет моделировать будущее без новых Action statuses; потребуется Plan owner/schema. **pending**. |
| **PR-PLAN-02** · user+assistant / MEDIUM | Строго квалифицированные ссылки Plan→RDG R/A/C; контекстная обратная оценка Canon/Findings/рисков сроков по branch/time, без silent graph mutation. `REQUIRES PR-PLAN-01`; `RECOMMENDED_WITH PR-DEP-02`. | Два связанные, но разные владельца; reference/version freshness усложняет интеграцию. **pending**. |
| **PR-PLAN-03** · assistant / HIGH | Минимальный validation-first slice: read-only Plan с 2 ветвями, event trigger, относительным/абсолютным deadline и 2 RDG Action refs; **без** общего scheduler/executor/автокоммита. `RECOMMENDED_WITH PR-PLAN-01/02`. | Быстрое evidence до дорогих temporal функций. **pending**. |
| **PR-PLAN-04** · assistant / MEDIUM | Раздельные write permissions Plan authoring / actual-event attest / RDG Action.select, guarded Plan API, immutable factual event history, condition/evaluation invalidation. `REQUIRES PR-AUTH-03 + PR-PLAN-01`. | Ограничивает скрытое принятие решения, требует совместимых lock semantics. **pending**. |
| **PR-PLAN-05** · assistant conditional / LOW | Timeline/branch view/export Plan для Viewer/внешних consumers с provenance/timezone, read-only by default. `REQUIRES PR-PLAN-01`; `RECOMMENDED_WITH PR-REP-01/02`. | Полезно для пользователя, но не должно блокировать создание модели Plan. **pending**. |
| **PR-PLAN-06** · assistant alternative / USER_REQUIRED | Поздний **опциональный** автоматический executor/scheduler условных ветвей. `ALTERNATIVE_TO initial read-only/non-executing PR-PLAN-03` при расширении обещанного outcome; **excluded from v3 first slice**. | Отдельный authorization/infrastructure/safety/product decision, преждевременная сложность. **pending, not selected**. |

**Связь с PR исходного review:** `PR-RV-01/06A` соответствует теперь явному user constraint `graph.create` без принятого D; `PR-RV-02A` отражает user constraint «revoke before commit»; `PR-RV-08A` отражает bearer-only client с внутренним trusted receipt. Это **selected semantic directions by user**, но исходные PR-RV остаются **не исполненными/не verified resolved** и не копируются в этот документ как новые canonical записи. `PR-RV-03/04/05/07` являются **pending** техническими шагами. Альтернативы `PR-RV-02B` (in-flight allowed), `PR-RV-06B` (graph.create imports accepted), `PR-RV-08B` (second client HMAC credential) **не соответствуют последним пользовательским решениям** в предложенном первоначальном виде; сохранить в истории review, но **исключить из рекомендуемого исполнения v3**, не переписывая их historical status задним числом.

**Атрибут выбора:** пользователь уже установил `Action.selected` = реально принято, а не предварительное preference; отказываться от графового `preselected`. Это не новый Proposal на создание статуса. Дополнительные флаги принятия и автосокрытие вариантов в canonical JSON не нужны; Viewer может скрывать невыбранные варианты **лишь в проекции**, не удаляя history/альтернативы.


## 10. Cross-finding Candidate Composition, отношения и происхождение

### 10.1. Группы и реальные зависимости

| PG / тип | Included и зависимость | Граница принятия |
|---|---|---|
| **PG-AUTH · HARD_BUNDLE** | `PR-AUTH-01 + PR-AUTH-02 + PR-AUTH-03 + PR-AUTH-04` для **полного S-AUTH**. `PR-AUTH-01B` — альтернативный credential mechanism. Нужно подтвердить trusted user issuance route; нельзя принять рабочий token writer без enforcement/admin control. | Совместно принять согласованный **первый работающий функциональный contract**; допускаются отдельные некоммитящие validation probes. |
| **PG-SEM · SOFT_BUNDLE** | `PR-SEM-01/02/03/04/05`, связано с PG-AUTH для реальных защищённых writes. Exact QRPE↔Finding mapping и Action/O-D адаптер требуют evidence. | Принятие смыслового контракта отдельно от схемной/физической миграции. |
| **PG-WORK · SOFT_BUNDLE** | `PR-WORK-01/02/03/04`; `PR-WORK-03 REQUIRES owner/identity semantics` до safe archive/delete. | Самостоятельный research graph можно сначала читать/тестировать, promotion/delete только после решения о владельце. |
| **PG-DEP-REP · SOFT_BUNDLE** | `PR-DEP-01/02 + PR-REP-01/02`; `PR-DEP-03` — альтернативная стратегия runtime, `PR-REP-03` — отдельная дополнительная (не выбранная) writable feature. | Read-only representation и dependency pilot могут быть проверены независимо; не обещать semantic write-back. |
| **PG-PERSIST · conditional group** | `PR-PERSIST-01 + PR-PERSIST-02` для real GitHub canonical work-graph writer. | **Не коммитить remote cutover** до выбора repo/branch/writer и multi-file acceptance evidence. |
| **PG-PLAN · SOFT_BUNDLE** | `PR-PLAN-01/02/03/04` (core temporal meaning, Plan↔RDG refs, authoring rights), `PR-PLAN-05` optional view, `PR-PLAN-06` excluded executor. `PR-PLAN-02 REQUIRES PR-PLAN-01`; `PR-PLAN-04 REQUIRES PR-AUTH-03 + PR-PLAN-01`. | План как отдельный temporal owner может пройти read-only validation независимо от полной реализации Findings; запись/авторизация Plan требует authority gate; execution engine — отдельный будущий выбор. |
| **PG-ROLLOUT · sequence** | `PR-ROUTE-01` validation, затем staged integration; `PR-ROUTE-02` только после legacy coverage. | Это порядок obtaining evidence, а не единый продуктовый state-machine/commit. |

**Recommended Candidate Composition (v3):** `PG-AUTH {PR-AUTH-01,02,03,04 + targeted PR-RV-01/02A/03/04}` (реализация с учётом прямых решений пользователя), `PG-SEM {PR-SEM-01..05}`, `PG-WORK {PR-WORK-01..04}`, **`PG-PLAN {PR-PLAN-01..04,05 optional}`**, `PG-DEP-REP {PR-DEP-01,02, PR-REP-01,02}`, `PG-PERSIST {PR-PERSIST-01,02}` только после remote gate, `PR-ROUTE-01/02` как staged execution/retirement policy. Исключены из рекомендуемого состава сейчас `PR-AUTH-01B`, `PR-DEP-03`, `PR-REP-03`, и любая немедленная массовая O/D миграция/удаление старого кода. Все status = **pending**; «recommended» и «selected candidate» не равны committed.

**Проверка совместимости состава:** обязательные user wishes S-AUTH и S-DEP-REP покрыты; `PR-AUTH-03` не требует жёсткой изоляции вне API; Gendocen receipts не несут семантического authority; markdown/export не зависит от будущей GitHub ветки; архивный поиск не заставляет грузить все графы; перенос результатов не допускает двух канонических записей. Остались реальные gates: trust bootstrap, QRPE schema, owner promotion, remote owner и runtime integration; скрытых `REQUIRES` на немедленный remote commit нет.

### 10.2. Прослеживаемость предыдущей истории

| Исходный набор | Сохранён в новой композиции |
|---|---|
| H-PR-01: Authority Scope | `PR-AUTH-01..04` + WR-03..12; пользователь определил Helper + bearer token для любого чата. |
| H-PR-02: typed Findings | `PR-SEM-01`; review original F-P/F-R/F-U/F-O; multiple questions; no duplicate registry. |
| H-PR-03: open canons + upstream | `PR-SEM-02/03`; `U1+A2` vs `U2+A1`; T1 guard. |
| H-PR-04: persistence formula | `PR-WORK-04`, WR-22; `(C1 OR C2) AND C3`. |
| H-PR-05: transient Lens | `PR-WORK-04`, `PR-ROUTE-02`; no default LensRun, legacy deletion separately. |
| H-PR-06: independent research graphs | `PR-WORK-01`; no mandatory Git branches. |
| H-PR-07: hide/detach/archive/delete | `PR-WORK-03`; AI index/Viewer access, default context sparse. |
| H-PR-08: promote/associate | `PR-WORK-02`; single semantic owner. |
| H-PR-09: valuable verification without Finding | `PR-WORK-04`, WR-27; scope/commit/date/evidence. |
| 2026-10-17 pre-work v1 (`PR-01..11`) | Authority grant+guard+admin, QRPE, canon, generic API, O/D, independent graph, multi-writer, Helper/Viewer, deprecation сохранены в отдельных PR v2, без перенумерации v1 как committed. |
| Последующие требования Helper bearer-token | **Новые** `FR-01..05`, `PR-AUTH-04`, S-AUTH; прежний вопрос «кто root user?» закрыт. |
| Последующая идея дополнительных представлений | **Новые** `N-04`, `FR-08`, `PR-REP-01/02`; Markdown c абзацами и приложения. |
| Последующий архив Gendocen и предложение direct JSON overlay | **Новые** `N-05`, `FR-09`, `PR-DEP-01/02`, S-DEP-REP, EA-16..21; reuse existing engine вместо своего. |
| Post-review решения пользователя о принятии Action | `FR-14/15`, `WR-41..44`, `EA-28/29`; source Review `F-P-RV-01/02, F-U-RV-01/02`; нельзя объявить эти Problems resolved до кода и тестов. |
| Запрет сохранения preferences / `preselected` | `FR-14`, `WR-42/47/48`, `PR-PLAN-01/03`; никакой новый Action status не вводить. |
| Самостоятельный Plan именно **во времени** | `N-06/07, FR-11..13, S-TEMP, SRU-11/12, WR-45..53, EA-30..36, PG-PLAN`; RDG получает плановые условия для Canon/Finding, Plan остаётся отдельным владельцем своей временной истории. |
| Проверка ранее частично выполненного пилота | R-RDG-PILOT-20261018/v1, `8.1` и новая Stage 1C; pass старых regression ≠ accepted authority. |

Старые `F-P/F-R/F-U/F-O` review и текущие F локальны своим review/pre-work; не переносить их как фактически новые проблемы RDG. Действующий legacy v7 не переписан этим документом.

## 11. Recommended Resolution Route — кандидатный порядок с независимыми решениями

**Изменения маршрута v3 — фактический прогресс + temporal Plan (ниже исходные подробные инструкции стадий v2 сохраняются как методы, но не как утверждение об их текущем статусе).**

| Stage / фактический статус | Смысл следующей работы и реальный gate |
|---|---|
| **0 — partial DONE / read-only** | Установлен рабочий owner-mount без `.git` и прочитан существующий writer/нормативный контекст; точный Git diff не установлен. Перед конкретными изменениями ещё нужны адресные preflight/readback. |
| **1A — PARTIAL / NOT ACCEPTED** | Local bearer grant/opt-in guard работает в проверенных последовательных случаях, но Review v1 обнаружил privilege bypass и revoke race. Продолжить через **Stage 1C**; не пускать real grants. |
| **1B — PARTIAL / runtime NOT ACCEPTED** | Read-only `rdg-gendocen-adapter.py` создан, stable node IDs есть; multi-resource ID и tracked raw hash требуют refinement. Полный `docengine` rules/review freshness/Markdown **не подтверждены** независимым review. |
| **1C — NEXT, remediation authority** | Ввести separate accept/selection operation, запрет already-selected внутри plain create; linearizable revoke-before-commit; bearer-only client/internal trust receipt; структурные denial и writer-path automated tests. **Gate:** F-P-RV-01..04 retest + replay/recovery/denied invariant. |
| **2 — semantic contract** | Typed Findings, Canon, Action selection and T1, original O/D compatibility; Plan reads Actions, но не создаёт их own truth. Требует принятой границы authority прежде material writes. |
| **2P — NEW Temporal Plan contract, parallel read-only** | Определить minimal Plan ID, owner, branch/time/event semantics, refs, deadline provenance, read-only fixture; **gate:** отсутствие `preselected` и silent Action commit, user goal S-TEMP trace. |
| **3 — working/research graph** | Исследования, owner promotion/link, retention, snapshots, no forced LensRun; Plan refs across graphs с проверкой owner. |
| **3P — NEW temporal synthetic proof** | Сконструировать Plan с 2 candidate Actions, условными ветвями, возможным/фактическим event и deadline; оценить Canon/Finding с учётом Plan. **Gate:** проверенное разграничение candidate/accepted/actual и no-change RDG Action. |
| **4 — persistence/invalidation** | Plan owner persistence и Graph API на тех же ревизионных/authority принципах, Gendocen RDG↔Plan dependency receipts после runtime-gate; remote GitHub отдельно после выбора владельца. |
| **5 — integration** | Helper grants/UI и Plan authoring, Viewer timeline/branch + Markdown/external consumer; **раздельный installed Windows proof**; никакой исполнитель условных ветвей автоматически. |
| **6 — conditional retirement** | Только доказанная замена legacy функций/схем/архива и явные права; Plan не оправдывает удаление текущих моделей. |

**Order of decisions vs execution:** подтвердившиеся пользовательские semantic directions из `1.2 снимают соответствующие **нормативные** forks, но кодовая композиция Stage 1C остаётся pending до проверки. Стадии 2P и 1B разрешены **параллельно read-only**, не требуют коммита всего PG-AUTH. Stage 3P для реальных Plan writes требует Plan/Action permission contract, поэтому ещё не accepted. Группа `PG-PLAN` не является обязательным атомарным коммитом всего проекта; отдельно делегируемые границы — schema/read-only proof, затем guarded mutation, затем UI/execution.



**Порядок ниже не является committed execution.** В отличие от одной бесконечной разработки, каждая стадия получает evidence, на основании которого можно принять отдельную согласованную композицию, отказаться от преждевременной части либо перейти дальше. Одна и та же SRU не учитывается дважды как effort родителя и ребёнка.

### Stage 0 — Read-only preflight / конкретная контрольная точка

**Зачем:** избежать изменения не того источника и ложного заявления «уже реализовано» при отсутствии настоящего `.git` в RDG mount. **Scope:** только инвентаризация нужных исходников, инструкций, операций writer, тестов, Helper и Gendocen package layout, лицензии, прав; без правок.

**Prerequisites:** отдельное разрешение на начало реализации; доступный актуальный mount; README/AGENTS где существуют; фактические credentials не запрашивать без необходимости. **Gate / evidence:** inventory touched API and callers, current version, clean/dirty proof только там, где доступен реальный Git, карта legacy vs candidate и no-cutover. **Downstream:** выбрать точный минимальный тестовый полигон.

### Stage 1A — Authority validation-first slice (S-AUTH, SRU-02/03/04)

**Purpose:** проверить, что токен действительно даёт и ограничивает права любого чата, без полной системы deployment и сложного UI. Создать **только тестовые** grant store, mock Helper flow / admin API и test graph. Вход — два test actors (или два chat contexts), user-admin actor, ограниченный токен.

**Действия:** user issue token → передать другому test actor → permitted mutation → denied upstream mutation с `missingPermission/requestTo` → amend grant → verify new rights → revoke → rejected write → attempted delegated self-grant denied → secret not in graph/log. Политика проверяется на acceptance boundary. Полезная ошибка — результат, не invitation к bypass. Не нужна жёсткая ОС изоляция. **Gate:** authorized and unauthorized tests, no partial writes, no self-grant, user review UI concept. Если доверенный user-bootstrap не может быть установлен без нового trust backend, сделать candidate forks и остановить только production grant rollout.

**Решение после evidence:** утвердить `PG-AUTH` implementation contract либо выбрать иной минимальный способ из `PR-AUTH-01B`; нельзя выдавать real production tokens на основании mock.

### Stage 1B — Gendocen overlay validation-first slice (S-DEP-REP, SRU-07/08), **может идти параллельно с 1A**

**Purpose:** проверить user hypothesis «движок уже на JSON, просто добавить сверху», а не писать свой runtime. Вход — отдельный синтетический `graph.json` в формате RDG и извлечённый Gendocen runtime в разрешённой изолированной среде.

**Действия:**

1. Протестировать **read-only projection** существующего `graph.json` в ресурсный контракт Gendocen `$docengine`/`data` (или native resource adapter, если он доказанно проще). **Не менять исходный RDG JSON.**
2. Экспортировать `nodesById` по стабильным ID, существенные поля R/Action/Canon/Context/Finding и версию, соблюдая `identitySpace`; не считать позицию в `nodes[]` частью identity.
3. Зарегистрировать точную вычислительную зависимость Markdown-представления и содержательную семантическую зависимость оценки Action от существенного Context/Canon.
4. Изменить **несущественное** поле: отсутствие ложного material review / неверного rebuild.
5. Изменить **существенную** предпосылку: увидеть `review_required/stale`, diff/receipt/current source; не создать F-P автоматически.
6. Поменять source ещё раз до validate: прежний `review_context_id` должен быть отклонён. При новом контексте AI may record `still-valid` или обоснованный вывод в RDG только через разрешённый token API (для slice — mock/no-write).
7. Изменить сам Action: Markdown regenerates to current view; provenance/source revision/identity и T1 не изменены.
8. Проверить перестановку элементов массива `nodes` без смыслового изменения, пропущенную indirect dependency как негативный контрпример и доверенные границы project Python execution.

**Gate:** no RDG source mutation, exact/field-level dependency behavior, semantic review and generated view observed, configuration/third-party code/licensing feasible. При провале не выдавать PR-DEP-03 (свой runtime) за принятое решение: сначала показать конкретную несовместимость и delta стоимости.

### Stage 2 — общий RDG semantic contract (SRU-01/05 + writer guard SRU-04)

**Purpose:** один semantic owner и один general API; расширение старых объектов без нового параллельного реестра.

**Действия:** schema evolution `QRPE→typed Finding`; multiple questions/evidence/PR relations; substantive dispositions; controlled canon-extension; Action candidate/selected/implemented/verified statuses/events как независимые факты; authority policy on all mutation paths; ability to propose upstream compositions; correct persist `(C1∨C2)∧C3`; old O/D read-only compatibility. Не импортировать мета-оси review (CURRENT, Next Gate, Intervention Priority) как обязательные хранимые поля RDG.

**Gate:** legacy old QRPE untyped safe, T1 remains historical, negative canon doesn't auto-revoke, path-coverage tests, package/revision guard. Различать **T2** (позднее обнаружен факт о прошлом, который существовал при T1) и **T3** (обстоятельство действительно изменилось после T1): dependency diff сам по себе не устанавливает, какой это случай, и не переписывает историческую запись. **Отдельное решение:** физическая миграция O/D пока не включена.

### Stage 3 — independent work graphs + evidence lifecycle (SRU-06)

**Purpose:** обеспечить длинное исследование через несколько чатов и сохранять только существенные результаты в действующем main work.

**Действия:** новый standalone root-R research graph; связать с main; сделать synthetic Research→Finding/verified test→Proposals/canon→promote/associate result→archive; проверить `identitySpace`, `projectionOf`, owner, provenance, reference integrity, lazy index and hide/detach/delete guards. Пример без Finding, но с подтверждённым полезным тестом обязателен. **Gate:** один текущий semantic owner, no dangling references, archive discoverable, main context not flooded, no false accepted decision. Если move/link семантика остаётся материально различной — отдельный commit decision именно для ownership mechanism.

### Stage 4 — local persistence, Gendocen runtime state и GitHub (SRU-07/09)

**Purpose:** операции после нескольких файлов/чатов безопасны и подтверждаемы. **Часть локальной работы можно делать до GitHub выбора.**

**Действия:** локальные package-journal+catalog recovery / concurrent revisions; Gendocen receipts/baselines stored as **technical secondary state** with explicit regeneration/trust semantics; full read-back and fault-injection. Затем **отдельный gate пользователя** выбрать GitHub canonical repo/branch/writer и разрешить безопасную isolated remote проверку. Сравнить Git tree/ref transaction с Contents multi-PUT; проверить partial commit, index consistency, rollback/recoverability, token auth vs GitHub actor rights. Никаких real user-workspace writes до явного owner/access decision.

**Gate:** consistency observed for target environment; readback, concurrent branch protection, single active semantic owner; Gendocen runtime state recoverable/re-creatable без ложного восстановления старой правоты.

### Stage 5 — full integrations and representations (SRU-03/08/10)

**Purpose:** превратить proof в нормальный пользовательский путь.

**Действия:** Helper user admin UI; prompts and `work-kit` semantic contract; structured consumer/export API; Markdown narrative templates; Viewer Action/Findings/research metadata, archive toggle, provenance/evidence, refresh; доступный поиск архива и сохранение только выбранного context. Выполнить изолированные browser/source tests. **Отдельно** согласовать обновление установленного Windows/Tampermonkey/Helper и проверить там реальные operations после установки. G2 и Repo — разные окружения; owner HOST не использовать.

**Gate:** end-to-end три сценария, четкий source/install distinction; no unauthorized user-state mutation; rendered Markdown действительно читабелен и соответствует source; положительная и негативная ветки authority UI.

### Stage 6 — targeted simplification / возможное retirement

**Purpose:** убрать дублирование только после доказанного замещения. Оценить оставшийся `stable/protected` пилот, Lens application archive/metadata, старые O/D data и старые API. Если доказана ненужность и сохранена совместимость, создать отдельные migration/deprecation PR; не удалять автоматически код, пользовательские файлы, исторические snapshots или Git references. **Gate:** preserved historical fidelity, targeted legacy tests, user-approved scope где материален.

### Приоритет/стоимость

- **Now для планирования:** два validation slices 1A и 1B и точный контракт Stage 0; benefit — снять основные риски ранней архитектуры без реальной пользовательской записи.
- **Next conditional:** typed Findings/open canons/general Graph API и независимые графы — основа пользовательских сценариев; внедрение только после предыдущих gates.
- **Later conditional:** physical O/D migration, editable Markdown round-trip, remote cutover и deleting legacy — отсутствие сейчас не препятствует ранним outcomes.
- **Effort vs elapsed:** эти стадии имеют последовательные gates и частичную параллельность 1A/1B, но длительности и ресурсы неизвестны; календарных оценок/буфера нет. Нет подтверждённого hard deadline; feasibility unconfirmed. Cost delta между full-now и staged — качественная: staged раньше приносит evidence и уменьшает rework, но даёт дополнительную validation-операцию.

## 12. Candidate Verification Plan — что и как доказать

**Verification delta v3:** ниже исходная матрица v2 остаётся применимой как план, но её будущие PASS-критерии **не равны фактическим прошедшим тестам**. Авторитетное независимое status-подтверждение — Final Review v1 (`8.1), а уточнённые критерии следующей версии:

| Новый блок | Точный исполняемый тест / acceptance gate |
|---|---|
| **Authority remediation — WR-41..44, EA-28/29** | На test graph `graph.create` не допускает already-committed D/selected Action; раздельные create/canon/finding/select grants для двух actors; один внешний bearer без HMAC ключа; revoke after prepare before journal publication rejects without graph/index/history change, including concurrent processes and replay/recovery. Подтверждённые F-P-RV-01/02 должны получить независимый **post-fix** reproduction с новым исходом. |
| **Denial/test quality — F-P-RV-03/04, WR-08/39** | Новые автоматические tests **вызывают actual writer**, не только grant CLI; concrete `file/scope/permission` + request path, denied byte-identical, no secret in stderr/stdout/graph; stage-level full regression после точечных tests. |
| **Temporal Plan fundamentals — WR-45..48, EA-30..33** | Отдельный Plan без изменения RDG graph files; двухветвенный test Plan с candidate A1/A2, event-trigger, relative date and hard/soft deadline, schedule without invented exact times, Plan ref stable by owner/identity, unresolved branches not marked occurred, no `preselected`. |
| **Plan-aware meaning — WR-49/50/52, EA-34** | Как изменённый timeline/deadline делает Canon/Action finding **контекстно** reviewable; для hypothetical ветви допустим F-R/F-U, но отсутствие наступившего hard deadline не доказывает F-P; Plan edit does not alter T1; Gendocen rules differentiate significant vs irrelevant change. |
| **Temporal permissions — WR-51/53, EA-35/36** | Chat с `plan.write` может описать будущую ветвь, но не `action.select`, attest actual event без права или auto-execute; rejected mutation leaves Plan/RDG unchanged; второй reader получает time/branch view с as-of. |
| **Real Gendocen licensing/runtime — WR-28..31/40** | Read-only adapter projection ≠ actual Gendocen dependency engine; runtime environment, collision-safe resource IDs, semantic receipts, stale `review_context_id`, trusted Python and redistribution rights проверяются **до** заявлений о готовности или импорта движка. |



| Блок и WR/EA | Evidence и критерий будущего PASS | Ограничение/что не означает PASS |
|---|---|---|
| **Источники / WR-01/02/39** | Текущие README/AGENTS, mount, права, revision, diffs и actual `git status` только где возможно; exact links to prior v1/handoff; change log отделяет candidate/committed. | Не объявлять mount без `.git` чистым Git repository. |
| **Bearer token / WR-03/04/07, EA-01/02/04** | Два unrelated actors получают одинаковое право от одного токена; wrong token/expired/revoked/amended grant before/after tests; scope enforcement at commit. | Кто обладает токеном ≠ удостоверенный физический пользователь. |
| **Admin/UI / WR-05/06/08/11, EA-03/05/06** | Issue/list/amend/revoke via Helper and admin API; forbidden delegations denied, no partial write, useful required-permission/request path, no token leak in logs. | Mock Helper/CLI не означает проверенный установленный браузер. |
| **Authority coverage / WR-09/10/12/20, EA-07/08** | Матрица всех графовых operations включая edge/reparent/select/promote; allowed and denied; CI failure if route bypass; grant not equal decision competence. | API guard не обещает запрет raw files editing вне API или права GitHub/OS. |
| **Findings / WR-13..15, EA-09/10** | F-P/R/U/O semantics, questions[], evidence, multiple Proposals, unknown legacy QRPE stays unknown, independent disposition/status. | No automatic resolution on PR commit; current/upstream relative to scope. |
| **Canon/T1/upstream / WR-16..19, EA-11/12** | Prepared vs working canon distinction; add case with provenance; positive/negative condition; T1 pre/post identical; decision composition alternatives and authorization. | Detection of conflict not automatic upstream revoke. |
| **Generic API / WR-20/21/38, EA-07/13/26** | Legacy O/D & candidate-v6 fixtures, root/edge/Action operations, old history and links, negative cycle/identity; tests targeted then relevant full regression. | Legacy read adapter not proof physical migration is safe or needed. |
| **Persistence/Lens / WR-22/23/27, EA-15/27** | `(C1∨C2)∧C3` includes decision/plan and economic gate; ephemeral Lens no LensRun; valuable passed test stored without Finding; excess ephemeral not retained. | Old per-run archive is not deleted by this proof alone. |
| **Research owner/lifecycle / WR-24..26, EA-14/15** | Cross-chat resume, one canonical owner, move or link with provenance, hide/detach/archive/delete distinct and safe; lazy retrieval without flooding context. | Hiding/archive not physical deletion, Git branch not required. |
| **Gendocen adapter / WR-28/29/40, EA-16/17/21** | RDG input stays byte-identical; `$docengine/data` projection uses stable IDs; project root and runtime trust/side effects verified; dependency no false invalidation from reorder. | Gendocen source README not proof arbitrary RDG JSON direct acceptance. |
| **Change detection / WR-30/31/34, EA-18..20** | Material context change -> `review_required/stale`; irrelevant field -> no semantic revisit; stale review token rejected; missing indirect prerequisite test; RDG API token required for follow-up writes. | `review_required` ≠ Problem; `valid` receipt ≠ all assumptions considered. |
| **Markdown/other consumers / WR-32/33, EA-22/23** | Narrative paragraphs produced with meaningful sections; source IDs/revisions; generated drift detected; external read consumer renders its own view; safe no-write-back default. | Presentation neither canonical semantic data nor authorization token. |
| **Multi-file/GitHub / WR-35/36, EA-24** | Partial commit failpoint; catalog/graph identity; recovery; SHA/ref conflict; authorized remote test; read-back actual repo/branch/commit only after user selection. | Fake single-file SHA PUT not proof multi-file atomicity. |
| **Viewer/Helper installation / WR-37/39, EA-25** | Source tests + isolated browser; separately tested installed Tampermonkey/Helper with explicit permission; E2E S-AUTH, S-WORK, S-DEP-REP observed. | Repo code modification != installed == published. |
| **Work Value, scope / WR-12/38/40, EA-26/27** | Compare complexity with user benefit, coverage of legacy before retire, engine license/maintainability, no redundant registry/subsystem. | More tests/more files not automatically more evidence. |

**Материальные интеграционные сценарии, не заменяемые локальными unit tests:**

1. **S-AUTH pass:** user (Helper) creates limited token → second chat uses it on allowed action → attempts upstream prohibited edit → gets actionable refusal and unchanged graph → user changes grant → new operation allowed → user revokes → all future writes refused. Проверить обычный и delegated-admin отрицательный случай.
2. **S-WORK pass:** research graph across two chats → discovered new canon, typed Finding/questions, upstream composition considered → verified test (with or without Finding) → link/promote to correct owner → archive → AI and Viewer retrieve on demand. T1/history/identity intact.
3. **S-DEP-REP pass:** canonical RDG JSON unchanged → adapter and Gendocen registered dependencies → irrelevant vs material source change distinguished → stale review context rejected → appropriately interpreted human/AI review without self-authority → affected narrative Markdown updated → external read-only consumer shows current version.
4. **Failure/recovery pass:** concurrent graph edit, grant revoke race, Git file partial write, index refresh errors and installed/source mismatch all produce accurate failure or recovery state, never fabricated success.
5. **S-TEMP proof:** Plan содержит будущий эксперимент, событие и условные ветви A1/A2, дедлайн и временную зависимость «после результата»; оба Action остаются `candidate` до отдельного принятия; гипотетическое не становится фактическим; Plan-aware Finding/Canon учитывает лишь корректную ветвь/статус срока, изменение Plan даёт адресную переоценку, но не silent commit. Для следующего этапа отдельно проверяются guarded Plan write, authorized event attestation и playback/as-of.

## 13. Completeness, readiness и пользовательские вопросы — обновлённый статус v3

### Completeness checks

- **Историческое покрытие:** сохранены v2 `N/FR`, `WR-01..40`, `EA-01..27`, H-PR-01..09, PR-AUTH/SEM/WORK/DEP/REP/PERSIST/ROUTE, живые O/D и experimental Action, Finding F-P/R/U/O, T1/T2/T3, Canon, Lens, independent work graphs, archive, GitHub owner и Helper/Viewer.
- **Изменения после v2:** реальный partial Stage 1A/B и независимый Review с 4 подтверждёнными Problems (в scope), 2 Risks, 2 F-U, которые **не скрыты** за статусом 405 PASS; пользовательские решения creation/select, commit-time revoke, bearer-only client/internal receipt, no preference/preselected.
- **Temporal Plan как новая самостоятельная цель:** `N-06/07; FR-11..13, S-TEMP, SRU-11/12, PR-PLAN-01..06, WR-45..53, EA-30..36, Stage 2P/3P, собственные origin/time/branches/owner и двусторонняя RDG evaluation. Plan не превращён в RDG Action lifecycle, графовую декомпозицию R либо отображение Viewer.
- **Status/provenance:** v2 неизменённый historical snapshot; Review v1 как отдельный evidence owner; пользовательские направления — явные input decisions, но **не** technical PR/whole candidate baseline commit и **не** resolution F-P. `forfiles` не canonical storage/installed release.
- **Пропорциональность:** сначала Stage 1C defects + Plan/ Gendocen synthetic read-only, затем guarded/installed/remote этапы. Нет мнимого дедлайна RDG, отсутствуют обязательные CRON/executor/двусторонний Markdown.

### Readiness per route

| Компонент | Текущий вывод / gate |
|---|---|
| **Stage 0 preflight** | Частично подтверждён, актуальные файлы нуждаются в targeted read перед новыми правками. |
| **Stage 1A bearer opt-in** | **PARTIAL — NOT ACCEPTED**, F-P-RV-01/02/03/04 unresolved. Последовательные тесты ≠ race/semantic proof. |
| **Stage 1B Gendocen** | **PARTIAL — projection only**. Загрузка реального runtime, semantic deps, freshness, лицензирование и Plan resources не проверены. |
| **Stage 1C auth remediation** | **READY FOR DESIGN/ISOLATED TESTS**, три пользовательских направления уже даны; никаких real grants до safe gate. |
| **Stage 2/3 semantic & research graphs** | **PENDING**; QRPE Finding schema, Action semantics, owner promotion и backward compatibility — независимые технические gates. |
| **Stage 2P temporal model** | **READY FOR CANDIDATE DESIGN/READ-ONLY PROOF**. User intent established; exact Plan storage, branch grammar, time precision и linkage требуют решения после small fixture. |
| **Stage 3P / 4 Plan write + temporal deps** | **PENDING**; owner/identity/permission contracts, actual-event provenance и Gendocen runtime gate. |
| **Stage 5 Helper/Viewer/remote** | **PENDING / NOT INSTALLED**; реальный trusted user bootstrap и выбор GitHub canonical work owner остаются отдельными gates. |

### Decisions and questions

**Уже прямо установлено пользователем (не задавать повторно):**
1. `graph.create` создаёт candidate-only граф; выбор Action — отдельное право, потенциально другого чата.
2. Token revoke до durable commit должен остановить сохранение.
3. Bearer — единственный внешний credential для чата; internal confirmation/legacy HMAC handling принадлежит API.
4. `selected` = действительно принятый Action; preference не фиксировать; `preselected` не нужен.
5. Plan — **самостоятельная сущность во времени**, с будущими Actions, events, conditions, branches, deadlines; Plan informs RDG Canon/Finding и наоборот.

**Остаются технические forks, которые не стоит объявлять блокирующими всю работу:** verification bootstrap в Helper, специфический механизм HMAC/internal receipt, QRPE/Finding schema, research outcome owner transfer/link, native Gendocen adapter vs materialized projection, unique resource/Plan refs, temporal Plan persistence/schema/branches/events/timezone/unknown dates, real remote graph repo/branch/actor, optional Markdown write-back и optional executor. Сначала добрать адресное evidence; материалное изменение ожидаемого поведения или user-impact потребует отдельного Proposal/решения, без молчаливого выбора.

**User assistance:** прямо сейчас не нужно повторять вопросы, на которые пользователь ответил. Перед live GitHub graph writes требуется выбор canonical repo/branch/writer; до него возможна изолированная локальная работа. Перед production issue нужна авторитетная user-auth boundary Helper; пока только mock/local.

### Итоговая Candidate Composition / границы транзакции

**Candidate v3:** `PG-AUTH` с remediation `F-P-RV-01..04`, `PG-SEM`, `PG-WORK`, **`PG-PLAN`**, `PG-DEP-REP`, conditional `PG-PERSIST` и staged route/retirement policy. **Ни один новый technical PR автоматически не committed публикацией этого плана.**

**Следующее действие при отдельном запросе на реализацию:** Stage 1C локальный исправленный writer с тестами + независимо читаемый Plan prototype Stage 2P; Stage 1B complete runtime spike может идти параллельно. **Нет права** молча менять рабочие user graphs, Windows-installed scripts, GitHub canonical owner или вводить executor.


## 14. Источники, provenance и статус публикации

- Файлы пользователя: `1 (2).txt`, `2.txt`, `3.txt`, `4.txt`, `5.txt`, `6.txt`, `7.txt`; `RDG-handoff-full-2026-10-17(1).zip`; `gendocen-main (1)(1).zip`.
- Original Finding contract: внутри handoff `RDG-handoff/04-REVIEW-PROMPT-ORIGINAL.txt`, в частности Finding Model, Questions/Proposals, Disposition, User Review Priority/Intervention Priority/Decision Autonomy и distinction `Problem/Risk/Decision Uncertainty/Improvement Opportunity`.
- RDG inventory from previous targeted read: `README.md`; `docs/examples/RDG-V6-GENERAL-GRAPH-API-AND-SELECTIVE-LENS-20261017.md`; `docs/examples/RDG-V6-CROSSPLAN-REMEDIATION-20261017.md`; `tools/graph-apply.py`, `tools/rdg-graph-api.py`, `tools/rdg-v7-model.py`, `tools/graph-package.py`, `tools/graph-index.py`, `tools/rdg-github-store.py`; `work-kit/README.md`; `docs/guides/VIEWER-EXPLORER.md`.
- Gendocen archive source: `README.md` (runtime identity and data model), `src/docengine/resources.py` (`$docengine`/`data`), `docs/DEPENDENCY_MODEL.md`, `docs/SEMANTIC_REVIEW.md`, `docs/MATERIALIZATION_MODEL.md`, `docs/DEPENDENCY_AUTHORING_CHECKS.md`.
- Предыдущая версия Candidate Pre-work 2026-10-17: `rdg-candidate-prework-authority-and-roadmap-2026-10-17-v1.md`, GitHub reading snapshot `artifacts/2026-10-17/candidate-prework-rdg-authority-admin-api-roadmap-20261017-v1.md`. Статус прежней версии не переписан.
- Независимое [Final Review R-RDG-PILOT-20261018/v1](https://github.com/AlexPastukhh/forfiles/blob/main/artifacts/2026-10-18/review-rdg-authority-gendocen-pilot-20261018-v1.md): 4 confirmed Problems, 2 Risks, 2 F-U с reproduction/restrictions; отдельный canonical owner своих Findings/PR.
- Последующие прямые сообщения пользователя о `graph.create`, commit-time revoke, bearer-only client/internal HMAC, отсутствии `preselected`, отдельной Temporal Plan entity, ветвях/событиях **во времени** и использовании сроков Plan при проверке RDG — provenance для новых FR-14/15 и FR-11..13; это **не** старые обязательства v2 задним числом.
- Сохранившаяся семантика: `docs/guides/RDG-V7-WORKING-GRAPHS.md` `«Планирование будущего на бумаге»; `work-kit/modules/rdg.work.semantics.module.md` и `rdg.work.planning.module.md` — план альтернатив / decomposition ≠ временная очередь исполнения. Отдельного принятого temporal Plan data contract эти источники не подтверждают.
- Реально выполненный partial pilot (исторический) проверялся на `tools/rdg-authority.py`, `tools/graph-package.py`, `tools/rdg-gendocen-adapter.py`, `tests/rdg-bearer-authority.test.cjs`, README; **в этой редакции исходники не изменяются и повторные тесты не запускаются**. Git SHA для рабочего дерева RDG недоступен (нет project `.git` в mount).

- Данный документ — **reading copy / not canonical**. Публикация в `AlexPastukhh/forfiles` и/или GitHub-навигация могут подтверждаться **только отдельным реальным read-back**, не самим наличием этого предложения в плане.
