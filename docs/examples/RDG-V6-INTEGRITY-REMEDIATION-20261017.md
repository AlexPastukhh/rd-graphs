> **СТАТУС: АРХИВНЫЙ ПРИМЕР — НЕ АКТИВНАЯ МОДЕЛЬ.** `Decision/Option`, старые каталоги и команды ниже относятся к историческому корпусу, их нельзя выполнять как текущий `candidate-v6`. Новый чат: [текущая спецификация](../guides/RDG-CURRENT-STATE.md).

# Candidate v6 — устранение подтверждённых нарушений целостности (локальный этап)

**Статус:** opt-in code remediation / экспериментальный `actionModel: "candidate-v6"`, 2026-10-17. Сопоставление с [независимым Final Review v1](https://github.com/AlexPastukhh/forfiles/blob/main/artifacts/2026-10-17/final-review-rdg-v6-implementation-consistency-r-rdg-impl-20261017-01-v1.md) (`F-P-01..05`). Это **не** commit кандидатного архитектурного состава CPW v6. Legacy-графы `option/decision` остаются отдельно; пользовательские `graphs/workspaces/*/graph.json` не переписывались. Нет установленного доверенного issuer и нет нового External Dependencies block.

## Что исправлено в исходниках

1. **F-P-01 / PR-01 (техническая защита):** для действительного candidate-v6 исключены generic `update_node`, `add_node`, `add_edge`, `append_event`, `set_context_value` и другие не привязанные к собственной истории способы изменения R, Context, owner/root, данных канона и рёбер. Они возвращают `ACTION_MODEL_GUARD` без partial write. Готовую возможность точечной официальной ревизии R/Context с доказанными правами этот шаг **не добавляет** — до нового решения доступен fail-closed путь. `add_action` для *кандидата* (не выбор, не ввод R) допускается как подготовка плана; QRPE можно дополнять через `append_qrpe`.
2. **F-P-02 / PR-02 (ограниченный trust gate):** реальные selection/link/reconsider/QRPE status transitions требуют подписанного точного package. Проверяются purpose, срок, HMAC, `authorityPrincipal`, совпадение signed changes; в материальных событиях/переходах сохраняется `verifiedTrustReceipt`. При создании opt-in-графа с уже выбранным Action/events без подписи пакет блокируется. Неизменённый базовый writer v7 сохраняет собственную семантику (отдельный D/Option).
3. **F-P-03 / PR-03:** до результата Lens используется **валидатор самого writer**, включая links, events, owner/root и история Action. Повреждённый граф не получает `rootAchieved:true`; не создан второй обязательный schema-validator.
4. **F-P-04 / PR-04:** для material Maintenance apply нужно подписанное `lensApplication`, которое указывает *собственный* `A-L-MAINT-REVOKE`, root-R/conditional-R `R-L-MAINT-CHANGE`, target revision и digest prepared Lens. `Q-MAINT-EFFECTS` должен быть `resolved` либо `accepted-risk` с явной причиной и evidence, соответствующим использованному Context. После подтверждённой записи отчёт отражает реально выполненную Lens Action и достигнутую условную R, убирает старое `skipped` и `open` QRPE, а связь с Lens остаётся в `action_reconsidered`. Пропозиционный chat/report результат остаётся без записи и может содержать открытый QRPE; это **корректно до действия**.
5. **F-P-05 / PR-05:** актуальные README/guides теперь различают исторический read-only pilot, source-level opt-in writer+Viewer, установленные браузер/Helper и отсутствующий issuer. Исторические reviews/кандидатные документы не редактировались.

**Ограничения, которые нельзя считать устранёнными:** HMAC удостоверяет только владение тестовым/внешним ключом, не личность пользователя или его право менять реальный проект. Поля evidence с локальными хешами устанавливают целостность, а не истинность канонов. Доступ к файловой системе вне wrapper и прямой вызов внутренней функции с принудительным `trusted_verified=True` не являются защищёнными production API. Выполненные внешние побочные эффекты не отменяются через `reconsider_action`. Непосредственное автономное исполнение универсальной Lens/QRPE research, O/D migration, future effect occurrences и фактический Helper не добавлены. Полный санкционированный revision R/Context — отдельная будущая capability, не автопринятая политика.

## Доказательства

`tests/rdg-v6-reviewed-integrity.test.cjs` — новые реальные package negative/positive tests на silent R/Context edits, meta-root, подписи Action selection/link/QRPE, попытку unsigned source graph create и сохранение receipt. `tests/rdg-v6-lens-real-application.test.cjs` — отрицательные Lens cases invalid graph и недоказанного Lens effect QRPE; успешная signed applied Lens после writer read-back не оставляет ошибочного skipped R/open QRPE. Синтетические receipts в тестах подписываются временными случайными ключами, а не настоящими пользовательскими разрешениями.

```bash
cd /workspace/repos/rd-graphs
node --test tests/rdg-v6-reviewed-integrity.test.cjs tests/rdg-v6-lens-real-application.test.cjs tests/rdg-v6-action-reconsider-writer.test.cjs
node --test tests/*.test.cjs
node --test tools/rd-graph-viewer-smoke.test.cjs
```

**Следующие gates (не выполненные решения):** определить законные actor/workspace grants и authenticated issuer до реального write; отдельно выбрать стратегию Action ID/canon evaluator и санкционированной R/Context revision; защищённое выполнение внешних effects; настоящий Helper/browser E2E. Отсутствие fixed External Dependencies block, clone-per-Lens и mandatory persisted LensRun — сохранённое пользовательское направление.
