# RDG — контекст групп ведёт в Graph

> **СТАТУС: correction handoff-срез, 2026-10-26, Asia/Bangkok.** Продолжает `rdg-action-projection-and-group-labels-20261026`. Backend и live owners не изменялись.

## Последнее уточнение

Decision Groups не являются самостоятельными шагами Plan или History. В дорожке нет отдельного реестра групп и нет карточек групп как плановых сущностей. Группа остаётся ограничением выбора в Graph и контекстом Decision/Action.

## Правило Graph

- Graph содержит Requirements, Decisions, Canon, Context и membership-связи групп.
- Каждая membership-связь направлена только `Requirement → Decision`.
- Стрелок `Decision → Decision` нет.
- Группа показывается коротким `G#` на membership-связи; несколько групп объединяются как `G1 / G2`.
- Индикатор amber означает `selectionRequired`, violet — `mutuallyExclusive`; пустой кружок означает, что свойство выключено.

## Навигация из контекста

Ссылки на группы в Action details, History/Plan causal context и подписи membership-индикаторов интерактивны. Клик выбирает родительский Requirement, панорамирует к месту использования группы без изменения масштаба, показывает локальный Graph-фокус и раскрывает подробности группы в боковой панели: политика и участники.

## Prototype

Основной файл: `tests/visual/rdg-ui-prototype.html`. Actions остаются отдельными записями History/Plan; group refs хранятся в Action context. В Plan показываются только реальные Actions, Decisions и Requirements в порядке/ветвях.

Синтаксическая проверка и `RDG_GROUP_CONTEXT_SMOKE` пройдены. Browser manual pass не выполнялся.
