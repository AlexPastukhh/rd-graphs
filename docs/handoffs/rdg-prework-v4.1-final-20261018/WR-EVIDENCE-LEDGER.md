# WR-01…53 — source/evidence status ledger (Candidate Pre-work v4.1)

## Как читать

Приведённые ссылки указывают на реальные исходники или тесты, когда таковые есть. Наличие файла или теста НЕ означает полную реализацию WR. Поэтому direct_independent_acceptance_proven=false для всех WR: в этом пакете нет независимого полного production acceptance. Статус DONE-LOCAL отражает только проверенный технический пилот. Сигнал FAIL-EXPECTED для WR-31/WR-50 — дефект, не успешная проверка.

| WR | Status | evidence (точный repo path) | Remaining gate |
|---|---|---|---|
| WR-01 | PARTIAL | README.md (preflight; no .git) | repo preflight done; no Git owner diff |
| WR-02 | PARTIAL | source-candidate-prework-v3-reading-copy.md; source-independent-review-v1-reading-copy.md | user decisions preserved, not all PR accepted |
| WR-03 | OPEN | NO DIRECT PROOF: installed Helper UI pending | trusted Helper grant UI |
| WR-04 | DONE-LOCAL | tools/rdg-authority.py; tests/rdg-bearer-package.integration.test.py | bearer for 2 test actors |
| WR-05 | DONE-LOCAL | tools/rdg-authority.py; tests/rdg-bearer-package.integration.test.py | admin issue/amend/revoke/list |
| WR-06 | PARTIAL | tools/rdg-authority.py; tests/rdg-bearer-package.integration.test.py | delegated admin scoped tested |
| WR-07 | DONE-LOCAL | tools/rdg-authority.py; tests/rdg-bearer-package.integration.test.py | revocation race/replay local |
| WR-08 | PARTIAL | tools/rdg-authority.py; tests/rdg-bearer-package.integration.test.py | user-facing useful denial UI |
| WR-09 | PARTIAL | tools/rdg-authority.py; tests/rdg-bearer-package.integration.test.py | full operation path matrix |
| WR-10 | PARTIAL | tools/rdg-authority.py; tests/rdg-bearer-package.integration.test.py | human trust and decision autonomy |
| WR-11 | PARTIAL | tools/rdg-authority.py; tests/rdg-bearer-package.integration.test.py | all redaction/secret logs |
| WR-12 | DONE-LOCAL | tools/rdg-authority.py; tests/rdg-bearer-package.integration.test.py | guard boundary explicit |
| WR-13 | PARTIAL | tools/rdg-v7-model.py; docs/guides/RDG-TYPED-FINDINGS-STAGE2-PILOT.md | F-R/U/O typed; F-P blocked |
| WR-14 | PARTIAL | tools/rdg-v7-model.py; docs/guides/RDG-TYPED-FINDINGS-STAGE2-PILOT.md | questions/evidence/PR multi-relations |
| WR-15 | PARTIAL | tools/rdg-v7-model.py; docs/guides/RDG-TYPED-FINDINGS-STAGE2-PILOT.md | independent dispositions/status |
| WR-16 | PARTIAL | tools/rdg-canon-context-review.py (read-only only) | open canon authoring provenance |
| WR-17 | PARTIAL | tools/rdg-canon-context-review.py (upstream proof incomplete) | upstream comparison end-to-end |
| WR-18 | PARTIAL | tools/rdg-gendocen-t1-history-smoke.py (synthetic T1 only) | T1/prepared-to-working full lifecycle |
| WR-19 | PARTIAL | tools/rdg-v7-model.py; docs/guides/RDG-TYPED-FINDINGS-STAGE2-PILOT.md | selected vs performed/verified |
| WR-20 | PARTIAL | tools/rdg-v7-model.py; docs/guides/RDG-TYPED-FINDINGS-STAGE2-PILOT.md | full Graph API operation inventory |
| WR-21 | PARTIAL | docs/guides/RDG-V7-WORKING-GRAPHS.md | legacy O/D compatibility not migration |
| WR-22 | OPEN | docs/guides/RDG-V7-WORKING-GRAPHS.md | C1 OR C2 plus C3 applied scenario |
| WR-23 | PARTIAL | docs/guides/RDG-V7-WORKING-GRAPHS.md | transient Lens yes, retirement later |
| WR-24 | PARTIAL | docs/guides/RDG-V7-WORKING-GRAPHS.md | research two-chat demonstration |
| WR-25 | OPEN | NO DIRECT PROOF: hide/detach/archive pending | hide/detach/archive/delete/lazy retrieval |
| WR-26 | OPEN | NO DIRECT PROOF: promotion/link pending | cross-graph promotion one owner |
| WR-27 | OPEN | NO DIRECT PROOF: saved success without Finding pending | valuable success without Finding |
| WR-28 | DONE-LOCAL | tools/rdg-gendocen-adapter.py; tests/rdg-gendocen-resources.test.py | RDG JSON read-only Gendocen projection |
| WR-29 | PARTIAL | tools/rdg-gendocen-adapter.py; tests/rdg-gendocen-resources.test.py | stable IDs yes; branch deps gap |
| WR-30 | DONE-LOCAL | tools/rdg-gendocen-adapter.py; tests/rdg-gendocen-resources.test.py | real receipts and stale review in pilot |
| WR-31 | DEFECT-REPRODUCED | repro-branch-membership-gap.py; tests/rdg-gendocen-branch-membership.acceptance.test.py (FAIL-EXPECTED) | missing indirect branch dependency |
| WR-32 | OPEN | NO DIRECT PROOF: narrative Markdown pending | narrative Markdown representation |
| WR-33 | OPEN | tools/rdg-gendocen-adapter.py (external consumer unverified) | external consumer read view |
| WR-34 | PARTIAL | tools/rdg-gendocen-adapter.py; tests/rdg-gendocen-resources.test.py | no silent RDG write, real authorized review pending |
| WR-35 | PARTIAL | tools/graph-apply.py; tests/rdg-bearer-package.integration.test.py | local recovery yes, remote no |
| WR-36 | DECISION-GATE | NO DIRECT PROOF: GitHub owner user decision pending | canonical GitHub repo/branch/writer |
| WR-37 | OPEN | NO DIRECT PROOF: installed Helper/Viewer pending | Helper+Viewer new features installed |
| WR-38 | OPEN | NO DIRECT PROOF: retirement intentionally deferred | no deprecation decision |
| WR-39 | PARTIAL | tools/graph-apply.py; tests/rdg-bearer-package.integration.test.py | scope tests+full regression, no independent review |
| WR-40 | PARTIAL | docs/guides/RDG-GENDOCEN-RESOURCES-STAGE1B.md (license open) | runtime yes, license pending |
| WR-41 | DONE-LOCAL | tools/rdg-v7-model.py; tests/rdg-bearer-package.integration.test.py | candidate-only graph.create |
| WR-42 | DONE-LOCAL | tools/rdg-v7-model.py; tests/rdg-bearer-package.integration.test.py | separate selected Action |
| WR-43 | DONE-LOCAL | tools/rdg-v7-model.py; tests/rdg-bearer-package.integration.test.py | local revoke vs durable commit |
| WR-44 | DONE-LOCAL | tools/rdg-v7-model.py; tests/rdg-bearer-package.integration.test.py | bearer-only client + internal receipt |
| WR-45 | PARTIAL | tools/rdg-temporal-plan.py; tests/rdg-temporal-plan.test.py | standalone Plan read-only no writer |
| WR-46 | PARTIAL | tools/rdg-temporal-plan.py; tests/rdg-temporal-plan.test.py | temporal subset windows/relative dates |
| WR-47 | PARTIAL | tools/rdg-temporal-plan.py; tests/rdg-temporal-plan.test.py | single event hypothetical branching |
| WR-48 | PARTIAL | tools/rdg-temporal-plan.py; tests/rdg-temporal-plan.test.py | qualified actionRef not live owner writes |
| WR-49 | PARTIAL | tools/rdg-temporal-impact.py; tools/rdg-gendocen-t1-history-smoke.py | deadline risk F-R pilot not full Canon |
| WR-50 | DEFECT-REPRODUCED | repro-branch-membership-gap.py; tests/rdg-gendocen-branch-membership.acceptance.test.py (FAIL-EXPECTED) | branch invalidation absent |
| WR-51 | OPEN | NO DIRECT PROOF: Plan writer and attest grants pending | separate plan.write vs event.attest |
| WR-52 | PARTIAL | tools/rdg-gendocen-t1-history-smoke.py (synthetic T1 only) | synthetic T1 yes, Plan history absent |
| WR-53 | PARTIAL | tools/rdg-temporal-plan.py; docs/examples/temporal-plan-candidate-v1.json | Plan read-only not timeline UI |

## Обязательная регрессия P0

Следующий чат должен подтвердить EXPECTED-FAIL тест meaningful branch swap и PASS тест projection cosmetic reorder:

    RDG_GENDOCEN_SOURCE=/workspace/repos/gendocen PYTHONDONTWRITEBYTECODE=1 python3 docs/handoffs/rdg-prework-v4.1-final-20261018/tests/rdg-gendocen-branch-membership.acceptance.test.py -v

До исправления: 2 tests, 1 failure. После исправления: оба PASS, затем scoped и full regression.

## Машинная форма

Полная машиночитаемая структура с resolved_evidence_paths: WR-EVIDENCE-LEDGER.json.
