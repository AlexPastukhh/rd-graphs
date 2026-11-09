# WR delta — event context и Gendocen v1

Владелец WR-01..53 — baseline v4.1. PR-P1-01..05 остаются CANDIDATE.
**Stage 4 NOT ACCEPTED.**

| WR | Статус | Новое локальное доказательство | Открытая граница |
|---|---|---|---|
| WR-29 | PARTIAL | Стабильный event resource ID; отдельные current/fixed-knownAt identity и полный набор producer/declaration/subscriptions | Совместная coverage Plan/RDG/lifecycle/event |
| WR-47 | PARTIAL | Технические attestation/review/correction меняют Gendocen review, конфликт остаётся явным | Trusted event source и независимая проверка содержания evidence |
| WR-52 | PARTIAL | Поздние записи не меняют раннюю event-проекцию и её receipt; stale context отклоняется реальным движком | Полный historical Plan/RDG resolver и фактический пользовательский T1 |

Новый runtime proof ограничен event context. Dependency `valid` не
превращается в `factualEventVerified` и не выбирает RDG Action.
