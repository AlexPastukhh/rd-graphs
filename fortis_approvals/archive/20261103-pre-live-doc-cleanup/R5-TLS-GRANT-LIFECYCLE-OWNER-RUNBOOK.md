# R5: управление TLS identity и machine grant — подготовка для владельца

Статус: **SOURCE-ONLY / OFFLINE TEST PASS (2026-11-01)**. Это план проверки, **не разрешение** запускать контейнер с настоящим SonarCloud-токеном. Ниже нет команды, автоматически изменяющей действующие A3, G2, G4, RDG или Fortis Repo. Владелец сам утверждает trust, идентичность и порядок установки.

## Фактическая модель текущего R5

- R5 candidate: `fortis_approvals.r5_read_server`, Docker review tag `fortis-r5-sonar-read-candidate:review-20261101-e6aec453`, owner-reported image ID `sha256:5fa986d7e532639c5461a87e4a2c34ea8176ec58371f418758d0cd5dfc38bd02`. `preflight-imports` и fake Sonar READ source/lifecycle smoke PASS; **реальный R5-сервис не установлен**.
- R5 использует четыре **новых** тома: `fortis-r5-state` (изолированная `/state/private` с маркером `.fortis-r5-sonar-read-v1`), `fortis-r5-identity`, `fortis-r5-grant`, `fortis-r5-sonar-token`. Никакого A3/G2/G4 state/volume, key, grant или токена в R5 автоматически не переносить. Нельзя повторять A3 bootstrap на его существующих томах.
- Machine: `https://host.docker.internal:19104` (TLS 1.3, certificate SAN `host.docker.internal`, отдельный grant в приватном файле). Owner UI: `http://localhost:19103` (отдельный localhost-only WebAuthn origin). `Core.adapters={}`, Sonar operations только READ, `accept_issue`/Sonar POST не предусмотрены.
- **Текущее ограничение R5:** TLS `SSLContext` и `Authenticator` создаются при старте и остаются в памяти. Изменение файлов grant или TLS на Docker volume **не меняет активные ключи в уже запущенном процессе**. Для фактического отзыва или перехода на новый сертификат необходимо управляемо остановить **именно R5**, затем запустить его заново. В R5 ещё нет проверенной live hot-rotation и отдельного owner-API для отзыва.
- WebAuthn credentials и `Core` SQLite сохраняются в томе `fortis-r5-state` при перезапуске **того же R5 с тем же origin**. Browser sessions и незаконченные challenges хранятся в памяти: после перезапуска требовать новый WebAuthn login. Изменять `localhost:19103`/RP origin после enrollment нельзя без отдельного миграционного решения.
- **Не путать отдельный R5 pilot с конечной архитектурой «один Fortis»:** запущенный A3 использует `localhost:19093` и собственные WebAuthn/state, R5 пока создан как **отдельный** source/image candidate, причём в нём не зарегистрирован synthetic A3 executor. Чтобы считать его единственным production Fortis, нужны самостоятельная миграция/переход owner identity и согласование функций; простая замена имени/томов это не обеспечивает.

## Обязательные условия до действий владельца (все OPEN)

1. Проверенный source package, exact image SHA, независимый review immutable base digest, Python dependencies и уязвимостей; образ проверен на bytes/versions/pip-check, но **это ещё не supply-chain admission**.
2. Владелец утверждает свежую TLS identity: доверенная цепочка/anchor и канал доставки **только публичного** сертификата в клиент Fortis Repo. Имя `host.docker.internal` должно совпадать с SAN и реальным TLS endpoint. Проверка имени и цепочки TLS обязательна — не `verify=False`, не глобальное отключение проверки. Приватный ключ **никогда** не передавать через Repo/ИИ/Git/чат.
3. Владелец создаёт и проверяет scoped machine grant **локально на доверенном Windows/Docker-host**. Random secret, отдельный от Sonar API token, хранится без попадания в argv/env/логи/чаты. Точное содержимое grant/токена **не печатать и не хешировать для передачи**. Права файлов и изолированных private каталогов должны соответствовать runtime UID `10001`: private regular files 0600, state 0700; запрет symlink; отдельное управление резервными копиями.
4. Trusted host должен поддерживать изолированный монтаж `fortis-r5-state`, `-identity`, `-grant`, `-sonar-token` без Docker socket или A3/G2/G4 private mounts в `fortis-repo-test`. Docker `restart:no`, `cap_drop:ALL`, `no-new-privileges`, read-only root, localhost-only опубликованные порты.
5. Отдельно согласовать, какой контейнер будет единым Fortis, сохранятся ли A3 WebAuthn/ASK и как переключается клиент. R5 READ pilot **не выполняет** эту миграцию. Не выключать A3 при отсутствии альтернативного рабочего доступа и принятого cutover.
6. **Срок TLS текущего A3:** owner-reported expiry `2026-11-07T23:29:17Z`. Это **отдельная** существующая установка и отдельная приоритетная задача; процедура R5 ниже сама по себе не обновляет A3 и не продлевает его сертификат.

## Точный lifecycle для R5 (только после отдельного owner GO)

**A. До первоначального запуска R5**

