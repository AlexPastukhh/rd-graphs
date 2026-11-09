# Final Review — R-RDG-LARGE-STEPS-20261019-01/v1

Reading copy / not canonical. Срез: 2026-10-19, Asia/Bangkok. Статус проверенной реализации: Candidate; Stage 4 NOT ACCEPTED.
Target: завершённые крупные пакеты RDG — глубокие предварительные ветви, Action-instance/Plan API, ручной Viewer/Helper и межфайловая завершённость. Это review реализации, не meta-review прежнего отчёта.

## Краткий результат

Основные графовые сценарии выдержали адресную повторную проверку. Найдены две подтверждённые проблемы ручного редактирования времени: изменение даты может стереть зависимость другого шага и удалить другие временные ограничения. До цельного ручного прогона следует исправить этот путь. Настоящий Windows/G2 браузер не проверен.

Обе находки — CURRENT, User Review Priority HIGH, Intervention Priority NEXT. F-P-01: дата A меняется, но связь «B после A» исчезает либо запись отклоняется. F-P-02: та же операция удаляет deadline и меняет hard на soft. Связанный PR-01 — сохранить не редактируемые пользователем части расписания; status pending, Decision Autonomy HIGH, Proposal impact CURRENT. Решение модели графа для этого менять не требуется.

Повторно прошли 55 Python tests и 6 UI-controller cases; 2 live-Helper cases в Node-наборе пропущены. Три новых контрпримера воспроизвели дефекты, а не подтвердили исправление. Код и рабочий план в этом review не изменены.

Что в отчёте: «Target и baseline» отделяет прежние Candidate-идеи от действующих указаний; «Оси, WR и EA» показывает покрытие; «Findings» содержит ситуации и причины; «PR-01 и маршрут» задаёт небольшой исправляющий пакет; «Ограничения» отделяет локальные тесты от Windows и Gendocen.

## Target и baseline

Рабочий owner: `/workspace/repos/rd-graphs`. Перед проверкой подтверждены прямой доступ и RW-монтирование `/workspace/repos` из Windows. `/workspace/repo` — другой контур. `.git` отсутствует; `git status` вернул 128. Полнота чужих изменений вне выбранного набора не установлена. Mounts, ACL, общие сервисы и полномочия не менялись.

Проверен source Viewer 2.2.0 и действующие исходники, а не установленный Tampermonkey. Все 22 файла последнего CPW-RDG-CROSS-FILE-COMPLETION-20261019/v1 совпали с его SOURCE-HASHES.json. Для всего target и существенных зависимостей сохранены 32 SHA-256 в `docs/handoffs/rdg-large-steps-review-20261019/TARGET-HASHES.json`; SHA-256 этого manifest: `6f98bd4ad7d88b8e651da93d69bd28e64c781344a320843721ab48393966b621`. Перед завершением проверено отсутствие изменений этих файлов.

Прочитаны действующий `docs/guides/RDG-CURRENT-EXECUTION-PLAN.md`, README, SCOPE/CHECKPOINT пакетов `rdg-instance-temporal-workflow-20261019`, `rdg-manual-workflow-20261019`, `rdg-cross-file-completion-20261019`; релевантные разделы model/writers/readers/Helper/UI, их callers и тесты.

Исторический pre-work: `docs/handoffs/rdg-prework-v4.1-final-20261018/`. Его HANDOFF, WR-EVIDENCE-LEDGER и original v3/v4.1 остаются Candidate, не whole-baseline committed. Номера WR/EA ниже — ссылки на этот источник, не новые утверждённые требования. SRU-контекст: локальные части SRU-01/04/05/09/10/11/12; весь их первоначальный scope не объявляется реализованным.

Действующие ясные указания пользователя: один Action — один экземпляр; глубокое построение без выбора предков; создание не размещает во времени; размещение задаёт время и/или порядок; результат без размещения сразу виден в истории; исполненный Action сохраняется; отзыв старого варианта и выполнение другого сохраняются отдельно; subgoal и method_correctness имеют разные условия завершённости; человек и ИИ работают с теми же owners и правами.

