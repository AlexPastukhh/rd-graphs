# WR-01…53 — P0 checkpoint

Статус: Candidate. Исходный ledger v4.1 сохранён без изменений. Ни один WR не получил независимого полного production acceptance.

WR-31 и WR-50: локальный дефект branch membership исправлен и проверен; статус требований остаётся PARTIAL из-за оставшихся границ.

| WR | Статус | Изменение с v4.1 | Оставшийся gate |
|---|---|---|---|
| WR-01 | PARTIAL | Без изменения статуса | repo preflight done; no Git owner diff |
| WR-02 | PARTIAL | Без изменения статуса | user decisions preserved, not all PR accepted |
| WR-03 | OPEN | Без изменения статуса | trusted Helper grant UI |
| WR-04 | DONE-LOCAL | Без изменения статуса | bearer for 2 test actors |
| WR-05 | DONE-LOCAL | Без изменения статуса | admin issue/amend/revoke/list |
| WR-06 | PARTIAL | Без изменения статуса | delegated admin scoped tested |
| WR-07 | DONE-LOCAL | Без изменения статуса | revocation race/replay local |
| WR-08 | PARTIAL | Без изменения статуса | user-facing useful denial UI |
| WR-09 | PARTIAL | Без изменения статуса | full operation path matrix |
| WR-10 | PARTIAL | Без изменения статуса | human trust and decision autonomy |
| WR-11 | PARTIAL | Без изменения статуса | all redaction/secret logs |
| WR-12 | DONE-LOCAL | Без изменения статуса | guard boundary explicit |
| WR-13 | PARTIAL | Без изменения статуса | F-R/U/O typed; F-P blocked |
| WR-14 | PARTIAL | Без изменения статуса | questions/evidence/PR multi-relations |
| WR-15 | PARTIAL | Без изменения статуса | independent dispositions/status |
| WR-16 | PARTIAL | Без изменения статуса | open canon authoring provenance |
| WR-17 | PARTIAL | Без изменения статуса | upstream comparison end-to-end |
| WR-18 | PARTIAL | Без изменения статуса | T1/prepared-to-working full lifecycle |
| WR-19 | PARTIAL | Без изменения статуса | selected vs performed/verified |
| WR-20 | PARTIAL | Без изменения статуса | full Graph API operation inventory |
| WR-21 | PARTIAL | Без изменения статуса | legacy O/D compatibility not migration |
| WR-22 | OPEN | Без изменения статуса | C1 OR C2 plus C3 applied scenario |
| WR-23 | PARTIAL | Без изменения статуса | transient Lens yes, retirement later |
| WR-24 | PARTIAL | Без изменения статуса | research two-chat demonstration |
| WR-25 | OPEN | Без изменения статуса | hide/detach/archive/delete/lazy retrieval |
| WR-26 | OPEN | Без изменения статуса | cross-graph promotion one owner |
| WR-27 | OPEN | Без изменения статуса | valuable success without Finding |
| WR-28 | DONE-LOCAL | Без изменения статуса | RDG JSON read-only Gendocen projection |
| WR-29 | PARTIAL | Обновлено evidence | Stable IDs and scoped dependencies verified; historical as-of and full production consumers remain open. |
| WR-30 | DONE-LOCAL | Без изменения статуса | real receipts and stale review in pilot |
| WR-31 | PARTIAL | P0: исправлено и проверено локально | Branch-membership defect fixed locally. Complete future evaluator/dynamic multi-branch coverage and independent acceptance remain open. |
| WR-32 | OPEN | Без изменения статуса | narrative Markdown representation |
| WR-33 | OPEN | Без изменения статуса | external consumer read view |
| WR-34 | PARTIAL | Без изменения статуса | no silent RDG write, real authorized review pending |
| WR-35 | PARTIAL | Без изменения статуса | local recovery yes, remote no |
| WR-36 | DECISION-GATE | Без изменения статуса | canonical GitHub repo/branch/writer |
| WR-37 | OPEN | Без изменения статуса | Helper+Viewer new features installed |
| WR-38 | OPEN | Без изменения статуса | no deprecation decision |
| WR-39 | PARTIAL | Обновлено evidence | Fresh scoped/full regression passed; independent production review and installed checks remain open. |
| WR-40 | PARTIAL | Без изменения статуса | runtime yes, license pending |
| WR-41 | DONE-LOCAL | Без изменения статуса | candidate-only graph.create |
| WR-42 | DONE-LOCAL | Без изменения статуса | separate selected Action |
| WR-43 | DONE-LOCAL | Без изменения статуса | local revoke vs durable commit |
| WR-44 | DONE-LOCAL | Без изменения статуса | bearer-only client + internal receipt |
| WR-45 | PARTIAL | Без изменения статуса | standalone Plan read-only no writer |
| WR-46 | PARTIAL | Без изменения статуса | temporal subset windows/relative dates |
| WR-47 | PARTIAL | Без изменения статуса | single event hypothetical branching |
| WR-48 | PARTIAL | Без изменения статуса | qualified actionRef not live owner writes |
| WR-49 | PARTIAL | Без изменения статуса | deadline risk F-R pilot not full Canon |
| WR-50 | PARTIAL | P0: исправлено и проверено локально | Outcome-to-Action invalidation verified for candidate one-branch current projections; Plan history, multi-event and complete semantic evaluation remain open. |
| WR-51 | OPEN | Без изменения статуса | separate plan.write vs event.attest |
| WR-52 | PARTIAL | Без изменения статуса | synthetic T1 yes, Plan history absent |
| WR-53 | PARTIAL | Без изменения статуса | Plan read-only not timeline UI |

Точные пути evidence для всех WR: `WR-EVIDENCE-LEDGER.json`. Новые результаты: `CHECKPOINT.json`, `REAL-ENGINE-MATRIX.json` и логи рядом.

EA-18/EA-34: проявление branch-membership false valid устранено в проверенном scope. Полные оси и Stage 4 не объявляются закрытыми.
