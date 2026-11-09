"""Typed dependency capabilities and role matching; called by the Decision kernel.

No persistence or second review owner lives here. All effects are returned to the
existing graph transaction. Paths are bounded explicitly and never follow stale.
"""
import copy
from contextlib import nullcontext
import hashlib
import json

ROLE_LIMIT = 32
PATH_LIMIT = 32
WATCHES = {
    'definition': ('Содержание элемента', 'all', ['changed']),
    'directScope': ('Непосредственный состав и определения участников', ['requirement','decision','action'], ['changed','added','removed']),
    'membership': ('Состав динамической роли', 'all', ['added','removed']),
    'structuralScope': ('Состав структурных отношений и свойства Decision Groups', ['requirement','decision','action'], ['changed','added','removed']),
    'selection': ('Выбор Decision', ['decision'], ['changed']),
    'result': ('Результат элемента', ['requirement','decision','action'], ['changed']),
    'context': ('Состав и содержание контекста Decision', ['decision'], ['changed','added','removed']),
    'canon': ('Связанные Canon: состав и содержание', ['requirement','decision','action'], ['changed','added','removed']),
    'info': ('Непосредственные Info: состав и содержание', 'all', ['changed','added','removed']),
    'canonInfo': ('Info Canon решения · совместимость', ['decision','canon'], ['changed','added','removed']),
    'relations': ('Непосредственные отношения', 'all', ['added','removed']),
    'workGraphs': ('Принадлежность рабочим областям', 'all', ['added','removed']),
    'rootCauses': ('Основания корневого Requirement', ['requirement'], ['changed','added','removed']),
    'locks': ('Блокировки элемента', 'all', ['changed']),
    'event': ('Записанное событие RDG с участием элемента', 'all', ['changed']),
    'predicate': ('Переход наблюдаемого условия', 'all', ['changed','added','removed']),
}
EXTRA_RELATIONS = {
    'DECISION_MEMBER': ({'requirement','decision'}, {'decision'}),
    'FINDING_SUBJECT': ({'requirement','decision','action'}, {'finding'}),
    'DECISION_CONTEXT': ({'requirement','decision','action','context','finding','canon','info','evidence'}, {'decision'}),
    'ACTION_TARGET': ({'action'}, {'decision'}),
    'SHARED_WORK_GRAPH': ('all', 'all'),
}
FIELDS = {'selectionState', 'result.state', 'result.truth', 'tag', 'active'}

