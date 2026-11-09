> **СТАТУС: АРХИВ / ИСТОРИЧЕСКАЯ РАЗРАБОТКА — НЕ ДЕЙСТВУЮЩИЙ КОНТРАКТ.** Включая файлы с именами `CONTRACT`, `PLAN`, `STAGE`, `PILOT` и со словом «актуальный» в тексте. Новый чат должен использовать [единую текущую спецификацию](RDG-CURRENT-STATE.md); ниже сохранены прежние эксперименты, решения и протоколы.

# Совместный исторический context — scoped pilot v1

**Статус: CANDIDATE. Stage 4 NOT ACCEPTED.**
`tools/rdg-joint-context.py` собирает один явно заданный Plan, условный
branch/outcome, occurrence, применимость, lifecycle и точные RDG snapshots
в read-only bundle. Он проверяет согласованность предъявленного scope.
Полнота всех применимых owners и истинность claims остаются непроверенными.

Запрос:

```json
{
  "schemaVersion": 1,
  "mode": "scoped-joint-context",
  "lifecycle": "candidate",
  "planFile": "plans/demo/plan.json",
  "knownAt": "2026-10-19T00:00:00+00:00",
  "effectiveAt": "2026-10-18T10:45:00+00:00",
  "scenario": {"branchId": "B-RESULT", "outcome": "positive"},
  "occurrenceId": "O1",
  "baselineStateRevision": null
}
```

В `candidate` режиме версия выбирается из долговечной applicability history
по двум временам. В `accepted-future` режиме `baselineStateRevision`
обязателен: это **точная** запись отдельного baseline owner. Resolver
использует assertion этого baseline и цепочку его предков; более поздние
candidate records его не заменяют. Отозванный baseline, ещё недоступный
state или неподходящий `effectiveAt` дают ошибку. Автоматического выбора
между принятыми baseline по `effectiveAt` пока нет: у lifecycle records
не определена собственная история effective-интервалов.

`knownAt` должен быть timezone-aware instant не позже текущего локального
времени. `effectiveAt` сохраняет date-only либо instant precision.
Applicability и event time должны иметь ту же precision. Неизвестная дата
не подставляется. Нужен один совместимый leaf claim выбранного occurrence:
его точный Plan pin, event step и outcome должны совпасть со сценарием;
заявленное время события не должно быть позже `effectiveAt`.
Конфликт или несовместимая версия дают отказ. Это проверка согласованности
условного контекста; фактическая ветвь и Action не выбираются.

Четыре Plan-root owners читаются под общим shared lock. Prepared journal
любого из них блокирует bundle. Graph snapshots берутся только из
завершённой writer history, с прямым after-свидетельством к cutoff.
Поздние before-images не входят в историческое доказательство старого
bundle. Временная доступность проверяется для lifecycle, applicability,
Plan, Graph и event records. Отсутствие snapshot/квитанции, mismatch,
неизвестная версия и отзыв read grant дают явный отказ без current fallback.

Bundle содержит полные selected Plan/RDG snapshots и candidate assessment.
Contract `rdg-joint-review/v1` вычисляет девять subscriptions: coverage и
`query/lifecycle/applicability/plan/graphs/event/assessment/boundaries`.
Producer groups независимы от декларации. Перед регистрацией повторно
проверяются SHA snapshot, выбор применимости, event context, cutoff и
assessment на предъявленных snapshots. Пропущенные группы/subscriptions,
подменённая проекция или factual flags отклоняются.

CLI на разрешённых roots:

```bash
RDG_AUTH_TOKEN=... python3 tools/rdg-joint-context.py \
  --plan-root PLAN_ROOT --graphs-root GRAPHS_ROOT --store AUTH_STORE \
  --request REQUEST_JSON --projection
```

Без `--projection` возвращается bundle; с ним — ресурс Gendocen.
Нужны `plan.read` и `graph.read` для всех источников выбранной цепочки.
Новый конфликтующий запрос завершается ошибкой. Сохранённый старый bundle
остаётся доказательством только собственного явно указанного cutoff;
его нельзя подставлять как результат нового запроса. Каждый resource ID
нужно хранить как неизменный bundle. При новой реконструкции прежний ресурс
сохраняется: Gendocen использует его как основание старой receipt. Если
перезаписать файл другим resource ID и удалить прежний, движок вернёт
`invalid` из-за недоступного старого основания.

`scopedExactContextResolved=true` означает согласованную сборку этого
scope. `completeApplicableContextVerified=false`,
`automaticBaselineEffectiveSelectionComplete=false`,
`factualEventVerified=false`, `historicalT1KnowledgeVerified=false`.
Dependency `valid` в Gendocen относится к свежести документа этого bundle.
Он не подтверждает факт события, решение пользователя или полный as-of.

Проверки:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-joint-context.test.py -v
PYTHONDONTWRITEBYTECODE=1 python3 tools/rdg-joint-context-smoke.py \
  --engine-source /workspace/repos/gendocen
```

Runtime создаёт временные sources через штатные Graph/Plan/applicability/
baseline/event writers и использует реальный Gendocen. Он проверяет
ранний контекст, точный baseline, позднюю реконструкцию, stale context,
отказ новому конфликтующему запросу и неизменность источников при чтении.
Полный lifecycle effective selection, несколько owners/событий, совместные
concurrent write/recovery и trusted evidence требуют следующих gates.
