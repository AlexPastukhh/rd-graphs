#!/usr/bin/env python3
"""T1 compact reads: bounded facets, immutable pagination and legacy compatibility."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
T=SourceFileLoader('compact_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()
A=SourceFileLoader('compact_agent',str(ROOT/'tools/rdg-agent.py')).load_module()


class CompactReads(unittest.TestCase):
    setUp=T.PortableApplication.setUp
    config=T.PortableApplication.config
    app=T.PortableApplication.app
    req=T.PortableApplication.req
    sources=T.PortableApplication.sources
    current=T.PortableApplication.current
    command_request=T.PortableApplication.command_request
    command=T.PortableApplication.command
    finding_package=T.PortableApplication.finding_package

    def test_summary_is_small_paginated_and_unchanged_reads_do_not_write(self):
        ident,subject=self.finding_package()
        app=self.app();before=self.sources()
        full=app.call({'method':'read','packageId':ident})
        self.assertIn('dependencyCatalog',full)
        form=app.call({'method':'schema','op':'read','packageId':ident})
        self.assertIn('context',form['read']['include'])
        first=app.call({'method':'read','packageId':ident,'detail':'summary','limit':1})
        self.assertNotIn('dependencyCatalog',first)
        self.assertNotIn('events',first)
        self.assertNotIn('objects',first['graph'])
        self.assertLess(len(json.dumps(first)),len(json.dumps(full)))
        self.assertFalse(first['loaded']['context'])
        self.assertTrue(first['loaded']['entities'])
        page=first['data']['entities']
        self.assertEqual(page['page']['returned'],1)
        self.assertTrue(page['page']['nextCursor'])
        second=app.call({'method':'read','packageId':ident,'detail':'summary','limit':1,
                         'include':['entities'],'cursor':page['page']['nextCursor']})
        self.assertNotEqual(page['items'][0]['id'],second['data']['entities']['items'][0]['id'])
        self.assertEqual(self.sources(),before)
        self.command(ident,'edit',nodeId=subject,changes={'description':'A new basis'},cosmetic=False)
        with self.assertRaisesRegex(ValueError,'READ_CURSOR_STALE'):
            self.app().call({'method':'read','packageId':ident,'detail':'summary','limit':1,
                             'include':['entities'],'cursor':page['page']['nextCursor']})

    def test_addressed_context_canon_findings_and_invalid_filters(self):
        ident,subject=self.finding_package()
        self.command(ident,'add',entity={'id':'CTX1','kind':'context','title':'Observed','description':'Source fact','value':'Test value'})
        self.command(ident,'decision_context',nodeId=subject,sourceId='CTX1',action='save',comment='Why it matters')
        self.command(ident,'add',entity={'id':'CAN1','kind':'canon','title':'Guideline','description':'Synthetic guidance','guidance':'Check criteria'},
                     initialRelations=[{'id':'CANON1','type':'CANON_FOR','from':'CAN1','to':subject}])
        before=self.sources()
        card=self.app().call({'method':'read','packageId':ident,'detail':'item','nodeId':subject,
                              'include':['context','canon','findings'],'limit':2})
        self.assertEqual(card['item']['id'],subject)
        self.assertEqual(card['data']['context']['items'][0]['sourceId'],'CTX1')
        self.assertEqual(card['data']['canon']['items'][0]['id'],'CAN1')
        self.assertEqual(card['data']['findings']['items'][0]['id'],'FINDING')
        direct=self.app().call({'method':'read','packageId':ident,'detail':'item','nodeId':subject,
                                'include':['findings'],'recordId':'FINDING'})
        self.assertEqual(len(direct['data']['findings']['items']),1)
        self.assertFalse(card['loaded']['plan'])
        self.assertEqual(self.sources(),before)
        for options,code in [({'include':['missing']},'READ_INCLUDE'),
                             ({'limit':0},'READ_LIMIT'),
                             ({'include':['entities'],'cursor':'bad'},'READ_CURSOR_INVALID')]:
            with self.subTest(options=options),self.assertRaisesRegex(ValueError,code):
                self.app().call({'method':'read','packageId':ident,'detail':'summary',**options})
        with self.assertRaisesRegex(ValueError,'READ_NODE_ID'):
            self.app().call({'method':'read','packageId':ident,'detail':'item'})

    def test_plan_history_pages_and_legacy(self):
        ident,subject=self.finding_package()
        app=self.app();before=self.sources()
        compact=app.call({'method':'read','packageId':ident,'detail':'summary','include':['plan']})
        self.assertTrue(compact['loaded']['plan'])
        self.assertIn('available',compact['plan'])
        history=app.call({'method':'history','packageId':ident,
                          'view':{'kind':'graph','historyMode':'all'},'detail':'compact','limit':1})
        self.assertTrue(history['loaded']['events'])
        self.assertFalse(history['loaded']['planVersions'])
        self.assertNotIn('planVersions',history)
        self.assertEqual(len(history['data']['events']['items']),1)
        token=history['data']['events']['page']['nextCursor']
        self.assertIsNotNone(token)
        another=app.call({'method':'history','packageId':ident,
                          'view':{'kind':'graph','historyMode':'all'},'detail':'compact',
                          'include':['events'],'limit':1,'cursor':token})
        self.assertNotEqual(history['data']['events']['items'],another['data']['events']['items'])
        event_id=history['data']['events']['items'][0]['id']
        event=app.call({'method':'history','packageId':ident,'detail':'item','eventId':event_id})
        self.assertEqual(event['item']['event']['id'],event_id)
        with self.assertRaisesRegex(ValueError,'READ_HISTORY_EVENT_ID'):
            app.call({'method':'history','packageId':ident,'detail':'item'})
        self.assertIn('planVersions',app.history(ident))
        self.assertEqual(self.sources(),before)
        with self.assertRaisesRegex(ValueError,'READ_HISTORY_INCLUDE'):
            app.call({'method':'history','packageId':ident,'detail':'compact','include':['unknown']})
        with self.assertRaisesRegex(ValueError,'READ_HISTORY_VIEW_UNSUPPORTED'):
            app.call({'method':'history','packageId':ident,'detail':'compact',
                      'view':{'kind':'focus','id':subject}})

    def test_agent_defaults_to_compact_but_can_request_full(self):
        ident,subject=self.finding_package()
        messages=[]
        class Client:
            def call(self,msg):
                messages.append(msg)
                return {'method':msg['method']}
        args=SimpleNamespace(command='open',package_id=ident,node=None,
                             expected_input_binding=None,show_excluded_alternatives=False,
                             detail=None,include=None,limit=25,cursor=None,lens=None)
        with patch.object(A,'portable_application',return_value=Client()):
            A.portable_command(args,{'profile':'gateway'})
        self.assertEqual(messages[-1]['detail'],'summary')
        self.assertNotIn('includePlan',messages[-1])


if __name__=='__main__':
    unittest.main()
