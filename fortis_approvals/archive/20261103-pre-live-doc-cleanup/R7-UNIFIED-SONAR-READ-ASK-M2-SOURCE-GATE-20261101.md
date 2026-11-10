# R7 — один Fortis: Sonar READ + mutation ASK и ограниченный клиент Repo

> **CURRENT VERDICT 2026-11-03:** This file is a historical evidence journal. GO-1 trusted provisioning and GO-2 P1 R7 deployment/owner enrollment are **OWNER-REPORTED WINDOWS PASS**. GO-3 source/Guard release, revision-04 integrity and read-only pre-cutover checks are PASS, but Repo recreate/client RO mount are **NOT EXECUTED / NOT AUTHORIZED**. The P2 package and owner-reported Windows image/import audit pass for image `sha256:e751f6ca0cfe6ce290cf580de2f243071ee1f3e681baa8827c6cea41a16fa402`; P2 is not deployed. Full pinned WebAuthn/HTTPS remains BLOCKED in the Linux Repo environment. GO-4/live Repo→R7→Sonar E2E remains OPEN. Later dated evidence and the main plan supersede earlier next-step wording below; do not repeat provisioning, P1 build/audit or old preflights.

**Первоначальная дата журнала:** 2026-11-01. **Текущий срез:** 2026-11-02, `R7 P1 WINDOWS IMAGE-ONLY BUILD + EXACT-ID OFFLINE IMAGE AUDIT OWNER-REPORTED PASS / LIVE INTEGRATION OPEN`. **Не развёрнуто на Windows, не зарегистрировано как MCP tools Fortis Repo.** Реального SonarCloud-токена, Sonar GET/POST или изменяющего Docker действия нет. Это подготовка P1, **не** M2/M3 live PASS.

**Цель без изменения архитектуры:** любой авторизованный AI использует существующий Fortis Repo и передаёт typed request на **ОДИН** trusted Fortis контейнер с частным service token и одной owner Approvals queue. Когда нужны секрет или ASK — обращение идёт через Fortis; если не нужны — свободные операции могут идти прямо. Условие `DENY` перекрывает даже доступный сервисный токен. Один WebAuthn-owner, один `Core`, один `RepoIngress`, разные owner/machine порты; **никакого внешнего executor** и универсального HTTP proxy.

## Получившиеся исходники

- `fortis_approvals/r7_unified_candidate.py`: полноценная source-композиция именно R7 (без изменений действующего A3/R5), четыре typed Sonar `READ ALLOW` + `('sonarcloud','accept_issue'): ASK` в одном Core, `RepoIntentBroker` с READ и mutation grant, owner portal с strong-proof и **`blocked_approvals={('sonarcloud','accept_issue')}`**. Независимый транспорт `NoWriteTransport` отвергает любой Sonar POST до underlying network, даже если `Core.execute` вызвать вне браузерного route. Одна owner очередь для ASK; status доступен только инициатору.
- `fortis_approvals/r7_unified_server.py`: один source-only runtime с **TLS1.3 machine 19104** и **owner UI 19103**. Точный private grant и отдельный Sonar service token читаются только из owner-provisioned 0600 файлов; реальные файлы на Windows **не создавались**. `preflight-imports` (без сети/токена) и `health` готовы как source.
- `deploy/Dockerfile-R7-Unified-Read-Ask-Candidate` и `compose-r7-unified-read-ask.yaml`: неисполненные source-only кандидаты, явный список 15 Python modules и static assets, UID10001, readonly root, без Docker socket; внешние owner-prepared volumes `fortis-r7-state/identity/grant/sonar-token` (предыдущая volume/state preparation уже PASS; все четыре существуют и не прикреплены к контейнерам по owner metadata от 2026-11-02) и отсутствующий в системе R7 service. Повторное создание volumes запрещено. Порты совпадают с неизрасходованными R5 pilot ports, поэтому R5 и R7 **нельзя запускать параллельно** на одних published ports; R7 не усыновляет даже R5 state/marker.
- `fortis_approvals/repo_sonar_tools.py`: исходный **узкий клиент** из Repo для 6 операций (см. ниже), фиксированный `https://host.docker.internal:19104` и TLS cert verification, **ProxyHandler({})**, запрет произвольного URL/method, owner/admin routes и raw service tokens. Читает только scoped machine ingress grant из **отдельного** owner-provisioned 0600 `/run/fortis-client/grant` (не Sonar token, не Repo workspace); публичный pinned cert из `/run/fortis-client/server.crt`. Вызов mutation требует стабильный явный `--request-id`, чтобы другой UUID не создавал второй запрос при неопределённом исходе. Ответы строго типизированы, статус чужой заявки недоступен по политике Fortis. Никакого плейсхолдера bearer/token внутри исходников нет.
- **Важно:** Fortis Repo является недоверенным и имеет универсальную возможность запускать процессы. Его **scoped machine grant** может стать известным скомпрометированному ИИ, имеющему произвольную shell-capability. Поэтому никакой выданный Repo grant НЕ должен позволять owner approve, прямой upstream service POST или owner-only доступ. Разделение отдельных AI actors/grants и запрет bypass через другие plugins остаются M2/O-10 OPEN. Установка фиксированных `sonar.*` инструментов непосредственно в MCP surface Fortis Repo требует отдельного обновления его сервера/регистрации и подтверждения после нового запуска: написание Python-клиента **само по себе не добавляет инструменты в список текущего плагина**.

## Кандидат интерфейса Fortis Repo (ещё не зарегистрирован в MCP)

| Предлагаемое имя typed tool | Серверный маршрут | Условие |
|---|---|---|
| `sonar.list_projects` | `POST /v1/reads` | organization, page, pageSize, READ grant + ALLOW |
| `sonar.list_issues` | `POST /v1/reads` | project, page, pageSize, READ grant + ALLOW |
| `sonar.get_issue` | `POST /v1/reads` | issue key + projectKey, READ grant + ALLOW |
| `sonar.get_quality_gate` | `POST /v1/reads` | project; **CURRENT_DEFAULT_BRANCH**, `NOT_VERIFIED_D2`, не «PR проверен» |
| `sonar.propose_accept_issue` | `POST /v1/actions` | issue + projectKey + reason + stable request UUID, mutation grant + mandatory ASK |
| `approvals.request_status` | `GET /v1/requests/{uuid}` | только свой requestId, без owner preview/DB |

Это НЕ гарантирует, что любой AI может пользоваться инструментами сегодня; M2 предполагает отдельную owner-approved установку MCP integration, scoped machine client identities, отрицательные проверки и реальные вызовы Fortis Repo→Windows Fortis.

## Что проверено без реальной сети к Sonar

- `tests/test_r7_unified_candidate.py`: R7 source-composition не принимает R5/A3/G4 state, работает с новой private root 0700, duplicate/invalid org/grant fail-closed, один Core/owner portal/machine, `NoWriteTransport` не пропускает POST.
- Наследуемые R6 сценарии с **реальным ephemeral localhost HTTPS TLS1.3** и WebAuthn virtual authenticator: все четыре READ, quality gate `ERROR/CURRENT_DEFAULT_BRANCH`; source policy `ASK`, machine `202 PENDING`, owner pending после входа, three approve routes disabled, strong reject, status `REJECTED`, actor-bound status, replay и конфликт UUID, no POST.
- Реальный Python `repo_sonar_tools.call` → SSL/TLS1.3-validated R7 ephemeral listener (только тест перенаправляет TCP на localhost, SNI остаётся `host.docker.internal`): получает Quality Gate и Issue, создаёт `PENDING`, читает свой статус, без Sonar service token, без POST. Сервер Fortis один и тот же. **Это не подключённый MCP tool и не внешняя сеть Windows**.
- `tests/test_r7_image_manifest.py`: явные source filenames, manifest SHA, отсутствие вложенных секретных файлов/Repo client в будущем Docker image; compose readonly/isolated/private external volumes.
- Через **настоящий подключённый инструмент Fortis Repo** выполнена безопасная командная проверка `python -m fortis_approvals.repo_sonar_tools sonar.get_quality_gate`: **fail-closed**, пока нет `/run/fortis-client/grant` — `FORTIS_REPO_TOOL_DENIED=FORTIS_MACHINE_GRANT_FILE_REQUIRED`, без stdout данных и без внешней сети. Это доказывает только возможность запуска клиентского кода в Repo, **не** реальный Fortis/Sonar доступ и не регистрацию отдельных MCP tools.

