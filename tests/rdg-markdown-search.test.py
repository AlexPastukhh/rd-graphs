#!/usr/bin/env python3
"""B03B/B03C on real disposable Application owners."""
from contextlib import redirect_stdout
from importlib.machinery import SourceFileLoader
import io
import json
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
T = SourceFileLoader('document_fixture', str(ROOT/'tests/rdg-scoped-read.test.py')).load_module()
AGENT = T.T.A


class MarkdownSearch(unittest.TestCase):
    def setUp(self):
        self.fixture = T.ScopedReads()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.pid = self.fixture.fixture()
        self.app = self.fixture.app()

    def read(self, **request):
        return self.app.call({'method':'read', 'packageId':self.pid,
                              'format':'markdown', **request})

    def test_view_focus_branch_and_full_lens_read_without_writes(self):
        self.fixture.command(self.pid, 'work_graph', workGraph={
            'id':'WG', 'title':'Narrow area', 'rootIds':['R-STORE'], 'memberIds':['R-STORE','D-SQL'],
        })
        before = self.fixture.sources()
        full = self.read()
        self.assertEqual(full['scope']['kind'], 'graph')
        self.assertTrue(full['reading']['pagesComplete'])
        self.assertIn('общее вхождение', full['markdown'])
        anchors = re.findall(r'<a id="([^"]+)"></a>', full['markdown'])
        self.assertEqual(len(anchors), len(set(anchors)))
        links = re.findall(r'\]\(#(rdg-[a-f0-9]{24}) "(rdg:[^"]+)"\)', full['markdown'])
        self.assertTrue(links)
        self.assertTrue({anchor for anchor, _ in links} <= set(anchors))
        self.assertTrue(all(address.startswith('rdg:'+self.pid+'/') for _, address in links))
        area = self.read(view={'kind':'workGraph','id':'WG'})
        self.assertEqual(area['scope']['kind'], 'workGraph')
        self.assertEqual(area['scope']['view']['id'], 'WG')
        self.assertIn('D-SQL', [block.get('entityId') for block in area['blocks']])
        self.assertNotIn('D-FILE', [block.get('entityId') for block in area['blocks']])
        focus = self.read(detail='focus', nodeId='D-SQL')
        viewer = self.read(detail='full', view={'kind':'focus','id':'D-SQL'})
        self.assertEqual(focus['markdown'], viewer['markdown'])
        self.assertIn('Measured input', focus['markdown'])
        self.assertIn('Check consistency', focus['markdown'])
        self.assertIn('Wrong assumption', focus['markdown'])
        self.assertNotIn('D-FILE', [r.get('entityId') for r in focus['blocks']])
        branch = self.read(detail='branch', nodeId='R-STORE')
        self.assertIn('> # Free instructions', branch['markdown'])
        self.assertIn('R-DEEP', [r.get('entityId') for r in branch['blocks']])
        item = self.app.call({'method':'read','packageId':self.pid,'detail':'item','nodeId':'D-SQL'})
        self.assertEqual(item['item']['id'],'D-SQL')
        self.assertEqual(before, self.fixture.sources())

        form = self.app.schema('create',core_model='rdg-decision-v1',role='lens')['request']
        form.update(path='lenses/markdown-test',role='lens',lensKey='markdown-test',
                    title='Paper lens',scope='Disposable',rootReason='Synthetic method')
        lens = self.app.request(form)['packages'][0]['packageId']
        doc = self.app.call({'method':'read','format':'markdown','packageId':lens})
        self.assertIn('Paper lens',doc['markdown'])
        self.assertTrue(doc['reading']['pagesComplete'])

    def test_document_pages_snapshot_and_exact_assembly(self):
        from_read = self.app.read.__func__.__globals__['MARKDOWN']
        msg = {'method':'read','format':'markdown','packageId':self.pid,'detail':'branch','nodeId':'R-STORE'}
        full = self.app.call(msg)
        lengths = [len('\n'.join(full['markdown'].split('\n')[b['start']:b['end']]).encode())
                   for b in full['blocks']]
        budget = 2 * max(lengths) + 10000
        self.assertLess(budget,len(full['markdown'].encode()))
        with patch.object(from_read,'PAGE_BYTES',budget):
            first = self.app.call(msg)
            cursor = first['page']['nextCursor']
            self.assertTrue(cursor)
            self.assertFalse(first['reading']['pagesComplete'])
            self.assertIn('Частичная выдача',first['markdown'])
            joined = from_read.read_pages(self.app,msg,True)
            self.assertEqual(joined['markdown'],full['markdown'])
            self.assertTrue(joined['reading']['pagesComplete'])
            self.fixture.command(self.pid,'edit',nodeId='R-STORE',
                                 changes={'description':'Changed basis'},cosmetic=False)
            with self.assertRaisesRegex(ValueError,'MARKDOWN_CURSOR_STALE'):
                self.app.call({**msg,'cursor':cursor})

    def test_literal_search_fields_order_pages_and_permissions(self):
        self.fixture.command(self.pid,'edit',nodeId='R-STORE',changes={'title':'p95 target'},cosmetic=True)
        self.fixture.command(self.pid,'edit',nodeId='A-DEEP',changes={'resultCondition':'p95 below 300 ms'},cosmetic=False)
        self.fixture.command(self.pid,'edit',nodeId='CAN-SQL',changes={'canons':'p95 use the same profile'},cosmetic=False)
        before = self.fixture.sources()
        msg = {'method':'search','query':'P95','packageId':self.pid}
        found = self.app.call(msg)['items']
        hits = {r['ref']['nodeId']: r for r in found}
        self.assertTrue({'R-STORE','A-DEEP','CAN-SQL'} <= set(hits))
        self.assertTrue(all(i.startswith('OP-') for i in set(hits)-{'R-STORE','A-DEEP','CAN-SQL'}))
        self.assertEqual(found[0]['ref']['nodeId'],'R-STORE')
        self.assertEqual(hits['A-DEEP']['matches'][0]['field'],'resultCondition')
        self.assertEqual(hits['CAN-SQL']['target']['section'],'canon')
        self.assertEqual(self.app.call({**msg,'query':'[p95]'})['items'],[])
        self.assertEqual(self.app.call({**msg,'query':'d-sql'})['items'][0]['ref']['nodeId'],'D-SQL')
        cursor = self.app.call({**msg,'limit':1})['page']['nextCursor']
        self.assertEqual(self.app.call({**msg,'limit':1,'cursor':cursor})['items'],found[1:2])
        self.assertEqual(self.app.call({'method':'search','scope':'catalog','query':'p95'})['items'],found)
        self.assertEqual(before,self.fixture.sources())
        self.fixture.command(self.pid,'edit',nodeId='CAN-SQL',changes={'canons':'Different wording'},cosmetic=False)
        with self.assertRaisesRegex(ValueError,'SEARCH_CURSOR_STALE'):
            self.app.call({**msg,'limit':1,'cursor':cursor})
        self.fixture.authority.manage('revoke',self.fixture.admin,{'id':self.fixture.grant_id})
        with self.assertRaises(ValueError):
            self.app.call(msg)

    def test_agent_prints_raw_markdown_and_search_dispatch(self):
        config = {**self.fixture.config(), 'profile':'portable','packageId':self.pid}
        # CLI uses the normal parsed arguments and Application dispatch, while
        # the isolated test already supplies its authorized local client.
        for command, expected in [(['open','--format','markdown','--node','D-SQL'],'# Scope test'),
                                  (['search','--query','Check consistency'],'CAN-SQL')]:
            stdout = io.StringIO()
            with patch.object(AGENT,'config',return_value=config), \
                 patch.object(AGENT,'portable_application',return_value=self.app), \
                 patch.object(sys,'argv',['rdg-agent.py','--context','prepared',*command]), redirect_stdout(stdout):
                AGENT.main()
            self.assertIn(expected,stdout.getvalue())
            if command[0]=='open':
                self.assertTrue(stdout.getvalue().startswith('# '))


if __name__ == '__main__':
    unittest.main()
