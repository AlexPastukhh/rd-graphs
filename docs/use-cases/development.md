# RDG — менять исходники и доказывать результат

> **СТАТУС: ДЕЙСТВУЮЩИЙ СЦЕНАРИЙ РАЗРАБОТКИ.** Только source, тесты и Docker release gate; это **не** инструкция по Windows-обновлению. Общая доставка и GitHub разрешения определяются Fortis `UC-CONT-002/003`; RDG не владеет копией их процесса.

## UC-RDG-005

**Когда:** разработчик или ИИ меняет модель, API, writer, Viewer, документацию либо исследует регрессию/производительность RDG.

**Цель:** получить проверяемое изменение в правильном владельце кода, не повредить чужую работу и не объявить Linux PASS полноценным пользовательским внедрением.

**Предпосылки:** выбран фактический checkout `/workspace/repos/rd-graphs`, прочитаны его [AGENTS](../../AGENTS.md) и [README](../../README.md); проверены `git status --short`, текущий профиль и активные нормативные документы по [DOCS-POLICY](../DOCS-POLICY.json). Не смешивать `/workspace/repo/Workfiles` с Git-репозиторием.

**Как:**

1. Найти правду по маршруту [функция → код → тест](../guides/RDG-FUNCTIONS-AND-TESTS.md), проверить [текущее состояние](../guides/RDG-CURRENT-STATE.md), [backlog](../../BACKLOG-IMPROVEMENTS.md), [контракт](../guides/RDG-ACTIVE-CONTRACT.md) и конкретную API/UI страницу. `candidate` и устаревший handoff не заменяют действующее правило.
2. Воспроизвести существующую проблему на **новом изолированном owner**, измерить до изменения. Не править живые процессы и не удалять volumes. Для зависимостей сохранить последовательные проверки, L1/L2, review, errors, events, provenance; для writes — CAS, receipt, recovery и параллельную изоляцию.
3. Внести минимальное изменение в настоящего владельца; добавить адресные позитивные, негативные, исходно-равные и (при UI) браузерные тесты. Проверить `git diff --check`, docs audit и затронутые наборы. При performance-работе измерить одинаковые до/после inputs, p50/p95, память/модель/транспорт по отдельности, не обещать Windows SLA по Docker.
4. Если изменился runtime, выполнить full gate из корня RDG:

   ```sh
   DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 PYTHONWARNINGS=ignore python3 -B tools/rdg-ci.py
   ```

   Затем сверить `status.json`, `ready.json`, source SHA256, ZIP SHA256 и содержимое release. `ready` относится **только** к этому проверенному срезу. Если изменена только документация — проверить её адресными docs-тестами; новый READY не следует из docs-only правки.
5. Зафиксировать **статус задачи** в [backlog](../../BACKLOG-IMPROVEMENTS.md) и обновить **владельца правила** (contract/API/Viewer/lenses), а UC только если поменялся повторяемый практический маршрут. При смене чата дать короткий handoff по [AGENTS](../../AGENTS.md) с точным SHA, PASS и ограничениями; не множить архивные планы.

**STOP / UNKNOWN:** работающий Git checkout dirty, неподтверждённые owners или несовместимые профили, неправильно выбранная модель, отсутствие прав, просроченный READY, непроверенный browser или неизвестные GitHub capabilities — не делать reset/clean, массовый stage, push через обход Gateway, установка Windows или live migration без отдельного разрешённого пути. Общий container [README](https://github.com/AlexPastukhh/fortis-container/blob/main/README.md) и `UC-CONT-003` регулируют GitHub.

**Готово:** изменение и соответствующий смысл/документы совпадают, адресные проверки PASS, при runtime изменении точный Docker READY подтверждён; отдельные live/Windows/user acceptance помечены как **непроверенные**, пока не проведены.

**Владельцы и тесты:** [AGENTS](../../AGENTS.md), [операции](../guides/RDG-OPERATIONS.md#разработка-и-обновление-серверного-runtime), [CI driver](../../tools/rdg-ci.py), [docs audit](../../tools/rdg-docs-audit.py), [функции и тесты](../guides/RDG-FUNCTIONS-AND-TESTS.md).
