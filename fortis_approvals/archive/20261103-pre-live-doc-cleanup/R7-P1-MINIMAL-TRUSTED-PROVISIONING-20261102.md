# R7 P1 — minimal trusted provisioning runbook

**CURRENT STATUS (2026-11-03): GO-1 DONE; GO-2 DONE; GO-3 CUTOVER NOT EXECUTED / NOT AUTHORIZED; GO-4 NOT STARTED.** This runbook preserves the chronological provisioning and cutover evidence below. Historical design sections must not be read as current instructions.

- GO-1 trusted provisioning: **OWNER-REPORTED WINDOWS PASS**. Five R7 volumes and trust files, TLS identity, split server/client grants, private Sonar token custody and client-only trust material are reported provisioned. Do not rerun the old provisioner or recreate volumes.
- GO-2 P1 R7 deployment/enrollment: **OWNER-REPORTED WINDOWS PASS** for the P1 image `sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024f2c062bac0a18ce4`; R7 health and owner WebAuthn login are reported working. This is P1 runtime evidence, not P2 deployment.
- GO-3: revision-04 scripts and read-only pre-cutover checks are PASS, but the controlled Repo recreate and `/run/fortis-client:ro` mount were **NOT EXECUTED and NOT AUTHORIZED**. The existing Repo remains the rollback/current container.
- P2: immutable package, owner-reported Windows image build, installed-source/import audit are PASS for image `sha256:e751f6ca0cfe6ce290cf580de2f243071ee1f3e681baa8827c6cea41a16fa402`; P2 is not deployed.
- GO-4/live R7 → Sonar E2E: **OPEN / NOT STARTED**. The full pinned WebAuthn/HTTPS suite is still blocked in the Linux Repo environment.

Дата среза: 2026-11-03. Нормативный план: [Fortis secure development](../../docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md). Acceptance: [66 + P1 matrix](FORTIS-UNIVERSAL-GATEWAY-ACCEPTANCE-MATRIX-20261101.md).

## 1. Назначение и точная граница P1

Первый пилот: **один AI actor, один Repo client, один Fortis R7 Core, один GitHub/SonarCloud project**:
- GitHub repository: `AlexPastukhh/obs-planning-docs`, branch `main`;
- workflow: `.github/workflows/sonarqube.yml` (workflow_dispatch уже присутствует);
- Sonar organization: `alexpastukhh`;
- exact project key: `AlexPastukhh_obs-planning-docs`;
- region: `eu`;
- current scoped image tag: `fortis-r7-unified-read-ask-candidate:review-p1-scoped-20261102-fac3131e`;
- current owner-reported image ID: `sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024f2c062bac0a18ce4`.

Этот runbook готовит только доверенную границу для live READ + ASK/Reject. Он **не** реализует AI-triggered GitHub workflow-dispatch (P1-02), не запускает Sonar analysis и не разрешает Sonar WRITE. Для первого READ можно отдельно согласовать owner manual workflow run как baseline; это не закрывает AI-triggered dispatch acceptance.

## 2. Уже принятое evidence — не повторять

- Scoped Windows image-only build и exact-ID offline audit — OWNER-REPORTED PASS для указанного image ID; повторять build/audit без нового source/image digest не нужно.
- Corrected Windows read-only runtime preflight — OWNER-REPORTED PASS: image pin, Repo/A3 health, mount isolation, четыре существующих volume metadata/no attachments, Docker и Windows TCP ports 19103/19104.
- Repo1 и Repo2 read-only Guard Preview — OWNER-REPORTED PASS; Repo2 `ConfigState=Pinned`, container ID и direct module fingerprint verified.
- Pinned Compose `compose-r7-p1-scoped.yaml` SHA256 `115e283aaee3a6771f0a879008f4048c03150a7422f6b03757fb5105f6c4a5be`; Workfiles transfer copy byte-exact. Owner-provided Windows transcript confirms Repo container running, `docker cp` successful, SHA256 PASS, exact local image tag→ID PASS (`sha256:23667619…a18ce4`), and `docker compose --project-name fortis-r7-p1 -f <file> config --quiet` exit 0 / PASS. Config-only validation; no `up`, no container/volume/network creation. Evidence is owner-reported transcript, not independently executed in Linux Repo.
- Четыре ранее подготовленных volumes существуют; их contents не читались, они не прикреплены к контейнерам. **Не создавать, не удалять, не переименовывать и не очищать их.** Не запускать `Prepare-R7-Candidate.ps1`.
## 3. Выявленные implementation constraints

1. Старый `compose-r7-unified-read-ask.yaml` указывает `:local` и `build:`; это **не** тот exact-ID image, который прошёл scoped offline audit. Для будущего запуска подготовлен отдельный [pinned P1 Compose](compose-r7-p1-scoped.yaml): exact scoped tag, `pull_policy: never`, без build. До/после старта владелец должен сверить container `.Image` с полным ожидаемым image ID.
2. R7 server работает как UID/GID `10001:10001`; server-side private files проверяются как owner UID 10001 и mode 0600. Fortis Repo client работает как UID 1000; `repo_sonar_tools._grant_from_file()` требует owner текущего UID и mode 0600. Один и тот же grant-файл не удовлетворит обе проверки.
3. Repo client ожидает только `/run/fortis-client/grant` и публичный trust cert `/run/fortis-client/server.crt`. Нельзя монтировать в Repo весь `fortis-r7-identity`: там лежит `server.key`. Для Repo нужен отдельный client-only volume с grant-copy UID 1000 и **только публичным CA certificate**.
4. Добавление mount в уже работающий `fortis-repo-test` требует пересоздания контейнера с теми же существующими настройками. Docker не умеет безопасно прикрепить новый volume к уже созданному контейнеру. Это отдельное изменение действующего Windows container и требует **отдельного explicit owner GO**; Repo сейчас не трогать.
5. `OwnerWebAuthn.issue_invitation()` — operator-local действие, HTTP/AI route для него нет. Invitation выдавать только **после** первого старта R7: до старта создание `owner.sqlite` заполнит `/state/private`, и строгий `_fresh_r7_state()` не примет неинициализированный каталог как fresh state.
6. Уже выполненный corrected Windows preflight whitelist-ит только четыре server volumes и fail-closed отвергает любой дополнительный `fortis-r7-*` volume. После будущего GO-1 создания `fortis-r7-client` **не запускать старый preflight повторно**; нужен отдельный post-provision metadata verifier, который ожидает ровно пять имён и проверяет только безопасные file metadata.
7. Известная косметическая ошибка текущего scoped image: shared `OwnerPortal` при `read_only_banner=True` жёстко показывает заголовок `G4 READ ONLY`; R7 также включает этот флаг. Это не меняет auth/ASK/Reject policy, но заголовок R7 будет неверно называть G4. Не патчить image/volume на Windows; исправление потребует source change, новых tests и нового image digest/build/audit. До owner enrollment владелец должен знать об этой метке.

## 4. Volume и file map

| Volume | Состояние / содержимое после будущего GO | Кто читает |
|---|---|---|
| `fortis-r7-state` | Уже существует; `/state/private` уже подготовлен. R7 создаёт marker/SQLite state при первом старте. | Только R7, RW |
| `fortis-r7-identity` | Уже существует; будущие `server.key` (UID 10001, 0600) + `server.crt` (server leaf + CA chain). | Только R7, RO |
| `fortis-r7-grant` | Уже существует; будущий server grant file `grant` (UID 10001, 0600). | Только R7, RO |
| `fortis-r7-sonar-token` | Уже существует; будущий Sonar token file `token` (UID 10001, 0600). | Только R7, RO |
| `fortis-r7-client` | **НОВЫЙ, пока не создан.** Только client grant-copy (UID 1000, 0600) + public CA cert (UID 1000, 0644). Создавать лишь после отдельного GO. | Fortis Repo, RO |

## 5. Минимальный trust material — только после отдельного owner GO

### 5.1 TLS1.3 server identity

- Сгенерировать отдельный R7-only private CA и server leaf certificate с SAN `DNS:host.docker.internal`, EKU `serverAuth`, ограниченным сроком действия (предлагаемый максимум — 90 дней).
- CA private key держать только в памяти одноразового offline bootstrap-процесса; **не сохранять** его в volume, image, Repo, Workfiles или Git.
- В `fortis-r7-identity` сохранить `server.key` (UID 10001, GID 10001, mode 0600) и `server.crt` (server leaf + CA chain, public, mode 0644). Это соответствует `r7_unified_server.create_servers()` и TLS minimum 1.3.
- В `fortis-r7-client` сохранить только CA public certificate под именем `server.crt` (UID 1000, mode 0644). Client trust path и hostname должны остаться фиксированными: `host.docker.internal:19104`.
- Не использовать A3/R5/G2/G4 certificate/key. Не выводить PEM или private key в terminal/log/chat.

### 5.2 Один machine grant