- Независимо проверить image+base, сети и volume/mount boundaries, ключи и SAN; убедиться, что R5 owner/browser port и machine TLS port не заняты.
- Подготовить **новые пустые** R5 volumes и private paths строго через owner-reviewed bootstrap; не подключать старые A3 volumes. Проверить файловую структуру/UID/mode без вывода секретных bytes.
- Доверенно установить *публичный* cert pin/CA у клиента, не вносить приватный ключ в Repo. Выполнить TLS positive/negative handshake без bearer/token, затем scoped machine negative auth checks.
- Только отдельным действием owner вводит отдельный Sonar read token в private host storage. Реальный upstream Sonar GET — **ещё один** разрешаемый gate, не автоматическое следствие bootstrap.

**B. Ручная замена TLS identity R5 (без изменения Core/WebAuthn state)**

1. Из работающего R5 и доверенного клиента зафиксировать **публичные** данные: текущие image ID, cert fingerprint, SAN, expiry, hostname verification, доступность owner UI; убедиться, что `/state/private` на ожидаемом R5 volume. Никогда не запрашивать/логировать private key.
2. Owner локально готовит новый сертификат и ключ и проверяет корректность пары, срок действия, SAN, issuer/anchor, требования TLS и доступность trusted pin для клиента. **Пока R5 работает, не заменять файлы под его активным SSLContext.**
3. Согласовать окно R5-only downtime и канал восстановления, проверить сохранную **защищённую** backup state. Остановить **только R5**. Существующий `fortis-repo-test`, A3/G2/G4, Repo1/Repo2 scripts не останавливать.
4. Пока R5 остановлен, заменить только `server.crt` и `server.key` в **собственном** R5 identity volume с правильными UID/mode и синхронизацией файлов. Нельзя удалять или пересоздавать R5 state.
5. Запустить ровно утверждённый image+config с теми же state, grant, Sonar-token volumes и тем же owner origin. Проверить новый cert fingerprint/SAN/TLS1.3 и новый **публичный** client trust. Отрицательный тест старого pin (если он отозван), неверного hostname, отсутствующего machine grant; owner WebAuthn login после restart.
6. Если новая identity недопустима — **R5 остаётся остановленным**, пока владелец не согласовал отдельный безопасный rollback cert/anchor. Не отключать TLS verification ради успешного запуска и не возвращать отозванный machine grant.

**C. Выдача/замена/отзыв machine grant R5**

1. Подтвердить owner identity и точную *READ-only* область разрешений: только `list_projects`, `list_issues`, `get_issue`, `get_quality_gate`; отсутствуют Core execute и Sonar mutations. Убедиться, что исходный токен Sonar хранится **в другом** томе и не равен machine grant.
2. Owner локально генерирует новую непредсказуемую credential, не отражая bytes в консоли и истории PowerShell. Подготовить формат/права нового private grant file `/run/r5-grant/grant` (regular 0600 UID10001, без symlink).
3. Зафиксировать идентичность R5 image и owner state, согласовать R5-only окно. **Остановить R5 до замены**. Переключить только machine grant внутри R5 grant volume; существующий R5 state/WebAuthn и Sonar token не трогать.
4. Запустить тот же R5 image/config. Проверить **старый grant -> 401 DENIED**, **новый grant -> scoped READ 200** (на fake/безопасном fixture или предварительно разрешённом real GET), пустой grant -> 401, Sonar WRITE/action -> DENIED, чужой проект -> DENIED. Проверить отсутствие изменений Core state и отсутствие grant/sonar токена в ответе/логах. Требовать успешной проверки отрицательного старого grant, а не только положительного нового.
5. При неудаче R5 оставить остановленным и разбирать ситуацию локально; **не включать скомпрометированный старый grant как «быстрый rollback»**. Потерянный machine grant означает отсутствие доступа до новой выдачи, а не разрешение обойти TLS/auth.
6. Невозможно считать отозванный grant мгновенно запрещённым только потому, что owner заменил файл. **Окончательный revoke PASS только после фактического перезапуска и negative readback.** В этой source версии нет TTL/online revoke; отдельный scheduled expiry или hot-swap не утверждать.

**D. Приёмочные доказательства (без секретов)**

- exact image digest+source SHA и независимая trust review, публичная SAN/expiry/fingerprint; hostname-checked TLS1.3, negative wrong-hostname/untrusted-old pin.
- `old-grant DENIED / new-grant READ-scoped PASS / missing-grant DENIED / action+POST denied`; **никаких raw токенов или приватных путей в выводе**.
- R5 owner WebAuthn credential authentication после перезапуска и новая browser session, старые sessions/challenges недействительны.
- Наличие прежних R5 SQLite/state marker и корректных UID/mode; отсутствие mounts Docker socket/A3/G2/G4 state; работающий `fortis-repo-test` сохранён.
- Проверки source/import/image/package из R1–R5 не отменяют независимого admission. Owner принимает итог отдельно; until then **R5 TRUSTED ADMISSION=OPEN, Sonar WRITE=DISABLED**.

## Проверка сейчас (уже PASS только offline source)

`tests/test_r5_lifecycle_offline.py`: реальный TLS1.3 localhost для *двух последовательных* тестовых процессов, синтетический Sonar transport, FIDO2 virtual authenticator. Покрывает старый grant 200 до замены / 401 после, новый grant 401 до / 200 после, старый cert pin rejected, новый cert accepted, persistent owner/core SQLite и WebAuthn credential login после restart, завершение прежней browser session, fail-closed для неверных прав grant и повреждённого private key. **Без реальных Sonar requests, Windows/Docker/production private volumes, live credential или перезапуска A3.** Следующий owner шаг возможен лишь после подготовки reviewed оператора и отдельного GO; исполнять этот runbook на Windows сейчас не нужно.
