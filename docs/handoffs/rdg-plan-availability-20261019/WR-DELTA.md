# WR delta — свидетельство доступности Plan

Полный владелец WR-01..53 — baseline v4.1. Это уточнение локального
Candidate-пилота, без production acceptance. **Stage 4 NOT ACCEPTED.**

| WR | Статус | Новое доказательство | Открытая граница |
|---|---|---|---|
| WR-45 | PARTIAL | Квитанция Plan связана с owner path, revision и `recordDigest`; сохраняется после долговечной записи Plan store и индекса | Production owner, внешний trust и accepted future lifecycle |
| WR-48 | PARTIAL | Последний Plan имеет доступность `availableBy`; старые записи без квитанции используют следующий guarded edit | Исторический полный RDG-контекст и независимая аттестация часов |
| WR-52 | PARTIAL | `knownAt` для последнего Plan 1 и Graph 3 прошёл в real Gendocen synthetic smoke, поздние изменения не меняют pinned impact | `effectiveAt`, полнота применимого контекста, historical Gendocen as-of |

Квитанция ограничивает время доступности версии. Она не утверждает, что Plan
был последним или фактически применимым на дату, и не подтверждает событие.
PR-P1-01..05 остаются CANDIDATE.