- Сгенерировать криптографически случайный URL-safe grant (не менее 32 символов); не брать grant из A3/R5/G2/G4.
- Server copy: `fortis-r7-grant/grant`, UID 10001, mode 0600. Client copy: тот же byte value в `fortis-r7-client/grant`, UID 1000, mode 0600.
- Это credential вызова **Fortis**, не Sonar token. R7 сопоставляет его одному actor `repo-sonar-read-proposal-actor`; policy даёт четыре READ = ALLOW и `accept_issue` = ASK. Ни owner decision, ни Sonar token клиенту не выдаются.

### 5.3 Sonar API token (owner-approved; broad account token accepted)

- Владелец создаёт отдельный новый token для R7; **не копировать и не переиспользовать** токен G4 или иные действующие credentials.
- Использовать новый owner-created SonarCloud API token, который владелец считает достаточным для целевых типизированных операций. **Актуальная owner architecture допускает broad account PAT; Browse-only SOT или отдельный low-privilege account не являются обязательным gate.** Не переиспользовать существующий G4 token/volume: для R7 создать отдельный credential, но он может быть выдан тем же owner account и иметь широкие права этого аккаунта. Текущий GO-1 provisioner не проверяет token type, expiry или upstream privileges; это owner assertion. Существующие G4 live tests подтверждают GET → Fortis ASK Pending → WebAuthn Reject → History/readback, но не доказывают реальный Sonar POST/Administer Issues. До любого будущего WRITE остаются отдельные implementation/security/owner authorization gates; сам token не обходит Fortis policy внутри доверенного пути, но его утечка вне Fortis обходит ASK и несёт весь blast radius issuing account. Не присылать token в чат/Repo; вводить только скрытым локальным prompt. Архитектурное решение и остаточные риски: [G4 privileged-token ADR](G4-WRITE-PRIVILEGED-TOKEN-ADR.md), [G4 security review](G4-WRITE-SECURITY-REVIEW.md).
- Вводить только локальным скрытым prompt на Windows; скрипт преобразует SecureString в ASCII byte array и передаёт его напрямую в Docker process stdin. Токен не попадает в command-line args, environment, Compose `.env`, файл, Git, Workfiles или ChatGPT. BSTR и byte arrays очищаются best-effort; Windows/Docker host memory/crash dump остаются в доверенной границе.
- Широкий owner-created account token уже принят действующим owner ADR; отдельная Browse-only проверка или повторный scope-ack не требуются. Единственное интерактивное подтверждение provisioning — `PROVISION-R7-P1`; затем токен вводится скрытым локальным prompt. Provisioner не делает Sonar HTTP request и не проверяет upstream permissions offline.
- Server copy: `fortis-r7-sonar-token/token`, UID 10001, mode 0600. Ни client volume, ни Repo, ни AI не получают Sonar token. R7 держит его в памяти только во время работы и использует фиксированный EU Sonar GET transport.

## 6. Owner-only execution sequence — design, не команды для запуска сейчас

1. **Pre-provision review (read-only):** на Windows выполнить только `docker compose --project-name fortis-r7-p1 -f compose-r7-p1-scoped.yaml config --quiet` и сверить local scoped image tag→full ID; затем подтвердить четыре существующих volume metadata, отсутствие R7 containers и current Repo/A3 health. Compose config validation не запускает/не создаёт контейнеры и сети. Owner-provided Windows transcript reports transfer SHA256 PASS, exact scoped image ID PASS, and `docker compose ... config --quiet` PASS (exit 0); this closes the Compose parser/config syntax check only. It is not deployment evidence. Не читать volume contents; не выполнять повторную подготовку volumes. В Linux Repo container Docker CLI/YAML parser отсутствует, поэтому Windows validation remains owner-reported.
2. **Secret bootstrap (GO-1 script prepared, execution still requires explicit owner action):** использовать `Provision-R7-P1-Trusted-20261102.ps1` с exact image ID. Сначала read-only preflight helper (UID 10001, no capabilities, четыре server volumes RO + state RO); затем после одного typed provisioning GO и hidden Sonar token prompt создать только `fortis-r7-client` с unique per-run Docker volume label. Повторно проверить state/server-volume layout. Provision helper работает `--network none`, `--read-only` rootfs, без host bind/socket, UID 0 только с `CHOWN` + `FOWNER`; state volume не монтируется в provision helper. Он создаёт ephemeral CA key in process memory, server leaf/key, один random machine grant с server/client copies и Sonar token. Любой existing target/temporary file → STOP, никаких overwrite/repair/retry/automatic cleanup. На failure volume/files remain for owner review.
3. **Metadata and trust verification:** отдельный verify helper использует `--network none`, read-only rootfs и identity/grant/sonar-token/client volumes mounted RO (state volume не монтируется); `DAC_OVERRIDE` разрешён только для read-only чтения файлов разных UID. Внутри helper читает bytes, сравнивает server/client grant, проверяет key↔leaf pair, CA chain/signatures, SAN, EKU, validity/expiry и exact file set/owner/mode/size. В Windows terminal выдаются только metadata, public leaf SHA256 fingerprint, SAN/expiry и PASS markers — никогда secret bytes. Проверить, что client volume содержит ровно grant-copy + public CA cert и не содержит Sonar token/private key. State volume не монтируется в provision/verify и не меняется.
4. **R7 start (отдельный owner GO):** использовать только [pinned Compose](compose-r7-p1-scoped.yaml) с project name `fortis-r7-p1`; build/pull запрещены. Перед стартом сверить local tag→полный image ID, после старта сверить container `.Image` с тем же ID, loopback-only ports и health. Никаких `down --volumes`, prune или автоматического restart. Healthcheck проверяет owner HTTP + TLS1.3 machine listener, **не** делает Sonar request.
5. **Owner WebAuthn (после успешного первого старта):** локально выдать одну короткоживущую одноразовую invitation через operator-only `OwnerWebAuthn.issue_invitation()`; вывести её только в Windows terminal и ввести непосредственно в `http://localhost:19103/`. Не присылать invitation, PIN, cookie или assertion в чат. Зарегистрировать owner passkey и выполнить login. Owner portal остаётся loopback-only.
6. **Repo client mount (отдельный GO на изменение действующего контейнера):** сначала сохранить точную исходную конфигурацию `fortis-repo-test` и доказать воспроизводимый rollback. Затем owner-controlled recreate того же Repo container с единственным новым mount `fortis-r7-client:/run/fortis-client:ro`; сохранить workspace/trusted mounts, UID 1000, network и текущие Guard pins без других изменений. Если точную исходную конфигурацию/rollback подтвердить нельзя — не пересоздавать Repo и остановить пилот. Не создавать второй Repo/Tunnel/MCP architecture.
## 7. Первый функциональный smoke после всех GO

- Из одного авторизованного AI-сеанса через существующий Fortis Repo process tool вызвать фиксированный `fortis_approvals.repo_sonar_tools` client; отдельная MCP registration/bridge не нужна.
- Готовый однокомандный сценарий Repo-side: `python -m fortis_approvals.sonar_review_scenario review --issue-key <ISSUE_KEY> --reason '<owner-review rationale>'`. Он фиксирует org `alexpastukhh` и project `AlexPastukhh_obs-planning-docs`, выполняет четыре bounded READ (`list_projects`, `list_issues`, `get_quality_gate`, `get_issue`), проверяет точный Issue, формирует подробный JSON report и создаёт ровно один `PENDING` ASK. `FORTIS_REQUEST_ID` печатается до proposal; при потерянном клиентском ответе повторять с тем же `--request-id` и тем же reason, не генерировать новую заявку.
- После owner WebAuthn Reject получить итог тем же клиентом: `python -m fortis_approvals.sonar_review_scenario status --request-id <REQUEST_ID>`. Ожидаем `REJECTED`. Owner portal имеет `blocked_approvals`: Approve недоступен; AI не имеет owner routes/decision authority.
- Proposal — POST **только к Fortis ingress**; R7 policy создаёт `PENDING`, а `NoWriteTransport` блокирует любой upstream Sonar method кроме GET. Независимый Sonar GET должен подтвердить, что remote Issue не изменился; критерий — upstream Sonar POST = 0. Не выводить Issue message/private preview целиком в журнал.

**Важно о закрытии Issue:** текущий R7 candidate намеренно не умеет реально Approve/close Issue. Этот этап проверяет «ИИ предложил → владелец отклонил → ничего не изменилось». Реальное закрытие через Approve/POST — отдельный P1-C: новая реализация/сборка, одна disposable Issue, точная transition и новый explicit owner GO. Не пытаться включить это в текущем образе.

**GitHub analysis trigger:** P1-02 bounded workflow-dispatch ещё не реализован. Owner manual workflow run может дать baseline Sonar data для первого READ smoke, но не считается AI-triggered acceptance. Workflow-dispatch ASK/frozen target будет отдельной следующей source/test задачей.

## 8. Границы и остаточные риски

