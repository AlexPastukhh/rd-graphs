# Проверка плана и продвижения RDG + Temporal Plan

**ID:** R-RDG-PLAN-PROGRESS-20261019/v2. **Статус:** Candidate review.
**Вердикт:** направление согласовано с v4.1; ближайший маршрут требовал
ограничить scope и задать условия завершения. План исправлен.
**Stage 4 NOT ACCEPTED.** Это проверка в той же среде, не independent acceptance.

## Findings — в порядке важности

1. **F-R-PLAN-01 — размытое завершение P2.** До правки раздел «Следующие
   локальные срезы» одновременно требовал расширять inventory owners,
   события и lifecycle, а пользовательский сквозной сценарий относил к P5.
   У этих расширений не было ограниченного общего результата. Это создаёт
   риск продолжать частичные пилоты, откладывая смысловую проверку системы.
   **Исправлено в плане:** один локальный S-TEMP → S-DEP-REP в существующем
   scope, затем P3 на нём; полный расширенный scope остаётся отдельным gate.
   Изменён порядок исполнения, определения Need / FR / Desired Scenario / SRU сохранены.

2. **F-U-PLAN-02 — accepted lifecycle пока не имеет полной effective-семантики.**
   Baseline records хранят state revision и recordedAt, но не собственную
   историю effective-интервалов. Joint resolver требует точный
   baselineStateRevision. Это заявленная граница реализации, а не обнаруженный
   автоматический выбор неверной версии. Основание:
   [baseline owner](../../../tools/rdg-future-baseline-owner.py),
   [joint resolver](../../../tools/rdg-joint-context.py),
   [контракт пилота](../../guides/RDG-JOINT-CONTEXT-PILOT.md).
   **Открыто:** определить Candidate-правила связи applicability, replace/withdraw
   и двух времён; затем реализовать и проверить их в том же scope.
   Запись этого шага в план не устраняет пробел реализации.

3. **F-R-PLAN-03 — хранение прежних bundles пока находится в smoke-runner.**
   [CLI joint context](../../../tools/rdg-joint-context.py) выводит JSON;
   [smoke-runner](../../../tools/rdg-joint-context-smoke.py) отдельно архивирует
   прежний resource ID. Последний checkpoint подтверждает: если удалить
   старое основание receipt при смене ID, Gendocen получает invalid.
   Это корректно документированная интеграционная зависимость, но прежний
   план не выделял её как проверяемый deliverable обычного consumer.
   **Уточнено в плане:** до такого consumer нужны сохранение старых bundles,
   повтор и проверка сбоя при сохранении. Рабочий exporter этим review не создан.

**Несогласованность документации исправлена:** README называл срез доступности
Plan «текущим» и оставлял historical Gendocen без оговорки о новом joint scope.
Теперь он различает последнюю реализацию, прежние срезы и полные открытые gates.
[Отобранный diff](SELECTED-DIFF.patch) показывает правки.

## Как идём по плану

P0/P0.1 имеют локальные доказательства исправления branch dependency и coverage.
P1 остаётся Candidate-контрактом. В P2 появились реальные Plan/sidecar writers,
точная история, два времени и совместный Gendocen context. Это существенное
техническое продвижение, но завершённого полного пользовательского пути нет.
P3/P4/P5 частично подготовлены, P6/P7 не начаты.

Таблица P2 корректно содержит **7 локальных PASS, 12 PARTIAL, 1 OPEN**.
Это не процент готовности. P2-AC-04 остаётся OPEN: существующие тесты двух
разных Actions не доказывают два вхождения одного Action в разных cases.
Общие joint recovery/race проверки также не заменяются per-owner тестами.
Статусы таблицы и PR-P1-01..05 не повышены этим review.

## Проверки и Evidence Gaps

Свежие **35 тестов PASS**: Plan owner 17, joint context 12, исторический
branch acceptance 2, coverage guard 4. Branch acceptance и coverage guard
включают реальный Gendocen. [Команды и логи](test-results.json),
[повторяемый runner](run-focused-checks.py). Не складывать 35 с прежними
49: наборы частично пересекаются.

Проверены SHA последних 8 файлов, 22 dependencies и 16 evidence-файлов:
расхождений до правки документации нет. Архив v4.1 не изменён.
[Проверка целостности и before-хеши](BASELINE-AND-INTEGRITY.json).
Прежние 49 тестов и joint smoke 15 CLI подтверждены сохранёнными логами
и хешами; сам joint smoke в этом review не повторялся.

Review охватывает текущий план, P1/P2 matrix, v4.1 handoff/WR ledger,
последний checkpoint, связанные source paths и выбранные tests.
Это не новый полный аудит всех 53 WR и mutation paths. Trusted actor/source,
достоверность evidence, фактический пользовательский T1, production owner,
Windows/G2 install и публикация остаются непроверенными.

## Результат правок и ближайший шаг

Изменены только README и текущий план; добавлены материалы этого review.
Runtime-код, пользовательские графы, Proposals и прежние checkpoints не менялись.
В проекте нет .git; diff построен по before-копиям выбранных файлов.
Commit/push, установка и публикация не выполнялись.

Ближайший исполняемый шаг — acceptance-test P2-AC-04. Затем Candidate-контракт
lifecycle applicability и его реализация; совместная безопасность owners;
обычный локальный путь с сохранением bundles; P3 на том же сценарии.
[Исправленный план](../../guides/RDG-CURRENT-EXECUTION-PLAN.md).