## Owner Windows R7 REVIEW image-only build: owner-reported PASS, 2026-11-01 (не допуск)

- Source review ZIP: `/workspace/repo/Workfiles/fortis-r7-unified-source-review-20261101.zip` — **148981 bytes**, SHA256 `b0055e1954174b11794de787f1eff17506b68610859677e463df8eb94ae12cb9`; ровно **20 разрешённых source файлов + 1 SOURCE-MANIFEST.sha256**, без доверенных credentials/client grants/token file и без непредусмотренных путей. Manifest SHA256 `aca6ce714e8225e7f8e4638362b5f0ffa54f4e3a816f1ff80bf484229379257d`. Dockerfile SHA256 `b40e80a526c98e53a2df1cd07900a4513bfbe9fd2062726f05f776de0a8e0fce`.
- Owner source PowerShell: `fortis_approvals/deploy/Build-R7-Windows-ImageOnly.ps1`; immutable copy `/workspace/repo/Workfiles/Build-R7-Windows-ImageOnly-20261101.ps1` — **5992 bytes**, SHA256 `7ed8d5c65043f31ee6546b6d092c0f80e85f9779cf5a6b4897a4dacd0dbb943d`. Скрипт: проверяет exact ZIP SHA + manifest + SHA всех 20 файлов, Linux Docker Engine, отсутствие collision review-tag, системный диск 8 GiB free; выполняет ТОЛЬКО `docker build --no-cache --pull=false` с manifest-bound isolated context; inspect нового image ID. **Возможно сетевое скачивание образа и pip wheels, расход места/времени**, но нет `docker run/compose/stop/restart`, открытых портов, изменений A3/Repo/Guards/volumes/credential provision или запросов Sonar.
- Review tag: `fortis-r7-unified-read-ask-candidate:review-20261101-b0055e19` — не перезаписывать. **Owner-reported IMAGE BUILD PASS** с ID `sha256:d555bcd2baf10297e05547d8be7049fbbca80a40df4378e9912e0a3cbbdd9fba`, плюс owner output `FORTIS_R7_CONTAINERS_STARTED=NONE`, `FORTIS_R7_SONAR_TOKEN_PROVISIONED=NO`, `FORTIS_R7_SONAR_POST=DISABLED`, `FORTIS_R7_TRUSTED_ADMISSION=OPEN`. Это **не доказательство** preflight import внутри образа, независимого base provenance или реального Sonar GET; image не развёрнут.
- `tests/test_r7_windows_image_build_static.py` сверяет SHA ZIP, список, manifest и точные байты Workfiles скрипта и запрет опасных Docker-команд; `package_r7_review.py` — deterministic packager с no-overwrite. **STATIC SOURCE PASS ≠ Docker build PASS**. Build-only image НЕ допуск Sonar/owner GO и НЕ миграция единого Fortis.

**Исторический шаг v1 (выполнен и FAILED, не повторять): SHA-verified isolated R7 smoke:** `fortis_approvals/deploy/Smoke-R7-Windows-ImageIsolated.ps1`, новая неизменяемая Workfiles copy `/workspace/repo/Workfiles/Smoke-R7-Windows-ImageIsolated-20261101.ps1` (4469 bytes), SHA256 `ecc76e667d467bb729393ce88939da71ea6140f84f6f3a0f49c3cf8421f3d0ae`. Сверяет exact owner-reported image ID/metadata, затем запускает **только один временный `docker run --rm --pull=never --network none --read-only`** без volumes, ports, service token и других контейнеров, команду `r7_unified_server preflight-imports` с двумя обязательными success markers; проверяет auto-remove и оставляет admission OPEN. Source+Workfiles SHA и три static tests PASS; **впоследствии owner выполнил v1 smoke и получил EXIT_NONZERO (см. раздел ниже).** Отдельный audit всех image-file SHA, pip provenance и любые production действия остаются следующими gates.

**Отдельная регистрация MCP-инструментов:** настоящий Fortis Repo является runtime адаптером Desktop Commander, см. `/workspace/repo/Repos/tunnel/runtime/repo-mode/fortis-mcp-bridge.mjs`, который сейчас пробрасывает список инструментов установленного backend. Чтобы `sonar.*` стало отдельными живыми инструментами, нужно безопасно дополнить **источник MCP runtime и схему permissions**, протестировать tool registry и только после owner+Guard Preview обновить live bridge; не редактировать установленный мост или не перезапускать текущий Repo из chat. Наличие CLI `repo_sonar_tools.py` в workspace не регистрирует MCP tools.

## Windows R7 v1 import-smoke STOPPED → исправлено в исходниках v2 (2026-11-01)

**Владелец фактически выполнил прежний Smoke-R7-Windows-ImageIsolated-20261101.ps1** (его SHA256 совпал). Owner output: `FORTIS_R7_REVIEW_IMAGE_ID_MATCH_PASS`, `FORTIS_R7_REVIEW_IMAGE_METADATA_PASS`, `FORTIS_R7_SMOKE_BEGIN_NO_NETWORK_NO_MOUNTS_NO_PORTS`, затем `R7_IMAGE_IMPORT_SMOKE_EXIT_NONZERO`. Значит **Windows R7 v1 import smoke FAILED**, import PASS приписывать нельзя. Скрипт не запускал сервера и не создавал production volumes/ports; временный `docker run --rm` настроен на удаление, но owner ещё не прислал отдельный after-run container-list readback.

**Причина воспроизведена на байтах точного v1 ZIP:** `r7_unified_server.py` в команде `preflight-imports` содержит `from .g4_candidate import NoWriteTransport`, тогда как `g4_candidate.py` намеренно **отсутствует** в минимальном образе R7. Изолированная копия v1 archive даёт `ModuleNotFoundError: No module named 'fortis_approvals.g4_candidate'` и exit 1. Предыдущие source tests, запущенные из полного development checkout, эту ошибку не обнаруживали. Данный сбой объясняет owner log на уровне source, но сам Windows stderr не собирался, поэтому не утверждать, что локально на Windows это был единственный фактор.

**Исправление:** только source `r7_unified_server.py` теперь берёт `NoWriteTransport` из `r7_unified_candidate.py`, где он уже реализован и входит в минимальный R7-образ. Старые v1 zip, PowerShell, Docker image и tag **не изменять**; rebuild требуется под новым именем.

**Новый проверенный пакет v2:**
- `/workspace/repo/Workfiles/fortis-r7-unified-source-review-v2-20261101.zip` — 20 pinned source files + 1 manifest, **148989 bytes**, SHA256 `f9791fd1e5cee092092897825e7886fe040cc0d71d5ea43179c5593cb5ac9df7`, manifest SHA256 `c59e2b02f0404dab835c094806f5cb634e84ed81cb69f9c88d9004591db2a995`, Dockerfile прежний SHA256 `b40e80a526c98e53a2df1cd07900a4513bfbe9fd2062726f05f776de0a8e0fce`.
- `/workspace/repo/Workfiles/Build-R7-Windows-ImageOnly-v2-20261101.ps1` — **6107 bytes**, SHA256 `60fcfdb9eab1a101e887343a62fcf9e92f41d8f1cef10798db52f3c4d54d6971`. Тот же build-only guardrail/sha manifest preflight, immutable **новый** review tag `fortis-r7-unified-read-ask-candidate:review-20261101-f9791fd1`; оригинальный Windows R7 v1 image ID `sha256:d555bcd2baf10297e05547d8be7049fbbca80a40df4378e9912e0a3cbbdd9fba` остаётся неизменным, не использовать для live.
- В `tests/test_r7_windows_image_v2_release.py` **в каждом прогоне** воспроизводится failure точного v1 ZIP и success `exit 0 + TWO markers` точного **распакованного v2 ZIP в отдельной директории с отдельным PYTHONPATH**; SHA всех 20 файлов сравниваются с текущим фиксированным source. Original v1 tests остаются исторически привязаны к их невосстанавливаемым байтам. **Это OFFLINE v2 imported-package PASS, а НЕ Windows v2 build/import PASS.**
- **Исторический шаг v2 build уже выполнен владельцем (PASS):** image ID зафиксирован ниже. Следующее актуальное действие — отдельный SHA-pinned v2 isolated smoke; прежний v1 smoke не применять к v2. Нельзя запускать старый v1 smoke против v2, подменять старый тег или делать `docker compose up`.
- **R7 trusted admission остаётся OPEN;** SonarCloud token не provisioned; Sonar WRITE disabled; существующие A3, Fortis Repo, Repo1/Repo2 Guards не затронуты.

