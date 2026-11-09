# Temporal Plan owner — candidate-only пилот P2

Статус: Candidate, локальная opt-in реализация. **Stage 4 NOT ACCEPTED**.
Исходный контракт: [P1](RDG-TEMPORAL-PLAN-OWNER-CONTRACT-P1.md).
Контрольная точка: [P0.1 + вертикальный срез](../handoffs/rdg-vertical-slice-20261019/CHECKPOINT.md).

## Что работает

`tools/rdg-temporal-plan-owner.py` записывает только candidate Plan v1.
Операции `create/edit/branch` требуют явный существующий root и путь вида
`plans/<имя>/plan.json`. Индекс связывает пару `identitySpace + id` с одним
путём внутри этого root. Смена identity, дублирующий writable owner в том же
root, symlink и выход за root отклоняются. Это локальная граница, не глобальный
реестр владельцев между разными roots и не защита от прямой записи файлов.

Каждая версия содержит полный Plan, серверный `recordedAt`, hash-цепочку,
transaction ID и технический bearer receipt. Проверка `expectedRevision`
предотвращает потерю конкурирующей записи. Совпадающий повтор transaction ID
возвращает прежний результат; другое содержимое с тем же ID отклоняется.
`read --revision N` возвращает точную сохранённую версию или ошибку;
подстановка текущего Plan при отсутствии версии запрещена.

## Права и восстановление

Новый локальный тестовый authority store можно явно инициализировать через
`rdg-authority.py init --plan-capable`. Обычный bootstrap не меняется,
существующие stores не получают новые права. Plan требует точных
`plan.create/edit/branch/read`; `graph.write` и `grant.admin` их не заменяют.
Изменение ветвей, исходов событий или состава возможных шагов требует также
`plan.branch`. Перестановка элементов без смены смысла не требует этого права.
Plan grants не дают `graph.select_action`. Future acceptance и event attestation
не реализованы, даже если соответствующее имя permission есть у bootstrap.

Authority store должен находиться вне Plan root. Финальная проверка grant
и запись удерживают общий grant-lock. Долговечный journal `prepared` — точка
принятия технической транзакции: отзыв до неё запрещает запись, после неё
`recover` завершает уже принятую транзакцию, включая запись индекса.
Незавершённый journal блокирует чтение и проекцию. Recovery сначала проверяет
все цели; неожиданные raw-изменения или повреждённая история блокируют запись.
Повтор завершённого recovery безопасен. Это не принятие будущего плана.

## Связь с Gendocen и проверка поведения

Адаптер принимает versioned store только с явным `--plan-root` и выдаёт
текущий Plan с owner/version provenance. Старый raw Plan остаётся доступен.
`sourcePath` входит в identity зависимости. Номер версии и hash сохраняются
как provenance без глобального принудительного review при локальном изменении.
Контракт `rdg-temporal-review/v2` проверяет пять вычисляемых групп и учитывает
смысловой `title` Action/шага/ожидаемого события. После записи Plan проекцию
нужно обновить; автоматического слежения за произвольными файлами нет.

Сквозной прогон создаёт временные synthetic RDG/Plan и использует реальный
Gendocen 0.1.0.dev25. Проверяются A2-only, общий срок, перестановка ветвей,
конфликт сроков → два черновика F-R, сохранность T1/selectionBasis и версии 1,
запрет выбора Action редактором Plan и сохранение event.state=expected.
Черновики F-R — результат оценки кандидатных предположений. Они не записываются
автоматически и не доказывают реальную проблему F-P.

```bash
python3 tests/rdg-temporal-plan-owner.test.py -v
python3 tests/rdg-gendocen-coverage-guard.test.py -v
python3 tools/rdg-gendocen-t1-history-smoke.py --engine-source /workspace/repos/gendocen --plan-owner
```

CLI writer: `apply --root ROOT --store AUTH_STORE --request REQUEST_JSON`;
чтение: `read --root ROOT --store AUTH_STORE --file plans/NAME/plan.json --revision N`;
восстановление: `recover --root ROOT`. Токен передаётся через `RDG_AUTH_TOKEN`.
Request содержит ровно `transactionId/op/file/expectedRevision/plan`.
Для `create` expectedRevision=0 и Plan.revision=1; при edit/branch нужна следующая
ревизия. Recovery — локальная операция доверенного оператора над принятым journal,
не опубликованный сетевой endpoint и не выдача новых прав.

## Что остаётся открытым

Принятый будущий baseline, trusted human identity, утверждения/attestation/verification
реальных событий, разрешённый production owner и полная семантика Findings/Canons
ещё не реализованы. Точная история одного Plan не даёт полного исторического RDG
или запроса `knownAt + effectiveAt`: provenance явно указывает
`historicalRdgSnapshotResolved=false`. Нужны отдельные версии источников RDG
и resolver, который отклоняет неполный исторический контекст.
Установленные Windows Helper/Viewer и публикация этим пилотом не проверены.
