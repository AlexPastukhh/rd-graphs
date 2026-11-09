# Долговечная candidate history применимости — контрольная точка

**ID:** CPW-RDG-APPLICABILITY-OWNER-20261019/v1. **Статус:** Candidate.
**Stage 4 NOT ACCEPTED.** Изменения сделаны в Fortis Repo на RW-mount
`/workspace/repos/rd-graphs`. Проверки использовали только временные
синтетические roots. В G2, установленном Windows-приложении и на
пользовательских графах этот срез не проверялся. В проекте нет `.git`;
commit/push и публикация не выполнялись.

## Что добавлено

`tools/rdg-applicability-owner.py` хранит отдельную версионированную
candidate history для одного Plan owner: точные Plan/RDG pins, ветвь,
заявленный `effectiveAt`, `supersedes`, локальный `recordedAt` и
квитанцию доступности после долговечной записи. Запись требует
`plan.applicability.write`, отдельного opt-in при создании временного
authority store, права чтения sources, CAS и подготовленного журнала.
Recovery завершает prepared транзакцию; отсутствие прежней квитанции
блокирует новую запись. Исходная запись сохраняется, повтор транзакции
идемпотентен, изменение того же transaction ID отклоняется.

При чтении ранний `knownAt` исключает позднюю поправку; после её
`availableBy` запрос может выбрать её как **кандидатную позднюю
реконструкцию**. Несвязанный конфликт outcomes даёт отказ. История
сохраняет утверждения, но не подтверждает их: eventClaim остаётся
`unverified`, полный контекст и фактический T1-as-of не установлены.
[Формат и границы](../../guides/RDG-APPLICABILITY-OWNER-PILOT.md).

## Проверка и следующий gate

**49 адресных тестов PASS:** 9 новых owner, 17 Plan owner, 13 exact history,
6 двухвременных правил, 2 Graph writer/recovery и 2 bearer authority.
Команды и логи — в [CHECKPOINT.json](CHECKPOINT.json). Ранее проверенный
Gendocen работает с текущими проекциями; в этом срезе он не запускался
заново. Прежние 405 Node PASS не повторялись целиком.

P2-AC-13/15/16 остаются **PARTIAL**. Есть долговечная локальная запись и
recovery, но `effectiveAt` заявлен клиентом, trusted event source не
выбран, и полный набор применимых owners/событий не доказан. Следующий
gate: отдельный lifecycle принятого будущего baseline и attest/verify
событий, затем полный исторический resolver и Gendocen на синтетической
истории. [Актуальный план](../../guides/RDG-CURRENT-EXECUTION-PLAN.md) ·
[WR delta](WR-DELTA.md).

[SELECTED-DIFF.patch](SELECTED-DIFF.patch) — diff выбранных файлов от
before-копий и `/dev/null` для новых файлов; это не Git diff всего проекта.
SHA источников и evidence сохранены отдельно. Baseline v4.1 и старые
контрольные точки не переписывались.