## Что ещё нужно, порядок приёмки

1. **R7 build-only owner-reported PASS → isolated import smoke OPEN**: сверить exact R7 image ID, package source SHA и safe image metadata, выполнить owner-only one-time offline smoke; отдельный image contents SHA/pip audit и независимые base digest/dependency/CVE остаются OPEN. Старый R5 image не изменять. **R7 deploy GO отсутствует.**
2. **Восстановить/продлить действующий A3 TLS** до owner-reported `2026-11-07T23:29:17Z`; это отдельно от R7. Проверить R7 TLS identity/grant lifecycle, owner certificate trust and backup, защищённую выдачу отдельных `fortis-r7-*` private volumes и подлинного Sonar READ token **только владельцем в Windows trust boundary**; Repo1/Repo2 Guards перед воздействующими live changes.
3. **M2 интеграция инструментов:** расширить сам Fortis Repo MCP server (не просто создать Python CLI) шестью typed tools, прочно закрепить constant upstream endpoint, выдачу клиентских grants без Sonar service tokens, caller identity по actor и по операциям; собрать реальные доказательства двух разных AI actors. При необходимости оставить первую версию с одним scoped-actor, но **не считать A-01 PASS**.
4. **M3 первый live Sonar READ** через тот же Windows R7 с project allowlist, четырьмя READ, bad-grant/bad-project отрицательными тестами, без token leakage. Подтвердить реальную GitHub/Sonar PR SHA связь **отдельно** (D1/D2), не выдавать default-branch Quality Gate за PR checks PASS.
5. **M4 live ASK NO-WRITE:** настоящий Repo typed proposal попадает в тот же owner Approvals, owner WebAuthn Reject, caller read status; все approve routes всё ещё `403`; remote Sonar Issue неизменна. **M5 WRITE=NO-GO**, пока владелец отдельно не разрешит единственный disposable Sonar POST и не проверит stale/UNCERTAIN/readback.

**Вердикт:** `FORTIS_R7_UNIFIED_READ_ASK_SOURCE_GATE=TESTED`; `FORTIS_M2_PRODUCTION_AI_MCP_TOOLS=OPEN`; `FORTIS_R7_V2_WINDOWS_IMAGE_BUILD=OWNER_REPORTED_PASS_IMPORT_SMOKE_OPEN`; `FORTIS_R7_LIVE_SONAR_GET=NOT_EXECUTED`; `FORTIS_R7_SONAR_POST=DISABLED`; `FORTIS_UNIVERSAL_GATEWAY_PRODUCTION_ACCEPTANCE=OPEN`.

## R7 v2 owner-reported Windows build PASS → v2 image smoke OPEN (2026-11-01)

**Owner evidence:** `FORTIS_R7_IMAGE_ONLY_BUILD_PASS`; tag `fortis-r7-unified-read-ask-candidate:review-20261101-f9791fd1`, image ID `sha256:2a047aaa6ab74a0b3e47e3a02b3ac663301f8363515f0cd32ed3ad1a562d1b73`; `FORTIS_R7_CONTAINERS_STARTED=NONE`, `FORTIS_R7_SONAR_TOKEN_PROVISIONED=NO`, `FORTIS_R7_SONAR_POST=DISABLED`, `FORTIS_R7_TRUSTED_ADMISSION=OPEN`. Это PASS **только image build**, не startup/import, не живой R7 и не Sonar.

**Следующий один owner-only скрипт:** `fortis_approvals/deploy/Smoke-R7-Windows-ImageIsolated-v2.ps1`; Workfiles immutable copy `/workspace/repo/Workfiles/Smoke-R7-Windows-ImageIsolated-v2-20261101.ps1`, **5319 bytes**, SHA256 `997b315733382158a3ae08677738bc746c808404349d2ff7cf21f5d8ec81cd3f`. Exact pinned **v2** image ID; unique temporary container `fortis-r7-v2-import-smoke-20261101`; one Docker `run --rm --pull=never --network none --read-only` with no ports, secrets or external volumes, readonly UID10001, bounded CPU/memory/PIDs. It checks image metadata, verifies temporary container auto-removal **even when import fails**, and checks both `FORTIS_R7_UNIFIED_READ_ASK_IMPORTS_PASS` and `FORTIS_R7_SONAR_POST=DISABLED`. On failure prints bounded diagnostics from the disconnected/secret-free smoke before raising. **Source static tests PASS; v2 Windows owner execution NOT YET DONE**.

After owner-reported image smoke PASS, next check is an independent actual image-file SHA/pip contents audit, then separate owner-controlled admission gates. SonarCloud service token is not provisioned; no real GET or WRITE, and the existing A3, Fortis Repo, Guards, R5 and volumes are not changed. **Full R7 acceptance remains OPEN.**

## R7 v2 Windows exact-image bytes + pip check AUDIT PASS (owner-reported 2026-11-01)

Владелец выполнил SHA-verified `Audit-R7-v2-Windows-ImageContents-20261101.ps1`; получено `FORTIS_R7_V2_OWNER_REVIEW_IMAGE_PIN_PASS`, `FORTIS_R7_V2_IMAGE_19_INSTALLED_SOURCE_SHA256_PASS`, `FORTIS_R7_V2_IMAGE_FOUR_PINNED_PIP_VERSIONS_PASS`, `FORTIS_R7_V2_IMAGE_PIP_CHECK_PASS`, `FORTIS_R7_V2_AUDIT_DISPOSABLE_CONTAINERS_REMOVED_PASS`, `FORTIS_R7_V2_IMAGE_BYTES_AND_DEPENDENCIES_OWNER_AUDIT_PASS`. Также владелец сообщил `FORTIS_R7_V2_IMAGE_BASE_PROVENANCE_VULNERABILITY_ADMISSION=OPEN`, `FORTIS_R7_V2_TLS_GRANT_LIFECYCLE=OPEN`, `FORTIS_R7_V2_SONAR_TOKEN_PROVISIONED=NO`, `FORTIS_R7_V2_TRUSTED_ADMISSION=OPEN`. Сверка 19 installed files использует манифест **точного** архивного review image v2; четыре pinned версии и `pip check` проверены в трёх одноразовых сетево изолированных контейнерах. Это **owner-reported Windows image source/install audit**, не независимое происхождение base image, не CVE clearance и не production-deploy.

Точный R7 v2 image ID `sha256:2a047aaa6ab74a0b3e47e3a02b3ac663301f8363515f0cd32ed3ad1a562d1b73`, тег `fortis-r7-unified-read-ask-candidate:review-20261101-f9791fd1`. Рабочие A3/G2/G4/Repo и Guards остаются без изменённых конфигураций; R7 не запущен как service и не имеет настоящего Sonar token. Следующие gates: **base digest provenance + актуальный независимый vulnerability/SBOM scan**, проверенный TLS/grant revoke/rotation и отдельные реальные MCP AI инструменты; **Sonar POST остаётся отключён**.