- P1 single-client grant — не криптографическая identity конкретного AI process. Он идентифицирует один Fortis Repo client и maps на один server actor. Все процессы с тем же UID 1000 внутри общего `fortis-repo-test` потенциально могут прочитать этот grant и вызвать те же READ/ASK. Это допустимо только как **один-actor pilot** с отсутствием других недоверенных AI-сеансов в этом shared container; это не multi-agent isolation и не доказательство per-AI identity.
- Repo получает только ограниченный Fortis machine grant + публичный CA certificate. Repo **не** получает Sonar token, TLS private key, R7 state/SQLite, owner WebAuthn DB, Docker socket или server grant volume.
- Docker volume mode 0600/0700 защищает от обычного UID внутри Linux VM, но не от Windows/Docker administrator, daemon access, host compromise или backup extraction. Это не encrypted secret manager; owner accepts host-admin trust.
- Owner portal — HTTP localhost, host port 19103 опубликован только на loopback; внутри контейнера listener binds `0.0.0.0` на отдельной project-scoped Compose network. Не подключать к этой network недоверенные сервисы. Machine endpoint host port 19104 также loopback-only и использует TLS1.3 с проверкой SAN/CA. Не открывать порты в LAN/WAN.
- R7 grant/token rotation/revocation lifecycle, backup/restore и full certificate renewal automation не входят в P1. При подозрении на утечку — прекратить использование и отдельный owner incident/revoke plan; не заменять файлы на работающем сервисе.
## 9. Отдельные разрешения владельца — не объединять

| GO | Что разрешает | Что не разрешает |
|---|---|---|
| GO-1: trusted secret provisioning | Создать `fortis-r7-client`; однократно записать R7 TLS identity, server/client grant copies и новый owner-approved Sonar API token (broad account token accepted) в точные private volumes; metadata-only verification. | Не запускать R7, не менять Repo/A3/G2/G4, не делать Sonar request. |
| GO-2: R7 deployment + owner enrollment | Запустить только exact pinned R7 image через scoped Compose; проверить image ID/health; выдать локальную одноразовую invitation и зарегистрировать owner passkey. | Не пересоздавать Repo, не выполнять Sonar READ/ASK, не разрешать Sonar POST. |
| GO-3: Repo client mount/recreate | Owner-reviewed recreate существующего `fortis-repo-test` с единственным RO client volume mount и доказанным rollback. | Не менять Tunnel/Guards/A3, не создавать параллельный Repo/MCP bridge, не выдавать upstream token. |
| GO-4: live READ + ASK/Reject | Выполнить согласованный single-actor READ smoke и одну ASK/Reject с remote unchanged readback. | Не Approve/close Issue и не выполнять Sonar POST. |

До соответствующего GO **ничего из строк GO-1..GO-4 не выполнять**. Текущий пользовательский ответ «давай» разрешает подготовить этот runbook/config source, но не является согласием на запись секретов, создание volume, изменение действующего Repo container или deployment.

## 10. Безусловные STOP

STOP при любом image ID/tag mismatch; существующем target filename; неожиданном volume/container; changed metadata; invalid SAN/chain/expiry; неверном UID/mode; отказе владельца принять blast radius выбранного Sonar token; невозможности сохранить Repo rollback; любом требовании использовать G4/A3/R5 identity/state; необходимости открыть non-loopback port; health/HTTP/TLS failure; любом Sonar POST; либо попытке обойти owner Reject.

Не удалять и не чистить volumes; не запускать старый `compose-r7-unified-read-ask.yaml`, `Prepare-R7-Candidate.ps1` или исторический `Verify-R7-Candidate.ps1`; не трогать текущие Windows containers, Guards, Tunnel/MCP, Docker deployment и Sonar WRITE.

**Текущий итог:** дизайн подготовлен; pinned Compose source подготовлен; secrets/client volume не созданы; существующие четыре volumes не изменены; R7 не запущен; Repo не пересоздавался; TLS/grant/token не provisioned; Sonar network requests = 0; Sonar POST remains blocked; deployment remains NOT AUTHORIZED.


## 10. GO-1 script review handoff (2026-11-02; NOT EXECUTED)

- **Current source revision:** `Provision-R7-P1-Trusted-20261102.ps1`, SHA256 `0e41fc8ea14e9aabcc7aea8c0b3ea8f46b2f23be99f0423480c13b09d870cfea`; byte-exact Workfiles copy: `/workspace/repo/Workfiles/_fortis_windows_transfer_tmp/20261102-r7-p1-go1-owner-review-04/Provision-R7-P1-Trusted-20261102.ps1`. This revision follows the active owner ADR: a broad owner-created account token is accepted; Browse-only SOT/restricted PAT is optional, not a prerequisite. It also removes the redundant second token-scope acknowledgement; one `PROVISION-R7-P1` GO remains. Older owner-review-01/02/03 copies are superseded; do not run them.
- Offline evidence: `test_r7_p1_provisioning_script_static` 10/10 and `test_r7_p1_trusted_provisioning_static` 7/7 PASS; embedded Python compile PASS, offline PowerShell delimiters balance PASS, real cryptography 50.0.2 CA/leaf signing, SAN/EKU/chain verify and temp-directory end-to-end provision/verify PASS. Docs audit 594 links PASS. **No Windows PowerShell interpreter or Docker CLI in Fortis Repo**; owner has since reported exact SHA transfer PASS and Windows PowerShell 5.1 Parser.ParseFile PASS. Real Windows script runtime and Docker helper execution remain untested.
- The earlier Windows PowerShell 5.1 Parser.ParseFile PASS applied to owner-review-02 only. For owner-review-04, transfer byte identity is verified inside the Repo Workfiles mount; Windows-side `Get-FileHash` and `Parser.ParseFile` must be performed once for this new SHA. No Sonar Browse-only UI inspection or second token-scope acknowledgement is required by the active owner architecture. This review does not itself execute the script or create the fifth volume.
- The active owner ADR already accepts the broad account-token architecture, so no extra Browse-only check or second scope acknowledgement is required. The provisioner has one typed `PROVISION-R7-P1` owner GO followed by hidden local token input. The token is stored only in the R7 private server volume, never in Repo/AI/client volume. On any failure: stop, preserve artifacts, no rerun/cleanup/overwrite without forensic review; never publish stdout containing secret bytes.
- Image ID is still `sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024f2c062bac0a18ce4`; R7 deployment, Repo recreate, Sonar requests and Sonar POST all remain **NOT AUTHORIZED**.


## 11. Owner priority update 2026-11-02 — live E2E first, launcher maintenance AFTER

**Более позднее решение владельца; статусы source-only выше сохранены как исторический журнал, но не описывают текущее runtime-состояние.**

- **GO-1 DONE:** owner-reported trusted recovery PASS, пять volumes, шесть trust-файлов; проверены TLS SAN host.docker.internal, UID/mode и совпадение grants. Sonar token только в private R7 volume.
- **GO-2 DONE:** owner-reported exact image ID sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024f2c062bac0a18ce4, health healthy, 19103/19104 loopback-only, четыре server mounts + /tmp tmpfs; owner WebAuthn credential зарегистрирован, успешный login подтверждён скриншотом. Cosmetic G4 READ ONLY title принят.
- **GO-3A read-only inventory PASS:** текущий fortis-repo-test running, pinned container/image, три RW workspace volume mounts (root + Repos/Workfiles subpaths), UID 1000, RO rootfs, cap-drop/NNP, сети fortis-repo-egress и rdg_personal_agents, 4 GiB/2 CPUs/512 PIDs, restart unless-stopped. Repo НЕ пересоздан; client-only mount НЕ подключён.
- **Приоритет владельца:** сначала выполнить реальную single-actor цепочку AI→existing Repo→R7→четыре SonarCloud GET→bounded report→Fortis ASK/PENDING→WebAuthn Reject→REJECTED→независимый Sonar GET unchanged; Sonar POST=0. P1-02 GitHub workflow-dispatch и P1-C real Approve/WRITE отдельно, не блокируют первый READ/Reject E2E.
- **Отложенная задача ПОСЛЕ E2E:** обновить Guard/launcher совместимость Repo1/Repo2 точечно под один дополнительный RO mount fortis-r7-client:/run/fortis-client:ro и новый container ID, сохранить три исходных RW mounts/subpaths, image/UID/capabilities/network/resource/Guard checks, проверить rollback, согласовать owner cutover. Сейчас исходники Guard и Windows скрипты запускателей НЕ менять.
- **Непреодолённая техническая зависимость (STOP):** нужного client-only mount нет; Docker не добавляет mount в уже запущенный container. Recreate изменяет container ID и прекращает старые docker exec sessions; существующие Guards/launchers требуют старый container ID и ровно три mounts. Нельзя обходить Guards, временно копировать grant в Repo, заводить второй Repo/MCP или объявлять частичный R7 smoke полным E2E.
- **Решение о последовательности:** (1) только read-only исследовать безопасный путь к полному E2E без изменения launcher scripts; (2) если такой путь проверен, отдельный owner GO на runtime step; (3) full live E2E и independent readback; (4) ПОСЛЕ E2E — отдельный review/patch Guards/launchers. Если при сохранении trust boundary E2E-first невозможен, зафиксировать конфликт и запросить у владельца изменение порядка, а не молча обходить guards или менять runtime. GO-4 и Sonar POST из этой записи не разрешены.



