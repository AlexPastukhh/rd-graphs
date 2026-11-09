# RDG — исправления после уточнения общего текущего Context, 2026-10-16

**Статус:** выполненное исправление в живом Fortis Repo `/workspace/repos/rd-graphs`. Это запись исполнения и evidence, не второй контракт данных и не перезапись исторических кандидатов/ревью. Авторитетный контракт — §15 `docs/guides/RDG-V7-WORKING-GRAPHS.md`.

## Подтверждённый результат

- Общий `Context` теперь хранит одно **текущее** `contextValue={value,source,scope}` в единственном owning узле `kind=context`, либо не хранит `contextValue` (пустое поле). Нет `recordedAt/effectiveAt/validUntil` для ответов поля и нет `contextAnswers[]`. При изменении значение заменяется, а не записывается история; новая операция `set_context_value`, `value=null` очищает. Источник, смысл поля, scope и qualified `contextFieldRef` сохранены. Writer требует явный `value`, проверяет revision, owner, запрет update_node и read-back.
- CLI `--fields` и встроенный Viewer используют тот же `rdg-state.js`; показаны заполненное/пустое поле, условия now/later, общий ответ проекта. `--as-of` в режиме `--fields` отклоняется; **старый отдельный** canon lookup для R/D/C с `--option-id` и исторической оценкой оставлен без изменений. Это не история текущих ответов полей.
- Любой свободный Context больше не превращает пустое актуальное поле в `question=false`; свободные записи доступны для смысловой оценки по ситуации. Связывание с существующей свободной записью требует `mappingNote` и сохраняет её исходный текст, без автоматического семантического поиска/нового хранилища.
- T1/QRPE/composite history принятых решений **не менялись**. Writer сохраняет отдельный `selectionBasis.contextSnapshot` при новом D: это моментальный immutable снимок оснований принятия, а не лог изменений всех полей.
- Учебный `graphs/examples/context-working-root/graph.json` переведён с одного прежнего ответа на `contextValue`, revision 1→2; остальной состав учебных/рабочих владельцев не переносился. Старые внешние workspace с массивами `contextAnswers[]` следует **явно** мигрировать после определения их текущего значения; не выбирать автоматически из нескольких исторических ответов. Прежний contract теперь отвергается валидатором.
- Устранены текущие противоречия в документах, версиях и инструкции Viewer, статус раздела с источниками канонов, три битые относительные ссылки. `docs/examples/EXAMPLE-COVERAGE.md` отделяет текущие 100 графов от исторического среза на 88. Существующие старые планы/отчёты не переписаны как современные требования.
- Обновлены два исходных work-kit modules, пересобран импорт прежних **13 IDs** и доставлены две производные Helper-library записи; импорт в установленный Helper не утверждается.

## Read-back и реальные тесты

- `node --test --test-concurrency=2 tests/*.test.cjs`: **287/287 PASS**, 0 FAIL/SKIP, журнал `/workspace/repo/rdg-current-context-full-tests.log`. После последующего уточнения одного writer-теста на очистку/refill и повышения ревизии учебного графа адресный повтор: **18/18 PASS**, журнал `/workspace/repo/rdg-current-context-final-targeted.log`.
- Отдельный Chromium: `viewer-context-180.cjs` — 7 screenshots/PASS; `viewer-navigation-170.cjs` — 7 screenshots/PASS, page errors 0; результаты `/workspace/repo/rdg-current-context-browser` и `/workspace/repo/rdg-current-context-navigation`.
- `python3 tools/graph-index.py`: `INDEX_UPDATED graphs=100`. Итоговый CLI `--fields --set-id context-working`: accessibility=`now/known`, alternative-details=`later/missing`, delivery=`now/missing/question=true`. По 40 Markdown-файлам относительных битых ссылок **0**; embedded `rdg-state.js` совпадает с общим source. Каталог: 100 graph.json, 16 sets, 78 межграфовых отношений; revision рабочего учебного root — 2. Helper-delivery bytes проверены в адресных тестах.

## Граница доказанного

Продуктовые владельцы других графов, snapshots исторических решений и layouts не изменены. Реальная установленная Windows/Tampermonkey/Helper и пользовательские внешние workspace не проверены; браузерные проверки проведены в изолированном Chromium. Предыдущий review в `forfiles` — исторический срез **до** этого исправления, его находки не следует считать текущими без повторной проверки. Отдельная история R/D/C и QRPE сохраняет свою датированную семантику, отличную от простого общего текущего Context.

### Финальная адресная проверка общего Context в UI

В дополнение к первоначальному списку полей убрано предупреждение «дата действия неизвестна» для свободных `kind=context` в старой общей панели `projectContexts.records`; для R/D остаётся их независимая историческая проверка. После этой UI-правки повторно выполнены Node state/viewer/writer tests **16/16 PASS** (`/workspace/repo/rdg-current-context-last-check.log`) и реальный Chromium Viewer-context сценарий **PASS / 7 снимков** (`/workspace/repo/rdg-current-context-browser-final`). Общая 287/287 регрессия выполнена до этой небольшой UI-правки; её после неё не выдаём за заново запущенную.