## R7 v2 Windows import smoke PASS → точные image bytes/pip AUDIT OPEN (2026-11-01)

**Owner-reported v2 smoke PASS:** `FORTIS_R7_REVIEW_IMAGE_ID_MATCH_PASS`, `FORTIS_R7_REVIEW_IMAGE_METADATA_PASS`, `FORTIS_R7_SMOKE_BEGIN_NO_NETWORK_NO_MOUNTS_NO_PORTS`, `FORTIS_R7_V2_DISPOSABLE_CONTAINER_AUTO_REMOVED_PASS`, `FORTIS_R7_UNIFIED_READ_ASK_IMPORTS_PASS`, `FORTIS_R7_SONAR_POST=DISABLED`, `FORTIS_R7_V2_REVIEW_IMAGE_IMPORT_SMOKE_PASS`, `FORTIS_R7_RUNNING_SERVICES_NOT_MODIFIED_BY_SCRIPT`, `FORTIS_R7_SONAR_NETWORK_REQUESTS=NONE`, `FORTIS_R7_SERVICE_TOKEN_PROVISIONED=NO`, `FORTIS_R7_REPO_GUARDS_PREVIEW=NOT_EXECUTED`, `FORTIS_R7_TRUSTED_ADMISSION=OPEN`. Exact owner-image SHA256 `sha256:2a047aaa6ab74a0b3e47e3a02b3ac663301f8363515f0cd32ed3ad1a562d1b73`. This closes image-only isolated import **but not image content audit or deployment**.

**Next immutable owner-only script:** `/workspace/repo/Workfiles/Audit-R7-v2-Windows-ImageContents-20261101.ps1` — **7864 bytes**, SHA256 `fb729cf5b13bf1ae7545565f96bb96b20480d4dbf0fef5dc108b60c2fee06de3`, source `fortis_approvals/deploy/Audit-R7-v2-Windows-ImageContents.ps1`. Static tests `test_r7_v2_windows_image_contents_audit_static.py` verify SHA allowlist against the exact v2 ZIP `f9791fd1e5cee092092897825e7886fe040cc0d71d5ea43179c5593cb5ac9df7`, exactly **19 files** actually copied into R7 image (excluding build-context Dockerfile), owner-reported image ID, pinned four installed Python package versions (`fido2==2.2.1`, `cryptography==50.0.2`, `cffi==2.1.1`, `pycparser==3.12`) and offline `pip check`. Three `docker run --rm --pull=never --network none --read-only` ephemeral containers, no volumes/ports/secret mounts, UID10001. Source/static tests PASS; **owner Windows image contents audit NOT YET EXECUTED**.

**Residual gates unchanged:** independent Python/base-image provenance and vulnerability admission, TLS and grant issuance/revocation (A3 certificate expiry 2026-11-07T23:29:17Z), sealed owner-only Sonar service token provisioning, actual Fortis Repo registered MCP typed tools, real unified Windows Sonar GET and ASK, PR/SHA checks attestation, bypass review. Sonar POST disabled, production admission OPEN.


## R7 P1 source package prepared — exact current checkout (2026-11-02)

**Source drift audit:** the historical v2 ZIP differs from the current checkout in exactly three of its 20 pinned files: `fortis_approvals/core.py`, `fortis_approvals/owner_portal.py`, and `fortis_approvals/r7_unified_candidate.py`. Dockerfile and `requirements-owner.txt` are byte-identical to v2. The v2 image/tag/evidence remain immutable historical evidence and are not the P1 candidate.

**New immutable source package:**
- Repo builder: `fortis_approvals/deploy/package_r7_p1_20261102.py` (deterministic, no Docker/network/secrets, no-overwrite).
- Workfiles package: `/workspace/repo/Workfiles/fortis-r7-unified-source-review-p1-20261102.zip`; 20 explicit source files + `SOURCE-MANIFEST.sha256`; **150781 bytes**; ZIP SHA256 `7755e84ecb2a4abf23c66d97707a81838cadc2424c2c24700a499aa3b9a1d0d5`; manifest SHA256 `eeac1cb7847fb8c99f949b878d69968c311556fc5a27c91851db459f5e1db3cb`; Dockerfile SHA256 remains `b40e80a526c98e53a2df1cd07900a4513bfbe9fd2062726f05f776de0a8e0fce`.
- Target immutable review tag: `fortis-r7-unified-read-ask-candidate:review-p1-20261102-7755e84e`.
- Owner build-only source: `fortis_approvals/deploy/Build-R7-Windows-ImageOnly-p1-20261102.ps1`; immutable Workfiles copy `/workspace/repo/Workfiles/Build-R7-Windows-ImageOnly-p1-20261102.ps1`; **409a8062ea6ed8cc4378ac2e7e7e2b73f1572036a39679741a564b23cf04734f**. Script pins exact ZIP/manifest/Dockerfile/20-file allowlist, requires Linux Docker and 8 GiB free, rejects tag collision, builds only the new image tag and inspects image ID. It contains no `docker run`, `compose`, start/stop/restart, volume, token, service or Sonar command; output explicitly says `DEPLOYMENT=NOT_AUTHORIZED`.
- Exact archive extracted to a temporary isolated directory and `python -B -m fortis_approvals.r7_unified_server preflight-imports` returned exactly `FORTIS_R7_UNIFIED_READ_ASK_IMPORTS_PASS` and `FORTIS_R7_SONAR_POST=DISABLED`, with empty stderr and no checkout fallback.

**Current targeted verification:** `test_r7_p1_release.py` **3/3 PASS** (exact ZIP/source/manifest, isolated import, owner build script/copy/guardrails); `test_repo_sonar_tools.py` **12/12 PASS**; `test_r7_image_manifest.py` **3/3 PASS**. Combined **18/18 PASS**. The earlier `test_r7_unified_candidate.py` **17/17 PASS** remains previously recorded; it was not rerun in this container because its WebAuthn fixture imports `cryptography`, which is not installed here. No dependency was installed and no repository dependency file was changed.

**Not performed:** Windows Docker image build, Windows import/content audit for P1, R7 startup/deploy, TLS certificate or machine grant provisioning, new private volumes, Sonar token provisioning, any Sonar GET/POST, live MCP tool registration, GitHub workflow dispatch, A3/G2/G4/R5/Repo/Guard changes. `FORTIS_R7_P1_WINDOWS_BUILD=NOT_RUN`; `FORTIS_R7_P1_DEPLOYMENT=NOT_AUTHORIZED`; `FORTIS_R7_P1_TRUSTED_ADMISSION=OPEN`.

**Next owner-controlled gate:** inspect the exact Workfiles ZIP and build script hashes; only after explicit owner GO, run the build-only PowerShell script on Windows. It may consume disk/time and Docker may need the base image/pinned wheels; it does not start or deploy the service. After owner returns the image ID, prepare a separately SHA-pinned, no-network/no-mount isolated import/content audit. Tool registry, workflow dispatch and minimum TLS/grant/token admission remain independent OPEN gates.
## R7 P1 Windows image-only build — owner-reported PASS (2026-11-02)

Owner sent a PowerShell transcript containing `FORTIS_R7_P1_IMAGE_ONLY_BUILD_PASS`,
exact tag `fortis-r7-unified-read-ask-candidate:review-p1-20261102-7755e84e`,
image ID `sha256:2c634df43b988d05a83a5479aaf1d51fbea863da9a4e602aae7ce938815e4b78`,
`CONTAINERS_STARTED=NONE`, `SONAR_TOKEN_PROVISIONED=NO`,
`SONAR_POST=DISABLED`, `TRUSTED_ADMISSION=OPEN`, and
`DEPLOYMENT=NOT_AUTHORIZED`. This is **owner-reported Docker build evidence**,
not independent image-byte verification; no additional image build is necessary.

