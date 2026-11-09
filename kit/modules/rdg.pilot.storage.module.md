# Module — RDG Pilot — JSON и Fortis Repo

[PLANNING_HELPER_LIBRARY_ITEM]
{
  "schemaVersion": 1,
  "kind": "module",
  "id": "rdg.pilot.storage",
  "title": "RDG Pilot — JSON и Fortis Repo",
  "text": "Хранилище в тесте: /workspace/repos/rd-graphs/graphs/workspaces/try-it/graph.json. Скрипт проверки/записи: /workspace/repos/rd-graphs/tools/graph-apply.py. README и инструкция: /workspace/repos/rd-graphs/docs/guides/TRY-IT-WORKFLOW.md. Работай только через подключённый Fortis Repo, предварительно проверив фактическое существование файлов и текущую revision. Не предполагай доступ с Windows/через локальный host tunnel. Не создавай новых монтирований, туннелей, snapshots, Git commits/push без запроса.\ngraph.json: schemaVersion=1, revision (целое), nodes[], edges[], events[]. В начале новый тестовый граф содержит R-001 и не содержит принятых D. Viewer только читает граф, сохраняет ChatGPT через Fortis Repo.\nДля сохранения после фактического согласия пользователя: создай отдельный JSON patch в graphs/workspaces/try-it/patches/ с полями {\"schemaVersion\":1,\"expectedRevision\":<текущая ревизия>,\"operations\":[...]}. Допустимые операции: {\"op\":\"add_node\",\"node\":{...}}, {\"op\":\"update_node\",\"id\":\"...\",\"changes\":{...}}, {\"op\":\"add_edge\",\"edge\":{...}}, {\"op\":\"append_event\",\"event\":{...}}. Для нового D нужны kind=\"decision\", status=\"committed\", и append_event с type=\"decision_selected\", decisionId, by=\"user\", note=точная суть явно выбранного пользователем решения, уникальный id. Сначала DRY RUN: python3 /workspace/repos/rd-graphs/tools/graph-apply.py --graph /workspace/repos/rd-graphs/graphs/workspaces/try-it/graph.json --patch <абсолютный_путь_к_patch.json> --dry-run . Затем та же команда без --dry-run; перечитай graph.json, проверь revision, узлы и связи и сообщи результат. Не редактируй graph.json вручную поверх устаревшей ревизии.\nПри конфликте expectedRevision перечитай граф, проанализируй заново, не обходи защиту. При no-op не добавляй события. Не вызывай CLI ради простого анализа: PLAN/TRACE/STATUS/IMPACT обычно только читают файл.\nЕсли Fortis недоступен, честно обозначь BLOCKED, предложи патч, но не утверждай, что изменения записаны.",
  "createdAt": "2026-10-12T12:25:00.000Z",
  "updatedAt": "2026-10-12T12:25:00.000Z"
}
[/PLANNING_HELPER_LIBRARY_ITEM]
