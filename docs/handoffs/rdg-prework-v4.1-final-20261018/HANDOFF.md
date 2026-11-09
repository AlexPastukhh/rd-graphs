# RDG / Temporal Plan / Gendocen — ПОЛНЫЙ HANDOFF ДЛЯ НОВОГО ЧАТА

**Дата среза:** 2026-10-18. **Статус:** Candidate Pre-work и проверенные локальные прототипы, НЕ whole-baseline committed, НЕ production.
**Первым делом:** читай этот HANDOFF и соседний candidate-prework-v4.1-execution-reconciled.md. Исправленный v4 содержит полный оригинал v3 в Приложении A (FR/WR-01..53/EA-01..36/PR/SRU) и актуальные статусы и маршрут. Не замещай исходные решения новым дизайном без достаточного evidence.

**RDG owner workspace:** /workspace/repos/rd-graphs, через Fortis Repo, без .git. **Движок:** /workspace/repos/gendocen, Gendocen docengine 0.1.0.dev25. Доступ к путям надо проверять в новом чате; они не являются гарантией другой среды.

## Как начать: два режима доступа

**A. Есть Fortis Repo:** прочитай живой исходный код по путям в этом handoff, сравни source hashes из MANIFEST и только затем запускай локальные тесты. Снимки из пакета служат evidence, но рабочим owner остаётся подключённое дерево RDG.

**B. Нет Fortis Repo:** этот ZIP включает все pre-work документы, исходный v3, independent review, scoped checkpoints и 30 фокусированных RDG source snapshots. Он достаточен для понимания и code-review P0. Для запуска реального Gendocen требуется отдельный локальный источник docengine 0.1.0.dev25 или подключение к /workspace/repos/gendocen: движок намеренно не дублируется из-за неустановленного права распространять его исходный код. Не приписывать этому ZIP полный автономный executable environment.

**Обычный acceptance-test:** tests/rdg-gendocen-branch-membership.acceptance.test.py — сейчас 1 PASS и 1 **намеренный FAIL** (продуктовый дефект). Диагностический repro-branch-membership-gap.py отдельно возвращает 0 при BUG REPRODUCED. **Нельзя считать его exit 0 исправлением дефекта.** После P0 должны PASS оба acceptance-кейса; косметический reordering не должен давать false review. WR evidence paths и точные remaining gates — WR-EVIDENCE-LEDGER.md.

**Что копировать:** для передачи используется ZIP rdg-prework-v4.1-final-20261018.zip и все содержащиеся в нём файлы; не пытайтесь заменить его одним сокращённым чатом или исторической v3. Входным документом внутри архива остаётся HANDOFF.md.

## 0. Суть и первая обязательная задача

Архитектура исходного Pre-work v3 **в целом правильна**, но порядок исполнения надо скорректировать. RDG является смысловым владельцем Requirements/Actions/Canon/Findings/выбора T1; отдельный Temporal Plan — владельцем будущих шагов, событий, времени, возможных/условных путей и deadlines; Gendocen — вторичный dependency/review freshness engine; Authority — bearer-based writer policy, не доказательство фактической истины или человеческой личности.

**Главный открытый дефект, воспроизведённый на настоящем Gendocen 0.1.0.dev25:** если изменить соответствие исходов условной ветви Plan шагам Actions A1/A2, не меняя deadlines и canon/qrpe, оценки A1 и A2 остаются valid. Это неправильно, если оценка предполагала конкретное соответствие outcome→Action. Текущие subscriptions следят за timeConstraints, Canon, QRPE, но не за branchesById/cases. Дефект — WR-31/WR-50, EA-18/EA-34 оригинального v3. **Первый P0:** исправить coverage-contract, добавить обязательный отрицательный тест на branch membership, сохранить низкий уровень ложных invalidations.

Не продолжать бесконечно добавлять crash-tests — аварийный rollback уже проверен. Не внедрять новый scheduler/executor, не переводить Plan в RDG Action.preselected, не переписывать RDG под $docengine.

## 1. Что пользователь явно решил — не задавать эти вопросы повторно

