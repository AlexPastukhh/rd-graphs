> **СТАТУС: АРХИВНЫЙ ПРИМЕР — НЕ АКТИВНАЯ МОДЕЛЬ.** `Decision/Option`, старые каталоги и команды ниже относятся к историческому корпусу, их нельзя выполнять как текущий `candidate-v6`. Новый чат: [текущая спецификация](../guides/RDG-CURRENT-STATE.md).

# Candidate v6 — обычный Graph API и выборочное сохранение Lens-исследований

**Статус (17.10.2026):** экспериментальные исходники и изолированные проверки. **Не BASELINE COMMITTED, не production authorization, не переключённый Helper/браузер.** Материал следует из [Candidate Pre-work Composition v1](https://github.com/AlexPastukhh/forfiles/blob/main/artifacts/2026-10-17/candidate-prework-rdg-general-graph-api-lens-persistence-authority-20261017-v1.md). Предыдущие две причины сохранять R/A сохранены; третий критерий дорогой ценной работы с более высоким порогом для Lens пока **user-origin Proposal**, а не обязательный норматив. Нет обязательного Extra Dependencies block и LensRun.

## Что теперь можно сделать

### 1. Общее API без зависимости от типа Lens

`tools/graph-apply.py` принимает дополнительную операцию `graph_edit` через **тот же** транзакционный `graph-package.py`. Действия реализованы в `tools/rdg-graph-api.py` и относятся к любому opt-in `actionModel: "candidate-v6"`, независимо от того, что их предложило: прямой анализ ИИ, DRY, Maintenance или другой граф.

`action` в `graph_edit`: `create_requirement` (с DERIVES от активной R), `create_context`, `edit_node`, `reparent_requirement` (архивирует прежнюю DERIVES, записывает новую), `archive_edge`, `add_edge`, `detach_requirement` (архивирует INTRODUCES, не убивает R), `deactivate_requirement` (только не-root без активных зависимостей), `delete_orphan_requirement` (если нет активных связей / зависимых owner; архивные связи сохраняются в снимке), `delete_candidate` (только невыбранная A без зависимых объектов), `set_reconsideration_policy` (только R, event `by:user`). Существующие общие операции `add_action`, `select_action`, `link_action_requirement`, `reconsider_action`, `append_qrpe`, `transition_qrpe` остаются совместимыми; они **не** становятся Lens-операциями. Физическая O/D→A миграция не совершалась.

Пример **синтетического** material package (выданный тестовым issuer ключ не устанавливает личность пользователя):

```json
{
  "schemaVersion": 1,
  "transactionId": "edit-context-001",
  "changes": [{
    "file": "workspaces/pilot/graph.json",
    "patch": {"schemaVersion": 1, "expectedRevision": 1,
      "operations": [{
        "op": "graph_edit", "action": "create_context",
        "node": {"id": "C-INPUT", "kind": "context", "title": "Исходные условия"},
        "event": {"id": "E-INPUT", "type": "graph_changed",
          "operation": "create_context", "by": "assistant",
          "authorityPrincipal": "issuer-from-signed-package",
          "note": "Контекст установлен для исследования допустимого варианта"}
      }]
    }
  }],
  "trustedApproval": {"purpose": "rdg-v6-material-action-v1",
    "principal": "issuer-from-signed-package", "expiresAt": 0,
    "signature": "REPLACE_WITH_REAL_HMAC_SHA256_FOR_EXACT_PACKAGE"}
}
```

`expiresAt` и `signature` выше **невалидные заглушки**, а не готовое разрешение. Реальная операция требует точного HMAC и установленных полномочий; без них отклоняется. События `graph_changed` содержат old-node/edge snapshots и `verifiedTrustReceipt`. Запрещено менять identitySpace, root, ID/kind, T1 и историю обычным edit. Защищённая R может исследоваться, но её изменение, изменение собственных прямых связей/под-R, ввод дочерних R через выбранный Action, reparent и смена политики требуют правильно подписанного user event с matching authorityPrincipal; *это только техническая проверка issuer, не доказательство человека*.

### 2. Семантическая Lens без writer side effects

`tools/rdg-lens-session.cjs` разбирает подготовленный R/A-граф: старый format Lens semantic fixture либо обычный `schemaVersion:1`, `actionModel:"candidate-v6"`, `rootRequirementId` и `nodes/edges/events` с обязательной T1-историей для selected Actions. Обычный graph.json проверяется тем же валидатором, что и writer, до создания рабочей сессии. Возвращает **временный рабочий граф** с переданными аргументами, оценками канонов, QRPE, требуемыми evidence и статусами R. **Входящий target graph не меняется.** Специальных операций `deleteFromDry`, `maintenanceDelete` нет. Любые предложенные после исследования изменения записываются независимо через общий Graph API.

CLI без записи: `node tools/rdg-lens-session-cli.cjs --lens path/to/lens.json --bindings path/to/bindings.json [--assessments path/to/assessments.json] [--persistence path/to/decision.json] [--saved-metadata path/to/metadata-array.json]`. Вывод только на stdout в JSON, никаких файлов/commit. `bindings` включает `targetGraphId`, опциональный `targetActionId`/`targetRequirementId`, `arguments` и `relevantInputs`. `--persistence` лишь **предлагает** snapshot для отдельного Git save; сам CLI не сохраняет его. В режиме `--github-metadata` CLI вместо файла вручную загружает **только небольшие metadata-sidecar** из явно настроенного `RDG_GITHUB_REPOSITORY`/`RDG_GITHUB_BRANCH` с `GITHUB_TOKEN`; совместно с `--saved-metadata` использовать нельзя. `--open-previous` отдельно получает **полный** последний подходящий saved Lens-graph, сверяя Git blob SHA и metadata. Без этих флагов сетевого обращения нет. Выданный архив — лишь кандидат на переоценку, не автоматическое подтверждение старых выводов.

**Ограничение:** generic adapter — assessment scaffold, не общий проверенный evaluator канонов и QRPE. До наличия реальной проверки evidence даже заявленные в `rootAssessment` «achieved» или «blocked» выдаются как `rootResult:unknown`, а не как доказанная цель. Это намеренная защита от ложных результатов.

### 3. Ленивый персист и повторное использование

`tools/rdg-lens-research.cjs`: `eligible(session, claim)`, `capture(session, claim, recordedAt)`, `lastRelevant(savedMetadata, query)`. По умолчанию `save:false`. Для explicit save нужны шесть проверенных (пока **декларативных**, а не вычисленных) условий: незавершённая material работа; высокая стоимость восстановления; прогноз будущей пользы; отсутствует достаточная копия в основном графе; достаточно устойчивые вводные; maintenance оправдан. Также необходима причина и либо unresolved QRPE/неоцененный канон, либо конкретная уже завершённая содержательная оценка канона/Requirement с evidence по **ещё не выбранному** target Action. Для последнего случая явно указываются `pendingDecisionForActionId` и `pendingDecisionState:"unselected"`; одно самоутверждение pending не делает работу ценной. Полный временный граф сохраняется только по такому явному решению. **Не следует считать boolean-флаги доказательством** этих ценностей без содержательного решения ИИ/пользователя.

Поиск находит самое позднее **сохранённое** применение с тем же `lensId`, `targetGraphId`, `targetActionId`, `targetRequirementId`, существенными аргументами, и проверяет `definitionDigest`, `relevantInputsDigest` и подтверждённость свежести evidence. Последнее сохранённое ≠ последнее выполненное. Необязательные архивы не попадают в основной graph.json или исходный Viewer. Чтение metadata не подгружает весь рабочий экземпляр Lens в контекст.

### 4. GitHub — transport, не semantic authority

`tools/rdg-github-store.py`: opt-in Contents API transport с expected blob SHA, явным branch/repo/token, проверкой package trust и readback SHA; `save_research` сохраняет selected snapshot под `lens-applications/YYYY-MM-DD/<id>.json` и отдельный маленький `<id>.metadata.json` для адресного поиска. `list_research_metadata()` читает только metadata; `load_research(metadata)` после запроса читает snapshot и сверяет Git blob SHA. Два Contents-API PUT не атомарны: если metadata-операция не завершится, полный snapshot может остаться без указателя и потребуется ручное восстановление; это не гарантированный production commit. **Никакого live репозитория пользователя во время разработки не меняли; тест использует in-memory fake.** Реальные repo/branch/ACL/issuer и GitHub-based Viewer/source refresh ещё не подключены. Remote adapter сознательно отклоняет потенциально cross-graph изменения (`reconsider_action`, deactivate/detach/delete R), пока нет общей каталожной транзакции, которая проверяет связи через разные файлы. Поэтому это **не** полный замещающий `graph-package.py` writer.

Git хранит версии файлов, но не объясняет, почему решение принято, если в содержимом нет семантического evidence. Существующий `.transactions` локального writer пока сохранён как crash-recovery механизм, а не второй canonical Git history; удалять его до live GitHub cutover без отдельной проверки восстановления нельзя. Конфликты SHA отклоняются; идемпотентный replay и atomic multi-graph Git commits ещё требуют отдельного решения.

## Проверка

```bash
node --test tests/rdg-general-graph-api.test.cjs
node --test tests/rdg-general-lens-research.test.cjs
node --test tests/rdg-lens-cli.test.cjs
node --test tests/rdg-github-store.test.cjs
node --test tests/*.test.cjs
```

**Владелец runtime:** существующий `work-kit/modules/rdg.work.semantics.module.md` не перенаправлен автоматически; существующие `rdg-v6-lens-apply.cjs`/DRY/Maintenance адаптеры оставлены для совместимости со старыми тестами, не признаны обобщённым решением. Никаких автоматических миграций пользовательских графов или обновления установленного Helper/Viewer. До production: реальная выдача grant, атомарные изменения связанных файлов через Git, source-of-truth DRLD и API entrypoint в Helper, проверенный evaluator canonical cases, UI для оставшихся сохранённых исследований и privacy controls.
