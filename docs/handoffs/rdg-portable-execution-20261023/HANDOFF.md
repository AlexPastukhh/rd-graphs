# RDG — хендофф исполнения переносимых Graph, 2026-10-23

> **СТАТУС: АРХИВНЫЙ СНИМОК ПЕРЕДАЧИ.** Создан по прямому запросу пользователя остановить исполнение и передать работу следующему чату. Это навигация и evidence данного среза, не второй рабочий план и не новый контракт. Принятые пользовательские решения не пересматриваются этим файлом.

## Кратко для следующего чата

Основная задача — **выполнить план переносимых Graph**, соблюсти DRY, сохранить все состояния, ссылки, Plan/history/layouts и удобный путь пользователя. Сейчас реализованы и проверены backend, общий API, Agent/Helper/CLI, Viewer-контроллер, move, opt-in migration и восстановление принятой операции по ID. Пройден полный synthetic сценарий на настоящем 9p RW-монтировании проекта.

**Не завершено:** последний черновик `cancel_migration` сохранён отдельным **неприменённым и непроверенным патчем**; Agent для него ещё не подключён. Нужны адресное завершение/проверка этого хвоста, актуализация его документации и отдельные Windows/browser gates. Установленный Windows Viewer и пользовательская UI-приёмка не подтверждены; Stage 4 NOT ACCEPTED сохраняется. Ни один живой owner или grant не мигрирован.

Прочитать разделы «Где продолжать», «Оставшийся черновик» и «Следующие действия». Не начинать заново дизайн, review всего репозитория или все тесты без новой причины.

## Где продолжать и что читать

Проект в Fortis Repo: **`/workspace/repos/rd-graphs`**. Это Git root с приложением, тестами и документацией; `graphs/` — подкаталог.

Порядок чтения:

1. `AGENTS.md`, `README.md`, `docs/guides/RDG-CURRENT-STATE.md`.
2. **Единственный рабочий план:** `docs/guides/RDG-DEVELOPMENT-PLAN.md`, раздел «План переносимых Graph — 2026-10-23», прежде всего ход исполнения этапов 6–7 и остаток.
3. `docs/guides/RDG-ACTIVE-CONTRACT.md`: переносимые пакеты, текущий API, move/migration, история и отсутствие Plan.
4. `docs/guides/RDG-OPERATIONS.md`: portable Agent/Helper, move, `recover`, opt-in migration и завершение этапа.
5. `docs/guides/VIEWER-EXPLORER.md`: portable-сессия и границы UI-проверки.
6. При проверке конкретного решения — immutable дизайн `docs/handoffs/rdg-portable-packages-design-20261023-v3/DESIGN.md`, особенно §§4/7/8/10/12/16. SHA256: `5825bb1c82996385ebf7a72934ae3e264ee332379454237c9490dd13ac230390`.

Обычный `rg` скрывает архивы через `.ignore`. По прямому известному пути читать их можно; для поиска внутри нужного архива использовать `rg --no-ignore`. Не принимать скрытую зависимость за отсутствующую.

Связанный Final Review v2 относится к плану, не принимает нынешнюю реализацию: https://github.com/AlexPastukhh/forfiles/blob/main/artifacts/2026-10-23/final-review-rdg-portable-plan-60bac18a-v2.md . Его Findings/IDs не перенумеровывать и не объявлять устранёнными только по наличию нового кода.

## Путь, полномочия и Git

Перед новой записью заново проверить `pwd`, `findmnt -T .`, права и `git status`. Последняя фактическая проверка:

- `/workspace/repos` — 9p RW-монтирование `C:\[/Users/alexa/Repos]`; проект соответствует `C:\Users\alexa\Repos\rd-graphs`.
- `get_config` содержал устаревшее описание `/workspace/repos` как `C:\134`; прямой `findmnt` установил фактический mount. Не выбирать путь только по старому описанию инструмента.
- `/workspace/repo` — отдельный Docker/ext4 volume. В нём находились только synthetic runtime fixtures и synthetic authority/coordinator; исходники проекта туда не копировались.
- Repo не предоставляет Windows PowerShell/GUI/процессы владельца. G2 — отдельный гостевой Windows-контур. Старый owner HOST остановлен; не запускать его, не пользоваться старыми `app://` маршрутами, не менять mounts/ACL и не обходить ограничения через другой контур.
- Обычный лимит прямой передачи целых Windows-файлов в ChatGPT — 1 000 000 байт на файл и логический набор, без обхода нарезкой. Работа внутри разрешённого Repo mount — другой случай.