1. Graph API позволяет создавать граф с candidate Actions; создание НЕ принимает решение. Action.status=selected означает реально принятое решение и требует отдельного grant/операции.
2. Пользователь управляет полномочиями через Helper, выдаёт bearer-токен любому чату. Чат предъявляет только bearer. Проверка прав и формирование внутреннего technical receipt — задача API.
3. Если токен отозван ДО durable commit, writer не записывает изменение. Не предполагать право на принятие Action из права создать варианты/каноны/Findings.
4. Не нужен preselected и не надо хранить обычные preferences как выбранные Actions.
5. Temporal Plan — самостоятельная сущность **ВО ВРЕМЕНИ**. В ней есть плановые и возможные Actions, события, временные зависимости, условные ветви, deadlines; Plan может ссылаться на RDG сущности, но не копирует их как второго semantic owner и не делает candidate Action selected.
6. RDG при оценке канонов, Findings и сроков может учитывать Plan/ветвь/as-of. Гипотетические условия не превращаются в истинные обязательства проекта. Planned ≠ performed ≠ attested event ≠ verified result.
7. RDG должен существовать в нескольких представлениях (включая абзацный Markdown и данные для внешних приложений) без второго writable semantic owner. Использовать имеющийся Gendocen поверх RDG JSON.
8. Research graph — полноценный RDG для долгой работы нескольких чатов, не обязательно Git branch и не постоянный LensRun; сохранить ценное outcome, не захламляя основной граф, одна authoritative запись.

**Открытые пользовательские решения** перед соответствующим irreversible gate: trusted human Helper bootstrap, permanent Plan owner/storage if material to user contract, фактический event attestation и F-P evidence workflow, canonical GitHub work-graph repo/branch/writer, Windows/installed rollout, destructive migration/retirement. Не подменять их выбором ассистента.

## 2. Иерархия источников

- Прямые пользовательские сообщения и оригиналы 1 (2).txt…7.txt / RDG-handoff-full-2026-10-17.zip — semantic requirements.
- Фактические живые код и свежие тесты — текущая implementation truth.
- Соседний candidate-prework-v4.1-execution-reconciled.md — актуальная матрица статусов и новый маршрут; не является committed technical design.
- source-candidate-prework-v3-reading-copy.md — **побайтовая** исходная v3: Git blob SHA 6da1a3648528c01179bcc792b636f56d6b823901; полный N/FR/SRU/WR/EA/Proposals сохранён. В v4 эта v3 включена полностью как историческое Приложение A.
- Original v3 reading link: https://github.com/AlexPastukhh/forfiles/blob/main/artifacts/2026-10-18/candidate-prework-rdg-integrated-temporal-plan-postreview-20261018-v3.md
- Независимый Final Review R-RDG-PILOT-20261018/v1: https://github.com/AlexPastukhh/forfiles/blob/main/artifacts/2026-10-18/review-rdg-authority-gendocen-pilot-20261018-v1.md
- Файлы docs/guides, docs/examples и README текущего RDG — implementation evidence, не доказательство установленного Helper.

Reading copy в AlexPastukhh/forfiles — не canonical owner RDG и не место для live graph writes. Нет достоверного Git commit для текущего owner mount; пакет handoff в GitHub автоматически не опубликован.

## 3. Карта живых исходников

**Authority и writer:**
- tools/rdg-authority.py — bearer grants issue/list/amend/revoke, permissions, scopes, race/commit guard.
- tools/graph-apply.py, tools/graph-package.py — package writer, preconditions/transactions/recovery/authorization.
- tools/rdg-v7-model.py, tools/rdg-v6-action-trust.py, tools/rdg-graph-api.py — семантика Action, T1 selectionBasis, QRPE, general graph operations.
- tests/rdg-bearer-package.integration.test.py, tests/rdg-bearer-authority.test.cjs, tests/rdg-v7-authority.test.cjs — writer/authority negative tests.

**Temporal Plan/semantics:**
- tools/rdg-temporal-plan.py, docs/examples/temporal-plan-candidate-v1.json, tests/rdg-temporal-plan.test.py — candidate-only independent Plan v1, read-only.
- tools/rdg-temporal-impact.py, tests/rdg-temporal-impact.test.py — branch-specific lower-bound/deadline signals, one event only, no real actual event.
- tools/rdg-finding-drafts.py — read-only conditional F-R draft.
- tools/rdg-canon-context-review.py, tests/rdg-canon-context-review.test.py, docs/guides/RDG-CANON-CONTEXT-REVIEW-STAGE2.md — typed/provenance contextual review pilot.
- tools/rdg-problem-evidence-preflight.py, tests/rdg-problem-evidence-preflight.test.py — local evidence checks; even on PASS mayAppendFP=false.
- docs/guides/RDG-TYPED-FINDINGS-STAGE2-PILOT.md — partial semantics, not full verified F-P.

