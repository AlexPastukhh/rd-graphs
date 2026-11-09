# CPW-RDG-MANUAL-WORKFLOW-20261019/v1

Дата среза: 2026-10-19. Статус: **Candidate; local controller/writer integration**.
**Stage 4 NOT ACCEPTED.** Основание: прямое поручение выполнить следующий крупный
пакет текущего плана — ручной Viewer/Helper и общую историю.

## Краткий результат

В исходнике Viewer 2.1.0 реализован подключаемый ручной раздел «План и история».
Создание/правка, канон и QRPE, глубокие предварительные R/Actions, явное размещение,
выбор, запись результата и отзыв идут через существующих Graph/Plan writers.
Общее будущее и история читаются из тех же owners. A1 → выполнение → отзыв → A2
сохраняет все факты; выбор по-прежнему отличается от выполнения.

Контроллер проверен с настоящими writers через два транспорта: выбранную папку
сессии и loopback. **DOM в тестах имитируется.** Это не фактический прогон
установленного браузера/G2, native picker или визуальное QA. На Windows ничего
не установлено, новая shared infrastructure не запущена. После тестов все
временные Helper-процессы/потоки завершены.

## Baseline и границы записи

Проект: `/workspace/repos/rd-graphs`, Fortis Repo. Фактическое RW-монтирование
проверено через `/proc/mounts`, доступ записи подтверждён. `.git` отсутствует;
`git status` вернул 128. Вместо Git diff сохранены selected before-копии и хеши.
Предыдущие 17 source hashes из rdg-instance-temporal-workflow-20261019 совпали
до начала этого пакета. Найденные README/проектные инструкции прочитаны; AGENTS
в проверенных затронутых каталогах отсутствовал.

Изменялись выбранные код/тесты/документы и эта handoff-папка. Пользовательские
графы специально не редактировались; испытания использовали временных синтетических
владельцев и grant stores. Owner HOST, clipboard, Windows GUI/процессы, ACL, mounts,
порты хоста и туннели не изменялись. Git commit/push и deployment не выполнялись.

## Реализация и важные решения

- `rdg-workflow-ui.js` — общий контроллер ручного раздела. Штатный builder встраивает
  его в Viewer без новых @require/grants. Без явной сессии предметные факты Viewer
  остаются read-only. Подключение папки требует пользовательского picker.
- `rdg-workflow-helper.py` — явно запускаемый локальный session adapter. Основной
  файловый путь работает на уже разрешённом mount и не требует нового сервера.
  Браузер пишет завершённый request + ready marker; Helper атомарно публикует
  response. Клиент удаляет только свои завершённые exchange-файлы. Descriptor
  содержит session capability, но не bearer/HMAC key. Закрытие помечает inactive.
- Необязательный loopback adapter имеет случайный порт и секретный session URL,
  точные Host/Origin/header guards, no-store, CSP, no-CORS, allowlist ресурсов.
  Docker-loopback не считается доступом из Windows; проброс/туннель не создаётся.
- Snapshot для editor получается под прежними read locks/правами: Plan + Graph
  источники и расчёт завершённости. По умолчанию старый API/CLI не возвращает
  source payload. Выборочные refs/kind/identity сохраняют проверку.
- Graph/Plan mutations используют прежние permissions, CAS, snapshot/history,
  catalog, durable prepared journal, recovery и read-back. Helper не выдаёт grants,
  не изменяет политики и не создаёт Graph/Plan owners.
- Обычный bearer не получает by:user по полю события. Явная local manual session
  использует process-local ключ и существующий exact-package MAC verifier с TTL,
  purpose и тем же bearer principal; receipt local-manual-session. Это происхождение
  локального запроса, **не доказанная личность человека**. HMAC не доступен UI.
  Protected R через этот Helper не редактируются, даже с таким MAC.
- Сохранённый ответ не подменяется успехом оптимистической перерисовки. При потере
  ответа держится тот же request/transaction; новый action не запускается до
  разрешения исхода. Cache replay проверяет актуальные права и не пишет повторно.
  При restart cache утрачен: сначала фактический read-back, без слепого нового ID.
- Ошибка после частичной Plan publication не называется отказом без эффекта.
  Наличие pending journal означает unconfirmed outcome до recovery. После recovery
  тот же запрос идемпотентен. Ошибка render после сохранения отделена от writer outcome.

## Проверка и evidence

Широкая регрессия: **239 Python tests (23 набора) и Node run из 414 cases:
413 PASS, 0 FAIL, 1 SKIP**. Источники: regressions.json, runner.log, node-all.log
и отдельные *.test.py.log. Один Node case требует реального Helper; в общем Node
run без endpoint он пропущен. Он отдельно выполняется внутри Python acceptance
через оба транспорта, а не объявляется выполненным по skip.

