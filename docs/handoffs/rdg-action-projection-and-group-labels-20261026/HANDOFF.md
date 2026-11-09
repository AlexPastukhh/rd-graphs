# RDG — correction: Actions вне Graph, Groups на связях

> **СТАТУС: correction handoff-срез, 2026-10-26, Asia/Bangkok.** Продолжает `rdg-decision-action-layer-20261026`. Prototype исправлен по последнему уточнению пользователя.

## 1. Последнее уточнение пользователя

Actions в RDG не являются Graph-сущностями и не живут среди узлов Graph. Они существуют только как реальные записи работы в `History` и `Plan`.

Graph содержит:

- Requirements;
- Decisions;
- Decision Groups как ограничения выбора;
- Canon;
- Context и другие графовые справочные сущности.

Action хранит тип, свободный текст/контекст, ссылки на Requirements/Decisions/Groups и состояние выполнения, но не получает Graph-позицию, Graph identity и Graph edges.

## 2. Визуальные группы

Группа показывается короткой подписью на связи `parent → Decision`:

- `G1` или `G1 / G2` — только короткие идентификаторы на линии;
- подпись интерактивна;
- клик по подписи открывает подробности всех групп;
- подробности показывают родителя, `selectionRequired`, `mutuallyExclusive` и участников;
- обычная причинная стрелка и membership-подпись визуально различаются.

Если один Decision состоит в нескольких группах с одним и тем же parent, подписи объединяются в `G1 / G2`. Если parent разный, остаются отдельные подписи на соответствующих связях. Decision физически не копируется и не помещается в контейнер.

## 3. Что изменено в prototype

- Actions вынесены из `initialNodes` в отдельный `initialActions/actions` слой.
- Из Graph удалены Action nodes и `OPERATES_ON` edges.
- A1–A4 по-прежнему присутствуют в History/Plan как Action records.
- Клик по Action в History/Plan открывает Action details и ссылки на Graph targets; Graph viewport не подменяется Action-узлом.
- Low-level Actions можно скрывать из дороги настройкой; History facts остаются.
- Group labels строятся из `DECISION_MEMBER` relations и показывают только `G#`; подробности открываются через side panel.
- Overlapping membership G1/G2/G4 сохранена.

Backend, writers, current R/A contract и live owners не изменялись.
