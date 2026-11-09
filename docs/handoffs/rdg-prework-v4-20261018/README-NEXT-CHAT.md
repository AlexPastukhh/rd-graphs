# Новый чат: как продолжить RDG Pre-work (18.10.2026)

**Начни с `HANDOFF.md`**, затем открой `candidate-prework-v4-execution-reconciled.md`. Исправленный Pre-work v4 содержит полный исходный v3 в приложении; отдельная точная копия v3 находится здесь же. Срез исполнения **CANDIDATE**, ни Stage 4, ни production не приняты.

**Рабочие исходники:** `/workspace/repos/rd-graphs`. **Gendocen:** `/workspace/repos/gendocen` (0.1.0.dev25). Каталоги могут отличаться в новой среде. Технические результаты в `docs/examples/RDG-GENDOCEN-*.json`, тесты в `tools/rdg-gendocen-*.py`.

**Первый следующий шаг — P0**: исправить обнаруженный и воспроизведённый дефект полноты подписок. Когда условные исходы Temporal Plan обмениваются шагами Actions A1/A2, текущий Gendocen оставляет оба review `valid`! Не пропускать этот контрпример и не считать исправлением одни успешные crash/receipt tests.

Команда воспроизведения, из RDG root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 docs/handoffs/rdg-prework-v4-20261018/repro-branch-membership-gap.py --engine-source /workspace/repos/gendocen
```

**Важно:** `exit 0` у этого специального скрипта означает **BUG REPRODUCED**. После исправления нужны новые fail-first/acceptance тесты: изменение branch membership должно требовать пересмотра затронутых оценок; косметическая перестановка не должна вызывать ложное устаревание.

**Запреты:** не трогать рабочие `graphs/workspaces/*/graph.json`, пользовательские токены и установленный Helper/Viewer, не отправлять изменения на GitHub, не принимать решения/события от имени пользователя. Plan — независимая сущность во времени; Action.selected только отдельным авторизованным решением; planned ≠ performed; Gendocen receipts ≠ factual evidence. RDG owner mount без `.git`.

**Готовый промпт следующему чату:**

> Прочитай файлы HANDOFF.md и candidate-prework-v4-execution-reconciled.md из переданного архива и сверь живые исходники RDG/Gendocen. У нас Candidate Pre-work v4, полный исходный v3 в приложении. Продолжай с P0: воспроизведи дефект Gendocen на изменении принадлежности Action к условному исходу Temporal Plan, затем исправь dependency coverage с адресными подписками и отрицательными тестами. Сохраняй ограничения owner/Authority/T1/Plan и не меняй пользовательские графы. После исправления проведи targeted и полную регрессию, обнови ledger фактически выполненного. Не считай прошлые 405 PASS достаточным доказательством полноты семантики.