## 12. Owner correction 2026-11-02 — Guards в tunnel/current, запускатели Script Center — адаптеры

**Это актуальное owner-решение, заменяющее ошибочное размещение Guards и порядок раздела 11.** Для завершения одного live E2E нужен RO mount client-only volume в том же fortis-repo-test, то есть controlled recreate. Совместимость его Guards и launchers надо подготовить ДО recreate и E2E.

**Подтверждённая цепочка:** Windows script-control-center/Repo1-Worker.ps1 и Repo2-Worker.ps1 вызывают Get-TunnelWindowsMirror.ps1. Resolver проверяет чистые синхронизированные Git clones, source-manifest SHA и SHA восьми PowerShell файлов, затем запускает tunnel/runtime/windows-repo/current/Repo1-Worker.ps1 или Repo2-Worker.ps1. Repo1 -> launchers/chatgpt-repo-mode/run-tunnel-quiet-logs.ps1; Repo2 -> launchers/FortisRDGLauncherV2/Start-Fortis.ps1 -> Common.ps1 -> launchers/FortisRepoPlus2/FortisRepo2-quiet-logs.ps1 -> Repo2DirectGuard.ps1. Исторические script-control-center/launchers не являются активными источниками этих Guards.

**Правильный GO-3B source-only scope:** минимальные изменения в tunnel/runtime/windows-repo/current/launchers: Repo1 quiet launcher, Repo2DirectGuard, Repo2 quiet launcher, Common.ps1. Сохранять transport и остальную реализацию Tunnel без изменений. Resolver в script-control-center/Get-TunnelWindowsMirror.ps1 и привязанные манифесты/хеши меняются ТОЛЬКО по необходимости для проверки нового tunnel/current release; без ослабления Git main/clean/sync/manifest/file hash проверок. Нужно установить новый pin для полного container ID только после owner-controlled Docker create; никогда не разрешать wildcard ID или отключение Guard.

**Точный Docker-контракт:** три прежних RW workspace volume mounts и subpath без изменений плюс ТОЛЬКО fortis-r7-client:/run/fortis-client:ro. Сохранить прежний pinned image, UID 1000, RO rootfs, cap-drop, NNP, tmpfs, limits, network, установленный Direct MCP hash, owner Windows identity, runtime SHA и no-duplicate-session checks. Никакого второго Repo, Tunnel, MCP или временной копии grant в workspace.

**Порядок:** (1) source-only GO-3B и offline/PowerShell syntax/tests; (2) новый tunnel manifest+8 hashes, согласованный Script Center resolver pin, проверка двух Git-clones в Windows; (3) owner-local Docker config snapshot, полный recreate/rollback plan, сохранение рабочего Repo2 процесса до cutover; (4) отдельный owner GO на контролируемое пересоздание одного Repo с одним новым RO mount и full-ID repin, проверка обновлённых Repo1/Repo2 Guard Preview и reconnect; (5) отдельный GO-4: настоящие четыре Sonar GET -> bounded report -> Fortis ASK/PENDING -> WebAuthn Reject/REJECTED -> независимый GET unchanged -> Sonar POST=0.

**Evidence nuance:** все 8 исходников доступного tunnel/current snapshot совпали с source-manifest.json SHA256 D47234936171E7E47B870533AB06452BFA13E0DAA30F90ABB1367C4B66EC91E0. В текущем Linux checkout runtime/windows-repo обозначен untracked; это не доказательство drift Windows Git clone. Owner ранее сообщил TUNNEL MIRROR PASS и Repo1/Repo2 Preview PASS; новая ревизия требует новых pins и Windows проверки, но не повторения неизменённых audits. Пока никакие tunnel/source/Windows scripts, Docker/Repo/Tunnel процессы не изменялись.


## 13. GO-3B revision 2026-11-02 — проверять Docker security POLICY, не постоянный container ID

**Это новейшее решение владельца; заменяет требование обязательного full-ID repin в разделе 12.** Постоянно закреплённый Docker container ID меняется при каждом легитимном recreate; он не является устойчивой границей безопасности. Не ослаблять security contract: Guard проверяет фактическое имя одного Repo, format Docker full ID, pinned Docker image digest, UID, read-only rootfs, capabilities, NNP, networks, resource limits, optional tmpfs, отсутствие Docker socket, direct MCP fingerprint и owner/tunnel/runtime pins. Внутри одной Guard-инвокации захваченный Docker full ID используется для последующих docker exec, что снижает риск подмены имени во время проверки, но **никакого изменения исходника на каждый container recreate не нужно**.

Mount allowlist: **строго** три прежних RW volume-backed workspace mounts/subpaths; четвёртый mount **необязателен**, но если есть, то только volume fortis-r7-client по точному target /run/fortis-client в RO, подтверждённый одновременно Docker HostConfig.Mounts и effective Mounts. Никаких других mounts, bind, Docker socket или server private volumes. Прежняя конфигурация 3 mounts сохраняет работоспособность; новая 4 mounts валидируется теми же Guards без изменения их source при пересоздании.

**SOURCE-ONLY результат:** подготовлен отдельно от активного tunnel/current review bundle по пути /workspace/repo/Repos/tunnel/runtime/windows-repo/candidates/go3b-r7-p1-policy-review-01; изменены только 4 из 8 копий PowerShell файлов (Repo1 launcher, Repo2 Direct Guard, Repo2 Common, Repo2 launcher SHA-pin). Старый current не изменён; исходные 8 SHA и source manifest совпадают. Политика прошла 24 негативных/позитивных synthetic PowerShell cases (PS7.6.9) и все 8 PS7 Parser.ParseFile; существующий tunnel test_release_contract.py 6/6 PASS на неизменённом current. Никакой Windows PS5.1/runtime Guard Preview не проводился; это **ещё не релиз**.

**Оставшиеся GO-3B release gates:** новый tracked/owner-reviewed tunnel source release и восьмифайловый manifest + новый SHA pin в script-control-center/Get-TunnelWindowsMirror.ps1, согласование provenance, Windows PS5.1 parser/SHA, два Guard Preview и доказанный rollback/reconnect. Resolver всё ещё исторически ожидает manifest со статусом byte-exact mirror of script-control-center:main; когда canonical Guards изменятся в tunnel, нельзя ложно сохранять старую provenance: проектировать обновление resolver/manifest вместе и не отключать Git clean/main/sync/hash проверки. **Никаких live Docker changes без отдельного owner GO; GO-4 Sonar live отдельно.**


## 14. GO-3B source implementation 2026-11-02 — canonical Guards updated, Docker unchanged

**Позднейший статус по владельческому запросу:** исправления четырёх Guard/launcher файлов теперь применены к **source tree** tunnel/runtime/windows-repo/current, а не только к candidate. Repo1 quiet launcher и Repo2 Direct Guard перестали hardcode Docker container ID, проверяют фактическое имя и 64-символьный full ID, после inspect используют тот же ID для docker exec в пределах инвокации. Repo2 quiet launcher проверяет имя/full-ID format и новый SHA256 Repo2 Guard; Common.ps1 допускает 3 или 4 mounts, но только три исходных RW workspace + опциональный exact fortis-r7-client:/run/fortis-client:ro. Все исходные проверки image/UID/RO rootfs/caps/NNP/network/resource/tmpfs/runtime/Direct MCP сохранены.

**Source-chain integrity:** tunnel/current/source-manifest.json теперь честно обозначает canonical tunnel:main source, содержит hashes всех 8 файлов и детерминированный sha256_file_inventory_v1 revision (не Git commit/container ID). Новый exact manifest SHA256: CADDA676CE273ADEC08DDF8FF7BDBAC355CF2D361F0AEE1308001FFAB97121AB. Точно этот hash привязан в tunnel/runtime/windows-repo/Invoke-FortisRepo.ps1 и script-control-center/Get-TunnelWindowsMirror.ps1; старые Script Center launchers/Guard copies не изменялись. Git clean/main/sync и SHA каждой из восьми исходных программ сохраняют свой контроль. Изменение security policy требует нового review/manifest pin; обычный Docker recreate с тем же policy — не требует.

**Offline verification:** 24/24 positive/negative synthetic mount policy cases (PowerShell 7.6.9); 7/7 source contract tests tunnel; 50/50 relevant script-control-center tests; PS7 Parser.ParseFile для 12 изменённых или связанных PowerShell файлов PASS. Это НЕ Windows PowerShell 5.1 Parser или live Docker Guard Preview.

**Стоп перед реальным GO-3 cutover:** Linux tunnel Git status показывает runtime/windows-repo untracked и другие чужие модификации. Никакого Git stage/commit/push, изменения живого Windows clone или Docker здесь нет. Нужен отдельный owner-reviewed Git commit/paired Windows clean main sync (без затрагивания других незакоммиченных файлов), Windows PS5.1 SHA/Parser, оба Guard Preview на старом 3-mount Repo, owner-local Docker snapshot/reproducible rollback и отдельный explicit owner GO на recreate того же Repo. Затем Repo1/Repo2 reconnect; только затем отдельный GO-4 live E2E. Sonar POST=0.