Принятого полного DRLD в прочитанных owner-источниках не установлено: v4.1 §3 прямо называет S-AUTH/S-WORK/S-DEP-REP/S-TEMP candidate/inferred. Для обязательных переходов использовано scenarioBasis B: прямые пользовательские указания и безопасное редактирование действующих owners. Размещение → изменение только показанной даты не даёт разрешения удалять чужую sequence-связь или невидимый deadline. Удобный UI-маршрут целиком не повышен до FR. Автоматические knownAt/effectiveAt baseline, повторные физические исполнения и трёхстадийная регистрация внешних событий исключены позднейшими уточнениями; они не возвращены как условия проверки.

## Оси, WR и EA — фактическое покрытие

Предварительные оси сформированы до содержательных проб: глубокие ветви; явное размещение; результат/история; ручной путь; межфайловые owners/права; качество evidence и статусов. После чтения Helper добавлена адресная ось сохранности не показанных UI частей расписания.

| Ось и применимость | Что фактически проверено | Вывод |
|---|---|---|
| Можно ли глубоко строить R/Actions, каноны и QRPE без выбора предков? Это центральный пользовательский путь. | Чтение model/API; 24 deep-action tests; cross-file test глубокого выбора. | Выдержала локальную проверку; выбор потомка не активирует предка. |
| Размещение явно и безопасно меняет время/порядок? Plan не должен выбирать Action. | Workflow place/unplace, sequence-only, Plan CAS; отдельные новые Helper-пробы правки даты. | Основной API работает; F-P-01/F-P-02 в адаптере ручной правки. |
| Не смешаны ли выбор, выполнение и достижение? Сохраняются ли те же ID и факты? | 13 workflow tests и deep-action: unscheduled result, A1 → отзыв → A2, правка после исполнения, две роли R. | Выдержала локальную проверку; нового исполнения того же ID нет. |
| Согласованы ли владельцы, проекции, права и восстановление? Иначе цель может получить ложный успех. | 18 cross-file tests: оба вида R, snapshot owner, denied read/result write, duplicate/cycle, source race, частичный journal, revoke/recovery, реальный read lock. | Выдержала в объявленном одном Graph root/candidate-v6 scope. |
| Доступен ли ручной путь и сохраняет ли он пользовательские данные? | UI-код и 6 controller cases; новые пробы через настоящий Editor и writers. | Два подтверждённых дефекта; native picker/браузер не проверены. |
| Не преувеличены ли сделанное, публикация и acceptance? Проверяется работа ИИ. | Хеши, текущие статусы плана/CP, свежие логи, read-back отчёта. | Локальный Candidate отделён от установки; повтор всего широкого прогона не заявлен. |

Релевантные WR исходного Candidate pre-work, только в проверяемой части:

