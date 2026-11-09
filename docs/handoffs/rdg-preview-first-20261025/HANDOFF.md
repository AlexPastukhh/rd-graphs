# RDG — хендофф для продолжения: ранняя ручная проверка

> **СТАТУС: АРХИВ / ХЕНДОФФ СРЕЗА, 2026-10-25, Asia/Bangkok.** Создан по прямому запросу пользователя для передачи другому чату. Это снимок состояния и маршрут продолжения. Действующие правила и дальнейший план остаются в AGENTS.md и документах docs/guides. Этот файл после создания не обновлять под видом прежнего среза.

**ID:** RDG-HANDOFF-PREVIEW-20261025/v1.  
**Проект:** /workspace/repos/rd-graphs.  
**Кодовый срез прочитан:** 2026-10-24T18:58:53.675479+00:00 (UTC).  
**Текущий исходный Viewer:** 2.7.0. Установка пользовательского Tampermonkey неизвестна.  
**Состояние:** ручной preview подготовлен и проверен в изолированном Chromium; первый пользовательский Windows-запуск и оценка удобства ещё не подтверждены. Полная Stage 4/security acceptance и независимый Stage 6 не приняты.

## 1. Самое важное для следующего чата

Продолжать существующий RDG, сохраняя текущий dirty working tree. Не создавать новый сайт, проект, Git-клон или инфраструктуру по факту наличия подключений. Не начинать с повторного большого security audit или с восстановления Stage 3 поверх новых файлов.

**Последнее решение пользователя, дословно:**

> надо делат так чтобы можно было побыстрее посмотреть на результат, протестировать его вручную пользователю. все секьюрити риски можно отмечать как известные и оставлять на потом,если при этом общая идея работает и корректная.

Это решение ПОЗЖЕ прежней сверки, где ранний trust proof ставился перед расширением approval-реализации. Текущий порядок: показать работающий пример → получить ручной feedback → исправить реальные препятствия → расширять нужные операции. Security risks остаются известными незакрытыми рисками. Их отсрочка не означает новых OS-прав, разрешения менять ACL/mounts/tunnels, доступ к owner home/GUI/clipboard, миграцию или удаление живых данных.

**Ближайший результат уже подготовлен:** в корне Windows-репозитория есть Start-Preview.cmd. По фактическому mount путь соответствует C:\Users\alexa\Repos\rd-graphs\Start-Preview.cmd. Пользователь должен открыть его в своём Windows-сеансе. Скрипт создаёт отдельный venv, запускает тот же Viewer/Application/writer/WebAuthn над тремя новыми тестовыми Graph и открывает браузер.

**К моменту передачи пользователь ещё не сообщил результат запуска.** Следующий чат должен сначала учесть новый feedback, если он появился. При его отсутствии помочь выполнить этот один запуск. Ошибку Python/Node/порта/импорта исправлять как конкретную startup-проблему. Не подменять этот шаг полной матрицей операций или обязательным закрытием всех security risks.

## 2. Источники и порядок чтения

Пути далее относительно /workspace/repos/rd-graphs, если не указан полный путь. Сначала прочитать AGENTS.md, README.md, docs/guides/RDG-CURRENT-STATE.md; затем применимые разделы RDG-DEVELOPMENT-PLAN.md, RDG-ACTIVE-CONTRACT.md и RDG-OPERATIONS.md в том же каталоге. Пользовательское поведение Viewer описано в docs/guides/VIEWER-EXPLORER.md, браузерные проверки — в tests/visual/README.md.

Один действующий план дальнейшей работы — docs/guides/RDG-DEVELOPMENT-PLAN.md. Его начало содержит продолжение после Stage 3, approval, persistence и последующий приоритет ручного preview. Остальные разделы также содержат общие направления RDG; текущая ветвь не закрывает автоматически модули, весь Gendocen audit или все portable/visual gates.

docs/handoffs/candidate-prework-rdg-context-checkpoints-dependencies-approval-v9.md — неизменяемый источник пользовательских требований, сценариев и стадий этой предработы. Он остаётся CANDIDATE для полной технической композиции и не является текущим журналом выполнения. Старое NOT IMPLEMENTED в его заголовке не отменяет позднейшие реализованные части. Принятый пользовательский смысл и technical candidate/committed — разные статусы.

