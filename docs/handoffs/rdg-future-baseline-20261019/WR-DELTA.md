# WR delta — технический будущий baseline

Полный владелец WR-01..53 — baseline v4.1. PR-P1-01..05 остаются
CANDIDATE. **Stage 4 NOT ACCEPTED.**

| WR | Статус | Новое локальное доказательство | Открытая граница |
|---|---|---|---|
| WR-45 | PARTIAL | Отдельный `plan.accept` закрепляет точную candidate-версию; новая редакция Plan не меняет запись | Human acceptance, полный lifecycle и UI |
| WR-51 | PARTIAL | `plan.edit` не даёт `plan.accept`; запись и read grant разделены | Отдельный trusted event-attest actor/source |
| WR-52 | PARTIAL | Точная старая baseline-версия доступна после нового candidate; `knownAt` учитывает owner availability | Фактический T1, полный as-of и historical Gendocen |

P2-AC-08 только PARTIAL: техническая запись не доказывает авторизованное
человеческое принятие или неизменность реального T1.
