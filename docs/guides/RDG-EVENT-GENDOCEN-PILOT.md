> **СТАТУС: АРХИВ / ИСТОРИЧЕСКАЯ РАЗРАБОТКА — НЕ ДЕЙСТВУЮЩИЙ КОНТРАКТ.** Включая файлы с именами `CONTRACT`, `PLAN`, `STAGE`, `PILOT` и со словом «актуальный» в тексте. Новый чат должен использовать [единую текущую спецификацию](RDG-CURRENT-STATE.md); ниже сохранены прежние эксперименты, решения и протоколы.

# Event history → Gendocen: явный контракт v1

**Статус: CANDIDATE. Stage 4 NOT ACCEPTED.**
`tools/rdg-event-gendocen.py` формирует отдельный read-only ресурс
`rdg-event-review/v1` из аутентифицированного чтения
[технической истории события](RDG-EVENT-LIFECYCLE-PILOT.md).
Он предназначен для review документа, который использует этот контекст.
Статус Gendocen `valid` означает свежую dependency receipt для контекста;
он не подтверждает наступление события, личность источника или выбор Action.

Ресурс имеет два режима. `current-known-records` включает известные сейчас
записи выбранного occurrence. `fixed-knownAt` включает только записи,
доступные к указанному cutoff; pinned Plan тоже должен быть доступен к нему.
Режим и нормализованный `knownAt` входят в identity ресурса. Разные cutoff
не подменяют друг друга. Поздняя запись по другому occurrence не меняет
проекцию выбранного события. Поздняя attestation, review, correction или
новый конфликт меняют текущую проекцию. Ранняя проекция сохраняется.

Контракт содержит восемь точных subscriptions: coverage и семь групп
`identity/knowledge/claims/attestations/reviews/resolution/boundaries`.
Группы producer заданы независимо от изменяемой декларации. При удалении
группы, пропуске subscription, изменении вычисленной проекции или новом
неподдержанном поле регистрация отклоняется. Claims включают точные
Plan pins, payload, record digest, записанное время и квитанцию доступности;
attestations и reviews включают payload, digest и квитанцию.
Технические границы доверия также входят в dependency.

`completeForDeclaredScope=true` относится к покрытию прочитанных полей
одного предъявленного event context. Поля
`completePlanRdgContext=false`, `factualEventVerified=false`,
`factualBranchResolved=false` и `actionSelected=false` сохраняются.
Содержание opaque evidence IDs не читается. Полный исторический Plan/RDG
resolver, принятый lifecycle и доверенный источник фактов этим ресурсом
не объединены. Старый current-only Plan adapter продолжает отклонять
новые sidecars; новый ресурс используется явно и отдельно.

CLI на разрешённом временном root:

```bash
RDG_AUTH_TOKEN=... python3 tools/rdg-event-gendocen.py \
  --root PLAN_ROOT --store AUTH_STORE --file plans/demo/plan.json \
  --occurrence-id O1 --known-at 2026-10-18T11:00:00+00:00
```

Без `--known-at` получается текущая event-проекция. Токен требует
`plan.read`. Результат следует пересоздать после изменения sources перед
проверкой Gendocen. Для доверенного локального project config есть
`project_config([(targetName, resourceRelativePath), ...])`; регистрация
при каждом запуске повторно проверяет producer/declaration/subscriptions.

Локальные проверки:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-event-gendocen.test.py -v
PYTHONDONTWRITEBYTECODE=1 python3 tools/rdg-event-gendocen-smoke.py \
  --engine-source /workspace/repos/gendocen
```

Smoke использует реальный локальный Gendocen 0.1.0.dev25 и только tempfile.
Он проверяет review текущего и раннего event context, адресное изменение
attestation/review/correction, явный конфликт, отказ при stale review context,
сохранность ранней проекции, текста review и owner bytes при чтении.
Двигатель не копируется и не устанавливается.

Для дальнейшего исполнения есть два независимых gate. Предметный gate:
выбрать доверенный actor/source и подтвердить evidence перед фактическим
применением. Технический gate: объединить lifecycle, применимость, Plan/RDG
snapshots и event context в историческом resolver и проверить его Gendocen
coverage на синтетической истории. Технический gate можно выполнять до
выбора реального источника; результат сохраняет Candidate и false factual flags.
