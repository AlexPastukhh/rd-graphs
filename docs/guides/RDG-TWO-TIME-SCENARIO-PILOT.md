> **СТАТУС: АРХИВ / ИСТОРИЧЕСКАЯ РАЗРАБОТКА — НЕ ДЕЙСТВУЮЩИЙ КОНТРАКТ.** Включая файлы с именами `CONTRACT`, `PLAN`, `STAGE`, `PILOT` и со словом «актуальный» в тексте. Новый чат должен использовать [единую текущую спецификацию](RDG-CURRENT-STATE.md); ниже сохранены прежние эксперименты, решения и протоколы.

# Два времени — read-only проверка правила для candidate-сценария

**Статус: CANDIDATE. Stage 4 NOT ACCEPTED.**
`tools/rdg-two-time-scenario.py` проверяет узкий случай P1-I17/I18:
что поздняя поправка с более ранним `effectiveAt` не становится известной
раньше своего Plan и RDG snapshot. Это **модельное утверждение о применимости**,
переданное в запросе, а не запись owner, принятый baseline или факт события.

Запрос задаёт `knownAt` как instant с часовым поясом, `effectiveAt` как
instant **или** календарную дату, а также список утверждений. Каждое
утверждение содержит `id`, собственное `effectiveAt`, `supersedes` (ID
исправляемого утверждения либо `null`), `eventClaim` (либо `null`) и `source` —
полный exact-reference запрос из [пилота точных снимков](RDG-EXACT-HISTORY-PILOT-P2.md)
без `knownAt`. В `eventClaim` допускается только `verification: "unverified"`;
`eventStepId` и `outcome` должны совпасть с ветвью Plan. Даже один такой claim
не делает outcome фактом и не выбирает Action.

Форма (хеши и остальные поля exact-reference source здесь сокращены):

```json
{
  "schemaVersion": 1,
  "mode": "candidate-two-time-scenario",
  "knownAt": "2026-10-18T11:00:00+00:00",
  "effectiveAt": "2026-10-18T10:45:00+00:00",
  "assertions": [
    {
      "id": "C1", "effectiveAt": "2026-10-18T10:00:00+00:00",
      "supersedes": null,
      "source": {"...": "exact-reference Plan r1 + RDG pins"},
      "eventClaim": {"eventStepId": "S-RESULT", "outcome": "positive",
                     "verification": "unverified"}
    },
    {
      "id": "C2", "effectiveAt": "2026-10-18T10:30:00+00:00",
      "supersedes": "C1",
      "source": {"...": "exact-reference Plan r2 + RDG pins"},
      "eventClaim": {"eventStepId": "S-RESULT", "outcome": "positive",
                     "verification": "unverified"}
    }
  ]
}
```

Многоточие в примере — пояснение, **не исполняемый JSON-запрос**. Для запуска
нужны реальные SHA и `recordDigest` сохранённых версий на временном root.
CLI: `python3 tools/rdg-two-time-scenario.py --plan-root ROOT --graphs-root GRAPHS_ROOT --store AUTH_STORE --request REQUEST_JSON`;
read token передаётся через `RDG_AUTH_TOKEN` и требует `plan.read`/`graph.read`
для всех указанных источников.

Все pins разрешаются и проверяются до временного отбора. План выбирается
только при подтверждённой доступности к `knownAt` и заявленной применимости
к `effectiveAt`; выбранные RDG after-образы дополнительно должны пройти
свой `knownAt` cutoff. Порядок списка assertions не влияет на результат.
Поправка должна указывать прежний ID и более высокую Plan revision. Пока
поддерживается только неубывающее `effectiveAt` в цепочке поправок; более
ранняя ретроактивная граница явно отклоняется как unsupported. Несвязанные
применимые утверждения, включая разные outcomes, дают конфликт, а не выбор
самой поздней revision. Date-only и instant не смешиваются и не переводятся
в полночь. Неизвестная дата отклоняется без подстановки текущего времени.

Результат имеет `status=candidate-scenario`, возвращает выбранный
exact-reference source и причины исключения других утверждений. Поля
`applicabilityAttested`, `eventClaimVerified`, `completeApplicableContextVerified`,
`twoTimeAsOfResolved` и `historicalT1KnowledgeVerified` остаются `false`.
Неизвестны другие применимые owners/события/версии вне переданного набора;
этот пилот не выбирает принятый будущий baseline и не включает историческую
Gendocen subscription. Локальный clock/hash не подтверждает человеческого
автора или истинность данных. Защищённая запись применимости, исправлений и
доверенное event attestation — следующий отдельный gate.

Проверка: `PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-two-time-scenario.test.py -v`.
Тест строит два Plan snapshots и завершённый Graph journal в tempfile;
ранний `knownAt` исключает r2, поздний допускает его как кандидатную
реконструкцию. Проверяются конфликт, точность времени, повреждённая ссылка,
отсутствие Graph time, отзыв read grant и неизменность исходных байтов.