# User-facing explanations travel with the executable capability registry.
# Technical IDs remain stable and are shown separately from the meaning.
RELATION_HELP = {
 'FINDING_SUBJECT': ('Элемент находки', 'Исходный элемент → Finding; наблюдается его содержание.', 'D-1 → F-P-1.'),
 'FINDING_RESPONSE': ('Решение разрешить файндинг', 'Исходный элемент → обычный Decision разрешить находку.', 'D-1 → D-resolve.'),
 'FINDING_PROPOSAL': ('Способ разрешения файндинга', 'Decision разрешить Finding → обычный Decision-proposal.', 'D-resolve → D-proposal.'),
 'DERIVES': ('Дочернее требование', 'Родительское Requirement → дочернее Requirement. Дочернее требование уточняет обязательство родителя.', 'R-1 → R-2: для достижения R-1 необходимо выполнить R-2.'),
 'DRIVES': ('Решение для требования', 'Requirement → Decision. Решение является вариантом достижения этого требования. Стрелка направлена от требования к решению.', 'R-1 «Хранить данные» → D-1 «Использовать PostgreSQL».'),
 'INTRODUCES': ('Требование, введённое решением', 'Decision → Requirement. Выбранное решение вводит дополнительное требование.', 'D-1 «Использовать PostgreSQL» → R-2 «Обеспечить резервирование».'),
 'REQUIRES_ACTION': ('Обязательное действие', 'Requirement или Decision → Action. Действие относится к выполнению этого требования или решения.', 'D-1 → A-1 «Настроить развёртывание».'),
 'CANON_FOR': ('Критерии оценки блока', 'Canon → Requirement, Decision или Action. Canon задаёт критерии оценки указанного блока.', 'Can-1 «Требования к надёжности» → D-1.'),
 'CONTEXT_FOR': ('Контекст, связанный с блоком', 'Context → Requirement, Decision или Action. Это обычная контекстная связь. Включение в «Контекст принятия решения» задаётся отдельным отношением.', 'Ctx-1 «Окружение» → A-1 «Развернуть сервис».'),
 'INFO_FOR': ('Информация об элементе', 'Info → элемент любого поддерживаемого типа. Информация поясняет получателя связи и не создаёт структурного родителя.', 'Inf-1 «Документация PostgreSQL» → Can-1.'),
 'EVIDENCE_FOR': ('Свидетельство для элемента', 'Evidence → Requirement, Decision, Action или Context. Свидетельство относится к утверждению или результату указанного элемента.', 'Ev-1 «Результат нагрузочного теста» → D-1.'),
 'DEPENDS_ON': ('Источник зависимости → зависимый элемент', 'Стрелка направлена от наблюдаемого источника к зависимому элементу. Это существующая ручная зависимость; она не создаёт родительство. Для новой политики такая связь не обязательна.', 'Ctx-1 → D-1: решение зависит от наблюдаемых изменений Ctx-1.'),
 'DECISION_MEMBER': ('Вариант в группе решений', 'Requirement → Decision через Decision Group. Решение входит в группу вариантов для данного требования. Отношение вычисляется из состава группы.', 'D-1 и D-2 входят в группу вариантов для R-1.'),
 'DECISION_CONTEXT': ('Элемент контекста принятия решения', 'Requirement, Decision, Action или Context → Decision. Участник включён именно в «Контекст принятия решения». Учитываются и прежние ссылки, и настроенные контекстные зависимости.', 'Ctx-1 «Нагрузка» включён в контекст принятия D-1.'),
 'ACTION_TARGET': ('Решение, на которое направлено действие', 'Action → Decision из списка целей действия. Это назначение действия, а не структурное родительство.', 'A-1 «Выбрать вариант» направлено на D-1.'),
 'SHARED_WORK_GRAPH': ('Участники одной рабочей области', 'Два разных элемента входят в одну Working Graph. Отношение симметрично и не означает родительство или зависимость само по себе.', 'D-1 и Ctx-1 включены в область «Хранилище».'),
}
WATCH_HELP = {
 'definition': ('Содержание самого элемента', 'Сравниваются название, описание, метки и предметные поля элемента: область Requirement, значение Context/Info, критерии Canon, поля Evidence, тип и назначения Action. Одна ревизия сама по себе не вызывает срабатывания.', 'В Ctx-1 значение нагрузки изменилось со 100 на 1000 запросов.', {'changed':'Изменилось содержание элемента'}),
 'directScope': ('Содержание и состав ближайшего окружения · L2', 'Наблюдаются непосредственные структурные соседи по правилам типа источника, прямые Canon и Context, состав и правила связанных Decision Groups, а у Decision — его контекст принятия решения. Сравниваются состав и включённые определения; глубина не увеличивается при stale соседнего блока.', 'У источника добавлен непосредственный ребёнок или изменилось описание его непосредственного родителя.', {'changed':'Изменились включённые данные ближайшего окружения','added':'В окружении появился участник или связь','removed':'Из окружения исключён участник или связь'}),
 'membership': ('Состав выбранного набора участников', 'Отслеживается попадание элементов в динамическую роль и выход из неё. Изменение текста участника при сохранении состава настраивается отдельным наблюдением.', 'В набор «Элементы контекста родителя» вошёл Ctx-2.', {'added':'Участник вошёл в выбранный набор','removed':'Участник вышел из выбранного набора'}),
 'structuralScope': ('Непосредственные структурные связи и правила групп', 'Отслеживаются непосредственные структурные связи, состав Decision Groups, обязательность и взаимоисключение выбора. Текст соседних блоков, Info, Evidence и состав рабочих областей сюда не входят.', 'У блока изменился родитель или в его группе решений изменилось правило обязательного выбора.', {'changed':'Изменились правила или состав Decision Group','added':'Добавлена непосредственная структурная связь или группа','removed':'Удалена непосредственная структурная связь или группа'}),
 'selection': ('Состояние выбора Decision', 'Отслеживается переход между состояниями «обнаружен», «выбран» и «выбор снят». Изменение описания или результата Decision настраивается отдельно.', 'У D-1 снят ранее сделанный выбор.', {'changed':'Изменилось состояние выбора Decision'}),
 'result': ('Сохранённый результат блока', 'Сравнивается сохранённый результат Requirement, Decision или Action: открытие, подтверждение и данные результата. Выполнение дочернего действия само по себе не означает подтверждение результата родителя.', 'Подтверждённый результат D-1 переоткрыт.', {'changed':'Изменился сохранённый результат блока'}),
 'context': ('Состав и наблюдаемые данные контекста Decision', 'Наблюдается «Контекст принятия решения»: добавление и исключение участников, а также изменения по сохранённым настройкам их наблюдения. Например, настройка L2 участника включает его ближайшее окружение. Обычная связь CONTEXT_FOR сама по себе не включает элемент в этот набор.', 'В контекст D-1 добавлен уже существующий Ctx-2; позднее изменилось его наблюдаемое значение.', {'changed':'Изменились наблюдаемые данные участника контекста','added':'Участник включён в контекст Decision','removed':'Участник исключён из контекста Decision'}),
 'canon': ('Прямые Canon блока: состав и содержание', 'Отслеживаются Canon, связанные непосредственно с наблюдаемым блоком через «Критерии оценки блока», их добавление, исключение и содержание. Связанные с Canon Info сюда не включаются.', 'Для D-1 добавлен Can-2 или изменены критерии Can-1.', {'changed':'Изменилось содержание связанного Canon','added':'Canon привязан к наблюдаемому блоку','removed':'Canon отвязан от наблюдаемого блока'}),
 'info': ('Прямые Info элемента: состав и содержание', 'Отслеживаются только Info, непосредственно связанные с выбранным элементом. Для наблюдения Info Canon решения используется отдельный вариант ниже.', 'К D-1 непосредственно добавлена Inf-1 или изменилось её содержание.', {'changed':'Изменилось содержание прямого Info','added':'Info непосредственно привязано к элементу','removed':'Info отвязано от элемента'}),
 'canonInfo': ('Info Canon решения · совместимость', 'Для Decision наблюдаются Info его непосредственно связанных Canon. Для Canon наблюдаются его собственные Info. Этот вариант сохраняет смысл прежнего наблюдения info при переносе старой политики.', 'Изменилось Inf-1, связанное с Can-1, который оценивает D-1.', {'changed':'Изменилось содержание Info Canon','added':'Добавлено Info Canon','removed':'Удалена связь с Info Canon'}),
 'relations': ('Добавление и удаление прямых отношений', 'Наблюдается состав отношений вокруг элемента: реальные рёбра и вычисляемые связи участников групп, контекста и целей Action. Общая рабочая область выбирается отдельным наблюдением.', 'Для элемента создана или удалена связь с другим участником.', {'added':'Появилось непосредственное отношение','removed':'Исчезло непосредственное отношение'}),
 'workGraphs': ('Включение элемента в рабочие области', 'Отслеживается включение самого элемента в Working Graph и исключение из неё. Изменение названия, цвета или других участников области не является таким событием.', 'D-1 включён в область «Хранилище».', {'added':'Элемент включён в рабочую область','removed':'Элемент исключён из рабочей области'}),
 'rootCauses': ('Основания корневого Requirement', 'Сравниваются записи оснований выбранного Requirement: их наличие и сохранённые сведения. Структурная активность блока проверяется отдельным условием.', 'У R-1 изменилось записанное основание существования.', {'changed':'Изменена запись корневого основания','added':'Добавлено корневое основание','removed':'Удалено корневое основание'}),
 'locks': ('Настройки блокировок элемента', 'Отслеживаются изменения конфигурации блокировок самого элемента. Это не наблюдение за его содержанием или результатом.', 'Для редактирования D-1 установлена блокировка.', {'changed':'Изменены настройки блокировок элемента'}),
 'event': ('Конкретное записанное событие RDG', 'Выбирается тип Graph-события. Условие срабатывает, когда событие этого типа записано с участием наблюдаемого элемента. Обобщённое событие «Изменение элемента» не гарантирует изменение содержания: оно используется и для служебных изменений, включая review.', 'Для наблюдаемого Decision записано событие «Выбор Decision снят».', {'changed':'Записано выбранное событие с участием элемента'}),
 'predicate': ('Изменение истинности условия', 'Сравнивается условие до и после изменения: наличие метки, выбор Decision, состояние результата или структурная активность. Постоянно ложное условие не создаёт повторные срабатывания. Такое же условие в разделе применимости имеет другой эффект — отключение применения.', 'У элемента исчезла метка «проверено»: условие стало ложным.', {'changed':'Истинность условия изменилась','added':'Условие стало истинным','removed':'Условие стало ложным'}),
}
EVENT_HELP = {
 'created':('Элемент создан','В Graph зарегистрировано создание элемента.'),
 'edited':('Изменение элемента зарегистрировано','Обобщённый факт изменения. Для наблюдения именно содержания выбирайте «Содержание самого элемента»; edited также используется при review.'),
 'linked':('Связь создана','Зарегистрирована новая связь между участниками.'),
 'unlinked':('Связь удалена','Связь удалена; сами участники могут продолжать существовать.'),
 'removed':('Элемент удалён','Удалён сам элемент. Исключение из контекста без удаления элемента — другая операция.'),
 'group_changed':('Группа решений изменена','Изменена конфигурация Decision Group.'),
 'work_graph_changed':('Рабочая область изменена','Изменена Working Graph; для включения конкретного участника используйте наблюдение принадлежности рабочим областям.'),
 'root_cause_changed':('Корневые основания изменены','Зарегистрировано изменение корневых оснований.'),
 'decision_selected':('Decision выбран','Зарегистрирован выбор Decision.'),
 'decision_unselected':('Выбор Decision снят','Зарегистрировано снятие выбора Decision.'),
 'branch_cancelled':('Структурная ветвь отменена','Зафиксирована структурная отмена. Это самостоятельный факт, а не статус stale.'),
 'action_executed':('Выполнение Action подтверждено','Записан факт выполнения Action.'),
 'requirement_achieved':('Достижение Requirement подтверждено','Записан подтверждённый результат Requirement.'),
 'decision_completed':('Результат Decision подтверждён','Записан подтверждённый результат Decision.'),
 'reopened':('Результат переоткрыт','Ранее подтверждённый результат переоткрыт.'),
 'lock_set':('Блокировка установлена','Зарегистрирована установка или настройка блокировки.'),
 'lock_removed':('Блокировка удалена','Зарегистрировано удаление блокировки.'),
 'lens_application_recorded':('Применение линзы записано','Зафиксировано применение линзы с соответствующими ссылками.'),
 'policy_changed':('Политика изменена','Записано изменение конфигурации политики. Это не событие её срабатывания.'),
 'binding_changed':('Применение политики изменено','Записано создание или изменение применения. Это не подтверждение пересмотра.'),
}
POLICY_HELP = {
 'builtin:finding-subject':dict(name='Содержание элемента файндинга',description='Изменение содержания исходного элемента требует пересмотра находки.',applicability='Исходный элемент Finding существует. Потеря применимости отключает применение.',observes='Содержание исходного элемента; review и disposition не являются его содержанием.',example='Описание D изменилось → пересмотр Finding.'),
 'builtin:L1':dict(name='L1 · Содержание источника',description='Цель требует пересмотра, когда изменилось содержание выбранного источника. Родственная или структурная связь между ними не требуется.',applicability='Источник существует; цель — Requirement, Decision или Action. Оба элемента выбираются при применении.',observes='Название, описание, метки и предметные поля источника. Состояние выбора, результат и блокировки наблюдаются отдельными настройками.',example='Ctx-1 «Нагрузка» изменён → D-1 «Выбрать хранилище» требует пересмотра.'),
 'builtin:L2':dict(name='L2 · Содержание и ближайшее окружение',description='Цель требует пересмотра при изменении содержания источника, состава его ближайшего окружения или включённых в это окружение данных. Это наблюдение шире, чем только список детей.',applicability='Источник — Requirement, Decision или Action; цель выбирается отдельно. Обязательное родство источника и цели не требуется.',observes='Непосредственные структурные соседи по типу источника, прямые Canon и Context, состав и правила Decision Groups; у Decision также контекст принятия решения в обоих поддерживаемых форматах. Глубокие потомки, Info и Evidence не включаются автоматически.',example='Изменилось описание непосредственного родителя источника или в его контекст добавлен участник → выбранная цель требует пересмотра.'),
 'builtin:decision_state':dict(name='Decision · Выбор и результат',description='Цель требует пересмотра при изменении состояния выбора или сохранённого результата выбранного Decision.',applicability='Источник — Decision. Цель — любой поддерживаемый блок пересмотра; родственная связь не требуется.',observes='Переход состояния выбора и изменение сохранённого результата. Описание Decision и его контекст настраиваются отдельными наблюдениями.',example='У D-1 снят выбор или переоткрыт результат → зависимый R-1 требует пересмотра.'),
 'builtin:decision_context':dict(name='Decision · Содержание и контекст',description='Цель требует пересмотра при изменении содержания самого Decision, состава его контекста принятия или наблюдаемых данных участников контекста.',applicability='Источник — Decision; цель выбирается независимо от родительства. Пустой контекст допустим.',observes='Собственное содержание Decision и его контекст принятия решения. Сохранённые наблюдения участников контекста, в том числе L2, учитываются. Обычный CONTEXT_FOR не заменяет включение в контекст принятия решения.',example='В контекст D-1 включён Ctx-2 или изменилось описание самого D-1 → выбранная цель требует пересмотра.'),
 'builtin:decision_canon':dict(name='Decision · Содержание и критерии Canon',description='Цель требует пересмотра при изменении содержания самого Decision, добавлении или отвязке его прямых Canon и изменении содержания этих Canon.',applicability='Источник — Decision; цель выбирается отдельно. Наличие хотя бы одного Canon не обязательно.',observes='Содержание Decision и его прямые Canon. Info, поясняющие Canon, выбираются отдельным наблюдением.',example='Для D-1 добавлен Can-2 или изменены критерии Can-1 → выбранная цель требует пересмотра.'),
 'builtin:canon_criteria':dict(name='Canon · Содержание критериев',description='Цель требует пересмотра при изменении содержания выбранного Canon. Это вариант L1 с источником типа Canon.',applicability='Источник — Canon; цель выбирается при применении. Наличие CANON_FOR между ними не требуется.',observes='Название, описание, метки и содержание критериев Canon. Для привязанных Info существует отдельное наблюдение.',example='Изменены критерии Can-1 → явно выбранный D-1 требует пересмотра, даже если между ними нет CANON_FOR.'),
 'builtin:structural':dict(name='Изменения непосредственного родителя',description='Непосредственный ребёнок требует пересмотра при изменении содержания родителя. Для родительского Decision дополнительно учитываются контекст принятия и прямая команда снятия выбора.',applicability='Источник — непосредственный структурный родитель цели через дочернее требование, решение, обязательное действие или участие в группе. При потере этого отношения применение отключается и сохраняется.',observes='Содержание родителя; для Decision — добавление и исключение участников контекста и изменения по сохранённым настройкам их наблюдения. Правило не распространяет stale рекурсивно на всё поддерево.',example='У D-1, родителя R-1, в контекст добавлен Ctx-2 → R-1 требует пересмотра по условию добавления участника.'),
 'builtin:automatic-canon':dict(name='Canon оцениваемого блока',description='Блок требует пересмотра при появлении у него прямого Canon или при изменении содержания уже привязанного Canon. Применение определяется связью оценки автоматически.',applicability='Canon связан с целью через CANON_FOR. После удаления обязательной связи применение отключается и сохраняется.',observes='Привязка этого Canon к существующему оцениваемому блоку и последующее изменение его содержания. Снятие связи является потерей применимости этого применения.',example='Can-1 привязан к D-1 → требуется пересмотр; позднее изменение критериев Can-1 создаёт отдельную причину.'),
 'builtin:structural-topology':dict(name='Непосредственные структурные связи',description='Сам элемент требует пересмотра при изменении своих непосредственных структурных связей, состава или правил выбора связанных Decision Groups.',applicability='Цель — Requirement, Decision или Action. Набор родителей и детей может быть пустым; исчезновение последней связи не отключает это наблюдение.',observes='Добавление и удаление непосредственных структурных отношений; состав групп, обязательность и взаимоисключение выбора. У каждого затронутого блока своё применение.',example='У D-1 изменился структурный родитель → D-1 требует пересмотра; применение наблюдения содержания прежнего родителя при этом может отдельно отключиться.'),
}