## 15. GO-3C shared Guard release accepted; next is GO-3 runtime cutover (2026-11-02)

**Owner-reported Windows completion:** the simplified shared Repo1/Repo2 Guard policy is published in AlexPastukhh/tunnel:main; current nine-file manifest SHA256 is 8036348F69BB37F94F5E6FDE529BF44A292F4EB91977CE91A491E9860AADBFCA. Windows paired-source/static preflight, PowerShell/WinForms compile, Repo1 Guard Preview, Repo2 Guard Preview and Script Catalog shortcut switch are reported PASS. Owner subsequently reports that both Repo1 and Repo2 reconnected and are working. This closes the source/Windows Guard release gate; it does not imply the Fortis Repo Docker container was recreated or that the R7 client mount is attached.

**Exact next runtime step:** controlled recreate of only the existing fortis-repo-test container to add fortis-r7-client at /run/fortis-client read-only. Do not restart/recreate the R7 server; it remains the separate healthy container. Preserve the three original RW fortis-repo-workspace mounts/subpaths, fortis-repo-egress and optional rdg_personal_agents networks, UID 1000:1000, read-only rootfs, dropped capabilities, no-new-privileges, /tmp and /home/node tmpfs, resource ceilings, restart policy, image and runtime config. The shared Guard policy now explicitly allows exactly this optional RO client volume and no other extra mount.

**GO-3 read-only pre-recreate script prepared:** /workspace/repo/Workfiles/_fortis_windows_transfer_tmp/20261102-go3-repo-recreate-preflight-01/Inspect-R7-Repo-Recreate-ReadOnly-20261102.ps1, SHA256 4bb8e9977d291adc2c698ae5580e7dda024e7e4f9196631cf7a85c60da0b03b0, 11,668 bytes. It uses the canonical shared policy from the Windows tunnel clone, checks current Repo policy and Linux runtime config, verifies R7 health/exact image/four server mounts/loopback ports, checks client-volume labels and attachment metadata, captures Docker image/network/volume/container inspect plus docker diff, and saves the complete inspect snapshot encrypted with Windows DPAPI CurrentUser under %LOCALAPPDATA%\Fortis\GO3-Cutover. It never reads volume file contents, never prints environment values/secrets and issues no Docker mutation. PowerShell 7 parser PASS in the Linux review environment; Windows PowerShell 5.1 parser/runtime still must be executed by owner.

**Cutover/rollback caution:** a container mount cannot be added in-place; docker restart alone is insufficient. Recreating fortis-repo-test interrupts both Repo1 and Repo2 docker exec/MCP sessions and also interrupts this Fortis Repo tool session (the tool runs inside that container). Therefore the next owner-side sequence is: (1) run the read-only script and review sanitized output; (2) derive exact recreate and rollback commands from the actual inspect snapshot; (3) preserve the old stopped container as a rollback object rather than deleting it; (4) only after a separate explicit owner GO, replace fortis-repo-test with the same image/config plus the one RO mount; (5) verify new Guard Preview and reconnect Repo1 then Repo2; (6) retain rollback until GO-4 acceptance.

**Authorization boundary:** current instruction authorizes continuation and the read-only preflight only. It is not yet the final destructive GO to stop/rename/remove/recreate the shared Repo container. No Docker container has been stopped/recreated in this step; no volume was changed; no Sonar request or POST was made.


### 15.1 GO-3 preflight correction: Docker legacy Binds (2026-11-02)

The first read-only preflight review-01 stopped at its R7 mount check. Owner-side read-only diagnostics proved this was a checker defect, not an R7 deployment defect:

- R7 is running and healthy.
- Exact image ID remains sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024f2c062bac0a18ce4.
- Effective Mounts contains exactly the four expected named volumes and destinations, with state RW and identity/grant/token RO.
- Docker records the requested legacy volume declarations in HostConfig.Binds (four entries) and reports HostConfig.Mounts = null. The first checker incorrectly required four HostConfig.Mounts entries.

A corrected read-only script was prepared as review-02:

/workspace/files/_fortis_windows_transfer_tmp/20261102-go3-repo-recreate-preflight-02/Inspect-R7-Repo-Recreate-ReadOnly-20261102.ps1

SHA256: 7d00dff6db2333bbacdf740a4b6dcfd6e1cee8380e016b9c4dac5a901105e0b3 (12,341 bytes).

Review-02 validates both views independently: exactly four effective non-tmpfs Mounts, exactly four expected HostConfig.Binds strings with exact RO/RW modes, and no HostConfig.Mounts entries. PowerShell 7.6.9 parser PASS; synthetic positive case PASS; wrong access mode, extra bind and mixed Mounts/Binds negative cases all DENY as expected. Static scans confirm no Docker mutation commands and no secret-value output. The /workspace/files/... and /workspace/repo/Workfiles/... transfer paths resolve to identical bytes.

The first Windows launch exposed a transfer encoding defect: the artifact contained two literal escaped BOM strings rather than one UTF-8 BOM. It has been corrected to a single actual UTF-8 BOM and CRLF line endings. The corrected bytes are mirrored at both transfer paths. PowerShell 7.6.9 parser, synthetic positive/negative mount tests, static no-mutation scan and no-secret-output scan all PASS.

Still OPEN: Windows PowerShell 5.1 SHA/parser verification for the corrected review-02 and live read-only preflight execution. No R7/Repo container was changed, no volume content was read or modified, and no Sonar request was made. Do not use review-01 again.


### 15.2 GO-3 review-03: PowerShell 5.1 null-array correction (2026-11-02)

The corrected review-02 passed Windows SHA256 and PowerShell 5.1 parsing, but its live read-only run stopped at the R7 requested/effective mount count check. The underlying issue was the checker expression @($r7.HostConfig.Mounts): in Windows PowerShell 5.1 a scalar $null wrapped in the array subexpression is counted as one element. Owner's prior raw Docker inspect established that HostConfig.Mounts is actually JSON null, while HostConfig.Binds contains the four expected legacy volume declarations and effective Mounts contains the four resolved volumes.

A new immutable transfer artifact review-03 was created:

/workspace/files/_fortis_windows_transfer_tmp/20261102-go3-repo-recreate-preflight-03/Inspect-R7-Repo-Recreate-ReadOnly-20261102.ps1

SHA256: 329c7973e92aa61520d97c7d4bbaca926ba850202fa94be2cd6ca88398bdbc49; size 12,597 bytes; one actual UTF-8 BOM and CRLF. Identical mirror: /workspace/repo/Workfiles/_fortis_windows_transfer_tmp/20261102-go3-repo-recreate-preflight-03/Inspect-R7-Repo-Recreate-ReadOnly-20261102.ps1.

Review-03 filters null values from HostConfig.Mounts before counting. It accepts the known legacy-Binds representation only when exactly four effective mounts and four exact requested Binds are present, and continues to reject any non-null Mounts object, extra bind, or incorrect RO/RW mode. PowerShell 7.6.9 parser PASS; synthetic null-Mounts positive case PASS; wrong access, extra bind and non-null Mounts negative cases DENY; static Docker-mutation and secret-output scans PASS.

Still OPEN: owner must transfer review-03 to Windows, verify exact SHA/size and Windows PowerShell 5.1 Parser.ParseFile, then execute the read-only preflight. Do not use review-01 or review-02 again. No container/volume mutation, no volume-content read, no Sonar request, and no Repo recreate occurred during review-03 preparation.


### 15.3 GO-3 pre-recreate inventory accepted; snapshot decode next (2026-11-02)

Owner-reported Windows read-only verification of review-03 completed:

- Exact fortis-repo-test full container ID and pinned image ID matched.
- The three original RW workspace mounts matched exactly.
- docker diff contained exactly C /workspace, A /workspace/files, and A /workspace/repos; owner independently confirmed the set exactly. These are accepted as expected mountpoint scaffolding corresponding to the three existing volume destinations, not unexplained writable-layer changes.
- NO_CONTAINER_MUTATION and NO_VOLUME_CONTENT_READ confirmed.
- Existing DPAPI CurrentUser snapshot remains at %LOCALAPPDATA%\Fortis\GO3-Cutover\20261102-144258\fortis-repo-test.inspect.dpapi, SHA256 31d12e32e2f7cade1cb1f058e31e57b6819489bfb0b8d3888144d7507badcc74.

This closes the review-03 writable-layer STOP. It does NOT authorize or perform container stop/rename/create/start.

Next read-only action is to decode the existing DPAPI snapshot locally under the same Windows user and review the exact Docker create/rollback contract. A sanitized decoder artifact was prepared at:

/workspace/repo/Workfiles/_fortis_windows_transfer_tmp/20261102-go3-cutover-snapshot-review-01/Inspect-R7-Cutover-Snapshot-ReadOnly-20261102.ps1

