# Fortis — зафиксированная смена архитектуры: старый reporting → рабочий цикл через защищённый Sonar Gateway

**Статус:** проектная запись и инвентаризация существующего кода. **Дата среза: 30 октября 2026 года.** Основано на просмотре `main` трёх GitHub-репозиториев и действующих workflows, а также на ранее проверенных CI и Windows smoke. **Этот файл не вносит изменений в репозитории и не означает, что Gateway уже создан или авторизован.**

**Существенный подтверждённый факт:** на доверенном Windows **уже работала авторизация через SonarQube CLI (`sonar`)**; скрипты вызывали `sonar api get` для приватного `gd-cap` и других разрешённых Sonar данных. **Новое решение не «научить Sonar авторизации», а перенести эту работающую возможность из Windows в защищённый контейнер**, доступный Fortis через ограниченный сетевой интерфейс. Интерактивный вход и credential из существующей Windows-сессии **не переносятся автоматически** — новая среда авторизуется отдельно.

**Основное решение:** перестать считать Windows reporting Dispatcher обязательным шагом к Fortis. Сначала строим минимальный **цикл разработки приложения**: задача → работа над кодом в Fortis Repo Docker *или* через GitHub connector → ветка и PR → GitHub Actions CI/SonarScanner → Fortis читает SonarCloud через отдельный защищённый контейнер → при необходимости правит PR → владелец проверяет и объединяет → отдельная Windows-копия получает определённую версию → отдельное решение о запуске. После одного рабочего цикла тот же процесс используем для разработки самого Fortis.

Ниже **as-built**, **что сохраняем**, **что меняем**, **точное значение «логина в Sonar внутри контейнера»**, и последовательность безопасного упрощения.

## 1. Карта репозиториев и подтверждённое состояние

