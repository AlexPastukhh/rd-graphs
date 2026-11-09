# Fortis — передача совершенно новому чату

**Срез: 2026-10-31.** Это **маршрут чтения**, не второй план. Главный источник архитектуры, очереди и приёмки — [`FORTIS-APPROVALS-SECURE-DEVELOPMENT.md`](../../guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md), **§0–1, §12–14**. До действий перепроверить Git, доступную сеть и профильные исходники: этот файл не доказывает, что Windows или GitHub доступны сейчас.

## Что строим

**ОДИН доверенный контейнер Fortis на существующем Windows Fortis_M.** Внутри: restricted Repo ingress, серверные политики `ALLOW/ASK/DENY`, owner WebAuthn/очередь, owner-only секреты, **один** `Core.execute`/typed adapters, readback и журнал. Обязательный второй Executor-контейнер/IPC **отменён владельцем**; G2 и G4 — только раздельные тестовые экземпляры.

Любое действие ИИ, для которого **нужен секрет ИЛИ потенциально нужен ASK**, должно идти через Fortis. Эти признаки независимы: secret+ALLOW, secret+ASK, ASK без секрета, ALLOW без секрета. `DENY`/Reject не исполняются; approved ASK и ALLOW используют **один и тот же** исполнитель. Сервер сам выбирает политику и токен; Repo не передаёт `approved`, owner proof, raw URL/method/secret и не имеет доступа к owner API/Docker socket. Read-only preview может использовать токен **до** ASK; изменяющий эффект — только после точного подтверждения. **Полная матрица и риски описаны один раз — в основном плане §0.**

Один контейнер **не** изолирует секреты от компрометации собственного Fortis-процесса или Windows/Docker admin: утёкший широкий Sonar bearer обходит Fortis ASK. Для реального WRITE обязательны audit token custody, независимая browser/machine auth, allowlisted typed ops, one-shot/stale/UNCERTAIN/readback; реальный Sonar POST **не разрешён**.

## Сейчас — только то, чего недостаточно увидеть из кода

- **Windows, по сообщению владельца:** G2 `localhost:18990` (synthetic Approvals), G4 `localhost:18991` (SonarCloud READ/ASK/Reject, проверка состояния Issue). **Две тестовые установки, не один принятый Fortis; Sonar Approve/POST отключён.** В этой сессии Windows непосредственно не проверялся.
- **Fortis Repo, проверено:** общий Core, строгий Repo intent/ingress и synthetic кандидат. **208/208 Python, 3/3 UI PASS** (локальные offline tests); localhost HTTP smoke — внутри Linux Repo, **не** связь с Fortis_M.
- **Не готово:** Repo→Windows TCP/TLS/identity, A3/A4 реальный end-to-end ALLOW/ASK, единый token-bearing Fortis, Repo-callable Sonar READ с разрешённым ответом (пока только `{requestId,state}`), Sonar WRITE, принятый GitHub→Windows pipeline и RDG G3.
- **Сеть:** Fortis_M уже выбран; `host.docker.internal` разрешался внутри Repo, но это **не доказательство TCP/TLS**. G2 Host connector не работает. **Первый открытый пункт — A2**, подробности в master plan §12.

## Запланировано — порядок и условия

1. **A2:** только согласованная с владельцем проверка маршрута Repo Linux → Fortis_M и отдельного тестового порта; не менять G2/G4. DNS ≠ TCP/TLS/host authenticity.
2. **A3–A4:** установить **один** отдельный синтетический тестовый Fortis candidate с собственными state/origin и защищённым машинным входом; реальный Repo `ALLOW` сразу, `ASK` → WebAuthn → тот же `Core.execute`; подтвердить deny/reject/replay/readback и недоступность owner routes. Существующие `Core`, `RepoIntentBroker`, `RepoIngress`, `repo_synthetic_candidate.py` переиспользовать; **не строить ещё один gateway**.
3. **Sonar в этом же Fortis:** owner-only secret store, scoped READ с полезным **отфильтрованным результатом для ИИ** (сегодня нет), обязательный ASK на `accept_issue`, one-shot и readback. Утёкший токен обходит ASK; **real POST только после отдельного exact owner authorization для disposable Issue**.
4. **D1 → D2 → D3 → D4:** ограниченная GitHub identity/typed operations → PR и **реальные** GitHub-hosted Actions/tests/Sonar checks → проверка PR/run/attempt/analysis/точного final SHA → независимый Windows importer, quarantine/AV/admission, **обязательный owner RUN** → проверенный RDG/Fortis update и контролируемое выключение старого ZIP→`Update-RDG.ps1 -Watch`. `IMPORT` может быть `ALLOW` после всех проверок либо `ASK` по политике; green CI **не** даёт права RUN. AI→GitHub операции с секретом/ASK тоже должны проходить Fortis либо отдельно утверждённый владельцем защищённый канал; CI runner/job secrets — отдельная trust boundary.
5. **Только после D1–D4 — G3 RDG:** `FREE/ASK` на блоки (без block DENY), AI FREE→ASK непосредственно, ASK→FREE через owner, одна pending на атомарную запись; после approval **тот же RDG Application/prepare/commit/CAS writer**, без bypass через Gateway/Agent/Helper. Navigation Bridge к нужной открытой вкладке/сущности и обратно. Далее прочая RDG product work через принятый secure pipeline.