| WR / provenance | Статус в этом scope | Evidence |
|---|---|---|
| WR-07 — актуальные grants и acceptance boundary; FR-01/03 в original v3 | satisfied, локальные проверенные операции | Cross-file deny/revoke/replay/recovery tests. Полная матрица всех операций не проверена. |
| WR-08 — отказ до изменения; explicit user | satisfied для проверенных отказов | Workflow/CrossFile сравнивают источники после deny; новая неудачная правка даты также не изменила Plan. |
| WR-09 — разные виды прав; user chronology | satisfied в проверенном локальном пути | Read/result write проверены отдельно, проекция не расширяет authority. |
| WR-19 — выбран / выполнен / достигнуты раздельно; user model | satisfied | Deep-action/workflow/cross-file, исходные ID и история. |
| WR-20 — общий Graph API; user request + pilot | satisfied в проверенных Graph-операциях | Deep-action/workflow/cross-file; все CRUD/edge/canon операции исчерпывающе не проверялись. |
| WR-35 — согласованная запись/recovery; existing architecture | satisfied для local multi-file части | 18 cross-file cases. Remote concurrency вне этого review. |
| WR-37 — Helper/Viewer и отдельный installed proof; user direction | unverifiable целиком; локальная часть проверена | UI source/controller; настоящий браузер, installed Helper и управление grants через GUI не проверены. |
| WR-39 — доказанные проверки/версии/read-back; operational constraints | satisfied для этого review; не production acceptance | Адресные логи, source hashes, явные ограничения и подтверждённая запись отчёта. |
| WR-45 — отдельный Plan owner; direct user | satisfied в локальном scope | Plan identity/history отдельно; размещение не меняет graph bytes. |
| WR-46 — временные связи/предшествование; user direction | violated в сохранении порядка при ручной правке | F-P-01. Полная precision/window/timezone матрица не повторялась. |
| WR-48 — stable Graph refs без копии/выбора; direct user | satisfied в проверенном scope | Те же IDs/owners, mismatch отказ, candidate не становится selected от placement. |
| WR-49 — различать strength и provenance; direct user | violated в сохранении metadata ручным редактором | F-P-02. Полная оценка Canon/Finding относительно ветвей отдельно не проверена. |
| WR-51 — Plan permission не даёт Graph selection; direct delegation | satisfied для проверенных ролей | Workflow отдельные права Plan/Graph, cross-file result-write denial. |
| WR-52 — перепланирование сохраняет прошлое; прежние FR + новый Plan | satisfied для проверенных history transitions | A1/result/withdraw/A2, неизменность graph при placement. Полный исторический temporal-as-of не проверен. |
| WR-53 — читаемое представление без обязательного executor; user direction | satisfied в локальном scope | JSON/Markdown/HTML workflow, executor не введён. |

WR-21/38 и EA-13/26 о физической миграции/retirement не применены как задача этого review: замены legacy здесь нет. Прежняя широкая регрессия 259 Python + 413 Node PASS/2 SKIP относится к исходному checkpoint и не выдана за заново выполненную.

Исходные candidate EA: EA-04/05/07 проверены адресными deny/revoke/partial-write/policy тестами — в этих случаях механизм не проявился. EA-10 проверена разделением выбора и результата; EA-23 — owner pins, identitySpace и read lock; EA-25 — source/installed/publication статусы. EA-13/26 вне scope миграции. EA-29 использует тот же acceptance/revoke evidence; EA-30/33/35 проверены стабильными refs и раздельными Plan/Graph permissions. EA-32 не даёт основания считать Candidate hard-метку реальным обязательством; полная timezone/precision часть не проверена. EA-34/Gendocen отдельно вне scope; EA-36 проверена отсутствием нового executor/lifecycle. Новая ситуационная ось — безопасный круг чтение → изменение одного поля → сохранение: она дала F-P-01/F-P-02. Список EA не принят автоматически за полный.

## Findings

### Правка даты стирает зависимость другого шага — Проблема F-P-01

Target: `manual workflow → Helper.dispatch(place) → Plan.apply_placements`. Level CURRENT. User Review Priority HIGH: затронут обычный смысл плана. Intervention Priority NEXT: исправить перед цельным ручным прогоном; обязательного дедлайна или необратимой потери в проверяемом synthetic состоянии нет. Disposition unresolved. scenarioBasis B: явное планирование по времени/порядку и изменение только запрошенных данных; релевантная часть WR-46.

**Ситуация.** A размещён на 20 октября. B размещён после A; у B также есть своя дата. Пользователь у A меняет только дату начала на 22 октября и сохраняет. Операция успешна, но `sequence` меняется с `[{before:'S-A1', after:'S-A2'}]` на `[]`. Условие «B после A» потеряно без отдельного выбора пользователя.

Если у B нет своей даты и задан только порядок после A, изменение даты A вместо этого завершается `TEMPORAL_PLAN_ACTION_STEP_NOT_PLACED`. Plan остаётся прежним. Пользователь не может выполнить нормальную правку даты.

**Причина.** UI отправляет `afterStepId` редактируемого шага. Helper всегда передаёт `sequence: []` либо только его входящую связь. `apply_placements` трактует этот список как полную замену всех связей, где участвует шаг, включая исходящие связи других шагов. Полный replace-контракт допустим для API; адаптер не сохранил части, которые пользователь не редактировал.

