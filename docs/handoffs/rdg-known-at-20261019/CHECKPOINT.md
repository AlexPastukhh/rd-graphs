# Ограниченный knownAt для точных Plan + RDG — контрольная точка

**ID:** CPW-RDG-KNOWN-AT-20261019/v1. **Статус:** Candidate.
**Stage 4 NOT ACCEPTED.** Изменено в Fortis Repo на RW-mount
`/workspace/repos/rd-graphs`, который затрагивает настоящие Windows-файлы.
Проверено только на временных синтетических корнях. В G2/Windows GUI не
проверялось; установка, пользовательские графы, commit/push и публикация
не выполнялись. В проекте нет `.git`, поэтому Git status/diff невозможны.

## Сделано

Graph package writer теперь сохраняет journal schemaVersion 2:
`preparedAt` при принятии пакета, `recordedAt: null` до завершения,
`recordedAt` после долговечной записи и обратного чтения графа. Recovery
после сбоя ставит консервативное время завершения. Регресс локальных часов
останавливает запись. Старый schemaVersion 1 остаётся разрешимым без
временной метки.

Read-only resolver принимает опциональный точный `knownAt`. Для выбранных
Graph revisions требуется завершённый v2 after-образ, записанный к cutoff.
Для Plan revision N требуется N+1: защищённый следующий edit уже прочитал
N из сохранённого owner store, а время N+1 даёт верхнюю границу доступности
N. Последняя Plan revision и старые Graph journals для `knownAt` отклоняются.
Без `knownAt` прежний exact-reference режим работает как раньше; current
`graph.json` не используется как подстановка. В Gendocen smoke после Plan 5
старые Plan 1 / Graph 3 разрешены повторно с тем же условным impact.

Это проверка доступности закреплённых источников, **не** выбор полного
применимого контекста на дату. `effectiveAt` по-прежнему отклоняется;
`knowledgeTimeVerified=false`, `twoTimeAsOfResolved=false`,
`historicalT1KnowledgeVerified=false`. Локальные часы и hashes не доказывают
личность, истинность события, factual outcome или accepted future baseline.
Сам Gendocen использовал текущие проекции. [Формат и границы](../../guides/RDG-EXACT-HISTORY-PILOT-P2.md).

## Проверки

После исправления момента `recordedAt` прошли **42 Python-теста**:
13 exact-history, 2 writer/recovery, 13 bearer writer, 14 Plan owner.
**405 Node-тестов**: 404 в `tests/*.test.cjs` и 1 viewer smoke в `tools/`.
**1 реальный Gendocen 0.1.0.dev25 smoke PASS** в изолированном
синтетическом проекте. Логи и команды — в [CHECKPOINT.json](CHECKPOINT.json).
Ранние логи без суффикса `-final` в этой папке относятся к варианту
до коррекции временной границы; итоговый результат основан на `-final`
логах, `smoke.log`, `node.log`, `node-tool.log`.

## Дальше

Нужна долговечная верхняя граница для **последней** Plan revision без
ожидания следующего edit, затем provenance `effectiveAt` и проверка
полного применимого RDG/Plan/event контекста. Отдельно потребуется
исторический Gendocen runtime. Прежние checkpoints и v4.1 ZIP не изменены.
[WR delta](WR-DELTA.md).

Вместо Git diff сохранён [SELECTED-DIFF.patch](SELECTED-DIFF.patch) по
before-копиям из `BASELINE.json`; SHA выбранных файлов и доказательств —
в `SOURCE-HASHES.json` и `EVIDENCE-HASHES.json`. Это не diff всего проекта.
