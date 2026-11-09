# RDG — браузерные проверки

> **СТАТУС: ДЕЙСТВУЮЩАЯ ИНСТРУКЦИЯ ПРОВЕРКИ.** [Функции и тесты](../../docs/guides/RDG-FUNCTIONS-AND-TESTS.md) · [регламент](../../docs/guides/RDG-OPERATIONS.md).

## Обязательный CI

| Сценарий | Что проверяет |
| --- | --- |
| [rdg-decision-desktop.cjs](rdg-decision-desktop.cjs) | Explorer, Graph/Structure, группы, контексты/Canon, черновики, зависимости, инстансы, карточки инвалидации/история, Plan и переходы |
| [rdg-server.cjs](rdg-server.cjs) | Реальный packaged server, Caddy/Host checks, browser login, private gateway, общий writer UI/API, F5/restart и сохранность owners |

Состав запуска и лимиты — в [rdg-ci.py](../../tools/rdg-ci.py). Сценарии создают свои temporary owners; их PNG/JSON остаются в каталоге данного CI run. Нельзя выдавать изолированный процесс за запись, доступную пользователю на работающем сервере.

## Запуск

Подготовленный headless Chromium и зависимости читаются из окружения [rdg-visual-test.sh](../../tools/rdg-visual-test.sh). Скрипт не использует личный Windows-браузер пользователя.

```sh
PYTHONWARNINGS=ignore bash tools/rdg-visual-test.sh tests/visual/rdg-decision-desktop.cjs
```

Изолированный тест упакованного сервера требует актуальный ZIP (`RDG_SERVER_ARCHIVE`), server Python и Caddy. Эти значения выставляет полный CI:

```sh
DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 PYTHONWARNINGS=ignore python3 -B tools/rdg-ci.py
```

После ошибки смотрите `failure.json`, PNG и соответствующий `.log`; после PASS — `result.json`/stdout того же запуска. Число сценариев не фиксируется в документации: оно меняется с тестами.

## Дополнительные сценарии

| Файл | Область; не подменяет основной desktop gate |
| --- | --- |
| [rdg-decision-integration.cjs](rdg-decision-integration.cjs) | Согласованная работа Plan/layout/history |
| [rdg-decision-system.cjs](rdg-decision-system.cjs) | Роли reusable графов, copy, реестр и системные операции |
| [rdg-webauthn.cjs](rdg-webauthn.cjs) | Настоящие браузерные WebAuthn credentials в отдельном тестовом контуре |
| [rdg-approval-viewer.cjs](rdg-approval-viewer.cjs) | Исторический/отдельный approval-путь Viewer; не Fortis Sonar runtime |

Эти файлы запускаются явно при соответствующем изменении. [Старые сценарии и замеры](README-HISTORY.md) описывают прежние версии и не являются текущим статусом.

## Что PASS не доказывает

Пользовательское удобство, точный установленный Windows build, публичный TLS и native Windows durability требуют своих свидетельств. Проверка механики линзы/шаблона не является оценкой качества его предметного содержания. Сетевые/процессные тесты завершают только своих потомков; живой сервис не перезапускается для искусственного сбоя.

T5 Planning Meta Action: `bash tools/rdg-visual-test.sh tests/visual/rdg-planning-meta-actions.cjs` — создание из Plan, местный предмет и линза, переходы/возврат, обычное редактирование, F5, отсутствие Graph/Structure узла и снятие placement с сохранением Action. Использует изолированные owners; входит в полный CI.