Prepared a new exact-ID offline audit script:
`fortis_approvals/deploy/Audit-R7-P1-Windows-ImageOffline-20261102.ps1`,
SHA256 `3e73f098e2a5b1053b9705a74537d514404d44217afbfa4970649f406687e108`.
Copied byte-for-byte to
`/workspace/repo/Workfiles/_fortis_windows_transfer_tmp/20261102-r7-p1-offline-audit/Audit-R7-P1-Windows-ImageOffline-20261102.ps1`.
Static tests `test_r7_p1_image_offline_audit_static.py`: **2/2 PASS**.
Script pins the owner-reported image ID and expected SHA256 of **19 installed
source files for the NEW artifact**, checks public image metadata, executes
two disposable `--rm --network none --read-only` containers for `sha256sum`
and `preflight-imports`. It does not invoke pip list/check, rebuild,
mount, provision, expose ports, deploy services, or contact Sonar.

**Current gate:** offline image audit **NOT RUN / OWNER GO PENDING**.
No P1 service started, no SonarCloud token/GET/POST, no TLS/grants,
no GitHub workflow dispatch or live AI tool registration.
The immutable 2026-11-01 handoff snapshot was not modified.

## P1 pinned Windows image audit — OWNER-REPORTED PASS (2026-11-02)

The owner ran the SHA-pinned `Audit-R7-P1-Windows-ImageOffline-20261102.ps1`
(script SHA256 `3e73f098e2a5b1053b9705a74537d514404d44217afbfa4970649f406687e108`)
and returned the following markers for the **new P1 image only**, not historical v2:

- `FORTIS_R7_P1_OWNER_REVIEW_IMAGE_PIN_PASS`
- `FORTIS_R7_P1_REVIEW_IMAGE_ID=sha256:2c634df43b988d05a83a5479aaf1d51fbea863da9a4e602aae7ce938815e4b78`
- `FORTIS_R7_P1_IMAGE_METADATA_PASS`
- `FORTIS_R7_P1_IMAGE_19_INSTALLED_SOURCE_SHA256_PASS`
- `FORTIS_R7_P1_EXACT_IMAGE_IMPORTS_PASS`
- `FORTIS_R7_P1_SONAR_POST_DISABLED_IMPORT_PASS`
- `FORTIS_R7_P1_AUDIT_DISPOSABLE_CONTAINERS_REMOVED_PASS`
- `FORTIS_R7_P1_IMAGE_OFFLINE_IMPORT_AND_SOURCE_AUDIT_PASS`
- `FORTIS_R7_P1_NO_LIVE_CONTAINER_DEPLOYMENT`
- `FORTIS_R7_P1_SONAR_TOKEN_PROVISIONED=NO`
- `FORTIS_R7_P1_SONAR_NETWORK_REQUESTS=NONE`
- `FORTIS_R7_P1_PINNED_PIP_AND_PIP_CHECK=NOT_REPEATED`
- `FORTIS_R7_P1_TRUSTED_ADMISSION=OPEN`

**Verdict:** image-only build **PASS owner-reported**; exact-ID offline image
metadata/source hash/import **PASS owner-reported**; Windows Docker is not
directly observable from the Repo container. The two audit containers were
disposable and isolated from the network. Pinned pip dependencies and `pip
check` were intentionally **NOT repeated**. No image rebuild, Sonar traffic,
real ASK/approval, live Fortis process or token/grant/credential provisioning
occurred in this gate. Do not repeat these immutable image audits absent a
new image digest, incident, or explicit new acceptance scope.

**Next P1 gate OPEN:** one authorized AI actor needs a safe supported
Fortis Repo tool-registration surface for the six fixed Sonar typed operations.
Current `repo_sonar_tools.py` is client/CLI only; the existing
`/workspace/repo/Repos/tunnel/runtime/repo-mode/fortis-mcp-bridge.mjs`
is a presentation/pass-through layer over Desktop Commander, **not** a
Sonar tool registry. It has been inspected read-only, **not modified**.
Next, select one owner-approved GitHub/SonarCloud project and existing
workflow, then complete a minimal, separately owner-approved trusted R7
deployment with TLS1.3, one scoped machine identity and private Sonar READ
token before real READ. No Sonar WRITE GO has been issued; double write
blockers stay on. M2/M3/M4 live remain OPEN; M5 NO-GO.

## P1 routing clarification — trusted destination-policy proxy (2026-11-02)

Owner decision: **the Fortis Secure Gateway is the trusted application proxy and policy enforcement point**. Do **not** require six new MCP tool registrations or modify the existing Fortis Repo MCP bridge for P1. The authorized AI can use the existing Fortis Repo process capability to invoke a fixed HTTPS client (`repo_sonar_tools.py`) or send equivalent limited requests to the R7 machine ingress. The client is a convenience, **not a security perimeter**: arbitrary Repo shell/HTTP requests must still be denied server-side unless they match an authenticated actor, preapproved destination/service, exact operation, route, target/project scope, bounded schema and rate limit.

Current source is **typed operation routing**, not a general-purpose URL-forwarding proxy: `RepoIngress` allows only `POST /v1/reads`, `POST /v1/actions` and `GET /v1/requests/{id}`; `RepoIntentBroker` checks actor operation scopes; `Core` enforces `ALLOW/ASK/DENY` for `(actor, service, operation)`; service adapters choose the pinned Sonar upstream host/path. A `POST /v1/reads` is a read-only *machine ingress call*, **not** a Sonar mutation. Sonar READ operations are `ALLOW`, `accept_issue` is ASK/proposal `PENDING` with zero upstream Sonar POST; unknown operations/destinations are `DENY`. The historical v2/P1 images both hard-block Sonar writes via `NoWriteTransport` plus owner `blocked_approvals`. Owner `Approve` on Sonar is **not enabled** for P1-A/B. The firewall isolates the network boundary; Gateway policy decides operation permission and requires one machine identity even for `ALLOW`.

Pilot destination selected by owner and verified from GitHub: `AlexPastukhh/obs-planning-docs`, `main`, `.github/workflows/sonarqube.yml` (supports `workflow_dispatch`), Sonar project `AlexPastukhh_obs-planning-docs`, organization `alexpastukhh`. The Sonar scan includes the Planning Helper JavaScript component, **not the entire documentation repository**. The latest GitHub workflow run checked was successful (2026-10-29); actual live SonarCloud QG/issues are still unverified. GitHub workflow dispatch is a **separate future destination/operation** and must be allowlisted and owner-approved (ASK first); it is not currently supported by the P1 R7 Sonar proxy.

**Live gate still OPEN**: Windows P1 image audit is owner-reported PASS, but no live R7 deployment, new TLS identity/machine grant, Sonar READ credential, mounted client secrets, or real Repo→R7→SonarCloud GET. No new MCP tools, direct owner-admin connector, generic shell executor in Fortis, new image, or Sonar WRITE required for the first READ smoke.

## P1 single-project destination scope — source hardening and new immutable candidate (2026-11-02)

**Detected limitation before live credential provisioning:** previously accepted P1 image `sha256:2c634df43b988d05a83a5479aaf1d51fbea863da9a4e602aae7ce938815e4b78` has an *organization-wide* allowlist: if the Fortis-held Sonar credential can see multiple projects in owner-approved org, machine callers can read/query/propose on them. This is not evidence of an exploit or secret leakage: P1 had no live service, grant or Sonar token. Do not deploy the historical image for **one-project** OBS P1. No need to repeat the existing owner build/audit; they remain PASS for their exact historical bytes.

**Exact project fixes to source:** `SonarReadAdapter` accepts owner-controlled `allowed_project_keys`, gates Issues / individual Issue / Quality Gate **before** foreign-project HTTP and filters `list_projects` to only those pinned keys (with membership verification). `build_r7_unified_candidate` passes the same project allowlist to both trusted READ and ASK adapter; the ASK adapter's project allowlist disables its organization-wide fallback. `r7_unified_server.create_servers` requires one valid `project_key` before reading secrets; `main` requires `FORTIS_SONAR_PROJECT_KEY`. Compose requires `FORTIS_SONAR_PROJECT_KEY` from owner, not from AI payload. Unknown destination/URL/method and Sonar POST remain DENY, no new MCP tool registration.

