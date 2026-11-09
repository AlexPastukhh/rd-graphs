# WR delta — модель двух времён

Полный владелец WR-01..53 — baseline v4.1. Статусы ниже остаются PARTIAL;
PR-P1-01..05 остаются CANDIDATE. **Stage 4 NOT ACCEPTED.**

| WR | Статус | Новое локальное доказательство | Открытая граница |
|---|---|---|---|
| WR-47 | PARTIAL | Неаттестованный `eventClaim` остаётся заявлением и не вызывает выбор Action | Trusted attestation, verification и factual branch |
| WR-48 | PARTIAL | Exact Plan/RDG pins проверяются до модельного отбора; knownAt использует post-write availability | Owner history применимости, другие контексты и независимый clock trust |
| WR-52 | PARTIAL | Ранняя дата знания исключает позднюю поправку; поздняя допускает её как candidate реконструкцию; конфликт отклоняется | Долговечная correction chain, полный `effectiveAt` resolver и historical Gendocen |

Проверка P2-AC-13/15/16 переведена только в PARTIAL: assertions о
применимости заданы клиентом в read-only запросе. Их время и исход нельзя
считать историческим фактом без owner journal и проверенного источника.
