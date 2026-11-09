# Двухвременной candidate rule probe — контрольная точка

**ID:** CPW-RDG-TWO-TIME-SCENARIO-20261019/v1. **Статус:** Candidate.
**Stage 4 NOT ACCEPTED.** В Fortis Repo изменены исходники на RW-mount
`/workspace/repos/rd-graphs`, который затрагивает настоящие Windows-файлы.
Runtime-проверка использовала только временные синтетические roots. В G2,
установленном Windows-приложении и на пользовательских графах не проверялось;
commit/push и публикация не выполнялись. В проекте нет `.git`.

## Результат

Новый read-only `tools/rdg-two-time-scenario.py` принимает точные
Plan/RDG ссылки и **клиентские candidate-утверждения** об `effectiveAt`.
Он разрешает каждый pinned source через прежний exact resolver, проверяет
Plan availability на `knownAt` и выбранный Graph after-образ на том же
cutoff. Поздняя r2 исключается из раннего знания, а после её записи может
заменить r1 только через явный `supersedes`. Несвязанные применимые claims,
включая разные outcomes, дают конфликт. Date-only/instant не смешиваются;
неизвестная дата не превращается в текущую. Порядок массива не влияет на
выбор; чтение повторно проверяет grant и не меняет Plan/Graph bytes.

`eventClaim` допускается только с `verification=unverified` и не выбирает
фактическую ветвь. Результат сохраняет `twoTimeAsOfResolved=false`,
`historicalT1KnowledgeVerified=false`, `completeApplicableContextVerified=false`.
Это проверка правила выбора на предъявленном наборе, а не разрешение
полной owner history. [Формат, CLI и границы](../../guides/RDG-TWO-TIME-SCENARIO-PILOT.md).

## Проверки и границы

**21 Python-тест PASS:** 6 новых двухвременных сценариев, 13 exact-history
regression и 2 реальных Graph writer/recovery tests. Логи и команды — в
[CHECKPOINT.json](CHECKPOINT.json). Gendocen и Node-код в этом срезе не
менялись и их runtime не запускался заново. Прежний реальный синтетический
Gendocen PASS относится к текущим проекциям, не к новой модели.

Правило пока требует неубывающий `effectiveAt` внутри correction chain;
ретроактивная поправка с более ранней границей отклоняется. Нет долговечной
записи применимости, удостоверенного event source, полноты всех применимых
owners и фактического T1-as-of. Ближайший gate — owner journal для этих
records с правом записи, recovery и повторением P2-AC-13/15/16 на сохранённой
истории. [Актуальный план](../../guides/RDG-CURRENT-EXECUTION-PLAN.md) ·
[WR delta](WR-DELTA.md).

[SELECTED-DIFF.patch](SELECTED-DIFF.patch) сравнивает выбранные источники
с before-копиями и `/dev/null` для новых файлов; это не Git diff всего
проекта. SHA источников и логов сохранены отдельно. Старые checkpoints и
v4.1 ZIP не переписывались.
