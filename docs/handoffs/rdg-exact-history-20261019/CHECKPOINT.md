# Точные Plan + RDG snapshots — контрольная точка

**ID:** CPW-RDG-EXACT-HISTORY-20261019/v1. **Статус:** Candidate.
**Stage 4 NOT ACCEPTED.** Изменено и проверено в Fortis Repo на
синтетических источниках. Установки Windows, записи в пользовательские графы,
commit/push и публикации не было.

## Результат

Новый read-only `tools/rdg-exact-history.py` принимает точные ссылки на одну
версию candidate Plan и нужные RDG revisions для выбранного условного
сценария. Plan читается из owner store; RDG — из `before/after` завершённых
журналов штатного Graph writer. Identity, путь, revision, SHA, Plan recordDigest
и Plan actionRef совпадают. Resolver отклоняет отсутствующую версию, неверный
хеш, другую identity, неоднозначную ревизию, незавершённый или испорченный
журнал и нехватку `plan.read`/`graph.read`. Текущий `graph.json` не подставляется.

После Graph revision 5 и Plan revision 5 сквозной synthetic прогон вновь
разрешил закреплённые Graph revision 3 / Plan revision 1. Impact выбранного
сценария совпал с первичной оценкой; поздний QRPE не попал в старый снимок.
Настоящий Gendocen продолжал проверять **текущие** проекции и сохранил T1,
selectionBasis, review и recovery. Он не исполнял исторический as-of.
[Формат и границы](../../guides/RDG-EXACT-HISTORY-PILOT-P2.md).

## Проверки

**60 Python-тестов PASS, 2 Node-теста PASS, 1 реальный Gendocen smoke PASS**
в этом срезе. 11 новых тестов проверяют в том числе `before`-образ,
отсутствующую историю при наличии current graph, ambiguous revision, хеши,
права/отзыв, symlink и recovery gate. Ещё 49 Python-тестов повторно проверяют
Plan owner, impact, bearer writer и branch acceptance. Сохранены команды,
результаты и логи в [CHECKPOINT.json](CHECKPOINT.json).
Ранее подтверждённые 405 Node-тестов и другие smokes остались в
[предыдущем checkpoint](../rdg-vertical-slice-20261019/CHECKPOINT.md);
в этом срезе они не запускались заново.

Первый вызов branch acceptance использовал неверный путь к историческому
тесту. Ошибка сохранена как `branch-acceptance-wrong-path.*`; затем тест
запущен из handoff и прошёл 2/2. После изменения только имени proof-поля
сквозной smoke повторён и прошёл; предыдущая запись сохранена отдельно.

## Ограничение и следующий шаг

Журнал Graph writer сохраняет снимки, но не доверенное `recordedAt` для RDG.
Время файлов не заменяет commit time. Поэтому `knowledgeTimeVerified=false`,
`twoTimeAsOfResolved=false`, `historicalT1KnowledgeVerified=false`.
Запросы `knownAt/effectiveAt` отклоняются. Даже точный SHA не доказывает
личность человека, реальность события или полноту исторического контекста.
Accepted future baseline и event-attest также не реализованы.

Следующий технический шаг — добавить доверенную временную историю RDG в
штатную точку записи и проверить пары `knownAt/effectiveAt` вместе с точной
версией Plan и ветвью. Пока нельзя превращать выбор сценария в фактический
outcome или выдавать historical Gendocen valid. Исторические v4.1/P0/P1
и предыдущие checkpoints не переписывались. [WR delta](WR-DELTA.md).

В проекте нет `.git`. `SELECTED-DIFF.patch` — сравнение выбранных before-копий,
а не Git diff всего проекта. Изменения и SHA перечислены в `SOURCE-HASHES.json`.