def check(value, code):
    if not value: raise ValueError('POLICY_' + code)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':')).encode()).hexdigest()


def relation_pairs(K):
    pairs = {**K.RELATION_PAIRS, **EXTRA_RELATIONS}
    return {key: (set(K.ENTITY_KINDS) if a == 'all' else set(a),
                  set(K.ENTITY_KINDS) if b == 'all' else set(b))
            for key, (a,b) in pairs.items()}


def relation_types(value):
    return value if isinstance(value,list) else [value]


def valid_relation(value,K):
    values=relation_types(value)
    return bool(values) and all(isinstance(v,str) and v in relation_pairs(K) for v in values) and len(set(values))==len(values)


def compatible_relation(value,left,right,direction,K):
    for typ in relation_types(value):
        a,b=relation_pairs(K)[typ]
        if direction=='in':a,b=b,a
        if set(left)&a and set(right)&b:return True
    return False


def capabilities(K):
    observations = [{'id':key,'name':WATCH_HELP[key][0],'description':WATCH_HELP[key][1],'example':WATCH_HELP[key][2],'operationLabels':WATCH_HELP[key][3],'kinds':sorted(K.ENTITY_KINDS if kinds=='all' else kinds),
                     'operations':ops,'operationsByKind':({'action':['added','removed'],'requirement':ops,'decision':ops} if key=='structuralScope' else {})} for key,(name,kinds,ops) in WATCHES.items()]
    relations = [{'id':key,'name':RELATION_HELP[key][0],'description':RELATION_HELP[key][1],'example':RELATION_HELP[key][2],'fromKinds':sorted(a),'toKinds':sorted(b),
                  'directions':['out','in'],'minDepth':1,'maxDepth':PATH_LIMIT}
                 for key,(a,b) in sorted(relation_pairs(K).items())]
    # Each row is an executable family, not a separate persisted policy.
    combinations = [{'sourceKind':kind,'watch':o['id'],'operations':o['operationsByKind'].get(kind,o['operations']),
                     'targetKinds':sorted(K.REVIEW_KINDS)}
                    for o in observations for kind in o['kinds']]
    return {'version':2,'entityKinds':sorted(K.ENTITY_KINDS),'targetKinds':sorted(K.REVIEW_KINDS),
            'relations':relations,'observations':observations,'events':sorted(K.EVENT_TYPES),
            'eventDescriptions':[{'id':key,'name':EVENT_HELP[key][0],'description':EVENT_HELP[key][1]} for key in sorted(K.EVENT_TYPES)],
            'policyHelp':copy.deepcopy(POLICY_HELP),'predicateFields':sorted(FIELDS),'maxRoles':ROLE_LIMIT,'maxPathDepth':PATH_LIMIT,
            'combinations':combinations}


def predicate_valid(pred, kinds, K):
    check(isinstance(pred,dict) and set(pred)=={'field','equals'} and pred['field'] in FIELDS,
          'PREDICATE_SCHEMA')
    field=pred['field'];value=pred['equals']
    if field=='selectionState':check(set(kinds)<={'decision'} and value in ('discovered','selected','unselected'),'PREDICATE_KIND')
    elif field=='result.state':check(set(kinds)<=K.NODE_KINDS and value in ('open','confirmed'),'PREDICATE_KIND')
    elif field=='result.truth':check(set(kinds)<=K.NODE_KINDS and value in ('true','false','unknown'),'PREDICATE_KIND')
    elif field=='active':check(set(kinds)<=K.NODE_KINDS and type(value) is bool,'PREDICATE_KIND')
    else:check(K.text(value),'PREDICATE_VALUE')


def validate_definition(p, K):
    common={'id','version','name','description','status','pattern','sourceKinds','targetKinds','rules'}
    check(isinstance(p,dict) and common<=set(p) and set(p)<=common|{'roles','relations','origin','automatic'},'SCHEMA')
    check(K.text(p['id']) and K.text(p['name']) and isinstance(p['description'],str) and
          type(p['version']) is int and p['version']>=1 and p['status'] in ('active','disabled','archived'), 'SCHEMA')
    check(K.unique_strings(p['sourceKinds']) and bool(p['sourceKinds']) and
          set(p['sourceKinds'])<=K.ENTITY_KINDS and K.unique_strings(p['targetKinds']) and
          bool(p['targetKinds']) and set(p['targetKinds'])<=K.REVIEW_KINDS, 'KINDS')
    check(p['pattern'] in ('direct','parentDecisionContext','roles'),'PATTERN')
    check(p.get('origin','user') in ('user','system'),'ORIGIN')
    check('automatic' not in p or p.get('origin')=='system' and p['automatic'] is True,'AUTOMATIC_ORIGIN')
    roles={}
    if p['pattern']=='roles':
        check(isinstance(p.get('roles'),list) and 2<=len(p['roles'])<=ROLE_LIMIT,'ROLES')
        for role in p['roles']:
            check(isinstance(role,dict) and {'id','kinds'}<=set(role)<=
                  {'id','name','kinds','selector','required','conditions'} and K.text(role['id']) and
                  role['id'] not in roles and K.unique_strings(role['kinds']) and bool(role['kinds']) and
                  set(role['kinds'])<=K.ENTITY_KINDS and type(role.get('required',True)) is bool,'ROLE_SCHEMA')
            check('name' not in role or K.text(role['name']),'ROLE_NAME')
            conditions=role.get('conditions',[])
            check(isinstance(conditions,list),'ROLE_CONDITIONS')
            constraints={}
            for pred in conditions:
                predicate_valid(pred,role['kinds'],K)
                if pred['field']!='tag':
                    check(pred['field'] not in constraints or constraints[pred['field']]==pred['equals'],'CONTRADICTORY_CONDITIONS')
                    constraints[pred['field']]=pred['equals']
            sel=role.get('selector')
            if sel:
                check(isinstance(sel,dict) and set(sel)=={'anchor','relation','direction','minDepth','maxDepth'} and
                      sel['anchor'] in roles and valid_relation(sel['relation'],K) and
                      sel['direction'] in ('in','out') and type(sel['minDepth']) is int and type(sel['maxDepth']) is int and
                      1<=sel['minDepth']<=sel['maxDepth']<=PATH_LIMIT,'SELECTOR')
                check(compatible_relation(sel['relation'],roles[sel['anchor']]['kinds'],role['kinds'],sel['direction'],K),'RELATION_KIND')
            roles[role['id']]=role
        check('target' in roles and not roles['target'].get('selector') and
              set(roles['target']['kinds'])==set(p['targetKinds']),'TARGET_ROLE')
        check(isinstance(p.get('relations'),list),'RELATIONS')
        for rel in p['relations']:
            check(isinstance(rel,dict) and set(rel)=={'from','to','type'} and
                  rel['from'] in roles and rel['to'] in roles and valid_relation(rel['type'],K),'RELATION_SCHEMA')
            check(compatible_relation(rel['type'],roles[rel['from']]['kinds'],roles[rel['to']]['kinds'],'out',K),'RELATION_KIND')
    else:
        check('roles' not in p and 'relations' not in p,'LEGACY_SCHEMA')
        if p['pattern']=='parentDecisionContext':
            check(p['sourceKinds']==['decision'] and set(p['targetKinds'])<={'requirement','action'},'PARENT_SOURCE_KIND')
    check(isinstance(p['rules'],list) and bool(p['rules']),'RULES')
    ids=set()
    for rule in p['rules']:
        check(isinstance(rule,dict) and {'id','name','watch','operations','enabled'}<=set(rule)<=
              {'id','name','watch','operations','enabled','role','eventType','predicate','whenKinds','memberRole'} and
              K.text(rule['id']) and rule['id'] not in ids and K.text(rule['name']) and
              type(rule['enabled']) is bool and rule['watch'] in WATCHES and
              K.unique_strings(rule['operations']) and bool(rule['operations']),'RULE_SCHEMA')
        ids.add(rule['id'])
        if p['pattern']=='parentDecisionContext':
            check(rule['watch']=='definition' and set(rule['operations'])<={'changed','added','removed'},'CONTEXT_RULE_WATCH')
            continue
        role=rule.get('role','source')
        check(p['pattern']!='roles' or role in roles,'RULE_ROLE')
        kinds=roles[role]['kinds'] if roles else p['sourceKinds']
        if 'whenKinds' in rule:
            check(K.unique_strings(rule['whenKinds']) and bool(rule['whenKinds']) and set(rule['whenKinds'])<=set(kinds),'RULE_KIND_GUARD')
            kinds=rule['whenKinds']
        if 'memberRole' in rule:
            check(p['pattern']=='roles' and rule['memberRole'] in roles and rule['watch'] in ('directScope','context','canon','info','canonInfo','relations'),'RULE_MEMBER_ROLE')
        _,allowed,operations=WATCHES[rule['watch']]
        legacy=p['pattern']=='direct' and rule['watch'] in K.DEPENDENCY_WATCH
        if legacy:
            for kind in kinds:K.validate_dependency_rule({'preset':'custom','watch':[rule['watch']]},kind)
        check((legacy or allowed=='all' or set(kinds)<=set(allowed)) and set(rule['operations'])<=set(operations),'RULE_OPERATION_WATCH')
        if rule['watch']=='structuralScope' and set(kinds)=={'action'}:check('changed' not in rule['operations'],'RULE_OPERATION_WATCH')
        if rule['watch']=='event':check(rule.get('eventType') in K.EVENT_TYPES,'EVENT_TYPE')
        else:check('eventType' not in rule,'EVENT_TYPE')
        if rule['watch']=='predicate':predicate_valid(rule.get('predicate'),kinds,K)
        else:check('predicate' not in rule,'PREDICATE_SCHEMA')
    return p


def validate_catalog(definitions, K):
    check(isinstance(definitions,list),'CATALOG_TYPE');keys=set();versions={}
    for p in definitions:
        validate_definition(p,K);key=(p['id'],p['version'])
        check(key not in keys,'VERSION_DUPLICATE');keys.add(key)
        versions.setdefault(p['id'],[]).append(p['version'])
    for values in versions.values():check(sorted(values)==list(range(1,max(values)+1)),'VERSION_CHAIN')