**Доказательства.** `tools/rdg-workflow-ui.js:178–188`; `tools/rdg-workflow-helper.py:187–201`; `tools/rdg-temporal-plan.py:237–241`. Независимый воспроизводимый probe: `docs/handoffs/rdg-large-steps-review-20261019/probe-placement.py`, результат `probe-placement.log`. Обе ветви выполнены через настоящий Editor и guarded writers во временных owners; graph bytes не изменились.

Связанный **PR-01** описан ниже: pending, Autonomy HIGH, impact CURRENT. Next Gate: помощник реализует сохранение исходящих связей и проверяет оба случая до нового ручного acceptance. Вопроса к пользователю о смысловой модели здесь нет.

### Правка даты удаляет deadline и меняет strength — Проблема F-P-02

Target: `manual workflow → Helper.dispatch(place) → timeConstraints`. Level CURRENT. User Review Priority HIGH, Intervention Priority NEXT, Disposition unresolved. scenarioBasis B: общий ручной/API owner и безопасная правка показанного поля; релевантная часть WR-49. Это текущая потеря данных, не гипотетический риск.

**Ситуация.** В допустимом Candidate Plan у A сохранены `notBefore 2026-10-20 / hard` и `deadline 2026-10-25 / hard`. Через Helper изменяется только показанная дата начала на 21 октября. Операция сообщает saved=true. После неё остался один `notBefore 2026-10-21 / soft`; deadline исчез.

**Причина.** Поле UI показывает только notBefore. Helper создаёт новый единственный constraint с strength=soft и передаёт его как полный список `timeConstraints`. Writer правильно заменяет список для этого шага, но пользователь не выбирал удаление deadline или смену strength. Метка hard в Candidate Plan не объявляется committed обязательством: подтверждённый дефект — утрата сохранённых данных и смысла.

**Доказательства.** `tools/rdg-workflow-ui.js:142–144,188`; `tools/rdg-workflow-helper.py:194–197`; `tools/rdg-temporal-plan.py:230–236`. Независимый probe: `probe-constraints.py` и `probe-constraints.log` в той же папке evidence; before/after выше получены настоящими writers.

Связанный **PR-01**: pending, Autonomy HIGH, impact CURRENT. Next Gate: сохранить невидимые constraints и метаданные либо явно отказать при непредставимом формате, затем проверить новый контрпример. Пользовательское решение об удалении deadline не требуется и не предполагается.

## PR-01 и рекомендуемый маршрут

**PR-01 — безопасная ручная правка размещения.** Origin review. Status pending. Traceability F-P-01/F-P-02 → WR-46/49 и явное ручное редактирование общего Plan. User Review Priority HIGH; Decision Autonomy HIGH; Proposal impact CURRENT. Выбор технический: не затрагивает Need, scope продукта, модель экземпляра Action или принятие Scenario.

Предлагаемый небольшой пакет:

1. Для существующего размещения сохранять исходящие sequence-связи; изменять только представленный UI входящий порядок. В API не менять значение полного replace без отдельного основания.
2. Сохранять deadline и прочие не редактируемые constraints. Для редактируемого notBefore сохранять strength и поддерживаемые метаданные. При нескольких/непредставимых правилах выдавать явный отказ с переходом к полному API; не обрезать их.
3. Проверить A → B с датой B и только с порядком; существующие deadline/hard; новое простое размещение и явное изменение/снятие порядка; CAS/deny/read-back. Проверить фактический запрос UI, не только функцию replace.

Отношения: одна canonical запись PR решает обе находки; REQUIRES/conflicts/PG не нужны. Альтернатива полного календарного редактора сейчас не оправдана. Временный отказ всех сложных размещений уменьшил бы риск потери данных, но не устранил бы обычный сбой A → B и добавил бы ручную работу через API.

