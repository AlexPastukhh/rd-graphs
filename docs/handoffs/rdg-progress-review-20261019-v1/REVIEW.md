# Проверка движения и корректности RDG — R-RDG-PROGRESS-20261019/v1

**Итог:** порядок P0 → P1 → P2 соответствует v4.1. Переход к P2 требует
предварительно закрыть дополнительный пробел P0.1 в проверке полноты источников.
Исходный branch-membership дефект исправлен; полноценный coverage gate ещё
не закрыт. P1 подготовлен как Candidate-документация, а не реализованный lifecycle.
Stage 4 остаётся NOT ACCEPTED.

Это повторная проверка текущих исходников и evidence в том же рабочем контуре,
не независимый production acceptance. Ни одно Finding не записано в рабочий RDG.

## Findings — по приоритету

### F-P-PROGRESS-01 — HIGH — декларация сама задаёт критерий собственной полноты

**Тип:** F-P, подтверждённая текущая проблема guard/доказательной проверки.
**Статус:** OPEN. **Уверенность:** высокая для воспроизведённого scope.
**Основание:** P0 в v4.1 требует intentionally omitted indirect prerequisite
с fail-closed/diagnostic; WR-31/WR-50, EA-18/EA-34.

`tools/rdg-gendocen-dependencies.py`:

- строки 61–69: `complete` определяется числом branches, а не полнотой вычисленных частей контекста;
- строки 78–113: extractor всегда вычисляет identity/branches/steps/sequence/timeConstraints;
- строки 130–135: подписки формируются по ключам `READ_MATRIX`;
- строки 146–154: `assert_coverage` сравнивает переданные подписки с ожидаемыми, которые получены из той же декларации;
- строки 169–171: штатная конфигурация передаёт guard именно только что построенный список.

Текущий отрицательный тест удаляет `/sequence` **после** `build_contract`.
Такой пропуск обнаруживается. Он не проверяет пропуск в самой декларации.

**Новая проверка на реальном Gendocen 0.1.0.dev25:** в памяти producer и во
временной project config намеренно убрана группа `sequence` из READ_MATRIX.
Репозиторный модуль не изменён. Extractor продолжает создавать sequence facet.
На этой неполной декларации создана синтетическая baseline; затем minDelayDays
увеличен на 9 и Plan перепроецирован.

Наблюдение: sequence facet изменился, guardAccepted=true, coverageComplete=true,
checkOk=true, exitCode=0, A1=valid/A2=valid. При штатной полной декларации тот же
тип изменения даёт review_required обеим оценкам.

**Масштаб:** это ошибка реакции на намеренно внесённый пропуск декларации в
доверенном коде/config. В неизменённой штатной READ_MATRIX группа sequence есть;
review не утверждает, что обычная смена sequence сейчас всегда пропускается.
Проблема в заявленном fail-closed coverage contract и полноте его отрицательной
проверки. Это не обход ОС и не модель намеренно враждебного Python-кода.

**Evidence:** `PROBES.json` (missing-source-group и normal-sequence),
`coverage-review.log`; новый обычный acceptance test: 2 tests, 1 PASS/1 FAIL,
process exit 1. Wrapper завершил сбор evidence; его завершение не означает PASS
вложенного acceptance test. Результат вложенного теста — `coverage-review-result.json`.

**Критерий устранения:** требуемые группы подписок проверяются относительно
фактически производимых/читаемых частей контекста, независимо от редактируемой
декларации. Пропуск в producer declaration должен дать явный incomplete coverage
до подтверждения review, а не valid. Старый тест пропуска после build_contract
тоже должен сохраниться. Нужны случаи пустого исходного набора и первого нового
косвенного ограничения. Не заменять это глобальным semanticSHA256.

### F-R-PROGRESS-02 — MEDIUM — смысл события может находиться в исключённом title

**Тип:** F-R, риск границы между presentation и смыслом. **Статус:** OPEN.
**Уверенность:** высокая для наблюдения, средняя для предметного влияния.

`tools/rdg-gendocen-dependencies.py:102–104` исключает `title` у всех Plan steps.
Это осознанная граница P0 и проверяется cosmetic title-edit test. Однако текущая
schema v1 не имеет отдельного текстового определения смысла event/milestone:
человек получает его из title, kind и outcomes. P1 запрещает переиспользовать
step ID для другой по смыслу сущности, но writer, который проверяет это, пока нет.

В отдельном синтетическом probe изменён title события S-RESULT: вместо получения
результата эксперимента — получение разрешения на удаление. Global Plan semantic
hash изменился, адресные review facets не изменились, A1/A2 остались valid.

**Интерпретация:** наблюдаемое исключение title подтверждено. Недопустимость
именно такой правки зависит от ещё не закрытого договора о том, какие поля
определяют смысл события. Поэтому это Risk, а не доказанный дефект ordinary
branch/sequence invalidation. До реального event/Plan lifecycle нельзя считать
любой title-edit безусловно косметическим.

