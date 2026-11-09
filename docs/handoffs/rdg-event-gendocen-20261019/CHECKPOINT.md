# Event context → Gendocen v1 — контрольная точка

**ID:** CPW-RDG-EVENT-GENDOCEN-20261019/v1. **Статус:** Candidate.
**Stage 4 NOT ACCEPTED.** Исходники изменены в Fortis Repo
`/workspace/repos/rd-graphs` на Windows RW-mount. Все runtime-записи
проверки использовали временные синтетические roots. Пользовательские графы,
установленное Windows-приложение и G2 не проверялись. В проекте нет
`.git`; commit/push и публикация не выполнялись.

## Результат

`tools/rdg-event-gendocen.py` добавляет отдельный явный ресурс и
контракт `rdg-event-review/v1`. Текущая проекция включает известные
records одного occurrence; фиксированная проекция включает только
records к `knownAt`. Режим/cutoff входят в resource identity.
Producer, декларация и восемь subscriptions проверяются до регистрации.
Пропуск группы, stale projection и неизвестные поля отклоняются.
Технические границы доверия остаются отдельной semantic dependency.

Новый runtime runner использует реальный Gendocen 0.1.0.dev25:
attestation, review, позднее исправление и конфликт требуют review текущего
event context. Другой occurrence не меняет его. Ранняя проекция и её receipt
остаются valid; stale review context отклоняется без новой receipt.
Consumer не меняет Plan, owner JSON или review Markdown.
[Формат и границы](../../guides/RDG-EVENT-GENDOCEN-PILOT.md).

`valid` здесь относится к dependency receipt документа event context.
`factualEventVerified=false`, `factualBranchResolved=false`,
`actionSelected=false`, `completePlanRdgContext=false`.
Полный historical Plan/RDG/lifecycle resolver и фактический T1 не доказаны.
Старый current-only Plan adapter сохраняет явный отказ для sidecars.

## Проверки и следующий gate

**22 адресных теста PASS:** 6 новых event projection/coverage,
13 event owner и 3 старого consumer guard.
**Новый реальный синтетический Gendocen smoke PASS:** 25 отдельных CLI
processes, 6 owner records, текущий и ранний event-review документы.
[CHECKPOINT.json](CHECKPOINT.json) содержит команды и ссылки на логи.
Предыдущие 88 тестов и полный набор 405 Node в этом срезе не повторялись.

P2-AC-15/16/18/20 остаются PARTIAL; текущие суммы — 7 локальных PASS,
12 PARTIAL, 1 OPEN. План уточнён: предметное доверие к источнику и
техническая реализация joint historical context — разные gates.
Ближайший технический срез связывает lifecycle, применимость, точные Plan/RDG
snapshots и event context на синтетической истории. Выбор реального источника
и проверка evidence нужны перед фактическим применением.
[Актуальный план](../../guides/RDG-CURRENT-EXECUTION-PLAN.md) ·
[WR delta](WR-DELTA.md).

[SELECTED-DIFF.patch](SELECTED-DIFF.patch) сравнивает выбранные файлы с
before-копиями и `/dev/null` для новых; это не Git diff всего проекта.
SHA источников и evidence сохранены отдельно. Старые checkpoints и архив v4.1
не переписывались.
