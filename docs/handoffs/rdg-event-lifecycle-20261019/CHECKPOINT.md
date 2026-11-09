# Технические стадии события — контрольная точка

**ID:** CPW-RDG-EVENT-LIFECYCLE-20261019/v1. **Статус:** Candidate.
**Stage 4 NOT ACCEPTED.** Изменены исходники в Fortis Repo
`/workspace/repos/rd-graphs` на Windows RW-mount. Новые записи и тесты
работали только на временных синтетических roots; пользовательские графы,
установленное Windows-приложение и G2 не проверялись. В проекте нет
`.git`; commit/push и публикация не выполнялись.

## Результат

`tools/rdg-event-owner.py` хранит отдельно claim, техническую attestation
и технический review. Claim закрепляет точную candidate Plan revision,
ожидаемый event step/outcome, заявленное `occurredAt`, occurrence ID и
opaque evidence IDs. Две следующие стадии ссылаются на прежние записи и
требуют отдельных прав и разных bearer grant IDs. Право
`plan.event_verify` доступно только при явном bootstrap **нового**
синтетического authority store; существующие grants не менялись.
Исправление сохраняет прежний claim; несвязанные claims дают конфликт.
Время `availableBy` после долговечной записи отделено от заявленного
времени события. CAS, revoke, одновременная запись и recovery проверены.

Даже `reviewed-supported` оставляет
`humanIdentityVerified=false`, `evidenceContentsVerified=false`,
`factualEventVerified=false`, `factualBranchResolved=false` и
`actionSelected=false`. Ни событие, ни RDG Action не выбираются.
[Формат и ограничения](../../guides/RDG-EVENT-LIFECYCLE-PILOT.md).

Старый current-only `rdg-gendocen-adapter.py` теперь возвращает
`UNSUPPORTED_OWNER_LIFECYCLE` для baseline/applicability/event sidecar,
prepared sidecar journal и symlink. Его текущая Plan-проекция без sidecars
сохранила прежнее поведение. Это локальный guard входа adapter, а не
поддержка исторической event history в Gendocen.

## Проверки и gate

**88 адресных тестов PASS:** 13 event owner, 3 adapter guard, 17 Plan owner,
9 baseline, 9 applicability, 13 exact history, 6 two-time, 2 Graph writer,
10 Gendocen resources, 4 coverage guard, 2 bearer authority.
Команды и логи — в [CHECKPOINT.json](CHECKPOINT.json).
**Реальный синтетический Gendocen smoke PASS** для прежних текущих
проекций и versioned candidate Plan после изменения adapter.
Он не использовал новые event sidecars и не подтверждает historical
Gendocen as-of; весь набор Node-тестов не повторялся.

P2-AC-18 переведён только из OPEN в **PARTIAL**. Текущая исполнительная
таблица P2: 7 локальных PASS, 12 PARTIAL, 1 OPEN. Следующий gate —
доверенный actor/source и независимая предметная проверка события,
затем версионная semantic coverage и исторический Gendocen без silent valid.
[План](../../guides/RDG-CURRENT-EXECUTION-PLAN.md) ·
[WR delta](WR-DELTA.md).

[SELECTED-DIFF.patch](SELECTED-DIFF.patch) охватывает только выбранные
источники от before-копий и `/dev/null`; это не Git diff всего проекта.
SHA источников и evidence сохранены отдельно. Архив v4.1 и прежние
контрольные точки не переписывались.