**Real Gendocen:**
- tools/rdg-gendocen-adapter.py; tests/rdg-gendocen-resources.test.py — stable RDG/Plan resources and projections; avoid raw positional node indices.
- tools/rdg-gendocen-runtime-smoke.py — actual co-located Gendocen 0.1.0.dev25 on synthetic RDG/Plan adapter outputs, receipts, stale review and crash/recover.
- tools/rdg-gendocen-t1-history-smoke.py — actual synthetic authorized writer event EV-T1, post-T1 QRPE F-R and transition, co-located Gendocen, Plan branch/deadline, forced crash 91.
- docs/guides/RDG-GENDOCEN-RESOURCES-STAGE1B.md, RDG-GENDOCEN-RUNTIME-SMOKE-STAGE1B.md, RDG-GENDOCEN-CRASH-HISTORY-STAGE4.md, RDG-GENDOCEN-T1-QRPE-PLAN-STAGE4.md.
- docs/examples/RDG-GENDOCEN-COLOCATED-RUNTIME-CHECKPOINT-20261018.json, RDG-GENDOCEN-CRASH-HISTORY-CHECKPOINT-20261018.json, RDG-GENDOCEN-T1-QRPE-PLAN-STAGE4-20261018.json.
- /workspace/repos/gendocen/src/docengine — реализация Gendocen; project Python config is trusted executing code, не OS sandbox. Лицензию/право distribution проверить отдельно.

