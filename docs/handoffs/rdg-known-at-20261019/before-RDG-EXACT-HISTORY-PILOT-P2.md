# Точные Plan + RDG snapshots — read-only пилот

**Статус: CANDIDATE. Stage 4 NOT ACCEPTED.** Это локальное разрешение точных
ссылок для одного условного сценария, а не полный запрос `knownAt/effectiveAt`.
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

В Graph writer journal **нет доверенного `recordedAt` для RDG**. Поэтому
результат отмечает `knowledgeTimeVerified=false`, `twoTimeAsOfResolved=false`,
`historicalT1KnowledgeVerified=false`. Пилот не принимает `knownAt/effectiveAt`,
не доказывает знание на T1 и не подключает исторический режим к Gendocen
subscription/runtime. Даже совпадение SHA не доказывает человека или факт
события. Полный as-of потребует собственных неизменяемых временных records RDG,
проверки порядка lifecycle/branch и отдельного trust gate.

Проверка: `python3 tests/rdg-exact-history.test.py -v` и
`python3 tools/rdg-gendocen-t1-history-smoke.py --engine-source /workspace/repos/gendocen --plan-owner`.
В последнем прогоне Graph writer создаёт реальный локальный журнал; после
последующих QRPE/Plan изменений resolver вновь выдаёт тот же pinned T1 graph
snapshot и ту же оценку выбранного сценария. Сам Gendocen остаётся на текущих
проекциях и не подтверждает historical T1-as-of.
