# WR delta — exact-reference pilot

Полный владелец WR-01..53 — baseline v4.1. Статусы ниже унаследованы из
предыдущего среза и уточняют только новые доказательства. Independent
production acceptance не заявлено.

| WR | Статус | Новое доказательство | Открытая граница |
|---|---|---|---|
| WR-31/50 | PARTIAL | Повторный branch acceptance 2/2, exact scenario resolver не подставляет current graph | Multi-event/future evaluator, historical Gendocen runtime |
| WR-45 | PARTIAL | Путь/identity/версия Plan и SHA связаны с RDG refs | Production owner и accepted future lifecycle |
| WR-47 | PARTIAL | Условный outcome остаётся сценарием оценки | Factual event/attest/verify |
| WR-48 | PARTIAL | Exact RDG journal snapshot по actionRef revision и hash | Полная история, источник knownAt, другие контексты |
| WR-49 | PARTIAL | Impact выбранной ветви оценивает точные графы read-only | Семантическое подтверждение Canon/Finding |
| WR-51 | PARTIAL | `graph.read` и `plan.read` проверяются отдельно от writer/selection; отзыв перед выдачей блокирует результат | Trusted identity, remote/OS boundary, accept/event rights |
| WR-52 | PARTIAL | Exact Plan 1 + Graph 3 сохраняют оценку после поздних изменений | RDG recordedAt, knownAt/effectiveAt и T1-as-of |
| WR-53 | PARTIAL | Локальный CLI | Installed timeline UI |

PR-P1-01..05 остаются CANDIDATE. **Stage 4 NOT ACCEPTED**.
