# RDG — графы рабочих инструкций и граф на бумаге

> **СТАТУС: HANDOFF / СНИМОК ПРОВЕРКИ НА 2026-10-22, НЕ НОРМАТИВНЫЙ КОНТРАКТ.** Действующие источники: [линзы](../../guides/RDG-LENSES.md), [контракт](../../guides/RDG-ACTIVE-CONTRACT.md), [bootstrap](../../guides/RDG-AGENT-BOOTSTRAP.md).

## Результат

Существующая Graph-модель поддерживает предварительное построение. Зафиксирован термин «граф на бумаге»: можно исследовать цели, способы, разбиения и потенциальные рабочие состояния без выбора, Temporal Plan и исполнения. Сохранение рисунка через writer меняет Graph и его журнал, но не означает применение нарисованного способа. Уже принятые факты не стираются.

Рабочие инструкции сгруппированы в девять обычных R/A-графов orient/clarify/explore/shape/work/review/handoff/operate/develop. Корневая candidate decomposition Action связана с potential R через существующие OUTCOME_OF; подцели имеют свои способы. Альтернативы не подменены последовательностью, selected/history не сфабрикованы. Справочные схемы, точные команды, права и изменяемые факты остаются в документации соответствующих owners.

Добавлен каталог назначений и применимости, companions и instructionCoverage для 15 текущих нормативных источников. Ключи линз читаются из каталога, не из Python whitelist. Команды lenses и lens читают определения без приватного контекста и прав на owners; open привязывает выбранные графы к настоящим Graph/Plan hashes. --lens можно повторять. В ответе сохранены graph.nodes/edges, unresolvedQrpe, unassessedOrStaleCanons и ограничения. Каталог не исполняет автоматический подбор: линзы выбирает AI по задаче либо пользователь явно.

Исправлен дефект rdg-lens-session.cjs: обычный Graph writer уже валидировал OUTCOME_OF, а адаптер линз пропускал эти отношения и отвергал потенциальные дочерние ветви как недостижимые. Теперь потенциальные отношения сохраняются без фиктивного выбора.

## Практическая проверка

Во временном workspace через реальный Graph package writer:
- добавлен candidate decomposition Action под исходной R;
- подготовлена potential R;
- добавлен второй candidate Action под этой потенциальной R и ещё одна потенциальная дочерняя R;
- замысел изменён через edit_title;
- fresh-process open прочитал глубокий focus как potential и incomplete;
- все новые Actions остались candidate, дочерние R — potential, INTRODUCES отсутствовали;
- action_selected/action_executed/requirement_achieved не появились;
- отдельный Plan остался побайтно прежним.

Совместное открытие clarify/explore/shape также не изменило owners. Прежний реальный CSV-сценарий с последующим разрешённым выбором, Plan, исполнением, evidence и продолжением продолжает проходить.

## Проверки

- 5 Python-тестов каталога: чтение без credentials, маршруты к действующим документам, настоящая валидация всех определений, расширение доверенного каталога без whitelist, отказ для незарегистрированных путей/дубликатов/symlinks.
- 14 Python-тестов рабочего клиента, включая бумажную вложенную ветвь и несколько линз.
- 10 Node-тестов generic lens session/research и CLI, включая сохранение потенциальной структуры без selection и отказ malformed childRole.
- 13 Node-тестов документации, актуальных owners и защиты reset.
- Документационный audit PASS до добавления этого отчёта; финальная проверка выполняется после сохранения ссылки на снимок.

Проверены исходники и изолированные сценарии; это не самостоятельная работа второго AI-чата, не пользовательская оценка UI и не формальная приёмка Stage 4.

## Незавершённый перенос

Точные три исходных пользовательских критерия создания блоков в проверенных исходниках не восстановлены. Исторический REVIEW уже отмечал этот пробел. Personal Context недоступен. В shape сохранён открытый Q-THREE-CRITERIA; правило persistence (C1 OR C2) AND C3 не признано заменой. Этот гайд не объявлен завершённым. Для завершения нужны исходные формулировки и их логическая связь.

instructionCoverage проверяет адресные соответствия документов и узлов; наличие строки не доказывает семантическую полноту переноса неизвестных правил. Общий проверенный evaluator канонов и долгоживущие canon assessments остаются отдельными пробелами. RootResult остаётся unknown.

## Сохранность состояния

158 файлов Graph/Plan/Gendocen и кода/реестра экспериментальных модулей сверены по SHA256 с состоянием перед изменением: изменений нет. Учебный reset, выдача реальных grants, публикация владельцев, установка Viewer, изменение модульной подсистемы и Git push не выполнялись. .git в доступной копии отсутствует.

## SHA256 проверенных исходников

- tools/rdg-agent.py: 66142442919bb49b788eab32006ac3e3bbc806c13e2b7ad2c943affda9b4df9c
- tools/rdg-lens-session.cjs: 73120c4d96dcfaab5ae8dcaa63d520a36fbd911424b2db2739059931f18afdab
- tools/rdg-agent-lenses/catalog.json: 4060d45db23f93cbb4d95a8d29a72964fe5143fb919b9610bc0400b98c7856e3
- tests/rdg-agent.test.py: 51a706917477a945d760abf752508364552ed9d8aa93b1a55383b48b39361b79
- tests/rdg-lens-catalog.test.py: fabdfeb86c6ffd9586debda83fb320a992608a69b6f9a62e3db620cadf0e1039
- tests/rdg-general-lens-research.test.cjs: 0424a2625e75053ba4f6716ca9c45442743f1cd9cf193cb499f0b84d6748b0b0
- tools/rdg-agent-lenses/clarify.json: a3c26ea39d3849db9187496f16ab4036472d9d7164bc34705cbc12a28f5e796f
- tools/rdg-agent-lenses/develop.json: abc8b29b042f33a4de14aaa80220debb22fd2a7f753cd2796ecaf6f30563459e
- tools/rdg-agent-lenses/explore.json: 932b16364be430eb17e7094e3cb9535f66640948a838184e776f8439ec8285c3
- tools/rdg-agent-lenses/handoff.json: 8b4a3985b00f884c5febcf45180197493d3eddab2c1a23c1ad45b04662aad533
- tools/rdg-agent-lenses/operate.json: 56e423e69e98ae60380e6e28bb9600b95ac3292e64702b04c2dcccbcca63aa02
- tools/rdg-agent-lenses/orient.json: deb22c204db2d68a9c5646efb6adaab43690443af85591c87745616bb081b6a1
- tools/rdg-agent-lenses/review.json: e757c0c9c57e9cdf2dc0a2b4d2e05033d7faa80792c94dd20d0e912d482cdab4
- tools/rdg-agent-lenses/shape.json: 12e7e6ad6b365217859b6db78ad03466b8860197b798a234ede31f0bde08d3e1
- tools/rdg-agent-lenses/work.json: e766bebc4d8aa88be09dc0634d71b4f9493a35cccd8b0c5faa064eb14bbc035c
