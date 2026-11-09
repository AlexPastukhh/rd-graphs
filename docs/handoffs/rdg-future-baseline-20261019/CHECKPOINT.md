# Технический будущий baseline — контрольная точка

**ID:** CPW-RDG-FUTURE-BASELINE-20261019/v1. **Статус:** Candidate.
**Stage 4 NOT ACCEPTED.** Изменены исходники в Fortis Repo
`/workspace/repos/rd-graphs` на Windows RW-mount. Все новые runtime-тесты
работали только с временными синтетическими roots. В G2, установленном
Windows-приложении и на пользовательских графах срез не проверялся.
В проекте нет `.git`; commit/push и публикация не выполнялись.

## Результат

`tools/rdg-future-baseline-owner.py` сохраняет отдельную техническую
историю будущего baseline. `accept` закрепляет точную candidate Plan
revision; `replace` требует более позднюю Plan revision и сохраняет старую
запись; `withdraw` оставляет историю доступной. Новая candidate-редакция
сама не заменяет baseline. `plan.accept` и `plan.read` нужны отдельно
от `plan.edit`. Plan store, RDG Action и события не меняются.

Owner проверяет Plan SHA/digest, CAS, отзыв права перед prepared commit,
одновременные записи и три точки аварийного восстановления. После
долговечной записи есть отдельная квитанция `availableBy`.
`knownAt` выбирает прежний доступный baseline без подстановки latest
candidate. Технический bearer receipt и строка basis **не подтверждают**
решение человека. Результат явно содержит
`humanAcceptanceVerified=false`, `actionSelected=false`,
`eventsAttested=false` и `productionAccepted=false`.
[Формат и границы](../../guides/RDG-FUTURE-BASELINE-PILOT.md).

## Проверка и следующий gate

**58 адресных тестов PASS:** 9 новых baseline, 17 Plan owner,
9 applicability owner, 13 exact history, 6 двухвременных правил,
2 Graph writer/recovery и 2 bearer authority. Команды и логи —
в [CHECKPOINT.json](CHECKPOINT.json). Gendocen и весь набор Node-тестов
не запускались заново: этот owner ещё не подключён к consumer.
P2-AC-08 повышен только с OPEN до **PARTIAL**; подтверждение пользователя,
фактический T1 и общий lifecycle не проверены. Сумма текущей
исполнительной таблицы P2: 7 локальных PASS, 11 PARTIAL, 2 OPEN.

Следующий gate — отдельные записи заявления о событии, attestation и
verification с доверенным путём actor/source; затем проверить старый
current-only consumer на явный отказ или review для нового lifecycle.
[Актуальный план](../../guides/RDG-CURRENT-EXECUTION-PLAN.md) ·
[WR delta](WR-DELTA.md).

[SELECTED-DIFF.patch](SELECTED-DIFF.patch) показывает выбранные файлы от
before-копий и `/dev/null` для новых; это не Git diff всего проекта.
SHA источников и evidence записаны отдельно. Архив v4.1 и прежние
контрольные точки не переписывались.