Последний коммит **до подготовки этого checkpoint**: `176ce44c820757ecfb827ea881c0cac6613c8831` — `Preserve portable copies and expose one application API to Agent and Viewer`. Более ранние: `436ff25` — kernel/retained detached; `fe8c792` — coordinator/auth/reference barrier; `706ffad` — документация и Git-порядок. Remote не настроен; push не выполнялся.

Новый checkpoint с данным хендоффом нужно находить по факту, а не угадывать hash:

```sh
cd /workspace/repos/rd-graphs
git log -1 --format='%H %s' -- docs/handoffs/rdg-portable-execution-20261023/HANDOFF.md
git status --short
```

Перед применением черновика проверить, не появились ли чужие изменения. Не использовать `reset --hard`, `git clean`, force-push или массовую перезапись. Коммиты — только отобранные файлы. Не создавать новый сайт, инфраструктуру, snapshot, второй план или ещё один handoff без задачи.

## Закрытая семантика — не задавать пользователю заново

- **Ready/lens — бумажный шаблон:** все R potential, все A candidate; нет рабочего выбора, active работы, execution/history или Plan. Технические receipts/CAS разрешены. Вставляется весь шаблон со всеми альтернативами.
- Apply — ADD_ROOT или REPLACE_R; нет автоматического matching по названиям и выбора A. Активируется только вставленная корневая R, а не все её варианты/потомки.
- При удалении/замене R снимаются она, её текущие incident refs и **все** её current placements из всех затронутых Plan. Новая R их не наследует. Sequence не склеивается. История и остальные существующие placements сохраняются.
- Потеря зависимости изменяет ситуацию A и требует stale/review. Она не переводит A автоматически в candidate/superseded/withdrawn и не придумывает невыполнение.
- После потери последней DRIVES A и ветвь могут стать отрезанными. Они сохраняют прежние ID, owner, membership, выбор, историю, stale и Plan до явного решения. У исходного Graph есть отдельное представление «Отрезанные графы»; это не корзина и не новый owner. Detached и stale независимы.
- **Copy сохраняет всё выбранного scope:** state/choices/results/stale/facts, Plan versions, evidence, layouts, внешние зависимости. Новые IDs связаны lineage; копирование не является новым исполнением и не сбрасывает состояние.
- Copy и detached используют общий контракт точных typed refs. Внешняя, в том числе same-owner/outside-fragment, связь сохраняется семантически и доступна по правам. Source change даёт review; refresh/rebind/remove — явные действия. Удалённая зависимость остаётся historical pin, не current dangling edge и не воскресший узел.
- Цельный move сохраняет identity и всё содержимое. Реальная папка задаёт расположение; ложного folder override для portable owner нет.
- DRY: один current owner, общий planner/ref visitor и Application; capture/rooted/freshness — осмысленно разные policies. Нового универсального framework/БД/фонового сервиса не добавляли.
- Legacy 2D/Decision/Option conversion, развитие WIP-модулей и прежние deferred F-O-01/02/03 с PR-06/07/08 вне scope. Живые migration, новые grants, установка и публикация не следуют автоматически из разработки.

## Что реализовано в Repo

### Model, state и storage

- `tools/rdg-core-model.py`: retained selected после доказанной потери зависимости, derived detached components, исторические причины stale, remove через coordinator, origin barrier и inherited fact lineage. Нет нового select/complete без необходимой основы.
- `tools/rdg-portable-model.py`: pure EffectPlan, typed refs/pins и remap, copy/insert/apply/delete, capture/boundary inventory, Plan v2, общая серверная presentation projection. Не зависит от FS/HTTP/UI/clock/RNG; datetime используется для разбора, allocation/clock находятся выше.
- `tools/rdg-transaction-io.py`: общий POSIX IO/reference barrier и безопасные пути; route gates и распознавание package interiors. Native Windows writer не подтверждён.
- `tools/rdg-portable-store.py`: namespace, manifest/generations/receipts/history/provenance, durable stage до acceptance, all-head publication/recovery, actor/request idempotency, catalog identity conflicts и own completion witnesses. Imported incomplete не выдаётся за healthy. Доказанно unaccepted staged creation отделена от current incoming closure; accepted/unknown incomplete по-прежнему блокирует полноту.

### Общий API и UI

