#!/usr/bin/env python3
"""End-to-end portable Application layout occurrence references and copy."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE=SourceFileLoader('visual_app_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()


class VisualOccurrences(unittest.TestCase):
    setUp=BASE.PortableApplication.setUp
    config=BASE.PortableApplication.config
    app=BASE.PortableApplication.app
    create=BASE.PortableApplication.create
    current=BASE.PortableApplication.current
    req=BASE.PortableApplication.req
    command_request=BASE.PortableApplication.command_request
    command=BASE.PortableApplication.command

    def make_graph(self):
        source=self.create('shared')
        self.command(source,'add',entity={'id':'A1','kind':'action','title':'Shared Action'})
        self.command(source,'add',entity={'id':'R2','kind':'requirement','title':'Another goal','description':'Goal','scope':'S'})
        self.command(source,'add',entity={'id':'R3','kind':'requirement','title':'Output','description':'Output','scope':'S'})
        self.command(source,'link',edge={'id':'d1','type':'DRIVES','from':'R1','to':'A1'})
        self.command(source,'link',edge={'id':'d2','type':'DRIVES','from':'R2','to':'A1'})
        self.command(source,'link',edge={'id':'o1','type':'INTRODUCES','from':'A1','to':'R3','origin':{'role':'method_correctness'}})
        return source

    def layout(self,source,occ):
        app=self.app();before=self.current(source)
        graph=before['graph']
        key=json.dumps([graph['identitySpace'],graph['id']],separators=(',',':'))
        request=app.schema('layout_edit',source)['request']
        request['commands']=[{'type':'set_positions','graphKey':key,'positions':{'A1':{'x':200,'y':70}}},
                             {'type':'set_occurrences','graphKey':key,'occurrences':occ}]
        return app.request(request),key

    def test_shared_visual_occurrence_preserved_by_real_copy_without_new_domain_node(self):
        source=self.make_graph()
        original=self.current(source)['graph']
        extra={'occ-second':{'entityId':'A1','x':480,'y':220,'parentId':'R2','viaEdgeId':'d2'},
               'occ-output':{'entityId':'R3','x':680,'y':220,'parentId':'occ-second','viaEdgeId':'o1'}}
        self.layout(source,extra)
        current=self.current(source);self.assertEqual(current['graph'],original)
        request=self.app().schema('copy',source)['request'];request['note']='Synthetic layout copy';request['path']='copies/visual-occurrences'
        response=self.app().request(request)
        copied=response['packages'][0]['packageId']
        result=self.current(copied);mapping=response['packages'][0]['receipt']['effects']['idMap']
        occurrences=next(iter(result['layouts']['layouts'].values()))['occurrences']
        self.assertEqual(occurrences['occ-second']['entityId'],mapping['entity']['A1'])
        self.assertEqual(occurrences['occ-second']['parentId'],mapping['entity']['R2'])
        self.assertEqual(occurrences['occ-second']['viaEdgeId'],mapping['edge']['d2'])
        self.assertEqual(occurrences['occ-output']['parentId'],'occ-second')
        self.assertEqual(occurrences['occ-output']['viaEdgeId'],mapping['edge']['o1'])
        self.assertEqual(len(result['graph']['nodes']),len(original['nodes']))
        self.assertEqual(self.current(source),current)

    def test_workgraph_external_visual_occurrence_does_not_add_membership(self):
        source=self.make_graph()
        self.command(source,'work_graph',id='WG-other',title='Another area',
                     rootIds=['R2'],memberIds=['R2'])
        app=self.app();before=self.current(source)
        subset=app.read(source,False,{'kind':'workGraph','id':'WG-other'})
        self.assertEqual({n['id'] for n in subset['view']['entities']},{'R2'})
        self.assertEqual(subset['view']['edges'],[])
        key=subset['view']['graphKey']
        alias={'occ-external-A':{'entityId':'A1','x':325,'y':45,'parentId':'R2','viaEdgeId':'d2'}}
        request=app.schema('layout_edit',source)['request']
        request['commands']=[{'type':'set_occurrences','graphKey':key,'occurrences':alias}]
        app.request(request)
        after=self.current(source)
        self.assertEqual(after['graph'],before['graph'])
        area=next(w for w in after['graph']['workGraphs'] if w['id']=='WG-other')
        self.assertNotIn('A1',area['memberIds'])
        self.assertEqual(after['layouts']['layouts'][key]['occurrences'],alias)

    def test_reject_dangling_display_edge_and_parent_without_updating_graph(self):
        source=self.make_graph();before=self.current(source)
        with self.assertRaisesRegex(ValueError,'LAYOUT_OCCURRENCE_EDGE'):
            self.layout(source,{'occ-1':{'entityId':'A1','x':2,'y':3,'parentId':'R2','viaEdgeId':'nonexistent'}})
        with self.assertRaisesRegex(ValueError,'LAYOUT_OCCURRENCE_PARENT'):
            self.layout(source,{'occ-1':{'entityId':'A1','x':2,'y':3,'parentId':'R1','viaEdgeId':'d2'}})
        self.assertEqual(self.current(source),before)


if __name__=='__main__':unittest.main()
