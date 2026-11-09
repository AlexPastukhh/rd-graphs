# WR delta — стадии события и guard старого consumer

Полный владелец WR-01..53 — baseline v4.1. PR-P1-01..05 остаются
CANDIDATE. **Stage 4 NOT ACCEPTED.**

| WR | Статус | Новое локальное доказательство | Открытая граница |
|---|---|---|---|
| WR-47 | PARTIAL | Claim/attestation/review хранятся раздельно; коррекция сохраняет историю, конфликт outcomes не выбирает ветвь | Trusted event source и фактическая независимая проверка |
| WR-51 | PARTIAL | `plan.edit`, `plan.event_attest` и opt-in `plan.event_verify` разделены; разные bearer grant IDs обязательны | Человеческая личность и доверенный путь ввода |
| WR-52 | PARTIAL | Квитанции `availableBy` исключают поздние claims/attestations на раннем `knownAt`; старый adapter даёт явный отказ на sidecars | Полный T1-as-of и исторический Gendocen на новом lifecycle |

P2-AC-18 только PARTIAL: adapter guard проверен, исторический runtime
для новых records пока не реализован.
