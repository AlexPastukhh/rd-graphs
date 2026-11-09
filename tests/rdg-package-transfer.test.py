#!/usr/bin/env python3
"""Filesystem transfer faults on temporary, explicitly scoped packages."""
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE=SourceFileLoader('transfer_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()


class Moves(unittest.TestCase):
    setUp=BASE.PortableApplication.setUp
    app=BASE.PortableApplication.app
    config=BASE.PortableApplication.config
    create=BASE.PortableApplication.create
    current=BASE.PortableApplication.current
    req=BASE.PortableApplication.req
    command_request=BASE.PortableApplication.command_request
    command=BASE.PortableApplication.command
    sources=BASE.PortableApplication.sources
    review=BASE.PortableApplication.review

    def request(self,ident,path):
        request=self.app().schema('move',ident)['request'];request.update(path=path,note='Synthetic move');return request

    @staticmethod
    def fail(phase):
        def injected(point):
            if point==phase:raise RuntimeError('Injected '+phase)
        return injected

    def test_rename_preserves_bytes_identity_history_and_old_receipt_after_later_edit(self):
        ident=self.create('rename');original=self.store.read(ident);request=self.request(ident,'2026-10/renamed')
        before=self.sources();preview=self.app().request(request,preflight=True);self.assertEqual(before,self.sources())
        result=self.app().request(request);self.assertTrue(result['published']);self.assertEqual(preview['effects'],result['effects'])
        current=self.store.read(ident);self.assertEqual(current['path'],'2026-10/renamed');self.assertEqual(current['headBytes'],original['headBytes'])
        self.assertFalse((self.root/original['path']).exists());self.assertEqual(current['graph'],original['graph']);self.assertEqual(current['plan'],original['plan'])
        self.command(ident,'edit',nodeId='R1',changes={'title':'Later valid edit'})
        self.assertTrue(self.app().request(request)['idempotent']);self.assertEqual(self.current(ident)['graph']['nodes'][0]['title'],'Later valid edit')
        receipt=self.app().receipt(ident,request['transactionId']);self.assertTrue(receipt['published'])
        self.assertTrue(self.app().history(ident)['planVersions'])
        copied=self.app().schema('copy',ident)['request'];copied.update(path='copies/moved',note='Copy moved package')
        copy_id=self.app().request(copied)['packages'][0]['packageId']
        inventory=self.store.inventory(self.store.read(copy_id))
        self.assertTrue(any(p.endswith('/.rdg/moves/'+request['transactionId']+'.json') for p in inventory))

    def test_copy_protocol_recovers_after_publication_and_revocation(self):
        ident=self.create('cross-fs');before=self.store.read(ident);app=self.app();app.transfers.same_filesystem=lambda *_:False
        request=self.request(ident,'moved/cross-fs')
        with self.assertRaisesRegex(RuntimeError,'Injected move-published'):app.request(request,failpoint=self.fail('move-published'))
        self.assertTrue((self.root/before['path']).is_dir());self.assertTrue((self.root/'moved/cross-fs').is_dir())
        with self.assertRaisesRegex(ValueError,'DUPLICATE_IDENTITY|MOVE_RECOVERY_REQUIRED'):self.store.read(ident)
        self.authority.manage('revoke',self.admin,{'id':self.grant_id})
        recovered=app.call({'method':'recover','transactionId':request['transactionId']});self.assertTrue(recovered['published']);self.assertFalse((self.root/before['path']).exists())
        self.assertEqual(self.store.read(ident)['headBytes'],before['headBytes'])

    def test_partial_source_cleanup_is_resumable_and_never_removes_unexpected_data(self):
        ident=self.create('partial');original=self.store.read(ident);app=self.app();app.transfers.same_filesystem=lambda *_:False
        request=self.request(ident,'moved/partial')
        with self.assertRaisesRegex(RuntimeError,'Injected move-cleanup-file'):app.request(request,failpoint=self.fail('move-cleanup-file'))
        self.assertTrue(app.request(request)['published']);self.assertFalse((self.root/original['path']).exists())
        self.assertEqual(self.store.read(ident)['graph'],original['graph'])

    def test_source_change_after_publication_is_preserved_as_recovery_blocker(self):
        ident=self.create('unexpected');original=self.store.read(ident);app=self.app();app.transfers.same_filesystem=lambda *_:False
        request=self.request(ident,'moved/unexpected')
        with self.assertRaises(RuntimeError):app.request(request,failpoint=self.fail('move-published'))
        unexpected=self.root/original['path']/'unexpected.txt';unexpected.write_text('Do not remove')
        with self.assertRaisesRegex(ValueError,'SOURCE_TREE_CHANGED'):app.request(request)
        self.assertEqual(unexpected.read_text(),'Do not remove');self.assertTrue((self.root/'moved/unexpected/package.json').exists())

    def test_source_tree_cas_includes_non_graph_files_before_acceptance(self):
        ident=self.create('source-cas');row=self.store.read(ident);note=self.root/row['path']/'note.txt';note.write_text('before')
        request=self.request(ident,'moved/source-cas');app=self.app();app.transfers.same_filesystem=lambda *_:False
        with self.assertRaisesRegex(ValueError,'SOURCE_TREE_CHANGED'):
            app.request(request,before_accept=lambda:note.write_text('concurrent change'))
        self.assertFalse(app.transfers.journal(request['transactionId']).exists());self.assertEqual(note.read_text(),'concurrent change')
        self.assertEqual(self.store.read(ident)['path'],row['path']);self.assertFalse((self.root/'moved/source-cas').exists())

    def test_identity_scope_does_not_grant_folder_access_or_escape_root(self):
        ident=self.create('scope');row=self.store.read(ident)
        token=self.authority.manage('issue',self.admin,{'permissions':['graph.read','plan.read','package.move','folder.write'],
            'scopes':['packages/'+self.namespace+'/'+ident]})['token']
        request=self.request(ident,'moved/scope')
        with self.assertRaisesRegex(ValueError,'PORTABLE_SCOPE_DENIED'):self.app(token).request(request)
        request=self.request(ident,'../outside')
        with self.assertRaisesRegex(ValueError,'PATH_COMPONENT'):self.app().request(request)
        self.assertEqual(self.store.read(ident)['path'],row['path'])

    def test_real_folder_create_move_pin_and_multiple_packages(self):
        app=self.app();create=app.schema('folder_create')['request'];create['path']='organized';app.request(create)
        self.assertTrue((self.root/'organized').is_dir());self.assertTrue(app.request(create)['idempotent'])
        first=self.create('one');second=self.create('two')
        request=app.schema('folder_move',source_path='working')['request'];request['path']='organized/working'
        (self.root/'working/ordinary-note.txt').write_bytes(b'Synthetic folder data')
        with self.assertRaisesRegex(ValueError,'SOURCE_TREE_CHANGED'):app.request(request)
        request=app.schema('folder_move',source_path='working')['request'];request['path']='organized/working'
        app.transfers.same_filesystem=lambda *_:False;result=app.request(request)
        self.assertEqual({p['packageId'] for p in result['packages']},{first,second})
        for ident in (first,second):self.assertTrue(self.store.read(ident)['path'].startswith('organized/working/'))
        self.assertEqual((self.root/'organized/working/ordinary-note.txt').read_bytes(),b'Synthetic folder data')
        self.assertFalse((self.root/'working').exists())

    def test_move_preserves_detached_selected_stale_and_current_plan(self):
        ident=self.create('detached')
        self.command(ident,'add',entity={'id':'A','kind':'action','title':'Retained action'})
        self.command(ident,'link',edge={'id':'driver','type':'DRIVES','from':'R1','to':'A'})
        self.review(ident);self.command(ident,'select',nodeId='A');self.review(ident)
        placement=self.app().schema('place',ident,'A')['request'];placement.update(at='2026-10-30',note='Synthetic time')
        self.app().request(placement);self.command(ident,'unlink',edgeId='driver')
        before=self.current(ident);self.app().request(self.request(ident,'moved/detached'));after=self.current(ident)
        self.assertEqual(before['graph'],after['graph']);self.assertEqual(before['plan'],after['plan'])
        self.assertEqual(before['detached'],after['detached']);self.assertTrue(after['completion']['A']['reviewRequired'])

    def test_folder_move_cannot_relocate_unmigrated_legacy_owner(self):
        ident=self.create('portable');row=self.store.read(ident)
        raw=self.root/'working/unconverted/graph.json';raw.parent.mkdir();raw.write_text(json.dumps(row['graph']))
        with self.assertRaisesRegex(ValueError,'LEGACY_OWNER_REQUIRES_EXPLICIT_MIGRATION'):
            self.app().schema('folder_move',source_path='working')
        self.assertTrue(raw.is_file());self.assertEqual(self.store.read(ident)['path'],row['path'])

    def test_stable_lens_key_follows_actual_location(self):
        app=self.app();request=app.schema('create')['request'];request.update(role='lens',path='lenses/original',title='Lens',scope='Synthetic lens scope',lensKey='stable-test-key')
        ident=app.request(request)['packages'][0]['packageId'];app.request(self.request(ident,'other-folder/renamed-lens'))
        row=next(r for r in app.catalog()['packages'] if r.get('lensKey')=='stable-test-key')
        self.assertEqual(row['packageId'],ident);self.assertEqual(row['path'],'other-folder/renamed-lens')


if __name__=='__main__':unittest.main()
