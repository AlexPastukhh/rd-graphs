# Final Review v1 — первый выполненный этап RDG: bearer grants и Gendocen projection

**Review ID:** R-RDG-PILOT-20261018/v1  
**Дата среза:** 2026-10-18. **Тип:** независимый review выполненной работы; reading copy / not canonical.  
**Источник проверки:** живое дерево `/workspace/repos/rd-graphs` в Fortis Repo, SHA-256 проверяемых файлов ниже; Candidate Pre-work `CPW-RDG-INTEGRATED-20261018-01/v2` ([reading copy](https://github.com/AlexPastukhh/forfiles/blob/main/artifacts/2026-10-18/candidate-prework-rdg-integrated-authority-gendocen-representations-20261018-v2.md)), статус **CANDIDATE, NOT BASELINE COMMITTED**.  
**Независимая запись в проект:** не выполнялась. Репозиторий `forfiles` хранит только данный исторический обзор.

## Краткий результат / Для пользователя

**Вердикт: PARTIAL / CORRECTIONS REQUIRED BEFORE AUTHORITY PILOT ACCEPTANCE.** Проверены фактически реализованные `tools/rdg-authority.py`, изменения `tools/graph-package.py`, `tools/rdg-gendocen-adapter.py`, новый тест и README. Не оценивались как завершённые будущие стадии Findings, research graphs, installed Helper/Viewer и remote GitHub.

Изолированный end-to-end сценарий **создать граф → отказать в иной операции без побочного эффекта → изменить grant → разрешить → отозвать → отказать** прошёл. Однако подтверждены Problems:

- **F-P-RV-01 — семантическое повышение прав через создание графа:** bearer с одним `graph.create` создаёт legacy `Decision(status=committed)` с `decision_selected`, без отдельного права на выбор. **HIGH User Review Priority**, intervention **NEXT**. `PR-RV-01` / `PR-RV-06A/B`.
- **F-P-RV-02 — отзыв не синхронизирован с commit:** отозванный между `prepare()` и публикацией grant не останавливает публикацию. Условие воспроизведено. **HIGH**, intervention **NEXT**. `PR-RV-02`.
- **F-P-RV-03 — тесты не доказывают интеграцию writer:** новый тест запускает только CLI выдачи токенов, не `graph-package.py`. **HIGH**, intervention **NEXT**. `PR-RV-03`.
- **F-P-RV-04 — отказ не всегда называет target:** `AUTH_MISSING_PERMISSION` сообщает операцию и Helper, но не запрошенный путь/область графа. **NORMAL**, intervention **NEXT**. `PR-RV-04`.

Дальнейшие риски: `RDG_AUTH_STORE` необязателен (преднамеренный fail-open legacy mode); в Gendocen projection `resource_id` одинаков для разных графов; сырой `sourceSHA256` меняется при перестановке массива и должен быть исключён из неточно настроенных семантических правил. Отдельная существенная развилка: как bearer должен сочетаться с прежним HMAC signed material-Action path.

**Карта отчёта:** §1 scope и основания; §2 доказательства и повторные тесты; §3 оси и WR/EA; §4 canonical Findings и связанные PR; §5 совместимый маршрут решения; §6 ограничения/Review Log. **Следующий gate:** разрешить семантику creation/approval и acceptance point revoke до расширения прав на реальные графы.

## 1. Target, baseline и сценарная основа

### 1.1. Scope и provenance

Проверяется только реально объявленный предыдущим исполнителем первый инкремент:
1. Локальный эксперимент bearer-grant: `init/issue/amend/revoke/list`, scope+operation check и подключение к writer; без обязательного UI.
2. Read-only JSON projection в контракт `$docengine/data`, `nodesById`/ `edgesById`, исходный JSON не модифицировать.
3. Регрессионная совместимость, тесты и достоверность statements/source state.

**Прямые Needs/FR** из pre-work: `N-01/N-02/N-04/N-05`; **FR-01..05** (управление Helper, bearer для любого чата, отказ до записи, admin API, соразмерность), **FR-08/09/10** (канонический RDG JSON, внешний dependency engine, отсутствие несанкционированной миграции). Helper UI как будущий этап **не объявляется дефектом из-за неготовности на стадии validation-first**.

**Сценарная основа:** Candidate/inferred **S-AUTH** и **S-DEP-REP** из pre-work; *подтверждённого committed DRLD для этих новых capabilities не выявлено*. Для текущей работы нормативно применимы явно выраженная просьба пользователя начать изменения, безопасность старых данных и точная граница stage 1A/1B. Полный желаемый путь Helper→сервис→чат→граф пока не исполнен; отсутствие installed Helper не повышается до F-P по пилотному scope. Слой Work/SRU: `SRU-02/03/04` (часть validation-first) и `SRU-07/08` (read-only overlay spike); другие SRU — вне фактического выполненного target.

**Действительность Candidate Composition:** это не committed baseline RDG. Здесь `satisfied/violated` оценивает соответствие заявленной реализации выбранному **candidate acceptance contract**, а не ретроактивную ошибку старых legacy-функций. Изначальная v7 O/D / candidate-v6 модель не была мигрирована.

### 1.2. Inventory и версия

В Fortis Repo подтверждён mount `/workspace/repos` (9p Windows path), проект `/workspace/repos/rd-graphs`; он **не содержит .git**, поэтому точный git diff/commit родительской версии не подтверждён. README и доступные AGENTS проверены: в проверенных местах файлы AGENTS не обнаружены. Файлы прочитаны, и по их содержимому и текущим SHA установлен объект review.

| Проверяемый файл | SHA-256 2026-10-18 |
|---|---|
| `tools/rdg-authority.py` | `890c41cec36218d1f9d7fb6b122b1a0c595d203fbda3b023d7526eaba9853750` |
| `tools/graph-package.py` | `347e9f6548da52cbbf699f06a9bf3990769b7e6d2c0ecda8d2e3a34bb76eeb51` |
| `tools/rdg-gendocen-adapter.py` | `c53323fd15f83eb04280e783265d8a67a20d7a3045e04b77084e0c75f5106454` |
| `tests/rdg-bearer-authority.test.cjs` | `9d1aec3705d195a1e9c2679928c882e20af27c072312883c1b734a6ab57d2bb6` |
| `README.md` | `286690cd0120d12b4d1a15ccdbf423aac531784f65a78ec3dc33f5177a8e58cf` |

Вызовы: `graph-apply.py` CLI → `graph-package.execute()` → `prepare()` → `require_package_authority()` → `Authority.authorize_package()`. Для material Action mutation остаётся независимая проверка `rdg-v6-action-trust.py`; согласованность и атомарный локальный recovery — в `graph-package.py` / `graph-index.py`. `rdg-gendocen-adapter.py` не вызывается из этих writer-путей. Поиск callers/config в `tools`, `tests`, README не выявил другого пути установки нового bearer guard. Это **не** inventory всех внешних Windows/Helper клиентов.

## 2. Evidence — независимые испытания

**EV-01. Состояние источников:** read-only поиск mount/README/AGENTS/.git, прямое чтение всех пяти названных файлов и `graph-package.py`, сравнение связи API с writer, SHA-256; код не изменён.

**EV-02. Кросс-слой, положительный и отрицательный flow:** скопированы writer и необходимые зависимости в отдельную временную директорию (не `graphs/workspaces` проекта). Bootstrap локального admin, issue ограниченного `graph.create`, запись синтетического Action-model графа — **APPLIED**. Вызов `add_action` без соответствующего grant — `AUTH_MISSING_PERMISSION: graph.add_action; request via Helper`, байты графа без изменений. После `amend` токен `graph.add_action` выполняет запись — **APPLIED**. После `revoke` следующая попытка — `AUTH_TOKEN_REVOKED`, граф byte-identical относительно предыдущего результата. Тот же token принимает любой клиент, способный предъявить его; **реальные два ChatGPT-чата не тестировались**.

**EV-03. Конкурентный отзыв:** в изолированной копии `graph-package.py` тестовый hook оборачивает `prepare()`; после успешной проверки полномочий вызывает `revoke` и возвращает готовую запись. Наблюдалось `REVOKED_BEFORE_COMMIT False`, затем `APPLIED transactionId=race1` и наличие графа. Это управляемая имитация пересечения потоков; непосредственно параллельные ОС-процессы не запускались. Логика возможна, поскольку управление grants использует отдельный lock, а writer не перечитывает grants при фактическом commit.

**EV-04. Семантика `graph.create`:** тестовый bearer с **единственным** `graph.create` создал корректный legacy граф с `Decision(status='committed')` и `event(type='decision_selected', by='assistant')`. Результат `APPLIED transactionId=create_committed`, read-back подтвердил `committed`. Отдельный permission для select/approve не выдавался; bearer-контроль проверял только `create`, а подписанная проверка material Action не запускается в этом legacy сценарии.

**EV-05. Повтор тестов:** адресные `node --test tests/rdg-bearer-authority.test.cjs` — **2/2 PASS**; `node --test tests/rdg-general-graph-api.test.cjs` — **7/7 PASS**. Компиляция `compile(...,'exec')` трёх изменённых Python-файлов — PASS. Старый полный прогон **405/405 PASS** приведён в предыдущем исполнении той же беседы; **не повторялся независимо в этом review**. Он не закрывает отсутствие нового integrated authority test.

**EV-06. Адаптер:** прочитан `tools/rdg-gendocen-adapter.py`; Python вызов `adapt()` в temp: `nodesById` одинаков при перестановке двух узлов, `sourceSHA256` изменился; если поменять `identitySpace`, значение `$docengine.resource_id` всё равно `rdg.graph`. Проверена успешная синтаксическая компиляция. В оригинальной директории RDG файлы `graph.json` не изменялись.

**EV-07. Gendocen runtime:** `importlib.util.find_spec('docengine')` возвращает False в доступном Python окружении. Настоящая регистрация dependency rules, `review_required`, `review_context_id`, Markdown materialization, drift и project Python trust **не перепроверены в этом review**. Сведения из раннего эксперимента в предыдущем ответе не заменяют текущий runtime test.

**EV-08. Публикация/установка:** доступный текущий `forfiles` — **private**, разрешён для reading-copy отчёта. Git history фактического RDG отсутствует в том mount, source-mode не равен установленному Helper/Viewer; ничего не устанавливалось и реальные графы не изменялись.

## 3. Review axes и статусы WR/EA

### 3.1. Оси → evidence / вывод

| Ось и проверяемый вопрос | Evidence | Вывод |
|---|---|---|
| Target, version, constraints, candidate status и source ownership? | EV-01, plan v2, §1 | Ограничено отсутствием project .git; scope восстановлен |
| Admin grant lifecycle без самоповышения? | EV-02, EV-05, `Authority.manage()` | Частично выдержало; локальный CLI не Helper UI |
| Разрешённая запись / отказ без побочных эффектов? | EV-02 | Выдержало для описанного последовательного сценария |
| Семантические границы `create` vs `select/approve`? | EV-04 | **F-P-RV-01** |
| Revoke/amend при гонке проверки с записью? | EV-03 | **F-P-RV-02** |
| Удобство и полнота отказа, target/scope? | EV-02, `authorize_package()` | **F-P-RV-04** |
| Существующий trust HMAC и соответствие bearer? | `graph-package.py:75..98`, `rdg-v6-action-trust.py` | **F-U-RV-01**: один токен не заменяет MAC |
| Тесты охватывают реальные изменение/отказ/ревизию? | EV-05, прочитан тестовый файл | **F-P-RV-03** |
| Совместимость старого API и отсутствие миграции? | EV-05, EV-01 | Адресная регрессия выдержала; full baseline regression не повторена |
| Прямой JSON projection, стабильный ID, исходный файл не меняется? | EV-06 | Выдержало как read-only transform; **F-R-RV-02** для будущего multi-graph |
| Реальная зависимость Gendocen, semantic invalidate, stale packet? | EV-07 | **Не проверено**: adapter не dependency integration |
| Нет скрытого source/install/push и излишней сложности? | EV-01/08; README | Выдержало в границах заявленного pilot; **F-R-RV-01** для будущего rollout |

### 3.2. Candidate WR statuses (только затронутые)

| WR | Результат относительно выполненного slice; source |
|---|---|
| WR-01/02 | `satisfied in inspected slice / partial historical evidence`: mount, README и legacy safety сверены, Git diff недоступен (EV-01). |
| WR-03 | `unverifiable / deferred stage`: Helper UI отсутствует, Stage 5; CLI не эквивалентен Helper. |
| WR-04 | `partially satisfied`: bearer переносим без identity чата; работа двух настоящих чатов не тестировалась (EV-02). |
| WR-05 | `partially satisfied`: issue/list/amend/revoke в локальном API есть, реальные Helper user-auth и network endpoint отсутствуют (EV-05). |
| WR-06 | `satisfied for tested delegation`: limited admin ceiling, root immutable (EV-05); гонки управления grants не тестировались. |
| WR-07 | `violated in revoke-before-commit race`: F-P-RV-02; последовательный revoke проходит. |
| WR-08 | `partially violated`: no graph changes при отказе (EV-02), но отсутствует требуемый target/scope в диагностике (F-P-RV-04). |
| WR-09 | `partially violated in semantic creation`: F-P-RV-01; полный permission taxonomy отложен и не объявляется реализованным. |
| WR-10 | `unverifiable / decision fork`: bearer сам по себе не является human approval, MAC ещё необходим для material Action (F-U-RV-01). |
| WR-11 | `partially satisfied`: в локальном store digest, list не выдаёт token, graph не содержит секрет; нет систематического внешнего log audit. |
| WR-12 | `satisfied`: локальный opt-in guard, без претензий на ОС sandbox, README предупреждает. |
| WR-20 | `partially satisfied in legacy existing API`: 7/7 старых Graph API tests, но нет новой полной матрицы bearer на всё содержимое пакета. |
| WR-28 | `satisfied at projection layer`: исходный RDG JSON не требует `$docengine` и не меняется при `adapt()` (EV-06). |
| WR-29 | `partially satisfied`: ID-based `nodesById/edgesById`, array reorder stable по этим полям; semantic rules не зарегистрированы. |
| WR-30/31 | `unverifiable / not implemented in repo slice`: Gendocen runtime, stale context, completeness of declarations (EV-07). |
| WR-34 | `partially satisfied by separation`: adapter только читает; token required for opt-in writer, но end-to-end Gendocen callback не существует. |
| WR-38 | `satisfied no-retirement`: удалений legacy либо O/D migration не выявлено в целевых правках; не означает proof of complete coverage. |
| WR-39 | `violated for claimed guard verification`: F-P-RV-03; 405 old+new regression PASS не доказывают нужную интеграцию writer. |
| WR-40 | `unverifiable for distribution`: установленного runtime нет; зависимости/licensing/side effects требуют отдельного gate перед интеграцией. |

**Прочие WR-13..19, 21..27, 32/33, 35..37** относятся к более поздним SRU либо явно не объявленным как выполненные в этой единице. Их статус **not in completed scope**, не «violated».

### 3.3. Baseline EA и дополнительные оси

| EA | Фактический результат |
|---|---|
| EA-01 | Частично снята: opt-in writer проверяет токен; отключённый режим требует отдельного rollout guard — F-R-RV-01. |
| EA-02 | Факт: bearer не доказывает пользователя; проблемы смешения с MAC остаются в F-U-RV-01. |
| EA-03 | Проверено: самоэскалация delegated admin за ceiling отклоняется (EV-05). |
| EA-04 | **Воспроизведено:** revoke/check/commit race — F-P-RV-02. |
| EA-05 | Денежность/целостность только в последовательном отказе подтверждена (EV-02); exhaustive partial multi-file deny не проверен. |
| EA-06 | Хранение hashed и отсутствие plaintext в синтетическом graph проверены; произвольные логи вне scope. |
| EA-07 | **Воспроизведён** содержательный обход через `graph.create` → committed Decision: F-P-RV-01. |
| EA-08 | Нет автоделегирования OS/GitHub; отдельные API не подвергнуты live изменению. |
| EA-16 | Read-only `$docengine/data` projection работает (EV-06); загрузка в runtime не подтверждена. |
| EA-17 | `nodesById` сохраняется при reorder; raw `sourceSHA256` не сохраняется, нужна точность tracked fields (F-R-RV-02). |
| EA-18..21 | Нет фактического integration evidence; `docengine` не установлен, review_context/licensing/trust gap (EG-RV-01). |
| EA-25 | Отличие source от установленного Helper/Viewer и GitHub сохранено; README явно предупреждает. |
| EA-26..27 | Старые модули не удалялись, pilot сравнительно мал; полный economic assessment новых runtime не готов. |

**Добавленные ситуационные оси:** semantic effect of graph.create (не выводится из одного named operation), shared-lock revoke/commit, stable resource identity for multi-graph, error target completeness, direct writer coverage in new test, historical accepted Decision during bootstrap. Эти оси не создают второй постоянный axis registry.

## 4. Canonical Findings и предложения

Все обозначения `F-*-RV-*` и `PR-RV-*` локальны этой **R-RDG-PILOT-20261018/v1**. `CURRENT/UPSTREAM`, Priority и Next Gate являются оценками для текущего scope/даты. Все новые Proposals: **origin: review; status: pending**. Нет committed решения, реализованного исправления или `resolved` Finding только от публикации этого файла.

### F-P-RV-01 — создание графа позволяет обойти семантическое право выбора

**Type:** Problem; **level:** CURRENT на границе bearer enforcement / **impact upstream** на SRU-02 authority contract; **scenarioBasis:** C (candidate S-AUTH) + прямое user разграничение прав и candidate WR-09/EA-07; **Disposition:** unresolved.  
**Intervention Priority:** NEXT, пилот не развёрнут; **User Review Priority:** HIGH.  
**Evidence:** EV-04; `rdg-authority.py:144..167`, `graph-package.py:85..111`.

**Concrete:** grant `permissions=['graph.create']`, scope `workspaces/new/graph.json` → пакет `create` содержит R0, D1 `status=committed`, `decision_selected` event → `APPLIED` → readback подтвердил принятую D. **Expected из candidate WR-09:** создание нового графа без делегированного права decide/approve не должно само означать право material acceptance. Механизм: bearer guard видит только внешнее `create`, а legacy create validator подтверждает форму события, но не отдельное bearer-разрешение для семантического принятия.

**Связанные PR:**
- **PR-RV-01** — в процессе `create` классифицировать его материализованное содержимое: стартовый пустой/undecided граф и импорт уже принятой истории требуют разных полномочий. **Status pending; Autonomy MEDIUM** (без выбора семантического policy нельзя считать интерфейс окончательным); **Proposal impact: UPSTREAM**. Плюсы: нет обхода, совместимость с source/read; минусы: операция creation станет чуть сложнее.
- **PR-RV-06A** — безопасный default: `graph.create` создаёт новый undecided граф; импорт accepted истории требует специализированного `graph.import_accepted` с provenance/authorization. **pending, USER_REQUIRED, impact UPSTREAM**.
- **PR-RV-06B** — явно документировать, что `graph.create` является расширенным полномочием на импорт исторической принятой записи, и пользователь выбирает такой grant осознанно. **pending, USER_REQUIRED, impact UPSTREAM**, `ALTERNATIVE_TO PR-RV-06A`. Минус: сложнее ограничить полномочия обычных чатов.

**Question (blocking для расширения bearer на реальные graph.create):** является ли создание *пустого графа* отдельным действием от *импорта принятой истории*? Решается семантическим выбором контракта; не мешает самостоятельным тестам. **Next Gate:** согласовать безопасное разделение и написать allow/deny тест содержимого (developer + user для policy).

### F-P-RV-02 — revoke после проверки не блокирует публикацию

**Type:** Problem по candidate WR-07 acceptance gate / EA-04; **level:** CURRENT; **scenarioBasis:** C + FR-03 request-before-write; **Disposition:** unresolved.  
**Intervention Priority:** NEXT; **User Review Priority:** HIGH.  
**Evidence:** EV-03; `graph-package.py:70..74, 263..290`, `rdg-authority.py:102..144`.

**Concrete:** вызывается writer `execute()`; `prepare()` уже проверил bearer → отдельное управление grants отвечает revoke (state `active=False`) → writer без второй проверки сохраняет prepared journal и новый graph. Наблюдалось `REVOKED_BEFORE_COMMIT False` и `APPLIED`. Использованы только синтетические объекты и тестовый hook. **Механизм:** lock файла grants отдельно от writer lock; проверка происходит до durable journal/finish. Поскольку grant может измениться после check, не установлена консистентная граница «полномочия на commit».

**PR-RV-02A** — синхронизировать admin grant mutations и транзакционное принятие writer через однозначный общий lock или атомарный grant-revision check прямо на commit boundary. **pending; Autonomy MEDIUM**, impact CURRENT, нужны fault tests. Плюсы: гарантируемая ревокация по определённой линейной истории; минусы: contention/deadlock риск при неверном порядке lock.
**PR-RV-02B** — фиксировать точку авторизации как начало `prepare()`, допускать уже авторизованную in-flight операцию после revoke и явно показывать это в Helper. **pending; USER_REQUIRED; impact UPSTREAM**, `ALTERNATIVE_TO PR-RV-02A`. Это другая пользовательская семантика revoke, не «молчаливое исправление».

**Question (blocking для production revoke semantics, частично blocking для дальнейшей модели token):** должен ли уже начатый, но ещё не зафиксированный write завершиться после отзыва? Для утверждения production-варианта требуется пользовательское решение о моменте силы отзыва; кодовые регрессионные проверки можно готовить независимо. **Next Gate:** выбрать contract, затем тестировать два процесса / revoke+commit и crash recovery, не только последовательную выдачу.

### F-P-RV-03 — новая автоматическая проверка не проходит через writer

**Type:** Problem относительно Candidate Verification Plan / WR-39; **level:** CURRENT; **scenarioBasis:** D (проверка качества работы ИИ); **Disposition:** unresolved.  
**Intervention Priority:** NEXT; **User Review Priority:** HIGH (ложная уверенность может ускорить преждевременный rollout). **Evidence:** EV-05; `tests/rdg-bearer-authority.test.cjs:1..43`.

Фактически файл тестирует `init/issue/amend/revoke/list` и ceiling, но **не использует** `graph-package.py`, `graph-apply.py` и не утверждает unchanged graph на отказе. Тестовая переменная `request` не используется. Старые 405/405 PASS включают два новых CLI-теста, а не новую permission integration matrix. Независимый EV-02 восполнил **часть** доказательств в ходе review, но не создал повторяемый тест проекта.

**PR-RV-03** — добавить изолированный автоматизированный writer harness (копия нужных modules в temp) с grant issue/amend/revoke, scope, material op, replay, denied unchanged bytes, cross-file denial, race и failure, включая `trustedApproval` cases. **pending; Autonomy HIGH; impact CURRENT; RECOMMENDED_WITH PR-RV-01/02/04**. Малый проверочный сценарий прежде полного E2E, экономит будущий debugging. **Next Gate:** developer добавляет targeted tests и независимый read-back до заявления acceptance.

### F-P-RV-04 — диагностике denied permission не хватает конкретного target

**Type:** Problem относительно candidate WR-08 (полезный отказ); **level:** CURRENT; **scenarioBasis:** C (S-AUTH); **Disposition:** unresolved.  
**Intervention Priority:** NEXT; **User Review Priority:** NORMAL. **Evidence:** EV-02, `rdg-authority.py:144..167`.

Вызов `graph.add_action` для `workspaces/demo/graph.json` возвращает `AUTH_MISSING_PERMISSION: graph.add_action; request via Helper`. Код и missingPermission есть, но **цель и требуемый scope отсутствуют**; для нескольких проектов пользователь не узнаёт, какой именно grant менять, без восстановления исходного запроса.

**PR-RV-04** — возвращать структурированный отказ (`code`, `file/scope`, `operation`, `requiredPermission`, `requestPath`) без токена и секретов. **pending; Autonomy HIGH; impact CURRENT; RECOMMENDED_WITH PR-RV-03**. Издержка — небольшой контракт ошибок и тесты. **Next Gate:** developer проверяет оба denial вида, без утечек credentials.

### F-R-RV-01 — fail-open настройка будет опасна при неподготовленном deployment

**Type:** Risk; **level:** UPSTREAM относительно pilot → production rollout; **scenarioBasis:** C + FR-03; **Disposition:** deferred до Stage 5 / установки.  
**Intervention Priority:** LATER; **User Review Priority:** HIGH. **Evidence:** `graph-package.py:59..67`, README section: без `RDG_AUTH_STORE` вообще нет нового bearer barrier. Сейчас это **преднамеренная и документированная совместимость**, не текущий дефект stage 1A.

**Механизм будущего риска:** включить UI в Helper или заявить token enforcement, но не настроить `RDG_AUTH_STORE` у действительного writer; старый API продолжит принимать операции, где их допускают прежние правила, без нового токена. **PR-RV-05** — при production интеграции явный protected-mode/fail-closed startup self-check, отдельный legacy compatibility route; **pending, MEDIUM, impact UPSTREAM**. Trade-off: требует контроля roll-out и миграции клиентов. **Next Gate:** отложить до отдельного решения о переходе на установленный writer; перед релизом proof of denied unauthenticated mutation.

### F-R-RV-02 — одинаковый Gendocen resource ID и нестабильный raw digest

**Type:** Risk для следующего шага Stage 1B; **level:** CURRENT на адаптер / UPSTREAM impact для multi-graph runtime; **scenarioBasis:** C (S-DEP-REP); **Disposition:** unresolved.  
**Intervention Priority:** NEXT перед multi-graph loading; **User Review Priority:** NORMAL. **Evidence:** EV-06; `rdg-gendocen-adapter.py:27..33`.

Два разных RDG-графа с разными `identitySpace` проецируются под одним `$docengine.resource_id='rdg.graph'`; если Gendocen требует уникальных resource IDs в одном проекте, могут возникнуть коллизия или недостоверное provenance. При простой перестановке `nodes[]` stable `nodesById` прежний, однако сырой `sourceSHA256` иной: если будущий review rule отслеживает именно digest, возникнет ложный сигнал. **Коллизия в реально запущенном Gendocen ещё не воспроизведена**; Risk, не Problem. 

**PR-RV-07** — дать ресурсу уникальную стабильную identity на основе подтверждённого owner/path/identitySpace + безопасного resource naming; использовать `nodesById` для field-level semantic dependencies, отдельно учитывать raw SHA для byte-exact provenance; настроить правила + comparative runtime tests. **pending; Autonomy MEDIUM; impact CURRENT**, `RECOMMENDED_WITH` integration gate Stage 1B. Цена — небольшой mapper/contract, вместо второй базы dependency engine. **Next Gate:** developer должен проверить реальный Gendocen resource loader и зарегистрировать правила в изолированном проекте.

### F-U-RV-01 — bearer и существующее HMAC: два жизнеспособных контракта

**Type:** Decision Uncertainty; **level:** UPSTREAM (SRU-02/04); **scenarioBasis:** C + explicit bearer intention; **Disposition:** unresolved.  
**Intervention Priority:** NEXT до полного material Action rollout; **User Review Priority:** HIGH.

**Known:** token guard включается по `RDG_AUTH_STORE`; для `select_action/link_action_requirement/reconsider_action/transition_qrpe/graph_edit` по-прежнему обязательно `trustedApproval` с HMAC issuer key и совпадающим attribution. Токен со scope правом поэтому **не достаточен сам по себе** для этих операций в текущем прототипе. Подпись issuer *не является* подтверждением идентичности пользователя.

**Fork / Proposal:**
- **PR-RV-08A:** после проверки bearer доверенный writer сам формирует или получает доверенное transaction approval, сохраняет legacy HMAC как внутренний целостностный шаг; требует trusted grant administrator/service, меньше migration риска. **pending; Autonomy LOW, impact UPSTREAM**.
- **PR-RV-08B:** новая bearer-based material write policy с доказательным transaction receipt; старый HMAC путь оставить только legacy-compatible или поэтапно заменить после тестов. Меньше двойных credentials в UX, выше цена пересмотра guard и regression. **pending; Autonomy LOW, impact UPSTREAM; ALTERNATIVE_TO PR-RV-08A**.

**Question (partially blocking):** какой actor/provider достоверно утверждает user-only решения и как он связан с bearer grant, без фиктивного `by:'user'`? Блокирует *полную* модель material Action, не блокирует read-only Gendocen и synthetic `add_action`. **Next Gate:** отдельное пользовательское решение после технического сравнения ошибок/усилий, не хранить issuer key в выдаваемом чату bearer.

### F-U-RV-02 — смысл grant `graph.create` и исторического импорта

**Type:** Decision Uncertainty; **level:** UPSTREAM на authority scope; **scenarioBasis:** C; **Disposition:** unresolved.  
**Intervention Priority:** NEXT до общего контракта create; **User Review Priority:** HIGH. **Evidence:** EV-04; связывает F-P-RV-01.

**Fork:** защищённая модель fresh graph (`PR-RV-06A`) против широкой модели historical import (`PR-RV-06B`), с различными требованиями к пользовательскому одобрению и происхождению событий. **Question blocking** для final acceptance of create semantics, не для проверки алгоритмов. **Next Gate:** пользователь определяет семантику; разработчик может предложить безопасный default A и отдельный разрешённый import, без изменения legacy данных.

## 5. Candidate Resolution Composition, отношения, затраты и route

**Все PR-RV pending; ни один не committed и не реализован.**

**PG-RV-AUTH (HARD_BUNDLE для *заявления полного* accepted authority validation slice, не одна обязательная code patch):** `PR-RV-01` + выбранная `PR-RV-06A|06B`, `PR-RV-02A|02B`, `PR-RV-03`, `PR-RV-04`. Обоснование: без одного из эффектов остаётся смысловой privilege bypass, гонка, непроверенный путь или непригодный отказ; последовательное внедрение допускается, но не следует принимать отдельную часть как completed S-AUTH. 
**PG-RV-TRUST (ALTERNATIVE_GROUP):** `PR-RV-08A|08B` на поздний material-Action gate, REQUIRES согласованный authority policy и полноценные negative tests. 
**PG-RV-DEP (SOFT_BUNDLE):** `PR-RV-07` с реальным Gendocen runtime+rules, может идти параллельно исправлениям bearer. 
**PR-RV-05** — deferred rollout guard, RECOMMENDED_WITH PG-RV-AUTH перед установленной интеграцией.

**Рекомендованный маршрут:**

1. **Acceptance contract — отдельная transaction выбора.** Установить `graph.create` vs `import accepted` и семантику in-flight revoke; `PR-RV-06A/06B`, `PR-RV-02A/02B`, F-P-RV-01/02, F-U-RV-02. *Gate:* согласованный default и негативные сценарии. До решения можно независимо разработать безвредные targeted тесты.
2. **Минимальный ремонт bearer guard.** `PR-RV-01 + PR-RV-02A (если выбран) + PR-RV-03 + PR-RV-04`; подготовить reject без частичной записи, legacy/nested operations и replay/recover сценарии. *Gate:* синтетический end-to-end + race + negative semantic history + readback, без claims production.
3. **Material-action trust fork.** `PR-RV-08A/B`, F-U-RV-01; до удаления legacy HMAC обязательна совместимость и faithful event attribution. *Gate:* trusted approval схема и regression material graph operations, no self-authority. Отдельная transaction не должна требовать заранее коммитить Stage 3..5.
4. **В параллельной независимой ветви — Gendocen.** `PR-RV-07`: проверить loader/unicity/licensing/runtime, зарегистрировать field-level semantic rules, проверить false invalidation и stale review context, затем Markdown source version. *Gate:* actual `docengine` test and source unchanged. Подключение адаптера ≠ успешное завершение Stage 1B.
5. **До пользовательского release.** `PR-RV-05`: Helper UI и production configuration, fail-closed guard для нового writer с явным legacy lane; отдельно установленный Windows environment и user control. Live GitHub owner и графы не изменять до соответствующего согласования.

**Work value и cost/timing:** сейчас оправданы небольшие отрицательные тесты и точечный контракт: они исключают преждевременную безопасную «галочку» при сравнительно малых затратах и избегают rework широкой реализации. Полный security framework и complete Helper UI сейчас были бы преждевременны. Сравнение staged vs full-now: staged сохраняет существующий writer и legacy, но оставляет временную двойную схему grants/HMAC; full-now добавит риск переопределения прав и миграций. **Effort/elapsed/deadline** количественно неизвестны: пользователь не устанавливал hard deadline, ресурсная оценка отсутствует; не приписывать проверкам календарный срок.

## 6. Evidence Gaps, User Assistance, Review Log

### Evidence gaps / limitations

- **EG-RV-01 — реальный runtime Gendocen отсутствует** в текущем Python `docengine` search; независимая полнофункциональная проверка Stage 1B невозможна без отдельного доступного isolated runtime. Старые заявления о `review_required` не считаются репродукцией текущей интеграции.
- **EG-RV-02 — installed Helper/Viewer и реальные chat credentials не проверялись**; отсутствие UI отнесено к будущей стадии, но никакой пользовательский end-to-end не принят.
- **EG-RV-03 — проектный .git отсутствует** в актуальном RDG mount. Diff относительно предыдущего committed tree не установлен, проверена только читаемая версия и хэши файлов.
- **EG-RV-04 — полная mutation-matrix/race multi-process не выполнена**, хотя направленные контрпримеры и синтетические tests есть. Старый полный 405/405 не повторялся; новые targeted tests не являются security proof.
- **EG-RV-05 — license/third-party execution trust Gendocen** не проверены для реального distribution; использование proprietary archive нельзя считать разрешённым только из технической возможности чтения.

**User Assistance:** на этом этапе пользовательского файла/секрета/Windows-доступа не требуется. Материальные будущие решения F-U-RV-01/02 и политика отзыва F-P-RV-02 могут потребовать выбора пользователя перед изменением contract; независимые тесты могут быть подготовлены без него.

### Review Log (один индекс, не второй owner)

`R-RDG-PILOT-20261018/v1` | target: пять локальных source/test/doc файлов, partial Stage 1A+1B. Итог: **PARTIAL / corrections required**.  
**Confirmed Problems:** F-P-RV-01, F-P-RV-02, F-P-RV-03, F-P-RV-04 — unresolved.  
**Risks:** F-R-RV-01 — deferred до release gate; F-R-RV-02 — unresolved до Gendocen runtime proof.  
**Decision Uncertainties:** F-U-RV-01, F-U-RV-02 — unresolved.  
**Proposals:** PR-RV-01, PR-RV-02A/B, PR-RV-03, PR-RV-04, PR-RV-05, PR-RV-06A/B, PR-RV-07, PR-RV-08A/B — all pending; PG-RV-AUTH / PG-RV-TRUST / PG-RV-DEP candidate only.  
**Evidence:** EV-01..EV-08; **limitations:** EG-RV-01..05.  
**Upstream / next gate:** align `graph.create` permission with semantic Decision authority, define revoke linearization, choose bearer+HMAC relation before installed Helper rollout.  
**Final prompt meta-checkpoints:** target remained executed slice; candidate ≠ committed preserved; no source/graph writes; tests named with observed counts; F types vs evidence gaps separated; publication/readback checked separately; no claims full Gendocen/runtime/Windows coverage.

**Reading copy / not canonical; no graph edit, no PR acceptance, no baseline commit.**