def _relation_cache(g, K):
    """Only a single read_scope may memoize these *derived* relations.

    BaseContext deliberately omits Finding-derived context. It must not share
    a relation index with the normal Decision kernel for the same Graph.
    The scope ends before any writer mutation; no cross-request global cache.
    """
    analysis = getattr(K, 'ANALYSIS', None)
    cache = analysis.active_read_cache(g) if analysis is not None else None
    if cache is None:
        return None, None
    kernel = getattr(K, 'K', K)
    return cache, ('dependency_relations', kernel, isinstance(K, analysis.BaseContext))


def relations(g, K):
    cache, key = _relation_cache(g, K)
    if cache is not None and key in cache:
        # Never expose the cached relation templates to a caller: those rows
        # are ordinary dictionaries and might otherwise be mutated through an
        # alias. Values are primitive strings (id/type/from/to).
        return [dict(fields) for fields in cache[key]]
    rows=[{'id':e['id'],'type':e['type'],'from':e['from'],'to':e['to']} for e in g['edges']]
    for group in g['decisionGroups']:
        rows.extend({'id':m['id'],'type':'DECISION_MEMBER','from':group['parentId'],'to':m['decisionId']} for m in group['members'])
    for n in K.entities(g).values():
        if n['kind']=='decision':
            rows.extend({'id':'context:'+n['id']+':'+i,'type':'DECISION_CONTEXT','from':i,'to':n['id']}
                        for i in sorted({x['sourceId'] for x in K._context_sources(g,n['id'])}))
        if n['kind']=='finding' and n.get('subjectId') in K.entities(g):
            rows.append({'id':'finding:'+n['id'],'type':'FINDING_SUBJECT','from':n['subjectId'],'to':n['id']})
        if n['kind']=='action':
            rows.extend({'id':'action-target:'+n['id']+':'+i,'type':'ACTION_TARGET','from':n['id'],'to':i} for i in n['targetIds'])
    if cache is not None:
        # Frozen tuples disconnect cache storage from the mutable output.
        cache[key] = tuple(tuple(row.items()) for row in rows)
    return rows


def neighbors(g, K, anchor, typ, direction):
    if isinstance(typ,list):return sorted(set(pair for t in typ for pair in neighbors(g,K,anchor,t,direction)))
    if typ=='SHARED_WORK_GRAPH':
        return [(i,'workGraph:'+w['id']) for w in g['workGraphs'] if anchor in w['memberIds']
                for i in w['memberIds'] if i!=anchor]
    cache, relation_key = _relation_cache(g, K)
    if cache is None:
        a,b=('from','to') if direction=='out' else ('to','from')
        return [(e[b],e['id']) for e in relations(g,K) if e['type']==typ and e[a]==anchor]
    index_key = ('dependency_neighbors', relation_key)
    if index_key not in cache:
        incoming, outgoing = {}, {}
        for edge in relations(g, K):
            outgoing.setdefault((edge['type'], edge['from']), []).append((edge['to'], edge['id']))
            incoming.setdefault((edge['type'], edge['to']), []).append((edge['from'], edge['id']))
        cache[index_key] = (incoming, outgoing)
    by_endpoint = cache[index_key][1 if direction=='out' else 0]
    return list(by_endpoint.get((typ, anchor), ()))


def predicate(g, K, ident, pred):
    node=K.entities(g).get(ident)
    if node is None:return False
    field=pred['field']
    if field=='tag':return pred['equals'] in node.get('tags',[])
    if field=='active':value=ident in K.support_state(g)['activeIds']
    else:
        value=node
        for part in field.split('.'):value=value.get(part) if isinstance(value,dict) else None
    return value==pred['equals']


def resolve(g, p, b, K, trace=None):
    ns=K.entities(g);matched={};paths={};problems=[]
    if p['pattern']!='roles':
        matched={'target':[b['targetId']]}
        if p['pattern']=='direct':matched['source']=[b.get('sourceId')]
        else:
            parent=b.get('parentId');matched['parent']=[parent]
            matched['context']=[x['sourceId'] for x in K._context_sources(g,parent)] if parent in ns else []
            paths[('parent',parent)]=[e['id'] for e in g['edges'] if e['from']==parent and e['to']==b['targetId'] and e['type'] in ('INTRODUCES','REQUIRES_ACTION')]
            if not K._structural_decision_parent(g,parent,b['targetId']):problems.append('PARENT_RELATION_MISSING')
        for role,ids in matched.items():
            if role=='context':continue
            for ident in ids:
                if ident not in ns:problems.append('PARTICIPANT_MISSING:'+str(ident))
        if b['targetId'] in ns and ns[b['targetId']]['kind'] not in p['targetKinds']:problems.append('TARGET_KIND')
        if p['pattern']=='direct' and b.get('sourceId') in ns and ns[b['sourceId']]['kind'] not in p['sourceKinds']:problems.append('SOURCE_KIND')
        return matched,paths,problems
    bindings=b.get('participantBindings',{})
    for role in p['roles']:
        rid=role['id'];sel=role.get('selector');found={};required=role.get('required',not bool(sel))
        if not sel:
            ident=b['targetId'] if rid=='target' else bindings.get(rid)
            if ident in ns:found[ident]=[]
            elif required:problems.append('PARTICIPANT_MISSING:'+rid+':'+str(ident))
        else:
            frontier={i:paths.get((sel['anchor'],i),[]) for i in matched.get(sel['anchor'],[])};seen=set(frontier)
            frontier_nodes={i:set((trace or {}).get((sel['anchor'],i),{}).get('nodeIds',[i])) for i in frontier};found_nodes={}
            for depth in range(1,sel['maxDepth']+1):
                nxt={};nxt_nodes={}
                for anchor,path in frontier.items():
                    for ident,eid in sorted(neighbors(g,K,anchor,sel['relation'],sel['direction'])):
                        if ident in seen:continue
                        nxt[ident]=sorted(set(nxt.get(ident,[])+path+[eid]))
                        nxt_nodes.setdefault(ident,set()).update(frontier_nodes[anchor]|{ident})
                if depth>=sel['minDepth']:
                    found.update(nxt);found_nodes.update(nxt_nodes)
                seen.update(nxt);frontier=nxt;frontier_nodes=nxt_nodes
        found={i:path for i,path in found.items() if ns[i]['kind'] in role['kinds'] and
               all(predicate(g,K,i,pred) for pred in role.get('conditions',[]))}
        matched[rid]=sorted(found)
        paths.update({(rid,i):path for i,path in found.items()})
        if trace is not None:
            trace.update({(rid,i):{'nodeIds':sorted(found_nodes[i]) if sel else [i],'relationIds':path} for i,path in found.items()})
        if required and not found:problems.append('ROLE_EMPTY:'+rid)
    for rel in p['relations']:
        left=matched[rel['from']];right=set(matched[rel['to']])
        if not left or not right or any(not right.intersection(i for i,_ in neighbors(g,K,a,rel['type'],'out')) for a in left):
            problems.append('RELATION_MISSING:'+rel['from']+':'+('/'.join(relation_types(rel['type'])))+':'+rel['to'])
    return matched,paths,sorted(set(problems))


def binding_valid(b, p, K):
    required={'id','policyId','policyVersion','targetId','sourceId','parentId','enabled'}
    check(isinstance(b,dict) and required<=set(b)<=required|{
        'participantBindings','status','reasonCode','revision','disabledAt','disabledEventId',
        'violations','participantSnapshot','relationSnapshot','observedSources'},'BINDING_SCHEMA')
    check(K.text(b['id']) and K.text(b['targetId']) and type(b['enabled']) is bool and
          type(b['policyVersion']) is int and b['policyVersion']>=1 and
          all(v is None or K.text(v) for v in (b['sourceId'],b['parentId'])),'BINDING_SCHEMA')
    check(b.get('status','active' if b['enabled'] else 'disabled') in ('active','disabled','deleted') and
          (b.get('status')!='active' or b['enabled']) and
          (b.get('status') not in ('disabled','deleted') or not b['enabled']),'BINDING_STATE')
    check(type(b.get('revision',1)) is int and b.get('revision',1)>=1,'BINDING_REVISION')
    if 'reasonCode' in b:check(b['reasonCode'] in (None,'manual','applicability','policy','removed'),'BINDING_REASON')
    for field in ('disabledAt','disabledEventId'):
        if field in b:check(K.text(b[field]),'BINDING_HISTORY')
    if 'violations' in b:check(K.unique_strings(b['violations']),'BINDING_VIOLATIONS')
    if 'relationSnapshot' in b:check(K.unique_strings(b['relationSnapshot']),'BINDING_RELATIONS')
    if 'observedSources' in b:
        check(isinstance(b['observedSources'],dict) and all(K.text(r) and isinstance(rows,list) and all(isinstance(n,dict) and set(n)=={'id','kind','title'} and K.text(n['id']) and K.text(n['title']) and n['kind'] in K.ENTITY_KINDS for n in rows) for r,rows in b['observedSources'].items()),'BINDING_OBSERVED_SOURCES')
    if 'participantSnapshot' in b:
        check(isinstance(b['participantSnapshot'],dict) and all(K.text(i) and isinstance(n,dict) and
            set(n)=={'id','kind','title'} and n['id']==i and n['kind'] in K.ENTITY_KINDS and K.text(n['title'])
            for i,n in b['participantSnapshot'].items()),'BINDING_SNAPSHOT')
    if p['pattern']=='roles':
        explicit={r['id'] for r in p['roles'] if not r.get('selector') and r['id']!='target'}
        check(isinstance(b.get('participantBindings'),dict) and set(b['participantBindings'])<=explicit and
              all(K.text(v) for v in b['participantBindings'].values()),'BINDING_ROLES')
    else:check('participantBindings' not in b,'BINDING_ROLES')
    if p['pattern']=='direct':check(b['sourceId'] is not None and b['parentId'] is None and b['sourceId']!=b['targetId'],'BINDING_ENDPOINT')
    if p['pattern']=='parentDecisionContext':check(b['parentId'] is not None and b['sourceId'] is None,'BINDING_PARENT')


