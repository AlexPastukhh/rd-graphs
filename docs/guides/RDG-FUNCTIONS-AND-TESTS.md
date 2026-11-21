# RDG — функции, код и тесты

> **СТАТУС: ДЕЙСТВУЮЩАЯ КАРТА ПРОВЕРОК.** Для основного `rdg-decision-v1`; совместимость отмечена отдельно. Тест доказывает указанный сценарий, а не все возможные комбинации пользовательских данных.

## Модель и источники истины

| Функция / ожидаемое поведение | Реализация | Где проверить |
| --- | --- | --- |
| R/Decision/Action, общие участники, последнее основание и cascade | [kernel](../../tools/rdg-decision-model.py) | [модель](../../tests/rdg-decision-model.test.py): shared identity, rootless cycle, last basis |
| Контекст принятия не является структурным родителем; copy/capture сохраняют границы | [kernel](../../tools/rdg-decision-model.py), [Application](../../tools/rdg-portable-service.py) | [контекст и remap](../../tests/rdg-decision-model.test.py), [reusable API](../../tests/rdg-portable-service.test.py) |
| Граф/Структура/фокус: реальные вхождения, группы, области без owner writes | [проектор](../../tools/rdg-visual-projection.js), [UI](../../tools/rdg-decision-ui.js) | [структура](../../tests/rdg-decision-structure.test.cjs), [desktop](../../tests/visual/rdg-decision-desktop.cjs) |
| Общий банк Context, вложенные группы, поиск/CRUD/переносы и прежние ID | [UI](../../tools/rdg-decision-ui.js), [Application](../../tools/rdg-portable-service.py) | [desktop](../../tests/visual/rdg-decision-desktop.cjs): process-wide context bank; модель/copy — [analysis suite](../../tests/rdg-analysis.test.py); [приёмка ТЗ](RDG-DECISION-V1-CONTRACT.md#группы-контекстов-процесса) |
| Result/выбор/размещение различаются; подтверждение требует evidence и guards | [kernel](../../tools/rdg-decision-model.py) | [completion, observed pins, locks](../../tests/rdg-decision-model.test.py) |

T5 Planning Meta Action в исходниках: [Action/refs](../../tools/rdg-decision-model.py), [Application](../../tools/rdg-portable-service.py), [batch](../../tools/rdg-batch.py), [API-приёмка](../../tests/rdg-planning-meta-actions.test.py) и [Viewer](../../tests/visual/rdg-planning-meta-actions.cjs); runtime определяется точным READY, Windows/UX отдельно.

<!-- rdg-test-ci: tests/rdg-decision-model.test.py::test_losing_last_basis_cascades_selection_but_preserves_confirmed_fact -->
<!-- rdg-test-ci: tests/rdg-decision-model.test.py::test_rootless_cycle_does_not_support_itself -->
<!-- rdg-test-ci: tests/rdg-decision-model.test.py::test_decision_process_context_is_not_part_of_reusable_template -->
<!-- rdg-test-ci: tests/rdg-decision-model.test.py::test_action_and_requirement_completion_use_evidence_and_real_obligations -->

## Политики и инвалидация

| Функция / ожидаемое поведение | Реализация | Где проверить |
| --- | --- | --- |
| Общий каталог, версии, типы ролей, пути и конечный словарь наблюдений | [политики/resolver](../../tools/rdg-dependency-policies.py), [схема](../../tools/contracts/rdg-decision-v1.schema.json) | [матрица kind/watch/operation и отношений](../../tests/rdg-dependency-policies-v2.test.py) |
| Изменение данных → review; потеря применимости → disabled; восстановление не активирует | [политики](../../tools/rdg-dependency-policies.py), [writer](../../tools/rdg-decision-model.py) | [applicability/lifecycle, locked removal, atomic failure](../../tests/rdg-dependency-policies-v2.test.py) |
| Inspector: зависимости/влияния, постоянные группы, конкретные инстансы и pinned version | [UI](../../tools/rdg-decision-ui.js), [read projection](../../tools/rdg-dependency-policies.py) | [per-actor/context snapshots](../../tests/rdg-dependency-policies-v2.test.py), [группы/инстансы/возврат](../../tests/visual/rdg-decision-desktop.cjs) |
| Инвалидация: карточки, одно review на элемент, разные циклы отключения, история | [read projection](../../tools/rdg-dependency-policies.py), [UI](../../tools/rdg-decision-ui.js) | [review/disabled cycles, legacy fallback, snapshots](../../tests/rdg-dependency-policies-v2.test.py), [карточки и переходы](../../tests/visual/rdg-decision-desktop.cjs) |

<!-- rdg-test-ci: tests/rdg-dependency-policies-v2.test.py::test_v2_every_observation_operation_family_executes -->
<!-- rdg-test-ci: tests/rdg-dependency-policies-v2.test.py::test_v2_all_relation_kind_pairs_match_in_both_directions -->
<!-- rdg-test-ci: tests/rdg-dependency-policies-v2.test.py::test_v2_applicability_latches_until_explicit_activation -->
<!-- rdg-test-ci: tests/rdg-dependency-policies-v2.test.py::test_v2_instances_keep_each_actor_with_its_observed_members -->
<!-- rdg-test-ci: tests/rdg-dependency-policies-v2.test.py::test_v2_invalidation_review_groups_causes_and_keeps_resolution_cycles -->
<!-- rdg-test-ci: tests/rdg-dependency-policies-v2.test.py::test_v2_invalidation_disabled_cycles_wait_for_activation_and_keep_history -->
<!-- rdg-test-ci: tests/rdg-dependency-policies-v2.test.py::test_v2_invalidation_legacy_missing_evidence_is_not_fabricated -->

## Файндинги

Новый writable surface и совместимость старых данных проверяются отдельно. Семантика — в [смысловом источнике](../lenses/bootstrap/model.md#findings-и-основания-вывода), форматы и приёмка — в [техническом ТЗ](RDG-DECISION-V1-CONTRACT.md#приёмка-и-порядок-реализации).

| Функция / ожидаемое поведение | Реализация | Где проверить |
| --- | --- | --- |
| Четыре типа, вопросы/ограничения, отдельные review/disposition и относительный scope | [Finding](../../tools/rdg-findings.py), [kernel](../../tools/rdg-decision-model.py) | [Finding compatibility](../../tests/rdg-findings.test.py): proof/scopes/completion; [analysis](../../tests/rdg-analysis.test.py): новые subject/types/guards |
| Subject definition → review Finding; дополнительные политики, disabled/активация | [общий resolver](../../tools/rdg-dependency-policies.py) | [Finding suite](../../tests/rdg-findings.test.py), [матрица всех kinds](../../tests/rdg-dependency-policies-v2.test.py) |
| Прежние response/proposal payloads: чтение, основания, completion и явный перенос | [kernel](../../tools/rdg-decision-model.py), [analysis](../../tools/rdg-analysis.py) | [совместимость Finding](../../tests/rdg-findings.test.py), [перенос](../../tests/rdg-analysis.test.py) |
| Вкладка Decision, роли/происхождение контекста, Canon и возврат; ширина сведений и один owner в обоих видах | [UI](../../tools/rdg-decision-ui.js), [проектор](../../tools/rdg-visual-projection.js) | [проекция](../../tests/rdg-decision-structure.test.cjs), [desktop](../../tests/visual/rdg-decision-desktop.cjs): Finding acceptance |
| Только Decision-subject, запрет новых resolve/proposals, защищённый производный контекст и комментарии | [analysis](../../tools/rdg-analysis.py), [kernel](../../tools/rdg-decision-model.py) | [analysis suite](../../tests/rdg-analysis.test.py): subject, manual/derived, disabled provenance, locks, циклы и ограниченное по времени открытие разветвлённого графа |
| Обязательность R через новый/существующий Decision, явный перенос старой находки, remap групп/комментариев | [analysis](../../tools/rdg-analysis.py), [copy](../../tools/rdg-portable-model.py) | [analysis suite](../../tests/rdg-analysis.test.py), [API](../../tests/rdg-portable-service.test.py), [desktop](../../tests/visual/rdg-decision-desktop.cjs) |
| Подтверждения как Context, явный перевод старого Evidence, отсутствие Finding/Evidence на canvas/в дереве | [analysis](../../tools/rdg-analysis.py), [kernel](../../tools/rdg-decision-model.py), [проектор](../../tools/rdg-visual-projection.js) | [analysis suite](../../tests/rdg-analysis.test.py), [API](../../tests/rdg-portable-service.test.py), [Structure](../../tests/rdg-decision-structure.test.cjs), [desktop](../../tests/visual/rdg-decision-desktop.cjs) |

<!-- rdg-test-ci: tests/rdg-analysis.test.py::test_only_decision_accepts_new_findings -->
<!-- rdg-test-ci: tests/rdg-analysis.test.py::test_two_findings_and_manual_share_one_row_and_keep_role -->
<!-- rdg-test-ci: tests/rdg-analysis.test.py::test_dynamic_source_retains_recorded_provenance_while_disabled -->
<!-- rdg-test-ci: tests/rdg-analysis.test.py::test_grouping_does_not_invalidate_content_but_fact_edit_does -->
<!-- rdg-test-ci: tests/rdg-findings.test.py::test_subject_content_invalidates_finding_with_named_cause -->
<!-- rdg-test-ci: tests/rdg-findings.test.py::test_completion_of_resolution_decisions_does_not_set_finding_resolved -->
<!-- rdg-test-ci: tests/rdg-portable-service.test.py::test_finding_schema_preflight_retry_and_restart_share_writer -->
<!-- rdg-test-ci: tests/rdg-portable-service.test.py::test_finding_copy_remaps_subject_context_provenance_and_evidence -->

## Хранение, план и API

| Функция / ожидаемое поведение | Реализация | Где проверить |
| --- | --- | --- |
| schema → readonly preflight → apply → receipt; actor/scopes/CAS и exact retry | [Application](../../tools/rdg-portable-service.py), [store](../../tools/rdg-portable-store.py) | [Application](../../tests/rdg-portable-service.test.py), [catalog recovery](../../tests/rdg-dependency-policies-v2.test.py) |
| Заголовок Graph: общий writer graph_title, CAS/locks, техническая History, каталог/Markdown, сохранность paper identity и historical pins | [kernel](../../tools/rdg-decision-model.py), [Application](../../tools/rdg-portable-service.py), [publisher](../../tools/rdg-lens-publish.py) | [discovery/roles/guards](../../tests/rdg-api-discovery.test.py), [publication/navigation recovery](../../tests/rdg-structured-lenses.test.py) |
| Обнаружение API: основной/legacy профиль, типизированные add-формы, paper capabilities, locks и прямые Agent reads | [Application](../../tools/rdg-portable-service.py), [builders](../../tools/rdg-workflow-commands.py), [Agent](../../tools/rdg-agent.py) | [discovery](../../tests/rdg-api-discovery.test.py), [gateway](../../tests/rdg-gateway.test.py); [матрица](RDG-DECISION-V1-CONTRACT.md#матрица-операций-api-для-ии) |
| T1: компактный overview/item, адресные facets, cursor с pin снимка, пагинация Plan/History и legacy full | [read-проектор](../../tools/rdg-compact-read.py), [Application](../../tools/rdg-portable-service.py), [Agent](../../tools/rdg-agent.py), [CLI](../../tools/rdg-portable.py) | [компактное чтение](../../tests/rdg-compact-read.test.py): отсутствие write, уменьшение bytes, facets, stale cursor, History; facet Questions поддерживает текущие canonical Questions |
| B03A: адресные focus/branch, полные bodies, parents/shared/cycle refs, материалы и pinned --all-pages | [Проектор](../../tools/rdg-scoped-read.py), общий [read](../../tools/rdg-portable-service.py), [Agent](../../tools/rdg-agent.py)/[CLI](../../tools/rdg-portable.py) | [Приёмка](../../tests/rdg-scoped-read.test.py): scope, циклы, immutable memo/oracle, no-write, source/Plan/Registry pins и CLI; [Gateway](../../tests/rdg-gateway.test.py), [полный пример](../../tests/rdg-current-example.test.py); [ручной benchmark](../../tests/rdg-scoped-read-benchmark.py) |
| T2: атомарный пакет одного owner/Plan, alias→ID, до 100 шагов, один CAS/receipt | [batch-проектор](../../tools/rdg-batch.py), [Application](../../tools/rdg-portable-service.py), [Agent](../../tools/rdg-agent.py), [CLI](../../tools/rdg-portable.py) | [batch suite](../../tests/rdg-batch.test.py): preflight/no-write, поздняя ошибка, CAS, retry, одно создание+размещение; [HTTP gateway](../../tests/rdg-gateway.test.py) — тот же общий writer; ограничения/бенчмарки — [план](RDG-DEVELOPMENT-PLAN.md#удобство-api-для-ии) |
| T3 Questions и T4 оценки Action: CRUD/Viewer, происхождение user_answer, history/version guard, явный legacy-перенос, copy/remap с изоляцией копий, batch и estimates definition-review | [kernel](../../tools/rdg-decision-model.py), [Questions](../../tools/rdg-questions.py), [Application](../../tools/rdg-portable-service.py), [Viewer](../../tools/rdg-decision-ui.js) | [T3/T4 acceptance](../../tests/rdg-questions-estimates.test.py), [regression](../../tests/rdg-question-first-slice.test.py), [HTTP](../../tests/rdg-gateway.test.py), [browser/F5](../../tests/visual/rdg-question-editing.cjs) |
| B02B адресные рекомендации: тексты, все типы привязок, CRUD/compact/copy и возврат | [resolver](../../tools/rdg-recommendations.py), [Application](../../tools/rdg-portable-service.py), [Viewer](../../tools/rdg-decision-ui.js) | [API](../../tests/rdg-recommendations-authoring.test.py), [browser](../../tests/visual/rdg-recommendations-authoring.cjs) |
| B02A теория Decision/Action: «Каноны» (включая известные ошибки) и «Общее», запрет нового авторинга теории R, legacy-чтение без автозаписи, API/batch, before/after, review и Graph/Structure/F5 | [kernel](../../tools/rdg-decision-model.py), [Application](../../tools/rdg-portable-service.py), [Viewer](../../tools/rdg-decision-ui.js) | [B02A](../../tests/rdg-decision-theory.test.py), [HTTP](../../tests/rdg-gateway.test.py), [browser](../../tests/visual/rdg-decision-theory.cjs) |
| T1/T2 короткий сценарий без живых owners: непринятые альтернативы, Context/Canon/Finding, Plan, адресное чтение и сравнительная стоимость | [тест сценария](../../tests/rdg-t1-t2-workflow.test.py), общий [Application](../../tools/rdg-portable-service.py) | [workflow suite](../../tests/rdg-t1-t2-workflow.test.py): два проверяемых сценария, измерения bytes/локального времени, проверка эквивалентности 10 Graph-команд; это не автономный ИИ-тест или p95 |
| Plan/layout/history, порядок/время, restart без потери facts | [Application](../../tools/rdg-portable-service.py), [проектор](../../tools/rdg-visual-projection.js) | [Decision integration](../../tests/rdg-decision-integration.test.py), [desktop](../../tests/visual/rdg-decision-desktop.cjs) |
| History: четыре режима, реальные R activity, косметическое переименование, сохранённые снимки | [проекция](../../tools/rdg-history-view.py), [Application](../../tools/rdg-portable-service.py), [UI](../../tools/rdg-decision-ui.js) | [History suite](../../tests/rdg-history-view.test.py), [API](../../tests/rdg-portable-service.test.py), [desktop](../../tests/visual/rdg-decision-desktop.cjs) |
| Маркеры начала/конца без Action, дата/время, общая часть один раз и корневые группы | [model](../../tools/rdg-portable-model.py), [UI/проектор](../../tools/rdg-visual-projection.js) | [Decision integration](../../tests/rdg-decision-integration.test.py), [линейный объём](../../tests/rdg-plan-view.test.cjs), [desktop](../../tests/visual/rdg-decision-desktop.cjs) |
| Полный текущий пример, exact retry, временные ветви без выбора Decision | [создание примера](../../tools/rdg-current-example.py) | [изолированная приёмка](../../tests/rdg-current-example.test.py) |
| ready/lens/copy, rebind, общий Registry, namespace isolation | [model](../../tools/rdg-portable-model.py), [store](../../tools/rdg-portable-store.py) | [Application](../../tests/rdg-portable-service.test.py); дополнительно [system suite](../../tests/rdg-decision-system.test.py) |
| Сборка, gateway, browser auth, F5, одинаковые факты UI/API | [server](../../tools/rdg-server.py), [gateway](../../tools/rdg-gateway.py), [CI](../../tools/rdg-ci.py) | [server/gateway](../../tests/rdg-server.test.py), [packaged browser](../../tests/visual/rdg-server.cjs) |
| Owner-run установка из GitHub CI, чистота source mirror, provenance/digest, отдельный runtime | [installer](../../deploy/rdg-server/Install-RDGFromGitHub.ps1), [updater](../../deploy/rdg-server/Update-RDG.ps1), [порядок установки](RDG-OPERATIONS.md#разработка-и-обновление-серверного-runtime) | [GitHub delivery](../../tests/rdg-github-delivery.test.py), [CD](../../tests/rdg-cd.test.py); Windows/live acceptance отдельно |
| Упаковка новых Python-модулей T1/T2 в preview и серверный ZIP | [preview inventory](../../tools/rdg-preview-package.py), [server package](../../tools/rdg-server-package.py) | [CI package](../../tests/rdg-ci.test.py): manifest, hashes и наличие обоих модулей |
| Прежние L1/L2 и operation locks `rdg-core-v1` | [прежний core](../../tools/rdg-core-model.py) | [native compatibility](../../tests/rdg-native-dependencies.test.py), [locks](../../tests/rdg-locks.test.py) |

<!-- rdg-test-ci: tests/rdg-portable-service.test.py::test_preacceptance_retry_keeps_logical_ids_and_accepts_one_result -->
<!-- rdg-test-ci: tests/rdg-api-discovery.test.py::test_every_advertised_decision_command_has_a_readonly_form -->
<!-- rdg-test-ci: tests/rdg-compact-read.test.py::test_summary_is_small_paginated_and_unchanged_reads_do_not_write -->
<!-- rdg-test-ci: tests/rdg-compact-read.test.py::test_addressed_context_canon_findings_and_invalid_filters -->
<!-- rdg-test-ci: tests/rdg-compact-read.test.py::test_plan_history_pages_and_legacy -->
<!-- rdg-test-ci: tests/rdg-batch.test.py::test_schema_preflight_atomic_apply_receipt_restart_exact_retry -->
<!-- rdg-test-ci: tests/rdg-batch.test.py::test_bad_final_step_and_bad_plan_cannot_commit_first_steps -->
<!-- rdg-test-ci: tests/rdg-batch.test.py::test_stale_revision_and_preview_pin_are_atomic -->
<!-- rdg-test-ci: tests/rdg-batch.test.py::test_preacceptance_interruption_retries_original_batch -->
<!-- rdg-test-ci: tests/rdg-question-first-slice.test.py::test_create_answer_assess_and_read_links_without_false_completion -->
<!-- rdg-test-ci: tests/rdg-question-first-slice.test.py::test_fails_closed_for_unproven_user_answer_generic_edit_and_foreign_reference -->
<!-- rdg-test-ci: tests/rdg-question-first-slice.test.py::test_change_condition_marks_assessment_stale_and_copy_preserves_it -->
<!-- rdg-test-ci: tests/rdg-question-first-slice.test.py::test_answer_edit_remove_preserves_history_and_invalidates_assessment -->
<!-- rdg-test-ci: tests/rdg-question-first-slice.test.py::test_existing_question_without_answer_history_stays_valid -->
<!-- rdg-test-ci: tests/rdg-question-first-slice.test.py::test_question_panel_mode_is_session_only_and_validates_selected_id -->
<!-- rdg-test-ci: tests/rdg-t1-t2-workflow.test.py::test_isolated_branch_compact_read_and_metrics -->
<!-- rdg-test-ci: tests/rdg-t1-t2-workflow.test.py::test_ten_graph_operations_batch_vs_separate_transactions -->
<!-- rdg-test-ci: tests/rdg-gateway.test.py::test_gateway_atomic_batch_aliases_preflight_and_retry -->
<!-- rdg-test-ci: tests/rdg-gateway.test.py::test_gateway_question_create_answer_assess_readback -->
<!-- rdg-test-ci: tests/rdg-api-discovery.test.py::test_typed_add_forms_publish_each_current_kind_with_receipts_and_exact_retry -->
<!-- rdg-test-ci: tests/rdg-api-discovery.test.py::test_form_request_keeps_cas_and_rejected_changes_are_atomic -->
<!-- rdg-test-ci: tests/rdg-gateway.test.py::test_gateway_decision_typed_form_preflight_receipt_and_retry -->
<!-- rdg-test-ci: tests/rdg-decision-integration.test.py::test_pr6_order_layout_retry_and_restart -->
<!-- rdg-test-ci: tests/rdg-decision-integration.test.py::test_pr6_plan_retry_after_staging_and_time_edit_preserves_order -->
<!-- rdg-test-ci: tests/rdg-native-dependencies.test.py::test_l1_and_l2_have_distinct_direct_scope -->
<!-- rdg-test-ci: tests/rdg-locks.test.py::test_edit_lock_does_not_implicitly_lock_link_or_remove -->
<!-- rdg-test: tests/rdg-decision-system.test.py::test_system_template_instances_copy_layout_and_namespace_safety -->

<!-- rdg-test-ci: tests/rdg-history-view.test.py::test_selection_and_withdrawal_record_real_transitive_requirement_activity -->
<!-- rdg-test-ci: tests/rdg-history-view.test.py::test_cosmetic_and_semantic_rename_are_explicit_and_only_semantic_invalidates -->
<!-- rdg-test-ci: tests/rdg-history-view.test.py::test_unknown_old_rename_is_not_guessed_cosmetic -->
<!-- rdg-test-ci: tests/rdg-history-view.test.py::test_relation_endpoint_snapshot_keeps_its_name_after_later_rename -->
<!-- rdg-test-ci: tests/rdg-portable-service.test.py::test_history_modes_and_requirement_activity_do_not_change_plan_or_owner -->
<!-- rdg-test-ci: tests/rdg-current-example.test.py::test_full_example_retry_and_plan_views_preserve_actual_choices -->

<!-- rdg-test-ci: tests/rdg-decision-integration.test.py::test_pr6_plan_markers_start_without_action_and_join_shared_continuation_with_client_parity -->
<!-- rdg-test-ci: tests/rdg-decision-integration.test.py::test_pr6_plan_markers_reject_invalid_time_end_and_readonly_author_atomically -->
<!-- rdg-test-ci: tests/rdg-decision-integration.test.py::test_pr6_plan_copy_preserves_optional_markers_and_maps_root_decisions -->

## Производительность RDG

При изменении Application, FileStore, модели Decision, writer, API или Explorer найди затронутый путь в таблице. Проверь инвариант на обычной точке входа этой функции. Точный формат ответов и предметные правила принадлежат [техническому контракту](RDG-DECISION-V1-CONTRACT.md). Числа и условия уже выполненных измерений собраны в [текущем состоянии](RDG-CURRENT-STATE.md#одно-сканирование-метаданных-для-каталога-и-полного-чтения-2026-11-19). Полная нагрузочная приёмка остаётся в [B07](../../BACKLOG-IMPROVEMENTS.md#p1--измерить-и-закрыть-послев-ходе-сквозного-сценария).

Сначала убирай повторную работу на том же снимке, ограничивай объём читаемых данных областью запроса и выноси необязательные вычисления с пути первого кадра. Между запросами храни только проверенные производные результаты, с ключом по влияющим входам, пределами числа записей и объёма памяти. Источники истины, проверка доступа и правила записи остаются в общем Application и FileStore.

### Что уже работает и что сохранять

| Путь и действующая оптимизация | Инвариант при изменении | Проверка |
| --- | --- | --- |
| Каталог и чтение пакета. [Application](../../tools/rdg-portable-service.py) передаёт результаты одного сканирования namespace в [FileStore](../../tools/rdg-portable-store.py) и чтения текущих связанных пакетов | В пределах одного `catalog`, `recommendation_catalog` или полного `read` используй одно сканирование. Сохраняй read-lock, проверку доступа, обнаружение дублей, проверку head, digest и receipt/witness. При добавлении ссылки или новой проекции проверь, что вложенный вызов использует уже полученные метаданные | [Подсчёт сканирований](../../tests/rdg-portable-service.test.py) и [проверки FileStore](../../tests/rdg-portable-store.test.py) |
| Компактное и адресное чтение T1/B03A. [Проекции](../../tools/rdg-compact-read.py) и [focus/branch](../../tools/rdg-scoped-read.py) возвращают выбранные поля и страницы. Полные тела выдаются один раз, повторные вхождения используют ссылки | Сохраняй совместимый `full`, границы области, выбранные поля, порядок, ссылочную целостность и привязку страниц к одному снимку. Для новой страницы или поля проверяй актуальность соответствующих Graph/Plan, Registry и источников. Изменение только Plan может сделать курсор недействительным при прежней ревизии Graph | [Компактное чтение](../../tests/rdg-compact-read.test.py) и [scope, курсоры и CLI](../../tests/rdg-scoped-read.test.py) |
| Визуальная проекция и History. [Application](../../tools/rdg-portable-service.py) хранит ограниченные производные результаты. Компактные страницы History используют одно проверенное восстановление, `detail=item` собирает нужную запись напрямую | Проверяй права, принятый head и целостность источников до выдачи из кэша. Для History сохраняй проверку артефактов inventory под read-lock. Для визуальной проекции учитывай входы Graph, представления и раскладки. Проверяй холодный проход, попадание, изменение только Plan или раскладки, отзыв прав, повреждённые данные и независимость результата от мутации предыдущего ответа | [Ключи, лимиты, изоляция и тёплое чтение](../../tests/rdg-projection-cache.test.py) |
| Открытие Explorer. [Viewer](../../tools/rdg-decision-ui.js) показывает Graph или Working Graph и Plan после `read`. History загружается в фоне, общий список применений через `dependency_usage` запрашивается для «Политик» | Обычное открытие использует один основной `read` и один отдельный `history`. Graph и Plan видны при задержанном History. Закрытая панель подробностей не добавляет запросов. Поздний ответ принимается только для того же экрана и снимка. Повтор History и переключения панелей используют свой действующий маршрут | [Сценарии Explorer](../../tests/visual/rdg-decision-desktop.cjs), [HTTP Gateway](../../tests/rdg-gateway.test.py) |
| Подробности политик. [Application](../../tools/rdg-portable-service.py) переиспользует ограниченный кэш списка кандидатов, вычисляет записи применений для запрошенной страницы и отдельно выдаёт инвалидации | Сохраняй независимость `localApplications` и `invalidationRecords`, точечный `recordId`, совместимый полный ответ и явную кнопку продолжения в Viewer. Все страницы сохраняют порядок и в сумме совпадают с полным ответом. При продолжении проверяются текущие права, head и ревизии, включая случай изменения только Plan. Размер страницы ограничен 4 000 000 байт. Фильтры и счётчики Viewer относятся к загруженным записям, пока есть продолжение | [Совпадение страниц, отзыв прав и курсор](../../tests/rdg-dependency-policies-v2.test.py), [Gateway](../../tests/rdg-gateway.test.py), [Viewer](../../tests/visual/rdg-decision-desktop.cjs) |
| Большой Graph. [Модель](../../tools/rdg-decision-model.py) использует индексы исходящих связей, групп и сущностей. [Viewer](../../tools/rdg-decision-ui.js) ищет узлы по визуальному ID и считает пересечения для меток только при наличии меток | При добавлении правил, связей или визуальных элементов используй индексы на неизменяемых входах. Проверяй, что обработка каждого узла или связи не возвращает повторный обход всего Graph. Сохраняй результаты поддержки, завершённости и границ, порядок и видимость связей и меток, работу алиасов, фокуса и рабочих областей | [Модель](../../tests/rdg-decision-model.test.py), [проекции и вхождения](../../tests/rdg-visual-occurrences.test.cjs), [desktop](../../tests/visual/rdg-decision-desktop.cjs) и сравнительный прогон большого графа |
| Подготовка writer и batch. [Вычислитель](../../tools/rdg-decision-model.py) переиспользует производные отношения только внутри одного вызова `native_dependency_impacts` с `fresh=True` | Каждый шаг сохраняет собственный пересчёт политик и evidence, промежуточную валидацию и события. Один и тот же словарь Graph может меняться между шагами. Кэш завершается вместе с вычислением, включая исключение. Сохраняй равенство prepared effects, CAS, атомарность, receipt и повтор исходной команды | [Локальный кэш writer](../../tests/rdg-writer-calculation-cache.test.py), [batch и поздняя ошибка](../../tests/rdg-batch.test.py) |

<!-- rdg-test-ci: tests/rdg-portable-service.test.py::test_catalog_and_full_read_reuse_one_namespace_scan -->
<!-- rdg-test-ci: tests/rdg-projection-cache.test.py::test_compact_history_reuses_reconstruction_across_pages_and_facets -->
<!-- rdg-test-ci: tests/rdg-projection-cache.test.py::test_revoked_real_grant_and_new_application_cannot_reuse_cache -->
<!-- rdg-test-ci: tests/rdg-projection-cache.test.py::test_tampered_historical_graph_still_fails_warm_compact_history -->
<!-- rdg-test-ci: tests/rdg-dependency-policies-v2.test.py::test_dependency_details_pages_match_full_records_and_recheck_revision_and_scope -->
<!-- rdg-test-ci: tests/rdg-writer-calculation-cache.test.py::test_batch_prepare_exact_parity_including_plan_and_policy_projections -->

### Как проверить изменение

1. **Начни с пути и фактов.** Проверь, нужен ли новому экрану полный Graph, достаточно ли адресного чтения и что действительно должно быть готово к первому кадру. Измерь участок до изменения. Сохраняй дорогие подробности за отдельным запросом или страницей, если экран использует их по требованию. Увеличение размера ответа должно соответствовать данным, которые использует вызывающая сторона.
2. **Сначала проверь эквивалентность.** Сравни ответы и порядок записей на одном снимке. При намеренном изменении формата проверь ожидаемую разницу и совместимость прежнего входа. Для записи сравни эффекты, Graph, Plan, события, ошибки и receipt. Для кэша проверь инвалидирование на изменившихся входах, доступ после отзыва прав и ограничение памяти. Стабильные регрессии проверяй числом сканирований, RPC, страниц, размером ответа и фактическим порядком готовности экранов.
3. **Меняй одну характеристику нагрузки за раз.** Для проекций используй временные Graph на 50/500/5000 блоков. Плотность связей, число событий, объём Plan, число связанных пакетов и размер каталога проверяй раздельно. Для каталога подходят изолированные конфигурации на 3/16/38 процессов с фиксированным набором линз. Для writer используй временный FileStore. Рабочий RDG подходит для небольшого read-only замера с фиксированной ревизией.
4. **Разделяй уровни и условия измерений.** Запиши SHA, среду, характеристики фикстуры, сценарий первого вызова и прогретых повторов. На Application измеряй вычисление, при необходимости CPU, память и файловые операции. Для HTTP записывай TTFB, время полного ответа, байты и число RPC. В браузере измеряй отдельно старт Explorer, открытие Graph/Working Graph, готовность Plan и History, интервал после HTTP до DOM или контрольного кадра. Проводя замер браузера, фиксируй видимость вкладки. Время модели ИИ учитывай отдельно. Указывай число повторов, p50, разброс и p95 при достаточном числе измерений.
5. **Сверяй бюджет на настоящем пути.** У [Gateway](../../tools/rdg-gateway.py) таймаут ожидания upstream 60 с и предел тела ответа 16 000 000 байт. Проверяй запас отдельно от CPU и времени отрисовки. Для изменённого пути сопоставь до/после на одной нагрузке и объясни, если выросли байты, RPC или вычисления. Медианы прошлых запусков служат ориентиром для сравнения. Локальные проверки, полный CI и замеры установленной Windows-сборки дают отдельные результаты.

Изолированный [benchmark адресного чтения](../../tests/rdg-scoped-read-benchmark.py) запускается из корня репозитория. Он измеряет Application для full/focus/branch, размечает первые вызовы и повторы, сохраняет размеры ответа и число страниц. Для каждого прогона указывай новый выходной файл.

```sh
python3 -B tests/rdg-scoped-read-benchmark.py --sizes 50 500 5000 --samples 5 \
  --output /workspace/repo/Workfiles/rdg-scoped-read-benchmark.json
```

Для Viewer используй [штатный запуск Chromium](../../tests/visual/README.md). Он проверяет поведение UI на изолированных данных. Для замеров полного Explorer на большом графе и установленных Windows-версий смотри условия и расположение сырых результатов в [срезе B07](RDG-CURRENT-STATE.md#начальное-чтение-и-подробности-больших-графов-2026-11-20).


## Как читать результат

**Обязательный набор:** [CI driver](../../tools/rdg-ci.py), включая зарегистрированные в нём [браузерные проверки](../../tests/visual/README.md#обязательный-ci). Остальные файлы `tests/` не запускаются только потому, что присутствуют в Repo. `rdg-decision-system.test.py`, отдельные migration/storage/WebAuthn/Fortis suites выбираются по изменению и описывают свои границы.

Ссылки на выбранные Python-сценарии выше дополнительно проверяются аудитом документации: тест существует и, где отмечено, его файл входит в CI. Это трассировка, не измерение покрытия строк и не доказательство произвольного сочетания правил.

**Результат:** `rdg-ci/status.json`, `ready.json` и логи того же запуска в Workfiles. **Ограничения:** неизвестные legacy причины, локальные view-фильтры, Windows/UX и отдельные подсистемы — в [плане](RDG-DEVELOPMENT-PLAN.md). [Смысл состояния](../lenses/README.md#владельцы-правил-и-карта-покрытия) не выводится из одного PASS.

Адресуемая теория Decision/Action: [контракт](RDG-DECISION-V1-CONTRACT.md#rdg-theory-addressable-items), реализация [rdg-theory.py](../../tools/rdg-theory.py), [источники](../../tools/rdg-theory-sources.py), [проверки API/Agent/copy/полноты](../../tests/rdg-theory-items.test.py), [сценарий Viewer](../../tests/visual/rdg-decision-theory.cjs).
