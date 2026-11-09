# Следующий шаг после review P0/P1

Читать REVIEW.md и FINDINGS.json. Текущий маршрут: P0.1 → уточнение title/meaning
в Candidate-контракте → P2 synthetic guarded writer → прежняя очередь P3…P7.

P0 original branch acceptance повторно PASS 2/2; dependencies PASS 11/11.
Новый coverage-review.acceptance.test.py: 2 tests, 1 FAIL. Дефект guard касается
намеренного пропуска группы sequence в producer declaration; в штатной
READ_MATRIX sequence присутствует и обычное изменение обнаруживается.
Сохранить это различие при исправлении и отчёте.

P0.1: сверить актуальные пути/права, README/AGENTS и хеши. Не менять живые графы,
реальные токены, mounts/ACL, engine source или Windows installations.
Исправить независимую проверку фактически производимых/читаемых групп против
декларации и подписок. Не выводить expected subscriptions только из декларации,
которая может быть неполной. Добавить случаи missing/unknown/duplicate group,
empty-to-first-constraint и сохранить оба уровня omission-тестов.

После исправления сначала сделать зелёным реальный отрицательный review-test,
затем старый branch/cosmetic acceptance, dependencies, необходимые scoped и
full regression. Зафиксировать реальные хеши и обновить ledger. Не считать
простой diagnostic exit 0 исправлением.

F-R-PROGRESS-02: title исключён из review facets, но у event/milestone может
нести смысл. Уточнить presentation vs semantic fields и покрытие до реального
lifecycle. Не вводить новый формат без явного Candidate Proposal.

Stage 4 NOT ACCEPTED; P1 только Candidate-документация; P2 не начат.
В этом review runtime fix не делался, исходные checkpoints не переписывались.