**Target:** GitHub `AlexPastukhh/obs-planning-docs` branch `main`, workflow `.github/workflows/sonarqube.yml` (GitHub `workflow_dispatch`), Sonar organization `alexpastukhh`, pinned project `AlexPastukhh_obs-planning-docs`; only Planning Helper JavaScript is scanned. Real SonarCloud READ remains OPEN.

**Source/offline evidence:** `test_sonar_read_adapter.py` now 15/15 PASS, `test_r7_unified_candidate.py` now 19/19 PASS using existing fido2/cryptography venv, including TLS/owner Reject E2E and new foreign-project READ/ASK denies, plus a read-only preflight draft pinned to the older P1 image (3/3 static PASS, later retired without use or transfer). These are **not** Windows-live results. Historical P1 archive tests are intentionally tied to the old source bytes.

**NEW immutable scoped-project source package:** `/workspace/repo/Workfiles/fortis-r7-unified-source-review-p1-scoped-20261102.zip`, 20 source files and manifest, 152366 bytes, SHA256 `fac3131e52cf2ca549d40f6037645519e33e61d332dd70e659a06d0b3dd27f83`; manifest SHA256 `e58bde24a1a7ca714c2202879367d944bf90c14cd76dba94f121641b33b7ad74`. Relative to previous P1 ZIP only three production source files and the manifest changed: `sonar_read.py`, `r7_unified_candidate.py`, `r7_unified_server.py`. Immutable source builder: `fortis_approvals/deploy/package_r7_p1_scoped_20261102.py`. Owner **image-only** build script `fortis_approvals/deploy/Build-R7-Windows-ImageOnly-p1-scoped-20261102.ps1`, Workfiles byte-exact copy, SHA256 `83a87c9bc1d5104fc6200f1fc04b55de4112e9c87bb9baa1c8f15f8c638d68a0`, target tag `fortis-r7-unified-read-ask-candidate:review-p1-scoped-20261102-fac3131e`. New package exact source/isolated import/build-script/compose static tests **4/4 PASS**.

**NO Windows action performed** for scoped project revision: image-only build NOT RUN, isolated Windows image audit NOT RUN, live deployment NOT AUTHORIZED, no TLS/grant/token/volume, no Sonar GET/POST, no GitHub workflow dispatch. Only after an **explicit owner GO** on the new versioned package can a new image be built, inspected, audited and later separately deployed. The previously drafted read-only preflight pinned to the *old* image should not be used for the scoped image; prepare a fresh exact-image-ID preflight **after** the owner gives the new image ID. This is not a request to redo old v2/P1 audits.

**Scoped source-only Windows transfer staged (not copied to Windows, not executed):** `/workspace/repo/Workfiles/_fortis_windows_transfer_tmp/20261102-r7-p1-scoped-build/fortis-r7-p1-scoped-transfer-20261102.zip`, 159640 bytes, SHA256 `c75b9b9919c7f42ba8ecc718ac246ca64b98dc8d8ff339caee7360e4a37c7d1e`, manifest SHA256 `6c93633eaece508af924c8d967cbbd7dafbf4f59ca3b17e1f9356b60239a3213`. Contains only the scoped P1 source ZIP and image-only PowerShell script (plus transfer manifest); exact contents/sha verified. Transfer on Windows, build and image audit all require distinct owner actions; nothing to run now. No Windows files were assumed to appear automatically from Docker.

## R7 P1 scoped-project Windows image-only build — owner-reported PASS (2026-11-02)

Owner supplied the PowerShell output from the **new scoped-project** image-only build:

- `FORTIS_R7_P1_SCOPED_IMAGE_ONLY_BUILD_PASS`
- tag `fortis-r7-unified-read-ask-candidate:review-p1-scoped-20261102-fac3131e`
- `FORTIS_R7_P1_SCOPED_REVIEW_IMAGE_ID=sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024f2c062bac0a18ce4`
- `FORTIS_R7_P1_SCOPED_CONTAINERS_STARTED=NONE`
- `FORTIS_R7_P1_SCOPED_SONAR_TOKEN_PROVISIONED=NO`
- `FORTIS_R7_P1_SCOPED_SONAR_POST=DISABLED`
- `FORTIS_R7_P1_SCOPED_TRUSTED_ADMISSION=OPEN`
- `FORTIS_R7_P1_SCOPED_DEPLOYMENT=NOT_AUTHORIZED`

**Verdict:** scoped Windows image-only build **OWNER-REPORTED PASS** for this exact image ID. Docker is not directly available from the repo connector to independently verify Windows image contents; **19 installed source SHA256, image metadata, and isolated image import are still NOT YET owner-run for this new image**. Earlier unscoped P1/v2 tests are not substituted for new image content acceptance. Do not rebuild, overwrite old image/tag, or repeat old v2/unscoped P1 audits.

**Scoped offline image audit prepared, NOT RUN:** Repo source `fortis_approvals/deploy/Audit-R7-P1-Scoped-Windows-ImageOffline-20261102.ps1`; exact Workfiles copy at `/workspace/repo/Workfiles/_fortis_windows_transfer_tmp/20261102-r7-p1-scoped-image-audit/Audit-R7-P1-Scoped-Windows-ImageOffline-20261102.ps1`; SHA256 `84c469e780f19544cacbc350450e503b6c73bfa03b5159e251805193ec5c17c2` (both bytes verified equal). Pins **only** scoped image ID `sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024f2c062bac0a18ce4` and 19 installed SHA256 read from the **scoped** 20-file source ZIP manifest; those 19 differ from prior image in precisely `r7_unified_candidate.py`, `r7_unified_server.py`, `sonar_read.py`. The audit does `docker image inspect` (metadata) and runs two ephemeral `--rm --pull=never --network none --read-only` containers exclusively for SHA256 and `preflight-imports`, then verifies cleanup. It does not rebuild, deploy, modify volumes/ports, provide token/grant, call Sonar, or rerun pip pin/`pip check`. New audit static **3/3 PASS**, existing scoped package/test **4/4 PASS**; `RDG_DOCS_AUDIT PASS`. Separate owner GO is required before running this temporary-container audit; **trusted live admission and R7 runtime still OPEN**.

Next after owner audit PASS: plan minimal owner-controlled R7 TLS1.3 identity, one machine grant, one pinned Sonar READ credential and isolated new private volumes with Guard Preview. No deployment or real Sonar READ/ASK/WRITE performed.


## R7 P1 scoped-project image audit — OWNER-REPORTED PASS (2026-11-02)

Owner completed the **new scoped-project exact-ID Windows image audit** and provided the complete PASS markers below. These supersede the `NOT RUN` wording in the preceding chronological entry; no previous image was rebuilt or reaudited.

- `FORTIS_R7_P1_SCOPED_OWNER_REVIEW_IMAGE_PIN_PASS`
- `FORTIS_R7_P1_SCOPED_REVIEW_IMAGE_ID=sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024f2c062bac0a18ce4`
- `FORTIS_R7_P1_SCOPED_IMAGE_METADATA_PASS`
- `FORTIS_R7_P1_SCOPED_IMAGE_19_INSTALLED_SOURCE_SHA256_PASS`
- `FORTIS_R7_P1_SCOPED_EXACT_IMAGE_IMPORTS_PASS`
- `FORTIS_R7_P1_SCOPED_SONAR_POST_DISABLED_IMPORT_PASS`
- `FORTIS_R7_P1_SCOPED_AUDIT_DISPOSABLE_CONTAINERS_REMOVED_PASS`
- `FORTIS_R7_P1_SCOPED_IMAGE_OFFLINE_IMPORT_AND_SOURCE_AUDIT_PASS`
- `FORTIS_R7_P1_SCOPED_NO_LIVE_CONTAINER_DEPLOYMENT`
- `FORTIS_R7_P1_SCOPED_SONAR_TOKEN_PROVISIONED=NO`
- `FORTIS_R7_P1_SCOPED_SONAR_NETWORK_REQUESTS=NONE`
- `FORTIS_R7_P1_SCOPED_PINNED_PIP_AND_PIP_CHECK=NOT_REPEATED`
- `FORTIS_R7_P1_SCOPED_TRUSTED_ADMISSION=OPEN`

