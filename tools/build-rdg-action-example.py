#!/usr/bin/env python3
"""Rebuild a synthetic read-only Action example through isolated real writers.

Uses temporary test owners and grants, never the project's workspace or grants.
The exported workflow is an illustrative snapshot, not a live Helper session.
"""
from importlib.machinery import SourceFileLoader
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = SourceFileLoader("action_example_fixture", str(ROOT/"tests/rdg-workflow.acceptance.test.py")).load_module()
WF = SourceFileLoader("action_example_workflow", str(ROOT/"tools/rdg-workflow.py")).load_module()
SLUG = "reference-action-time-plan"
FILE = "examples/"+SLUG+"/graph.json"

def build():
    f=FIX.Workflow("test_whole_future_execution_withdrawal_new_variant_and_history")
    original_create=FIX.DEEP.DeepAction.create
    def create_with_title(self,graph=None,tid="create"):
        graph=copy.deepcopy(graph or self.graph)
        graph["nodes"][0]["title"]="Обеспечить надёжное оформление заявки"
        return original_create(self,graph,tid)
    FIX.DEEP.DeepAction.create=create_with_title
    try:
        f.setUp()
    finally:
        FIX.DEEP.DeepAction.create=original_create
    try:
        w=f.w
        original_event=w.event
        def teaching_event(kind,**rest):
            event=original_event(kind,**rest)
            event["note"]={"action_selected":"Учебный выбор способа для существующей цели",
                "graph_changed":"Учебное изменение структуры или материала графа"}.get(kind,"Учебная запись результата")
            return event
        w.event=teaching_event
        def action(aid,rid,title,positive,negative,typ="general"):
            op=w.add(aid,rid,typ);n=op["action"];n["title"]=title
            n["canonBlock"]={"recommended":[{"id":"C-"+aid+"-PLUS","text":positive}],
                "contraindicated":[{"id":"C-"+aid+"-MINUS","text":negative}]}
            n["qrpe"]=[{"id":"Q-"+aid,"text":"Подтверждены ли условия применения способа в этом учебном контексте?","status":"open"}]
            return op
        def prepare(aid,rid,title,role="subgoal"):
            op=w.prepare(aid,rid,role);op["node"]["title"]=title;return op
        def result(nid,note,act=False):
            op=w.result(nid,act);op["event"]["note"]=note;return op
        w.apply([action("A-SPLIT","R0","Разделить оформление на ввод и подтверждение",
                "Ввод можно сохранять отдельно, а отправку подтверждает сервер; границы двух результатов известны.",
                "Ввод и подтверждение должны совершаться одной неделимой операцией; такое разбиение не обеспечит атомарность.","decomposition"),
            prepare("A-SPLIT","R-INPUT","Сохранить введённую заявку при разрыве связи"),
            prepare("A-SPLIT","R-SEND","Подтвердить приём заявки ровно один раз"),
            prepare("A-SPLIT","R-CHECK","Проверить полноту границ ввода и подтверждения","method_correctness"),
            action("A-ATOMIC","R0","Оформлять заявку одной серверной транзакцией",
                "Постоянная связь гарантирована, и сервер может атомарно принять все данные.",
                "Пользователь работает без устойчивой связи; потеря формы недопустима.")])
        w.apply([w.choose("A-SPLIT")])
        w.apply([result("R-CHECK","На учебных сценариях проверены сохранение ввода, повтор отправки и получение подтверждения. Границы разбиения согласованы.")])
        assert w.states()["A-SPLIT"]["complete"] and not w.states()["R0"]["complete"]
        w.apply([
            action("A-LOCAL","R-INPUT","Сохранять черновик в локальном хранилище",
                "Устройство личное, объём небольшой, локальное хранение разрешено политикой данных.",
                "Устройство общее или локальное хранение чувствительных данных запрещено."),
            action("A-SERVER","R-INPUT","Сохранять черновик на сервере по мере ввода",
                "Связь доступна хотя бы периодически; черновик нужен на нескольких устройствах.",
                "Связи нет до завершения ввода, а ввод нельзя потерять даже при закрытии страницы."),
            action("A-IDEMPOTENT","R-SEND","Отправлять заявку с ключом идемпотентности",
                "Сервер хранит результат по ключу и возвращает то же подтверждение при повторе.",
                "Ключ меняется при каждом повторе или срок хранения короче возможного повтора; дубликат не исключён."),
            action("A-QUERY","R-SEND","После тайм-аута проверять приём по номеру заявки",
                "До отправки выделяется устойчивый номер; сервер позволяет однозначно узнать факт приёма.",
                "Номер появляется только после успешного ответа; проверить потерянный ответ невозможно."),
            prepare("A-IDEMPOTENT","R-RETRY","Проверить повторную отправку после потери ответа","method_correctness"),
            action("A-RETRY-TEST","R-RETRY","Воспроизвести потерю ответа после записи на сервере",
                "В тестовой среде можно оборвать ответ после фиксации записи.",
                "Среда не позволяет отличить потерю запроса от потери ответа; вывод о дубликатах будет ненадёжен.")])
        # Placement is explicit; the atomic alternative and deep test remain unplaced.
        f.owner(f.placement_request([f.place("S-SPLIT","A-SPLIT"),
            f.place("S-LOCAL","A-LOCAL"),f.place("S-INPUT","R-INPUT","requirement"),
            f.place("S-IDEMPOTENT","A-IDEMPOTENT"),
            f.place("S-SEND","R-SEND","requirement",sequence=[{"before":"S-IDEMPOTENT","after":"S-SEND"}])]))
        w.apply([w.choose("A-LOCAL","R-INPUT")])
        w.apply([result("A-LOCAL","Учебная проверка: черновик восстановлен после перезагрузки без сети.",True)])
        # Annotation edit must not overwrite the saved event's canon/QRPE.
        w.apply([w.edit("edit_node",nodeId="A-LOCAL",changes={"canonBlock":{
            "recommended":[{"id":"C-A-LOCAL-PLUS","text":"После проверки политики: разрешено только на личном устройстве с явным выходом из аккаунта."}],
            "contraindicated":[{"id":"C-A-LOCAL-MINUS","text":"Общее устройство: локальный черновик сохранять нельзя."}]}}),
            {"op":"append_qrpe","targetId":"A-LOCAL","issue":{"id":"Q-SHARED-DEVICE",
                "text":"В учебный контекст добавлено общее устройство; прежний способ нужно пересмотреть.","status":"open"}}])
        withdraw={"op":"withdraw_action","actionId":"A-LOCAL","dispositions":[],
            "event":w.event("action_withdrawn",actionId="A-LOCAL",driverRequirementId="R-INPUT")}
        withdraw["event"]["note"]="Появилось требование общего устройства. Прежнее выполнение сохранено, текущий выбор отозван."
        w.apply([withdraw])
        w.apply([w.choose("A-SERVER","R-INPUT"),w.choose("A-IDEMPOTENT","R-SEND")])
        f.owner(f.placement_request([f.place("S-SERVER","A-SERVER")]))
        view=WF.read_workflow(f.root,f.rel,w.home/"graphs",w.store,w.token,[w.rel],include_sources=True)
        graph=w.read()
        # Publish only synthetic data; bearer credentials and trust-store files
        # are never exported. Event principals are opaque attribution, not tokens.
        graph.update(id=SLUG,title="Actions · заявка, история и план",
            readOnly=True,exampleOnly=True,hypothetical=True,selectedInProject=False,
            presentation={"usage":"working","archived":False,
                "title":"Actions · история и план во времени",
                "description":"Текущая модель: варианты, каноны, QRPE, две роли R, выполнение, отзыв и явное размещение."},
            coverage="Учебные факты из изолированного writer. Выбранный decomposition выполнен, его подцели ещё не достигнуты. Локальный черновик выполнен и затем отозван; новый способ выбран, но ещё не выполнен.")
        view["graphFile"]=FILE;view["planFile"]="example://action-time-plan"
        view["title"]="Учебный план · надёжная заявка"
        view["permissions"]=["graph.read","plan.read"];view["capabilities"]=[]
        view["exampleOnly"]=True
        for field in ("graphOwners","completionProvenance","planProvenance"):
            view.pop(field,None)
        completion=view["sources"]["completion"].pop(w.rel)
        for state in completion.values():
            if state.get("ownerRef",{}).get("graphFile")==w.rel:state["ownerRef"]["graphFile"]=FILE
        view["sources"]["completion"]={FILE:completion}
        view["sources"].pop("graphs")
        for row in view["history"]:
            row["graphFile"]=FILE
        for name in ("future","excludedPlacements","unresolved"):
            for row in view[name]:
                for key in ("graphRef","ownerRef"):
                    if row.get(key,{}).get("graphFile")==w.rel:row[key]["graphFile"]=FILE
        for step in view["sources"]["plan"]["steps"]:
            for key in ("actionRef","requirementRef"):
                if step.get(key,{}).get("graphFile")==w.rel:step[key]["graphFile"]=FILE
        view["sources"]["plan"]["title"]=view["title"]
        graph["workflowExample"]=view
        encoded=json.dumps(graph,ensure_ascii=False,indent=2)+"\n"
        assert w.token not in encoded and w.owner not in encoded
        out=ROOT/"graphs"/FILE;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(encoded)
        print("Published",FILE,"nodes",len(graph["nodes"]),"events",len(graph["events"]),
              "history",len(view["history"]),"future",[r["nodeId"] for r in view["future"]])
    finally:
        f.doCleanups()

if __name__=="__main__":
    build()
