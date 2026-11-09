# Stage 3P — Temporal Plan → RDG: временные сигналы для пересмотра Canon / Findings

**Статус:** ограниченный **read-only / synthetic validation pilot**, НЕ accepted full semantic contract, НЕ typed Finding writer и НЕ production dependency engine. Вход: Candidate Pre-work v3, `S-TEMP`, `SRU-11/12`, `WR-45..53`, пользовательская граница `Action.selected` ≠ запланированное действие. Предпосылка: `Stage 2P`, [модель Temporal Plan](RDG-TEMPORAL-PLAN-STAGE2P.md).

## Для чего

Проверить материальную связь двух **самостоятельных owners**: Temporal Plan содержит порядок, условия и сроки будущих действий/событий; RDG содержит Action, каноны и факты принятых решений. Plan ссылается на Action по точной `{graphFile,identitySpace,nodeId}`. Изменение временного контекста может потребовать переоценки канонов/связанных Findings, но **не является автоматической оценкой истинности канона, принятием Action или доказательством действующей проблемы F-P**.

Исходники графов, события `T1`, `Action.status` и сами `Plan` не меняются. Output — только производные review signals с указанием ветви, исходного временного ограничения и стабильного Action ID.

## Реализованная узкая семантика

- `rdg-temporal-impact.py` читает валидный **candidate** Plan v1, **отдельно рассматривает исходы одного условного события**. Взаимоисключающие будущие шаги других ветвей исключаются из текущего расчёта; сложные комбинации нескольких независимых событий **отклоняются явно**. Без ветви можно рассматривать обычную последовательность.
- Анализирует `sequence`, `minDelayDays` и **строгие `notBefore`** как *нижние границы* возможного момента. Сравнивает эти границы с `deadline` той же точности; дата без времени не превращается в вымышленный timestamp, момент с timezone нормализуется по UTC. Перекрёстное сравнение календарной даты и instant **не создаёт доказанного конфликта**.
- Если даже минимально возможный момент позднее `hard deadline`, выдаёт `candidate-plan-hard-constraint-conflict`: это **внутренняя несогласованность временных предпосылок сценария**, а не F-P текущего проекта. `soft/hypothetical` deadline не может доказывать hard conflict; `no-conflict-proven` означает только «противоречие не доказано», **не** «план выполним».
- Для каждого Action в отдельном case трассирует временных предшественников/последователей и показывает релевантные `timeConstraints`. Проверяет действительный `actionRef` против RDG `identitySpace` и `kind: action`; явно квалифицированная ссылка на другой `identitySpace` допускается при доступном source owner. Проводит **индексацию** `canonBlock.recommended/contraindicated`, не вычисляя их применимость из текста. `canonReview.applicability: not-evaluated`; при отсутствии канонов `unknown-or-not-provided` вместо ложного «каноны пусты».
- `--before-plan` сравнивает два сценария **при одном доступном RDG snapshot**; локальный `dependencyDigest` учитывает релевантные время/путь, Action status и содержимое Canon, но не cosmetic title/revision. Изменение deadline может затронуть Action обеих ветвей; constraint только в ветви A2 **не** помечает A1. Это **validation digest**, не замена Gendocen, не подписанный receipt и не долговечная система зависимостей. Отдельный `revisionChanged` сообщает, что graph revision разошлась с reference.
- У результатов `committedFindings: []`, `selectedActions: []`, `findingType: null`, `findingProposal: null` и `requiresHumanAssessment: true`. При рассмотрении пользователя это могут быть материалы для **F-R, F-U или другого корректного типа**, но классификация требует независимого содержательного подтверждения и действительного scope, а не строкового `hard` кандидатного Plan.

## Запуск

```bash
# Синтетический fixture создаётся самими тестами во временном каталоге:
PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-temporal-impact.test.py -v

# При собственных явных test fixtures (и доступном graph source):
python3 tools/rdg-temporal-impact.py \
  --plan /tmp/temporal-plan-after.json \
  --before-plan /tmp/temporal-plan-before.json \
  --graphs-root /tmp/rdg-synthetic-graphs
```

Не передавайте в `--graphs-root` рабочие источники, если план/токен не предусматривают нужного безопасного чтения. Указание пути само по себе **не предоставляет полномочий**. CLI не создаёт рабочий граф и не пытается записать его. Основной Stage 2P example `docs/examples/temporal-plan-candidate-v1.json` содержит иллюстративные ссылки на несуществующие real RDG Action; поэтому Stage 3P тест генерирует реальные **синтетические** графы только в `tempfile`.

## Фактические проверки

`tests/rdg-temporal-impact.test.py`: отдельная ветвь A1/A2, конфликт при раннем дедлайне, условное ограничение только ветви A2, отсутствие hard proof для `soft/hypothetical`, инвариант неавтоматического Finding, отсутствие timestamp inference, отказ при неподтверждённом graph source, разрешённая explicit cross-identity ссылка, прицельные digest changes и отсутствие изменений исходных файлов. Результаты конкретного прогона указываются при выполнении; наличие теста **не равно успешному запуску**.

## Открытые границы

1. Сценарии **нескольких событий/сложных branch joins**, вероятностные прогнозы, отменённые ветви и реальные `occurred`/attested события не реализованы.
2. Расчёт времени не включает ресурсы, capacity, оценку длительности самих Actions, рабочие календари, различие instant vs local business date, полноту возможных последовательностей и критический путь. Непротиворечивость **не доказывает осуществимость**.
3. **No actual Canon applicability** или typed Finding creation: канон требует проверки конкретной ситуации, источника, evidence и истинности. Здесь индексированы случаи для human review; нельзя назвать F-P подтверждённой проблемой только по гипотезе.
4. Сравнение `--before-plan` перечитывает **текущий** RDG snapshot для обеих версий Plan. Для исторических разниц канонов/Action нужен доверенный старый snapshot, нельзя делать ретроспективные выводы только по этому CLI.
5. Никаких модификаций T1, Graph API acceptance, Gendocen runtime, Persistence, Helper/Viewer, исполнения событий и авторизованной Plan записи. Это следующие отдельные gates, а не скрытые возможности пилота.

**Следующий gate:** согласовать semantic Finding/Canon evaluation и historical source snapshots; затем Stage 4: настоящая интеграция Gendocen с точными Plan↔RDG dependency resources, проверенными правилами и реальным read-only review freshness. Отдельно решить writer/rights для принятого Temporal Plan.