def reconcile(before, after, K, event):
    transitions=[];old={b['id']:b for b in before.get('dependencyBindings',[])}
    for b in after.get('dependencyBindings',[]):
        if not b['enabled'] or b.get('status')=='deleted':continue
        p=K._policy_at(after,b['policyId'],b['policyVersion'])
        _,_,problems=resolve(after,p,b,K)
        if p['status']=='disabled':problems=['POLICY_VERSION_DISABLED']+problems
        if not problems:continue
        # New/explicitly activated invalid bindings are rejected, never silently saved disabled.
        check(b['id'] in old and old[b['id']]['enabled'],'BINDING_INAPPLICABLE:'+','.join(problems))
        trace={};roles,paths,_=resolve(before,p,old[b['id']],K,trace)
        participant_ids={i for ids in roles.values() for i in ids}|{i for path in trace.values() for i in path['nodeIds']}
        participants={i:{'id':i,'kind':K.entities(before)[i]['kind'],'title':K.entities(before)[i]['title']}
                      for i in participant_ids if i in K.entities(before)}
        rels={e for values in paths.values() for e in values}
        for rel in p.get('relations',[]):
            for source in roles.get(rel['from'],[]):
                rels.update(eid for target,eid in neighbors(before,K,source,rel['type'],'out') if target in roles.get(rel['to'],[]))
        rels=sorted(rels)
        reason='policy' if p['status']=='disabled' else 'applicability'
        for ident in {i for ids in roles.values() for i in ids}:
            if ident in K.entities(after):K.guard(K.entities(after)[ident],event,'dependency_remove')
        b.update(enabled=False,status='disabled',reasonCode=reason,revision=b.get('revision',1)+1,
                 disabledAt=event['recordedAt'],disabledEventId=event['id'],violations=problems,
                 participantSnapshot=participants,relationSnapshot=rels)
        transitions.append({'bindingId':b['id'],'policyId':p['id'],'policyVersion':p['version'],
            'policyName':p['name'],'from':'active','to':'disabled','reasonCode':reason,
            'violations':problems,'participants':participants,'relations':rels})
    return transitions


def observation(g, ident, rule, K, cosmetic=()):
    ns=K.entities(g);node=ns.get(ident)
    if node is None:return None
    watch=rule['watch']
    if watch=='canonInfo':
        value=K._effective_observable(g,ident,{'watch':['info']},set(cosmetic))
        return K._projection_item_index(value.get('info'),'info') if value else None
    if watch=='membership':return None
    if watch=='predicate':return predicate(g,K,ident,rule['predicate'])
    if watch=='locks':return copy.deepcopy(node.get('locks',[]))
    if watch=='structuralScope':
        return {row['id']:{k:v for k,v in row.items() if k!='endpointDefinition'} for row in K._native_direct_scope(g,ident) if row['type'] in K.STRUCTURAL_KINDS|{'DECISION_GROUP'}}
    if watch=='relations':return {e['id']:e for e in relations(g,K) if ident in (e['from'],e['to'])}
    if watch=='workGraphs':return {w['id']:{'id':w['id']} for w in g['workGraphs'] if ident in w['memberIds']}
    if watch=='rootCauses':return {c['id']:c for c in g['rootCauses'] if c['requirementId']==ident}
    if watch=='info':return {e['id']:{'infoId':e['from'],'definition':K._native_definition(g,e['from'])}
                             for e in g['edges'] if e['type']=='INFO_FOR' and e['to']==ident}
    value=K._effective_observable(g,ident,{'watch':[watch]},set(cosmetic))
    result=value.get(watch) if value else None
    if watch in ('directScope','context','canon'):return K._projection_item_index(result,watch)
    return result


def role_impacts(before, after, p, b, K, cosmetic=(), event=None):
    pre,prepaths,_=resolve(before,p,b,K);post,postpaths,problems=resolve(after,p,b,K)
    if problems or p['status']=='disabled':return []
    rows=[]
    for rule in p['rules']:
        if not rule['enabled']:continue
        role=rule.get('role','source');prior=set(pre.get(role,[]));current=set(post.get(role,[]))
        for source in sorted(prior|current):
            source_node=K.entities(after).get(source) or K.entities(before).get(source)
            if rule.get('whenKinds') and source_node['kind'] not in rule['whenKinds']:continue
            operations=[];watch=rule['watch']
            if source not in prior:operations=[('added',source,None)]
            elif source not in current:operations=[('removed',source,None)]
            elif watch=='event':
                if event and event['type']==rule['eventType'] and source in event['nodeIds']:operations=[('changed',source,None)]
            else:
                old=observation(before,source,rule,K,cosmetic);new=observation(after,source,rule,K,cosmetic)
                if old==new:continue
                if isinstance(old,dict) and isinstance(new,dict) and watch in ('directScope','structuralScope','context','canon','info','canonInfo','relations','workGraphs','rootCauses'):
                    for op,keys in [('added',set(new)-set(old)),('removed',set(old)-set(new)),
                                    ('changed',{i for i in set(old)&set(new) if old[i]!=new[i]})]:
                        for key in sorted(keys):
                            item=new.get(key,old.get(key));member=(item.get('endpoint') or item.get('sourceId') or item.get('canonId') or item.get('infoId') or source)
                            operations.append((op,member,key))
                elif watch=='predicate':
                    op='added' if new else 'removed'
                    operations=[(op if op in rule['operations'] else 'changed',source,None)]
                else:operations=[('changed',source,None)]
            for op,member,relation in operations:
                if op not in rule['operations']:continue
                if rule.get('memberRole') and member not in set(pre.get(rule['memberRole'],[])+post.get(rule['memberRole'],[])):continue
                matched={rid:ids[0] for rid,ids in post.items() if len(ids)==1} if p['pattern']=='roles' else {}
                matched.update(targetId=b['targetId'],sourceId=source)
                if member!=source:matched['memberId']=member
                rels=set(prepaths.get((role,source),[])+postpaths.get((role,source),[]))
                for rel in p.get('relations',[]):
                    rels.update(eid for anchor in pre.get(rel['from'],[])+post.get(rel['from'],[])
                        for graph in (before,after) for neighbor,eid in neighbors(graph,K,anchor,rel['type'],'out')
                        if neighbor in set(pre.get(rel['to'],[])+post.get(rel['to'],[])))
                if relation:rels.add(relation)
                endpoints={source,b['targetId'],member}
                for graph in (before,after):
                    for edge in relations(graph,K):
                        if edge['id'] in rels:endpoints.update((edge['from'],edge['to']))
                if p['pattern']=='roles':
                    for rid in set(pre)|set(post):
                        for ident in sorted(set(pre.get(rid,[])+post.get(rid,[]))&endpoints):
                            if ident not in matched.values():matched[rid+':'+ident]=ident
                rows.append({'edgeId':'binding:'+b['id'],'sourceId':source,'dependentId':b['targetId'],
                    'level':'custom','changedParts':[K.DEPENDENCY_WATCH_PARTS.get(watch,'structure')],
                    'origin':'policy','policyId':p['id'],'policyVersion':p['version'],'policyName':p['name'],
                    'ruleId':rule['id'],'ruleName':rule['name'],'bindingId':b['id'],'triggerOperation':op,
                    'matchedParticipants':matched,'matchedRelations':sorted(rels),
                    'ruleSnapshot':copy.deepcopy(rule),'participantSnapshot':{
                        i:{'id':i,'kind':n['kind'],'title':n['title']} for i in set(matched.values())
                        if (n:=(K.entities(after).get(i) or K.entities(before).get(i)))}})
    return rows


def builtins(K):
    policies=[]
    names={'L1':'L1 · Изменение содержания','L2':'L2 · Содержание и непосредственный состав',
        'decision_state':'Decision · Состояние','decision_context':'Decision · Контекст',
        'decision_canon':'Decision · Канон','canon_criteria':'Canon · Критерии'}
    for key,watches in K.DEPENDENCY_PRESETS.items():
        kinds=['canon'] if key=='canon_criteria' else ['decision'] if key.startswith('decision_') else sorted(K.NODE_KINDS) if key=='L2' else sorted(K.ENTITY_KINDS)
        p={'id':'builtin:'+key,'version':1,'name':names[key],
           'description':'Готовая системная политика. Применяется непосредственно к выбранным участникам.',
           'origin':'system','status':'active','pattern':'direct','sourceKinds':kinds,
           'targetKinds':sorted(K.REVIEW_KINDS),'rules':[{'id':'watch-'+w,'name':WATCHES[w][0],
             'watch':w,'operations':WATCHES[w][2],'enabled':True} for w in watches]}
        policies.append(p)
    for origin,name,source_kinds,types in [
        ('structural','Автоматические структурные зависимости',sorted(K.NODE_KINDS),
         ['DERIVES','DRIVES','INTRODUCES','REQUIRES_ACTION','DECISION_MEMBER','FINDING_RESPONSE','FINDING_PROPOSAL']),
        ('automatic-canon','Автоматическое наблюдение Canon',['canon'],['CANON_FOR']),
        ('finding-subject','Содержание элемента файндинга',sorted(K.NODE_KINDS),['FINDING_SUBJECT'])]:
        target_kinds={'finding'} if origin=='finding-subject' else K.NODE_KINDS
        p={'id':'builtin:'+origin,'version':1,'name':name,'description':'Автоматическое применение по существующим отношениям Graph; без дублирующих DEPENDS_ON.',
           'origin':'system','automatic':True,'status':'active','pattern':'roles','sourceKinds':source_kinds,'targetKinds':sorted(target_kinds),
           'roles':[{'id':'target','kinds':sorted(target_kinds),'required':True},{'id':'source','kinds':source_kinds,'required':True}],
           'relations':[{'from':'source','to':'target','type':types}],
           'rules':[{'id':'definition','name':'Изменение содержания источника','role':'source','watch':'definition','operations':['changed'],'enabled':True}]}
        if origin=='structural':
            p['roles'].append({'id':'context','kinds':['requirement','decision','action','context','finding'],'required':False,
                'selector':{'anchor':'source','relation':'DECISION_CONTEXT','direction':'in','minDepth':1,'maxDepth':1}})
            p['rules'].extend([
                {'id':'context-content','name':'Изменились наблюдаемые данные элемента контекста родителя','role':'source','watch':'context','whenKinds':['decision'],'operations':['changed'],'enabled':True},
                {'id':'context-membership','name':'Участник добавлен в контекст родителя или исключён из него','role':'source','watch':'context','whenKinds':['decision'],'operations':['added','removed'],'enabled':True},
                {'id':'parent-withdrawn','name':'Снятие выбора родительского Decision','role':'source','watch':'event','whenKinds':['decision'],'eventType':'decision_unselected','operations':['changed'],'enabled':True}])
        if origin=='automatic-canon':p['rules'].append({'id':'canon-attached','name':'Canon привязан к оцениваемому блоку','role':'target','watch':'canon','memberRole':'source','operations':['added'],'enabled':True})
        policies.append(p)
    types=['DERIVES','DRIVES','INTRODUCES','REQUIRES_ACTION','DECISION_MEMBER','FINDING_RESPONSE','FINDING_PROPOSAL']
    policies.append({'id':'builtin:structural-topology','version':1,'name':'Изменение структурного состава',
        'description':'Наблюдает непосредственные структурные отношения и свойства Decision Groups. Пустой набор отношений допустим; это отдельная причина от изменения содержания родителя.',
        'origin':'system','automatic':True,'status':'active','pattern':'roles','sourceKinds':sorted(K.NODE_KINDS),'targetKinds':sorted(K.NODE_KINDS),
        'roles':[{'id':'target','kinds':sorted(K.NODE_KINDS),'required':True},
            {'id':'parents','kinds':['requirement','decision'],'required':False,'selector':{'anchor':'target','relation':types,'direction':'in','minDepth':1,'maxDepth':1}},
            {'id':'children','kinds':sorted(K.NODE_KINDS),'required':False,'selector':{'anchor':'target','relation':types,'direction':'out','minDepth':1,'maxDepth':1}}],
        'relations':[],'rules':[{'id':'structural-membership','name':'Изменение непосредственного структурного состава',
            'role':'target','watch':'structuralScope','operations':['added','removed','changed'],'enabled':True}]})
    for policy in policies:
        help=POLICY_HELP[policy['id']];policy['name']=help['name'];policy['description']=help['description']
    return policies


