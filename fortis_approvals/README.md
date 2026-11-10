# Fortis Approvals — source map and operating status

> **СТАТУС: ДЕЙСТВУЮЩИЙ SOURCE ENTRY POINT.** Текущая система — live R7 Unified Gateway для одного AI actor / одного SonarCloud project. Нормативное описание состояния: [Fortis current state](../docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md).

## Что работает сейчас

- Fortis Repo обращается к одному R7 Gateway по фиксированному TLS 1.3 machine ingress.
- R7 содержит Core, policy, Owner Portal/WebAuthn, durable request state и Sonar adapter. Approval application **не размещено в Fortis Repo**.
- Четыре typed Sonar READ операции, одна typed `accept_issue` ASK proposal и чтение request status работают из Repo.
- Owner WebAuthn Approve запускает проверенную Core execution path; для Issue `AaGC4d7SJxEkuf26a_Wh` подтверждены `EXECUTED` и независимый Sonar `ACCEPTED`. Отдельный owner Reject для Issue `AaGC4d7SJxEkuf26a_Wg` дал `REJECTED` без adapter dispatch. Подробности и Request IDs: [live evidence](evidence/FORTIS-SONAR-LIVE-E2E-20261103.md).
- P2 image `sha256:e751f6ca0cfe6ce290cf580de2f243071ee1f3e681baa8827c6cea41a16fa402` прошёл owner-reported Windows build и installed-source audit; deployment/health также owner-reported. Live Repo→R7→Sonar операции подтверждены отдельно.

## Один рабочий сценарий

Из Fortis Repo:

```sh
cd /workspace/repos/rd-graphs
python3 -m fortis_approvals.sonar_review_scenario review \
  --issue-key ISSUE_KEY \
  --reason "Обоснование для owner review"
```

Проверка результата:

```sh
python3 -m fortis_approvals.sonar_review_scenario status \
  --request-id REQUEST_UUID
```

`review` читает закреплённый project, Issues, Quality Gate и точную Issue, затем создаёт одну заявку `PENDING`. Он не запускает новый Sonar analysis, не делает Approve и не отправляет Sonar mutation. Approve/Reject выполняет владелец в R7 Owner Portal.

### Что именно вызывается

| Слой | Разрешённые операции | Фактический маршрут |
| --- | --- | --- |
| Repo client → R7 | `sonar.list_projects`, `sonar.list_issues`, `sonar.get_issue`, `sonar.get_quality_gate` | `POST /v1/reads` с typed envelope |
| Repo client → R7 | `sonar.propose_accept_issue` | `POST /v1/actions`; результатом является `PENDING`, не Sonar POST |
| Repo client → R7 | `approvals.request_status` | `GET /v1/requests/{requestId}` |
| R7 → SonarCloud | READ | GET-only allowlist для projects/issues/quality gate |
| R7 → SonarCloud | WRITE | Только после owner WebAuthn: один `POST .../do_transition` с `accept`, затем GET readback |

### Approval state machine

`PENDING` — frozen preview и fingerprint ждут решения владельца. `REJECTED` завершает заявку без adapter dispatch. `APPROVED` проходит final re-read/policy/grant checks, затем `DISPATCHED` и `EXECUTED` после подтверждённого Sonar readback. Изменившийся preview/policy получает `STALE` или `EXPIRED`; неопределённый удалённый результат не повторяется вслепую.

### Где читать документацию

- Нормативное состояние и архитектура: `docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md`.
- Карта исходников и команды: этот README.
- Live request/readback evidence: `evidence/FORTIS-SONAR-LIVE-E2E-20261103.md`.
- Deployment/image/volume references: `deploy/README.md` и `deploy/compose-r7-p2-20261103.yaml`.
- Старые provisioning/cutover/source-review документы — архивные указатели, не runbook.

## Архитектурные entry points

| Файл | Назначение |
| --- | --- |
| `core.py` | Durable request lifecycle, policy, owner decision, execution и reconciliation |
| `owner_auth.py` | WebAuthn credential/challenge verification и owner sessions |
| `owner_portal.py` | Owner Pending/History UI и decision routes |
| `r7_unified_server.py` / `r7_unified_candidate.py` | Единый R7 runtime и composition |
| `repo_ingress.py` | Authenticated machine ingress и typed route dispatch |
| `repo_action_contract.py` | Закрытый schema/allowlist machine intents |
| `repo_sonar_tools.py` | Repo-side TLS client; только четыре READ, ASK proposal и request status |
| `sonar_read.py` | Независимый GET-only Sonar read adapter и публичная projection |
| `sonar.py` | Typed SonarCloud adapter; только разрешённые endpoints и `accept_issue` |
| `sonar_review_scenario.py` | Однокомандный READ/report → ASK сценарий |

## Действующие ограничения

- Один actor, одна организация `alexpastukhh`, один project `AlexPastukhh_obs-planning-docs`.
- Единственная разрешённая Sonar mutation — `accept_issue` / transition `accept`; каждая Issue требует отдельного owner WebAuthn Approve.
- Нет bulk/arbitrary Sonar writes, произвольных URL/methods, token exposure или AI owner routes.
- Вызов доступен AI в активной сессии через существующий Fortis Repo process tool. Фоновый scheduler, autonomous issue monitor и AI-triggered GitHub workflow dispatch не реализованы.
- Machine grant доступен процессам общего Repo container; это не multi-agent isolation.
- Sonar Quality Gate report относится к `CURRENT_DEFAULT_BRANCH`; PR/SHA binding не подтверждён.

## Тесты

```sh
python3 -B -m unittest discover -s fortis_approvals/tests -p 'test_r7_unified_candidate.py' -v
python3 -B -m unittest discover -s fortis_approvals/tests -p 'test_r7_p2_webauthn_execute_static.py' -v
python3 -B -m unittest discover -s fortis_approvals/tests -p 'test_repo_sonar_tools.py' -v
python3 -B -m unittest discover -s fortis_approvals/tests -p 'test_sonar_review_scenario.py' -v
python3 -B -m unittest discover -s fortis_approvals/tests -p 'test_sonar_read_adapter.py' -v
```

Проверенные адресные suites в Repo: Core 28/28, R7 P2 static 4/4, Repo typed client 12/12, Sonar review scenario 7/7, Sonar READ adapter 15/15, Gateway 6/6, Owner Portal input 7/7; `compileall` PASS. Offline dependency gap: `test_r7_unified_candidate.py` не загружается из-за отсутствующего `cryptography`; в `test_sonar.py` 21 из 22 тестов проходят, один test loader завершается из-за отсутствующего `fido2`. Эти две ошибки окружения не отменяют отдельное live owner WebAuthn Approve → Sonar ACCEPTED evidence, но полный pinned WebAuthn/HTTPS offline suite в Repo не объявляется PASS.

## Старые артефакты

`deploy/` содержит current P2 references и исторические G2/G4/R5/A3/P1 scripts. **Не запускать** старые provisioning, preflight, cutover, build или rollback scripts как часть обычной работы. Одноразовые GO-1/GO-2/GO-3 операции завершены. Исторические документы сохранены в `archive/20261103-pre-live-doc-cleanup/`; краткий указатель deployment-файлов: [deploy README](deploy/README.md).
