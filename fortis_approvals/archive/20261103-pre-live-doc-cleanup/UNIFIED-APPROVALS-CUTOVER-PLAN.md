# Один доверенный контейнер Fortis: безопасный переход с G2 и G4

> **Исторический срез 2026-10-31.** Утверждения ниже вида «Repo→Windows не работает», «только offline», «A3 не развернут» и старые числа тестов описывают состояние **на тот момент**, а не актуальный факт. **2026-11-01: A4 synthetic Repo→Windows A3 TLS/ASK/ALLOW/Reject и Windows ACL/status PASS; production admission и Sonar READ в едином Fortis OPEN.** Действующие статусы/задачи — в [основном плане §12–14](../../docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md). Owner решил **отложить** процедуры ручной замены TLS и выдачи/отзыва machine access до production admission; ближайшая работа Sonar READ offline без реального токена.


**OWNER DECISION 2026-10-31 — TARGET ONE CONTAINER. DESIGN / NOT DEPLOYED.** Нормативная архитектура и задачи — [`Fortis master plan`](../../docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md), §0–1, §12–14. Это **не** инструкция трогать живые контейнеры, секреты, Docker, SQLite или WebAuthn. Прежняя гипотеза «Approvals + отдельный token-bearing Trusted Executor» отменена в пользу **одного доверенного Fortis Secure Gateway** на Fortis_M. Если впоследствии появится подтверждённый риск, второй контейнер можно обсудить как **новое** решение; сейчас не нужен IPC/отдельная queue/отдельный UI.

## Целевая конфигурация

Один owner-managed Docker контейнер: restricted AI/machine ingress → actor grants / trusted server-side `ALLOW/ASK/DENY` → owner WebAuthn Pending/History (только для ASK) → **тот же Core.execute** → typed adapters → secret resolver/owner-only volume **только если нужен токен** → upstream action + readback/audit/uncertain recovery. Owner UI и client ingress — разные **авторизованные маршруты**, но один контейнер; owner endpoints недоступны machine actor. Не создавать generic HTTP POST proxy, shell executor или отдельный service daemon только ради `ALLOW/ASK`. Все действия с секретом **или потенциальным ASK** маршрутизировать сюда, независимо друг от друга. Для RDG будущий G3 обязан закрыть обход через прямой штатный writer, не добавляя отдельный writer.

**Четыре комбинации «нужен секрет / нужен ASK» и точная логика для одной операции зафиксированы ровно в одном нормативном месте** — [master plan §0](../../docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md). Текущий cutover реализует их в одной установленной системе, не вводя дополнительные политики и не дублируя writer.

## Текущая реальность и незавершённые проверки

- **Fortis Repo:** Linux Docker, доступ к source, но **не** Windows trusted host/owner secret volume. `RepoIntentBroker`, `RepoIngress` и Core в Python уже есть; synthetic 208/208 Python и 3/3 UI по последнему отчёту другого чата, повторять после любых code changes. Временный local HTTP test внутри Repo **не подтверждает** маршрут на Windows.
- **Windows Fortis_M:** G2 `http://localhost:18990` (synthetic owner WebAuthn) и G4 `http://localhost:18991` (Sonar EU READ, ASK/Reject, NO POST) — независимые owner-reported running **test** candidates с разными SQLite, token volume, owner WebAuthn RP origin. Не переносить их state/secret/passkey автоматически; разные `localhost:port` WebAuthn origins несовместимы без отдельного owner-controlled enrollment/migration.
- **A2 настоящий сетевой маршрут:** из Repo `host.docker.internal` DNS сообщил Docker Desktop alias `192.168.65.254`, `gateway.docker.internal` `192.168.65.1` — это **не** TCP/TLS acceptance, не доказательство identity Fortis_M и не гарантия доступности `localhost:18990/18991` из Repo. Инструмент G2 Host не работает; использовать **Fortis Repo** и отдельную согласованную owner-side read-only проверку, не сканировать случайные порты.
- **Secret:** owner-only G4 token volume сейчас содержит plaintext token at rest. Его нельзя монтировать в Repo, включать в ZIP/CI или автоматически присоединять к новому Fortis. Проект сознательно допускает широкие права Sonar; утечка токена обходит ASK даже в правильном Fortis.

