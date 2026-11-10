#!/usr/bin/env python3
"""Create a coherent read-only, multi-level R–D demonstration.

All SH-* nodes, choices and events are HYPOTHETICAL: not sourced facts,
not user-authorized decisions, not writer-compatible projects.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "graphs" / "examples"
PREFIX = "reference-complete-"
SPACE = "showcase:booking-example-v1"
SOURCE = "docs/examples/COMPLETE-REFERENCE-GUIDE.md"
TM_FEATURE = ("obs-planning-docs/planning/documentation/idtspe-methodology/"
              "active/profiles/sds/target-modules/TM-FEATURE.md")
TM_SCENARIO = ("obs-planning-docs/planning/documentation/idtspe-methodology/"
               "active/profiles/sds/target-modules/TM-SCENARIO-PLANNING.md")

def N(id, kind, title, **properties):
    return {"id": "SH-" + id, "kind": kind, "title": title, **properties}

def E(id, type, src, dst, meaning, **properties):
    return {"id": "SH-E-" + id, "type": type, "from": "SH-" + src,
            "to": "SH-" + dst, "meaning": meaning, **properties}

def G(slug, title, root, nodes, edges, *, entry=False, events=None, description=""):
    assert nodes[0]["id"] == "SH-" + root and nodes[0]["kind"] == "requirement"
    return dict(schemaVersion=1,id=PREFIX+slug,revision=1,title=title,
                identitySpace=SPACE,rootRequirementId="SH-"+root,
                readOnly=True,exampleOnly=True,hypothetical=True,
                selectedInProject=False,catalogHidden=not entry,
                canonicality="ILLUSTRATION_ONLY",
                demonstrationGroup="complete-booking-showcase",
                origin="New complete hypothetical illustration, NOT original EX-* and NOT a real project.",
                sourceDocument=SOURCE,
                coverage=description,
                nodes=nodes,edges=edges,events=events or [])

def selected(scope, description, **kwargs):
    return dict(status="selected-in-example-only",selectedInExample=True,
                selectedInProject=False,scope=scope,description=description,**kwargs)

def available(description, **kwargs):
    return dict(status="reusable-unselected",selected=False,
                templateOnly=True,description=description,**kwargs)

def hypothetical_event(id, type, decision, note):
    return {"id":"SH-EVENT-"+id,"type":type,"decisionId":"SH-"+decision,
            "by":"example-only","note":note,"exampleOnly":True}

graphs = []
graphs.append(G("app","R · Спланировать приложение бронирования","R-APP",[
 N("R-APP","requirement","Спланировать приложение бронирования",description="Условная цель. Само слово «Features» здесь не навязывает метод планирования."),
 N("C-TEAM","context","Команда ограничена по ресурсам",description="Условный контекст, не нормативное R."),
 N("D-APP-SPLIT","decision","Выделить функционал, сценарии и реализационные требования",
   **selected("Планирование условного приложения","Конкретное примерное D вводит РОВНО три R. Готовые решения по дальнейшим уровням здесь не выбраны.",concreteBranchCount=3)),
 N("R-FUNC","requirement","Расписать функционал",description="Нейтральный дочерний R; только на ЕГО уровне решается «через Features» или другим способом."),
 N("R-SCENARIOS","requirement","Описать сценарии",description="Отдельный уровень Scenarios; не копия R-FUNC."),
 N("R-REALIZATION","requirement","Определить реализационные ограничения",description="Найти актуальные ограничения, а не придумать дочерние задачи."),
],[
 E("APP-01","DRIVES","R-APP","D-APP-SPLIT","Требование требует ответа о плане."),
 E("APP-02","CONTEXT_FOR","C-TEAM","D-APP-SPLIT","Ограниченные ресурсы учитываются при выборе границ."),
 E("APP-03","INTRODUCES","D-APP-SPLIT","R-FUNC","Первый из трёх точных дочерних R.",parent="SH-R-APP"),
 E("APP-04","INTRODUCES","D-APP-SPLIT","R-SCENARIOS","Второй дочерний R.",parent="SH-R-APP"),
 E("APP-05","INTRODUCES","D-APP-SPLIT","R-REALIZATION","Третий дочерний R.",parent="SH-R-APP"),
],entry=True,events=[
 hypothetical_event("APP-SELECT","decision_selected","D-APP-SPLIT","В вымышленной истории выбран состав из трёх R. НЕ событие пользователя."),
],description="Входной граф; нейтральные дочерние Requirements вводятся D, а отдельные их уровни определяются через identitySpace/rootRequirementId."))
graphs.append(G("functionality","R · Расписать функционал","R-FUNC",[
 N("R-FUNC","requirement","Расписать функционал",description="Тот же SH-R-FUNC, что ввело D-APP-SPLIT в предыдущем файле."),
 N("V-BY-FEATURES","variant","Готовое разбиение по Features · 1..N",
   **available("Повторяемое правило: для каждого элемента будущей коллекции Features создать R и проработать через один и тот же TM-FEATURE. НЕ фактические 2 ветви.",
     repetition={"mode":"PER_ITEM","cardinality":"1..N","collectionRole":"Features",
                 "itemRequirementPattern":"Расписать Feature {item}","preparedModelId":"TM-FEATURE",
                 "oneApplicationPerItem":True})),
 N("V-BY-SCENARIOS","variant","Готовый альтернативный способ: по сценариям",
   **available("Иной возможный способ описания функционала, не выбранный. Альтернативность обсуждаемая, не доказанная эквивалентность.")),
 N("R-FEATURE-ROLE","requirement","Шаблон будущего R для одной Feature",
   status="template-placeholder",templateOnly=True,description="Это роль, НЕ третий конкретный R и НЕ принятая Feature."),
 N("V-TM-FEATURE","variant","Одна готовая модель TM-FEATURE",
   **available("Одна reusable Target Module Model из SDS. Проекция здесь не копирует её исходные Units.",
               preparedModelId="TM-FEATURE",source=TM_FEATURE)),
 N("C-SCOPE","context","Для условной первой версии нужны две области",
   description="Условное основание выбора двух Features, не свойство любого приложения."),
 N("D-CHOOSE-FEATURES","decision","В примере выбрано 2 Features",
   **selected("SH-R-FUNC; условная первая версия",
              "Одно условное D использует готовое правило 1..N и вводит РОВНО два R: Availability и Reservation. Одна TM-FEATURE Model применяется два раза. Никаких реальных решений пользователя.",
              usesPreparedDecompositionRef="SH-V-BY-FEATURES",concreteBranchCount=2,
              modelApplicationCount=2,preparedModelRef="TM-FEATURE")),
 N("R-FEAT-AVAIL","requirement","Проработать Feature Availability",description="Первая из ровно двух конкретных дочерних R. Следующий граф начинается с того же ID."),
 N("R-FEAT-RES","requirement","Проработать Feature Reservation",description="Вторая конкретная дочерняя R, не клон модели."),
 N("APP-AVAIL","application","Применение TM-FEATURE к Availability",
   status="example-application",targetRequirementId="SH-R-FEAT-AVAIL",
   preparedModelRef="TM-FEATURE",governingDecisionRef="SH-D-CHOOSE-FEATURES",
   description="Демонстрационное отдельное применение модели; kind=application не поддерживается текущим writer."),
 N("APP-RES","application","Применение TM-FEATURE к Reservation",
   status="example-application",targetRequirementId="SH-R-FEAT-RES",
   preparedModelRef="TM-FEATURE",governingDecisionRef="SH-D-CHOOSE-FEATURES",
   description="Второе применение той же модели, без повторного общего D."),
 N("Q-FEATURE-COVERAGE","question","Покрывают ли две Features потребности сценариев?",
   status="open",description="QRPE достаточности. Наличие вопроса не отменяет автоматически выбранное D."),
],[
 E("FUN-01","OPTION_FOR","R-FUNC","V-BY-FEATURES","Готовый альтернативный способ для R, ещё не принято."),
 E("FUN-02","OPTION_FOR","R-FUNC","V-BY-SCENARIOS","Другая готовая схема; не выбранная."),
 E("FUN-03","GENERATES_ITEM_ROLE","V-BY-FEATURES","R-FEATURE-ROLE","Роль одного повторяемого R, а не фактическая ветвь."),
 E("FUN-04","PER_ITEM_MODEL","V-BY-FEATURES","V-TM-FEATURE","Для каждого элемента используется ОДНА готовая TM-FEATURE Model."),
 E("FUN-05","DRIVES","R-FUNC","D-CHOOSE-FEATURES","R требует конкретного выбора способа."),
 E("FUN-06","CONTEXT_FOR","C-SCOPE","D-CHOOSE-FEATURES","Ограничение первой версии учитывается в конкретном выборе."),
 E("FUN-07","USES_PREPARED","D-CHOOSE-FEATURES","V-BY-FEATURES","Выбранное условное D ссылается на готовую схему 1..N."),
 E("FUN-08","INTRODUCES","D-CHOOSE-FEATURES","R-FEAT-AVAIL","Первая конкретная Feature: Availability.",parent="SH-R-FUNC"),
 E("FUN-09","INTRODUCES","D-CHOOSE-FEATURES","R-FEAT-RES","Вторая конкретная Feature: Reservation.",parent="SH-R-FUNC"),
 E("FUN-10","INSTANCE_OF_MODEL","V-TM-FEATURE","APP-AVAIL","Одна модель, применение 1 из 2."),
 E("FUN-11","INSTANCE_OF_MODEL","V-TM-FEATURE","APP-RES","Одна модель, применение 2 из 2."),
 E("FUN-12","GOVERNED_BY_SHARED_CHOICE","D-CHOOSE-FEATURES","APP-AVAIL","Одно общее D управляет первым применением."),
 E("FUN-13","GOVERNED_BY_SHARED_CHOICE","D-CHOOSE-FEATURES","APP-RES","То же общее D управляет вторым применением."),
 E("FUN-14","QRPE_FOR","Q-FEATURE-COVERAGE","D-CHOOSE-FEATURES","Нужно проверить полноту покрытия условных сценариев, не пересматривать автоматически."),
],description="Готовое разбиение 1..N против точных двух дочерних R, альтернативы, единая модель TM-FEATURE, два её применения, общий scope и открытый вопрос."))

graphs.append(G("scenarios","R · Описать сценарии","R-SCENARIOS",[
 N("R-SCENARIOS","requirement","Описать сценарии",description="Корневой R, введённый на уровне приложения без смены ID."),
 N("D-SCENARIO-SET","decision","Для примера определить создание и отмену",
   **selected("Первая условная версия сценариев","Два конкретных R описания отдельных сценариев, ещё не результаты их выполнения.",concreteBranchCount=2)),
 N("R-SCREATE","requirement","Описать сценарий создания бронирования",
   description="Дочернее R делегируется в отдельный уровень того же ID; там возможен Scenario Target Module."),
 N("R-SCANCEL","requirement","Описать сценарий отмены бронирования",
   description="Второй конкретный R; отдельный детальный уровень в этом showcase не создан, связь не выдумана."),
],[
 E("SC-01","DRIVES","R-SCENARIOS","D-SCENARIO-SET","Состав сценариев отвечает требованию."),
 E("SC-02","INTRODUCES","D-SCENARIO-SET","R-SCREATE","Первый определённый сценарий, не placeholder.",parent="SH-R-SCENARIOS"),
 E("SC-03","INTRODUCES","D-SCENARIO-SET","R-SCANCEL","Второй определённый сценарий.",parent="SH-R-SCENARIOS"),
],description="Два конкретных сценария, но только для первого существует собственный граф."))
graphs.append(G("realization","R · Определить реализационные ограничения","R-REALIZATION",[
 N("R-REALIZATION","requirement","Определить реализационные ограничения",
   description="Выявить действующие требования из условного контекста; не произвольно создать ветви работ."),
 N("C-INDEPENDENT","context","Команда условно требует независимых слайсов",
   description="Не превращать сведения об организации работы в отдельное R без реального обоснования."),
 N("D-FIND-RR","decision","Выявлены ограничения независимости и изменений",
   **selected("Условная команда","Иллюстративное обнаружение требований, не разбиение по дочерним задачам.")),
 N("R-INDEPENDENT","requirement","Обеспечить независимые изменения Features",
   crosscutting=True,status="example-crosscutting",
   description="ОДИН сквозной R; применяется к двум существующим Features, не создаёт копии."),
 N("R-BOUNDARY","requirement","Уточнить границы ответственности",
   status="derived-clarification",description="Содержательное уточнение исходного R через DERIVES, не INTRODUCES."),
 N("R-FEAT-AVAIL","requirement","Проработать Feature Availability",
   referenceOnly=True,description="Ссылка на тот же R-ID из functionality/availability, а не новое R."),
 N("R-FEAT-RES","requirement","Проработать Feature Reservation",
   referenceOnly=True,description="Ссылка на тот же R-ID из functionality/reservation, а не новое R."),
 N("Q-NEED-INDEPENDENCE","question","Нужна ли именно независимая разработка?",
   status="open",description="QRPE необходимости R. Может привести к уточнению при проверке, не отменяет R автоматически."),
],[
 E("RR-01","DRIVES","R-REALIZATION","D-FIND-RR","Найти действующие для проекта ограничения."),
 E("RR-02","CONTEXT_FOR","C-INDEPENDENT","D-FIND-RR","Основание поиска, не автоматически нормативное R."),
 E("RR-03","IDENTIFIES","D-FIND-RR","R-INDEPENDENT","Выявлен сквозной R; НЕ введён дочерний R планирования."),
 E("RR-04","DERIVES","R-INDEPENDENT","R-BOUNDARY","Содержательное уточнение R, без создания задачи через D."),
 E("RR-05","APPLIES_TO","R-INDEPENDENT","R-FEAT-AVAIL","Один сквозной R прямо применяется к Availability."),
 E("RR-06","APPLIES_TO","R-INDEPENDENT","R-FEAT-RES","Тот же R прямо применяется к Reservation, без копирования."),
 E("RR-07","QRPE_FOR","Q-NEED-INDEPENDENCE","R-INDEPENDENT","Проверка необходимости именно этого нормативного R."),
],description="Происхождение R через IDENTIFIES, содержательное DERIVES, две прямые области APPLIES_TO от одного crosscutting R, проверка необходимости."))
graphs.append(G("availability","R · Проработать Feature Availability","R-FEAT-AVAIL",[
 N("R-FEAT-AVAIL","requirement","Проработать Feature Availability",
   description="Тот же R, который фактически введён на уровне функционала; декомпозиция на Units здесь не требуется."),
 N("D-AVAIL-OLD","decision","Прежний примерный ответ: только просмотр интервалов",
   status="superseded-in-example-only",scope="Только условная Availability",
   description="Устаревшее D в придуманной истории. Не переписывать прошлое и не выдавать за действующий выбор."),
 N("C-REFRESH","context","Появилась необходимость обновлять доступность",
   description="Иллюстративное изменение контекста, не автоматически принятая ревизия."),
 N("D-AVAIL-NEW","decision","Новый примерный ответ: обновление и явная неизвестность",
   **selected("Только условная Availability","Конкретный ответ напрямую на R без дочерних R. Событие пересмотра отдельно, не связано с Proposal.")),
 ],
 [
 E("AV-01","DRIVES","R-FEAT-AVAIL","D-AVAIL-OLD","Прежний ответ на тот же R; сейчас superseded в условной истории."),
 E("AV-02","DRIVES","R-FEAT-AVAIL","D-AVAIL-NEW","Новый ответ на тот же R. Для прямого ответа под-R не обязателен."),
 E("AV-03","CONTEXT_FOR","C-REFRESH","D-AVAIL-NEW","Новый контекст учтён при изменении ответа."),
 ],events=[
 hypothetical_event("AV-SELECT-OLD","decision_selected","D-AVAIL-OLD","Событие выбора в условной истории, не запись пользователя."),
 hypothetical_event("AV-REVISED","decision_revised","D-AVAIL-NEW","Условно принято новое D вместо старого; это не равнозначно одному RECONSIDERS."),
 ],description="ПРЯМОЙ D без под-R, пример изолированной истории реального изменения D и superseded состояния: события только учебные, формат их by не допускает запись writer."))
graphs.append(G("reservation","R · Проработать Feature Reservation","R-FEAT-RES",[
 N("R-FEAT-RES","requirement","Проработать Feature Reservation",
   description="Тот же R из функционального разбиения. У этого R возможен прямой выбор и локальные под-R."),
 N("V-BEHAVIOR-PATH","variant","Готовый Behavior Path",
   **available("Переиспользуемое описание поведения по действиям/реакциям/ошибкам, не committed D.")),
 N("V-STATES","variant","Готовые State Transitions",
   **available("Альтернативный готовый вариант со состояниями и переходами.")),
 N("C-INTERACTION","context","В исходном контексте удобна последовательность шагов",
   description="Исходное условное основание."),
 N("D-BEHAVIOR","decision","Выбрать Behavior Path для Reservation",
   **selected("Behavior Feature Reservation условного приложения","Выбрано только в примере; D ссылается на готовый вариант, не копируя его. Достаточность решения не равна реализации.")),
 N("R-ERRORS","requirement","Описать ошибки и потерю ответа",
   description="Локальная часть выбранного разбиения Behavior Path; здесь показана как один конкретный дочерний R."),
 N("C-STATE-NEW","context","Появились внешние события, зависящие от состояния",
   description="Новый условный контекст; не событие пересмотра D."),
 N("Q-BEHAVIOR","question","Достаточен ли Behavior Path при новых событиях?",
   status="open",description="QRPE обоснованности действующего D."),
 N("PR-STATE","proposal","Предложение: пересмотреть выбор в пользу State Transitions",
   status="pending",description="Не выбранный кандидат, не новое committed D."),
],[
 E("RS-01","OPTION_FOR","R-FEAT-RES","V-BEHAVIOR-PATH","Готовый вариант для этого R до конкретного выбора."),
 E("RS-02","OPTION_FOR","R-FEAT-RES","V-STATES","Другой готовый вариант, остаётся доступным."),
 E("RS-03","DRIVES","R-FEAT-RES","D-BEHAVIOR","R драйвер конкретного ответа в выбранном scope."),
 E("RS-04","CONTEXT_FOR","C-INTERACTION","D-BEHAVIOR","Почему Behavior Path был удобен."),
 E("RS-05","USES_VARIANT","D-BEHAVIOR","V-BEHAVIOR-PATH","Конкретное D выбирает переиспользуемую заготовку."),
 E("RS-06","INTRODUCES","D-BEHAVIOR","R-ERRORS","Принятое только в примере D ввело локальную подзадачу.",parent="SH-R-FEAT-RES"),
 E("RS-07","CONTEXT_FOR","C-STATE-NEW","D-BEHAVIOR","Новый контекст для оценки действующего выбора; сам его не отменяет."),
 E("RS-08","QRPE_FOR","Q-BEHAVIOR","D-BEHAVIOR","Открытый вопрос обоснованности D."),
 E("RS-09","RECONSIDERS","PR-STATE","D-BEHAVIOR","Предлагает пересмотр; пока решение НЕ пересмотрено."),
 E("RS-10","USES_VARIANT","PR-STATE","V-STATES","Кандидат предлагает другую готовую модель, не выбрана."),
],events=[
 hypothetical_event("RS-SELECT","decision_selected","D-BEHAVIOR","В условной истории принят Behavior Path."),
 {"id":"SH-EVENT-RS-NEW-CONTEXT","type":"context_changed","by":"example-only",
  "note":"Появился условный контекст; прежнее D ещё не изменено.","exampleOnly":True},
 {"id":"SH-EVENT-RS-PROPOSAL","type":"proposal_considered","by":"example-only",
  "note":"Предложение на рассмотрении; не decision_revised.","exampleOnly":True},
],description="Готовые варианты vs выбранное D, локальное INTRODUCES, QRPE и невыбранный RECONSIDERS. События меняют хронологию, но не делают pending Proposal принятой."))
graphs.append(G("scenario-create","R · Описать сценарий создания бронирования","R-SCREATE",[
 N("R-SCREATE","requirement","Описать сценарий создания бронирования",
   description="Тот же SH-R-SCREATE с предыдущего уровня; готовый Target Module не подменяет R."),
 N("V-TM-SCENARIO","variant","Готовая модель Scenario Target Module",
   **available("Ссылка на реальную SDS-модель TM-SCENARIO-PLANNING для одного coherent real-life Scenario. Модель не является другим R и здесь не копируется.",
               preparedModelRef="TM-SCENARIO-PLANNING",source=TM_SCENARIO)),
 N("D-DESCRIBE","decision","Условное описание создания бронирования",
   **selected("Scenario создания бронирования","В описании показаны подтверждение, занятый слот и неопределённый результат при потере ответа; это не доказательство работающей реализации.")),
 N("R-RESULT","requirement","Пользователь должен узнать итог подтверждения без дублирования",
   description="Выявленная функциональная потребность, НЕ дочернее R на написание описания Scenario."),
 N("R-FEEDBACK","requirement","Уточнить обратную связь при неопределённом результате",
   description="Содержательное уточнение R-RESULT через DERIVES, не INTRODUCES."),
 N("C-STATUS","context","В условной системе есть средство проверки статуса",
   description="Доступное средство может оказаться недостаточным — нужен QRPE."),
 N("D-STATUS","decision","Условный локальный ответ: проверить статус и показать итог",
   **selected("Подтверждение бронирования и обратная связь","ОДНО D отвечает сразу двум R с общим предметом, использует содержание описанного сценария. Достаточность остаётся под вопросом.")),
 N("Q-STATUS","question","Может ли статус достоверно установить результат?",
   status="open",description="QRPE достаточности, не событие принятия и не доказанный дефект."),
],[
 E("CR-01","OPTION_FOR","R-SCREATE","V-TM-SCENARIO","Готовая модель доступна для конкретного сценария."),
 E("CR-02","DRIVES","R-SCREATE","D-DESCRIBE","Тот же R остаётся драйвером после условной делегации."),
 E("CR-03","USES_VARIANT","D-DESCRIBE","V-TM-SCENARIO","D отвечает в рамках готовой модели, модель не второе R."),
 E("CR-04","REVEALS_NEED","D-DESCRIBE","R-RESULT","При раскрытии Scenario обнаружена отдельная функциональная потребность."),
 E("CR-05","DERIVES","R-RESULT","R-FEEDBACK","Содержательно уточнено требование, не декомпозиция описания."),
 E("CR-06","DRIVES","R-RESULT","D-STATUS","Первый R-драйвер общего локального ответа."),
 E("CR-07","DRIVES","R-FEEDBACK","D-STATUS","Второй R-драйвер того же D, без дублирования."),
 E("CR-08","INFORMS","D-DESCRIBE","D-STATUS","Используется только содержание о потере ответа и подтверждении; НЕ весь сценарий."),
 E("CR-09","CONTEXT_FOR","C-STATUS","D-STATUS","Имеющееся средство учитывается при выборе, не гарантирует достаточность."),
 E("CR-10","QRPE_FOR","Q-STATUS","D-STATUS","Проверить достаточность D-STATUS для точного результата."),
],description="Scenario TM применим, R сохраняет identity; INFORMS часть D, REVEALS_NEED обнаруживает функциональный R, DERIVES уточняет R, одно локальное D отвечает двум R; QRPE достаточности.")
);


# Complete the semantic paths of the same hypothetical composition. These
# are author edits of a teaching fixture, not real project decisions.
from copy import deepcopy
suite = {g["id"][len(PREFIX):]: g for g in graphs}
def node(part, ident):
    return next(n for n in suite[part]["nodes"] if n["id"] == "SH-" + ident)
def add_node(part, record):
    assert not any(n["id"] == record["id"] for n in suite[part]["nodes"])
    suite[part]["nodes"].append(record)
def reference(part, owner, ident):
    original = node(owner, ident)
    record = {key:deepcopy(original[key]) for key in (
        "id","kind","title","status","scope","crosscutting","templateOnly",
        "selectedInExample","selectedInProject","evidenceStatus","delegations","targetModule"
    ) if key in original}
    record.update(referenceOnly=True,
                  projectionOf={"graphSlug":suite[owner]["id"],"nodeId":original["id"]},
                  description="Ссылка на ту же смысловую запись. Полный ответ и основания находятся в указанном источнике.")
    return record
def add_reference(part, owner, ident):
    add_node(part, reference(part,owner,ident))

# Concrete Scenario answers are the sources of Feature boundaries.
node("scenario-create","D-DESCRIBE").update(
    targetModule="SH-TM-SCREATE · Scenario S-CREATE",
    description="Условный пользователь выбирает комнату и время, получает свободные интервалы, выбирает слот и отправляет подтверждение. При занятом слоте видит отказ и может выбрать другой. При потере ответа видит неизвестность; результат устанавливается для того же подтверждения. Описание не доказывает реализацию.",
    answerParts=[
        {"id":"SH-CREATE-SLOT","text":"Выбрать комнату, время и доступный слот."},
        {"id":"SH-CREATE-CONFIRM","text":"Подтвердить бронирование и различить подтверждение, занятый слот и неизвестный результат."},
        {"id":"SH-CREATE-LOSS","text":"После потери ответа установить результат того же подтверждения без повторного создания."}])
node("scenarios","R-SCREATE").update(
    targetModule="SH-TM-SCREATE · Scenario S-CREATE",
    delegations=[{"targetModuleInstance":"SH-TM-SCREATE",
                 "modelRef":"TM-SCENARIO-PLANNING","requirementId":"SH-R-SCREATE",
                 "answerRef":"SH-D-DESCRIBE","answerGraph":PREFIX+"scenario-create",
                 "status":"delegated-in-example-only","fulfillment":"unverified"}])
node("scenarios","R-SCANCEL")["description"]="Тот же R получает локальный ответ в этом файле; отдельный граф отмены не нужен для данного примера."
add_node("scenarios",N("D-CANCEL","decision","Описание отмены и её результата",
    **selected("Scenario отмены бронирования","Пользователь находит существующее бронирование, отменяет его и видит результат. Условное описание; работа приложения не доказана.",
               evidenceStatus="unverified",
               answerParts=[{"id":"SH-CANCEL-RESULT","text":"Найти бронирование, отменить его и получить понятный результат отмены."}])))
add_reference("functionality","scenario-create","D-DESCRIBE")
add_reference("functionality","scenarios","D-CANCEL")
suite["scenarios"]["edges"].append(E("SC-04","DRIVES","R-SCANCEL","D-CANCEL","Конкретный ответ на описание отмены, не исполнение отмены."))
suite["functionality"]["edges"] += [
    E("FUN-15","INFORMS","D-DESCRIBE","D-CHOOSE-FEATURES",
      "Использует SH-CREATE-SLOT для Availability и SH-CREATE-CONFIRM для Reservation; НЕ всю документацию Scenario.",
      usedParts=["SH-CREATE-SLOT","SH-CREATE-CONFIRM"]),
    E("FUN-16","INFORMS","D-CANCEL","D-CHOOSE-FEATURES",
      "Использует SH-CANCEL-RESULT: отмена и её результат относятся к Reservation.",
      usedParts=["SH-CANCEL-RESULT"])]
node("functionality","D-CHOOSE-FEATURES")["description"] += " Границы основаны на конкретных частях описаний создания и отмены; независимость разработки остаётся непроверенной."
node("functionality","Q-FEATURE-COVERAGE").update(
    blocking="partially-blocking",blocks="положительное заключение о полноте и независимости выбранных границ",
    closesWith="сопоставление всех существенных потребностей Scenario с конкретными ответами Features")

# ONE shared choice of form; local answers below have distinct subjects.
add_node("functionality",N("R-BEHAVIOR","requirement","Описать Behavior обеих Features",
    crosscutting=True,scope="Behavior Availability и Reservation",
    description="Одна общая потребность описать действия, реакции, ошибки и правила обеих Features; это не одинаковое поведение."))
for ident in ("V-BEHAVIOR-PATH","V-STATES","C-INTERACTION"):
    add_node("functionality",deepcopy(node("reservation",ident)))
add_node("functionality",N("D-BEHAVIOR-SHARED","decision","Общий выбор: Behavior Path для обеих Features",
    **selected("Behavior Availability и Reservation",
        "ОДНО условное D о форме описания. Availability и Reservation используют его, но имеют разные локальные ответы. Новое событие или вопрос не отменяют его автоматически.")))
suite["functionality"]["edges"] += [
    E("SHARED-01","DRIVES","R-BEHAVIOR","D-BEHAVIOR-SHARED","Один R с общим scope требует одного выбора формы."),
    E("SHARED-02","CONTEXT_FOR","C-INTERACTION","D-BEHAVIOR-SHARED","Исходное основание общего выбора формы."),
    E("SHARED-03","USES_VARIANT","D-BEHAVIOR-SHARED","V-BEHAVIOR-PATH","Общее D использует одну reusable форму."),
    E("SHARED-04","APPLIES_TO","R-BEHAVIOR","R-FEAT-AVAIL","Требование описания Behavior относится к Availability."),
    E("SHARED-05","APPLIES_TO","R-BEHAVIOR","R-FEAT-RES","То же требование относится к Reservation.")]
node("reservation","D-BEHAVIOR").update(
    title="Локальный Behavior подтверждения Reservation",
    description="Конкретное содержание Reservation: подтверждение, отказ занятого слота и обработка потери ответа. Форму не выбирает заново: использует общий SH-D-BEHAVIOR-SHARED. Реализация не подтверждена.",
    usesSharedDecisionRef="SH-D-BEHAVIOR-SHARED",evidenceStatus="unverified")
node("reservation","R-ERRORS").update(
    scope="Ошибки подтверждения в Reservation",
    description="Локальный R из слота ошибок общего Behavior Path. D-STATUS отвечает только части о потере ответа; занятый слот описан отдельным D-BUSY. Полнота всех ошибок не подтверждена.")
for part in ("availability","reservation"):
    add_reference(part,"functionality","R-BEHAVIOR")
    add_reference(part,"functionality","D-BEHAVIOR-SHARED")
suite["availability"]["edges"] += [
    E("AV-04","DRIVES","R-BEHAVIOR","D-BEHAVIOR-SHARED","То же общее R/D видны в области Availability."),
    E("AV-05","GOVERNED_BY_SHARED_CHOICE","D-BEHAVIOR-SHARED","D-AVAIL-NEW","Локальное описание Availability использует общее решение о форме.")]
suite["reservation"]["edges"] += [
    E("RS-11","DRIVES","R-BEHAVIOR","D-BEHAVIOR-SHARED","Тот же R остаётся драйвером общего D."),
    E("RS-12","GOVERNED_BY_SHARED_CHOICE","D-BEHAVIOR-SHARED","D-BEHAVIOR","Общая форма управляет локальным ответом, не копируется как новый выбор.")]
for e in suite["reservation"]["edges"]:
    if e["id"]=="SH-E-RS-06":
        e.update(**{"from":"SH-D-BEHAVIOR-SHARED","parent":"SH-R-BEHAVIOR",
                    "meaning":"Общий выбранный формат вводит локальный R ошибок Reservation; parent — тот же общий R Behavior."})
    if e["id"] in {"SH-E-RS-07","SH-E-RS-08","SH-E-RS-09"}:
        e["to"]="SH-D-BEHAVIOR-SHARED"
node("reservation","Q-BEHAVIOR").update(
    blocking="partially-blocking",blocks="утверждение достаточности общего способа в новом контексте",
    closesWith="сравнение форм на одном фрагменте внешнего события")
node("reservation","PR-STATE")["description"]="Pending предложение пересмотра общего SH-D-BEHAVIOR-SHARED, не новое принятое D."
# Keep the earlier local selection explicitly local in the hypothetical log.
suite["reservation"]["events"][0]["note"]="В условном сюжете выбран локальный ответ Reservation; общий формат задан отдельно."
node("scenario-create","D-STATUS").update(
    scope="Локальная обработка потери ответа подтверждения в Reservation",
    description="Показать понятную неизвестность, проверить статус того же подтверждения и показать подтверждение или отказ только после окончательного результата. Промежуточный ответ не превращать в отказ. Не создавать повторное бронирование автоматически. Достаточность условна; контракт средства не проверен.",
    evidenceStatus="unverified",openQuestion="SH-Q-STATUS",
    answerParts=[
        {"id":"SH-STATUS-UNKNOWN","text":"При потере или промежуточном ответе сохранить неизвестность; это не отказ."},
        {"id":"SH-STATUS-CORRELATE","text":"Проверять статус именно того же подтверждения; возможность корреляции пока не подтверждена."},
        {"id":"SH-STATUS-FINAL","text":"Показывать подтверждение или отказ только при установленном окончательном результате."},
        {"id":"SH-STATUS-NO-DUP","text":"Повторное создание не является автоматическим способом получить ответ."}],
    answerBindings=[
        {"requirementId":"SH-R-RESULT","parts":["SH-STATUS-CORRELATE","SH-STATUS-FINAL","SH-STATUS-NO-DUP"],"sufficiency":"conditional"},
        {"requirementId":"SH-R-FEEDBACK","parts":["SH-STATUS-UNKNOWN","SH-STATUS-FINAL"],"sufficiency":"conditional"},
        {"requirementId":"SH-R-ERRORS","parts":["SH-STATUS-UNKNOWN","SH-STATUS-CORRELATE","SH-STATUS-FINAL"],"sufficiency":"partial; только потеря ответа"}])
node("scenario-create","Q-STATUS").update(
    blocking="partially-blocking",blocks="заключение о достаточности и реализация статусного способа",
    closesWith="контракт и проверка корреляции с нужным подтверждением, окончательности и достижимости результата после потери ответа")
for ident in ("R-RESULT","R-FEEDBACK","C-STATUS","D-STATUS","Q-STATUS"):
    add_reference("reservation","scenario-create",ident)
suite["reservation"]["edges"] += [
    E("RS-13","DRIVES","R-ERRORS","D-STATUS","Часть ответа на локальный R ошибок: потеря ответа; не весь список ошибок.",
      usedParts=["SH-STATUS-UNKNOWN","SH-STATUS-CORRELATE","SH-STATUS-FINAL"]),
    E("RS-14","DRIVES","R-RESULT","D-STATUS","Тот же D одновременно отвечает функциональной потребности без дублирования."),
    E("RS-15","CONTEXT_FOR","C-STATUS","D-STATUS","Основания того же локального способа."),
    E("RS-16","QRPE_FOR","Q-STATUS","D-STATUS","Тот же вопрос достаточности, не копия вопроса.")]
add_node("reservation",N("D-BUSY","decision","При занятом слоте показать отказ и предложить другой",
    **selected("Обработка занятого слота в Reservation","Ответ только на часть R-ERRORS о занятом слоте. Не закрывает все ошибки и не заменяет D-STATUS.",evidenceStatus="unverified")))
suite["reservation"]["edges"].append(E("RS-17","DRIVES","R-ERRORS","D-BUSY","Другая конкретная часть ответа R-ERRORS; не второй D-STATUS."))

# Different local State subjects do not reselect the shared Behavior form.
for part, suffix, title, answer in [
    ("availability","SELECTION","Описать состояние выбора комнаты и времени","Простой список данных: выбранная комната и интервал; не таблица состояний бронирования."),
    ("reservation","RESERVATION","Описать состояние бронирования","Таблица состояний бронирования; неизвестность ответа клиента не равна отказу бронирования.")]:
    root_id=suite[part]["rootRequirementId"][3:]
    add_node(part,N("R-STATE-"+suffix,"requirement",title,scope=title,
                   description="Самостоятельный локальный предмет, уточнённый из Feature R; не новый Scenario."))
    add_node(part,N("D-STATE-"+suffix,"decision","Локальный ответ: "+("список данных" if part=="availability" else "таблица состояний"),
                   **selected(title,answer,evidenceStatus="unverified")))
    suite[part]["edges"] += [
        E("STATE-"+suffix+"-01","DERIVES",root_id,"R-STATE-"+suffix,"Содержательное уточнение предмета локального состояния, не введение задачи общим D."),
        E("STATE-"+suffix+"-02","DRIVES","R-STATE-"+suffix,"D-STATE-"+suffix,"Разные локальные R получают разные D, общий выбор Behavior не изменяется.")]
# Explicit owner references for repeated Requirements and ready variants.
owners={}
for g in graphs:
    for e in g["edges"]:
        if e["type"]=="INTRODUCES":
            owners[e["to"]]=g["id"]
owners.update({"SH-D-BEHAVIOR-SHARED":PREFIX+"functionality",
               "SH-R-BEHAVIOR":PREFIX+"functionality",
               "SH-V-BEHAVIOR-PATH":PREFIX+"functionality",
               "SH-V-STATES":PREFIX+"functionality",
               "SH-C-INTERACTION":PREFIX+"functionality"})
for g in graphs:
    part=g["id"][len(PREFIX):]
    for i,n in enumerate(g["nodes"]):
        owner=owners.get(n["id"])
        if owner and owner!=g["id"] and not n.get("projectionOf"):
            g["nodes"][i]=reference(part,owner[len(PREFIX):],n["id"][3:])
    g["revision"]=3
    # Complete example histories belong to owning records, not projections.
    for n in g["nodes"]:
        if (n["kind"]=="decision" and not n.get("projectionOf") and
            n.get("status")=="selected-in-example-only" and
            not any(ev.get("decisionId")==n["id"] for ev in g["events"])):
            g["events"].append(hypothetical_event("SELECT-"+n["id"][3:],"decision_selected",n["id"][3:],
                             "Выбор только в вымышленном сюжете; не решение реального пользователя."))

EXPECTED_SLUGS = {PREFIX+s for s in (
    "app","functionality","scenarios","realization","availability",
    "reservation","scenario-create")}
WRITER_TYPES = {"DRIVES","INTRODUCES","DERIVES","CONTEXT_FOR","APPLIES_TO"}
assert {g["id"] for g in graphs} == EXPECTED_SLUGS
assert len({g["rootRequirementId"] for g in graphs}) == len(graphs)
covered_types = set()
for g in graphs:
    ids = [n["id"] for n in g["nodes"]]
    edges = [e["id"] for e in g["edges"]]
    assert len(ids) == len(set(ids)) and len(edges) == len(set(edges)), g["id"]
    kinds = {n["id"]: n["kind"] for n in g["nodes"]}
    drivers={(e["from"],e["to"]) for e in g["edges"] if e["type"]=="DRIVES"}
    for edge in g["edges"]:
        assert edge["from"] in kinds and edge["to"] in kinds, (g["id"],edge)
        assert edge.get("meaning"), edge
        if edge["type"] == "INTRODUCES":
            assert kinds[edge["from"]] == "decision"
            assert kinds[edge["to"]] == "requirement"
            assert (edge["parent"],edge["from"]) in drivers
            assert edge["parent"] in kinds and kinds[edge["parent"]]=="requirement"
        if edge["type"]=="APPLIES_TO":
            assert any(n["id"]==edge["from"] and n.get("crosscutting")
                       for n in g["nodes"])
        covered_types.add(edge["type"])
    for ev in g["events"]:
        assert ev.get("exampleOnly") and ev.get("by")=="example-only", ev
assert len(covered_types) == 17, sorted(covered_types)

# Scale is a task property, independent of file size. Broad feature/scenario
# plans remain TM; narrow statements/answers are separate Unit views.
for g in graphs:
    g["planningScale"] = "module"
    g["revision"] = 4

narrow = {
    "availability":["R-STATE-SELECTION"],
    "reservation":["R-STATE-RESERVATION","R-ERRORS"],
    "realization":["R-BOUNDARY"],
    "scenario-create":["R-RESULT","R-FEEDBACK"],
    "scenarios":["R-SCANCEL"],
}
unit_views = []
for part, ids in narrow.items():
    parent = suite[part]
    for ident in ids:
        rid = "SH-"+ident
        answer_ids = {e["to"] for e in parent["edges"] if e["type"]=="DRIVES" and e["from"]==rid}
        keep = {rid, *answer_ids}
        # Retain relevant questions/grounds, not a clone of the whole source graph.
        for e in parent["edges"]:
            if e["to"] in answer_ids and e["type"] in {"CONTEXT_FOR","QRPE_FOR"}:
                keep.add(e["from"])
        nodes = [reference(part, part, n["id"][3:]) for n in parent["nodes"] if n["id"] in keep]
        for n in nodes:
            original = next(x for x in parent["nodes"] if x["id"]==n["id"])
            if original.get("projectionOf"):
                n["projectionOf"] = deepcopy(original["projectionOf"])
        slug = PREFIX+"unit-"+ident.lower()
        unit_views.append(dict(schemaVersion=1,id=slug,title="Unit · "+node(part,ident)["title"],
            revision=1,identitySpace=SPACE,rootRequirementId=rid,planningScale="unit",
            readOnly=True,exampleOnly=True,hypothetical=True,selectedInProject=False,
            catalogHidden=True,demonstrationGroup="complete-booking-showcase",canonicality="ILLUSTRATION_ONLY",
            expansionOf={"graphSlug":parent["id"],"nodeId":rid},sourceDocument=SOURCE,
            coverage="Отдельный граф узкой задачи; R/D ссылаются на прежних владельцев. Нового выбора нет.",
            nodes=nodes,edges=[deepcopy(e) for e in parent["edges"] if e["from"] in keep and e["to"] in keep],
            events=[]))
graphs.extend(unit_views)

if __name__ == "__main__":
    import sys
    check_only = "--check" in sys.argv[1:]
    for graph in graphs:
        path = DIR / graph["id"] / "graph.json"
        content = json.dumps(graph, ensure_ascii=False, indent=2) + "\n"
        if check_only:
            assert path.read_text(encoding="utf-8") == content, path
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                existing=json.loads(path.read_text(encoding="utf-8"))
                assert existing.get("id")==graph["id"] and existing.get("readOnly") is True
                assert existing.get("demonstrationGroup")=="complete-booking-showcase"
            path.write_text(content, encoding="utf-8")
    print("COMPLETE_SHOWCASE_OK:",len(graphs),"graphs,",len(covered_types),
          "edge types,",sum(len(g["nodes"]) for g in graphs),"nodes,",
          sum(len(g["edges"]) for g in graphs),"edges, check_only=",check_only)
