# CPW-RDG-INSTANCE-TEMPORAL-WORKFLOW-20261019/v1

Дата среза: 2026-10-19 UTC. Статус: **Candidate, local API proof; Stage 4 NOT ACCEPTED**.
Поручение: выполнить текущий план крупным связным пакетом для ранней проверки целого.
Проект: `/workspace/repos/rd-graphs`, Fortis Repo; RW Windows mount проверен по
`/proc/mounts`, права записи подтверждены. `.git` отсутствует: Git status/commit/push
недоступны. До правок сохранены выбранные файлы и их хеши. Пользовательские графы
не менялись; испытания использовали временные синтетические владельцы.

## Результат

Реализован сквозной API-путь одного владельца: явное размещение R/Action →
выполнение → история; также выполнение без размещения → история.
Выполнен A1 → отозван A1 → выбран и выполнен отдельный A2 для той же R.
Старые выполнение и отзыв остаются отдельными фактами с исходными ID.
Выполненный A1 после правки не возвращается в будущее и не выполняется второй раз.

`rdg-workflow.py` даёт read-only JSON/Markdown/HTML из существующих владельцев.
Будущее исключает завершённое при чтении, без перезаписи Plan и отдельного
lifecycle закрытия шага. HTML — снимок, не живой редактор.

## Состав и интеграция

- Модель сохраняет исторический факт выполнения Action, отдельно проверяет
  currentScopeComplete для текущего обязательного состава родительской R.
  Снимки basis и выходных наборов не переписываются; неизвестные роли и неполная
  композиция не доказывают успех родителя.
- Новый withdraw_action относится к уже выполненному selected Action. Записывает
  отзыв через прежний writer/receipt и отдельный grant graph.withdraw_action;
  не утверждает Canon review или физическую отмену внешнего результата.
  Богатый reconsider_action и его review-гейты сохранены. Политики защищённых R,
  точные child dispositions, shared support и catalog guards применяются.
- R refs и place/unplace идут через существующую Plan edit-транзакцию: права,
  CAS, журнал, идемпотентный retry и recovery. Граф не меняется от размещения.
- Общий reader проверяет Plan read и Graph read, owner/kind/ID, использует locks,
  сохраняет порядок фактов внутри одного пакета. Pending journal блокирует
  чтение успеха до recovery. Ошибочная ссылка не скрывается как успешный результат.
- Gendocen projection включает actionType. R steps явно incomplete с
  REQUIREMENT_STEPS_NOT_COVERED; полного Canon-контекста этим не заявлено.
- README, руководство модели, API-guide и рабочий execution plan обновлены.

## Проверка и свидетельства

Широкий регрессионный прогон: **226 Python tests (22 набора) + 407 Node tests
(57 файлов), все прошли**. Источники: regressions.json, runner.log, node-all.log
и отдельные *.test.py.log в этой папке. В этом прогоне workflow имел 12 тестов.

После добавления проверки порядка событий EV9/EV10 одного пакета и финальной
доработки reader отдельно прошли 13 workflow tests (workflow-final.log) и
24 deep-action tests (deep-final.log). После последнего сужения нового прямого
отзыва до уже выполненного экземпляра повторно прошли **13 workflow tests**
(workflow-final2.log), включая отрицательный сценарий отзыва невыполненного Action.
Наборы пересекаются; это не повтор полного регрессионного прогона после последней правки.

Проверены: полный путь A1/withdraw/A2; вариант без размещения; предварительная R;
порядок без даты; CAS/replay; отсутствие записи при deny/неверной ссылке;
отдельные Plan/Graph read права; protected policy; судьба shared/dropped children;
краши Graph и Plan с recovery; один пакет без ложного промежуточного достижения R;
неизменность Plan при чтении; сохранение старого basis; CLI/API equivalence;
HTML escaping; старые snapshots и регрессионные writer/engine/Viewer сценарии.
Финальные выбранные Python-файлы проходят AST parse.

Первичные ошибки workflow-initial.log сохранены: добавлена поддержка receipt-bearing
withdrawal в существующем retirement guard; тест ретрая согласован с прежним
REPLAY_STATE_CHANGED после последующих изменений. Защита от старого ретрая не снята.
Deep-initial.log отражает прежние ожидания повторного исполнения; тесты обновлены
по прямому уточнению пользователя, остальные инварианты сохранены.

## Быстрая проверка результата

`demo/workflow-before.{json,md,html}` и `demo/workflow-after.{json,md,html}` получены
из фактического синтетического acceptance-прогона. До: A1/A2/R0 в будущем.
После: будущее пусто; в истории выполнение A1, отзыв A1, выполнение A2 и достижение R0.
Это снимки реального теста, а не работа с пользовательскими данными.

Команда reader:

```sh
python3 -B tools/rdg-workflow.py --root /path/to/plan-owner \
  --file plans/example/plan.json --graph-root /path/to/graph-owner \
  --graph workspaces/example/graph.json --store /path/to/grants.json --format html
```

Bearer передаётся через существующий RDG_AUTH_TOKEN. Форматы: json, markdown, html.
Поля placement и withdrawal описаны в docs/guides/RDG-DEEP-ACTION-AND-HISTORY.md.

## Ограничения и следующий пакет

Живой ручной редактор размещения/выполнения/отзыва и общая GUI-лента ещё не сделаны.
Следующий связный пакет — подключить существующий Viewer/Helper к этому API и
повторить тот же путь вручную с теми же правами и источниками.
Межфайловой расчёт owning/projectionOf остаётся OPEN; unresolved owner не даёт успеха.
Полный Gendocen Canon-контекст нового workflow и новый реальный engine smoke этого
scope не проверены; прежние engine-наборы прошли регрессию.
Скрытие/приоритет истории второстепенны и не реализованы. Браузерный визуальный
render HTML и установленный Windows/G2 не проверены. Нет установки, deployment,
нового сервера, ACL/mount/tunnel изменений, миграции или принятия Stage 4.

## Воспроизводимость и передача

BASELINE.json + before/ — исходный selected baseline; SOURCE-HASHES.json — точные
финальные исходники; SELECTED-DIFF.patch и DIFF-STAT.json — только выбранные изменения.
SCOPE.md — исходный scope этого пакета. Исторические checkpoint/review не изменялись.
Рабочий следующий порядок находится в docs/guides/RDG-CURRENT-EXECUTION-PLAN.md.