**Research/Viewer/remote и legacy:**
- docs/guides/RDG-V7-WORKING-GRAPHS.md, tools/rdg-v6-action-reconsider.py, tools/rdg-github-store.py, tests/rdg-v7*.test.cjs.
- tools/rd-graph-viewer*.js, work-kit/modules/*.module.md, docs/handoffs/rdg-context-180-20261016 — исторические контексты, не новый Plan owner.

## 4. Что действительно сделано — по этапам

| Stage | Выполненное | Незакрытый acceptance |
|---|---|---|
| 0 | Repo preflight, mount/no .git; оригинальные материалы исследованы | Версионируемый canonical Git checkout недоступен |
| 1A/1C | Локальный bearer authority, admin CLI, candidate-only graph.create, select отдельно, внутренний receipt, revoke-before-commit и replay/race tests | Нет trusted Helper/bootstrap и installed UI; не independent production review |
| 1B | Gendocen real runtime, collision-safe identity, semantic hash, stable paths | **Нет полного source-dependency coverage, branch membership defect** |
| 2 | Typed QRPE subsets (F-R/F-U/F-O), F-P evidence fail-closed, canon context review, T1 history | Full typed Finding/Proposal/disposition, applicability/canon authoring, independent F-P attestation |
| 2P | Separate candidate Temporal Plan, шаги/события/условные ветви/date+instant/deadlines/refs | No Plan writer/accepted/actual event/history, multi-event unsupported |
| 3 | Existing working/research/Lens v7 foundations | Cross-chat promote/link one owner, archive/hide/detach/delete, successful verification without Finding end-to-end |
| 3P | Read-only temporal signals, separate Finding draft, targeted digests | No full semantic assessment, no historic RDG snapshots for delta |
| 4 | Co-located Gendocen receipts, stale rejection, forced crash 91 + recovery/history; T1 from synthetic bearer writer with rev3→4→5 QRPE | **NOT ACCEPTED**: branch defect, Plan owner/writer, real-user evidence, production snapshots |
| 5 | Legacy Viewer source/tests | New Helper grants UI/Plan editor/timeline/narrative Markdown/external consumer/installed checks |
| 6 | No migrations or deletion | Correctly deferred |

**Особый scope T1:** тестовое EV-T1 реально создано штатным writer через bearer Action.select, by=assistant в synthetic temporary graph. Это не user-approved Action в настоящем графе; позднее F-R и QRPE status=resolved тоже не attested external T2/T3. Восстановление Gendocen вернуло receipts и историю, не переписало technical T1.

**Тестовое evidence до handoff:** после T1 pilot полная Node regression 405/405 PASS, writer 13, adapter 10, Plan 12, impact 20, Canon context 13; при последнем аудите 43/43 scope PASS. Но реальный отрицательный branch audit **не прошёл ожидаемый semantic gate**; прежние PASS не закрывают новый дефект. Не маркировать все EA/WR completed.

## 5. Как воспроизвести обнаруженный дефект (первый P0)

Plan: branch B-RESULT event S-RESULT, outcome positive → S-A1, negative → S-A2.
Подписки Gendocen для двух review ориентированы на Canon/QRPE и timeConstraintsByStep/S-A1,S-A2,S-DELIVERY, но не на branchesById/B-RESULT/cases.

1. Создать две synthetic validated reviews A1/A2 через штатный co-located Gendocen.
2. Обменять массивы stepIds у cases positive и negative, увеличить plan.revision, выполнить projection адаптером; **не** менять deadline/canon/qrpe/actionRef.
3. Запустить check. **Observed:** A1=valid, A2=valid. Семантическая принадлежность исходов Actions поменялась, значит по ним требовалась новая оценка.
4. Исправить dependency registrations/coverage, а не только Gendocen persistence. После fix ожидается review_required у затронутых оценок либо явный fail-closed incomplete coverage, косметический reorder не должен вызывать пересмотр.

Диагностический файл repro-branch-membership-gap.py оставлен отдельно: exit 0 означает воспроизведение БАГА, а не тестовый PASS. Новый tests/rdg-gendocen-branch-membership.acceptance.test.py содержит обычную семантику unittest: на текущем коде meaningful change FAIL, cosmetic projection PASS. После исправления оба должны PASS.

Это относится к исходным v3 WR-31, WR-49/50, EA-18/34. Дополнительно важна historical RDG snapshot: сравнение Plan старой и новой версии против только CURRENT графа не доказывает, что изменилось на T1.

## 6. Исправленный порядок — без изменения смысла требований v3

**P0 — СЕЙЧАС:** определить полную матрицу Plan→RDG semantic reads и Gendocen subscription coverage (branch/case membership, steps/actionRefs, sequence, constraints, Canon, QRPE, Action status, owner/as-of), исправить false valid, добавить негативные тесты и full regression.

**P1:** принять минимальный контракт Temporal Plan owner/version/as-of с candidate vs accepted future paths, unknown dates и отдельной аттестацией реальных событий. Не scheduler.

**P2:** guarded Plan persistence: independent Plan create/edit/branch/event-attest grants, CAS+expectedRevision+revoke-before-commit, failpoints/recovery, history. plan.write != action.select != factual event.attest.

**P3:** завершить Typed Finding/Canon/Proposal semantics и Plan-aware review, preserve late fact about T1 vs change after T1; подтверждённый F-P только с независимым evidence.

**P4:** research graphs S-WORK, two-chat full workflow, one semantic owner promotion/link, hiding/archive/retrieval, saved useful verification without artificial Finding.

**P5:** минимальный пользовательский vertical slice S-AUTH/S-TEMP/S-DEP-REP: Helper grant UI, Plan editor/timeline, Gendocen review, narrative Markdown, Viewer/external consumer; installed verification separate.

**P6:** после решения пользователя canonical GitHub repo/branch/writer — multi-file transactions/ref CAS and remote failure testing; legal engine license and trusted Python review.

**P7:** conditional legacy retirement only after coverage proven.

Приоритеты описаны подробнее в candidate-prework-v4.1-execution-reconciled.md с таблицей всех 53 WR; original full v3 в Приложении A документа и отдельным файлом.

## P0 acceptance — обязательно до расширения продукта

1. Зафиксируй baseline real co-located Gendocen. Проекция Plan через текущий RDG adapter; никакой ручной подмены resource IDs.
2. Переставь stepIds у cases positive и negative: именно outcome-to-Action semantics меняется, constraints/canon/QRPE — нет. Затронутые A1 и A2 не могут остаться valid.
3. Косметически переставь порядок cases, не меняя содержимое. Источник должен сохранить semantic hash и не вызвать лишний review.
4. Проверяй полноту зависимостей для branch membership, steps, actionRefs, sequence и применимых as-of/context facts; избегай full-resource global invalidation без анализа.
5. Включи новый fail-first acceptance test в проверку и добейся двух PASS; только затем scoped и full Node regression. Результаты ранее 405 PASS не доказывают этот контракт.
6. Отдельно проверяй scope: техническое review_required не подтверждает смысловой Finding F-P, bearer receipt не равен пользовательскому утверждению.

## 7. Безопасные команды и checks

В текущем owner repo:

    PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-bearer-package.integration.test.py -q
    PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-gendocen-resources.test.py -q
    PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-temporal-plan.test.py -q
    PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-temporal-impact.test.py -q
    PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-canon-context-review.test.py -q
    PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-problem-evidence-preflight.test.py -q
    PYTHONDONTWRITEBYTECODE=1 python3 tools/rdg-gendocen-runtime-smoke.py --engine-source /workspace/repos/gendocen
    PYTHONDONTWRITEBYTECODE=1 python3 tools/rdg-gendocen-t1-history-smoke.py --engine-source /workspace/repos/gendocen
    node --test --test-concurrency=2 tests/*.test.cjs tools/rd-graph-viewer-smoke.test.cjs

Все runtime smoke работают с temp synthetic sources, а не настоящими пользовательскими graphs. Если environment/source в новом чате иной, сначала inspect mount/root/version/instructions/AGENTS; не пытаться использовать секреты или live user graphs для воспроизведения.

## 8. Что нельзя обещать, менять или случайно принять

- Не менять user graphs/workspaces/*/graph.json, Helper/Viewer installation, Windows, owner GitHub, действительные bearer stores и токены без отдельной авторизации; не загружать приватные файлы в публичный репозиторий.
- Не утверждать, что любой bearer подтверждает личность человека, факт/Problem или пользовательское T1; internal HMAC/receipt — технический след.
- Не считать технический valid/review_required признаком истинности канона/F-P. При отсутствующей зависимости valid может быть ложным.
- Не считать даже strength=hard в candidate Plan подтверждённым FR проекта, не отмечать возможный event как наступивший.
- Не объявлять Stage 4 accepted, потому что crash recovery или 405/405 regression PASS.
- Не делать bulk migration legacy O/D, не удалять Lens/protected истории и не принимать автоматические решения по Plan.
- Не переносить ownership на forfiles, не обещать Git diff там, где RDG нет .git, не заявлять установленный user-visible Helper.
- Не утверждать, что original v3 historical status таблицы описывают текущее состояние; используется v4 overlay.