- `tools/rdg-portable-service.py` — один Application для core/paper/copy/apply/delete, Plan/evidence/layouts, resolve/history, move/migration dispatch и `recover`.
- `tools/rdg-portable.py` — composition/CLI; `tools/rdg-workflow-commands.py` — общие legacy command builders. Agent не импортирует Helper.Editor.
- `tools/rdg-agent.py`, `tools/rdg-workflow-helper.py`: thin portable adapters; прежние file/loopback transports и отдельные legacy маршруты сохраняются. `by:user` ручной сессии не является удостоверенной личностью или правом менять protected R.
- `tools/rdg-portable-ui.js` — один source-модуль контроллера. `tools/build-rdg-layout.py` встраивает его в `tools/rd-graph-viewer.user.js`; отдельного UI writer/алгоритма stale нет. Source Viewer **2.6.0**, установленная версия неизвестна.
- UI показывает реальное дерево папок/ролей, focus/workGraph, detached/external, Plan/history, preflight и точное подтверждение. Ready/lens не показывают рабочие Plan/history. Раскладка блокирует copy/переход до сохранения либо отмены; при drag линии следуют узлам. Проверка контроллера — с DOM adapter, не полноценным browser.
- `source_snapshot` открывает точную сохранённую версию Graph только для чтения. Проверено чтение own provenance cache копии после удаления synthetic source. Исторический renderer общий с текущим; edit controls у snapshot отсутствуют.
- Copy сохраняет отсутствие Plan. `plan_create` явно создаёт первый Plan только у working/copy; не требует `plan.read` отсутствующего Plan и требует `plan.create`. Insert copy с Plan в destination без Plan сохраняет временной контекст.
- Default copy path задаёт Application: `copies/<дата Asia/Bangkok>/<transactionId>`, пользователь может выбрать свой разрешённый путь. UI не рассчитывает вторую дату/identity.
- `recover --transaction-id UUID` завершает **только уже принятую** операцию исходного bearer actor без потерянного request body; другой actor/unknown/unaccepted отвергаются. Это проверено и после revoke через новый процесс Agent. Portable credential loading оставляет семантическую проверку Application; legacy credentials по-прежнему проверяются прежним активным `_actor`.

### Move и opt-in migration

- `tools/rdg-package-transfer.py`: package/folder move, rename либо полностью staged/verified copy-протокол, source tree/head CAS, раздельные folder grants, фазовые journals, безопасный resumable source cleanup и own move witnesses. Неожиданные исходные данные не удаляются. Нельзя через folder_move незаметно переместить немигрированный Graph/Plan owner.
- `tools/rdg-legacy-migration.py`: только явно настроенные core sources. Полный source capture/CAS и discovery, final grants/reference barrier, writer exclusion/route switch, exact accepted retry, старые Graph/Plan versions и scoped journal projections. Известный Plan owner той же identity нельзя пропустить даже при пустом Plan. Настоящий Graph-only source сохраняет отсутствие Plan.
- Runtime config/flags описаны в регламенте: `confirmOwnerSwitch`, `legacyWritersQuiesced`, `presentationSourcesComplete`, `presentationWritersPaused` по умолчанию false. Старые процессы должны быть действительно остановлены: cached версия может не знать marker. Источники saved layouts выбирает оператор. Авто-grants и startup migration нет.
- Raw current Graph/raw Plan owner сохранены; текущий поддерживаемый Plan переведён в v2 новой revision. Общий legacy journal копируется только owner-specific projection с неизменёнными relevant records, record hashes и hash оригинального envelope. Это **не** оригинальный полный envelope; чужие payloads не копируются. Gaps не скрыты.
- Неподдерживаемые current Plan-only event/gate/branch, WIP-поля и incoming legacy refs дают blocker, а не скрытую конверсию/потерю.
- Текущие старые Graph/Plan writers и readers блокируются route marker; explicit historical Plan revision остаётся читаемой. Исправлены также catalog/Agent/Helper discovery и current Activity/CompletionContext. Gendocen live refresh не объявляется portable capability: у него отдельная ответственность/доступ.
- В `tools/rdg-agent-lenses/catalog.json` добавлен пропущенный instruction route для нового AGENTS.md; соответствующий catalog test после исправления прошёл.

## Фактически выполненные проверки

Не суммировать повторные/пересекающиеся прогоны как число уникальных тестов. PASS относится к указанному срезу, **без применения pending patch**.

