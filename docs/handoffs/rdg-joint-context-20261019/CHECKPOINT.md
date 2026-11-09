# Совместный context v1 — контрольная точка

**ID:** CPW-RDG-JOINT-CONTEXT-20261019/v1. **Статус:** Candidate.
**Stage 4 NOT ACCEPTED.** Исходники изменены в Fortis Repo
`/workspace/repos/rd-graphs` на Windows RW-mount. Runtime использовал
только временные синтетические roots. Пользовательские графы,
установленное Windows-приложение и G2 не проверялись. В проекте нет
`.git`; commit/push и публикация не выполнялись.

## Результат

`tools/rdg-joint-context.py` связывает lifecycle, долговечную применимость,
точный Plan, завершённые Graph snapshots и один совместимый event occurrence
по `knownAt/effectiveAt`. Candidate выбирается из applicability history.
Accepted-future требует точный `baselineStateRevision`; его assertion и
предки читаются отдельно от новых candidate records. Withdrawn baseline,
gap, конфликт, несовместимый Plan pin и отсутствие временного доказательства
дают отказ без current fallback. Четыре Plan-root owners читаются под общим
shared lock; незавершённый journal блокирует bundle.

Исторический Graph proof сохраняет прямой after-journal к cutoff; поздние
before-images не меняют старую проекцию. Контракт `rdg-joint-review/v1`
проверяет девять subscriptions и повторно сверяет snapshot SHA, selection,
event context и assessment. Неизвестные factual flags, пропущенные группы
и подменённые snapshots отклоняются.
[Формат и ограничения](../../guides/RDG-JOINT-CONTEXT-PILOT.md).

Scope ограничен одним Plan/branch/occurrence. Baseline owner пока не задаёт
собственные effective-интервалы: автоматический выбор между accepted states
не реализован. `completeApplicableContextVerified=false`,
`automaticBaselineEffectiveSelectionComplete=false`,
`factualEventVerified=false`, `historicalT1KnowledgeVerified=false`.
Gendocen `valid` относится к документу явно указанного bundle.

## Проверки и следующий gate

**49 адресных тестов PASS:** 12 новых joint context/coverage,
9 applicability, 9 baseline, 13 exact history, 6 event projection.
**Реальный синтетический Gendocen smoke PASS:** 15 CLI-запусков,
штатный изолированный Graph writer и настоящие Plan/sidecar writers.
Ранний candidate bundle и exact baseline сохранились после поздних
Graph/Plan/applicability/event записей. Новая реконструкция потребовала
review; stale context отклонён без новой receipt, новый конфликтующий
запрос отвергнут. Sources и review Markdown при чтении не менялись.
[Команды и логи](CHECKPOINT.json).

При смене resource ID smoke сохраняет прежний bundle в immutable archive:
старые receipts должны иметь доступное прежнее основание. Перезапись его
другим resource ID давала `invalid`; сохранение истории даёт ожидаемый
`review_required` новой реконструкции.

P2-AC-08/15/16/18/20 остаются PARTIAL; суммы — 7 локальных PASS,
12 PARTIAL, 1 OPEN. Следующий срез: P2-AC-04, явная lifecycle applicability
принятого baseline, затем расширение scope и совместные concurrent
write/revoke/recovery. Trusted источник факта — отдельный предметный gate.
[План](../../guides/RDG-CURRENT-EXECUTION-PLAN.md) · [WR delta](WR-DELTA.md).

[SELECTED-DIFF.patch](SELECTED-DIFF.patch) охватывает выбранные файлы от
before-копий и `/dev/null`; это не Git diff всего проекта. SHA источников
и evidence сохранены отдельно. Прежние checkpoints и архив v4.1 не переписывались.