SHA256 e3888b0d8bbc89ae5929a1fccb47f303f4397050f46de157871e9b8c5af74d74, size 9,665 bytes. Mirror under /workspace/files/_fortis_windows_transfer_tmp/... is byte-identical. It checks the known DPAPI snapshot hash, decrypts in memory using the original entropy and CurrentUser scope, validates snapshot schema/container/image identity, and emits sanitized Docker config metadata only. It does not print environment values, label values, command/entrypoint values, or secrets; it performs no Docker mutations and reads no volume contents.

The decoder has passed static scans for DPAPI unprotect, no Docker mutation commands, and no secret-value output. PowerShell is not installed in the Linux review container, so Windows PowerShell 5.1 SHA/Parser/runtime verification remains OPEN. Owner must transfer the exact artifact, verify SHA/size and PS5.1 Parser.ParseFile, then run it. Use its sanitized output to derive and review a deterministic recreate/rollback plan. Only after that plan is checked may a separate explicit owner GO authorize the cutover.

No container has been stopped, renamed, removed, recreated or started in this step. R7 remains untouched. No Sonar request was made; Sonar POST remains prohibited.


### 15.4 GO-3 snapshot decoded; network/volume detail review next (2026-11-02)

Owner-reported Windows execution of Inspect-R7-Cutover-Snapshot-ReadOnly-20261102.ps1 completed with:
- exact decoder SHA256 e3888b0d8bbc89ae5929a1fccb47f303f4397050f46de157871e9b8c5af74d74, size 9,665 bytes;
- Windows PowerShell 5.1 parser PASS;
- DPAPI CurrentUser decrypt PASS and snapshot SHA256 matched 31d12e32e2f7cade1cb1f058e31e57b6819489bfb0b8d3888144d7507badcc74;
- exact old Repo container ID and image ID matched the preflight evidence;
- no Docker mutation, no volume-content read, no environment values or secret values printed.

Snapshot-derived Repo configuration:
- image ref fortis-repo-mode:dc-0.2.52, exact image ID sha256:2c84fabebb34265e53b020f21a11683a4c68cbb41a08f5f11f9b01c7de5ed8c9;
- user 1000:1000, working directory /workspace/repos, read-only rootfs, non-privileged, CapDrop=ALL, no-new-privileges, runtime runc, restart unless-stopped;
- memory 4 GiB, NanoCPUs 2, PIDs 512, shm 64 MiB;
- network mode fortis-repo-egress, attached networks fortis-repo-egress and rdg-personal_agents;
- tmpfs /home/node = rw,nosuid,nodev,noexec,uid=1000,gid=1000,mode=700,size=128m; /tmp = rw,nosuid,nodev,noexec,mode=1777,size=128m;
- exactly three requested volume mounts, all source fortis-repo-workspace: /workspace/repo root, /workspace/repos subpath Repos, /workspace/files subpath Workfiles; all RW;
- HostConfig.Binds count 0; HostConfig.Mounts count 3;
- effective environment, Entrypoint and Cmd exactly match the pinned image defaults. The first decoder did not yet compare User/WorkingDir against image defaults; that comparison is included in the detail review.
- snapshot contains inspect metadata for two networks and six named volumes. Their exact drivers/options/labels/IPAM metadata and the Repo endpoint details have not yet been reviewed.

Important correction to older narrative: the three workspace paths are not host bind mounts or three independent volumes. They are three subpath mounts of the same named volume fortis-repo-workspace. Any recreate command must preserve VolumeOptions.Subpath exactly. Do not use -v shorthand or recreate the workspace volume.

Next read-only artifact:

/workspace/repo/Workfiles/_fortis_windows_transfer_tmp/20261102-go3-cutover-snapshot-review-02/Inspect-R7-Cutover-Network-Volume-ReadOnly-20261102.ps1

SHA256 dc67f00243efeeb05506de5d3ab202bc9d7f19cd3ce1313fc7067555cdea38ce, size 12,714 bytes. Byte-identical mirror is under /workspace/files/_fortis_windows_transfer_tmp/20261102-go3-cutover-snapshot-review-02/. It decrypts the same DPAPI snapshot and emits sanitized requested/effective mount metadata, image-default comparisons, Repo network endpoint details, two network inspect records and six volume inspect records. It prints only label/option key names except the non-secret R7 client role and a boolean provision-ID format check. It makes no Docker calls, reads no volume contents and prints no environment values/secrets.

Static review with the bundled PowerShell 7.6.9 parser PASS; transfer mirrors byte-identical; static no-Docker-mutation scan PASS; DPAPI-only source scan PASS. This is not Windows PowerShell 5.1 or Windows runtime evidence. Owner must transfer, verify SHA/size, parse with Windows PowerShell 5.1 and execute locally before exact network/volume metadata can be accepted.

No Docker container or network has been changed. The old fortis-repo-test remains running; R7 remains untouched. No Sonar request or POST was made. No cutover authorization has been issued.


### 15.5 GO-3 network/volume detail review accepted; recreate contract corrections (2026-11-02)

Owner-reported Windows execution of Inspect-R7-Cutover-Network-Volume-ReadOnly-20261102.ps1 completed:
- exact SHA256 dc67f00243efeeb05506de5d3ab202bc9d7f19cd3ce1313fc7067555cdea38ce, size 12,714 bytes;
- Windows PowerShell 5.1 Parser.ParseFile PASS;
- DPAPI CurrentUser decrypt PASS; snapshot SHA256 remains 31d12e32e2f7cade1cb1f058e31e57b6819489bfb0b8d3888144d7507badcc74;
- two network records and six volume records found; exact expected name sets PASS;
- no Docker commands, no volume-content reads, no environment values/secrets printed.

Exact networks from snapshot:
- fortis-repo-egress: ID 65a8a1d816e3c6e5703d976d31514ecd657dfb14f5e5fafaba0e5208046e3ffd; bridge/local; Internal=false; IPv6=false; subnet 172.18.0.0/16, gateway 172.18.0.1; attachable=false; ingress=false.
- rdg-personal_agents: ID a4b5b7e37facafe180b5bb572ea3d228e3349b77f6babb760452708082566524; bridge/local; Internal=true; IPv6=false; subnet 172.25.0.0/16, gateway 172.25.0.1; attachable=false; ingress=false.
- Both network IDs and metadata must be rechecked live immediately before cutover. Reuse existing networks; do not recreate them. Preserve internal=true on rdg-personal_agents and attach the replacement Repo to both networks. No static IP or alias was configured in the old Repo endpoint.

Exact named volumes from snapshot (all Driver=local, Scope=local, no driver options):
- fortis-repo-workspace (label key fortis.repo-mode): retain untouched and preserve all three existing requested mounts/subpaths.
- fortis-r7-state, fortis-r7-grant, fortis-r7-identity, fortis-r7-sonar-token: R7 server volumes; do not detach, remount, recreate, or inspect contents.
- fortis-r7-client: label keys com.fortis.r7.p1.role and com.fortis.r7.p1.provision-id; role client-only; provision ID format is 32 hex characters. Mount into replacement Repo only at /run/fortis-client, read-only. Snapshot metadata does not prove the current attachment count; live pre-cutover check is still required.

CRITICAL CORRECTION TO §15.4: Repo Config.WorkingDir is /workspace/repos, while the pinned image default WorkingDir is /workspace/repo (REPO_WORKDIR_MATCH_IMAGE_DEFAULT=False). A replacement must explicitly set working directory /workspace/repos; inheriting the image default is wrong. Config.User is 1000:1000 and matches image default. Environment, Entrypoint and Cmd match image defaults. Therefore preserve the exact pinned image and explicitly override only WorkingDir (plus the reviewed new client mount and network membership).

Additional exact runtime values to preserve:
- Memory=4,294,967,296 bytes (4 GiB); MemorySwap=5,368,709,120 bytes (5 GiB total limit); MemoryReservation=0.
- NanoCpus=2,000,000,000; CpuShares=0; CpuQuota=0; CpuPeriod=0; PidsLimit=512; ShmSize=67,108,864 bytes (64 MiB).
- IpcMode=private; CgroupnsMode=private; Runtime=runc; AutoRemove=false.
- RestartPolicy=unless-stopped, MaximumRetryCount=0.
- Log driver json-file, no log config.
- No port bindings; no devices/device requests; no volumes-from; no extra hosts; no sysctls; no ulimits.
- CapDrop=ALL; CapAdd empty; SecurityOpt contains no-new-privileges; Privileged=false; ReadonlyRootfs=true.
- tmpfs exactly /home/node = rw,nosuid,nodev,noexec,uid=1000,gid=1000,mode=700,size=128m and /tmp = rw,nosuid,nodev,noexec,mode=1777,size=128m.
- HostConfig.Binds=0 and HostConfig.Mounts=3. Requested VolumeOptions.Subpath values are empty/root for /workspace/repo, Repos for /workspace/repos, and Workfiles for /workspace/files; all three are RW. Effective Mounts.SubPath printed empty, so use requested HostConfig.Mounts.VolumeOptions.Subpath as the source of truth. Do not use -v shorthand.

