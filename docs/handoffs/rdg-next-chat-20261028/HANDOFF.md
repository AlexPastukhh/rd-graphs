# RDG — handoff следующему чату: интеграция Decision UI

> Срез: 2026-10-28 (Asia/Bangkok). Это передача рабочего контекста, а не приёмка продукта, commit или разрешение на миграцию/push.

## Коротко: с чего продолжать

Пользователь работает над **`rd-graphs`**. Не переключаться на другие проекты и не начинать заново проектирование модели. Минимальные **D1/D2 — Decision kernel и общий Application/API — реализованы**. Следующая полезная работа — подключить этот backend к настоящему generated Viewer и доказать один сквозной путь с сохранением и readback. Это больше, чем нарисовать UI, но меньше, чем сразу реализовать весь D3–D9.

**Текущий рекомендуемый шаг:** ранний интеграционный проход **PR-6 (candidate, не committed)**: временный Decision-процесс → общий Application/API → основной generated Viewer → одна совместимая фундаментальная линза → первый order-only Plan placement и позиция блока → restart → readback. Подробный критерий и очередь — в `docs/guides/RDG-DEVELOPMENT-PLAN.md`.

## Источники истины

1. `docs/guides/RDG-CURRENT-STATE.md` — актуальный вход, проверенное состояние и ограничения.
2. `docs/guides/RDG-DEVELOPMENT-PLAN.md` — единая очередь D1–D9 и критерии этапов; верхние разделы актуальны, помеченные historical/superseded — только история.
3. `docs/guides/RDG-ACTIVE-CONTRACT.md` — принятая семантика пользователя; не заменять её предположениями из прототипа.
4. `docs/guides/RDG-DECISION-V1-CONTRACT.md` — технические schema/refs/effects/API-контракты нового профиля.
5. `docs/guides/RDG-OPERATIONS.md` — разрешённые рабочие операции; `docs/guides/RDG-LENSES.md` — требования к фундаментальным линзам.

Старые handoff и review snapshots полезны для происхождения решений, но **не** описывают текущее состояние runtime. Не использовать `rdg-next-chat-20261026` или `rdg-stage1-to-d1-20261027` как текущую очередь.

## Что действительно готово: D1/D2

- `tools/rdg-model-profiles.py` маршрутизирует `rdg-core-v1` и `rdg-decision-v1` раздельно. Legacy `rdg-core-model.py` сохраняет прежнюю R/A-семантику; не пытаться сделать его единственной моделью и не менять глобальный profile constant вместо dispatch.
- `tools/rdg-decision-model.py` содержит новый pure kernel: Requirement (R), Decision, явные Graph Actions и внешние Actions, typed relations, overlapping Decision Groups, независимые `rootCauses` и fixed-point актуальность. Выбор Decision, completion Decision, исполнение Action и достижение R — разные факты.
- D1 также включает каскад снятия актуальности при отказе Decision без удаления identities/evidence/events/history; другое действующее основание сохраняет общий R. Есть guards, completion с проверкой обязательств/Evidence, reopen, atomic connected add и coordinated remove. Если для безопасного удаления нельзя согласованно разрешить чужие Plan placements/current refs, операция должна отказать целиком (fail-closed).
- `tools/rdg-portable-model.py` и `tools/rdg-portable-service.py` подключают новый профиль к существующим owner/authority/writer/CAS/preflight/receipt/retry/recovery механизмам. Поддержаны create, schema, read/focus, preflight, apply, receipt/exact retry и history на synthetic owners.
- Agent (`tools/rdg-agent.py`), CLI (`tools/rdg-portable.py`) и Helper маршрутизируют новый профиль через тот же Application. Strict R/D/Graph Action focus и отдельные details внешнего Action существуют. `showExcludedAlternatives` и group visibility — только проекция вида, не изменение выбора.
- Адресные исправления из D1/D2 reviews `F-P-01–13` отражены в `RDG-CURRENT-STATE.md`; это не закрывает D3–D9, F-R-1 из `RDG-IMPL-20261027/v1` в части integrated Viewer/lens runtime или Stage 4. Не путать его с исправленным stage-1 contract F-R-1 про atomic add+initialRelations.

## Что ещё открыто

- **D3:** полноценный Decision Plan v3 и History, placements/ветвления/периоды показа, корректный readback после restart.
- **D4:** authoritative persistent registry/versioning/connect/disconnect для пакетов рекомендаций.
- **D5:** шаблоны, copy/insert и полный typed-instance ID/ref remap для нового профиля.
- **D6:** общий R/D/Action visual projector, occurrences, независимые координаты и camera/view state через общий API.
- **D7:** интегрированный основной Viewer с настоящими Decision data/controls; checkbox конфликтующих альтернатив должен управлять только view filter.
- **D8:** пересборка фундаментальных линз под реально поддержанные команды нового профиля. Все 11 существующих зарегистрированных линз пока относятся к `rdg-core-v1`; не считать их автоматически инструкциями Decision v1.
- **D9:** полный сквозной сценарий и затем отдельная пользовательская проверка. Установка нового Viewer в Windows и Stage 4 acceptance не подтверждены.

## Следующий шаг: PR-6, ранний сквозной срез

Делать на **временном synthetic process**, не на живом owner:

