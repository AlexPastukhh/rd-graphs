# Матрица доказательств P2/P3 после Candidate P1

Статус: PLANNED-NOT-EXECUTED. Это план будущих проверок, не PASS нового lifecycle. Существующие tests дают только частичные основания.

| ID | Правила P1 | Сценарий | Ожидаемое поведение | Этап |
|---|---|---|---|---|
| P2-AC-01 | P1-I02, P1-I03 | Одна identity у двух независимо изменяемых путей | Отклонить конфликт owner; не выбирать самый новый файл и не создавать второго writable owner. | P2 |
| P2-AC-02 | P1-I04 | sourcePath содержит traversal, абсолютный путь или symlink за root | Отклонить без записи и без поиска в других контурах. | P2 |
| P2-AC-03 | P1-I01, P1-I09 | Создать/изменить/разветвить candidate Plan со ссылкой на candidate A1 | Байты RDG, status и T1 неизменны; preselected не появляется. | P2 |
| P2-AC-04 | P1-I03, P1-I09 | Два разных шага в разных cases ссылаются на один RDG Action | Один смысловой владелец Action; membership относится к вхождению; нет копии или автоматического выбора. | P2 |
| P2-AC-05 | P1-I06 | Два writer изменяют одну expectedRevision | Не более одного commit; устаревшая запись отклоняется; смешанной версии нет. | P2 |
| P2-AC-06 | P1-I06, P1-I07 | Plan grant отозван до durable commit | Новая версия/state/history не записаны; bearer secret не раскрыт. | P2 |
| P2-AC-07 | P1-I08, P1-I09 | Edit grant передаёт accepted status или acceptance operation | Отклонить до проверки отдельного права и пути принятия baseline; Action.select не вызывается. | P2 |
| P2-AC-08 | P1-I08, P1-I09, P1-I18 | После принятого будущего baseline создан новый candidate | Прежний принятый baseline доступен по точной ссылке; нет автоматической замены или правки T1. | P2 |
| P2-AC-09 | P1-I13 | Candidate или принятый будущий Plan содержит hard deadline | Новый FR или F-P не создаётся автоматически; provenance/applicability ограничения явны. | P2/P3 |
| P2-AC-10 | P1-I10, P1-I11, P1-I12 | Date-only, instant с offset, неизвестный относительный anchor и окно notBefore/deadline | Не выдумывать дату или instant; несовместимая precision явна; delay остаётся нижней границей; выполнимость не заявляется. | P2 |
| P2-AC-11 | P1-I14, P1-I15 | Автор Plan передаёт observedAt/outcomeObserved, чужой receipt или by=user | Строка не подтверждает реальное событие; требуется отдельное право и проверенный источник. | P2 |
| P2-AC-12 | P1-I15 | Plan editor или event-attest actor пытается вызвать graph.select_action | Отклонить без повышения прав между owners и без частичной записи Plan/RDG. | P2 |
| P2-AC-13 | P1-I16, P1-I17 | Позднее исправление или конфликт outcome для одного event occurrence | Сохранить исходную запись, correction link и recordedAt; незакрытый конфликт вернуть явно. | P2/P3 |
| P2-AC-14 | P1-I05, P1-I18, P1-I19 | Точный исторический Plan/RDG snapshot отсутствует или digest не совпадает | Явный evidence gap и блокировка исторического утверждения; не подставлять current projection. | P2/P3 |
| P2-AC-15 | P1-I17, P1-I18 | r1 recorded 10:00/effective 10:00; r2 recorded 14:00/effective 10:30; запрос known 11:00/effective 10:45 | Исключить r2; не считать её известной на T1=11:00. | P2/P3 |
| P2-AC-16 | P1-I17, P1-I18, P1-I19 | Та же история: known 15:00/effective 10:45, явная ретроспективная реконструкция | r2 допустима только с обозначением позднего знания; исходный T1/selectionBasis неизменен. | P2/P3 |
| P2-AC-17 | P1-I06, P1-I09 | Crash на каждом failpoint Plan persistence; recover выполнен дважды | Согласованно завершить принятую транзакцию или откатить; сохранить прежние baseline/events/T1; повтор идемпотентен. | P2 |
| P2-AC-18 | P1-I20 | Новые owner/lifecycle/event данные переданы старому current-only контракту Gendocen | Явное unsupported coverage или review_required; silent valid недопустим. | P2/P3 |
| P2-AC-19 | P1-I05, P1-I07, P1-I19 | Клиент передал revision/hash и bearer receipt без доверенного snapshot/источника | Не подтверждать историческое знание, личность человека или истинность факта. | P2/P3 |
| P2-AC-20 | P1-I01, P1-I08, P1-I14 | SchemaVersion=1 consumer получает неподдержанные accepted/actual поля | Сохранить candidate-only поведение; отклонить неподдержанные данные до явной версионной интеграции. | P2 |
