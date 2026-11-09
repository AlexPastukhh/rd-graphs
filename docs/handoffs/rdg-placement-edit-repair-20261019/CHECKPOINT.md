# CPW-RDG-PLACEMENT-EDIT-REPAIR-20261019/v1

Дата среза: 2026-10-19, Asia/Bangkok.
Target: PR-01 из [R-RDG-LARGE-STEPS-20261019-01/v1](https://github.com/AlexPastukhh/forfiles/blob/813be44ebb626ac126c5c47813c1695664657e16/artifacts/2026-10-19/final-review-rdg-large-steps-r-rdg-large-steps-20261019-01-v1.md).
Owner: /workspace/repos/rd-graphs. Viewer source 2.2.1.
Статус реализации: **Candidate, локально проверено; Stage 4 NOT ACCEPTED**.
Решение PR-01 принято прямым указанием пользователя «исправь» после review.
Это commit решения к исполнению, не Git commit, не установленный Windows и не
whole-version acceptance.

## Результат

F-P-01/F-P-02 устранены и проверены в локальном ручном адаптере. Изменение даты
сохраняет исходящие связи других шагов, deadline и параметры существующих правил.
Предшественник меняется или снимается отдельно, с сохранением minDelayDays.
Исходные Action-instance, owners, расчёт завершённости и полный replace-контракт
Plan API не менялись.

GUI перечитывает дату и порядок при выборе другого сохранённого размещения,
показывает deadline/strength/интервал и блокирует редактирование правил, которые
не может представить без потерь. Эти правила остаются доступными полному API.

Исторический Final Review v1 сохранён. Его Findings были unresolved для source
2.2.0; вывод ниже относится к проверенному source 2.2.1.

## Findings и исполнение PR-01

| Canonical Finding / Proposal | Фактический исход этого среза |
|---|---|
| F-P-01: правка даты A теряла B после A либо получала ACTION_STEP_NOT_PLACED | resolved в локальном scope: связь сохранилась при наличии даты у B и при одном лишь порядке; дата A изменилась успешно. |
| F-P-02: правка notBefore удаляла deadline и ослабляла hard до soft | resolved в локальном scope: deadline, strength, basis и Graph ref сохранены; меняется только запрошенная дата. |
| PR-01 | committed прямым поручением пользователя; реализован и проверен в указанном scope. Native browser/Windows acceptance не следует из этого результата. |

## Что изменено

- Helper использует прежний step/ref при правке размещения. Отсутствующее поле
  запроса сохраняет прежнее условие; явная пустая дата снимает только notBefore,
  явный пустой afterStepId — только входящее предшествование.
- Исходящие sequence-связи сохраняются. При неизменном предшественнике Helper
  не отправляет ненужную полную замену sequence. При смене предшественника
  сохраняет minDelayDays и исходящие связи.
- Не редактируемые timeConstraints сохраняются; существующий notBefore
  сохраняет strength/basis. Новое простое правило по-прежнему имеет soft strength.
- Полный Plan API по-прежнему трактует явно переданный sequence/timeConstraints
  как replace. Изменение ограничено адаптером ручной команды.
- Несколько notBefore, несколько входящих предшественников либо не дневная
  точность даты не превращаются в простое правило. Для UI-запроса Helper
  возвращает HELPER_COMPLEX_PLACEMENT_USE_FULL_API до записи; некорректный формат
  новой даты — HELPER_DATE_ONLY_USE_FULL_API. Полный API остаётся доступен.
- Выбор размещения перезагружает поля и варианты предшественников. Другие
  размещения той же сущности не исключаются из допустимых предшественников;
  сам редактируемый step исключён.
- Viewer собран с общим UI-модулем; source version 2.2.1. Установленный
  Tampermonkey не обновлялся.
- Два прежних acceptance-набора получили необязательный
  RDG_WORKFLOW_TEST_LOG_DIR. Этот прогон записал GUI-логи в новый checkpoint,
  не перезаписав исторические evidence-файлы прежних пакетов.

## Проверки и evidence

Первый адресный прогон выявил ошибку нового test fixture: полный Plan edit
не передавал next revision. Исправлен fixture по существующему CAS-контракту;
API не ослаблен. Финальный набор содержит **7 Python tests**, все прошли:
[placement-last.log](placement-last.log).

Проверены: исходящие связи с датой B и только порядком; deadline/hard/basis
и observedGraphRevision; явная смена/снятие порядка с minDelayDays; снятие
только показанной даты; несколько правил, precise time и несколько предков
с отказом без записи; CAS, denied plan.edit, exact retry; настоящий
UI controller → live Helper → guarded writers. DOM имитируется.
[Финальный живой controller](live-controller-final.log).

[Общий относящийся к изменению прогон](regression-results.json):
**74 Python tests** в шести suites:
7 placement + 13 manual Helper + 13 workflow + 19 cross-file +
5 temporal placement + 17 Plan owner. Все прошли.
[Общий Node run](node-all.log): **417 cases, 414 PASS, 0 FAIL, 3 SKIP**.
Пропуски требуют live Helper и отдельно выполнены внутри перечисленных
Python suites: обычный manual через HTTP/файлы, cross-owner и новый placement.
Числа вложенных прогонов не складываются в число уникальных тестов.

После последнего уточнения выбора предшественника между размещениями одной
сущности адресно повторены:
- весь placement Python suite: 7/7, включая настоящий Helper/writer;
- [UI tests](ui-final.log): 7 PASS, 0 FAIL, 3 SKIP;
- Python AST выбранных файлов, JS syntax, идемпотентная сборка встроенного
  модуля и [Viewer smoke](viewer-smoke-final.log): PASS.
[Финальные проверки](final-checks.json).
Весь общий прогон после этого узкого UI-уточнения не повторялся.

Независимые исходные counterexamples review сохранены отдельно; их historical
assertions BUG REPRODUCED не переписаны. В этом срезе выполнены копии с ожидаемым
исправленным результатом:
[порядок](probe-placement-fixed.log),
[deadline/strength](probe-constraints-fixed.log).
Обе исходные ситуации правки порядка и ситуация правки ограничений теперь
дают ожидаемый результат. Это verification исправления, не одна лишь зелёная
проверка прежнего defect assertion.

## Версия, сохранение и границы

Перед правкой повторно подтверждены актуальный путь, RW mount и разрешения.
Все 32 SHA-256 review target/dependencies совпали. .git отсутствует; git status
недоступен (128). Поэтому выбранный baseline сохранён в
[BASELINE.json](BASELINE.json) и before/, итог —
[SOURCE-HASHES.json](SOURCE-HASHES.json),
[SELECTED-DIFF.patch](SELECTED-DIFF.patch),
[DIFF-STAT.json](DIFF-STAT.json).
Код и документация перечитаны после записи; ссылки и хеши проверены.
Выбранных файлов 14: 13 существовавших и один новый test suite.

Реальные пользовательские графы и Plan не правились; тесты использовали
временные синтетические owners и существующие grants внутри fixtures.
Нет Git commit/push, публикации рабочего проекта, Windows установки,
новых mounts/ACL, owner GUI/clipboard или общих сервисов.

Scope проверки: локальный Candidate workflow. Native picker, настоящий
установленный браузер Windows/G2 и полный новый Gendocen context остаются
непроверенными. Исторический review и прежние checkpoints не обновлялись
задним числом. Следующий gate текущего плана — настоящий ручной Windows/G2
прогон на эффективных гостевых правах; Stage 4 не принят.
