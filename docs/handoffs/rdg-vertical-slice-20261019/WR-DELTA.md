# WR delta к P1

Полный владелец WR-01..53: baseline v4.1. Здесь только изменение фактического
исполнения после P1 и review; остальные строки не переоцениваются.
Независимое полное production acceptance не доказано ни для одного WR.

| WR | Текущий статус | Новое доказательство | Что остаётся |
|---|---|---|---|
| WR-31 | PARTIAL | P0.1 producer completeness, semantic title и owned branch swap | Полный evaluator, несколько условий/событий |
| WR-45 | PARTIAL | Локальный candidate owner/path, CAS, неизменные версии | Canonical production owner, accepted lifecycle |
| WR-46 | PARTIAL | Прежний temporal subset, повторная регрессия | Новые units/calendars и полная выполнимость |
| WR-47 | PARTIAL | Ожидаемое событие не становится фактом при записи Plan | Actual event lifecycle и trusted verification |
| WR-48 | PARTIAL | Owner/path binding и exact Plan revision | Точные исторические RDG snapshots и полный resolver |
| WR-49 | PARTIAL | Versioned Plan → два черновика F-R без автозаписи | Полная семантика Canon/Finding, verified F-P |
| WR-50 | PARTIAL | Текущие owned projections, локальная A2 точность, общий срок/branch swap | Full history/multi-event semantic evaluation |
| WR-51 | PARTIAL (ранее OPEN) | Plan writer/authorizer, branch guard, revoke/race/recovery и запрет graph selection | Accept/event-attest lifecycle, доверенная идентификация |
| WR-52 | PARTIAL | Exact Plan history, recordedAt, revision 1 после пяти версий, T1 не переписан | knownAt/effectiveAt и исторический RDG resolver |
| WR-53 | PARTIAL | CLI/adapter pilot | Timeline UI и installed rollout |

F-P-PROGRESS-01 — исправлен локально, подтверждён отрицательными тестами.
F-R-PROGRESS-02 — риск пропуска title снят консервативным включением title
в смысловой контракт; display-only редактирование пока отдельно не выделено.
Статусы PR-P1-01..05 остаются CANDIDATE. **Stage 4 NOT ACCEPTED**.
