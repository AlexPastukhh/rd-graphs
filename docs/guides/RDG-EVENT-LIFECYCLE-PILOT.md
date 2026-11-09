> **СТАТУС: АРХИВ / ИСТОРИЧЕСКАЯ РАЗРАБОТКА — НЕ ДЕЙСТВУЮЩИЙ КОНТРАКТ.** Включая файлы с именами `CONTRACT`, `PLAN`, `STAGE`, `PILOT` и со словом «актуальный» в тексте. Новый чат должен использовать [единую текущую спецификацию](RDG-CURRENT-STATE.md); ниже сохранены прежние эксперименты, решения и протоколы.

# Событие: заявление, attestation и техническая проверка

**Статус: CANDIDATE. Stage 4 NOT ACCEPTED.**
`tools/rdg-event-owner.py` хранит отдельную историю для ожидаемого
события Temporal Plan. Это локальный пилот на явно заданном root. Plan
schema v1, RDG Action и фактический T1 не меняются. В этой истории нет
подтверждённого факта, даже если технический reviewer указал
`reviewed-supported`.

| Стадия | Запись | Право | Что остаётся непроверенным |
|---|---|---|---|
| claim | `occurrenceId`, точный Plan pin, ожидаемый event step, outcome, `occurredAt` с исходной точностью, opaque `evidenceRefs`, `supersedes` | `plan.edit` + `plan.read` | Содержание evidence и наступление события |
| attest | Ссылка на точный claim и свои `evidenceRefs` | `plan.event_attest` + `plan.read` | Личность actor и достоверность источника |
| verify | Ссылка на точную attestation, решение `reviewed-supported` или `disputed` и свои `evidenceRefs` | `plan.event_verify` + `plan.read` | Независимая предметная проверка результата |

`plan.event_verify` появляется только при **явном** локальном
`rdg-authority.py init --plan-capable --event-verify-capable` для нового
синтетического authority store. Существующие grants не изменяются.
Три записи должны иметь разные grant IDs; это лишь техническое разделение
bearer-токенов, не доказательство разных людей. Клиентские
`evidenceRefs` — идентификаторы, их содержимое пилот не читает.

Операция `apply` принимает
`transactionId/kind/file/expectedRevision/payload`. Например, payload
для claim (хеши здесь сокращены, пример не исполняемый):

```json
{
  "id": "C1",
  "occurrenceId": "O1",
  "planPin": {
    "file": "plans/demo/plan.json",
    "identitySpace": "temporal-demo",
    "planId": "PLAN-ID",
    "revision": 1,
    "snapshotSHA256": "exact snapshot SHA256",
    "recordDigest": "exact owner record digest"
  },
  "eventStepId": "S-RESULT",
  "outcome": "positive",
  "occurredAt": "2026-10-18T10:00:00+00:00",
  "evidenceRefs": ["EV-C1"],
  "supersedes": null
}
```

Attest payload:
`{"id":"A1","claimId":"C1","evidenceRefs":["EV-A1"]}`.
Verify payload:
`{"id":"V1","attestationId":"A1","decision":"reviewed-supported","evidenceRefs":["EV-V1"]}`.
Каждая стадия требует следующую `expectedRevision` owner history.
Plan pin должен разрешаться к настоящему сохранённому candidate snapshot,
а event step и outcome — совпадать с его expected event. Claim может
исправить предыдущий claim через `supersedes`; прежняя запись остаётся.
Разная precision времени одного occurrence отклоняется. Несвязанные
claims дают явный `claimConflict=true`, даже если их outcomes совпадают.
Последний файл не назначается фактической ветвью.

Owner хранит hash-цепочку, prepared journal и квитанцию `availableBy`
после долговечной записи каждой стадии. После сбоя чтение блокируется до
`recover`; прежняя квитанция не перезаписывается. Отзыв до prepared
commit отклоняет запись. Повтор transaction ID идемпотентен, другое
содержимое с тем же ID отклоняется. Отдельный `knownAt` исключает
ещё недоступные записи; закреплённый Plan также должен быть доказанно
доступен к cutoff.

CLI на временном синтетическом root:

```bash
RDG_AUTH_TOKEN=... python3 tools/rdg-event-owner.py apply \
  --root PLAN_ROOT --store AUTH_STORE --request REQUEST_JSON
RDG_AUTH_TOKEN=... python3 tools/rdg-event-owner.py read \
  --root PLAN_ROOT --store AUTH_STORE --file plans/demo/plan.json \
  --occurrence-id O1 --known-at 2026-10-18T11:00:00+00:00
python3 tools/rdg-event-owner.py recover --root PLAN_ROOT
```

Read возвращает все известные claims, attestation и reviews с точными
record digests и `availableBy`. Поля `factualEventVerified`,
`factualBranchResolved`, `humanIdentityVerified`,
`evidenceContentsVerified`, `actionSelected` остаются `false`.
Нет trusted source, разрешения полного контекста по `effectiveAt`,
связи с установленным Helper/Viewer и историческим Gendocen. Старый
current-only `rdg-gendocen-adapter.py` теперь явно отклоняет owned Plan,
если рядом есть baseline/applicability/event sidecar или незавершённый
журнал. Это локальная проверка входа adapter; реальный исторический
Gendocen runtime с этими records ещё не интегрирован.

Проверка:
`PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-event-owner.test.py -v`.
Тесты используют только tempfile, без пользовательских графов.