Snapshot writable-layer diff remains the accepted exact set C /workspace, A /workspace/files, A /workspace/repos, reviewed in §15.3 as mountpoint scaffolding. The snapshot was captured at 14:42:58 +07:00; live network IDs, container identity/state, R7 health/mounts and client volume attachment must be rechecked immediately before any cutover.

CUTOVER REMAINS NOT AUTHORIZED. No container/network/volume mutation occurred during this detail review. The old fortis-repo-test remains the rollback candidate; R7 remains untouched. No Sonar request or POST was made. The next gate is a fresh read-only live pre-cutover check that accepts only the previously reviewed Docker diff set and confirms client-volume attachment is absent (or exactly the expected Repo attachment if already provisioned), R7 remains healthy on its pinned image with its exact four mounts, and both network IDs remain unchanged. Only after presenting the deterministic create/rollback plan should a separate explicit owner GO authorize stop/rename/create/start.


### 15.6 GO-3 fresh live pre-cutover verification artifact (2026-11-02)

Prepared current artifact:

/workspace/repo/Workfiles/_fortis_windows_transfer_tmp/20261102-go3-live-precutover-review-02/Test-R7-Repo-Live-PreCutover-ReadOnly-20261102.ps1

Byte-identical mirror:

/workspace/files/_fortis_windows_transfer_tmp/20261102-go3-live-precutover-review-02/Test-R7-Repo-Live-PreCutover-ReadOnly-20261102.ps1

SHA256 d72610fbf3e34c6af3c7e1c49f4bd71050990e0d167690fbeb5e3906a9221650; size 19,036 bytes; ASCII, CRLF, no BOM. PowerShell 7.6.9 parser PASS; static no-Docker-mutation PASS; static no-file-write PASS; output-sanitization review PASS; transfer mirrors byte-identical.

Review-01 is superseded. Review-02 corrects PowerShell 5.1 null/empty collection counting for optional Docker inspect fields. Do not transfer or execute review-01.

The script is read-only. It invokes only Docker inspect, image inspect, network inspect, volume inspect, docker ps, and docker diff, plus local file/hash checks. It does not stop/start/recreate/rename/remove containers, change networks, mount/unmount volumes, write files, read volume contents, or issue Sonar requests. It loads Docker inspect metadata in memory; environment arrays are compared to pinned image defaults but never printed or persisted. It also verifies the existing DPAPI rollback snapshot path/hash.

Required checks:
- original Repo full container ID and pinned image ID; running state; user, working directory, read-only rootfs, non-privileged status, runtime, resource limits, capabilities, security options, tmpfs, log driver, and no unexpected devices/ports/extra mounts;
- exact three workspace mount sources/targets/subpaths and RW mode; client mount absent;
- exact two Repo network names and network IDs; rdg-personal_agents remains Internal=true;
- all six expected local volume metadata records; client role/provision-ID metadata and zero client-volume attachments;
- one R7 container, running/healthy on exact scoped image, exact four server mounts and RO/RW modes, /tmp, and loopback-only published ports;
- exact accepted old Repo diff set: C /workspace, A /workspace/files, A /workspace/repos;
- existing DPAPI rollback snapshot SHA256.

Windows transfer and execution remain OPEN. Owner must use Windows PowerShell 5.1, transfer from the Fortis Repo container, verify exact size/SHA, run Parser.ParseFile, and execute the read-only script. Expected terminal markers include GO3_LIVE_PRECUTOVER_PREFLIGHT_PASS, CUTOVER_NOT_AUTHORIZED, NO_DOCKER_MUTATION, NO_VOLUME_CONTENT_READ, and NO_SONAR_REQUEST.

Any STOP or mismatch means no cutover; preserve output and investigate only the failed check. If PASS, present the deterministic create/rollback commands for review and request a separate explicit owner GO. This script itself does not authorize or perform cutover.


### 15.7 GO-3 live pre-cutover verification correction (2026-11-02)

Owner executed review-02 on Windows. Integrity and Windows PowerShell 5.1 parser checks passed. Execution reached the final docker diff call, where it stopped because review-02 passed an undefined $repoId variable, causing Docker to receive docker diff with no container argument. This is a script defect, not evidence of a Docker/R7/volume failure. No mutating command was invoked; no cutover occurred. The docker diff read itself did not run.

Corrected artifact: review-03.

Container path:
/workspace/repo/Workfiles/_fortis_windows_transfer_tmp/20261102-go3-live-precutover-review-03/Test-R7-Repo-Live-PreCutover-ReadOnly-20261102.ps1

Windows mirror path:
/workspace/files/_fortis_windows_transfer_tmp/20261102-go3-live-precutover-review-03/Test-R7-Repo-Live-PreCutover-ReadOnly-20261102.ps1

SHA256 1a13b6783ce2d4c2f6504f6f5498ce9ea5f72dd9972d58f85875023832acf053; size 19,239 bytes; ASCII/CRLF/no BOM. It uses the already-pinned and verified full Repo container ID $repoIdExpected for docker diff and asserts that value is nonempty. PowerShell 7.6.9 parser PASS, static undefined-variable check PASS, static no-mutation/no-file-write checks PASS, and the two transfer mirrors are byte-identical.

Review-03 supersedes review-02. Transfer review-03 to Windows, verify exact size and SHA256, parse with Windows PowerShell 5.1, and run. Do not rerun review-02. Preserve all STOP output. Cutover remains unauthorized until a complete PASS and a separate explicit owner GO.


### 15.8 GO-3 live pre-cutover PASS and owner-reviewed cutover plan (2026-11-02)

**Owner-reported Windows review-03 execution: PASS.** Exact SHA256 and size were accepted; Windows PowerShell 5.1 Parser passed. Live checks passed for Repo full identity/security/runtime, three workspace mounts/subpaths, exact two network IDs/policy, six volume metadata records, client-only volume unattached, R7 healthy on pinned image with exact four server mounts, accepted Repo writable-layer diff, and DPAPI rollback snapshot integrity. Final markers: GO3_LIVE_PRECUTOVER_PREFLIGHT_PASS, CUTOVER_NOT_AUTHORIZED, NO_DOCKER_MUTATION, NO_VOLUME_CONTENT_READ, NO_SONAR_REQUEST. No Docker mutation occurred.

**GO state correction:** GO-1 DONE; GO-2 DONE (the owner handoff records registered WebAuthn credential and successful login); GO-3 live pre-cutover PASS, but Repo recreate/mount not yet done; GO-4 not started. The previous interim assistant summary that GO-2 enrollment still required confirmation was too cautious; the existing owner evidence records GO-2 complete.

Owner-readable cutover plan prepared (review only; not an executable script):

/workspace/files/_fortis_windows_transfer_tmp/20261102-go3-cutover-plan-review-01/GO3-CUTOVER-PLAN-20261102.md

Size 7,986 bytes; SHA256 e2e2cb2b48d4401bef368a95b380851d338c18060a5c54dc2577cdc463be0308.

Exact plan preserves:
- old Repo full ID 0c0f8cb2d608679b4c3de51c527cbe2aca687cbf1360e6bf116444b2a0928cc2 as a stopped rollback container named fortis-repo-test-go3-rollback-20261102-144258;
- image reference fortis-repo-mode:dc-0.2.52 and required image ID sha256:2c84fabebb34265e53b020f21a11683a4c68cbb41a08f5f11f9b01c7de5ed8c9;
- all three existing RW workspace volume mounts and exact Repos/Workfiles subpaths;
- only one new mount fortis-r7-client:/run/fortis-client:ro;
- /workspace/repos working directory (must be explicit; image default differs);
- UID, RO rootfs, CapDrop=ALL, no-new-privileges, both tmpfs, resources, restart/log/runtime and both existing networks;
- no volume/network deletion or recreation, no R7 restart, no Sonar request.

The plan includes the proposed docker create argument array, secondary network connect, post-create verification, rollback sequence (remove only replacement container without -v, restore the original full-ID container), Repo1/Repo2 Guard Preview/reconnect, and GO-4 boundary. The Fortis Repo tool session runs inside this container, so cutover must be run entirely from local Windows PowerShell 5.1 and will interrupt the tool session.

**No cutover authorization has been issued.** The plan is for owner review only. Before execution, the rollback container name must be confirmed absent, the image tag->ID and network IDs must be rechecked, R7 health/mounts and client-volume unattached state rechecked, and the DPAPI snapshot revalidated. A separate explicit owner GO is required before stop/rename/create/start. Retain the old stopped Repo through GO-4 acceptance.


### 15.9 GO-3 cutover and rollback scripts prepared — Windows review pending (2026-11-02)

Two owner-review scripts were created under:

/workspace/files/_fortis_windows_transfer_tmp/20261102-go3-cutover-scripts-review-02/

