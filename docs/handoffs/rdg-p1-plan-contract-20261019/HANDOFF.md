# RDG — продолжение после Candidate P1

Контрольная точка: RDG-P1-PLAN-CONTRACT-20261019.
P1 подготовлен как Candidate-контракт; не whole-baseline committed и не
исполняемый lifecycle. Stage 4 NOT ACCEPTED. Новый код не добавлялся.

## Что читать

1. `../../guides/RDG-TEMPORAL-PLAN-OWNER-CONTRACT-P1.md` — владелец определений P1.
2. `P1-CONTRACT.json` — индекс 20 правил и пяти Candidate Proposals, не Plan schema.
3. `P2-ACCEPTANCE-MATRIX.json` — 20 будущих проверок; PLANNED-NOT-EXECUTED.
4. `CHECKPOINT.json`, `SOURCE-HASHES.json`, `INHERITED-RUNTIME-HASHES.json`.
5. `WR-EVIDENCE-LEDGER.md/.json` — все 53 WR; повышение статусов по документу отсутствует.

Полная историческая v4.1 остаётся в `../rdg-prework-v4.1-final-20261018/`,
исправление P0 и фактические runtime логи — в `../rdg-p0-dependencies-20261018/`.
Оба пакета сохранены без изменений. RDG root — `/workspace/repos/rd-graphs`;
source Gendocen — отдельный `/workspace/repos/gendocen`.

## Подготовлено

Owner identity отдельно от sourcePath; конфликт двух writable owners.
Точные версии и происхождение, candidate отдельно от принятого будущего baseline.
Date/instant/relative/unknown time; окно не считается доказанно выполнимым.
Будущий case не считается фактом; statement, attestation и verification различаются.
recordedAt/knownAt отдельно от effectiveAt; исторический запрос не подменяется
текущей проекцией, а новый candidate не заменяет ранее принятый baseline.
Step ID — вхождение в Plan, не новая identity RDG Action.

Схема v1 всё ещё candidate-only. P1 поля/операции — семантический Candidate,
а не объявление доступного API. Конкретная сериализация и persistence — P2.
Plan acceptance не выбирает Action и не переписывает T1/selectionBasis.
Technical receipt не подтверждает человека, факт или F-P.

## Что реально проверено

`DOCUMENT-CONSISTENCY.json` фиксирует совпадение ID/ссылок/источников и то,
что 32 runtime/fixture файла не менялись после P0. Это документальная проверка,
не исполнение Plan owner/version/as-of. Runtime evidence унаследовано из P0:
88/88 scoped Python, 405/405 Node и два smoke PASS. В P1 эти tests не повторялись.
Постоянное production storage, trusted Helper/event source, installed deployment,
канонический GitHub repo/branch/writer и Gendocen distribution не подтверждены.

## Следующий шаг — P2, ограниченный synthetic pilot

Сначала проверить актуальные пути/mount/права и README/AGENTS. Сверить хеши P1;
не стирать чужие изменения. В RDG нет .git: не заявлять Git diff/commit/push.

Начать с candidate-only Plan create/edit/branch в явно переданном временном
root: owner/path binding, version/CAS, отдельные grants и append-only history.
Использовать временный authority store и синтетические Plan/RDG, не настоящие
bearer credentials. Не выбирать production root или remote destination.

До включения новой версии данных уточнить сериализацию lifecycle и snapshots
как Candidate Proposal, сопоставить с P1 и расширить P0 coverage contract:
старый current-only consumer не должен молча принимать новые поля как fully covered.
Для каждого writer-перехода нужны denied-unchanged, CAS/race/revoke-before-commit,
failpoints/recover и сохранение RDG T1/selectionBasis.

Baseline acceptance, event-attest и графовый Action.select должны оставаться
разными правами. Их реальные trusted user/event пути не имитировать строкой
by=user или клиентским receipt. Synthetic proof не является real-user acceptance.
Точные serialisation/permission choices сохранять со статусом Candidate;
существенный user-facing design fork вынести на отдельное решение.

P3 — полные Canon/Finding/Proposal и historical evidence; P4 — research graphs;
P5 — UI/external views; P6 — выбранные пользователем production/remote решения;
P7 — retirement после доказанной замены. Эти этапы не объявлены выполненными.
