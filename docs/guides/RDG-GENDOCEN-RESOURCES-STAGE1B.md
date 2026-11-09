> **СТАТУС: АРХИВ / ИСТОРИЧЕСКАЯ РАЗРАБОТКА — НЕ ДЕЙСТВУЮЩИЙ КОНТРАКТ.** Включая файлы с именами `CONTRACT`, `PLAN`, `STAGE`, `PILOT` и со словом «актуальный» в тексте. Новый чат должен использовать [единую текущую спецификацию](RDG-CURRENT-STATE.md); ниже сохранены прежние эксперименты, решения и протоколы.

# Stage 1B — RDG / Temporal Plan read-only Gendocen resource projections

**Статус:** исправленный **read-only projection pilot**, не установленный `docengine` runtime, не dependency evaluator и не Gendocen persistence. В проверенном окружении Python пакет `docengine` отсутствует. Этот адаптер создаёт JSON ресурсы в установленной форме `{"$docengine":{"resource_id":...,"materialize":[]},"data":{...}}`, однако совместимость с конкретным runtime, подписки и правила материализации **не подтверждены**.

> **Дополнение 2026-10-20 (к историческому Stage 1B):** в последующих работах реальный Gendocen 0.1.0.dev25 был проверен. Старые сведения этого пилота про отсутствие движка относятся к исходному срезу. Для нового opt-in контекста исполнения используйте `--graph <path> --workflow-context`: он формирует **отдельный** `rdg.graph.workflow-v1.<sha256(identitySpace,graphFile)[:24]>`. Обычный `--graph` и `adapt(path)` формируют прежний `rdg.graph.<...>` без смены ID/hash, а Plan остаётся `rdg.plan.<...>`. Обе Graph-проекции одного источника одновременно загружаются в Gendocen; изменение `readOnly` инвалидирует только workflow review. Экспериментальные старые workflow receipts с общим ID требуют повторной оценки при переходе; **не** переиспользуйте их автоматически. См. [текущий execution plan](RDG-CURRENT-EXECUTION-PLAN.md); данное историческое руководство не является статусом installed Windows/Stage 4.

## Что экспортируется

`tools/rdg-gendocen-adapter.py` поддерживает две формы:

1. **RDG graph** — устойчивое имя ресурса `rdg.graph.<sha256(identitySpace,graphFile)[:24]>`; `graphFile` строго `workspaces/.../graph.json`. В `data` входят `nodesById`, `edgesById`, `events`, owner, root, `actionModel`, `sourceRevision` и `semanticSHA256`. Статус Action, каноны, QRPE и T1 остаются в исходных узлах/событиях и не меняются.
2. **Temporal Plan** — отдельно `rdg.plan.<sha256(identitySpace,planId)[:24]>` с `stepsById`, `branchesById`, `sequenceByPair`, `timeConstraintsByStep`, `actionRefsByStep`, статусом кандидатного Plan и `sourceRevision`. Это ссылки на RDG, а **не** выбор/исполнение соответствующих Actions.

Идентичности graph ref двух разных графов различаются даже при одинаковом локальном `graph.id`. Если путь реального файла содержит `workspaces/.../graph.json`, переданный `--graph-ref` обязан ему соответствовать. Для внешней копии без понятного каталога `workspaces` путь нужно указать явно; caller отвечает за корректность квалифицированного owner ref.

`semanticSHA256` вычисляется по смысловому содержимому объекта **не по исходным байтам файла**. Порядок узлов/рёбер/шагов и альтернативных исходов нормализуется, как и порядок списка ограничений. Изменение ревизии без смысловых изменений **не меняет semantic hash**, но `sourceRevision` для диагностики остаётся. События RDG сохраняют хронологический порядок (он значим). Полный digest меняется при любом содержательном изменении; **для адресного отслеживания** нужно подписываться на узкие поля `nodesById/<id>`, `stepsById/<id>`, `timeConstraintsByStep/<id>`, а не на `semanticSHA256` всего ресурса.

**Важно:** тесты доказывают стабильность *локально сформированных JSON data paths* и отсутствие ложной смены hash от реорганизации JSON. Они **не** доказывают, что реальный Gendocen учитывает эти пути именно так, что подписки обновляются адресно, что документ устаревает или что output регенерируется без ошибок. Полноценный runtime-spike — следующий gate Stage 1B/4.

## Запуск

```bash
python3 tools/rdg-gendocen-adapter.py --graph /tmp/graphs/workspaces/a/graph.json
python3 tools/rdg-gendocen-adapter.py \
  --graph /tmp/external-copy.json --graph-ref workspaces/a/graph.json
python3 tools/rdg-gendocen-adapter.py --plan docs/examples/temporal-plan-candidate-v1.json

PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-gendocen-resources.test.py -v
```

В pilot `adapt(path)` для прежних вызывающих клиентов оставлен как alias к graph projection. Выбор исходника, авторизация чтения и защита приватности файлов остаются обязанностью вызывающего компонента; этот CLI не является сервером авторизации. Любые изменения canonical owner, Helper/Viewer, Plan execution и автоматическая запись Findings/Canon не входят в scope.

## Следующий gate

При наличии настоящего `docengine` runtime исполнить правила/подписки на два RDG графа и Temporal Plan, проверить события изменения отдельных fields/branches, invalidation freshness и historical snapshot; после этого выбрать точные стабильные URI и схему зависимостей для Stage 4. До runtime-теста не объявлять Gendocen интегрированным.
