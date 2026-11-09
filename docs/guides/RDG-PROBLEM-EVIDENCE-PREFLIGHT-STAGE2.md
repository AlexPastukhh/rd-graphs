> **СТАТУС: АРХИВ / ИСТОРИЧЕСКАЯ РАЗРАБОТКА — НЕ ДЕЙСТВУЮЩИЙ КОНТРАКТ.** Включая файлы с именами `CONTRACT`, `PLAN`, `STAGE`, `PILOT` и со словом «актуальный» в тексте. Новый чат должен использовать [единую текущую спецификацию](RDG-CURRENT-STATE.md); ниже сохранены прежние эксперименты, решения и протоколы.

# Stage 2 evidence gate — preflight для подтверждённого F-P (read-only)

**Статус:** проверка готовности фактических источников к независимому подтверждению, **не реализация удостоверения F-P** и **не** trusted Helper/identity provider. Происхождение: Candidate Pre-work v3, N-01/FR-06/FR-07/FR-15 и Stage 2. Код: `tools/rdg-problem-evidence-preflight.py`; тесты: `tests/rdg-problem-evidence-preflight.test.py`.

## Зачем отдельный этап

F-P означает *подтверждённую текущую проблему*. Подстановка поля `confirmed:true`, запись `by:user`, наличие hash, `evidenceStatus=checked-present` или выданный чату bearer **не доказывают объективный факт**. Отдельный Actor с полномочием может в будущем удостоверять подтверждение по договорённому trusted workflow, но этот workflow ещё не реализован. Никакая проверка в этом инструменте не выводит `mayAppendFP:true`.

Уже реализованный writer `append_finding` продолжает **отказывать при F-P**. Preflight никогда его не вызывает и не меняет `graph.json`.

## Проверяемый пакет

Для чтения передаётся JSON с **точно этими полями**: `graphFile`, `identitySpace`, `observedRevision`, `targetId`, `findingId`, `statement`, `targetScope`, `asOf`, `evidenceRefs[]`, `reviewQuestions[]`.

`graphFile` — путь `workspaces/.../graph.json`, `identitySpace` — идентичность RDG; `targetId` — требование, Action, Option или Decision. Источники — точные `graph-node:<id>@<sha256>`, как в local evidence tooling. Хеш считается по каноническому JSON узла, не по файловым байтам. `reviewQuestions` не может быть пустым.

Preflight проверяет наличие ссылки, hash, `kind:context`, `contextValue`, `evidenceStatus=checked-present`, scope, `effectiveAt/validUntil`, **`recordedAt` не позже `asOf`** и совпадение ревизии графа. `asOf` должен быть сегодняшним днём **по UTC** для CURRENT preflight; при оценке на историческую дату применяется отдельный T1/T2 review, а не утверждение «проблема сейчас».

Если все локальные проверки успешны, возвращается `localEvidenceReadyForReview:true`; но `confirmedProblem:false`, `mayAppendFP:false`, `trustProofValidated:false`, `humanIdentityVerified:false` **всегда**. `missingGates[]` всегда содержит `trusted-independent-factual-attestation-not-implemented`. Даже созданный пользователем Context с `checked-present` здесь считается только **сохранённым заявлением о наблюдении**, а не самостоятельным независимым доказательством. Эвристики Temporal Plan, срок `hard` в кандидатном Plan и будущие события не проходят как current fact.

## Запуск

```bash
# Проверка на синтетических источниках в tempfile:
PYTHONDONTWRITEBYTECODE=1 python3 tests/rdg-problem-evidence-preflight.test.py -v

# Для явно предоставленных, доступных только на чтение graph/request:
python3 tools/rdg-problem-evidence-preflight.py \
  --graph /tmp/graphs/workspaces/pilot/graph.json \
  --request /tmp/fp-evidence-request.json
```

**Следующий gate:** определить доверенного реального подтверждающего субъекта/источник и способ проверки доказательств (например, Helper user identity и фиксированное разрешение на `F-P`), границу commit, append-only evidence receipt и отделение verifier от подготовившего материалы. Только после этого можно обсуждать разрешение F-P через Graph API. **Не выдавать существующий bearer receipt за доказанную личность или истину.**