| Проверка | Подтверждённый результат и граница |
| --- | --- |
| `tests/rdg-portable-store.test.py` | 12 PASS после move witnesses/path guards |
| `tests/rdg-package-transfer.test.py` | 10 PASS, в том числе forced copy-протокол, recovery после revoke, source change, folder grants и несколько packages |
| `tests/rdg-legacy-migration.test.py` | 10 PASS: scoped history/Plan, source/layout CAS и новый owner, staged/prepared recovery, revoke, unsupported constructs, пропущенный Plan, Graph-only source |
| `tests/rdg-portable-transports.test.py` | 11 PASS через реальный Helper/Agent/CLI; затем последний UI-кейс повторён адресно после tree/drag правок — 1 PASS |
| `tests/rdg-mounted-storage.test.py` | 1 PASS на настоящем 9p RW source mount, 266.908 s всего сценария; это не latency одного UI-действия |
| `tests/rdg-portable-service.test.py` | 10 PASS после новых Plan/recovery/API изменений |
| `tests/rdg-portable-model.test.py` | 23 PASS после общего Graph pin validator |
| `tests/rdg-portable-copy.test.py` | 16 PASS после source/history API; позднейшие узкие permission/recovery правки покрывались service/transports |
| `tests/rdg-temporal-plan-owner.test.py` | 20 PASS после legacy route/reference gates |
| `tests/rdg-core-workflow.test.py` | 11 PASS после legacy route gates |
| `tests/rdg-agent.test.py` | 14 PASS в этом исполнении до позднего defer-active portable credential loading; legacy default при этом не менялся |
| `tests/rdg-workflow-helper.test.py` | 17 PASS после route integration |
| Node source catalog suites | 6 PASS |
| `tests/rdg-lens-catalog.test.py` | 5 PASS после AGENTS route |
| `tests/rdg-portable-layout.test.cjs` | 3 PASS |
| `tests/rdg-documentation.test.cjs` | 5 PASS после обновления шести активных документов; для нового хендоффа нужен завершающий audit |
| Архитектурный проход | Pure model import direction, отсутствие Helper import в Agent, generated Viewer parity, syntax изменённых Python — PASS |
| Исторический checkpoint `176ce44` | core 25 PASS и pure copy-model 9 PASS; это прежний срез, не свежий запуск всех suites |

9p сценарий: ready → REPLACE_R → retained selected A + stale/detached → снятие только удалённой R из Plan → copy с layouts → реальный rename → чтение истории из собственной копии без source. Только временные synthetic package data; authority/coordinator находились вне Git root. Каталоги `.rdg-storage-test-*` после теста отсутствовали.

Cross-FS ветвь tested через принудительный выбор copy-протокола. Настоящий перенос между дисками Windows, поведение при потере питания, native Windows writer, визуальный browser и пользовательская оценка UI **не проверены**. Последние generated parity и immutable design SHA подтверждены отдельно. Все запущенные тестовые процессы завершились; инфраструктуру/сервисы для них не перезапускали.

## Оставшийся черновик: отмена непринятой миграции

**Статус: candidate / НЕ ПРИМЕНЁН / runtime tests НЕ ВЫПОЛНЕНЫ.** В Repo действует проверенный `recover` принятой операции. Черновик касается другого случая: процесс может оборваться после записи `switching` routes, но до durable acceptance. Обычные исключения уже очищают собственные routes; hard crash в этом промежутке может требовать безопасно снять только непринятый switch. Дизайн §12 допускает возврат до принятого изменения, но запрещает потерю новых фактов.

Файл рядом с этим хендоффом: `pending-cancel-migration.patch`.

SHA256 патча: `28b3e28ee91cef0c1ef902479ccbabba50de87a3ab0371ff62c9ffbfcdebcc08`.

Патч содержит **только последние не применённые изменения** пяти файлов: backend `Migration.cancel`, запрет retry cancelled intent, общий dispatch/CLI/UI и candidate tests. Он не содержит основной реализации этапа 6: она уже в рабочем дереве/checkpoint. Применение проверялось только реконструкцией точных before bytes и локальной синтаксической проверкой draft, не тестовым исполнением.

Ожидаемая база патча:

| Файл | SHA256 before |
| --- | --- |
| `tools/rdg-legacy-migration.py` | `edb05b21b55c4a7564a7e08190546c7be1fcbf41876181da4e27ce9b1569aa55` |
| `tools/rdg-portable-service.py` | `e5641453a77bbe5798d23646c101ac626fa38eae154fee8a9cac8920ccdfd4bc` |
| `tools/rdg-portable.py` | `03de478331d2f2bc95546e7d203f92321e5fd2de46a73880a41212b3879bc4e3` |
| `tools/rdg-portable-ui.js` | `d295bc5395751b53ebba39d911c5e4a7c4a304c91b1b1a974a9302c2539d4f25` |
| `tests/rdg-legacy-migration.test.py` | `a6e329880c92269655ebd4b9b612d74639f45a0fc5b4744c2575416c32d66a9c` |