**Никаких новых параллельных планов:** статус A0–A4 обновлять в master plan §12; текущий срез — §13; спецификацию и acceptance D1–D4 — §7–10, RDG G3 — §5. Исторические G2/G4 записи и fake split-worker experiments не задают будущую топологию.

## Где читать дальше

| Нужна информация | Читай |
| --- | --- |
| Правила Git и карта проекта | [`AGENTS.md`](../../../AGENTS.md), [`README.md`](../../../README.md), [`docs/README.md`](../../README.md) |
| Единственная целевая архитектура, статус, план и A2 | [Основной Fortis-план, §0–1 и §12–14](../../guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md) |
| Core / WebAuthn / Repo API | [`fortis_approvals/README.md`](../../../fortis_approvals/README.md), [`core.py`](../../../fortis_approvals/core.py), [`repo_action_contract.py`](../../../fortis_approvals/repo_action_contract.py), [`repo_ingress.py`](../../../fortis_approvals/repo_ingress.py), [`repo_synthetic_candidate.py`](../../../fortis_approvals/repo_synthetic_candidate.py), [`owner_portal.py`](../../../fortis_approvals/owner_portal.py) |
| Входной контракт и ограничения тестов | [`FORTIS-REPO-ACTION-CONTRACT-V1.md`](../../../fortis_approvals/deploy/FORTIS-REPO-ACTION-CONTRACT-V1.md), [`FORTIS-REPO-INGRESS-GATE-V1.md`](../../../fortis_approvals/deploy/FORTIS-REPO-INGRESS-GATE-V1.md) |
| Sonar credentials / переход с G2/G4 | [`G4-WRITE-PRIVILEGED-TOKEN-ADR.md`](../../../fortis_approvals/deploy/G4-WRITE-PRIVILEGED-TOKEN-ADR.md), [`UNIFIED-APPROVALS-CUTOVER-PLAN.md`](../../../fortis_approvals/deploy/UNIFIED-APPROVALS-CUTOVER-PLAN.md), [`sonar.py`](../../../fortis_approvals/sonar.py) |
| GitHub Actions → Windows | Основной план §7–10, [`.github/workflows/rdg-ci.yml`](../../../.github/workflows/rdg-ci.yml), [`tools/rdg-ci.py`](../../../tools/rdg-ci.py), [`Update-RDG.ps1`](../../../deploy/rdg-server/Update-RDG.ps1) |
| RDG позже | [`RDG-CURRENT-STATE.md`](../../guides/RDG-CURRENT-STATE.md), [`RDG-DEVELOPMENT-PLAN.md`](../../guides/RDG-DEVELOPMENT-PLAN.md), [`RDG-ACTIVE-CONTRACT.md`](../../guides/RDG-ACTIVE-CONTRACT.md), [`RDG-OPERATIONS.md`](../../guides/RDG-OPERATIONS.md) |
| Старые отчёты — только по необходимости | [Handoff 2026-10-30](../fortis-approvals-secure-dev-20261030/HANDOFF.md), [`G4-WRITE-LAB-ACCEPTANCE.md`](../../../fortis_approvals/deploy/G4-WRITE-LAB-ACCEPTANCE.md) |

## Первая инструкция новому чату

> Продолжай Fortis через `/workspace/repos/rd-graphs` (Fortis Repo). Прочитай этот handoff, **основной план §0–1 и §12–14**, `AGENTS.md`; проверь `pwd`, `git status --short`, `git diff --cached --binary | sha256sum` и доступные инструменты. Репозиторий сильно dirty; **не** stage/commit/reset/clean. Цель — **один** доверенный Fortis-контейнер с секретами и встроенными Approvals, не два обязательных контейнера. Начни с **A2**: безопасная проверка Repo→Fortis_M сети с разрешения владельца; G2/G4/SQLite/WebAuthn/токены и работающий RDG не трогай. Никаких реальных Sonar POST без отдельного exact разрешения. Далее A3–A4 → Sonar → D1–D4 GitHub Actions/Windows → G3 RDG. Source PASS не считать live Windows/GitHub PASS. Не добавляй новые фреймворки или параллельную документацию.

**Тесты для воспроизведения:** `cd /workspace/repos/rd-graphs`; `/workspace/repo/.rdg-webauthn-venv/bin/python -B -m unittest discover -s fortis_approvals/tests -q`; `node --test fortis_approvals/tests/ui.test.cjs`; `python3 -B tools/rdg-docs-audit.py`. Путь `/workspace/repo/Workfiles` — экспорт, не Git root. GitHub workflow `.github/workflows/rdg-ci.yml` локально untracked; это **не** доказательство remote Actions run/required checks.
