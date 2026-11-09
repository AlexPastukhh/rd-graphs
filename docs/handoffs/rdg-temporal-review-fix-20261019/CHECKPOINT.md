# Явное размещение и повторная сверка плана

**ID:** CPW-RDG-TEMPORAL-PLACEMENT-20261019/v1. **Статус:** CANDIDATE,
PASS только для проверенного локального scope. **Stage 4 NOT ACCEPTED.**
Fortis Repo: /workspace/repos/rd-graphs, Windows RW 9p mount. .git отсутствует.

Новая запись Action-шага в будущую часть требует времени или явного порядка.
Пустое будущее допустимо. Структурное чтение старых schema-v1 snapshots и
идемпотентный повтор уже принятого запроса сохраняются. Отказ новой записи
без размещения не создаёт версию/историю и не меняет RDG.

Исправлены также маршрут выполнения без предварительного размещения,
различие создания/достижения подцели и преждевременное утверждение о готовой
общей истории. Описание и полный scope — [повторный review](REVIEW.md).

**155 тестов PASS** в 16 связанных suites, включая 5 новых acceptance cases.
[Результаты](test-results.json). Реальный shared Action Gendocen case —
21 CLI-запуск; control A2 остаётся valid при адресных изменениях A1.
До исправления новые 4 cases: 1 OK, 2 FAIL, 1 ERROR; это доказательство
несоответствия, а не PASS старого поведения.

R-placement, candidate Action descendants, completion/outcome evaluator,
общая читаемая лента и installed Windows proof не закрыты этим срезом.
Исторические P2-AC статусы остаются 8 локальных PASS / 12 PARTIAL / 0 OPEN.
Полные WR и Proposals не повышены автоматически.

[Diff](SELECTED-DIFF.patch) · [Metadata и хеши](CHECKPOINT.json).
Тесты работали только на временных данных; пользовательские графы,
remote/commit/push и публикацию не меняли.
