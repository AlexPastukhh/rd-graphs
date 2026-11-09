> **СТАТУС: АРХИВ / ИСТОРИЧЕСКАЯ РАЗРАБОТКА — НЕ ДЕЙСТВУЮЩИЙ КОНТРАКТ.** Включая файлы с именами `CONTRACT`, `PLAN`, `STAGE`, `PILOT` и со словом «актуальный» в тексте. Новый чат должен использовать [единую текущую спецификацию](RDG-CURRENT-STATE.md); ниже сохранены прежние эксперименты, решения и протоколы.

# Принятый будущий baseline — отдельный локальный owner

**Статус: CANDIDATE. Stage 4 NOT ACCEPTED.**
`tools/rdg-future-baseline-owner.py` хранит техническую запись о принятии
**точной candidate-версии** Temporal Plan. Она находится рядом с Plan, но
не меняет `plan.json`, статус его candidate-версий и RDG Action.
Запись не является независимым подтверждением решения пользователя:
`humanAcceptanceVerified=false`.

## Операции и права

`accept` создаёт первую запись с точным `planPin` (путь, identity,
revision, SHA snapshot и digest owner record). `replace` требует новую
более позднюю Plan revision и сохраняет прежний baseline; `withdraw`
сохраняет запись об отзыве, не удаляя старые записи. Повторное принятие
после отзыва в этой версии не реализовано. Каждая операция требует
`plan.accept` **и** `plan.read`, `expectedStateRevision`, непустое
`basis` и уникальный `transactionId`. `basis` остаётся заявлением
технического bearer actor. `plan.edit`, `plan.branch` и `graph.write`
не дают право принять baseline.

Форма запроса:

```json
{
  "transactionId": "synthetic-accept-r1",
  "op": "accept",
  "file": "plans/demo/plan.json",
  "expectedStateRevision": 0,
  "planPin": {
    "file": "plans/demo/plan.json",
    "identitySpace": "temporal-demo",
    "planId": "PLAN-ID",
    "revision": 1,
    "snapshotSHA256": "64 hex chars from the exact owner snapshot",
    "recordDigest": "64 hex chars from the owner record"
  },
  "basis": "Synthetic technical approval"
}
```

Поля SHA в примере поясняющие; для исполнения нужны настоящие 64-символьные
хеши из сохранённого Plan owner. Запись использует отдельный state revision
для lifecycle, CAS, hash-цепочку, prepared journal и квитанцию `availableBy`
после сохранения. После сбоя чтение блокируется до `recover`. Прежняя
квитанция сохраняется при recovery. Никакие grants, ACL и существующие
authority stores не расширяются: `plan.accept` уже отделён в Plan owner.

CLI для **временного синтетического root**:

```bash
RDG_AUTH_TOKEN=... python3 tools/rdg-future-baseline-owner.py apply \
  --root PLAN_ROOT --store AUTH_STORE --request REQUEST_JSON
RDG_AUTH_TOKEN=... python3 tools/rdg-future-baseline-owner.py read \
  --root PLAN_ROOT --store AUTH_STORE --file plans/demo/plan.json \
  --state-revision 1 --known-at 2026-10-18T11:00:00+00:00
python3 tools/rdg-future-baseline-owner.py recover --root PLAN_ROOT
```

Чтение возвращает точную принятую Plan revision, в том числе после появления
новой candidate-редакции. Без `--state-revision` выбирается последняя
доступная запись owner; с `knownAt` — последняя запись, доступная к этому
моменту. Выбранный Plan тоже должен иметь доказанную доступность к cutoff.
Отзыв возвращает `state=withdrawn`, а старая запись остаётся доступной
по точной ссылке. Чтение повторно проверяет право перед выдачей.

Результат имеет `status=technical-future-baseline` и явные
`actionSelected=false`, `eventsAttested=false`,
`humanAcceptanceVerified=false`, `completeApplicableContextVerified=false`.
Старый candidate-only consumer не подключён к этому owner. Условная ветвь
Plan остаётся условной; событие и Action не становятся фактом или выбором.
Нет доверенного пути подтверждения пользователя, отдельного attest/verify
событий и исторического Gendocen для нового lifecycle.

Проверка:
`PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-future-baseline.test.py -v`.
Тесты работают в tempfile и проверяют изоляцию candidate, отказ без
`plan.accept`, повтор/CAS, отзыв, точную историю, ранний `knownAt`,
revoke, повреждённый pin и три точки аварийного восстановления.