def automatic_key(row):
    return 'automatic:'+digest([row['origin'],row['sourceId'],row['dependentId']])[:32]


def automatic_policy_id(origin):
    return {'structural':'builtin:structural','canon':'builtin:automatic-canon','structural-topology':'builtin:structural-topology','finding-subject':'builtin:finding-subject'}[origin]


def automatic_matches(g,K):
    result={automatic_key(r):r for r in K._subscriptions(g).values() if r['origin'] in ('structural','canon','finding-subject')}
    for node in g['nodes']+g['externalActions']:
        if node.get('lowLevel'):continue
        row={'id':'topology:'+node['id'],'origin':'structural-topology','sourceId':node['id'],'dependentId':node['id']}
        result[automatic_key(row)]=row
    return result


def impact_automatic_key(row):
    if row.get('origin')=='structural' and 'structure' in row['changedParts']:
        return automatic_key({'origin':'structural-topology','sourceId':row['dependentId'],'dependentId':row['dependentId']})
    return automatic_key(row)


def explain_automatic(rows,before,after,K,cosmetic=()):
    result=[]
    def record(row,origin,rule_id,operation='changed',member=None,relation=None):
        policy=next(p for p in builtins(K) if p['id']==automatic_policy_id(origin))
        rule=next(r for r in policy['rules'] if r['id']==rule_id)
        target=row['dependentId'];parent=row['sourceId']
        key=(automatic_key({'origin':origin,'sourceId':target,'dependentId':target})
             if origin=='structural-topology' else automatic_key(row))
        if after.get('dependencyAutomaticStates',{}).get(key,{}).get('status','active')!='active':return
        source=member or parent
        participants={'sourceId':source,'targetId':target}
        rels={row['edgeId'].removeprefix('owner:')}
        if member is not None:
            participants.update(parentId=parent,contextId=member)
            for graph in (before,after):
                rels.update(e['id'] for e in relations(graph,K) if e['type']=='DECISION_CONTEXT' and e['from']==member and e['to']==parent)
                rels.update(e['id'] for e in graph['edges'] if e['type']=='DEPENDS_ON' and e.get('dependencyPurpose')=='decisionContext' and e['from']==member and e['to']==parent)
        if relation:rels.add(relation)
        hit={**row,'sourceId':source,'policyId':policy['id'],'policyVersion':policy['version'],
            'policyName':policy['name'],'ruleId':rule['id'],'ruleName':rule['name'],'bindingId':key,
            'triggerOperation':operation,'matchedParticipants':participants,'matchedRelations':sorted(rels),
            'ruleSnapshot':copy.deepcopy(rule),'participantSnapshot':{
                i:{'id':i,'kind':n['kind'],'title':n['title']} for i in set(participants.values())
                if (n:=(K.entities(after).get(i) or K.entities(before).get(i)))}}
        result.append(hit)
    for row in rows:
        origin=row.get('origin')
        if origin=='finding-subject':
            record(row,origin,'definition');continue
        if origin not in ('structural','canon'):result.append(row);continue
        if origin=='canon':
            record(row,origin,'canon-attached' if 'structure' in row['changedParts'] else 'definition',
                   'added' if 'structure' in row['changedParts'] else 'changed')
            continue
        parts=set(row['changedParts'])
        if 'structure' in parts:
            rid=row['edgeId'].removeprefix('owner:')
            was=any(e['id']==rid for e in relations(before,K));now=any(e['id']==rid for e in relations(after,K))
            operation=('added' if now else 'removed') if was!=now else 'changed'
            record({**row,'changedParts':['structure']},'structural-topology','structural-membership',operation)
        if 'context' in parts:
            for operation,member,relation in K._policy_part_differences(before,after,row['sourceId'],'context',cosmetic):
                record({**row,'changedParts':['context']},'structural',
                    'context-content' if operation=='changed' else 'context-membership',operation,member,relation)
        if 'basis' in parts:record({**row,'changedParts':['basis']},'structural','parent-withdrawn')
        remaining=parts-{'structure','context','basis'}
        if remaining:record({**row,'changedParts':sorted(remaining)},'structural','definition')
    return result


def reconcile_automatic(before,after,K,event):
    prior=automatic_matches(before,K);current=automatic_matches(after,K)
    states=after.setdefault('dependencyAutomaticStates',{})
    transitions=[]
    for key,row in sorted(prior.items()):
        if key in current or states.get(key,{}).get('status') in ('disabled','deleted'):continue
        participants={i:{'id':i,'kind':K.entities(before)[i]['kind'],'title':K.entities(before)[i]['title']}
                      for i in (row['sourceId'],row['dependentId']) if i in K.entities(before)}
        state={'id':key,'sourceId':row['sourceId'],'targetId':row['dependentId'],'origin':row['origin'],
               'status':'disabled','reasonCode':'applicability','revision':states.get(key,{}).get('revision',0)+1,
               'disabledEventId':event['id'],'disabledAt':event['recordedAt'],
               'participantSnapshot':participants,'violations':(['PARTICIPANT_MISSING:'+i for i in sorted({row['sourceId'],row['dependentId']}) if i not in K.entities(after)] or ['AUTOMATIC_RELATION_MISSING'])}
        for ident in (row['sourceId'],row['dependentId']):
            if ident in K.entities(after):K.guard(K.entities(after)[ident],event,'dependency_remove')
        states[key]=state
        transitions.append({'bindingId':key,'policyId':automatic_policy_id(row['origin']),
            'policyVersion':1,'policyName':next(p['name'] for p in builtins(K) if p['id']==automatic_policy_id(row['origin'])),
            'from':'active','to':'disabled','reasonCode':'applicability','violations':state['violations'],
            'participants':participants,'relations':[] if row['origin']=='structural-topology' else [row['id']]})
    return transitions


def lifecycle_transitions(before,after,K,already):
    recorded={r['bindingId'] for r in already};prior={b['id']:b for b in before.get('dependencyBindings',[])};rows=[]
    for b in after.get('dependencyBindings',[]):
        old=prior.get(b['id'])
        if not old or b['id'] in recorded:continue
        old_state=old.get('status','active' if old['enabled'] else 'disabled')
        new_state=b.get('status','active' if b['enabled'] else 'disabled')
        if old_state==new_state:continue
        p=K._policy_at(after,b['policyId'],b['policyVersion'])
        rows.append({'bindingId':b['id'],'policyId':p['id'],'policyVersion':p['version'],'policyName':p['name'],
            'from':old_state,'to':new_state,'reasonCode':b.get('reasonCode'),
            'violations':[],'participants':b.get('participantSnapshot',{}),'relations':b.get('relationSnapshot',[])})
    previous=before.get('dependencyAutomaticStates',{});matches=automatic_matches(before,K)
    for key,state in after.get('dependencyAutomaticStates',{}).items():
        if key in recorded:continue
        old=previous.get(key,{});old_status=old.get('status','active' if key in matches else None)
        if old_status is None or old_status==state['status']:continue
        policy=next(p for p in builtins(K) if p['id']==automatic_policy_id(state['origin']))
        participants={i:{'id':i,'kind':node['kind'],'title':node['title']} for i in {state['sourceId'],state['targetId']}
            if (node:=(K.entities(after).get(i) or K.entities(before).get(i)))}
        rows.append({'bindingId':key,'policyId':policy['id'],'policyVersion':1,'policyName':policy['name'],
            'from':old_status,'to':state['status'],'reasonCode':state.get('reasonCode'),
            'violations':[],'participants':participants,'relations':[]})
    return rows



def describe_applications(g, K):
    analysis = getattr(K, 'ANALYSIS', None)
    with analysis.read_scope(g) if analysis is not None else nullcontext():
        return _describe_applications(g, K)


