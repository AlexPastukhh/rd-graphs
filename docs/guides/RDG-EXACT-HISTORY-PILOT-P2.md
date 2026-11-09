> **СТАТУС: АРХИВ / ИСТОРИЧЕСКАЯ РАЗРАБОТКА — НЕ ДЕЙСТВУЮЩИЙ КОНТРАКТ.** Включая файлы с именами `CONTRACT`, `PLAN`, `STAGE`, `PILOT` и со словом «актуальный» в тексте. Новый чат должен использовать [единую текущую спецификацию](RDG-CURRENT-STATE.md); ниже сохранены прежние эксперименты, решения и протоколы.

# Точные Plan + RDG snapshots — read-only пилот

**Статус: CANDIDATE. Stage 4 NOT ACCEPTED.** Это локальное разрешение точных
ссылок для одного условного сценария. Опциональный `knownAt` проверяет
доказуемую доступность закреплённых источников к моменту отсечения;
это не полный исторический as-of с `effectiveAt`.
Основание: [контракт P1](RDG-TEMPORAL-PLAN-OWNER-CONTRACT-P1.md) и
[Plan owner P2](RDG-TEMPORAL-PLAN-OWNER-PILOT-P2.md).

`tools/rdg-exact-history.py` получает сохранённую ревизию candidate Plan из
owner store и сохранённые образы RDG из **завершённых** журналов штатного
`graph-package.py`. У каждого источника должна быть явная identity, точная
revision и закреплённый SHA-256 канонического JSON. Для Plan нужен также
`recordDigest` его записи. Читатель проверяет owner/path, структурную
целостность, соответствие actionRef по graphFile/identitySpace/revision и
выбранный branch/outcome. Снимок берётся из before или after завершённой
транзакции. Несколько разных образов одной ревизии, незавершённый/испорченный
журнал, неверный хеш или отсутствующая ревизия останавливают разрешение.
Текущий `graph.json` не читается и не заменяет отсутствующий снимок.

Временный локальный bearer grant должен иметь `plan.read` и `graph.read`
с соответствующими путями. `graph.write`, `plan.create`, `grant.admin` и
права выбора Action не подменяют чтение. Права повторно проверяются перед
выдачей результата. Файловый доступ Docker сам по себе не изолирует
этот пилот от raw-правок и не служит production authorization.

Пример формы запроса (`snapshotSHA256` и `recordDigest` берутся из реально
сохранённых источников, не вычисляются по текущим файлам):

```json
{
  "schemaVersion": 1,
  "mode": "exact-reference",
  "lifecycle": "candidate",
  "plan": {
    "file": "plans/demo/plan.json",
    "identitySpace": "temporal-demo",
    "planId": "P-DEMO",
    "revision": 1,
    "snapshotSHA256": "<64 hex>",
    "recordDigest": "<64 hex>"
  },
  "graphs": [{
    "graphFile": "workspaces/temporal-fixture/graph.json",
    "identitySpace": "temporal-demo",
    "revision": 3,
    "snapshotSHA256": "<64 hex>"
  }],
  "scenario": {"branchId": "B-RESULT", "outcome": "positive"}
}
```

CLI: `python3 tools/rdg-exact-history.py --plan-root ROOT --graphs-root GRAPHS_ROOT --store AUTH_STORE --request REQUEST_JSON`;
токен в `RDG_AUTH_TOKEN`. Roots указываются явно. Это read-only операция:
она не вызывает Graph writer, Plan writer, принятие или event attestation.
Временной impact оценивает только выбранный сценарий по проверенным снимкам.
Условный сценарий не становится фактически наступившей ветвью; оценка срока
остаётся предположением кандидата. Она не создаёт Finding и не меняет T1.

В новых Graph writer journals (schemaVersion 2) `preparedAt` означает
момент попытки принять транзакцию. Это **не** время доступности нового графа.
После долговечной записи и обратного чтения графа writer ставит `recordedAt`
при завершении; после сбоя recovery ставит более позднюю, консервативную
метку. Для старого schemaVersion 1 метки нет. Локальные часы и SHA не служат
независимым подтверждением личности или факта.

Опциональный `knownAt` — строка с точным временем и часовым поясом. Resolver
сравнивает время с `recordedAt` каждого выбранного RDG **after**-образа.
Для Plan revision N его собственный `recordedAt` ещё предшествует долговечной
записи. Новый owner создаёт отдельную квитанцию `availableBy` после записи и
синхронизации Plan store и owner index. Она привязана к пути, ревизии и
`recordDigest`. При сбое до квитанции recovery завершает запись и ставит
более позднее время; при сбое после квитанции сохраняет её прежнее время.
Поэтому и **последняя** новая версия Plan может пройти `knownAt`.

Для старой версии без квитанции resolver требует revision N+1: защищённое
редактирование уже прочитало N из сохранённого owner store, а время N+1
задаёт консервативную верхнюю границу доступности N. Старая последняя
версия без квитанции, Graph только из before-образа или старого журнала
не проходят проверку.
Без `knownAt` остаётся прежнее разрешение точных ссылок без утверждения
о времени. Отсутствующее свидетельство не заменяется текущим файлом.

Успешный запрос ставит `recordingCutoffVerified=true` только для этой
ограниченной проверки доступности закреплённых источников. Он не выбирает
полный контекст, который действовал на дату, и не доказывает, что выбранный
Plan был тогда последним или применимым. `effectiveAt` отклоняется;
`knowledgeTimeVerified=false`, `twoTimeAsOfResolved=false`,
`historicalT1KnowledgeVerified=false`. Это не подтверждение знания на T1,
не исторический Gendocen subscription/runtime и не принятие фактической
ветви. Для полного as-of нужны проверяемые события и применимость по
`effectiveAt`, вся относящаяся история RDG и отдельный trust gate.

Проверка: `python3 tests/rdg-exact-history.test.py -v`,
`python3 tests/rdg-writer-recording.test.py -v` и
`python3 tools/rdg-gendocen-t1-history-smoke.py --engine-source /workspace/repos/gendocen --plan-owner`.
В последнем прогоне Graph writer создаёт реальный локальный журнал; после
последующих QRPE/Plan изменений resolver вновь выдаёт тот же pinned T1 graph
snapshot и ту же оценку выбранного сценария. Пилот отдельно проверяет
`knownAt` для последней Plan revision 1 по её собственной квитанции. Сам Gendocen остаётся на текущих
проекциях и не подтверждает historical T1-as-of.
