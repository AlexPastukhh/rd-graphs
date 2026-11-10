#!/usr/bin/env python3
"""Regression gates for bounded, post-verification read projection caches."""
import copy
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE=SourceFileLoader('projection_cache_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()
CACHE=SourceFileLoader('projection_cache_unit',str(ROOT/'tools/rdg-projection-cache.py')).load_module()


class ProjectionCacheTests(unittest.TestCase):
    def setUp(self):
        self.fixture=BASE.PortableApplication('test_finding_schema_preflight_retry_and_restart_share_writer')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.owner,self.subject=self.fixture.finding_package()
        self.app=self.fixture.app()

    def uncached(self, **kwargs):
        return self.fixture.app().history(self.owner,**kwargs)

    def test_full_history_exact_and_isolated_from_mutated_result(self):
        expected=self.uncached()
        first=self.app.history(self.owner)
        self.assertEqual(first,expected)
        self.assertEqual(len(self.app._history_cache),1)
        first['events'].clear()
        first['planVersions'].append({'tainted':True})
        self.assertEqual(self.app.history(self.owner),expected)
    def test_explicit_full_and_default_are_both_cached_independently(self):
        expected=self.uncached()
        self.assertEqual(self.app.history(self.owner),expected)
        self.assertEqual(self.app.history(self.owner,detail='full'),expected)
        self.assertEqual(len(self.app._history_cache),2)
        with self.assertRaisesRegex(ValueError,'READ_DETAIL_REQUIRED'):
            self.app.history(self.owner,detail='full',include=['events'])

    def test_history_modes_do_not_mix_and_recheck_inventory(self):
        for mode in ('all','important','meaningful','technical'):
            opts={'view':{'kind':'graph','historyMode':mode}}
            self.assertEqual(self.app.history(self.owner,**opts),self.uncached(**opts))
        self.assertEqual(len(self.app._history_cache),4)
        with patch.object(self.app.store,'inventory',wraps=self.app.store.inventory) as verified:
            self.app.history(self.owner,view={'kind':'graph','historyMode':'all'})
            self.assertEqual(verified.call_count,1)

    def test_compact_and_item_never_cache_or_bypass_invalid_options(self):
        opts={'detail':'compact','include':['events']}
        expected=self.uncached(**opts)
        self.assertEqual(self.app.history(self.owner,**opts),expected)
        self.assertEqual(self.app.history(self.owner,**opts),expected)
        self.assertEqual(len(self.app._history_cache),0)
        with self.assertRaisesRegex(ValueError,'READ_HISTORY_INCLUDE'):
            self.app.history(self.owner,detail='compact',include=('events',))
        event=self.uncached()['events'][0]['event']['id']
        self.assertEqual(self.app.history(self.owner,detail='item',event_id=event),
                         self.uncached(detail='item',event_id=event))
        self.assertEqual(len(self.app._history_cache),0)

    def test_revoke_permission_still_denies_warm_history(self):
        self.app.history(self.owner)
        with patch.object(self.app,'authorize',side_effect=ValueError('DENIED')):
            with self.assertRaisesRegex(ValueError,'DENIED'):
                self.app.history(self.owner)
    def test_revoked_real_grant_and_new_application_cannot_reuse_cache(self):
        self.app.history(self.owner)
        fresh=self.fixture.app()
        self.assertEqual(len(fresh._history_cache),0)
        self.assertEqual(fresh.history(self.owner),self.app.history(self.owner))
        self.fixture.authority.manage('revoke',self.fixture.admin,{'id':self.fixture.grant_id})
        with self.assertRaisesRegex(ValueError,'TOKEN_REVOKED'):
            self.app.history(self.owner)
        with self.assertRaisesRegex(ValueError,'TOKEN_REVOKED'):
            fresh.history(self.owner)

    def test_tampered_historical_artifact_still_fails_warm_history(self):
        self.app.history(self.owner)
        row=self.app.snapshot(self.owner,True,False)
        relative=next(p for p in self.app.store.inventory(row)
                      if p.startswith('history/heads/'))
        path=self.app.store.io.safe_path(self.app.store.package_path(row['path']),relative,True)
        original=path.read_bytes()
        try:
            path.write_bytes(original+b' ')
            with self.assertRaisesRegex(ValueError,'HISTORY_HEAD_HASH_MISMATCH|INVENTORY_BYTES_MISSING'):
                self.app.history(self.owner)
        finally:
            path.write_bytes(original)
        self.assertEqual(self.app.history(self.owner),self.uncached())

    def test_new_head_invalidates_full_history(self):
        before=self.app.history(self.owner)
        self.fixture.command(self.owner,'edit',nodeId=self.subject,
                             changes={'title':'Cache new head'},cosmetic=True)
        after=self.app.history(self.owner)
        self.assertNotEqual(before,after)
        self.assertEqual(after,self.uncached())
        self.assertEqual(len(self.app._history_cache),2)

    def test_plan_only_commit_invalidates_history_even_with_same_graph(self):
        before_graph=self.app.snapshot(self.owner,True,False)['graph']
        before=self.app.history(self.owner)
        request=self.app.schema('plan_create',self.owner)['request']
        self.app.request(request)
        self.assertEqual(self.app.snapshot(self.owner,True,False)['graph'],before_graph)
        after=self.app.history(self.owner)
        self.assertNotEqual(before,after)
        self.assertTrue(after['planVersions'])
        self.assertEqual(after,self.uncached())
        self.assertEqual(len(self.app._history_cache),2)

    def test_plan_read_denied_after_warm_cache(self):
        request=self.app.schema('plan_create',self.owner)['request']
        self.app.request(request)
        self.app.history(self.owner)
        authorized=self.app.authorize
        def check(ident,permissions,path=None):
            if 'plan.read' in permissions:
                raise ValueError('AUTH_MISSING_PERMISSION: plan.read')
            return authorized(ident,permissions,path)
        with patch.object(self.app,'authorize',side_effect=check):
            with self.assertRaisesRegex(ValueError,'AUTH_MISSING_PERMISSION: plan.read'):
                self.app.history(self.owner)
        self.assertEqual(self.app.history(self.owner),self.uncached())

    def test_failed_history_reconstruction_never_populates_cache(self):
        with patch.object(self.app.migration,'historical_records',side_effect=ValueError('BROKEN_EVIDENCE')):
            with self.assertRaisesRegex(ValueError,'BROKEN_EVIDENCE'):
                self.app.history(self.owner)
        self.assertEqual(len(self.app._history_cache),0)
        self.assertEqual(self.app.history(self.owner),self.uncached())

    def test_writer_lock_still_blocks_warm_history_reader(self):
        self.app.history(self.owner)
        request=self.fixture.command_request(self.owner,'add',entity={
            'id':'CACHE-CONCURRENT','kind':'context','title':'Concurrent fact',
            'description':'Synthetic','value':'New committed content'})
        entered=threading.Event();release=threading.Event();started=threading.Event()
        def hold():
            entered.set()
            if not release.wait(12):raise RuntimeError('writer barrier timeout')
        def read():
            started.set()
            return self.app.history(self.owner)
        with ThreadPoolExecutor(max_workers=2) as executor:
            writer=executor.submit(self.fixture.app().request,request,before_accept=hold)
            try:
                self.assertTrue(entered.wait(12))
                reader=executor.submit(read)
                self.assertTrue(started.wait(3))
                time.sleep(.2)
                self.assertFalse(reader.done(),'History bypassed active exclusive writer lock')
            finally:
                release.set()
            self.assertTrue(writer.result(timeout=15)['published'])
            result=reader.result(timeout=15)
        self.assertEqual(result,self.uncached())
        self.assertEqual(self.app.history(self.owner),result)

    def test_visual_exact_hit_mutation_and_new_graph(self):
        expected=self.fixture.app().read(self.owner,True)['view']['visual']
        first=self.app.read(self.owner,True)
        self.assertEqual(first['view']['visual'],expected)
        self.assertEqual(len(self.app._visual_cache),1)
        first['view']['visual'].clear()
        with patch.object(self.app,'layout_port',side_effect=AssertionError('visual cache miss')):
            self.assertEqual(self.app.read(self.owner,True)['view']['visual'],expected)
        self.fixture.command(self.owner,'edit',nodeId=self.subject,
                             changes={'title':'Visual new head'},cosmetic=True)
        refreshed=self.app.read(self.owner,True)['view']['visual']
        self.assertEqual(refreshed,self.fixture.app().read(self.owner,True)['view']['visual'])
        self.assertEqual(len(self.app._visual_cache),2)

    def test_visual_layout_input_is_part_of_key_and_other_operations_not_cached(self):
        document={'revision':1,'layouts':{}}
        graph=self.app.snapshot(self.owner,layouts=False)['graph']
        view=self.app.model.presentation(graph,self.app.kernel)
        first=self.app.layout('project',graph=graph,view=view,document=document)
        changed=copy.deepcopy(document)
        changed['revision']=2
        self.assertEqual(self.app.layout('project',graph=graph,view=view,document=changed),first)
        self.assertEqual(len(self.app._visual_cache),2)
        with patch.object(self.app,'layout_port',side_effect=ValueError('NOT_CACHED')):
            with self.assertRaisesRegex(ValueError,'NOT_CACHED'):
                self.app.layout('validate',document=document)

    def test_failed_projection_is_not_cached(self):
        graph=self.app.snapshot(self.owner,layouts=False)['graph']
        view=self.app.model.presentation(graph,self.app.kernel)
        with patch.object(self.app,'layout_port',side_effect=ValueError('SYNTHETIC_ERROR')):
            with self.assertRaisesRegex(ValueError,'SYNTHETIC_ERROR'):
                self.app.layout('project',graph=graph,view=view,document={'revision':99})
        self.assertEqual(len(self.app._visual_cache),0)

    def test_lru_bounds_and_serialized_response_isolation(self):
        cache=CACHE.ProjectionCache(max_entries=2,max_bytes=160)
        for i in range(3):
            cache.put(i,{'item':i})
        self.assertEqual(len(cache),2)
        self.assertIsNone(cache.get(0))
        response=cache.get(2)
        response['item']='changed'
        self.assertEqual(cache.get(2),{'item':2})
        cache.put('oversize',{'value':'x'*300})
        self.assertEqual(len(cache),2)
        self.assertIsNone(cache.get('oversize'))


if __name__=='__main__':
    unittest.main(verbosity=2)