## 9. Протокол продолжения работы в другом чате

1. Прочитай HANDOFF + v4 + оригинальную v3 и фактологические source/tests. Сверь актуальную файловую систему и grant boundary.
2. Повтори отрицательный Plan branch test, сохрани фактические machine statuses без подмены.
3. Определи схему нужных tracked reads: branch membership, cases/outcomes, stepRefs, sequence и реальные versioned dependencies; обсуди false positives, missing source path fail-closed.
4. Исправь узким prototype change на синтетических fixtures; ничего не записывай в рабочий Graph/Plan.
5. Пройди negative test, cosmetic change, существующие Gendocen runtime+history, writer+Plan suite, при существенном изменении полный regression.
6. Сохрани evidence и открой следующие Plan owner/persistence gates, отделяя применение принятого технического контракта от других пока не выбранных user-facing PR.
7. Обнови v4 execution ledger с текущим результатом, но не изменяй оригинальную v3.

**Если пользователь говорит «продолжай»/«давай дальше», это запрос на actual implementation ближайшего незакрытого P0, не ещё одну обобщённую сводку или невыполнимый future promise.**

## 10. Файлы пакета и происхождение

**Актуальный Pre-work:** candidate-prework-v4.1-execution-reconciled.md; предыдущую v4 считать промежуточным draft. **Матрица evidence:** WR-EVIDENCE-LEDGER.md и JSON. **Проверяемый source snapshot:** source-snapshot/rd-graphs с точными хешами текущих исходников; это материалы для inspection, не заменяющие подключённый owner. **Fail-first тест:** tests/rdg-gendocen-branch-membership.acceptance.test.py, с зафиксированным ожидаемым FAIL до исправления.

## 10.1. Ранее составленный исторический inventory

- HANDOFF.md — данный полный handoff.
- candidate-prework-v4.1-execution-reconciled.md — актуальный исправленный v4 + историческая v3 полным текстом.
- source-candidate-prework-v3-reading-copy.md — точная original v3, SHA Git blob 6da1a3648528c01179bcc792b636f56d6b823901.
- repro-branch-membership-gap.py — negative co-located runtime reproduction.
- README-NEXT-CHAT.md — короткая инструкция/стартовый промпт.
- MANIFEST.json — хеши и inventory; возможно отдельная исходная копия review v1.

**Это transfer package, а не новый canonical commit.** Если другой чат не подключён к Fortis Repo, пользователь должен передать архив или соответствующие документы. Если доступ к окружению есть, достаточно указать директорию /workspace/repos/rd-graphs/docs/handoffs/rdg-prework-v4.1-final-20261018.