Предыдущая передача: docs/handoffs/rdg-stage3-execution-20261024/HANDOFF.md. Она описывает вход в это продолжение, а не нынешний конец работы. Её не переписывать. Реестр действующих документов — docs/DOCS-POLICY.json. docs/handoffs/** — immutable archive; .ignore скрывает этот каталог от обычного rg, но прямое чтение разрешённых файлов и rg --no-ignore по нужному пути работают.

## 3. Среда и эффективные границы доступа

**Fortis Repo** — Linux Docker, основной контур для исходников/Git/CLI/tests. Фактически проверено: /workspace/repos/rd-graphs находится в RW/9p mount /workspace/repos, source C:\[/Users/alexa/Repos]; /workspace/repo — отдельный RW/ext4 Docker volume /dev/sde[/data/docker/volumes/fortis-repo-workspace/_data]. Repo работает с UID/GID 1000; корень проекта доступен на чтение/запись/проход. Изменения под /workspace/repos меняют настоящие Windows-файлы. Не путать /workspace/repos и /workspace/repo.

Поле hostPath=C:\134 в get_config было устаревшим относительно прямого findmnt. На новой сессии сверить конфигурацию с прямым доступом, mount и правами; не переносить вывод из старой конфигурации без проверки.

**Fortis G2** — отдельная гостевая Windows-учётная запись. По последней read-only проверке identity FORTIS_M\FortisHostG1, Administrator=false. Разрешённые каталоги: C:\Users\FortisHostG1\AppData\Local\FortisHostG2\Workspace; C:\Tools\tunnel-client; C:\Tools\desktop-commander-runtime; C:\Tools\desktop-commander. Workspace гостя имеет FullControl для гостя, в общих Tools есть явный Deny записи/удаления/смены прав/TakeOwnership для него. Это ACL metadata, не полный adversarial OS test.

Прежний owner HOST остановлен; старый connector/app route не является действующим разрешением. Не запускать его самостоятельно. G2 не даёт права владельца. Не использовать G2 для обхода недоступного owner path, Repo для обхода запрета G2 или новый tunnel/ACL/mount как молчаливое средство.

В G2 подготовлен отдельный venv: C:\Users\FortisHostG1\AppData\Local\FortisHostG2\Workspace\rdg-manual-preview-20261025\venv. Установлены fido2 2.2.1, cryptography 50.0.2, cffi 2.1.1, pycparser 3.12, tzdata 2026.5. Найден гостевой Python 3.13.16 и machine Node.js. Код RDG в этот Workspace не передан и приложение там не запущено. Это окружение гостя, оно не доказывает готовность Python/venv владельца. Прочие гостевые эксперименты и browser-profiles к этой задаче не относятся.

Repo Docker loopback был проверен из G2 Windows отдельным безвредным HTTP probe и оказался недоступен. Не давать Docker localhost URL как работающий Windows URL и не считать произвольный порт опубликованным. Проверенный probe завершился; собственный служебный Docker preview остановлен, его temporary данные удалены. Пользовательский Windows-процесс в этом чате не наблюдался.

Локальный filesystem ChatGPT /workspace/scratch/... — другой контур. Для работы с проектом использовать Fortis Repo connector; обычный local exec_command не даёт автоматически тот же /workspace/repos.

## 4. Git и сохранность рабочего состояния

| Контрольная точка | Значение |
|---|---|
| HEAD / main | `176ce44c820757ecfb827ea881c0cac6613c8831` |
| Stage 3 code checkpoint | `7bd444eef83e4dad5439d3eb5c34b16c984e8cdc` |
| Stage 3 index checkpoint | `a4a69db2b278c548609607ef43a37e725cbc48b3` |
| SHA-256 текущего .git/index | `761fa68c2e2555a8f09cb6ebe669793d50b790ce3ef9c82fd9308be312fab318` |
| Пути до добавления этой передачи | 1812 |
| Git status до передачи, --untracked-files=all | 78 строк |

Имена refs: refs/heads/checkpoint/rdg-after-stage3-20261024T100902Z и refs/rdg-checkpoints/rdg-after-stage3-20261024T100902Z/index. Эти refs не обновлялись. HEAD/main и index сохранены; после Stage 3 новые commit/push не выполнялись. Пользователь сейчас попросил хендофф, а не commit/push.

Рабочее дерево содержит смешанные staged/unstaged/untracked изменения прежних этапов и этого продолжения. Полный status и manifest сохранены рядом в STATE.json. Не считать всё dirty «чужим мусором» или только работой последнего шага. Не применять reset --hard, git clean, force-push, массовый checkout/перезапись и не stage-ить всё сразу.

Некоторые файлы есть в checkpoint tree, но ещё untracked в текущем index. Сравнение git diff checkpoint само по себе может показывать мнимое удаление существующего файла. Проверять реальные байты/STATE.json/явные blobs; не восстанавливать файл поверх текущего только по такому diff. Существующее удаление tests/rdg-layout-commands.test.cjs также не является новым дефектом этой передачи.

**Живые owners не переключались и не правились для демонстрации:**

| Owner | Revision | SHA-256 |
|---|---:|---|
| graphs/workspaces/requirements-dependencies-demo/graph.json | 10 | f96fe888280d2a2181690379ea6e86d0bcee19e0e6efbfbcbb67ffa34a0db694 |
| graphs/workspaces/try-it/graph.json | 1 | 26abb345e49c674379947e6474675b222df2ea9fbe72c1acb70da5380a3013da |
| plans/requirements-dependencies-demo/plan.json | 4 | 21478d5d5905052af23851a8ed9557b6218b132ed7eb4fa43201ae0b7c4f7925 |

Не сбрасывать реальный учебный Graph и не мигрировать owners ради первого preview. Preview создаёт другой namespace и другие данные вне исходников. В этой передаче изменяется только ссылка в RDG-CURRENT-STATE.md и добавляются этот HANDOFF.md и STATE.json; runtime-код не меняется.

## 5. Что было до продолжения

Общая цель v9: сохранять осмысленную работу между чатами, основания выбора R/A, Canon/QRPE/Context/history, корректные зависимости и реальную предметную власть человека. Обычная разрешённая unlocked правка не должна требовать нового object key или обязательного human dialog.

| Этап предработы v9 | Реализованная часть к входному handoff | Ограничение evidence |
|---|---|---|
| Stage 1 — checkpoint/Canon | Одна checkpoint lens, пять последовательных маршрутов, пять Canon, семь shared criterion identities и 35 настоящих INFO_FOR relations/visual occurrences. Новый Canon comment-only-v1, без программного veto | Semantic/synthetic tests; не доказательство реального peer AI, человека или installed Viewer |
| Stage 2 — native L1/L2 | DEPENDS_ON CRUD/readback, общий semantic impact contract, direct Viewer controls; предусмотренные literal/cosmetic и направленные hit/no-hit cases | Проверенный code scope; не полная пользовательская приёмка всех сценариев |
| Stage 3 — права/замки | Bearer/grants, warning/hard для object+operation, несколько допустимых principals, no inheritance, delegated ceiling | Manual attribution=user ещё не удостоверяла человека |

Эти части были переданы, а не заново созданы в последнем шаге. Общие portable Graph, copy/apply/delete, Plan/history/layouts, move и opt-in migration уже существовали в описанном в рабочем плане synthetic/POSIX scope. Их Windows, визуальные и пользовательские gates не закрываются автоматически работой над approval.

Не переоткрывать принятые смыслы: пять маршрутов/seven shared IDs, no-veto Canon, native L1/L2 без L3-рекурсии, C3 nonpropagation через Canon, warning/hard object+operation, no inherited locks, обычный bearer для unlocked writes. Намеренно OPEN cosmetic bypass risk остаётся OPEN по решению пользователя; не добавлять detector, новый approval или обязательный checkpoint ради его «закрытия».

## 6. Что сделано после Stage 3

### 6.1 Pending API и exact inputs

Application/Agent/CLI получили approval_request и approval_read. Pending хранит точное тело, rationale, initiator token digest и preview snapshot; резервирует существующий unaccepted intent. Graph/Plan, accepted certificate и grants от создания запроса не меняются. Один UUID нельзя переназначить другому телу/автору/rationale; raw bearer в pending не записывается.

inputBinding policy full-read-set-v1 связывает request, namespace/actor grant, полный read set, catalog, required permissions и effect packages. Проверяются expectedInputBinding, final read/catalog CAS и права. P1→P1+P2 проверен при прежних target/JSON: появление второго Plan с incoming ref меняет closure, старое согласие отклоняется. Консервативная policy иногда требует новый preview и после несвязанного изменения каталога.

Обычный Application message contract не предоставляет approve/reject и не принимает proof dict, actor label или grant/key binding как доверенные данные. Pending API требует existing target и явно отклоняет move, folder_create, folder_move, migrate; полный eligibility inventory остаётся открытым.

### 6.2 WebAuthn и общий executor

tools/rdg-webauthn.py использует python-fido2: точный origin/RP, REQUIRED UV, UP, signature/challenge, expiry, user handle, counter и framing checks. Decision challenge связывает principal, решение и server approval digest; persistent mode добавляет binding digest. WebAuthn является проверкой допущенного ключа; реальная личность и доверенность первичной привязки требуют своего evidence.

tools/rdg-approval-executor.py готовит before/after всех меняемых owners через тот же planner и исполняет через общий FileStore/coordinator. Allocation IDs и event time фиксируются для ceremony. Preview пересчитывается перед prompt/complete; final gate держит grants/credential lock и CAS. Фактический executor grant/object principal назначает host, клиент их не выбирает. На реальных пользовательских grants этот контур не принимался.

Accepted transactions имеют schemaVersion 2 и rdgExactApproval context с отдельными initiator/approver/executor и digests. Raw bearer не попадает в публичные receipts; token digests остаются в private metadata. Старые обычные transactions сохраняют schemaVersion 1 и single-actor contract.

Reject сохраняет immutable metadata без Graph/Plan transaction и блокирует тот же ID. Принятый payload восстанавливается точно и однократно, включая потерю pending/intent или отзыв прав после acceptance, без отката более позднего head. Статусы: pending, rejected, approved-awaiting-recovery, executed-approved, executed-independently. decisionVerified=true означает проверенную подпись; humanApprovalVerified=false сохраняется как ограничение trust evidence.

### 6.3 Основной Viewer и transport

ApprovalSurface предоставляет list/open/choose/complete/status/recover только настроенному executor. Optional registration_begin/registration_complete работают с host-injected owner permit и заранее выбранным principal. Обычные CLI/Agent/FileSession этот approval transport не настраивают. Host/Origin/session, CSP и framing guards сохраняются.

В rdg-portable-ui.js и generated rd-graph-viewer.user.js есть список запросов, rationale, before/after всех owners, native Approve/Reject, cancellation, status read после uncertain response и exact recovery. Предметные поля идут первыми, история/служебные версии раскрываются отдельно. Прежний preview не заменяется молча новым. Новый P2 требует явного refresh и нового решения; изменённая target revision требует нового request ID от инициатора.

### 6.4 Постоянные credentials и audit

tools/rdg-credential-store.py добавляет opt-in WebAuthn substate в существующий Authority JSON под тем же lock; второй базы grants/scopes нет. Сохраняются owner-configured principal/namespace/existing grant/object-principal/origin/RP binding, публичный credential, user ID, counter, registration/decision evidence. Приватный authenticator key не сохраняется. Credential revision не меняет grants или grant revision.

tools/rdg-credentials.py: inspect/configure/invite/revoke/audit. Требуется существующий owner bearer с grant.admin; delegated admin недостаточно. Configure/revoke используют CAS. Invite выдаёт короткий one-use permit в новый private файл вне code root; Authority хранит digest. Raw permit не возвращается браузеру. Не выполнять эти команды с реальными credentials ради демонстрации.

Ключ/counter переживают новый процесс. Незавершённые ceremonies намеренно transient: после restart требуется новая ceremony, а не восстановление старого consent. Непрерванный issued permit не является автоматически новым human consent. Старый assertion новым процессом не принимается.

После подписи counter/evidence сохраняются; перед durable acceptance проверяются актуальные binding/key/grant под одним Authority lock. Отзыв после signature/staging, но до acceptance блокирует запись. Сохранённая подпись не равна accepted Graph transaction. Audit повторно проверяет публичное evidence после restart/revoke и возвращает authorizesNewExecution=false. Recovery принятого payload не требует действующего ключа.

Полное key management в Viewer НЕ сделано: registration есть, configure/invite/revoke пока owner CLI. Preview имеет отдельное упрощение автоматического приглашения только для своих тестовых данных.

### 6.5 Исправленные замечания в проверенном scope

| Finding | Результат |
|---|---|
| F-R-G0-01 | Воспроизведены обходы link/remove locks и лишний запрет edit lock; core/portable root removal проверяют точную операцию. Scoped regression прошла |
| F-R-G0-02 | В verified host ручная attribution=user могла снять lock без WebAuthn. Opt-in Helper теперь отклоняет ordinary preflight/apply lock_set/remove, включая core/paper_edit equivalents, с VERIFIED_APPROVAL_REQUIRED; Viewer создаёт pending и просит native consent |
| F-R-V7-01 | Trust boundary/real human binding остаются unresolved и отложены для раннего preview по последнему решению пользователя |
| F-R-V7-02 | Exact inputs/one-use/recovery существенно покрыты; полный pending portability/lifecycle не объявлен закрытым |

Фикс F-R-G0-02 не превращает весь default manual Helper в удостоверение человека. При отсутствии approval factory прежний manual path остаётся unverified. Обычные unlocked writes сохраняют прежний разрешённый путь.

## 7. Последний шаг: один ручной запуск

### 7.1 Файлы и назначение

| Файл | Назначение |
|---|---|
| Start-Preview.cmd | Запуск из существующего Windows-репозитория; отдельный venv и data, browser open |
| tools/rdg-preview.py | Явный --test-preview, три новых Graph, общий backend/WebAuthn, сохранение settings/key/data |
| tools/rdg-loopback-helper.py | Общий PortableEditor и loopback HTTP transport, вынесенные из legacy Helper без второго writer |
| tools/rdg-windows-lock.py | Windows byte-range locks; shared запросы сериализуются как exclusive |
| tools/requirements-preview.txt | WebAuthn requirements + tzdata 2026.5 для Windows ZoneInfo |
| tools/rdg-portable.py | Trusted Python composition принимает optional io_override/authority_factory; JSON и CLI flags их не выбирают |
| tools/rdg-workflow-helper.py | Re-export PortableEditor и делегирование общему loopback, legacy путь сохранён |
| tools/rdg-authority.py | Windows import fallback для locks; preview явно использует свой _save adapter |
| tests/visual/rdg-manual-preview.cjs | Реальный manual launcher/Viewer/WebAuthn/writer, restart и защита чужого data dir |

В ручном preview используются тот же Application/planner/FileStore/writer и та же криптографическая проверка, а не mock commit. Только platform IO/Authority persistence явно внедрены host composition для preview. Обычный backend по умолчанию сохраняет POSIX IO. Windows preview делает file flush, replace/readback и byte-range exclusion, но пропускает directory fsync. Он не доказывает production Windows durability, power-loss recovery или OS isolation.

### 7.2 Что делает Start-Preview.cmd

Требует Python через py -3 и Node.js. Создаёт %LOCALAPPDATA%\RDG-ManualPreview\venv и устанавливает tools/requirements-preview.txt при отсутствии импортов fido2/cryptography/tzdata. Запускает Python с UTF-8, -B, --test-preview, --data-dir %LOCALAPPDATA%\RDG-ManualPreview\data, --port 8794, --open-browser. Скрипт остаётся foreground процессом; после работы закрыть его консоль/остановить свой процесс.

Важно: G2 venv выше — другая учётная запись и другой путь. Start-Preview.cmd создаёт окружение пользователя, который сам его запускает. Готовность его Python/Node и сам cmd-проход не проверялись. В коде используется SourceFileLoader.load_module; фактически проверены Repo Python 3.11 и найден G2 Python 3.13.16. Совместимость иной пользовательской версии Python не считать автоматически доказанной.

Сначала создаются новый demo Authority, два тестовых grants и три Graph: 01-approve («Согласовать план работ» → «Согласовать план после проверки пользователем»), 02-reject («Сохранить исходный вариант» → предложение «Заменить исходный вариант»), 03-free («Свободная правка»). Первые два защищены edit lock и имеют pending requests. Последний доступен для ordinary edit. Примеры не используют живые owners.

Данные сохраняются вне code root. Preview отказывается инициализировать неизвестный непустой каталог. После restart origin/port и credential сохраняются, session URL меняется; новая ceremony нужна для нового действия. Новый active key не требует повторной регистрации. Preview автоматически готовит и при необходимости обновляет приглашение; это признанное тестовое упрощение доверенной enrollment.

### 7.3 Минимальный ручной проход

1. Открыть Start-Preview.cmd в своём Windows-сеансе и дождаться Viewer.
2. В панели запросов нажать «Зарегистрировать ключ» и пройти штатный browser/system dialog.
3. Открыть запрос с объяснением «Проверка подтверждения», прочитать Было / Станет, подтвердить и проверить новое название R1.
4. Открыть «Проверка отказа», отклонить и проверить сохранение исходного названия.
5. Открыть Graph «Свободная правка», проверить обычное редактирование без обязательного нового key dialog.
6. При желании закрыть и повторно запустить свой процесс, проверить сохранность данных/ключа. Пользовательский feedback важнее очередной общей сверки.

Занятый 8794 не освобождать убийством неизвестного процесса. Если это уже собственный preview, разобраться с его консолью/адресом. Смена origin/порта затрагивает сохранённый binding; не отключать origin/challenge checks ради обхода startup-проблемы. Не удалять всю data ради повтора без нужды: там тестовый ключ и результаты ручной проверки.

## 8. Проверки и пределы результатов

**Последний завершённый preview-срез:**

| Проверка | Фактический результат | Что доказывает |
|---|---:|---|
| tests/visual/rdg-manual-preview.cjs | 4/4 | Три отдельных примера; native registration; Approve/write и Reject/no change; restart и новый consent сохранённым ключом; отказ немаркированным данным |
| tests/visual/rdg-approval-viewer.cjs | 16/16 | Основной generated Viewer/transport, before/after, Approve/Reject, stale P2, target change, cancellation, JSON fallback, lost response/status/recovery, scope/origin/claims |
| tests/rdg-approval-surface.test.py | 7/7 | Transport/scope/expiry/client claims, recovery, manual-lock gate с synthetic verifier |
| tests/rdg-workflow-helper.test.py | 17/17 | Legacy Helper regression после выделения общего loopback |
| tests/rdg-documentation.test.cjs | 5/5 | Действующая документация/links/classification перед этой передачей |

Все native browser cases выполнялись в изолированном Docker Chromium с виртуальным CTAP2 authenticator. Технический preview verdict: mainViewer=true, realHumanProof=false, osIsolationVerified=false, liveOwnersTouched=false. Это не проверка owner Windows GUI, установленного Tampermonkey или реального пользовательского ключа.

**Предшествующий persistent/execution срез, исторические PASS:** credential store 9/9, execution 17/17, prework 15/15, portable store 12/12, transports 11/11, bearer authority 2/2; native WebAuthn 31/31, persistent Viewer 11/11. Persistent fixture проверяла настоящий новый PID на прежнем origin, старую ceremony, новый consent, audit после restart, revoke после staging, accepted recovery, замену ключа и управление замком через pending. Эти suites не надо объявлять заново выполненными на последнем refactor только потому, что они перечислены; последние regressions приведены отдельной таблицей.

Ранее Stage 1–3 имели свои semantic/core/UI/lock/dependency tests; подробнее рабочий план и предыдущий Stage 3 handoff. Не складывать повторные прогоны как разные независимые доказательства и не принимать полный S24/Stage 4 по общему числу зелёных проверок.

В начале manual fixture был пойман ошибочный seed: переданный Graph не соответствовал ready-role validation. Исправлен только seed — создание исходного Graph передано общему create builder, guard не ослаблялся. В persistent browser proof прежде была исправлена тестовая предпосылка counter==0: registration counter оказался 1; строгая counter policy сохранена.

Скриншоты для внутренней проверки: /workspace/repo/rdg-visual-output/rdg-manual-preview.png (76 323 байта), rdg-approval-viewer-desktop.png и rdg-approval-viewer-mobile.png в том же каталоге. Manual screenshot просмотрен: реальная панель регистрации/запросов и Было / Станет. Это технический вид, а не подтверждение удобства пользователем. Сессионные URL и реальные bearer в хендофф не включены.

### 8.1 Команды адресного повторения

```sh
cd /workspace/repos/rd-graphs
GIT_OPTIONAL_LOCKS=0 PYTHONDONTWRITEBYTECODE=1 \
RDG_WEBAUTHN_PYTHON=/workspace/repo/.rdg-webauthn-venv/bin/python \
  bash tools/rdg-visual-test.sh tests/visual/rdg-manual-preview.cjs
```

С теми же переменными можно выбрать tests/visual/rdg-approval-viewer.cjs, rdg-persistent-approval.cjs или rdg-webauthn.cjs. Обёртка подключает подготовленные Chromium/sysroot/fontconfig. puppeteer-core был доступен в /opt/dc/node_modules/puppeteer-core. Если runtime исчез, сначала проверить реальные пути и запуск; ошибка загрузчика не означает PASS. Общую инфраструктуру из-за этого не перезапускать.

```sh
cd /workspace/repos/rd-graphs
PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0 python3 -B tests/rdg-approval-surface.test.py -q
PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0 TMPDIR=/workspace/repo python3 -B tests/rdg-workflow-helper.test.py -q
GIT_OPTIONAL_LOCKS=0 node --test tests/rdg-documentation.test.cjs
git diff --check
```

Повторять подходящий scope после изменения или новой ошибки. Не тратить ранний ручной проход на полный повтор всех прежних suite без причины. После правок rdg-portable-ui.js пересобрать generated Viewer штатным python3 -B tools/build-rdg-layout.py и проверить parity; не править одновременно две копии логики вручную.

## 9. Непроверенное и оставшаяся работа

**Сейчас:** пользовательский Windows startup и первый manual feedback. Нет подтверждения, что пользователь открыл Start-Preview.cmd, прошёл свой настоящий WebAuthn dialog и оценил удобство. Это ближайший следующий шаг.

**После первого feedback:** нужные UX/startup fixes; единый inventory WR-29/53 (23 high-level API operations, 24 exposed core/paper_edit commands без remove, 15 lock operations; в самом kernel COMMANDS 25 с remove); полный mapping key-required eligibility, actual grants, direct/indirect object+operation effects и owners; несколько principals; key-management UI, сейчас configure/invite/revoke только CLI; portable pending при copy/move/orphan authority и readback инициатора.

**Известные отложенные security/platform risks:** Agent writable code/data/Authority boundary не доказана; real human/user binding не принят; preview invitation автоматическое; Windows directory/power-loss durability не проверена; полный real-key revoke/restart/recovery в пользовательском окружении не выполнен. Mode 0600, путь вне проекта и два процесса под одной учётной записью не доказывают OS isolation. Эти риски отражать, не скрывать и не ставить обязательным блокером отдельного учебного preview вопреки последнему решению пользователя.

**Далее Stage 5/6 и общий план:** full human-operation parity в одном Viewer, установленный Windows/Tampermonkey и переносимый пользовательский проход; независимый final review N/FR/S/WR/EA без ложных PASS. В большом плане RDG также остаются модульная подсистема, более широкая матрица Gendocen dependencies, визуальные/геометрические/доступностные gates и общий audit/DRY. Не расширять эти направления попутно вместо ближайшего результата.

Этот хендофф не является независимой Stage 6. Новых semantic user decisions по пяти Canon, L1/L2 или locks для продолжения не требуется. Существенную новую развилку прав/scope/пользовательского пути решать отдельно; routine implementation choices выполнять самостоятельно.

## 10. Отказ передачи архива и выбранный маршрут

Для G2 был подготовлен полный тестовый runtime build без реальных данных: архив 247 835 байт, логический набор 904 688 байт, 24 файла. Лимит 1 000 000 байт на файл и logical set соблюдался. Automatic approval review отклонил команду кодирования/вывода приватного архива для передачи через контекст в G2: пользователь не дал явного разрешения на этот payload и destination.

Архив НЕ был передан. Не обходить этот отказ chunks, другим reader/connector, косвенным исполнением или расширением доступа к owner path. Временный build script и свой неиспользуемый архив удалены; это не существующий deliverable. Использован существенно более безопасный путь: Start-Preview.cmd читает уже имеющиеся Windows-файлы проекта, а пользователь сам запускает свой процесс/браузер. Это не требует копии проекта, нового tunnel или доступа Agent к owner GUI.

Поручение создать этот текстовый хендофф прямо разрешает его передачу пользователю для следующего чата. Он содержит инструкции, состояние и hashes, без архива исходников, живых credentials или содержимого private Authority. Это не автоматическое разрешение на иной будущий source export.

## 11. Работа с инструментами в новом чате

Находить текущие capabilities через ALL_TOOLS по точным нужным именам. Использованные active tools: mcp__codex_apps__fortis_repo_get_config/get_file_info/read_file/start_process/read_process_output; для G2 — mcp__codex_apps__fortis_host_g2___restricted_test__fortis_host_g2_restricted_test_*. Не подменять их старым owner app route или считать две Repo namespaces одинаковыми без проверки.

Fortis Repo start_process принимает command и timeout_ms; сначала явно cd в /workspace/repos/rd-graphs. Если вернулся PID/running — читать тот же process output, не запускать запись повторно. При functions.exec «Script running with cell ID» продолжать через functions.wait, а не считать этот ID OS PID.

Периодически встречался «MCP server is not initialized». Для безопасного read можно повторить тот же запрос. После timeout/ошибки мутации сначала проверить фактический эффект. Не перезапускать общий Tunnel/Repo и не расширять allowedDirectories из-за единичной ошибки. Не печатать в чат raw bearer, permits, private stores, browser profile/clipboard/owner state.

Не рассчитывать на functions.store/load или историю этого чата: на новом turn сохранённые JS значения уже пропадали. Использовать файлы хендоффа, текущие источники и свежую проверку. Independent reads можно batch через Promise.allSettled, inspect каждый result; fulfilled wrapper может содержать isError внутри. Не посылать несколько mutations параллельно.

## 12. STATE.json и fingerprints

Рядом сохранён STATE.json: полный manifest всех исходных 1 812 paths (SHA-256 или null для отсутствующего tracked path), Git status до этой передачи, refs/index hash, critical files, owners и scope добавления хендоффа. Manifest исключает новые HANDOFF.md/STATE.json, чтобы не создавать self-hash cycle; hash RDG-CURRENT-STATE.md в нём соответствует добавленной ссылке на эту передачу. После добавления двух файлов ожидается 1 814 путей.

При различиях с новым working tree сначала выяснить legitimate новые изменения. Не откатывать их по snapshot автоматически. Проверять текущие права/paths отдельно от snapshot: hashes не дают OS-полномочий.

| Файл | Байты | SHA-256 на передаче |
|---|---:|---|
| `Start-Preview.cmd` | 870 | `a08bf67e6f2090891822d9170959204cd5d190c16543620ed52e6357c17a7b79` |
| `tools/rdg-preview.py` | 10731 | `8f547f3f4460dcaaff6cfa198ba7330f2ae6f9d1829ed191e4b5d9f31f9f6af8` |
| `tools/rdg-loopback-helper.py` | 8410 | `1fa21b9137cb6d3f7eeee95099e0d0784bd176848b281dbb5693fcad0131b50c` |
| `tools/rdg-windows-lock.py` | 1148 | `3610678539f265f0c02fe5b785da5559b4792c5a977b297d9f08d04769048734` |
| `tools/requirements-preview.txt` | 44 | `d190a0f226d9ad8ef1a686d062c29360df04cfb5d5d3873e83bf966302fe08be` |
| `tools/rdg-portable.py` | 5990 | `a12ebf0d8db9d41a77699f35f734a41d81cc57cd381129b1f7cbb52f018f74db` |
| `tools/rdg-authority.py` | 21264 | `bc569f0d254a8d7bf20494a56976d8dd7576a65cbab83e95126c3da159b082d0` |
| `tools/rdg-workflow-helper.py` | 40739 | `7884522c65d994f298409ee071020d2cad11f521c9da5b7dea8a2e925e1425d0` |
| `tools/rdg-core-model.py` | 78673 | `9e054d3e08aebd94663679a1d00a96f419473bf371ff7385e97f41e3998f64aa` |
| `tools/rdg-portable-service.py` | 70775 | `1943b326c41f2d41aca874acd9b4ba2cba5da6738f8d9fb3d4da852d3a974259` |
| `tools/rdg-portable-store.py` | 41930 | `8d714db0d2dbc560294f2775035844e4631051d0e32845608ad49e41b2a70eff` |
| `tools/rdg-portable-model.py` | 43807 | `2fb2440f9b8d9b0e8f00f7a6b4d15a6d91a79427f15d40f57c0aa73d649ad00f` |
| `tools/rdg-transaction-io.py` | 5344 | `2c03ee37f52fd85438feb5cc5e68322bbd426c3fee697ea77393d7ea219e8b18` |
| `tools/rdg-approval-executor.py` | 10892 | `ccfc42e4f4d140534fa7b2e5da57853e7733f4db3989a5a77296af5b5fd1dc9c` |
| `tools/rdg-approval-surface.py` | 9009 | `2a9c7862c798ab1b69a9a754a7ff4cda6e81756e360fd5fd73b7ca1d795b9fe5` |
| `tools/rdg-webauthn.py` | 12376 | `06fc02b17c895d4be5e0a62d205c2aee28722e5b18b5bdadda9d8199e2745d0f` |
| `tools/rdg-credential-store.py` | 16285 | `d1a749c273bc0c25871cda13c36404d75ab0f46987cc47516364bb678f366b16` |
| `tools/rdg-credentials.py` | 3442 | `4dfeae6834cb85645e313dd7dcc99a34ef1b7bd386fdd2c713500eff4333c1ab` |
| `tools/rdg-portable-ui.js` | 70150 | `e3336fd60764fed4274d6ee5a84493db8392d0cf9de267e9c45ff216650cc1d2` |
| `tools/rd-graph-viewer.user.js` | 484341 | `3f050097da4c15baf4877f4bc646f5cfbb183e310c483b174d23b6f6f368be8f` |
| `tools/requirements-webauthn.txt` | 140 | `3b1106349bd00ebe3118fc183ac9dbc8112490af0e005adc5f532b21c3c096b3` |
| `tests/visual/rdg-manual-preview.cjs` | 7565 | `1a076e866f99daf1180626619439265bc1fe8ed6cd68a1ec38cb2a5b09dc1726` |
| `tests/visual/rdg-approval-viewer.cjs` | 14748 | `ffbbd0422a64eddca91c7bb8c482de5bd8b9a55f3fb70316840b97bf69ab0244` |
| `tests/visual/rdg-persistent-approval.cjs` | 12105 | `735b6141d757615c9ca0df5670bae54973b99cc8be0bfa6420522519bd6e7736` |
| `tests/rdg-credential-store.test.py` | 10282 | `6d7f1671a954fdcbf32a53879ba1b16f23dc6f9e6bb9a797f45940fdb8f435ef` |
| `tests/rdg-approval-surface.test.py` | 8984 | `5f91522bc1b71b53732fee723824be862e01bb518ea7548dc7419b851b454d12` |
| `tests/rdg-approval-execution.test.py` | 19550 | `21c1102df7eefc6025b6e19f3e9dc01767b3821c3987fa5ee26555a8fd923d73` |
| `tests/rdg-approval-prework.test.py` | 20733 | `c423812fff2d275e13e351b70e4f68adff0b6ec8ae5f3da2cc41462964d54ad3` |
| `tests/rdg-persistent-viewer-fixture.py` | 8833 | `44c03aeef497b1bbf3ad936f04b6c25918ab3054f39e727ccab736f23ad278bf` |
| `tests/rdg-persistent-viewer-runtime.py` | 3264 | `2007100819f5d76d573ace8b4dbf0bc72a619e8bbbb40205066ebc34316bd222` |
| `tests/visual/README.md` | 13765 | `c0cc8a6fd11b46740c1d59e2462ee08f67de342476b66f5635abfdd76bfad7b3` |

## 13. Короткое сообщение для нового чата

```text
Продолжи RDG по /workspace/repos/rd-graphs/docs/handoffs/rdg-preview-first-20261025/HANDOFF.md и соседнему STATE.json. Сначала прочитай AGENTS/current-state и проверь путь, mount, git status. Последний приоритет пользователя — ранняя ручная проверка через Start-Preview.cmd; security risks известны и отложены. Код и browser proof готовы, первый пользовательский Windows-запуск ещё не подтверждён. Учти новый feedback и помоги пройти этот шаг; не начинай проект/аудит заново и не переписывай существующий dirty tree.
```