Cost/Timing Delta — качественно, без придуманной оценки часов: текущий путь требует восстановления потерянных связей/ограничений либо блокирует правку; локальное сохранение не редактируемых полей убирает эту работу. Реализация затрагивает небольшой адаптер и его проверки; новый scheduler, schema или инфраструктура не нужны. Полный editor дороже в разработке и поддержке. Hard deadline не задан; календарная оценка и buffer не определялись.

Recommended Candidate Composition: {PR-01}; нерешённых альтернатив, конфликтов и unsatisfied REQUIRES не обнаружено. Это кандидат, не committed Composition и не Git commit. Порядок: рассмотреть PR-01 → реализовать один согласованный пакет → повторить контрпримеры и адресную регрессию → проверить native Windows/G2 маршрут. Gate между исправлением и native прогоном — сохранность исходного порядка и constraints по read-back. В рабочий план этот маршрут review не записан; предлагается поставить его перед текущим Windows/G2 шагом.

## Что выдержало проверку, ограничения и помощь пользователя

Заново выполнены: deep-action 24/24; workflow 13/13; cross-file 18/18; UI-controller 6 PASS, 2 SKIP из 8. Всего 55 Python tests; наборы здесь не удваиваются с прежней широкой регрессией. Логи: `deep-action.log`, `workflow.log`, `cross-file.log`, `ui-controller.log`; команды и exit codes сохранены в review evidence. Exit 0 независимых probe означает BUG REPRODUCED, не resolved Findings.

EG-01 / Review Limitation: native File System Access picker, реальная читаемость UI, Windows/G2 эффективные права, installed Tampermonkey и цельный живой пользовательский путь не проверены. Node DOM имитируется; два требующих live Helper сценария не повторялись в этом review. Прежний checkpoint содержит их локальное controller evidence, но это не независимый native proof. Следующий gate — реальный browser прогон после PR-01.

EG-02 / Review Limitation: новый полный Gendocen Canon context, произвольные legacy/remote owners, миграция и все возможные исключения не проверялись: пользователь ограничил review очевидными препятствиями основным сценариям. Для completion остаётся объявленная граница одного Graph root, published candidate-v6 owners и read scopes всех workspace-файлов затронутого identitySpace. Это не новая найденная Problem.

Оригинальные семь исторических файлов и весь внешний чат не перечитаны; применены действующие ясные сообщения, owner-документы и сохранённые Candidate baseline. Более новая посторонняя версия этих крупных шагов не найдена в доступной проверенной линии; полный внешний поиск всех историй не выполнялся.

Нового upstream Finding, Risk, Decision Uncertainty или Opportunity с достаточным основанием не установлено. Отсутствие новых записей этих типов не доказывает их отсутствие во всём проекте. Тайм-ауты/тесты, не влияющие на основные сценарии, дополнительно не исследовались.

User Assistance сейчас не нужна: для PR-01 достаточно доступных исходников и воспроизводимых данных. Позже для native прогона потребуется эффективный G2-доступ к той же разрешённой папке сессии и обновлённый Viewer; права владельца, новые mounts/ACL/туннели не предполагаются. Без этого независимая работа по исправлению продолжается.

## Review Log

R-RDG-LARGE-STEPS-20261019-01/v1; source Viewer 2.2.0; 32 файла target/dependencies зафиксированы хешами. Итог: два unresolved CURRENT Problems F-P-01/F-P-02, один pending PR-01. Обе находки требуют внимания HIGH и запланированного вмешательства NEXT перед native прогоном; нет подтверждённого срочного дедлайна. Recommended Candidate Composition и gate — в разделе PR-01; принятия/исполнения/устранения не заявлено.

Доказательства: 55 Python и 6 UI-controller PASS/2 SKIP; новые три воспроизведённые ситуации; неизменность кода и рабочего плана. EG-01/02 ограничивают выводы о Windows/G2, Gendocen и полном scope проекта. Deferred Findings нет; второстепенное скрытие истории остаётся прежней задачей вне review.

Сохранение отчёта и навигационной ссылки проверяется после GitHub write. Публикация — только копия для чтения; она не меняет рабочий owner, Proposals, Stage 4 или установленный клиент.
