#!/usr/bin/env python3
"""Portable, advisory Lens notes in ready graphs and between prepared Lenses."""
import copy
import json
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
GRAPH=SourceFileLoader('ready_advice_graph_validator',str(ROOT/'tools/graph-apply.py')).load_module()
CORE=GRAPH.core_model()

class AdvisoryRecommendations(unittest.TestCase):
    def test_ready_template_preserves_advice_on_full_copy_only(self):
        g=json.loads((ROOT/'graphs/examples/reference-prepared-planning-tree/graph.json').read_text())
        self.assertTrue(g.get('readOnly') and g.get('templateOnly'))
        root=g['nodes'][0]['id']
        g['lensRecommendations']=[
            {'lensKey':'review','text':'Inspect method applicability before actual selection.'},
            {'lensKey':'clarify','targetId':root,'text':'Clarify the expected result of this root R.'}]
        GRAPH.validate(g)
        copied=copy.deepcopy(g)
        self.assertEqual(copied['lensRecommendations'],g['lensRecommendations'])
        self.assertTrue(copied['templateOnly'],'copy cannot become an executed work owner')
        for wrong in ('MISSING', ''):
            invalid=copy.deepcopy(g)
            invalid['lensRecommendations'][1]['targetId']=wrong
            with self.assertRaisesRegex(ValueError,'CORE_LENS_RECOMMENDATION'):
                GRAPH.validate(invalid)

    def test_prepared_lenses_recommend_others_without_command_edges(self):
        catalog=json.loads((ROOT/'tools/rdg-agent-lenses/catalog.json').read_text())
        entries={e['key'] for e in catalog['entries']}
        for key in ('work','review'):
            g=json.loads((ROOT/'tools/rdg-agent-lenses'/f'{key}.json').read_text())
            CORE.validate(g)
            recommendations=CORE.validate_lens_recommendations(g)
            self.assertTrue(recommendations)
            self.assertTrue(all(row['lensKey'] in entries for row in recommendations))
            self.assertTrue(all('targetId' not in row or row['targetId'] in CORE.entities(g)
                                for row in recommendations))
            self.assertFalse(any(e['type'] in ('APPLY_LENS','RUN_LENS') for e in g['edges']))
            self.assertFalse(any(n.get('result',{}).get('state')=='confirmed' for n in g['nodes']))

if __name__=='__main__':unittest.main()
