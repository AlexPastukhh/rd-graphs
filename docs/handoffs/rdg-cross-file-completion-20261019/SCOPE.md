# Межфайловое выполнение — Candidate

Поручение: следующий крупный пакет — общая обязательная композиция по точным projectionOf/expansionOf, сохранение владельцев и исполнения Action-instance. Общий resolver для writer/reader; права на каждый источник и автоматическую запись производных результатов во владельцев; единый lock/journal/recovery. Без копирования проектов, нового lifecycle, услуг, mounts/ACL, миграции пользовательских данных или Windows установки.

Проверка: parent → continuation → результат → автоматическая история родителя; неподтверждённые/непринятые ветви; shared/projection identity без двойного исполнения; missing/ambiguous/cyclic/denied owner, смешанные revisions и частичный сбой; прежний однофайловой API/GUI; источники при read/deny не меняются.