def _describe_applications(g, K):
    """Read-only current-Graph details from the execution resolver, including latches.

    A path is a witness graph, not an invented ordered path: execution can merge
    several paths to the same participant. Removed facts keep only recorded IDs.
    """
    ns=K.entities(g);edges={e['id']:e for e in relations(g,K)};result=[]
    definitions={p['id']:p for p in builtins(K)};cache={}
    def entity_ids(value):
        found=set()
        if isinstance(value,dict):
            for key,item in value.items():
                if key in ('id','endpoint','sourceId','canonId','infoId','contextId','from','to','requirementId') and isinstance(item,str) and item in ns:found.add(item)
                if isinstance(item,(dict,list)):found.update(entity_ids(item))
        elif isinstance(value,list):
            for item in value:found.update(entity_ids(item))
        return found
    def witness_ids(value,owner=None):
        found=set()
        if isinstance(value,dict):
            if value.get('sourceId') in ns:owner=value['sourceId']
            if value.get('type')=='DECISION_CONTEXT' and owner:
                found.update(e['id'] for e in edges.values() if e['type']=='DECISION_CONTEXT' and e['from']==value.get('endpoint') and e['to']==owner)
            if value.get('type')=='DECISION_GROUP':
                group=next((group for group in g['decisionGroups'] if group['id']==value.get('id')),None)
                if group:found.update(member['id'] for member in group['members'])
            for key,item in value.items():
                if key in edges:found.add(key)
                if key in ('id','edgeId') and isinstance(item,str) and item in edges:found.add(item)
                if isinstance(item,(dict,list)):found.update(witness_ids(item,owner))
        elif isinstance(value,list):
            for item in value:found.update(witness_ids(item,owner))
        return found
    def add(p,b,kind,edge=None,context=False,matched=True):
        p=copy.deepcopy(p);b=copy.deepcopy(b);trace={}
        resolved,paths,problems=resolve(g,p,b,K,trace)
        if kind=='automatic' and not matched:problems=sorted(set(problems+['AUTOMATIC_RELATION_MISSING']))
        if p['status']=='disabled':problems=sorted(set(problems+['POLICY_VERSION_DISABLED']))
        if p['pattern']=='roles':role_specs=p['roles']
        else:
            role_specs=[{'id':'target','name':'Зависимый элемент','kinds':p['targetKinds']},
                {'id':'source' if p['pattern']=='direct' else 'parent','name':'Источник изменений' if p['pattern']=='direct' else 'Родительский Decision','kinds':p['sourceKinds']}]
            if p['pattern']=='parentDecisionContext':
                role_specs.append({'id':'context','name':'Элементы контекста родителя','kinds':['requirement','decision','action','context'],
                    'required':False,'selector':{'anchor':'parent','relation':'DECISION_CONTEXT','direction':'in','minDepth':1,'maxDepth':1}})
                for ident in resolved.get('context',[]):
                    paths[('context',ident)]=[e['id'] for e in edges.values() if e['type']=='DECISION_CONTEXT' and e['from']==ident and e['to']==b['parentId']]
        configured={'target':b['targetId']}
        if p['pattern']=='roles':configured.update(b.get('participantBindings',{}))
        else:configured['source' if p['pattern']=='direct' else 'parent']=b.get('sourceId') or b.get('parentId')
        roles=[{**copy.deepcopy(role),'ids':resolved.get(role['id'],[]),'configuredId':configured.get(role['id'])} for role in role_specs]
        relation_ids={i for ids in paths.values() for i in ids}
        if edge:relation_ids.add(edge['id'])
        for rel in p.get('relations',[]):
            for source in resolved.get(rel['from'],[]):
                relation_ids.update(eid for target,eid in neighbors(g,K,source,rel['type'],'out') if target in resolved.get(rel['to'],[]))
        historical=b.get('participantSnapshot',{}) if not b.get('enabled',b.get('status','active')=='active') else {}
        historical_relations=set(b.get('relationSnapshot',[])) if historical else set()
        relevant={i for ids in resolved.values() for i in ids}|set(filter(None,configured.values()))|set(historical)
        for item in trace.values():relevant.update(item['nodeIds'])
        rule_rows=[];observed_ids=set();observation_paths=[]
        for rule in p['rules']:
            role=rule.get('role','context' if p['pattern']=='parentDecisionContext' else 'source')
            # Legacy parent-context rules watch the members, not the parent.
            actors=list(resolved.get(role,[]));configured_actor=configured.get(role)
            if not b.get('enabled',b.get('status','active')=='active') and configured_actor and configured_actor not in actors:actors.append(configured_actor)
            actors=[i for i in actors if i in ns and (not rule.get('whenKinds') or ns[i]['kind'] in rule['whenKinds'])]
            members=set();resolved_observations=[]
            if rule['enabled']:
                observed_ids.update(actors)
                for source in actors:
                    key=(source,p['pattern']=='direct',json.dumps(rule,sort_keys=True))
                    if key not in cache:
                        if p['pattern']=='direct' and rule['watch'] in K.DEPENDENCY_WATCH:
                            cache[key]=K._effective_observable(g,source,{'watch':[rule['watch']]},set())
                        else:cache[key]=observation(g,source,rule,K)
                    value=cache[key]
                    if rule.get('memberRole') and isinstance(value,dict):
                        allowed=set(resolved.get(rule['memberRole'],[]))
                        value={key:item for key,item in value.items() if isinstance(item,dict) and (item.get('endpoint') or item.get('sourceId') or item.get('canonId') or item.get('infoId') or source) in allowed}
                    members.update(entity_ids(value));witnesses=witness_ids(value,source)
                    if rule['watch']=='context':
                        member_ids=entity_ids(value)
                        witnesses.update(e['id'] for e in edges.values() if e['from'] in member_ids and e['to']==source and
                            (e['type']=='DECISION_CONTEXT' or e['type']=='DEPENDS_ON' and e.get('dependencyPurpose')=='decisionContext'))
                    if (rule['watch']=='canonInfo' or p['pattern']=='direct' and rule['watch']=='info') and ns[source]['kind']=='decision':
                        witnesses.update(e['id'] for e in edges.values() if e['type']=='CANON_FOR' and e['to']==source)
                    context_sources=[]
                    if rule['watch']=='context':
                        context_value=value.get('context',[]) if p['pattern']=='direct' and isinstance(value,dict) else value
                        for item in (context_value.values() if isinstance(context_value,dict) else context_value or []):
                            if not isinstance(item,dict) or item.get('sourceId') not in ns:continue
                            observed=item.get('projection') or {}
                            context_sources.append({'sourceId':item['sourceId'],'preset':item.get('rule',{}).get('preset'),
                                'watches':['canonInfo' if watch=='info' else watch for watch,projection in observed.items() if projection is not None],
                                'memberIds':sorted(entity_ids(observed)-{item['sourceId']})})
                    resolved_observations.append({'actorId':source,'memberIds':sorted(entity_ids(value)-{source}),
                        'relationIds':sorted(witnesses),'contextSources':context_sources,
                        'workGraphs':[{'id':area['id'],'title':area['title']} for area in g['workGraphs'] if source in area['memberIds']] if rule['watch']=='workGraphs' else [],
                        'predicateValue':predicate(g,K,source,rule['predicate']) if rule['watch']=='predicate' else None})
                    if witnesses:
                        relation_ids.update(witnesses)
                        nodes={source}|{endpoint for ident in witnesses for endpoint in (edges[ident]['from'],edges[ident]['to'])}
                        relevant.update(nodes)
                        observation_paths.append({'kind':'observation','role':role,'ruleId':rule['id'],'watch':'canonInfo' if p['pattern']=='direct' and rule['watch']=='info' else rule['watch'],
                            'participantId':source,'relationIds':sorted(witnesses),'nodeIds':sorted(nodes)})
                observed_ids.update(members)
            rule_rows.append({**copy.deepcopy(rule),'role':role,'actorIds':sorted(actors),'memberIds':sorted(members-set(actors)),
                'displayWatch':'canonInfo' if p['pattern']=='direct' and rule['watch']=='info' else rule['watch'],'observations':resolved_observations})
        relation_rows=[]
        for ident in sorted(relation_ids|historical_relations):
            if ident in edges:
                row={**copy.deepcopy(edges[ident]),'present':True,'historicalOnly':ident not in relation_ids}
                relevant.update((row['from'],row['to']))
            elif ident.startswith('workGraph:'):
                area=next((w for w in g['workGraphs'] if 'workGraph:'+w['id']==ident),None)
                row={'id':ident,'type':'SHARED_WORK_GRAPH','present':area is not None,'workGraphId':area['id'] if area else ident.removeprefix('workGraph:'),'title':area['title'] if area else None,'historicalOnly':ident not in relation_ids}
            else:row={'id':ident,'present':False,'historicalOnly':ident in historical_relations}
            relation_rows.append(row)
        relevant.update(observed_ids)
        participants={}
        for ident in sorted(relevant):
            n=ns.get(ident) or historical.get(ident)
            participants[ident]={'id':ident,'kind':n.get('kind') if n else None,'title':n.get('title',ident) if n else ident,'present':ident in ns,'recorded':ident in historical}
        status=b.get('status','active' if b.get('enabled',True) else 'disabled')
        result.append({'id':b['id'],'kind':kind,'policyId':p['id'],'policyVersion':p['version'],
            'policy':p,'binding':b,'targetId':b['targetId'],'status':status,'enabled':status=='active',
            'reasonCode':b.get('reasonCode'),'violations':copy.deepcopy(b.get('violations',[])),
            'currentViolations':problems,'applicable':not problems,'roles':roles,'participants':participants,
            'nodeIds':sorted(relevant),'observedIds':sorted(observed_ids),'relations':relation_rows,
            'paths':[{'role':role,'participantId':ident,'relationIds':ids,'nodeIds':trace.get((role,ident),{}).get('nodeIds',[])} for (role,ident),ids in sorted(paths.items()) if ids]+observation_paths,
            'rules':rule_rows,'legacyEdgeId':edge['id'] if edge and kind=='legacy' else None,
            'legacyContextId':b['sourceId'] if kind=='legacy-context' else None,'decisionContext':context})
    for b in g.get('dependencyBindings',[]):
        if b.get('status')=='deleted':continue
        p=K._policy_at(g,b['policyId'],b['policyVersion'])
        if p:add(p,b,'policy')
    matches=automatic_matches(g,K);states=g.get('dependencyAutomaticStates',{})
    for key in sorted(set(matches)|set(states)):
        match=matches.get(key);state=states.get(key,{})
        if state.get('status')=='deleted':continue
        origin=match['origin'] if match else state['origin']
        source=match['sourceId'] if match else state['sourceId'];target=match['dependentId'] if match else state['targetId']
        p=definitions[automatic_policy_id(origin)]
        b={**copy.deepcopy(state),'id':key,'sourceId':source,'targetId':target,'parentId':None,
            'policyId':p['id'],'policyVersion':p['version'],'enabled':state.get('status','active')=='active',
            'status':state.get('status','active'),'revision':state.get('revision',1),'participantBindings':{'source':source}}
        add(p,b,'automatic',matched=match is not None)
    for row in K._subscriptions(g).values():
        if row['origin'] not in ('manual','decisionContext'):continue
        rule=row['rule'];preset=rule['preset'];p=copy.deepcopy(definitions.get('builtin:'+preset,definitions['builtin:L1']))
        if preset=='custom':p.update(id='legacy:custom',name='Индивидуальные наблюдения прямой зависимости')
        p['rules']=[{'id':'watch-'+watch,'name':WATCH_HELP['canonInfo' if watch=='info' else watch][0],
            'watch':watch,'operations':WATCHES[watch][2],'enabled':True} for watch in rule['watch']]
        p['sourceKinds']=[ns[row['sourceId']]['kind']];p['targetKinds']=[ns[row['dependentId']]['kind']]
        edge=next((edge for edge in g['edges'] if edge['id']==row['id']),None);context=row['origin']=='decisionContext' or bool(edge and edge.get('dependencyPurpose')=='decisionContext')
        b={'id':row['id'],'policyId':p['id'],'policyVersion':1,'sourceId':row['sourceId'],'targetId':row['dependentId'],'parentId':None,'enabled':True,'status':'active'}
        add(p,b,'legacy-context' if row['origin']=='decisionContext' else 'legacy',edge,context)
    return sorted(result,key=lambda row:(row['policy']['name'],row['id']))