**Verdict:** the owner-reported scoped image build and isolated metadata/19-file hash/import/cleanup checks are **PASS for the exact immutable image ID**. It does not establish live deployment, actual SonarCloud GET, owner ASK/Reject, TLS/grant/token admission, or a production release. Do **NOT** ask owner to repeat the image build, import, 19 hashes, four pinned pip versions or `pip check` without a material image change. Sonar POST/Approve remain blocked.

**Next owner-safe gate (READ-ONLY, not yet executed):** `fortis_approvals/deploy/Preflight-R7-P1-Scoped-Windows-ReadOnly-20261102.ps1` checks image ID, reserved localhost ports 19103/19104, fresh R7 volume names, live A3/Repo health and Repo mount isolation; prints no secrets and creates/starts/stops nothing. It does not constitute Repo1/Repo2 Guard Preview. Owner provisioning of *new* R7 state/TLS identity/machine grant/private Sonar READ token and deployment remains separately blocked until exact explicit owner GO. Scope is one actor and Sonar project `AlexPastukhh_obs-planning-docs`; existing A3/G2/G4/Repo untouched.


## R7 scoped runtime preflight — STOP on pre-existing reserved volume (2026-11-02)

Owner ran `Preflight-R7-P1-Scoped-Windows-ReadOnly-20261102.ps1` against the exact scoped image. These checks passed: Linux Docker Engine, exact image ID, `fortis-repo-test` running, A3 healthy, Repo workspace/trusted-mount isolation. It then stopped at `R7_P1_SCOPED_RESERVED_VOLUME_ALREADY_EXISTS_REVIEW_REQUIRED` while checking the four reserved names `fortis-r7-state`, `fortis-r7-identity`, `fortis-r7-grant`, `fortis-r7-sonar-token`.

**Interpretation:** a Docker volume with at least one reserved R7 name already exists. This is a fail-closed safety stop, not evidence of a running R7 container, successful credential provisioning, data compromise, or image failure. The preflight checks for any R7-named container before this gate and had passed that check. The codebase contains a historical `Prepare-R7-Candidate.ps1` which, if executed, creates exactly these four names and initializes `/state/private`; this is a possible provenance only, **not proof it was executed**. The current `compose-r7-unified-read-ask.yaml` declares the same names as external volumes. Do not run Prepare/Verify/Compose, create alternate names, delete, prune, rename, mount, or inspect volume contents yet.

**Next action is metadata-only owner diagnosis:** enumerate all four exact names, report only `Name|Driver|Scope|CreatedAt` and any attached container `Name|Status` using `docker volume inspect --format` and `docker ps -a --filter volume=...`. Do not disclose mountpoints, volume contents, environment, token/cert/grant bytes, or use Docker volume prune/rm. If the volume is referenced by any container or provenance/contents remain unclear, stop and review before any reuse. The Windows preflight is **BLOCKED / not PASS** until this collision is resolved by an explicit owner decision. No volumes/containers/credentials/network/Sonar operations were changed by the failed preflight.


## 2026-11-02 — R7 pre-existing volumes: owner metadata accepted; wrong absence gate superseded

Owner's Windows metadata-only diagnostic returned all four reserved volumes:

| Name | Driver | Scope | CreatedAt | Attached containers |
|---|---|---|---|---|
| `fortis-r7-state` | `local` | `local` | `2026-11-01T08:15:45Z` | NONE |
| `fortis-r7-identity` | `local` | `local` | `2026-11-01T08:15:46Z` | NONE |
| `fortis-r7-grant` | `local` | `local` | `2026-11-01T08:15:46Z` | NONE |
| `fortis-r7-sonar-token` | `local` | `local` | `2026-11-01T08:15:46Z` | NONE |

This matches the current handoff's earlier accepted R7 volume/state preparation and its instruction not to rerun `Prepare-R7-Candidate.ps1`. The times are consistent with that script's sequential creation loop, but no claim is made about the volume contents from metadata. Preserve the existing volumes exactly. No volume contents were read, no container attached, no mutation occurred. Do not run `Prepare-R7-Candidate.ps1`; do not use historical `Verify-R7-Candidate.ps1` because its default image is the old unscoped tag.

**Correction to previous event:** `Preflight-R7-P1-Scoped-Windows-ReadOnly-20261102.ps1` (SHA256 `d201a062…1355dc`) stopped because it wrongly required all prepared R7 volumes to be absent. This is a **preflight script logic defect**, not an actual R7 volume conflict. Its earlier owner-reported checks remain valid: Linux Engine, exact scoped image pin, Repo/A3 health and mount isolation PASS. Port checks were not reached. Retire this script; do not ask owner to rerun it.

**Corrected continuation prepared:** `Preflight-R7-P1-Scoped-Windows-ReadOnly-Resume-20261102.ps1`, SHA256 `07315249b5e7dade0aec85599dc9948fc7d64e31b3c68434d609c1222d33d8b9`; static tests **3/3 PASS**. Workfiles transfer copy at `/workspace/repo/Workfiles/_fortis_windows_transfer_tmp/20261102-r7-p1-scoped-runtime-preflight-resume/` is byte-exact. It pins the same scoped image ID; checks only exact name/driver/scope/CreatedAt tuples and attached-container references for the four pre-existing volumes; checks existing Repo/A3 health and Repo mount isolation; and checks Docker-published + Windows TCP ports 19103/19104. It does not mount/read volume contents, mutate Docker, start/stop containers, provision credentials, run Guard Preview or deploy R7. Windows execution remains OPEN.

Next: owner runs the corrected read-only continuation. If PASS, perform separate Repo1/Repo2 Guard Preview and request explicit owner GO for any TLS identity, one machine grant, private Sonar READ token, client mounts or R7 start. Real Sonar GET and live PENDING/Reject remain OPEN; Sonar POST remains NO-GO.


## Продолжение 2026-11-02 — corrected R7 scoped runtime preflight OWNER-REPORTED PASS

Owner returned the complete output from `Preflight-R7-P1-Scoped-Windows-ReadOnly-Resume-20261102.ps1` (SHA256 `07315249b5e7dade0aec85599dc9948fc7d64e31b3c68434d609c1222d33d8b9`). Reported PASS markers: Linux Docker Engine; exact scoped image pin; existing Repo running; A3 healthy; Repo workspace/trusted mount isolation; exact four existing R7 volume metadata; all four volumes unattached; previous volume/state acceptance reused; Docker-published ports and Windows TCP ports 19103/19104 available; final read-only preflight PASS.

The owner output explicitly confirms: Guard Preview NOT EXECUTED; credential provisioning NOT EXECUTED; live deployment NOT AUTHORIZED; containers started NONE; volume contents read NO; volume mutations NONE. This closes the corrected **read-only runtime preflight** only. It does not authorize R7 start, TLS/grant/token provisioning, client mounts, MCP registration or Sonar requests.

Guard sequencing: the project matrix records Repo1 Guard Preview as previously PASS; do not repeat it absent source/config change. Repo2 Guard Preview is a separate outstanding read-only check. The canonical `script-control-center` Git source has `Repo2DirectGuard.ps1` SHA256 `08ab2a7b3051e6899a47af8cd09fc2ffe6e560cd7638b8160d1b2c3a40402241`, pinned by the Repo2 quiet launcher; source documentation identifies it as the Repo2 Preview entrypoint and requires non-elevated Windows PowerShell. This is source-only until owner runs `-Mode Preview`; it must not be invoked with `-Mode Run`. The current `script-control-center` checkout is on `main` at `51498cd6dd955667b15d54299045f10f5b432346`; unrelated worktree changes exist, but the relevant guard/launcher/docs paths are clean. Do not pull, stage, commit, or alter those unrelated files as part of this R7 gate.

