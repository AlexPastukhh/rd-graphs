# Prompt — RDG Pilot — записать выбранное решение

[PLANNING_HELPER_LIBRARY_ITEM]
{
  "schemaVersion": 1,
  "kind": "prompt",
  "id": "rdg.pilot.commit",
  "title": "RDG Pilot — записать выбранное решение",
  "text": "COMMIT: перенеси в тестовый граф только явно выбранное пользователем решение или точно утверждённое изменение.\n[[module:rdg.pilot.core]]\n[[module:rdg.pilot.storage]]\n[[module:rdg.pilot.response]]\nПрочитай актуальную revision и связанные R/D. Проверь, что выбор сделан пользователем в доступном контексте; если нет — не записывай и задай один конкретный вопрос. Подготовь минимальные операции в отдельном patch.json с новыми ID без конфликтов; для принятого D добавь точный decision_selected event. Вызови graph-apply.py с --dry-run, затем применяй, прочитай результат. Не добавляй неподтверждённые требования, автособытия и лишние файлы. После записи дай сжатую дельту и новую revision.",
  "createdAt": "2026-10-12T12:25:00.000Z",
  "updatedAt": "2026-10-12T12:25:00.000Z"
}
[/PLANNING_HELPER_LIBRARY_ITEM]