1. Проверить актуальный `git status`, существующие staged/unstaged изменения и точный код API/UI перед редактированием. Не предполагать, что всё, что описано в старом handoff, осталось неизменным.
2. Проследить реальный маршрут `rdg-decision-v1` через `rdg-portable-service.py` и текущий transport. Создать/прочитать/изменить R, Decision и Action только поддержанными командами.
3. Подключить данные к **основному generated Viewer**. Проверить source → `tools/build-rdg-layout.py` → generated `tools/rd-graph-viewer.user.js` и parity generated blocks. Наличие `RDGPortableUI` в bundle само по себе не означает готовый Decision UI: существующий `rdg-portable-ui.js` — прежний portable/package editor, а его текущая точка включения не завершает интеграцию нового Decision-профиля.
4. Использовать одну фундаментальную линзу только после проверки, что её определения и команды совместимы с `rdg-decision-v1`. Если ни одна из 11 текущих линз не совместима с `rdg-decision-v1`, выбрать одну существующую фундаментальную линзу, нужную для этого вертикального среза, и выполнить только минимальную профильную адаптацию, достаточную для реального API-прохода; отразить её как часть D8, оставив полную пересборку остальных линз открытой. Не пытаться завершить все D8 в рамках раннего прохода.
5. Проверить один первый **order-only** Plan placement (без даты) и сохранённую позицию блока. Не реализовывать сразу весь Plan v3 или всю раскладку, если маленький путь способен проверить стык; но не подменять настоящую запись mock/localStorage.
6. Перезапустить приложение/создать новый Application instance и прочитать состояние обратно. Зафиксировать точные факты: API result, Viewer display, stored state, restart/readback, тесты и непроверенные области.

PR-6 в плане помечен **candidate**. Не повышать его до committed Proposal без отдельного основания. Этот early pass не сокращает обязательные D3–D9 и не означает их завершение. После доказанного вертикального среза расширять D3, D6, D4/D5, D7 и D8 в порядке из единого плана; не создавать второй writer, второй registry или второй предметный JS-state.

## Проверки, выполненные при подготовке handoff

На текущем срезе после D1/D2 запускались:

- `python3 tests/rdg-decision-model.test.py` — **26/26 PASS**.
- `python3 tests/rdg-portable-service.test.py` — **26/26 PASS**.
- `python3 tests/rdg-portable-transports.test.py` — **13/13 PASS**.
- `node --test tests/rdg-documentation.test.cjs` — **6/6 PASS после правок документации** (2026-10-28).
- `python3 -B tools/rdg-docs-audit.py --list-active` — выполнено; актуальный список active docs выведен.
- `git diff --check` — PASS, whitespace errors не найдены.

Python печатает `DeprecationWarning` о `SourceFileLoader.load_module()`; он не провалил эти suites. Эти тесты подтверждают kernel/Application/transports и documentation audit в своих пределах, но **не** подтверждают интеграцию Decision в браузер, source/generated parity после новых правок, работу настоящего Viewer, Windows installation, UX acceptance или Stage 4.

## Среда и безопасность работы

- Репозиторий: `/workspace/repos/rd-graphs`; HEAD при проверке: `176ce44c820757ecfb827ea881c0cac6613c8831`.
- MCP `get_config` и hostname показывают `c6d7be9fe6eb` — старое имя. Фактическая проверка `findmnt` показала `/workspace/repos` на ext4 Docker volume `fortis-repo-workspace`, подкаталог `Repos`; `/workspace/repo` — корень того же volume; `/workspace/files` — `Workfiles`. `/workspace/repos` и `/workspace/repo/Repos` имеют одинаковые `st_dev`/`st_ino`. Имя из MCP не является доказательством реального container ID; не пересоздавать контейнер только из-за этого поля.
- Рабочее дерево уже сильно изменено: есть staged, unstaged и untracked файлы, в том числе код, тесты, fixtures и handoff-контекст. Перед работой заново выполнить `git status --short`; число путей меняется. Не выполнять `git reset --hard`, `git clean`, массовую очистку, Windows sync, commit или push без отдельного решения пользователя.
- Не изменять живые Graph/Plan owners, grants, credentials, Windows installation или старые backup/snapshot каталоги. Не считать Docker source change установленным Viewer.
- Scope: приложение/API/Viewer и фундаментальные линзы. Тематические 2D/3D/programming examples не требуют предметного аудита в этом этапе. Срок/бюджет не установлены.

## Что уже изменено в документации

Актуализированы `README.md`, `docs/guides/RDG-CURRENT-STATE.md`, `RDG-DEVELOPMENT-PLAN.md`, `RDG-ACTIVE-CONTRACT.md`, `RDG-OPERATIONS.md` и `RDG-LENSES.md`: D1/D2 обозначены как готовый минимальный срез, старые заявления «kernel/API ещё не реализованы» помечены историческими, PR-6 обозначен следующим candidate-шагом, а Viewer/Plan/registry/lenses/acceptance — открытыми. Этот handoff — объяснение для следующего чата, не новый canonical план и не commit.

**Перед дальнейшими документальными правками:** повторить `node --test tests/rdg-documentation.test.cjs` и `git diff --check`; при необходимости сверить active docs через `python3 -B tools/rdg-docs-audit.py --list-active`. Эти проверки уже прошли для состояния, записанного в handoff. Просмотреть diff только затронутых документов. Ничего не коммитить и не публиковать автоматически.