1. Invoke-GO3-Repo-Cutover.ps1
   - 18,590 bytes
   - SHA256 399d737e3b49f485da7fd2da1cb53d8eabaf935ccbe692e40e0ddbe21ff16660
   - Performs read-only preflight first: exact old Repo full ID, pinned local image tag->image ID, DPAPI snapshot hash, expected old Repo config/mounts/subpaths/diff, exact network IDs/policy, six volume metadata records, client volume role/provision-id/unattached state, and R7 health/image/four mounts.
   - Requires typed local confirmation RECREATE-FORTIS-REPO before writing a state record and making Docker changes.
   - Stops and renames the old Repo to fortis-repo-test-go3-rollback-20261102-144258, preserving its exact full ID; creates the replacement with the same pinned image/config plus only fortis-r7-client:/run/fortis-client:ro; attaches the existing internal network; inspects before start; starts and verifies; retains the old stopped container.
   - Does not delete containers, volumes or networks; does not restart R7; makes no Sonar request.

2. Restore-GO3-Repo-Rollback.ps1
   - 10,945 bytes
   - SHA256 13b6a27ab191d76abff3b1594ac929b4dcb7a5953b18f0bc9ce3cb9786ba941a
   - Reads the local cutover state file and requires the exact original full ID/name and recorded replacement full ID.
   - Requires typed local confirmation ROLLBACK-GO3-REPO.
   - If a replacement exists, verifies its recorded full ID, pinned image ID and exact four-mount contract, then removes only that container with docker rm (no -v); restores and starts the preserved old container; verifies the original ID/mounts, client volume unattached, original network IDs/policy and R7 health/image/mounts.
   - Never deletes a volume or network and never restarts R7.

Static review: both files are ASCII, CRLF, no BOM; delimiter scan passed; static policy audit passed. Confirmed cutover mutations are limited to stop/rename/create/network-connect/start; rollback removes only the recorded replacement container without -v, then renames/starts the old container. No volume/network delete, Sonar HTTP client or Sonar request is present.

Important verification limit: this Linux Fortis Repo environment has no PowerShell executable and no Docker CLI. The static delimiter scan is not a PowerShell parser. Windows PowerShell 5.1 Parser.ParseFile for both exact files is still OPEN. The files have not been transferred to Windows or executed. Neither script is authorized to run yet. Transfer, verify exact byte size/SHA256 and run Windows PowerShell 5.1 Parser.ParseFile only; do not invoke either script until a separate explicit owner GO for cutover or rollback.


### 15.10 GO-3 cutover script revision-03 — R7 identity pin added (2026-11-02)

Revision-02 is superseded. Transfer and review only revision-03:

/workspace/files/_fortis_windows_transfer_tmp/20261102-go3-cutover-scripts-review-03/

- Invoke-GO3-Repo-Cutover.ps1 — 19,134 bytes; SHA256 1af5ba6d32745c45683ddf169b2a8b41bd506bd00fe43af2ed42b20f9efa71f2.
- Restore-GO3-Repo-Rollback.ps1 — 11,216 bytes; SHA256 b6124b7fb7945939d2d0350bd40d4a5aad2b9cd36209ae1a3baade6d0947458c.

Revision-03 improvement: the cutover script captures the exact live R7 full container ID during read-only preflight, saves it in the local cutover state, and verifies the same R7 ID after Repo recreate. Rollback requires that saved R7 ID and verifies it remains unchanged, healthy, on the pinned image and with the same four server mounts. Repo policy checks also pin the previously observed PID/UTS/user namespace defaults and zero CPU reservation/quota/share settings.

Static policy audit PASS: ASCII/CRLF/no BOM, balanced delimiters, cutover mutations restricted to stop/rename/create/network-connect/start, rollback removes only the exact recorded replacement container without -v and restores the old container; no volume/network delete, no R7 restart, no Sonar HTTP/request. The scripts have not been executed. The current Linux environment has no PowerShell executable or Docker CLI, so delimiter/static checks are not a PowerShell parser/runtime test.

Next owner action: transfer only revision-03 to Windows; verify exact byte sizes and SHA256; run Windows PowerShell 5.1 Parser.ParseFile on both. Do not invoke either script. GO-3 cutover still requires a separate explicit owner GO after parser PASS and review of the exact script contents.


### 15.11 GO-3 script revision-04 — exact runtime-config checks strengthened (2026-11-02)

Revision-03 is superseded for cutover. Revision-03's Windows SHA/size and PowerShell 5.1 parser checks passed, but final content review against §15.5 found that the cutover preflight did not fail closed on every explicitly recorded empty/default setting. No script was executed and no Docker mutation occurred.

Revision-04 bundle:

/workspace/files/_fortis_windows_transfer_tmp/20261102-go3-cutover-scripts-review-04/

- Invoke-GO3-Repo-Cutover.ps1 — 20,000 bytes; SHA256 bb69f287dd76ddd0877ba315919f6b0d0ef236ac8a6beaaed2adb7cad0763c9e.
- Restore-GO3-Repo-Rollback.ps1 — 11,216 bytes; SHA256 b6124b7fb7945939d2d0350bd40d4a5aad2b9cd36209ae1a3baade6d0947458c (unchanged from revision-03).

Revision-04 cutover preflight now additionally requires exactly one SecurityOpt entry and that it is no-new-privileges (no extras); PublishAllPorts=false; ExtraHosts empty; Sysctls empty; Ulimits empty; LogConfig.Config empty. This aligns the checks with the accepted snapshot detail in §15.5. It retains the full R7 container-ID pin and existing mount/network/image/resource checks. Rollback script is byte-identical to the already Windows-parser-verified revision-03 rollback script.

Static review: both files ASCII, CRLF, no BOM; delimiter scan PASS; static mutation policy audit PASS. Cutover mutations remain stop/rename/create/network-connect/start only. Rollback removes only the exact recorded replacement container without -v, then restores the preserved old container. No volume/network delete, R7 restart, or Sonar HTTP/request.

**Owner action:** transfer revision-04 to Windows, verify exact size/SHA256 and run Windows PowerShell 5.1 Parser.ParseFile on both. Do not execute either script. Revision-04 supersedes revision-03 for cutover; no cutover authorization has been issued. After parser PASS, perform a final review and obtain a separate explicit owner GO before any Docker mutation.


### 15.12 GO-3 revision-04 Windows integrity and PowerShell 5.1 verification PASS (2026-11-02)

Owner-reported local Windows PowerShell 5.1 checks for the revision-04 bundle:

- Invoke-GO3-Repo-Cutover.ps1: 20,000 bytes; SHA256 bb69f287dd76ddd0877ba315919f6b0d0ef236ac8a6beaaed2adb7cad0763c9e; exact size/SHA PASS; Parser.ParseFile PASS.
- Restore-GO3-Repo-Rollback.ps1: 11,216 bytes; SHA256 b6124b7fb7945939d2d0350bd40d4a5aad2b9cd36209ae1a3baade6d0947458c; exact size/SHA PASS; Parser.ParseFile PASS.
- Final owner markers: GO3_REVISION04_VERIFIED_PASS, CUTOVER_NOT_EXECUTED, ROLLBACK_NOT_EXECUTED.

Revision-04 supersedes revision-03 for cutover. No Docker mutation occurred during this Windows verification. This establishes file integrity and Windows PowerShell 5.1 syntax only; it is not live cutover evidence and does not authorize execution.

**Current GO state:** GO-1 DONE; GO-2 DONE; GO-3 source/Guard release and read-only live pre-cutover checks PASS; GO-3 revision-04 script integrity/PS5.1 parser PASS; GO-3 controlled Repo recreate/client RO mount NOT EXECUTED and NOT AUTHORIZED; GO-4 NOT STARTED; Sonar POST=0.

Next action is a separate explicit owner authorization for GO-3. If authorized, owner runs Invoke-GO3-Repo-Cutover.ps1 locally from Windows PowerShell 5.1 only, reviews its fresh read-only preflight, then enters the script exact confirmation phrase RECREATE-FORTIS-REPO. Do not run it from the Fortis Repo container/tool session. Retain the old stopped container and DPAPI snapshot until GO-4 acceptance. Keep the rollback script available; never run rollback unless an actual cutover failure or explicit rollback decision requires it.


### 2026-11-03 — GO-3 current Repo mount owner-reported PASS

Owner supplied current Windows Docker inspect evidence for `fortis-repo-test`:

- current Repo container ID: `04fed7b726a8536d63c4d2533cfc7ee3072956ff0c3f571504d7f709f7909030`;
- `fortis-r7-client` is mounted at `/run/fortis-client` with `RW=false`;
- the three existing `fortis-repo-workspace` mounts remain at `/workspace/files`, `/workspace/repo` and `/workspace/repos` with RW=true;
- networks `fortis-repo-egress` and `rdg-personal_agents` remain attached with the accepted network IDs.

The older revision-04 GO-3 script was pinned to the superseded Repo ID and stopped before mutation. This inspect evidence is the authoritative current-runtime mount evidence; do not rerun the stale script. GO-3 runtime cutover/client RO mount is therefore **OWNER-REPORTED PASS**. The next gate is live Repo → R7 READ/report; no Sonar WRITE has occurred.
