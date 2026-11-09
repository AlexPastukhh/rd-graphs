> **СТАТУС: АРХИВ / ИСТОРИЧЕСКАЯ РАЗРАБОТКА — НЕ ДЕЙСТВУЮЩИЙ КОНТРАКТ.** Включая файлы с именами `CONTRACT`, `PLAN`, `STAGE`, `PILOT` и со словом «актуальный» в тексте. Новый чат должен использовать [единую текущую спецификацию](RDG-CURRENT-STATE.md); ниже сохранены прежние эксперименты, решения и протоколы.

# Долговечная история применимости candidate Plan

**Статус: CANDIDATE. Stage 4 NOT ACCEPTED.**
Пилот `tools/rdg-applicability-owner.py` записывает утверждения о
применимости Plan отдельно от версий Plan. Это локальный owner на явно
заданном временном root. Он сохраняет точные ссылки на Plan/RDG snapshots,
`effectiveAt`, `supersedes`, исходное `recordedAt` и квитанцию
`availableBy` после записи. Старое утверждение остаётся в истории.

Запись требует отдельного `plan.applicability.write` и чтения всех
указанных Plan/RDG sources. Разрешение чтения требует `plan.read` и
`graph.read`. Новый локальный bootstrap выдаёт возможность делегировать
это право только с явными `--plan-capable --applicability-capable`;
существующие grants не меняются. Bearer receipt подтверждает технический
grant, но не личность автора и не истинность события.

Запрос на запись содержит `transactionId`, `file` (путь
`plans/.../plan.json`), `expectedRevision` и `assertion` из
[модельного правила двух времён](RDG-TWO-TIME-SCENARIO-PILOT.md).
`assertion.source` — полный exact-reference запрос с Plan/RDG pins и
сценарием, без `knownAt`. `eventClaim` остаётся только
`verification=unverified`. Каждый record проходит проверку pinned sources;
CAS, повтор той же транзакции и correction chain проверяются до записи.
Несвязанные применимые записи можно сохранить, но чтение вернёт явный
конфликт. Цепь с более ранним `effectiveAt` пока отклоняется.

Пилот хранит `.rdg-applicability.json` рядом с Plan, отдельный
prepared journal на root и квитанцию каждой версии рядом с owner store.
После сбоя чтение блокируется до `recover`. Recovery дописывает принятую
prepared транзакцию и не меняет уже сохранённую квитанцию. Пока нет
квитанции предыдущей версии, следующая запись отклоняется.

CLI на **временном синтетическом root**:

```bash
RDG_AUTH_TOKEN=... python3 tools/rdg-applicability-owner.py apply \
  --root PLAN_ROOT --graphs-root GRAPHS_ROOT --store AUTH_STORE --request REQUEST_JSON
RDG_AUTH_TOKEN=... python3 tools/rdg-applicability-owner.py read \
  --root PLAN_ROOT --graphs-root GRAPHS_ROOT --store AUTH_STORE \
  --file plans/demo/plan.json --known-at 2026-10-18T11:00:00+00:00 \
  --effective-at 2026-10-18T10:45:00+00:00
python3 tools/rdg-applicability-owner.py recover --root PLAN_ROOT
```

Чтение сначала исключает records, которые ещё не были доказанно доступны
к `knownAt`, затем применяет
[read-only правило](RDG-TWO-TIME-SCENARIO-PILOT.md) к оставшимся.
Оно отдельно проверяет Plan availability и RDG writer time. Поздняя
поправка может дать **кандидатную ретроспективную реконструкцию** только
после собственного `availableBy`; ранний результат не переписывается.
`ownerHistory.assertionsDurablyRecorded=true` означает лишь сохранность
этого локального журнала. `applicabilityAttested=false`,
`completeApplicableContextVerified=false`,
`twoTimeAsOfResolved=false`, `historicalT1KnowledgeVerified=false`.

Журнал не доказывает, что доступны все другие owners/события и что
`effectiveAt` верен. Принятие будущего baseline, trusted event source,
фактический Action selection и историческая Gendocen subscription ещё
открыты. Тесты используют только tempfile, без рабочих графов и
установленного Windows-приложения.

Проверка: `PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-applicability-owner.test.py -v`.