После дополнительной проверки Plan error/partial publication отдельно заново
прошли **13 helper tests**: helper-final3.log. В общем регрессионном срезе helper
имел 12 тестов; полный широкий run после последнего изменения не повторялся.
Текущие изменённые Helper-пути проверены адресным финальным набором. Наборы
пересекаются; числа не суммируются как уникальные проверки.

Внутри helper acceptance выполнены 7 Node UI cases с настоящим endpoint через
loopback и через файловые request/response, в том числе кнопки построения глубокой
непринятой ветви. Логи: gui-controller.log и gui-file-controller.log.
После уточнения проверки disabled controls отдельно прошёл node-ui-final.log:
6 PASS, 0 FAIL, 1 expected endpoint-dependent SKIP; runtime UI не менялся.

Проверены существенные направления:

| Направление | Фактическое evidence / граница |
|---|---|
| Целый путь с теми же ID | Контроллер создаёт A1/A2, размещает их и R0, выбирает/выполняет A1, отзывает A1 и выполняет A2; future пустеет, все факты в истории; оба транспорта. |
| Глубокое планирование | Через кнопки построены candidate decomposition → potential R → candidate Action, канон/QRPE; предки не выбираются. API отдельно проверяет method_correctness и order-only R. |
| Отказ и concurrent edit | stale Graph/Plan CAS, отдельные read/write grants, revoke и cached retry; источники при отказе не переписаны. Старые owner concurrency-наборы прошли общую регрессию. |
| Retry и uncertainty | Потеря ответа держит тот же request; новый action заблокирован; cached подтверждение не пишет вновь. Изменённый body с тем же tx отклонён. |
| Recovery | Prepared Graph journal блокирует read; старый recovery завершает его. Сбой после первого Plan write не выдаёт success; recovery + exact retry не создаёт новую версию. |
| Права и локальная сессия | Обычный bearer/user spoof, HMAC без opt-in, поддельная подпись при opt-in, неверные session/Host/Origin/content type и filesystem symlink отклонены. Protected Graph write недоступен. |
| Безопасное представление | Source text через textContent; ошибки не дают оптимистический результат. Bearer и process key отсутствуют в snapshot/page; обычный read не меняет источники. |
| Existing API/Viewer | Общая регрессия прошла; tools/rd-graph-viewer-smoke.test.cjs подтвердил версию 2.1.0, launcher и JSON rendering. Viewer builder idempotent; generated UI равен общему исходнику. |
| Native browser / Windows | Не проверено: настоящий picker, визуальное QA нового раздела, Tampermonkey installation/cache, G2 доступ к той же папке. Контроллерный proof их не заменяет. |

Первичный helper-initial.log сохранён: полный HTTP путь уже прошёл, но обнаружены
два UI/test замечания — описание сохранённого результата после render failure и
начальное hidden-состояние fake DOM. Исправлены; helper-second/final прошли.
Последующий Plan fault regression сохранён в final2/final3, без стирания прежних логов.

## Ограничения и следующий шаг

Первый editor — один owning graph + существующий Plan того же identitySpace,
только R/Action steps без старых event/gate/Plan branches. Предварительные ветви
самого графа разрешены. Advanced Canon metadata не обрезается: GUI-изменение
отказывается, полный API остаётся доступен. Нет GUI для admin/policy/расширенной
Canon governance или подтверждённой human identity. Protected Graph write целиком
отказывается этим Helper. Скрытие/приоритет истории второстепенны и не реализованы.

Два независимых продолжения: установленный browser/G2 proof при подтверждённом
доступе к выбранной папке; межфайловой resolver owning/projectionOf с отказом при
missing/ambiguous/denied owner, cycles и без двойного учёта. Полный Gendocen Canon
workflow остаётся отдельным scope; его claims не расширялись этим пакетом.

Запуск и операции: docs/guides/RDG-DEEP-ACTION-AND-HISTORY.md, раздел
«Локальная ручная сессия Viewer/Helper 2.1.0». Актуальный порядок:
docs/guides/RDG-CURRENT-EXECUTION-PLAN.md. Исторические handoffs/reviews не менялись.

## Воспроизводимость

BASELINE.json + before/ — выбранные исходники до работы; SOURCE-HASHES.json —
точные финальные исходники; SELECTED-DIFF.patch + DIFF-STAT.json — selected changes.
SCOPE.md — scope пакета и обоснование файлового транспорта. Checkpoint не является
acceptance Stage 4, Git publication или установкой на Windows.