| Репозиторий | `main` на момент сверки | Его роль в старой системе | Роль в новой |
|---|---|---|---|
| [`AlexPastukhh/gd-cap`](https://github.com/AlexPastukhh/gd-cap) | `93648b45e2564b27d1fb21902074d579a330035c` | Продукт, Java CI + SonarScanner, формирование дополнительного `fortis-sonar-run` artifact | Рабочий проект: код, PR, тесты, SonarScan; legacy metadata позже убрать |
| [`AlexPastukhh/obs-planning-docs`](https://github.com/AlexPastukhh/obs-planning-docs) | `682fed9b3da35266ca6164fec651819751196fee` | Продукт/документы, SonarScanner определённой JS-области, дополнительный metadata artifact | Рабочий проект: код, PR, целевой JS SonarScan; legacy metadata позже убрать |
| [`AlexPastukhh/fortis-security-reports`](https://github.com/AlexPastukhh/fortis-security-reports) | `35099fdc473f7451bf21702634c4d33cc1ea59cf` | **Отдельный приватный архив** JSON, Windows Collectors/Publishers, облачный hourly OBS collector, экспериментальный Stage 7 | Оставить как исторический архив/потенциальную подсистему; **не считать основным репозиторием Fortis Core или Gateway** |

**Открытые PR:** [#32 — проектный `published` для старого Stage 7](https://github.com/AlexPastukhh/fortis-security-reports/pull/32) и [#33 — прежний Gateway-first roadmap в *архивном* репозитории](https://github.com/AlexPastukhh/fortis-security-reports/pull/33) оставлены открытыми, **не объединять автоматически**. Новый самостоятельный план точнее определяет **code-first** цикл с Windows как конечным этапом; не нужно принимать #32/#33 как утверждённую реализацию. Старая ветка разработки и архив не удалены.

## 2. Как работала старая версия (AS-BUILT, а не ожидания)

### 2.1 Исходные проекты: GitHub CI и SonarScanner

В обоих исходных репозиториях `.github/workflows/sonarqube.yml` запускает SonarScanner с отдельным GitHub Actions secret `SONAR_TOKEN`, передаёт `sonar.qualitygate.wait=true` и ждёт Quality Gate. `sonar-project.properties` задаёт проект, организацию, анализируемые исходники и тесты.

- **`gd-cap`:** `checkout`, Java 21, `sh build-java.sh` (компиляция + self-test), затем SonarScanner. В `sonar-project.properties` сканируются **`java-src` + Java binaries**; это **не** заявка на сканирование всех Windows/C#/AHK частей продукта. `pull_request` запускается на открытие/обновление PR; `push` для `main`; есть `workflow_dispatch`.
- **`obs-planning-docs`:** SonarScanner проверяет конкретный JavaScript Tampermonkey/Chat Command Palette и его тесты из `sonar-project.properties`, **не весь документационный репозиторий**. `push` и `pull_request` имеют `paths:`-фильтр. Для изменений вне этих путей Sonar workflow может **не запуститься** — отсутствие/пропуск Sonar-check не равно `PASS`.

Для старой цепочки **вдобавок** к Scanner были установлены (в обоих проектах):

1. `Prepare Sonar run metadata` — очищает временные `fortis-sonar-*` файлы, сохраняет checkout SHA.
2. `Test Sonar run metadata writer` — проверяет Python writer.
3. Scanner получает дополнительный `-Dsonar.scanner.metadataFilePath=.../fortis-sonar-report-task.txt`, чтобы получить CE task ID.
4. `Write advisory Sonar run metadata` (`.github/scripts/write_sonar_run_metadata.py`) — создаёт `fortis-sonar-run.json` с GitHub repo/run/attempt, событиями, PR head SHA, фактическим checkout SHA, CE task ID (если доступен) и честными флагами `analysis_to_sha_verified=false`, `historical_findings_verified=false`, `guard_approval=false`.
5. `Upload advisory Sonar run metadata` — сохраняет GitHub Actions artifact `fortis-sonar-run-<run-id>-attempt-<attempt>` с retention 90 days.

**Назначение дополнительных шагов:** снабжать отдельный Fortis evidence reader точной metadata для GitHub run. **Это не обязательные составляющие SonarScanner**, но без них конкретный старый Windows evidence reader теряет входной artifact. Нельзя просто удалить их без учёта зависимости.

### 2.2 Ручной Windows reporting, Stage 5

В приватном `fortis-security-reports` владелец вручную исполнял **доверенные Windows PowerShell 5.1** скрипты с GitHub/Sonar-доступом. Главное звено — [`scripts/manual-sonar-cycle-common.ps1`](https://github.com/AlexPastukhh/fortis-security-reports/blob/main/scripts/manual-sonar-cycle-common.ps1), entrypoint [`scripts/run-sonar-report-cycle.ps1`](https://github.com/AlexPastukhh/fortis-security-reports/blob/main/scripts/run-sonar-report-cycle.ps1).

Последовательность **фактически реализована именно так**, включая частичные исходы:

1. По точным `ProjectSlug / RunId / Attempt` повторно проверяется GitHub workflow run и собирается **run receipt**; он staging-ится и публикация **пытается выполниться первой**, отдельно от Sonar.
2. После этого Windows reader загружает `fortis-sonar-run-*` metadata artifact из GitHub, проверяет идентичность и при возможности читает Sonar CE task, analysis и Quality Gate через Sonar API. Собирает **advisory evidence**, но **не** исторический снимок всех Issues конкретного SHA.
3. `publish-sonar-evidence.ps1` записывает immutable evidence JSON в приватный архив. Если metadata отсутствует/истекла, Sonar API недоступен или evidence не получилось, уже записанная receipt **сохраняется**. Цикл диагностируется как `incomplete`, а не притворяется полным.
4. Если явно задан `-IncludeLiveSnapshot`, отдельно собирается текущий branch-time live snapshot (Issues/Hotspots/Quality Gate + manifest); он не считается историческими findings для этого GitHub run. Ошибка snapshot не отменяет уже сохранённую receipt.
5. Все шаги отражаются в локальном `cycle-result.json` со статусом complete/incomplete, bounded error codes и путями staging. Нет автоматического восстановления или Guard approval.

В реальном Windows были проверены **два основных цикла**: OBS с Gate OK и `gd-cap` с Gate ERROR/failed GitHub workflow. Некоторые edge cases (missing/expired artifact, optional snapshot через единый entrypoint, конкурентные полные циклы) оставались без реального owner smoke. **Stage 5 — рабочий ручной путь, не автоматический Fortis Core.**

### 2.2.1 ВАЖНО: на Windows уже был авторизованный «логин» SonarCloud, и он работал

**Это подтверждённый элемент старой системы, а не новая гипотеза.** На машине владельца под доверенной Windows-учётной записью уже был установлен и **авторизован SonarQube CLI (`sonar`)**. Его авторизованное состояние использовалось для чтения SonarCloud и позволяло обращаться к **приватному** `gd-cap` без передачи Sonar-секрета ассистенту, PowerShell-скриптам или GitHub Actions reporting-архива.

В старой документации [`docs/windows-private-reports.md`](https://github.com/AlexPastukhh/fortis-security-reports/blob/main/docs/windows-private-reports.md) это записано явно: Windows использует *already authenticated `sonar api get`*, а запрос к `gd-cap` уже был проверен интерактивно с того же Windows account. Диагностическая команда — `sonar auth status`. В [`scripts/private-sonar-common.ps1`](https://github.com/AlexPastukhh/fortis-security-reports/blob/main/scripts/private-sonar-common.ps1) реальный вызов выглядел так:

```powershell
# Пример старого режима: выполнялся под УЖЕ авторизованным Windows-пользователем.
sonar auth status
sonar api get "/api/project_analyses/search?project=AlexPastukhh_gd-cap&branch=main&ps=1"

# Фактически используемый PowerShell-хелпер:
$lines = @(& sonar api get $Endpoint)
```

**Что именно давал этот login:** уже авторизованный CLI мог делать разрешённые правами учётной записи запросы Sonar API, возвращал JSON с анализами, Quality Gate, Issues и Security Hotspots. Этим пользовались Windows collectors и evidence reader, включая чтение `/api/ce/task`, `/api/qualitygates/project_status` и `/api/project_analyses/search`. **Скрипты лишь передавали CLI endpoint, CLI сам управлял аутентификацией.** Это не та же вещь, что `SONAR_TOKEN` GitHub Actions для SonarScanner; это отдельная доверенная Windows-среда и отдельная авторизация. Для GitHub-данных Windows отдельно использовал авторизованный `gh` CLI.

**Что известно и что нет:** успешный доступ и наличие настроенной CLI-авторизации подтверждены проектной документацией и реальными Windows smoke; **точный способ первоначального входа** (браузерный `sonar auth login`, ввод токена, внешний credential store) и реальные права Windows credential **не доказаны содержимым GitHub**. Официальный SonarQube CLI поддерживает браузерный `sonar auth login` с сохранением credential в системном keychain, а также token-based noninteractive mode. Поэтому говорить «у нас была работающая авторизация Sonar в Windows» корректно; утверждать конкретный тип сохранённого секрета — нет.

**Что переносим:** именно способность *доверенной среды* выполнить авторизованный `sonar api get` и вернуть Fortis только допустимые результаты. Вместо зависимости от того, включён ли твой Windows и выполнен ли там login, авторизация будет принадлежать **изолированному Sonar Gateway-контейнеру**. Это перенос trust boundary, а не новая проверка самой возможности работать с приватным SonarCloud. Авторизация **в новом контейнере и сетевой доступ Fortis Repo к нему пока не проверены**.

### 2.3 Облачный архивный OBS collector и конкурирующие Git writers, Stage 6

Отдельный workflow [`fortis-security-reports/.github/workflows/collect-sonar.yml`](https://github.com/AlexPastukhh/fortis-security-reports/blob/main/.github/workflows/collect-sonar.yml) продолжает иметь `workflow_dispatch` и расписание `17 * * * *` UTC (GitHub может задерживать scheduled runs). На GitHub-hosted Linux он:

- запускает тесты нормализации;
- выполняет `scripts/collect_sonar.py` — публичные **текущие OBS Sonar данные** без пользовательского Sonar-токена;
- выполняет `scripts/collect_public_run_receipts.py` — периодически сверяет **историю GitHub Actions** и дописывает отсутствующие публичные OBS receipts;
- выполняет `scripts/publish_cloud_reports.py` — публикует immutable JSON в тот же архив с ограниченным non-fast-forward retry, без force push и перезаписи чужих файлов.

**Важное разграничение:** исторический backfill делает **старый облачный OBS collector**. Запрет автоматического history backfill в принятой ранее политике A относится к **проектировавшемуся Windows Dispatcher**, а не к облачному workflow, который уже существует.

Две реальные гонки **Cloud ↔ Windows writer** были проверены в обе стороны (Stage 6/P2): существующие файлы не переписывались, сообщения о конфликтном Git push не маскировались. Это доказательство **надёжности старой публикации в пределах теста**, не требование к будущему Gateway. Система реально записала JSON в архив и остаётся действующей, пока владелец отдельно не остановит schedule.

### 2.4 Stage 7 — написанный, но НЕ введённый в работу Dispatcher

В `fortis-security-reports` уже объединены PR [#27](https://github.com/AlexPastukhh/fortis-security-reports/pull/27)–[#31](https://github.com/AlexPastukhh/fortis-security-reports/pull/31):

| Код | Что есть | Что НЕ заработало как общий сервис |
|---|---|---|
| `scripts/dispatch-journal-common.ps1` | offline журнал принятых задач, дедупликация | нет сетевого приёма и исполнения Collector |
| `scripts/dispatch-verified-run-common.ps1` | exact GitHub run/attempt re-fetch | нет постоянно работающего Dispatcher |
| `scripts/dispatch-task-state-common.ps1` | append-only диагностические состояния и ручной read-only список незавершённых | нет `published` без proof и нет recovery worker |
| `scripts/dispatch-recovery-preflight-common.ps1` | read-only точная receipt на pinned archive SHA | нет разрешения/исполнения retry |
| `scripts/dispatch-evidence-inventory-common.ps1` | read-only проверка архивных evidence blobs/hash | не доказывает полную публикацию и не запускает задачи |

Windows PowerShell 5.1 **offline CI** для этих модулей прошёл. **Реального Windows Dispatcher smoke, Receiver, webhook или auto-recovery нет.** Ранее согласованная политика A: уже принятые локальные задачи переживают crash; после перезапуска только ручной обзор, никакого автоматического восстановления; события во время отсутствия Windows **не** догоняются.

### 2.5 Что старое НЕ делало

Старая система **не была** инструментом, который берёт задачу разработки, исправляет код, создаёт PR, читает Sonar и переносит готовое приложение в Windows. Она была *подсистемой сбора, архивирования и диагностики отчётов*, главным образом с ручным Windows участием. Отчёты, Green Gate и подтверждённый archive blob **никогда не были Guard approval, разрешением на импорт или выполнение кода**. Независимый Guard/Windows Commit Gate описывался и прототипировался отдельно; действующий защищённый импорт всей цепочки **не подтверждён**.

## 3. Новое решение — что заменяем и что НЕ заменяем

| Прежний механизм / задача | Новая реализация / решение | Статус |
|---|---|---|
| Для получения Sonar данных вручную запускать Windows Collector и публиковать `evidence` в GitHub archive | **Fortis Core запрашивает живые нужные данные через защищённый Sonar Gateway** и сразу использует их для исправления кода | **Запланировано, не проверено** |
| Для работы AI нужна копия приватных Sonar результатов в GitHub JSON-архиве | AI читает **фиксированный API Gateway**, у которого Sonar credentials; сложная архивная публикация **не является обязательной для MVP** | Запланировано |
| Рабочая разработка reporting-инструментов в GitHub connector + ручные PowerShell команды на Windows | Правка в **Fortis Repo Docker ИЛИ GitHub connector**, PR, CI и исправление в рабочей среде; Windows нужен только для финальной доставки/запуска | Запланировано |
| Сложный Windows Dispatcher, журнал, Receiver/webhook, replay, stages 7–10 | **Откладываем**, не включаем в MVP; не создаём дополнительных циклов retry | Код Stage 7 остаётся, не используется |
| GitHub Actions build/tests/SonarScanner и scanner `SONAR_TOKEN` | **Сохраняем**, они выполняют анализ и проверку кода; Gateway их не заменяет | Реально работает |
| Registry для разрешённых проектов | Небольшой allowlist в Gateway/политике Core; можно использовать существующие сведения, не плодя БД | Запланировано |
| Сонар-артефакт `fortis-sonar-run-*` для старого reader | Может исчезнуть **после** успешного Gateway smoke и решения об отключении old reader | Пока сохранён |
| Cloud OBS hourly reporting и накопленный архив | **Не удаляем сейчас**; после доказанного MVP решаем отключение расписания и сохранение истории | Активный legacy путь |
| Нужны ли общие Docker/Windows директории | **Нет**: отдельные Git clones, обмен кодом через GitHub, сетевые HTTP-запросы к Gateway | Архитектурное решение, сеть ещё не проверена |
| Sonar API чтение / редактирование Issues / администрирование | Gateway: **сразу только разрешённое чтение; write — отдельное точное подтверждение владельца позже** | Write/approval не реализованы |
| Guard / перенос Windows | Защищённый импорт/запуск — отдельные права и проверки; Sonar Gateway не подтверждает код и не разрешает выполнение | Будущая ветка работы |

**Нельзя сказать, что «всё старое не нужно».** Сохраняются работающие **проверки кода**, отчётные архивы и пригодная позже Windows-наработка. Но для проверки новой архитектуры **не надо** продолжать строить их как обязательный слой.

## 4. Что именно означает «Sonar login в контейнере»

### 4.1 Что значит «логин Sonar внутри контейнера» — аналог уже работавшего Windows CLI

**Требуемое поведение:** контейнер работает под доверенным оператором с настроенной аутентификацией SonarQube Cloud; внутри него доступна та же категория авторизованных запросов, что уже работала в Windows: `sonar api get` и JSON-результаты. Fortis Repo/AI **не логинится в SonarCloud самостоятельно**, не видит токен и не получает возможность вызывать произвольные CLI-команды. По сути мы **переносим авторизованный CLI-клиент из Windows на постоянно доступный защищённый runtime**.

Для MVP есть два способа реализации **внутри Gateway**; снаружи API Fortis остаётся одинаковым:

1. **Предпочтительно для преемственности:** установить поддерживаемый `sonar` (SonarQube CLI) внутри защищённого контейнера. Gateway для фиксированных разрешённых операций формирует заранее известный GET endpoint и вызывает только `sonar api get <точный endpoint>`. CLI сам подставляет авторизацию. **Никаких** передаваемых клиентом исполняемых команд, аргументов `sonar api post`, произвольных URL или shell-строк. Такой CLI **не является** Sonar MCP Server и не требует его установки.
2. **Равнозначный упрощённый вариант:** Gateway самостоятельно делает строго allowlisted HTTP GET к SonarCloud Web API с `Authorization: Bearer <TOKEN_ТОЛЬКО_В_GATEWAY>`. Это тот же upstream API, который вызывает Sonar CLI. Не обязательно создавать отдельную подсистему CLI, если обычный HTTPS-клиент окажется проще и проверяемее.

**Само понятие «логин»:** в CLI интерактивный `sonar auth login` может открывать браузер и сохранять credential в системном keychain. Для безголового Docker-режима **не нужен браузер или общий volume с Windows**: администратор защищённой среды заранее создаёт/передаёт credential при старте. Официальный CLI поддерживает `SONARQUBE_CLI_TOKEN` **вместе с** `SONARQUBE_CLI_ORG` (и при необходимости `SONARQUBE_CLI_SERVER`) для автоматизации; проверка доступности — `sonar auth status` и настоящий GET к приватному проекту. Без постоянного тома сохранённый внутри контейнера login может исчезнуть при пересоздании контейнера: **предусмотреть повторную безопасную подачу секрета при старте**, но не монтировать его в AI-контейнер. Пароли и браузерные cookie не нужны.

**SonarScanner — другое приложение:** его по-прежнему запускает GitHub CI для анализа исходников со своим `SONAR_TOKEN` из GitHub Secrets. Gateway/авторизованный Sonar CLI предназначен для чтения результатов, а не замены сканера. **Ни ChatGPT, ни Fortis Repo не должны видеть credential.** Для чтения Issues/Gate/Measures разрешаются фиксированные операции семейства `issues`, `qualitygates`, `measures` и при необходимости `ce/task`; конкретные пути и параметры перед реализацией сверяются с актуальной API-документацией.

Домен выбирается по реальному SonarCloud instance: EU `https://sonarcloud.io/api`, US `https://sonarqube.us/api`. Старый Windows-код проверял для своих задач `https://sonarcloud.io`; новый контейнер и его действительные права нужно подтвердить отдельно.

### 4.2 Где хранится ключ — и где НЕ хранится

1. На Windows **уже** существовала рабочая Sonar CLI-авторизация; для нового Gateway нужен **отдельно настроенный credential** (можно создать новый токен того же Sonar-аккаунта или, предпочтительно, отдельного read-only субъекта). Его создание, права и живой API-ответ **именно из контейнера** ещё не подтверждены. Владелец вводит credential в защищённую конфигурацию среды Gateway, не в чат, GitHub или Fortis Repo.
2. Секрет предоставляется Gateway **при запуске** (например, переменной окружения доверенного runtime или иным поддерживаемым секретным механизмом). **Общий volume или bind mount c исходниками не требуется.** Точный способ установки выбирает администратор Gateway; если используется переменная окружения, её может прочитать администратор Docker/хоста — это не изоляция от того, кто управляет daemon.
3. Только **процесс Gateway / его внутренний Sonar CLI** использует токен для SonarCloud; в ответах Fortis, JSON, журналах и отладочных сообщениях токен не появляется. Fortis Repo видит лишь нормализованные данные проекта и ошибку без чувствительного текста.
4. Рабочий Fortis Repo **не получает** Docker socket/exec/admin API, хранилище секретов и право обновлять policy, конфигурацию или image работающего Gateway. **Два контейнера на одном управляемом AI Docker daemon НЕ обеспечивают этот запрет.** Нужна отдельная административная граница (другой daemon/VM/хост или эквивалентная изоляция, факт которой проверяется).
5. Fortis Repo обращается к Gateway **по сети** (фиксированное имя/API, аутентификация клиента, network ACL, TLS при пересечении недоверенной сети). Docker не требует общих монтирований для TCP/HTTP; но сетевой маршрут **может отсутствовать** у конкретного подключения Fortis Repo — проверить, не предполагать.

### 4.3 «Токен со всеми правами, но запросы только на чтение» — важная граница

Это **технически возможно как Gateway policy**, но токен при этом **не становится read-only**. Личный Sonar токен действует в пределах прав учётной записи, создавшей его; если она администратор, компрометация Gateway потенциально даёт административные действия. Gateway ограничивает **то, что может попросить AI**, а не права украденного ключа.

**Для первого MVP:** рекомендован **отдельный Sonar user/credential с минимально достаточными правами чтения**. Если владелец сознательно использует один широко привилегированный токен в изолированном Gateway — это отдельный принятый риск, который не нужно создавать для проверки одного read-only API. В любом варианте внешний интерфейс Gateway **не** принимает arbitrary URL, HTTP method, headers, query или тело запроса.

**Позже**, если реально понадобятся изменения Sonar (False Positive, статус Security Hotspot, настройки проекта): добавить конкретные allowlisted команды с policy `APPROVAL_REQUIRED`. Gateway создаёт **точный запрос** (проект, объект, действие, старое и новое значение, срок, одноразовый ID), владелец **авторизуется в независимом канале подтверждения**, а сервер после проверки выполняет только это действие однократно. **Сообщение от AI «одобрено» не считается подтверждением.** Это ещё **не реализовано**. По возможности использовать **отдельный более привилегированный токен для write**, не раздавая его AI. Управление секретами/правами/политикой Gateway оставить запрещённым в AI API даже после подтверждения.

### 4.4 Путь одного реального GET

```text
Fortis Repo (без Sonar token)
  ── GET /v1/sonar/issues?project=gd-cap&limit=20 ──► Gateway
  [аутентификация Fortis client; серверный allowlist, limit, timeout]
  Gateway:
    gd-cap → owner-approved projectKey AlexPastukhh_gd-cap
    выбирает фиксированный SonarCloud API origin
    вызывает sonar api get с фиксированным GET endpoint,
    либо сам добавляет Bearer token к строго разрешённому HTTPS GET
  ── HTTPS GET /api/issues/search?componentKeys=AlexPastukhh_gd-cap&ps=20 ──► SonarCloud
  ◄── ограниченный JSON: issue key, rule, severity, file/line, message, status ──
Fortis Repo получает только данные, не исходный credential
```

Это **пример предлагаемого интерфейса, не уже созданные endpoints**. Для MVP достаточно двух операций: прочитать Quality Gate и ограниченную страницу Issues для одного из двух разрешённых проектов. Не нужен официальный Sonar MCP Server, оплачиваемый MCP-продукт, браузерная автоматизация, SonarScanner внутри Gateway или Windows.

### 4.5 Что подтвердит, что «авторизовались»

**Подтверждённая аутентификация** — не наличие переменной `SONAR_TOKEN` и не отсутствие ошибок запуска. Нужно увидеть:

- Gateway обращается к **нужному** Sonar instance, получает настоящий 2xx JSON по разрешённой операции для реально доступного проекта (при необходимости — к **непубличным** данным, иначе успешный анонимный GET не докажет применение токена).
- Fortis Repo получает этот JSON по **своему** API-запросу, но не может запросить другой проект, произвольный upstream URL, изменение Sonar, echo секретов или docker admin.
- Без токена / с отозванным токеном для защищённого запроса Gateway выдаёт явную ошибку; **не подменяет её анонимными публичными результатами** как якобы авторизованным успехом.
- Проверено, что токен не оказывается в клиентском HTTP, Docker image/repository, stdout/stderr и логах; при сетевом отключении/ошибке API результат честно `unknown/error`, а не «Green Gate».

**Обещание безопасности:** если AI управляет Docker daemon с Gateway, имеет возможность запускать привилегированный контейнер, подменять его образ или читать конфигурацию — секрет не изолирован. Сначала проверить реальную модель Fortis Repo и Gateway по месту развёртывания. Без такой проверки фраза «контейнер авторизован, AI доступа к токену нет» — **недоказанная гипотеза**.

## 5. Новый сквозной рабочий цикл (CODE FIRST)

1. **Владелец ставит задачу** по проекту. Fortis **либо** редактирует код внутри разрешённой рабочей среды Fortis Repo Docker, **либо** работает через GitHub connector. Это **два способа работы с Git**, а не две альтернативные системы полномочий. Для незащищённого кода — отдельные рабочие ветки; не push в `main`.
2. Fortis открывает PR в разрешённом GitHub repo. GitHub-hosted Actions запускают существующие build/tests и SonarScanner **с отдельным secret GitHub Actions**, а не с токеном Gateway. **Сканирование делает CI, а Gateway только читает результаты.**
3. Fortis получает точные GitHub job/check statuses и Sonar данные через Gateway. Для PR-анализа нужен результат именно для соответствующего PR, а не текущий `main` snapshot. Нужно различать PR HEAD, временный merge checkout GitHub Actions, `run_id/attempt` и конечный merge SHA. Если нужная проверка не запускалась из-за `paths`, не считать её зелёной.
4. Fortis исправляет PR, при необходимости проводит **одну** дополнительную итерацию. Сложные очереди, таймеры, автоматические восстановления и многократные retry **не требуются для MVP**. Если Sonar API недоступен или Gate ERROR — честно показать непрохождение/неопределённость.
5. **Владелец выполняет review и merge**. Позже можно разрешать другие действия через отдельный owner approval, но **не** автослияние по одному Sonar Gate. Sonar report не создаёт Guard approval.
6. **Доставка на Windows без shared mounts.** У Fortis Repo в Docker и у доверенного Windows **две разные копии одного GitHub репозитория**. После merge владелец/доверенный импортер выбирает проверенный финальный SHA; Windows выполняет `git fetch` с доверенного remote и получает именно его. Для *собственного доверенного инструментария* на первом этапе допускается управляемый `git pull --ff-only` после review, но нельзя выдавать это за строгий независимый admission. Для чужого/недоверенного кода требуется отдельный exact-SHA import и Guard. **Получение файлов и запуск — разные действия**; запуск на Windows только по отдельному подтверждению.
7. **Self-development:** та же схема используется для небольшого PR, исправляющего сам Fortis, без выдачи AI токенов или доступа к доверенному Windows.

Сценарий включает реальный перенос/запуск на Windows **как целевой конечный этап**, но первый тест Gateway/PR можно выполнить до него, без зависимости от домашнего Windows. Систему доставки проектируем с точными SHA, не строим заранее Windows Dispatcher.

## 6. Что удалять из репозиториев — только после нового smoke

| Где | Что оставить | Что потенциально удалить/остановить | Условие удаления |
|---|---|---|---|
| `gd-cap` | `.github/workflows/sonarqube.yml` с checkout/Java 21/build-java/SonarScan/CI; `sonar-project.properties`; scanner GitHub secret | `.github/scripts/write_sonar_run_metadata.py`, `.github/scripts/test_sonar_run_metadata.py`, `Prepare Sonar run metadata`, `Test Sonar run metadata writer`, `Write advisory Sonar run metadata`, `Upload advisory Sonar run metadata`, дополнительный `metadataFilePath` | После реального Gateway + PR/CI и решения отказаться от legacy artifact reader |
| `obs-planning-docs` | `.github/workflows/sonarqube.yml` с SonarScan/CI; `sonar-project.properties`; scanner GitHub secret; корректный path filter или пересмотр его охвата | Те же два metadata-скрипта, четыре отдельных legacy шага и дополнительный `metadataFilePath` | После проверки PR именно в реально сканируемой JS-области и зависимостей reader |
| `fortis-security-reports` | Старые immutable JSON/исторические подтверждения и код до решения владельца | Stage 7 helpers/Windows reporting как *необязательный* будущий функционал; отдельно `collect-sonar.yml` schedule, если перестанет быть нужен | Не удалять всё вместе. Сначала Gateway, затем owner-reviewed отключение расписания, сохранение архива, выбор архивации кода |

**Важно:** отключение `fortis-sonar-run-*` artifacts **ломает старый Windows evidence reader**; отключение `collect-sonar.yml` **останавливает** текущее OBS hourly пополнение архива. Это желаемые побочные эффекты только после осознанного решения владельца. Не удалять работающие SonarScanner workflow, Java build/test, GitHub secrets Scanner или sonar-project.properties как «следы старой отчётности».

## 7. Минимальный план без тысячи edge cases

| Шаг | Делаем | Доказательство готовности |
|---|---|---|
| **G0** | Определить место Gateway и границу Docker daemon (отдельно от AI); определить Sonar instance и разрешённые проекты | AI не имеет привилегированного доступа к Gateway, токен можно отозвать |
| **G1** | Поднять минимальный Gateway с токеном; фиксированные READ для Issues и Quality Gate. **Без монтирования и официального MCP** | Из Fortis Repo получен реальный Sonar JSON; секрет не виден; запрещённые методы и проекты получают отказ |
| **G2** | Проверить рабочую правку кода → GitHub PR → CI/Sonar → чтение результата Gateway → при необходимости одно исправление | Реальные ссылки на PR/CI, совпадение PR/checkout/analysis IDs; ни одной команды для Sonar в доверенном Windows |
| **G3** | Owner review/merge; получить финальный SHA в **отдельной** Windows Git-копии; отдельно запустить собственный доверенный инструмент | Владелец видит точный SHA, checks и результат запуска; no shared mounts |
| **G4** | Проделать такой же цикл для небольшой правки **самого Fortis** | Fortis помогает разрабатывать себя без доступа к секретам Gateway |
| Позже | При необходимости — одобряемые write-операции, независимый Guard/Windows importer, хранение артефактов, сокращение старых workflows | Отдельные PR и owner decisions, а не блокеры первого MVP |

**Намеренно не делаем сейчас:** Windows Receiver, event Dispatcher, запуск публичного webhook/tunnel, полную публикацию Sonar JSON в отдельный архив, retries, автоматическую доставку при выключенном Windows, отдельную БД, политический движок из сотни правил, новую облачную очередь. По мере необходимости можно использовать проверенные старые компоненты, но они больше не критический путь.

## 8. Честно не проверено на момент фиксации

- Нет созданного и протестированного Sonar Gateway, реального API-токена Gateway или демонстрации его прав на двух проектах.
- Не подтверждена сетевая достижимость Gateway из **конкретной среды Fortis Repo**. Docker network не обещает соединения между разными хостами.
- Не подтверждено, что AI лишён доступа к daemon/секретам при предполагаемом размещении Gateway; нужна реальная проверка окружения.
- Нет проведённого Fortis Core fix-loop на PR с конкретной Sonar analysis и последующим переносом этого же результата в Windows.
- Не подтверждён безопасный независимый Guard/Windows Commit Gate для нового автоматизированного контура. PR #32/#33 не являются механизмами исполнения.
- Настройки GitHub branch protection/required checks нужно проверить владельцу: чтение соответствующего GitHub API ранее возвращало `403`.

## 9. Источники и сохранённая история

**Внутренние GitHub источники:**

- [`gd-cap` Sonar workflow](https://github.com/AlexPastukhh/gd-cap/blob/main/.github/workflows/sonarqube.yml) и [`sonar-project.properties`](https://github.com/AlexPastukhh/gd-cap/blob/main/sonar-project.properties).
- [`obs-planning-docs` Sonar workflow](https://github.com/AlexPastukhh/obs-planning-docs/blob/main/.github/workflows/sonarqube.yml) и [`sonar-project.properties`](https://github.com/AlexPastukhh/obs-planning-docs/blob/main/sonar-project.properties).
- [`write_sonar_run_metadata.py` gd-cap](https://github.com/AlexPastukhh/gd-cap/blob/main/.github/scripts/write_sonar_run_metadata.py); аналогичный файл есть в OBS.
- [`manual-sonar-cycle-common.ps1`](https://github.com/AlexPastukhh/fortis-security-reports/blob/main/scripts/manual-sonar-cycle-common.ps1), [`sonar-run-evidence-common.ps1`](https://github.com/AlexPastukhh/fortis-security-reports/blob/main/scripts/sonar-run-evidence-common.ps1).
- [`collect-sonar.yml`](https://github.com/AlexPastukhh/fortis-security-reports/blob/main/.github/workflows/collect-sonar.yml), [`collect_public_run_receipts.py`](https://github.com/AlexPastukhh/fortis-security-reports/blob/main/scripts/collect_public_run_receipts.py), [`publish_cloud_reports.py`](https://github.com/AlexPastukhh/fortis-security-reports/blob/main/scripts/publish_cloud_reports.py).
- [Старый подробный reporting roadmap](https://github.com/AlexPastukhh/fortis-security-reports/blob/main/docs/fortis-reporting-roadmap.md) — **исторический план**, не новый порядок MVP.
- [Единый прежний end-to-end roadmap](https://github.com/AlexPastukhh/fortis-security-reports/blob/main/docs/fortis-end-to-end-roadmap.md) — концепция независимого Guard и Windows import; в нём есть устаревшие статусы и SHA.
- [Действительная Windows CLI авторизация](https://github.com/AlexPastukhh/fortis-security-reports/blob/main/docs/windows-private-reports.md) — уже авторизованный `sonar api get` для приватного `gd-cap`, отдельный `sonar auth status` и доступ GitHub из того же Windows account; [код GET-хелпера](https://github.com/AlexPastukhh/fortis-security-reports/blob/main/scripts/private-sonar-common.ps1).
- [Stage 6: Cloud-writer real race](https://github.com/AlexPastukhh/fortis-security-reports/actions/runs/40872501266) и [Stage 6: Windows-writer real race](https://github.com/AlexPastukhh/fortis-security-reports/actions/runs/40876094823).

**Официальные API источники:**

- [SonarQube Cloud Web API](https://docs.sonarsource.com/sonarqube-cloud/appendices/web-api) — `Authorization: Bearer …`, экземпляры EU/US.
- [Официальный SonarQube CLI](https://github.com/SonarSource/sonarqube-cli) — `sonar auth login`, `sonar auth status`, `sonar api get`, режим автоматизации `SONARQUBE_CLI_TOKEN` + `SONARQUBE_CLI_ORG`. Этот CLI не равен Sonar MCP Server или SonarScanner.
- [Personal Access Tokens в SonarQube Cloud](https://docs.sonarsource.com/sonarqube-cloud/managing-your-account/managing-tokens) — токен вместо пароля; права зависят от владельца, при неактивности токен может быть отозван сервисом.
- [Project permissions SonarQube Cloud](https://docs.sonarsource.com/sonarqube-cloud/managing-your-projects/administering-your-projects/setting-permissions) — Browse, Administer Issues, Administer Security Hotspots, Execute Analysis, Administer project — разные права.
- [GitHub Actions trigger and checkout](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) — PR head и фактически протестированный ref/merge commit необходимо различать.

### Решения, не путать с реализацией

**Решено:** code-first Fortis, собственный минимальный Gateway по Sonar REST, бесплатный SonarCloud без Sonar MCP Server, без общих монтирований, токен только у Gateway, автоматическое чтение, позже конкретные согласованные записи, финальное owner merge, отдельная Windows-копия и подтверждение запуска.

**Не решено:** точное размещение Gateway и защищённый сетевой канал; каким credential и от какой учётной записи его снабдить; какие Sonar действия write когда-либо разрешать; какой repo будет основным для самого Fortis Core/Gateway; схема будущего доверенного Windows импорта. Ничего из этого не нужно выдавать за существующую инфраструктуру.