Next: perform only the separate Repo2 read-only Guard Preview against the owner's current Windows Git clone after verifying the clone/source and pinned SHA. If PASS, request a distinct explicit owner GO before any TLS1.3 identity, one machine grant, private Sonar READ token, client mounts or R7 start. Repo1 preview remains previously accepted. Real Sonar GET, live PENDING/Reject and Sonar POST remain OPEN/blocked.


## Продолжение 2026-11-02 — Repo2 read-only Guard Preview OWNER-REPORTED PASS

Owner executed the exact Repo2 source-pin + read-only Preview sequence from `C:\Users\alexa\Repos\script-control-center`. Reported markers: `REPO2_GUARD_SOURCE_PIN_PASS`; `FORTIS_REPO2_GUARD_PREVIEW_PASS`. The two target source/launcher paths were clean; guard SHA256 matched `08ab2a7b3051e6899a47af8cd09fc2ffe6e560cd7638b8160d1b2c3a40402241`; launcher contained the exact uppercase pin. Guard JSON: `Mode=Preview`, `Preflight=PASS`, `ConfigState=Pinned`, `ContainerIdMatched=True`, `LinuxUid=1000`, `DirectModuleHashVerified=True`, `NoWindowsProfileEdits=True`.

This closes the separate Repo2 read-only Preview gate. Together with the previously accepted Repo1 Preview, **Repo1 + Repo2 Guard Preview = OWNER-REPORTED PASS**. Repo2 was not restarted; no Windows profile edits or Docker/volume/config mutations were reported. This is not `-Mode Run`, not a deployment/cutover, and does not authorize R7 start or provisioning.

Next: obtain a separate explicit owner GO for the exact proposed minimal R7 trust provisioning (TLS1.3 server identity, one scoped machine grant, private Sonar READ token, and read-only client mounts), then review each action against the preserved four existing R7 volumes and existing Repo/A3 isolation. No provisioning or live deployment until that GO. Sonar GET/ASK and live Repo→R7 integration remain OPEN; Sonar POST remains blocked.


## Продолжение 2026-11-02 — минимальный R7 trusted provisioning design подготовлен (SOURCE-ONLY)

После owner-reported PASS corrected runtime preflight и Repo1/Repo2 Guard Preview подготовлены два source-only артефакта: fortis_approvals/deploy/compose-r7-p1-scoped.yaml (exact scoped image tag, pull_policy: never, no build/pull, fixed non-secret org/project, loopback-only ports, four existing external volumes) и R7-P1-MINIMAL-TRUSTED-PROVISIONING-20261102.md (owner GO gates, TLS/grant/token/client mount and live READ/ASK sequence). Static design tests test_r7_p1_trusted_provisioning_static.py 7/7 PASS.

Source review found a real UID contract: R7 server private grant must be UID 10001/mode 0600; repo_sonar_tools._grant_from_file() requires the client grant owner to be Repo UID 1000/mode 0600. Therefore do not mount one server grant file into both. Proposed new fortis-r7-client volume (NOT CREATED) will contain only the client grant-copy + public CA certificate; no Sonar token, server private key, R7 state or owner DB. The four existing prepared volumes remain unchanged.

Adding the client mount to the already-running fortis-repo-test requires owner-reviewed recreation with exact configuration preservation and proven rollback; separate explicit GO is mandatory. No second Repo/Tunnel/MCP architecture. The shared Repo UID 1000 means this one machine grant is usable by any process in that container; it is a single-actor pilot boundary, not per-AI identity or multi-agent isolation.

The existing unpinned compose-r7-unified-read-ask.yaml uses :local + build and must not be used for this pilot. The new Compose is source-only and not executed. Owner WebAuthn invitation must be issued only after first R7 start because pre-creating owner.sqlite before _fresh_r7_state() marks the state root would make the strict fresh-state check fail.

No fifth volume created, no credentials/TLS provisioned, no R7/Repo container started or changed, no Sonar request, no Compose deployment. Separate GO-1 (secret provisioning), GO-2 (R7 start + owner enrollment), GO-3 (Repo recreate/client mount), GO-4 (live READ + ASK/Reject) are defined. Sonar POST and Approve remain blocked; P1-02 AI workflow dispatch and P1-C actual Issue mutation remain separate OPEN/NO-GO gates.


## Продолжение 2026-11-02 — pinned Compose review handoff / remaining pre-provision checks

A new source-only P1 Compose file was prepared and transferred to the Windows handoff area byte-for-byte: SHA256 115e283aaee3a6771f0a879008f4048c03150a7422f6b03757fb5105f6c4a5be. It pins the scoped owner-audited image tag, sets pull_policy never, contains no build stanza or secret environment, pins only EU + alexpastukhh + AlexPastukhh_obs-planning-docs, publishes only 19103/19104 on host loopback, and mounts only the four existing external server volumes (state RW; identity/grant/token RO). It does not include the proposed Repo-only client volume.

The Linux Fortis Repo environment has no Docker CLI, Ruby/YAML parser or yq, so Compose parser validation was not performed there. The next safe owner-side check is only `docker compose --project-name fortis-r7-p1 -f compose-r7-p1-scoped.yaml config --quiet` after SHA-verified docker cp to Windows, plus local image tag→full ID check. This config-only check does not start containers or create networks/volumes. Do not run `up`.

Additional source review caveats recorded in the provisioning runbook: (1) after GO-1 creates the fifth `fortis-r7-client` volume, do not rerun the previous four-volume preflight (it intentionally rejects unexpected R7 volume names); a separate five-volume metadata verifier is required. (2) The current audited image's shared OwnerPortal hardcodes the `G4 READ ONLY` heading when read_only_banner=True, and R7 enables that flag. This is cosmetic and does not alter auth/ASK/Reject enforcement, but it mislabels the R7 portal; disclose/accept it or request a source fix and new image digest/build/audit before owner enrollment.

No secret, certificate, grant, token or fifth volume was created. No existing volume content was read or changed. No container was started/recreated, no Sonar request made, no Docker deployment executed. Current status remains NOT AUTHORIZED.


Validation after the source-only Compose/runbook update (2026-11-02): `test_r7_p1_trusted_provisioning_static.py` **7/7 PASS**; `tools/rdg-docs-audit.py` **PASS** (`285` Markdown files, `18` normative, `64` archived, `203` immutable snapshots, `594` checked links); pinned Compose source and Workfiles copy byte-identical at SHA256 `115e283aaee3a6771f0a879008f4048c03150a7422f6b03757fb5105f6c4a5be`. Docker CLI and YAML parser are unavailable in Linux Repo container, so owner-side Windows `docker compose config --quiet` remains OPEN. No Docker/volume/container/secret/network/Sonar mutation was performed.


## Windows Compose validation evidence — owner-reported PASS (2026-11-02)

Owner supplied the full PowerShell transcript for the exact file `compose-r7-p1-scoped-20261102.yaml`: `docker inspect fortis-repo-test` reported running; `docker cp` succeeded from the prepared Repo Workfiles path; local SHA256 matched `115e283aaee3a6771f0a879008f4048c03150a7422f6b03757fb5105f6c4a5be`; local tag resolved to exact expected image ID `sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024f2c062bac0a18ce4`; and `docker compose --project-name fortis-r7-p1 -f <file> config --quiet` exited 0 and printed `FORTIS_R7_P1_COMPOSE_CONFIG_PASS`. Owner explicitly printed `FORTIS_R7_P1_DEPLOYMENT=NOT_AUTHORIZED`.

This closes the Windows Compose syntax/configuration check only. It does not authorize or evidence `compose up`, container/network/volume creation, secret provisioning, WebAuthn enrollment, Repo recreate/mount, or Sonar requests. No GO-1/GO-2/GO-3/GO-4 has been granted by this transcript. The next irreversible boundary remains separate explicit owner GO-1 for trusted secret provisioning; until then all four existing volumes remain untouched and the proposed fifth client volume remains uncreated.
