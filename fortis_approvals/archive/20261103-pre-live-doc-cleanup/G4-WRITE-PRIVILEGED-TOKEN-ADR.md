# Fortis Secure Gateway / Sonar privileged token — ACTIVE owner architecture

**Решение владельца от 2026-10-31, последнее по приоритету. STATUS: DESIGN, NO REAL WRITE AUTHORIZATION.** **Актуальный срез 2026-11-01:** A4 real Repo→Windows A3 TLS/owner WebAuthn/synthetic PASS, отдельный G4 Sonar GET/ASK/Reject/readback owner-reported PASS; **нет unified Repo-callable Sonar READ/real Sonar POST**. Следующая работа — Sonar READ source/offline без токена. В основном плане §12 владелец пометил проверенную процедуру TLS replacement и выдачу/отзыв machine access **DEFERRED до production**, не считать их уже принятыми. Главный нормативный источник — [`FORTIS-APPROVALS-SECURE-DEVELOPMENT.md`](../../docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md), §0–1 и §12–14. Этот ADR описывает **один** доверенный Fortis-контейнер, а не два. Любые ранние ссылки на обязательные отдельный Approvals-контейнер и token-bearing `Trusted Executor` **отменены**. Лабораторные worker/IPC-процессы — исторические эксперименты и не обязательный архитектурный gate.

## Что именно должно работать

```text
AI в Fortis Repo (не доверен; service tokens и owner proof отсутствуют)
  → typed intent + отдельно выданный ограниченный caller grant
  → ОДИН доверенный Fortis Secure Gateway Docker на Fortis_M
      1. Authenticate caller / allowlisted operation + target
      2. Trusted policy DENY / ALLOW / ASK (по текущему запросу)
      3. ASK? frozen pending → owner WebAuthn Approve/Reject
         ALLOW? без ожидания владельца
      4. Обе разрешённые ветки → ОДИН Core.execute + typed service adapter
      5. Адаптер берет секрет из локального owner-only vault, ЕСЛИ он нужен
      6. Fixed API call / preflight / durable dispatch / GET readback / audit
  → SonarCloud / RDG / GitHub / другие разрешённые системы
```

**Общая матрица четырёх комбинаций** (секрет нужен/не нужен × ASK нужен/не нужен) — в [основном плане §0](../../docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md). Для Sonar READ это секрет без ASK; для `accept_issue` — секрет и обязательный ASK. ADR не вводит отдельной политики и не требует второго исполнителя.

**Секреты:** сервисные credentials с широкими правами находятся внутри **того же доверенного контейнера**, в owner-managed private volume/secret file, не в Repo, Git, JSON, логах, HTTP response или owner browser JS. Fortis сам выбирает и применяет токен по фиксированным adapter scope/operation. У Fortis Repo свой restricted ingress grant **не равный** SonarCloud token. Owner browser имеет **другую** независимую WebAuthn/same-origin/session/CSRF авторизацию. Раздельные machine и owner маршруты могут обслуживаться одним контейнером; **машинный caller никогда не получает возможность вызвать owner_decide, поменять policy, прочесть secret или произвольный `POST URL`**. Secret volume недоступен AI mounts, а Docker socket/host admin не предоставляются Repo.

**Широкие права Sonar — осознанная архитектура:** владелец не требует mandatory narrow-scope Sonar PAT как условие Fortis. Fortis ограничивает действия собственного API по trusted policy. Скомпрометированный контейнер, Windows/Docker admin, backup, memory dump или утечка самого токена **полностью обходят Fortis ASK** и имеют весь blast radius действительных upstream прав, возможно включая другие организации. Это не устранено одним контейнером; owner bootstrap/hardening, доступ к volume, ограничение egress, token rotation/revocation и incident runbook — необходимые предрелизные меры. Разделение на два контейнера можно рассмотреть позже по новому конкретному решению, но **сейчас не добавлять второй обязательный контейнер, IPC или duplicate gateway**.

**Read-only preflight before ASK is allowed:** a trusted in-container Sonar adapter may use the secret for scoped GET/current-state preview before requesting owner approval, but it cannot send the mutating Sonar POST until the exact verified ASK approval is committed. This is a read/write effect distinction, not a second process or token service.

