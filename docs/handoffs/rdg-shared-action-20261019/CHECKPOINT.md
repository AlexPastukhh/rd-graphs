# Два вхождения одного Action — контрольная точка

**ID:** CPW-RDG-SHARED-ACTION-20261019/v1. **Статус:** CANDIDATE.
**Stage 4 NOT ACCEPTED.** Изменено в Fortis Repo на Windows RW 9p mount
`/workspace/repos/rd-graphs`. В проекте нет .git и AGENTS.md.
Все записи тестов выполнялись во временных синтетических roots.

## Результат и границы

Закрыт локальный P2-AC-04: разные Plan steps разных cases могут ссылаться на
один RDG Action. Plan writer и reader сохраняют разные step IDs и membership;
в RDG остаётся один Action. Байты RDG, candidate statuses и events не меняются.
Повторное использование одного step ID в двух cases отклоняется без записи;
точный исходный Plan snapshot сохраняется после последующих edits.

Новый acceptance обнаружил дефект общего регистратора: прежняя конфигурация
дважды регистрировала review одного Action. Реальный Gendocen отказал на sync:
`semantic rule already registered for target file://review/A1.md`.
[До исправления](before-fix.log) — 1 PASS, 1 FAIL; exit 1 означает дефект,
а не успешное выполнение acceptance.

`build_action_contract` объединяет подписки всех вхождений Action в одном
Plan/graph scope. `project_config` регистрирует одно правило на Action.
Набор step IDs сверяется с полным набором ActionRef этого graph owner/path/ID;
пропуск вхождения даёт `ACTION_OCCURRENCES_INCOMPLETE`, повтор пары отклоняется.
Низкоуровневый `build_contract` одного вхождения сохранён.
Текущий контракт — `rdg-temporal-review/v2`; новый lifecycle в него не добавлен.
[Обновлённое руководство](../../guides/RDG-GENDOCEN-DEPENDENCY-COVERAGE-P0.md).

## Проверки

**71 тест PASS:** новый acceptance — 2; dependencies — 14; coverage guard — 4;
Plan owner — 17; Plan reader — 12; resources — 10; joint context — 12.
[Новый acceptance](shared-action-result.json) выполнил **21 запуск реального
Gendocen 0.1.0.dev25**. Срок первого или второго вхождения и смена membership
требуют review A1; контрольный A2 сохраняет valid. Косметическая перестановка
сохраняет valid. Неполная конфигурация отклоняется без новой receipt.
После восстановления полного контракта сохранённый review снова valid.
Sources RDG и review Markdown не меняются consumer.
[Регрессия](regression-results.json); её реальные engine-запуски входят в
соответствующие tests и не прибавляются к числу 21 этого acceptance.

Scope — один candidate Plan, одна условная ветвь и один RDG graph.
Current-projection proof не закрывает accepted lifecycle applicability,
многособытийную полноту, trusted event source или фактический пользовательский T1.
Joint smoke 15 CLI, все 53 WR и полная Node regression здесь не повторялись.
Новые проверки не означают independent production acceptance.

## Передача

P2: **8 локальных PASS / 12 PARTIAL / 0 OPEN**. P2-AC-04 повышен только для
указанного scope; остальные строки не повышены. PR-P1-01..05 остаются CANDIDATE.
Следующий исполняемый шаг — Candidate-контракт и реализация lifecycle
applicability по двум временам; затем совместная безопасность owners и обычный
локальный consumer с сохранением bundles. [План](../../guides/RDG-CURRENT-EXECUTION-PLAN.md).

[Выбранный diff](SELECTED-DIFF.patch) построен по before-копиям; это не Git diff
всего проекта. [Хеши и metadata](CHECKPOINT.json). Runtime-код, тест и три
документа изменены; прежние checkpoints и v4.1 ZIP сохранены.
Установку Windows/G2, пользовательские графы, commit/push и публикацию не выполняли.