**Критерий закрытия риска:** явно определить presentation и смысл event/milestone.
Минимальный вариант для проверки — консервативно учитывать title там, где он
является единственным описанием смысла. Альтернатива — отдельное стабильное
semantic definition и соответствующий schema/coverage contract. Конкретный
формат остаётся Candidate Proposal; review не меняет schema автоматически.

## Что подтверждено

| Область | Наблюдение review | Вывод |
|---|---|---|
| Целостность | v4.1: 51 записей manifest, P0: 31, P1: 13; все хеши совпали | Исторические пакеты не переписаны |
| Исходный P0 acceptance | Свежий запуск 2/2 PASS | Branch swap вызывает требуемый пересмотр |
| Нынешний dependency suite | Свежий запуск 11/11 PASS | Сохранены заявленные прежние сценарии; новая producer-level omission ими не покрыта |
| Новая review acceptance | 1 PASS + 1 FAIL, exit 1 | Дополнительный coverage gate открыт |
| P1 | CANDIDATE, код/schema не менялись, нового lifecycle нет | Статус описан корректно |
| WR-ledger | В P1 сохранены статусы всех 53 WR; independent acceptance=false | Подготовка документа не выдана за исполнение требований |
| P2 | Не начинался | Исполняемый writer/CAS/grants/history не заявлены выполненными |
| Release | Нет .git, deployment/installed proof/публикации не заявлены | Эти границы не нарушены |

88/88 scoped Python, 405/405 Node и два smoke — историческое evidence P0.
В этом review повторены только acceptance 2 и dependencies 11, добавлен новый
отрицательный review-test и диагностический title probe. Полная Node-регрессия
не повторялась: репозиторный исполняемый код не менялся. Старые PASS не закрывают
новый Finding.

## Оценка движения по плану

| Gate | Фактическое состояние | Следующее действие |
|---|---|---|
| P0 branch reassignment | Исправлено и повторно проверено | Сохранить как regression |
| P0 source completeness | REOPENED по F-P-PROGRESS-01 | P0.1: независимая проверка extractor → declaration → subscriptions |
| P1 owner/version/as-of | Candidate-контракт подготовлен | Уточнить границу title/meaning до расширения lifecycle |
| P2 | PENDING, не готов к безусловному переходу | После P0.1 — synthetic candidate-only guarded writer |
| P3–P7 | Не выполнены этим review | Исходная последовательность v4.1 сохраняется |

Готовность к P2 в прежней передаче была сформулирована слишком широко:
неподдержанные данные и пропуски в producer declaration ещё не все блокируются.
Порядок работы корректируется локально, без нового архитектурного проекта.

## Proposals

| ID | Статус | Предложение | Acceptance |
|---|---|---|---|
| PR-PROGRESS-01 | CANDIDATE | Проверять declaration/subscriptions относительно независимого extractor/read contract; усилить отрицательные тесты | Новый source-group omission блокируется; прежние scoped/branch/cosmetic проверки проходят; после правки нужная регрессия |
| PR-PROGRESS-02 | CANDIDATE | Определить presentation vs semantic event definition и отразить её в coverage | Cosmetic label-edit и semantic event-change дают разные, обоснованные результаты |

Runtime fix, schema migration или принятие этих Proposals здесь не выполнялись.
Технический следующий шаг — PR-PROGRESS-01 / P0.1. Открытые решения о production
root, baseline acceptance rights, trusted Helper/event source и remote owner
остаются открытыми; они не требуют повторного выбора уже установленных принципов.

## Review Limitations и Evidence Gaps

- Проверен указанный RDG owner workspace через Fortis Repo. Windows/G2/installed Helper/Viewer, owner home и clipboard не использовались.
- Все новые runtime probes используют временные синтетические графы, Plan и config. Пользовательские bearer secrets и живые graph.json не используются.
- Это ограниченный source/evidence review, не полный аудит всего writer, Graph API или Gendocen engine и не независимый production acceptance.
- Fault injection меняет декларацию в памяти и в temp config. Она проверяет отказ при ошибке конфигурации, а не доказывает наличие пропуска sequence в обычном текущем конфиге.
- Проверка title устанавливает технический факт исключения поля. Материальное значение конкретного title-edit требует явного semantic contract.
- Реальные historical snapshots/as-of resolver, trusted event attestation, F-P facts и Plan persistence отсутствуют; review их не симулирует как реализованные.
- Нет Git working tree для global diff/commit. Хеши и diff выбранных документов фиксируются отдельно.

Воспроизведение из RDG root:

```bash
RDG_GENDOCEN_SOURCE=/workspace/repos/gendocen PYTHONDONTWRITEBYTECODE=1 \
python3 docs/handoffs/rdg-progress-review-20261019-v1/coverage-review.acceptance.test.py -v
```

Сейчас ожидается exit 1: новый тест producer-level omission FAIL. После P0.1
его критерий должен реально пройти; переименование FAIL в diagnostic success
не является исправлением. `PROBES.json` хранит все три фактических наблюдения.
