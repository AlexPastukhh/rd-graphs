> **СТАТУС: АРХИВ / ИСТОРИЧЕСКАЯ РАЗРАБОТКА — НЕ ДЕЙСТВУЮЩИЙ КОНТРАКТ.** Включая файлы с именами `CONTRACT`, `PLAN`, `STAGE`, `PILOT` и со словом «актуальный» в тексте. Новый чат должен использовать [единую текущую спецификацию](RDG-CURRENT-STATE.md); ниже сохранены прежние эксперименты, решения и протоколы.

# Stage 2 — типизированные Findings в существующем QRPE (первый реализационный срез)

**Статус:** локальный opt-in pilot, **не полный FR-07/PR-SEM-01 acceptance**. Связь с Candidate Pre-work v3: typed Findings F-P/F-R/F-U/F-O; работа через Graph API с отдельными полномочиями; T1 immutable; Temporal Plan — независимый источник контекста. Никакой новый глобальный реестр Findings не создаётся.

## Почему на базе QRPE

В RDG QRPE принадлежит соответствующему R/Option/Decision/Action и уже имеет `id`, `text`, `status`, `statusHistory`. Его статус отвечает на вопрос, открыт ли материал/вопрос и что с ним произошло, **не** означает принятие решения и не является состоянием Proposal.

**Typed Finding** — ровно запись в существующем `node.qrpe[]` с дополнительными полями:

- `findingType`: `F-R` (предположительный риск), `F-U` (неопределённость между реальными альтернативами), `F-O` (возможность улучшения). `F-P` означает **подтверждённую текущую проблему**, поэтому **в этом пилоте запись F-P запрещена**: cryptographic hash, текст и даже hard deadline в candidate Plan не проверяют объективную проблему. Отдельный verified-current-evidence/authority gate ещё предстоит определить.
- `findingScope`: `CURRENT` или `UPSTREAM`; temporal future leads по умолчанию предлагаются как `UPSTREAM`, не как установленная проблема проекта.
- `questions[]`, `evidenceRefs[]`, `proposalRefs[]`: независимые от статуса QRPE строки для последующей проверки. Отсутствие evidence допускается для исследовательского риска/возможности и **не должно маскироваться под verified**. `proposalRefs` — лишь ссылки, не создание/принятие Proposal.
- Только для `F-U` — `alternatives[]` с как минимум двумя разными названиями. Валидатор проверяет форму, **не доказывает жизнеспособность альтернатив**.
- Необязательный `temporalContext`: `{planId,planRevision,stepId,branchId,outcome,dependencyDigest,status:"candidate"}`. Это provenance сценария, **не** ссылка на доказанную реальность. Поля `selected/preselected/performed/confirmed` не разрешены.
- Новая запись начинается `status:open`; существующий `transition_qrpe` ведёт `statusHistory` и, для material transition, проверенный технический receipt. Для изменения сути/типизации Findings и привязки к Plan **пока нет отдельной операции ревизии**; не переписывать историю T1.

## Права и writer

Патч `{op:"append_finding",targetId:"A1",finding:{...}}` добавляет типизированную запись в QRPE R/Option/Decision/Action. В bearer opt-in режиме нужно отдельное разрешение **`graph.append_finding`** на конкретный graphFile. Наличие `graph.append_qrpe` не даёт права создать typed Finding: `append_qrpe` с `findingType` отклоняется. Попытка ввода `F-P` без независимого confirmed-evidence контракта также отклоняется. Ошибка до записи не меняет ревизию, файл, индекс или событие. Обычный untyped QRPE остаётся совместимым.

Упоминание Action/Decision в Finding само **не** выполняет `select_action`/`select_option`, не скрывает альтернатив и не означает достигнутую цель. Дополнительный Finding, созданный **после** выбора, не переписывает `selectionBasis` и T1. Изменение статуса Findings — QRPE transition, а не Decision event. `Proposal` и `Action` — отдельные сущности с собственным lifecycle.

## Temporal Plan → черновики для review

Stage 3P (`tools/rdg-temporal-impact.py`) формирует `readOnly` report. Следующая команда преобразует **только** обнаруженный кандидатный конфликт сроков в черновик исследовательского `F-R`. Она **ничего не записывает**:

```bash
python3 tools/rdg-finding-drafts.py --impact-report /tmp/temporal-impact.json
```

Каждый `reviewDrafts[]` содержит `targetGraphFile`, `targetActionId`, `suggestedFinding`, исходные сравнения, `reviewStatus: "draft-only-not-verified"` и `commitAllowedAutomatically: false`. В `committedFindings` и `acceptedProposals` всегда пусто. Без внутреннего временного конфликта шаблон `F-R` не создаётся. Перед дальнейшим `append_finding` нужен осмысленный review источников Plan, ветви, реальных обстоятельств и полномочия пользователя/чата. Автоматическое создание новых канонов по строкам temporal deadline также не разрешено.

## Тесты и ограничения

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-bearer-package.integration.test.py -v
PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-temporal-impact.test.py -v
```

Первый набор создаёт полностью изолированный временный RDG writer/authority: отдельная выдача права, успешная запись F-R, отказ через `append_qrpe`, запрет F-P, F-U alternatives, `transition_qrpe` с историей, сохранение T1 при дописывании F-O. Второй проверяет Temporal Plan → F-R **draft only**, правильную ветвь, отсутствие ложных Finding и read-only invariant.

**Ещё не сделано:** подтверждение и запись F-P по проверяемым current evidence; полноценный цикл Proposal/Action, команды ревизии содержимого typed Finding, автоматизированная оценка положительных/отрицательных канонов по ситуации, межграфовая семантическая доказательность `proposalRefs`, настоящий Gendocen runtime и installed Helper/Viewer. Текущий grant-store opt-in, не production. Полнота Stage 2 **не утверждена**.
