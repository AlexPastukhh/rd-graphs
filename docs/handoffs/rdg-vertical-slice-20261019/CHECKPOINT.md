# P0.1 + candidate Plan owner — контрольная точка

**ID:** CPW-RDG-P01-P2-CANDIDATE-20261019/v1. **Статус:** Candidate.
**Stage 4 NOT ACCEPTED.** Результат изменён и проверен в Fortis Repo;
установка Windows и публикация не выполнялись.

## Сделано и проверено

P0.1 закрывает F-P-PROGRESS-01: отсутствие вычисляемой группы в producer
declaration блокирует построение проекции, в том числе без Action steps.
Для F-R-PROGRESS-02 выбран консервативный контракт: title Action и всех
относящихся к оценке шагов/событий участвует в review dependency.
Это локальное исправление; полноценный future evaluator остаётся открытым.

Добавлен отдельный candidate-only Plan writer: явный root/owner/path binding,
Plan-scoped grants, CAS, идемпотентность, полные версии с recordedAt и hash-цепочкой,
подготовленный journal, проверка отзыва прав и восстановление после сбоя.
Существующие authority stores автоматически не расширены.
[Границы и команды](../../guides/RDG-TEMPORAL-PLAN-OWNER-PILOT-P2.md).

Сквозной synthetic прогон реального Gendocen 0.1.0.dev25 подтвердил:

- изменение A2 требует review только A2; общий срок и перестановка ветвей — A1/A2;
- противоречивые кандидатные сроки дают два черновика F-R без автоматического Finding/Action;
- исходные T1/selectionBasis и точная версия Plan 1 сохраняются после пяти версий;
- редактор Plan не может выбрать Action; событие остаётся expected;
- stale review и незавершённый recovery блокируют подтверждение.

## Результаты

**109 Python tests PASS, 405 Node tests PASS, 3 real-engine smokes PASS.**
Команды, длительности и выбранные доказательства: [CHECKPOINT.json](CHECKPOINT.json).
Каждый запуск имеет `*-result.json` и полный `*.log`. В Python-сумме учтены
10 suites, включая два исторических branch acceptance tests; повторные запуски
не суммируются. Три engine smokes — runtime, legacy T1 и owned Plan/T1.

Первый owned smoke остановился на AUTH_DELEGATION_CEILING: bootstrap временного
стенда не получил опциональный Plan режим. Исправлен только этот opt-in bootstrap;
проверка delegation ceiling сохранена. Ошибка сохранена отдельно в
`owned-t1-slice-before-fix.*`; повтор прошёл. Успешные сохранённые прогоны после
обрывов связи не повторялись без причины. Все экспериментальные записи —
во временных synthetic roots; пользовательские graph.json не редактировались.

## Ограничения и дальше

P2 выполнен частично: create/edit/branch/read и точные snapshots самого Plan.
Accepted future baseline, revise/withdraw, trusted user identity, фактические
события/attestation/verification не реализованы. Bearer receipt подтверждает
техническую запись, а не личность человека или факт предметного мира.
Plan schema v1 по-прежнему candidate-only; Proposals PR-P1-01..05 — CANDIDATE.

Следующий независимый технический срез — разрешение точных Plan+RDG snapshots
для исторической оценки с явным отказом при отсутствии источника. Нельзя считать
observedGraphRevision доказанным snapshot или подставлять текущий граф. Для
accepted baseline и фактических событий нужно отдельно сохранить разбиение
write/accept/event-attest/select и проверить доверенный источник. До этого
исторический T1-as-of и production acceptance не заявляются.

Полный baseline v4.1, P0, P1 и review остаются историческими неизменными пакетами.
См. [WR delta](WR-DELTA.md), `SELECTED-DIFF.patch` и `SOURCE-HASHES.json`.
В этом каталоге проекта нет `.git`: Git diff/status/commit/push не заявляются.
Выборочный diff сравнивает только сохранённые before-копии изменённых файлов;
новые файлы включены целиком. Это не diff всего проекта.
