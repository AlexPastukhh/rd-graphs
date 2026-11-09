#!/usr/bin/env python3
"""One full scenario on the actual source mount; only temporary synthetic data."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE=SourceFileLoader('mounted_portable_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()


class MountedStorage(unittest.TestCase):
    config=BASE.PortableApplication.config
    app=BASE.PortableApplication.app
    create=BASE.PortableApplication.create
    current=BASE.PortableApplication.current
    req=BASE.PortableApplication.req
    command_request=BASE.PortableApplication.command_request
    command=BASE.PortableApplication.command
    review=BASE.PortableApplication.review
    replace_request=BASE.PortableApplication.replace_request

    def setUp(self):
        BASE.PortableApplication.setUp(self)
        temporary=tempfile.TemporaryDirectory(prefix='.rdg-storage-test-',dir=ROOT)
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)/'packages'
        self.store=BASE.FIX.S.FileStore(self.root,self.namespace,BASE.FIX.IO,BASE.P,self.base)
        # Authority and coordinator files remain in the private Docker fixture,
        # outside the repository. Only synthetic package data use the source FS.

    def test_ready_replace_detached_plan_copy_layout_move_and_owned_history_on_source_mount(self):
        ident=self.create('work');ready=self.create('template','ready');app=self.app()
        self.command(ident,'add',entity={'id':'A','kind':'action','title':'Retained action'})
        self.command(ident,'link',edge={'id':'DRIVER','type':'DRIVES','from':'R1','to':'A'})
        self.review(ident);self.command(ident,'select',nodeId='A');self.review(ident)
        for node_id in ('R1','A'):
            request=app.schema('place',ident,node_id)['request'];request.update(at='2026-10-30',note='Synthetic placement');app.request(request)
        app.request(self.replace_request(ident,ready));current=app.read(ident,True)
        self.assertTrue(any('A' in c['memberIds'] for c in current['detached']))
        self.assertEqual(next(n for n in current['graph']['nodes'] if n['id']=='A')['status'],'selected')
        self.assertTrue(current['completion']['A']['reviewRequired'])
        self.assertEqual([s['ref']['nodeId'] for s in current['plan']['steps']],['A'])
        layout=app.schema('layout_edit',ident)['request'];layout['commands']=[{'type':'set_positions',
            'graphKey':current['view']['graphKey'],'positions':{'A':{'x':37,'y':61}}}];app.request(layout)
        pin=app.history(ident)['events'][-1]['source']
        request=app.schema('copy',ident)['request'];request.update(path='copies/mounted',note='Synthetic mounted copy')
        result=app.request(request);copied=result['packages'][0]['packageId'];mapping=result['packages'][0]['receipt']['effects']['idMap']['entity']
        copy=app.read(copied,True);self.assertTrue(copy['completion'][mapping['A']]['reviewRequired'])
        self.assertTrue(any(layout['positions'].get(mapping['A'])=={'x':37,'y':61} for layout in copy['layouts']['layouts'].values()))
        before=self.store.read(copied)['headBytes'];move=app.schema('move',copied)['request'];move.update(path='organized/mounted',note='Synthetic mount rename')
        app.request(move);self.assertEqual(self.store.read(copied)['headBytes'],before)
        self.assertEqual(app.read(copied,True)['plan'],copy['plan'])
        source=self.store.read(ident);shutil.rmtree(self.root/source['path'])
        snapshot=app.source_snapshot(copied,pin);self.assertTrue(snapshot['readOnly'])
        self.assertEqual(BASE.P.digest(snapshot['graph']),pin['sha256'])
        self.assertFalse(app.history(copied)['reconstructedExecution'])


if __name__=='__main__':unittest.main()
