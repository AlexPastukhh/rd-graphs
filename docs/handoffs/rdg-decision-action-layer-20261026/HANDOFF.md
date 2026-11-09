# RDG — handoff Decision + real Action layer

> **СТАТУС: новый handoff-срез, 2026-10-26, Asia/Bangkok.** Он продолжает `rdg-decision-model-transition-20261026`. Prototype обновлён ещё раз; backend и live owners не мигрированы.

**Prototype:** `tests/visual/rdg-ui-prototype.html`  
**Предыдущий handoff:** `docs/handoffs/rdg-decision-model-transition-20261026/HANDOFF.md`

## 1. Новое уточнение пользователя

`Decision` и `Action` — разные сущности.

- `Decision` — объект выбора/решения: его можно обнаружить, оставить `unselected`, выбрать `selected` и завершить `completed` после закрытия обязательной работы.
- `Action` — реальное действие, которое выполняет человек/AI и которое записывается в History/Plan.
- Action не должен быть замаскированным Decision. Он должен иметь тип, свободное название, свободный контекст и необязательные ссылки на Requirements, Decisions и Decision Groups.
- В Plan и History Actions должны быть одними из главных центральных элементов рядом с Decisions и Requirements.

Action type — типизированная подсказка для фильтрации/проверки, но не жёсткая структура текста. Пользователь может свободно написать, что сделать и в каком контексте.

Минимальные типы prototype:

- `discover_decision` — обнаружить вариант Decision;
- `discover_requirement` — обнаружить Requirement;
- `decide_acceptance` — решить, принимать Decision или оставить `unselected`;
- `select_decision` — выбрать Decision/Decisions с указанием групп;
- `rename_block` — низкоуровневое редактирование;
- `review_canon` — пересмотреть ориентиры Canon;
- `complete_requirement` — проверить закрытие Requirement.

## 2. Как Action меняет Decision

Action `decide_acceptance` содержит ссылку на Decision и свободный текст основания. При завершении Action он записывает `decision_selected` либо `decision_unselected`.

Action `select_decision` содержит ссылки на Decision и, если нужно, на одну или несколько групп. Перед завершением проверяются свойства групп:

- для `mutuallyExclusive=true` нельзя выбрать больше одного участника;
- для `selectionRequired=true` Action должен зафиксировать требуемый выбор;
- отдельное Decision может входить в несколько групп, и все их ограничения проверяются одновременно.

Action `discover_decision`/`discover_requirement` фиксирует появление объекта в рабочем рассмотрении. Наличие такого Action не означает принятия решения или закрытия Requirement.

`rename_block` — пример low-level Action. Он является настоящим действием и попадает в History/Plan, но пользователь должен иметь настройку скрыть low-level Actions из дороги, не удаляя их из истории.

Не вводить для каждого Action отдельный кодовый payload. Достаточно типизированного `actionType`, свободного `title/description/context`, `targetIds` и `groupIds`; конкретный смысл объясняется обычным текстом и ссылками.

## 3. Визуальная реализация Decision Groups

Группа не должна быть обычным Requirement/Decision-кружком и не должна физически владеть карточкой Decision. Из-за overlapping membership один Decision может находиться в нескольких группах.

В Graph prototype группа показана как отдельный **мета-слой**:

- пунктирный вертикальный rail/скоба с `G#` и краткими политиками;
- пунктирные линии членства от rail к обычным карточкам Decisions;
- обычные причинные связи R/D остаются отдельными сплошными стрелками;
- Action → target показан зелёной пунктирной операционной связью;
- один Decision может иметь несколько rails одновременно.

Это позволяет показать, что `D2` находится в `G1` и `G2`, а `D3` — в `G2` и `G4`, без копирования сущностей и без ложного вложения одного контейнера в другой.

В Plan/History группа дополнительно показана карточкой с:

- родителем группы;
- `выбор обязателен` или `можно не выбирать`;
- `взаимоисключаемые` или `можно выбрать несколько`;
- участниками и их Decision states.

Action-карточка показывает `Объекты Action` и `Группы Action` как боковые ссылки.

## 4. Что изменено в prototype

- Добавлен тип `action` с зелёной Graph-палитрой и отдельным `Action`-метаданным.
- Demo Graph теперь содержит A1–A4: обнаружение Decision, low-level rename, решение о принятии D5 и выбор в G1.
- Actions имеют `actionType`, `actionState`, `lowLevel`, `targetIds`, `groupIds` и свободный `context`.
- Action nodes связаны с Requirements/Decisions через `OPERATES_ON`.
- В Graph добавлены group rails и membership lines; DECISION_MEMBER больше не рисуется как обычная причинная стрелка.
- В Plan/History Actions отображаются рядом с Decisions/Requirements; для Action показываются тип, состояние, объекты и группы.
- В настройках дороги появился переключатель `Показывать low-level Actions`.
- Добавлены формы создания и завершения Action; завершение `select_decision`/`decide_acceptance` меняет Decision state с проверкой групп.
- Canon, Decision Groups и overlapping membership из предыдущего handoff сохранены.
- Старая искусственная dependency demo не возвращалась.

Prototype-only граница сохраняется: writers, event schemas, validators, Graph/Plan owners, installed Viewer и миграция не изменены.

## 5. Что ещё нужно решить до backend

- Какие Action types являются обязательным закрытым enum, а какие расширяемыми пакетами.
- Должен ли Action хранить только refs или также immutable text snapshot названий блоков на момент выполнения.
- Как action execution связывается с exact History event и правами executor.
- Как `select_decision` выражает выбор в нескольких независимых группах, если один Action должен фиксировать несколько решений.
- Как Action о `rename_block` вызывает review/stale, не превращаясь в скрытый прямой writer.
- Как low-level filter влияет на History navigation, counts, cursor и audit: скрытие только визуальное, факты не удаляются.
- Является ли `DecisionGroup` самостоятельной сущностью owner Graph или relation с собственной identity/revision.
- Как Plan размещает Action до выполнения и как после completion Action исчезает из Plan, а Decision остаётся selected/completed отдельно.

Текущий active contract всё ещё описывает R/A. Не обновлять его автоматически на основании prototype; следующий чат сначала готовит proposal/contract и тесты, затем отдельный migration plan.

## 6. Проверки и следующий шаг

Проверка prototype:

```text
sed -n '/<script>/,/<\\/script>/p' tests/visual/rdg-ui-prototype.html | sed '1d;$d' > /tmp/rdg-ui-prototype.js
node --check /tmp/rdg-ui-prototype.js
```

Smoke должен отдельно подтвердить: Action nodes/types, `OPERATES_ON`, low-level toggle, group rails, overlapping group membership и Action forms.

Browser manual pass после этого Action-layer изменения ещё не выполнен. Следующий чат должен проверить:

1. rail G1/G2/G4 и отсутствие дублирования D2/D3;
2. создание Action с типом, свободным контекстом, target refs и group refs;
3. завершение `decide_acceptance` и `select_decision` с конфликтами групп;
4. отображение Action в Plan/History;
5. скрытие low-level Action без удаления History event;
6. переход из Action/Plan/History в Graph с сохранением viewport.

Не считать синтаксический smoke доказательством runtime или backend semantics.
