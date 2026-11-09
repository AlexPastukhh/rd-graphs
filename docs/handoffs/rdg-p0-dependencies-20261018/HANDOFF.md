# RDG — продолжение после P0

Статус: Candidate; локальное исправление проверено. Stage 4 NOT ACCEPTED.
Исходная точка: полный пакет `../rdg-prework-v4.1-final-20261018/` и его ZIP,
сохранённые без изменений. Актуальный код — `/workspace/repos/rd-graphs`.
В дереве нет `.git`; commit/push/Windows deployment не выполнялись.

## Сделано

Дефект воспроизведён до правок: acceptance 1 PASS + 1 FAIL, после branch swap
A1/A2 оставались valid. После правок acceptance 2/2 PASS. Новый контракт
`rdg-temporal-review/v1` и оба runner подписывают адресные контексты каждого
Action-step: owner/ref, branch, steps, sequence/косвенные предпосылки, ограничения,
Canon/QRPE/status/selectionBasis. При пропуске подписки подтверждение блокируется.
Глобальный semanticSHA256 не используется как замена точным зависимостям.

Результаты: 88/88 scoped Python, 405/405 full Node, оба runtime smoke PASS,
включая прежние stale-review, T1, hard crash 91, rollback/history/idempotency.
Матрица реального движка: `REAL-ENGINE-MATRIX.json`. Смена ветви пересматривает
обе оценки; cosmetic reorder сохраняет valid; A2-only остаётся адресным.

Код и пределы контракта:
`../../guides/RDG-GENDOCEN-DEPENDENCY-COVERAGE-P0.md`.
Точные команды/логи: `CHECKPOINT.json`; изменения: `CHANGES.patch`;
хеши семи изменённых/новых файлов проекта: `SOURCE-HASHES.json`.
WR-29/31/39/50 обновлены в соседнем WR-ledger; полный набор — все 53 WR.
WR-31/50 остаются PARTIAL: конкретный дефект исправлен локально, полные требования
и независимый production acceptance не заявляются. EA-18/34 закрыты только
в части проверенного контрпримера branch membership.

## Что не доказано

Контракт ограничен текущими read-only проекциями и максимум одной условной
ветвью. Несколько ветвей блокируют guarded регистрацию. Старые consumers,
не использующие общий регистратор, не становятся исправленными автоматически.
После изменения исходников нужно заново построить проекции. Все активные
 deadlines включены как консервативные общие основания review.

`historicalSnapshotAvailable=false`: текущая revision не удостоверяет данные,
известные на T1. Unknown coverage check может сохранить диагностическое
состояние; отклонённый validate не создаёт receipt. Истинность F-P, личность
пользователя, Plan writer/event attestation и установленная Windows-система
этим исправлением не подтверждены. Рабочие графы и пользовательские токены
не использовались. Gendocen source не менялся и не перепубликовывался.

## Следующий этап — P1

Сначала прочитать актуальные исходники и проверить отсутствие чужих правок;
сверить хеши с SOURCE-HASHES.json. Установленные принципы из v4.1 сохраняются.
Подготовить минимальный Candidate контракт владельца Temporal Plan:
identitySpace/planId/path, candidate vs accepted future, относительное и
абсолютное время, unknown dates, revision/as-of/provenance, actual event vs
assumption. Не вводить scheduler, preselected или неявное принятие Action.

Постоянное production-хранилище и существенные user-facing design forks
требуют отдельного решения пользователя. Guarded persistence с CAS, revoke,
историей и отдельными plan.create/edit/branch/event-attest правами — P2,
после выравнивания контракта P1. P3…P7 из v4.1 сохраняются.