## Sonar `accept_issue`: отдельная строгая политика ASK

`READ` SonarCloud может проходить сразу по trusted `ALLOW`, используя внутренний токен; нельзя выдавать token Repo. `accept_issue` **в текущей модели всегда ASK**: frozen exact Issue key/project/transition, server-derived normalized SHA/current state, owner preview, verified owner session/WebAuthn, recheck immediately before dispatch, durable reservation/one real attempt at most, GET readback/receipt. `DENY`/Reject не исполняются. Настоящий Sonar endpoint не предоставляет атомарный GET→POST CAS; Race между GET и POST и status `UNCERTAIN` (lost response, 429 и т.д.) остаются обязательными открытыми рисками. Не слать повторно POST при неизвестном результате. Owner consent на архитектуру **не является** разрешением реального WRITE/конкретной Issue.

**Текущая Windows G4:** owner-reported отдельная test instance `http://localhost:18991`, GET/ASK/Reject PASS, POST и Approve заблокированы; G2 `http://localhost:18990` — отдельная synthetic test instance. Обе пока не объединять, не копировать G4 token/SQLite/passkey в Repo или новый image, не менять Docker/volumes без нового разрешения. Existing G4 содержит UI и READ-токен в одном контейнере — это не ошибка архитектуры, но для расширения до WRITE всё ещё необходимы строгие endpoint/owner guards и проверенная доверенная установка.

## Перед реальным WRITE: необходимые проверки, а не новая архитектура

| Проверка | Статус |
| --- | --- |
| Ограниченный Repo→один Fortis typed ingress; owner routes/credential store недоступны machine actor; связь/TLS/auth/ACL доказана | **A4 SYNTHETIC + A3 WINDOWS AUDIT PASS:** Repo→Windows A3 TLS1.3/hostname/grant scoped ALLOW/ASK/WebAuthn + owner/route negatives и read-only mount/ACL PASS. **PRODUCTION TRUST OPEN:** independent source/certificate admission, Sonar secret store и machine revoke. Не считать старый G4 интегрированным. |
| Secret volume доступен только Fortis/доверенному host admin, не Repo; audited grants/host/rootfs/mounts, backup, rotate/revoke | OPEN для нового единого WRITE runtime |
| Trusted policy `ASK` cannot be bypassed for Sonar mutation; strong owner proof exact ID/fingerprint/decision | PARTIAL offline fake; реальный POST невозможен в текущем G4 |
| Только фиксированные typed ops, grants, service scope, preflight, durable one-shot, readback, replay/UNCERTAIN/restart | PARTIAL synthetic; prod not audited |
| Документирован Sonar GET→POST non-atomic race и влияние на Issue/Quality Gate | OPEN before owner release |
| Отдельно обозначенная disposable Issue, однократная свежая owner WebAuthn авторизация на конкретный POST, readback/rollback | **НЕ ДАНО** |

## Подробные источники

- [`FORTIS-REPO-ACTION-CONTRACT-V1.md`](FORTIS-REPO-ACTION-CONTRACT-V1.md) — форма caller intent, auth/grant и Core conversion.
- [`FORTIS-REPO-INGRESS-GATE-V1.md`](FORTIS-REPO-INGRESS-GATE-V1.md) — WSGI API и ограничения source-only tests.
- [`UNIFIED-APPROVALS-CUTOVER-PLAN.md`](UNIFIED-APPROVALS-CUTOVER-PLAN.md) — будущая **одноконтейнерная** доверенная установка с сохранением старых G2/G4.
- [`G4-WRITE-LAB-ACCEPTANCE.md`](G4-WRITE-LAB-ACCEPTANCE.md) — историческое **fake-worker** испытание, не production requirement и не real POST proof.
- [`G4-WRITE-SECURITY-REVIEW.md`](G4-WRITE-SECURITY-REVIEW.md) — исходный обзор рисков (исторический); старые рекомендации mandatory executor process/container и mandatory narrow-scope Sonar credential **SUPERSEDED**, читать лишь для угроз и тестов.

**Вердикт:** один Fortis контейнер хранит секреты и исполняет запросы; ASK встроен и срабатывает только если trusted policy требует. **Нет второго обязательного Executor-контейнера или обязательного IPC. Real Sonar WRITE NO-GO.**
