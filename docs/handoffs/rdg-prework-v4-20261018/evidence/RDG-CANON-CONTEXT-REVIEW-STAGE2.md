# Stage 2 — проверяемые основания оценки канонов (read-only pilot)

**Статус:** дополнительный локальный эксперимент к [пилоту типизированных Findings](RDG-TYPED-FINDINGS-STAGE2-PILOT.md), **не окончательная истинностная оценка канонов** и не новый writer. Основан на существующем `rdg-context.py`, который сознательно сохраняет `overallVerdict: not-evaluated` и `needs-human-assessment`.

## Цель и границы

Для Action (`candidate-v6`) и legacy Option (`v7`) можно собрать **отдельную осмысленную оценку каждого положительного и каждого отрицательного canon case** в конкретном scope и на конкретную дату. `rdg-canon-context-review.py` перепроверяет, что **заявленные** результаты опираются на сохранённые, точно идентифицированные Context-узлы, но **не решает автоматически**, соответствует ли реальный проект условию текстового канона. И не выбирает Action, не изменяет T1/T2, не создаёт Finding, Proposal, Plan или execution event.

## Вход: самостоятельный файл assessment

```json
{
  "identitySpace": "temporal-demo",
  "graphFile": "workspaces/temporal-fixture/graph.json",
  "targetId": "A1",
  "targetScope": "subsystem-alpha",
  "asOf": "2026-10-18",
  "observedRevision": 1,
  "observedCanonSHA256": "<hash of current canonBlock>",
  "assessments": [
    {
      "caseId": "C-POS",
      "result": "applicable",
      "reason": "Assessor's contextual hypothesis",
      "evidenceRefs": ["graph-node:CTX-POS@<sha256 of exact graph node>"]
    },
    {
      "caseId": "C-NEG",
      "result": "unknown",
      "reason": "No validated source for this scenario",
      "evidenceRefs": []
    }
  ]
}
```

Сценарий выше — **образец формы**, а не действительный файл с вычисленными digest; строковые заглушки нельзя подставлять в настоящий пакет. Функция `sha` в модуле использует канонизацию JSON (sorted keys, compact UTF-8, SHA-256). Для достоверности локальной ссылки необходим настоящий доступный graph source; digest — не доказательство истинности внешнего мира и не подпись пользователя.

- `caseId` должен присутствовать в исходном `canonBlock.recommended[]` либо `canonBlock.contraindicated[]`; нельзя выдумать/дублировать case.
- `result` — **явная оценка участника** (`applicable` / `inapplicable` / `unknown`), **не вычисленная из текста**. Для утверждения не-`unknown` требуется хотя бы одна ссылка `graph-node:ID@SHA`, но даже проверенная ссылка оставляет `semanticApplicabilityProven: false`.
- Локальный `Context` подходит для **проверки существования и актуальности записи** только при `evidenceStatus=checked-present`, непустом `contextValue`, явных `recordedAt` и `effectiveAt` (формат `YYYY-MM-DD`), подходящем `scope`, `validUntil` если установлен, и точном hash. **Requirement — нормативный объект, не наблюдённый факт**, поэтому его наличие не подтверждает канон.
- **T1/T2:** `effectiveAt` (когда обстоятельство объективно действовало) не равно `recordedAt` (когда оно стало известно). Если `recordedAt` позже `asOf`, запись не может подтверждать, что факт был известен на T1 — даже если `effectiveAt` гораздо раньше.
- `observedRevision`, `observedCanonSHA256`, `identitySpace` и `graphFile` привязывают assessment к источнику. Изменившаяся ревизия/canon блокирует поддержку всех результативных claims. Неподходящая дата, scope, SHA, недоступный узел или неопределённый status маркируются без «подтверждено».
- Вывод содержит по каждому случаю `polarity`, `claimResult`, `verification`, `evidence` и глобальный `canonVerdict=needs-semantic-assessment`; список сигналов по плюсовым/минусовым cases сохраняется раздельно. Наличие одного подтверждённого по форме плюса **не перевешивает** актуальное противопоказание.

## Temporal Plan и пример команд

```bash
# Автоматические испытания на синтетическом source graph (без project writes):
PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-canon-context-review.test.py -v

# Для самостоятельного подтверждённо доступного source+assessment:
python3 tools/rdg-canon-context-review.py \
  --graph /tmp/graphs/workspaces/demo/graph.json \
  --assessment /tmp/canon-assessment.json

# Если отдельно есть производный, read-only Stage 3P report:
python3 tools/rdg-canon-context-review.py \
  --graph /tmp/graphs/workspaces/demo/graph.json \
  --assessment /tmp/canon-assessment.json \
  --impact-report /tmp/temporal-impact.json
```

Непосредственно Stage 3P показывает **кандидатную** ветвь/возможный временной конфликт, но **не доказывает положительный или отрицательный канон**. Анализ привязывает совпадения к точным `identitySpace + graphFile + Action.id`, чтобы совпадение ID из другого graph owner не создало ложную связь. Данные отчёта Temporal Plan не подписаны и считаются `candidate-context-only`, даже если там стоит `hard`.

## Что ещё не выполнено

Это *один проверочный слой* Stage 2, не все обещанные функции. Нельзя назвать локально актуальную Context-запись доказательством истинности, права автора оценки или достаточности доказательств. Не реализованы семантическое сопоставление смысла канона и evidence, проверка объективной достоверности/источника, автоматическая F-P, утверждение assessor identity, Gendocen dependency runtime и cross-graph evidence resolver. `recordedAt/effectiveAt` пока только календарные даты; для временных окон и T1 с часами потребуются отдельные точные snapshot/as-of правила, а не выдуманный timestamp. Никакой новый статус `preselected` не вводится.

**Дальнейший gate:** выработать явный контракт полномочного удостоверения контекстных фактов и смысловой оценки; затем связать адресные изменения с реально исполняемым Gendocen, сохраняя immutable T1 и независимость Temporal Plan.
