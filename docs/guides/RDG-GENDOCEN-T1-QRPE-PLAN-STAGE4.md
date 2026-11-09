> **СТАТУС: АРХИВ / ИСТОРИЧЕСКАЯ РАЗРАБОТКА — НЕ ДЕЙСТВУЮЩИЙ КОНТРАКТ.** Включая файлы с именами `CONTRACT`, `PLAN`, `STAGE`, `PILOT` и со словом «актуальный» в тексте. Новый чат должен использовать [единую текущую спецификацию](RDG-CURRENT-STATE.md); ниже сохранены прежние эксперименты, решения и протоколы.

# Stage 4 — штатный RDG T1, поздние QRPE и Temporal Plan через Gendocen

**Статус:** co-located synthetic integration proof PASS (2026-10-18), **не production acceptance**. Реальные компоненты: RDG package writer, bearer authority, Graph API, RDG Gendocen adapter и docengine 0.1.0.dev25.

## Что действительно записывается

Все исходники копируются только в tempfile. Авторизованный синтетический пакет создаёт RDG Requirement R0, Actions A1/A2 и реальное событие выбора EV-T1 через штатную операцию select_action. Кандидатный author-grant не может выполнять selection; отдельный selector-grant может. Попытка добавить второй action_selected через общий append_event запрещена даже с широким bearer graph.write. На T1 сохраняются status A1=selected, status A2=candidate, выбор с verifiedTrustReceipt.mode=bearer и immutable selectionBasis со снимками Requirement и исходного candidate Action.

**Не путать техническое событие с человеческим решением.** Bearer-grant принадлежит синтетическому тесту и событие подписано как by=assistant. Это не trusted human authentication, не фактическое принятие реальным пользователем и не проверка объективной истинности канонов.

После T1 добавляется F-R Risk через отдельный append_finding, затем QRPE Finding переводится из open в resolved штатным transition_qrpe с историей и техническим receipt. Эти две новые ревизии **не** аттестуют реальные наблюдения или действие во внешнем мире. Каждый раз проверяется идентичность события EV-T1, selectionBasis и статуса выбранного Action. F-P не создаётся.

## Реальный Gendocen runtime

RDG и Temporal Plan проецируются штатным rdg-gendocen-adapter.py как **разные resource owners**. Два semantic_review subscriptions следят за точными путями Action.canonBlock, Action.qrpe, Plan.timeConstraintsByStep/S-A1 и S-A2 и общим deadline S-DELIVERY.

| Изменение | A1 | A2 |
|---|---|---|
| Исходная синтетическая валидация | valid | valid |
| Позднее добавлен F-R на A1 | review_required | valid |
| F-R на A1 переведён в resolved | review_required | valid |
| Кандидатное ограничение только на A2 | valid | review_required |
| Общий дедлайн S-DELIVERY | review_required | review_required |

Проверяется и отклонение validation со старым review_context_id после QRPE revision; отказ не меняет dependency_state или receipts. Тестовый аварийный выход Gendocen с кодом 91 блокирует обычные чтения до recover, после которого state, receipts, events и публичная история возвращаются к прежнему состоянию. Исторический EV-T1 и selectionBasis сохраняются. После recover требуется **свежее** синтетическое подтверждение. Gendocen не вычисляет истинность канона и не принимает Action.

## Файлы и повторение

- tools/rdg-gendocen-t1-history-smoke.py — co-located end-to-end test.
- docs/examples/RDG-GENDOCEN-T1-QRPE-PLAN-STAGE4-20261018.json — подтверждённый машинный отчёт с SHA-256 файлов RDG и движка.

Команда:

    PYTHONDONTWRITEBYTECODE=1 python3 tools/rdg-gendocen-t1-history-smoke.py --engine-source /workspace/repos/gendocen

Рабочие графы пользователя и установленный Helper/Viewer не изменяются.

## Граница принятия Stage 4

Проверено настоящее **штатное событие T1 в изолированном техническом RDG**, но не user-approved T1 реального проекта. Поздние T2/T3 здесь означают **пост-T1 QRPE revisions**, а не подтверждённые внешние события. Plan остаётся кандидатом, без авторизованного Plan writer. Не проверены production replay, работа с настоящими user-authorized snapshots, гонки нескольких owners, независимая проверка F-P и доверенный human identity.

Следующий gate: persistence/authorization Temporal Plan и связь with selected Action/history через точные source snapshots; затем production-like review integration and race/recovery scenarios. Stage 4 production acceptance пока не достигнут.