Сначала прочитать патч. Перепроверить ownership и **полное** соответствие route markers, отсутствие accepted/completed certificates, опубликованного head и own acceptance/commit witnesses, порядок locks и повтор после прерывания. Нельзя считать одно отсутствие файла доказательством отсутствия принятия при повреждённом metadata. Нельзя снимать принятый switch, удалять facts или обосновывать rollback изменением selected/stale. Draft сохраняет staged bytes; cleanup данных не реализован и не подразумевается.

**Ещё не сделано даже в патче:** route `cancel_migration` в Agent (choices, portable dispatch и отказ вне portable context), обновление текущего контракта/регламента/плана и новый build Viewer после применения. В составленном candidate migration test hard-crash окно имитируется собственными markers; это не доказательство power-loss или настоящего kill в каждой фазе.

Не запускать прежние scratch patch scripts. Они уже были применены на более старых базах и способны перезаписать новые изменения. Этот ограниченный pending patch — единственный переносимый последний draft.

## Ограничения доступа и заблокированные действия

- Полный G2 `get_config` был отклонён **automatic approval review**: отдельный Windows-контур, сведения о клиентах/системе, нет явного разрешения пользователя и операция не необходима для Repo-разработки. Данные G2 не получены. Не повторять полный config, не обходить отказ другим контуром и не объявлять Windows PASS. Для дальнейшей конкретной Windows-проверки сначала определить минимальное разрешённое действие и, если требуется, получить явное разрешение с объяснением источника ограничения.
- Ранее отклонена попытка скопировать несколько Repo source files в Docker volume ради browser harness. Копия не была создана; этот обход оставлен. Вместо него выполнены контроллерные тесты с настоящим Helper в Repo и synthetic данными. Не возобновлять экспорт проекта под другим названием.
- Ранее отклонён whole-file restore Helper из HEAD из-за риска потери unstaged changes. Повреждённый собственным refactor span восстановлен адресно с diff/hash; Helper tests затем прошли. Не откатывать весь файл/репозиторий.
- Chromium executable в доступной среде отсутствует; локальная Playwright-попытка не прошла. Она не является browser PASS. Никакие браузеры, туннели и owner HOST ради этого не устанавливались/не запускались.

Вопросов о смысле ready/copy/Plan/stale/detached к пользователю не осталось. Следующие технические исправления не требуют заново спрашивать эти решения. Windows-доступ и UI-приёмка — отдельные gates, не смысловая развилка модели.

## Следующие действия

1. Сверить фактические Git/mount/права и прочитать действующих владельцев по порядку выше. Сохранить чужие правки. Уточнить реальный checkpoint по `git log`, не по старому ответу чата.
2. Сопоставить последнее состояние исходников с SHA base патча. `git apply --check docs/handoffs/rdg-portable-execution-20261023/pending-cancel-migration.patch` — только проверка применимости; она не доказывает корректность.
3. Адресно закончить либо исправить candidate отмены непринятого switch после проверки guards. Добавить отсутствующий Agent route и tests. Не откатывать принятую миграцию; для неё уже есть `recover`.
4. Выполнить соответствующие migration/transports tests, rebuild `python3 -B tools/build-rdg-layout.py`, адресный реальный Helper → UI controller test, `git diff --check` и нужные проверки авторизации/recovery. Не повторять дорогой 9p full pass без изменения backend или новой причины.
5. По фактам обновить существующие contract/operations/plan; выполнить `node --test tests/rdg-documentation.test.cjs`. Учитывать, что новый handoff snapshot не является active owner. Исторические версии не переписывать.
6. После прохода сделать выбранный Git checkpoint. Дальше — конкретный Windows/browser путь только в реально разрешённом окружении и пользовательская UI-приёмка. Не объявлять весь план завершённым до этих gates и не мигрировать живые owners автоматически.

Минимальная инструкция новому чату: **«Продолжи исполнение переносимых Graph. Сначала прочитай этот handoff и действующий план в `/workspace/repos/rd-graphs`. Основной код уже реализован и протестирован; не применён только candidate `pending-cancel-migration.patch`, ему ещё нужны Agent route, проверки и документация. Windows/browser acceptance остаётся открытой. Не переоткрывай закрытые семантические вопросы и не создавай новую инфраструктуру».**