## Очередь без лишних слоёв

1. **A0/A1:** source/core/ingress и Linux Repo discovery — проверены в синтетике. Зафиксирован A2 частичный DNS/topology; дальнейшее решение — живой маршрут.
2. **A2:** владелец read-only проверяет Windows Fortis_M (текущие 18990/18991 и свободный тестовый порт **19092**, без изменений текущих контейнеров). После согласования только одноразовая loopback TCP-проверка `Repo → host.docker.internal:19092`, отдельно TLS и host identity. В новом чате **не просить выбирать иной хост**: Fortis_M уже выбран. Это не production deployment.
3. **A3:** развернуть один отдельно установленный owner-controlled **тестовый Fortis-контейнер** на свободном порту/отдельном state, используя **существующие** `repo_action_contract.py`, `repo_ingress.py`, `core.py`, `owner_portal.py`; machine/owner routes изолированы auth/TLS/ACL; **никаких Sonar credentials на этапе синтетики**. Это не должен быть второй постоянный продукт и не должен менять G2/G4.
4. **A4:** настоящий запрос из Repo → новый Fortis с synthetic `ALLOW` и `ASK` + owner WebAuthn browser → **тот же Core.execute** → status, readback, audit; deny/reject/forged owner/replay/stale fail. Без direct token/proxy/owner-route access.
5. **Sonar in SAME Fortis container:** только после A4 и отдельного owner-controlled provisioning добавить allowlisted Sonar READ и внешний service token **в его private volume**, без Repo exposure. `accept_issue` оставлять mandatory ASK, исполнение только после exact new owner authorization и отдельной release review; никаких live POST по этому плану.
6. **Cutover:** после owner acceptance, backed-up legacy G2/G4 state, выбранного нового WebAuthn origin, owner enrollment/readback/rollback владелец отдельно решает, что делать со старыми тестовыми контейнерами. **Не делать `docker compose down -v`, silent passkey merge, token copy или автоматический сервисный restart.**
7. **Далее глобальный порядок:** D1 PR + GitHub-hosted Actions/Sonar → D2 SHA/run/attempt/analysis provenance → D3 Windows independent Importer/AV + mandatory owner RUN → D4 контролируемый отказ от старого Repo ZIP→Windows updater → после этого G3 RDG block FREE/ASK и Navigation Bridge.

## Риски и acceptance

- Если machine API позволяет указать URL/HTTP method/owner/secret/`approved=true` или прочитать любой credential — **не принимать**.
- Если Repo через mounts/socket/admin API может управлять Fortis policy, secret store, container runtime или owner state — **не принимать**.
- Если `ALLOW` ходит отдельным writer, `ASK` повторяется AI после approve или `ASK` без секрета игнорируется — **не принимать**.
- Если для успешной работы требуется установить второй отдельный token-executor container или IPC **только ради архитектуры**, это отклонение от текущего owner решения, не gate.
- Если нет owner-proven WebAuthn, точного frozen request, durable dispatch/one attempt, stale/preflight/receipt/readback/`UNCERTAIN` → real WRITE **NO-GO**. При сетевых/secret gate проблемах остановиться и отчитаться, не обходить через Repo.
- Секрет с широкими правами в одном Fortis — явный tradeoff: компрометация Fortis/Windows/Docker admin или token theft обходит Fortis ASK. Owner подтвердил **целевую топологию**, но **не дал** разрешение на реальный Sonar POST или отказ от конкретных защитных проверок.

**Это актуальный одно-контейнерный план; прежние ADR/архивные worker-lab документы с отдельным executor — только для истории угроз, не для выбора новой архитектуры.**
