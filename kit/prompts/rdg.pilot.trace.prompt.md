# Prompt — RDG Pilot — трассировка цели/решения

[PLANNING_HELPER_LIBRARY_ITEM]
{
  "schemaVersion": 1,
  "kind": "prompt",
  "id": "rdg.pilot.trace",
  "title": "RDG Pilot — трассировка цели/решения",
  "text": "TRACE: объясни происхождение выбранной R или D из фактически сохранённого тестового графа.\n[[module:rdg.pilot.core]]\n[[module:rdg.pilot.storage]]\n[[module:rdg.pilot.response]]\nЧитай graph.json, двигайся по настоящим направленным рёбрам, учитывая parent для INTRODUCES. Назови исходную цель, решения о разбиении, прямые драйверы и существенный контекст. Не приписывай рёбер и историй, которых нет. Не изменяй граф.",
  "createdAt": "2026-10-12T12:25:00.000Z",
  "updatedAt": "2026-10-12T12:25:00.000Z"
}
[/PLANNING_HELPER_LIBRARY_ITEM]