def transition_evidence(before, after, K, transitions):
    """Record event-time participants and roles once, inside the existing writer."""
    old={b['id']:b for b in before.get('dependencyBindings',[])}
    new={b['id']:b for b in after.get('dependencyBindings',[])}
    for item in transitions:
        ident=item['bindingId'];snapshot=before if item['to']=='disabled' and item['reasonCode']=='applicability' else after
        binding=(old.get(ident) if snapshot is before else new.get(ident)) or new.get(ident) or old.get(ident)
        if binding is None:
            state=after.get('dependencyAutomaticStates',{}).get(ident) or before.get('dependencyAutomaticStates',{}).get(ident)
            if not state:continue
            binding={'targetId':state['targetId'],'sourceId':state['sourceId'],'parentId':None,'participantBindings':{'source':state['sourceId']}}
        policy=K._policy_at(snapshot,item['policyId'],item['policyVersion']) or K._policy_at(after,item['policyId'],item['policyVersion'])
        if not policy:continue
        trace={};roles,paths,_=resolve(snapshot,policy,binding,K,trace)
        roles.setdefault('target',[])
        if binding['targetId'] not in roles['target']:roles['target'].append(binding['targetId'])
        configured=binding.get('participantBindings',{}) if policy['pattern']=='roles' else {('source' if policy['pattern']=='direct' else 'parent'):binding.get('sourceId') or binding.get('parentId')}
        for role,node in configured.items():
            if node and node not in roles.setdefault(role,[]):roles[role].append(node)
        ids={i for values in roles.values() for i in values}|{i for path in trace.values() for i in path['nodeIds']}
        ns=K.entities(snapshot);participants=copy.deepcopy(item['participants'])
        for ident in ids:
            if ident in ns:participants[ident]={k:ns[ident][k] for k in ('id','kind','title')}
        rel_ids=set(item['relations'])|{i for values in paths.values() for i in values}
        for rel in policy.get('relations',[]):
            for source in roles.get(rel['from'],[]):
                rel_ids.update(eid for target,eid in neighbors(snapshot,K,source,rel['type'],'out') if target in roles.get(rel['to'],[]))
        item.update(targetId=binding['targetId'],participants=participants,
                    participantRoles={r:sorted(set(ids)) for r,ids in roles.items()},relations=sorted(rel_ids),
                    relationSnapshot=[copy.deepcopy(r) for r in relations(snapshot,K) if r['id'] in rel_ids])


def describe_invalidation(g, K, applications=None):
    """Read-only list of recorded review causes and disable cycles, never a second evaluator.

    Current applicability comes only from describe_applications/resolve. Historical
    facts come only from Graph events; unknown legacy detail remains unknown.
    """
    applications=describe_applications(g,K) if applications is None else applications
    current={r['id']:r for r in applications};ns=K.entities(g)
    active=set(K.support_state(g)['activeIds']);events={e['id']:e for e in g['events']};order={e['id']:i for i,e in enumerate(g['events'])}
    resolutions={};cause_targets={}
    for event in g['events']:
        for resolved in event.get('reviewResolutions',[]):
            for cause in resolved['causeEventIds']:
                resolutions[(resolved['nodeId'],cause)]=event
                cause_targets.setdefault(cause,set()).add(resolved['nodeId'])
    for ident,node in ns.items():
        for cause in node.get('review',{}).get('causeEventIds',[]):cause_targets.setdefault(cause,set()).add(ident)
    for event in g['events']:
        for hit in event.get('dependencyImpacts',[]):cause_targets.setdefault(event['id'],set()).add(hit['dependentId'])
    records=[];groups={}
    for cause,targets in cause_targets.items():
        event=events.get(cause)
        for target in sorted(targets):
            node=ns.get(target);is_current=bool(node and node.get('review',{}).get('required') and cause in node['review']['causeEventIds'])
            resolution=resolutions.get((target,cause))
            # A later review does not close an event that is still explicitly a current cause.
            if is_current:resolution=None
            key=('review',target,'active' if is_current else resolution['id'] if resolution else cause)
            if key not in groups:
                group={'id':':'.join(key),'kind':'review','targetId':target,'active':is_current,
                    'structurallyActive':target in active,'targetPresent':node is not None,'causes':[],
                    'resolution':'reviewed' if resolution else 'targetRemoved' if node is None else 'historical',
                    'resolvedEventId':resolution['id'] if resolution else None,
                    'resolvedAt':resolution['recordedAt'] if resolution else None,
                    'participants':{},'policyVersions':[],'nodeIds':[target],'eventOrder':order.get(cause,-1)}
                groups[key]=group;records.append(group)
            group=groups[key];hits=[copy.deepcopy(h) for h in event.get('dependencyImpacts',[]) if h['dependentId']==target] if event else []
            group['causes'].append({'eventId':cause,'recordedAt':event.get('recordedAt') if event else None,
                'eventType':event.get('type') if event else None,'basis':event.get('basis') if event else None,'hits':hits})
            group['eventOrder']=max(group['eventOrder'],order.get(cause,-1))
            for hit in hits:
                group['participants'].update(copy.deepcopy(hit.get('participantSnapshot',{})))
                group['nodeIds'].extend([hit['sourceId'],hit['dependentId'],*hit.get('viaIds',[]),*hit.get('matchedParticipants',{}).values()])
                if hit.get('policyId') and hit.get('policyVersion'):group['policyVersions'].append([hit['policyId'],hit['policyVersion']])
    disabled_cycles={};latest={}
    for event in g['events']:
        for index,transition in enumerate(event.get('dependencyTransitions',[])):
            binding=transition['bindingId'];latest[binding]=(event,transition)
            if transition['to']=='disabled':
                # Repeated disabled checks are not new lifecycle cycles.
                if binding in disabled_cycles:continue
                target=transition.get('targetId');record={'id':'disabled:'+binding+':'+event['id']+':'+str(index),
                    'kind':'disabled','bindingId':binding,'targetId':target,'targetRecorded':bool(target),
                    'active':False,'policyId':transition['policyId'],'policyVersion':transition['policyVersion'],
                    'policyName':transition['policyName'],'policyVersions':[[transition['policyId'],transition['policyVersion']]],
                    'reasonCode':transition['reasonCode'],'violations':copy.deepcopy(transition['violations']),
                    'participants':copy.deepcopy(transition['participants']),'participantRoles':copy.deepcopy(transition.get('participantRoles',{})),
                    'relations':copy.deepcopy(transition['relations']),'relationSnapshot':copy.deepcopy(transition.get('relationSnapshot',[])),
                    'eventId':event['id'],'recordedAt':event['recordedAt'],'eventOrder':order[event['id']],
                    'resolvedEventId':None,'resolvedAt':None,'resolution':None}
                records.append(record);disabled_cycles[binding]=record
            elif binding in disabled_cycles:
                record=disabled_cycles.pop(binding);record.update(resolution='activated' if transition['to']=='active' else 'deleted',
                    resolvedEventId=event['id'],resolvedAt=event['recordedAt'])
    for binding,record in disabled_cycles.items():
        app=current.get(binding)
        record['active']=bool(app and not app['enabled'])
        if not record['active'] and not record['resolution']:record['resolution']='historical'
        if app and not record['targetId']:record['targetId']=app['targetId']
    for ident,app in current.items():
        if app['enabled']:continue
        record=disabled_cycles.get(ident)
        if record is None:
            # Legacy latch with no recorded transition: no fabricated event/time.
            record={'id':'disabled:'+ident+':unrecorded','kind':'disabled','bindingId':ident,
                'targetId':app['targetId'],'targetRecorded':False,'active':True,
                'policyId':app['policyId'],'policyVersion':app['policyVersion'],'policyName':app['policy']['name'],
                'policyVersions':[[app['policyId'],app['policyVersion']]],'reasonCode':app['reasonCode'],
                'violations':copy.deepcopy(app['violations']),'participants':copy.deepcopy(app['binding'].get('participantSnapshot',{})),
                'participantRoles':{},'relations':copy.deepcopy(app['binding'].get('relationSnapshot',[])),
                'relationSnapshot':[],'eventId':None,'recordedAt':None,'eventOrder':-1,
                'resolvedEventId':None,'resolvedAt':None,'resolution':None}
            records.append(record)
        record.update(applicationKind=app['kind'],applicable=app['applicable'],
            currentViolations=copy.deepcopy(app['currentViolations']),currentTargetId=app['targetId'],
            currentPolicyId=app['policyId'],currentPolicyVersion=app['policyVersion'],
            bindingRevision=app['binding'].get('revision',1))
    for record in records:
        ids=set(record.get('nodeIds',[]))|set(record['participants'])|{record.get('targetId')}
        if record['kind']=='disabled':
            ids.update(i for values in record.get('participantRoles',{}).values() for i in values)
            app=current.get(record['bindingId'])
            if record['active'] and app:ids.update(app['nodeIds'])
        record['nodeIds']=sorted(i for i in ids if i)
        for ident in record['nodeIds']:
            saved=record['participants'].get(ident);node=ns.get(ident)
            record['participants'][ident]={**(copy.deepcopy(saved) if saved else {'id':ident,'kind':node['kind'] if node else None,'title':node['title'] if node else ident}),
                'present':node is not None,'recorded':saved is not None}
        record['policyVersions']=[list(pair) for pair in sorted({tuple(pair) for pair in record['policyVersions']})]
    return sorted(records,key=lambda r:(not r['active'],-r['eventOrder'],r['id']))
