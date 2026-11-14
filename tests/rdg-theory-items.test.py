#!/usr/bin/env python3
"""Owned theory entries: real writer/read/copy, paging and bounded sources."""
import copy
import base64
import hashlib
from importlib.machinery import SourceFileLoader
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
F=SourceFileLoader('theory_items_fixture',str(ROOT/'tests/rdg-decision-theory.test.py')).load_module()
T=F.M.THEORY
A=SourceFileLoader('theory_items_agent',str(ROOT/'tools/rdg-agent.py')).load_module()


class TheoryItems(unittest.TestCase):
    setUp=F.Theory.setUp
    app=F.Theory.app
    config=F.Theory.config
    current=F.Theory.current
    req=F.Theory.req
    command_request=F.Theory.command_request
    command=F.Theory.command
    sources=F.Theory.sources
    review=F.Theory.review
    fixture=F.Theory.fixture
    add_theory=F.Theory.add_theory

    def read(self,pid,collection='overview',**options):
        return self.app().call({'method':'theory_read','packageId':pid,'theoryId':'K',
                               'collection':collection,**options})

    def test_overview_one_subset_and_all_at_one_snapshot_without_writes(self):
        pid=self.fixture()
        rows=[{'id':'c'+str(i),'title':'Canon '+str(i),'body':('large '+str(i)+'\n')*16000} for i in range(29)]
        target={'schemaVersion':1,'kind':'document','uri':'https://example.org/theory'}
        self.add_theory(pid,guidance='Use [the bound](theory:canons/c3) here. Read [source](theory:recommendations/r1) for context.',
                        canonItems=rows,recommendations=[{'id':'r1','title':'Material','targetRef':target}])
        before=self.sources()
        overview=self.read(pid)
        self.assertNotIn('body',overview['data']['canons']['items'][0]);self.assertEqual(overview['data']['canons']['page']['total'],29)
        self.assertFalse(overview['data']['canons']['page']['complete'])
        one=self.read(pid,'canons',itemIds=['c3'])['data']['canons']
        self.assertEqual(one['items'][0]['body'],rows[3]['body']);self.assertTrue(one['contentComplete'])
        self.assertIn('Use [the bound]',one['items'][0]['mentions'][0]['excerpt'])
        self.assertEqual(one['items'][0]['ref']['theoryRef']['nodeId'],'K')
        subset=self.read(pid,'canons',itemIds=['c1','c5'])['data']['canons']
        self.assertEqual([x['id'] for x in subset['items']],['c1','c5'])
        all_rows=T.read_pages(self.app(),{'method':'theory_read','packageId':pid,'theoryId':'K','collection':'canons','limit':3},True)
        self.assertEqual(all_rows['data']['canons']['items'][28]['body'],rows[28]['body'])
        self.assertTrue(all_rows['reading']['complete']);self.assertEqual(all_rows['reading']['pages'],10)
        external=self.read(pid,'recommendations')['data']['recommendations']['items'][0]
        self.assertEqual(external['resolved']['status'],'external');self.assertFalse(external['contentLoaded'])
        hits=self.app().call({'method':'search','packageId':pid,'query':'large 3'})['items']
        self.assertTrue(any(x['ref']['nodeId']=='K' for x in hits))
        self.assertEqual(before,self.sources())

    def test_invalid_collections_and_inline_references_are_atomic(self):
        pid=self.fixture();self.add_theory(pid,canonItems=[{'id':'a','title':'A','body':'Full A'}])
        before=self.sources()
        for fields,code in [({'canonItems':[{'id':'x','title':'A','body':'one'},{'id':'x','title':'B','body':'two'}]},'ITEM_ID_DUPLICATE'),
                            ({'guidance':'[gone](theory:canons/missing)'},'REFERENCE_MISSING'),
                            ({'canonItems':[{'id':'x','title':'A','body':'one','targetRef':{}}]},'CANON_CONTENT'),
                            ({'recommendations':[{'id':'r','title':'R','description':'duplicate explanation','targetRef':{}}]},'THEORY_ITEM')]:
            with self.assertRaisesRegex(ValueError,code):self.command(pid,'edit',nodeId='K',changes=fields,cosmetic=False)
            self.assertEqual(before,self.sources())
        self.command(pid,'edit',nodeId='K',changes={'guidance':'[A](theory:canons/a)'},cosmetic=False)
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'REFERENCE_MISSING'):self.command(pid,'edit',nodeId='K',changes={'canonItems':[]},cosmetic=False)
        self.assertEqual(before,self.sources())
        self.command(pid,'edit',nodeId='K',changes={'guidance':'New coherent theory','canonItems':[]},cosmetic=False)

    def test_cursor_rejects_owner_source_and_query_changes(self):
        pid=self.fixture();graph=self.current(pid)['graph'];ref=self.app().model.reference(pid,graph,'D')
        self.add_theory(pid,recommendations=[{'id':str(i),'title':'Source '+str(i),'targetRef':ref} for i in range(3)])
        page=self.read(pid,'recommendations',limit=1)
        cursor=page['data']['recommendations']['page']['nextCursor'];self.assertTrue(cursor)
        with self.assertRaisesRegex(ValueError,'CURSOR_INVALID'):self.read(pid,'recommendations',cursor=cursor,detail='summary')
        self.command(pid,'edit',nodeId='D',changes={'description':'Changed source'},cosmetic=False)
        with self.assertRaisesRegex(ValueError,'CURSOR_STALE'):self.read(pid,'recommendations',cursor=cursor)
        with self.assertRaisesRegex(ValueError,'REVISION_CHANGED'):self.read(pid,expectedTheoryRevision=999)
        with self.assertRaisesRegex(ValueError,'ITEM_NOT_FOUND'):self.read(pid,'canons',itemIds=['missing'])
        with self.assertRaisesRegex(ValueError,'ITEM_IDS'):self.read(pid,'canons',itemIds=[{}])

    def test_legacy_read_preserves_text_and_no_implicit_migration(self):
        pid=self.fixture();self.add_theory(pid,canons='One complete old canon\nincluding a bad case')
        before=self.sources();result=self.read(pid,'canons')
        self.assertEqual(result['data']['canons']['items'][0]['id'],'legacy-canons')
        self.assertTrue(result['data']['canons']['items'][0]['legacy']);self.assertEqual(before,self.sources())
        self.command(pid,'edit',nodeId='K',changes={'canons':'','canonItems':[{'id':'migrated','title':'Full old canon','body':result['data']['canons']['items'][0]['body']}]},cosmetic=False)
        self.assertEqual(self.read(pid,'canons')['data']['canons']['items'][0]['body'],result['data']['canons']['items'][0]['body'])

    def test_local_targets_copy_remap_and_individual_theory_target(self):
        pid=self.fixture();graph=self.current(pid)['graph'];ref=self.app().model.reference(pid,graph,'D')
        self.add_theory(pid,canonItems=[{'id':'a','title':'Whole canon','body':'A useful complete theory'}],
                        recommendations=[{'id':'rdg','title':'Decision source','targetRef':ref}])
        graph=self.current(pid)['graph'];target={'schemaVersion':1,'kind':'theoryItem','reference':self.app().model.reference(pid,graph,'K'),'collection':'canons','itemId':'a'}
        self.add_theory(pid,ident='K2',recommendations=[{'id':'theory','title':'Specific canon','targetRef':target}])
        read=self.app().call({'method':'theory_read','packageId':pid,'theoryId':'K2','collection':'recommendations','expand':True})
        self.assertEqual(read['data']['recommendations']['items'][0]['resolved']['content'],'A useful complete theory')
        request=self.app().schema('copy',pid,source_id=pid)['request'];request.update(path='copy/theory-items',note='Copy local theory references')
        copied=self.app().request(request)['packages'][0]['packageId'];graph=self.current(copied)['graph']
        canon=next(n for n in graph['objects'] if n.get('canonItems'))
        source=canon['recommendations'][0]['targetRef'];self.assertEqual(source['mode'],'inherited')
        resolved=self.app().call({'method':'theory_read','packageId':copied,'theoryId':canon['id'],'collection':'recommendations','expand':True})['data']['recommendations']['items'][0]['resolved']
        self.assertTrue(resolved['localBinding']);self.assertEqual(json.loads(resolved['content'])['kind'],'decision')
        self.assertEqual(resolved['sourcePin']['packageId'],copied)

    def test_explicit_source_expansion_network_budget_and_agent_all(self):
        pid=self.fixture();rows=[{'id':'r'+str(i),'title':'Document '+str(i),'targetRef':{'schemaVersion':1,'kind':'document','uri':'https://example.org/'+str(i)}} for i in range(11)]
        self.add_theory(pid,recommendations=rows);before=self.sources();client=self.app();client.kernel.for_profile('rdg-decision-v1')
        message={'method':'theory_read','packageId':pid,'theoryId':'K','collection':'recommendations'}
        with patch.object(T.SOURCES,'fetch_https',return_value={'status':'available','content':'Full material','contentLoaded':True}) as fetch:
            client.call(message);fetch.assert_not_called()
            page=client.call({**message,'expand':True,'limit':100});self.assertEqual(fetch.call_count,8)
            self.assertEqual(page['data']['recommendations']['page']['returned'],8)
            self.assertTrue(page['data']['recommendations']['page']['nextCursor'])
            with patch.object(A,'portable_application',return_value=client), patch.object(A.PORTABLE,'module',return_value=T):
                result=A.portable_command(SimpleNamespace(command='theory',package_id=pid,theory_id='K',collection='recommendations',detail='content',expand_sources=True,limit=100,cursor=None,item_id=None,all_pages=True,format='markdown',expected_input_binding=None),{'profile':'portable'})
            self.assertEqual(len(result['data']['recommendations']['items']),11)
            self.assertTrue(result['data']['recommendations']['contentComplete']);self.assertIn('Full material',result['markdown'])
        self.assertEqual(before,self.sources())

    def test_lens_source_pins_and_foreign_source_cursor(self):
        pid=self.fixture();app=self.app()
        request=app.schema('create',core_model='rdg-decision-v1',role='lens')['request']
        request.update(path='lens/theory-source',title='Source lens',scope='Synthetic',rootReason='A source fixture',lensKey='theory-source')
        source=app.request(request)['packages'][0]['packageId'];graph=self.current(source)['graph']
        ref=app.model.scope_reference(source,graph,'lens')
        target={'schemaVersion':1,'kind':'lens','reference':ref}
        self.add_theory(pid,recommendations=[{'id':str(i),'title':'Lens '+str(i),'targetRef':target} for i in range(3)])
        first=self.read(pid,'recommendations',limit=1,expand=True)
        value=first['data']['recommendations']['items'][0]
        self.assertEqual(value['sourceKind'],'lens');self.assertTrue(value['resolved']['contentLoaded'])
        self.assertIn('Source lens',value['resolved']['content'])
        request=app.schema('paper_edit',source,command='graph_title')['request'];request.update(data={'title':'Updated source lens'},note='Source version changed')
        app.request(request)
        with self.assertRaisesRegex(ValueError,'CURSOR_STALE'):
            self.read(pid,'recommendations',limit=1,expand=True,cursor=first['data']['recommendations']['page']['nextCursor'])
        self.assertTrue(self.read(pid,'recommendations',itemIds=['0'])['data']['recommendations']['items'][0]['resolved']['changed'])
        bad={'schemaVersion':1,'kind':'lens','reference':app.model.scope_reference(pid,self.current(pid)['graph'])}
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'SOURCE_NOT_LENS'):
            self.command(pid,'edit',nodeId='K',changes={'recommendations':[{'id':'bad','title':'Not a lens','targetRef':bad}]},cosmetic=False)
        self.assertEqual(before,self.sources())

    def test_owned_file_source_and_missing_item_are_explicit(self):
        pid=self.fixture();app=self.app();raw=b'A full authored evidence file'
        request=app.schema('attach_evidence',pid)['request'];request['contentBase64']=base64.b64encode(raw).decode()
        attached=app.request(request);pin=attached['packages'][0]['receipt']['effects']['evidenceRef']
        target={'schemaVersion':1,'kind':'file','packageId':pid,**pin}
        self.add_theory(pid,recommendations=[{'id':'file','title':'File material','targetRef':target}])
        value=self.read(pid,'recommendations',expand=True)['data']['recommendations']['items'][0]
        self.assertEqual(value['resolved']['content'],raw.decode());self.assertEqual(value['resolved']['sha256'],hashlib.sha256(raw).hexdigest())
        before=self.sources();bad=copy.deepcopy(target);bad['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'EVIDENCE_BYTES_UNAVAILABLE'):
            self.command(pid,'edit',nodeId='K',changes={'recommendations':[{'id':'bad','title':'Wrong bytes','targetRef':bad}]},cosmetic=False)
        self.assertEqual(before,self.sources())


class BoundedSources(unittest.TestCase):
    def test_private_addresses_credentials_and_redirects_are_rejected(self):
        S=T.SOURCES
        for url in ('http://example.org','https://user:secret@example.org','file:///etc/passwd','https://example.org:8443/a','https://example.org/\n'):
            with self.assertRaises(ValueError):S.url_parts(url)
        for ip in ('127.0.0.1','169.254.169.254','10.0.0.1','::1'):
            with patch.object(S.socket,'getaddrinfo',return_value=[(0,0,0,'',(ip,443))]):
                with self.assertRaisesRegex(ValueError,'PUBLIC_ADDRESS'):S.public_addresses('example.org')
        response=SimpleNamespace(status=302,getheader=lambda name,default=None:'https://127.0.0.1/private')
        class Connection:
            sock=None
            def __init__(self,*_):pass
            def request(self,*args,**kwargs):pass
            def getresponse(self):return response
            def close(self):pass
        calls=[]
        def addresses(host):
            calls.append(host)
            if host=='127.0.0.1':raise ValueError('private')
            return ['93.184.216.34']
        result=S.fetch_https({'uri':'https://example.org'},connection=Connection,addresses=addresses)
        self.assertEqual(result['status'],'unavailable');self.assertEqual(calls,['example.org','127.0.0.1'])

    def test_hash_media_encoding_and_size_are_explicit_states(self):
        S=T.SOURCES;data='Complete source'.encode()
        self.assertEqual(S.text_source(data,'text/plain','0'*64)['status'],'changed')
        self.assertEqual(S.text_source(data,'application/pdf')['status'],'unsupported-media')
        self.assertEqual(S.text_source(b'\xff','text/plain')['status'],'unsupported-encoding')
        self.assertEqual(S.text_source(data,'text/plain',hashlib.sha256(data).hexdigest())['content'],'Complete source')
        class Connection:
            sock=None
            def __init__(self,*_):self.data=io.BytesIO(b'x'*20)
            def request(self,*_,**__):pass
            def getresponse(self):return SimpleNamespace(status=200,getheader=lambda key,default=None:default,read1=self.data.read)
            def close(self):pass
        self.assertEqual(S.fetch_https({'uri':'https://example.org'},max_bytes=10,connection=Connection,addresses=lambda _:['93.184.216.34'])['status'],'budget-exceeded')


if __name__=='__main__':unittest.main()
