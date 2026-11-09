"""Candidate-v6 has closed built-in kinds and owner-scoped optional extensions."""
import copy
import json
import unittest
from pathlib import Path
from importlib.machinery import SourceFileLoader

ROOT=Path(__file__).resolve().parents[1]
M=SourceFileLoader('rdg_graph_apply_kinds',str(ROOT/'tools/graph-apply.py')).load_module()


def graph(id='normal-work',space='normal-work-space',**settings):
    return {'schemaVersion':1,'revision':1,'id':id,'title':'Isolated new-model graph',
      'identitySpace':space,'rootRequirementId':'R0','actionModel':'candidate-v6',
      'nodes':[{'id':'R0','kind':'requirement','title':'Active root','status':'active'}],
      'edges':[],'events':[],**settings}


class NodeTypePolicy(unittest.TestCase):
    def test_default_only_requirement_and_action(self):
        g=graph()
        M.validate(g)
        self.assertEqual(M.allowed_node_kinds(g),{'requirement','action'})
        for kind in ('context','question','proposal','decision','option','invented','custom-block'):
            invalid=copy.deepcopy(g)
            invalid['nodes'].append({'id':'BAD','kind':kind,'title':'Unknown or ungranted node'})
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'INVALID_OR_UNAPPROVED_NODE_KIND'):
                M.validate(invalid)

    def test_unknown_type_cannot_be_requested_as_extension(self):
        g=graph(nodeTypeExtensions=['custom-block'])
        with self.assertRaisesRegex(ValueError,'NODE_KIND_EXTENSION_NOT_GRANTED'):
            M.validate(g)

    def test_context_is_opt_in_only_for_explicitly_registered_owner(self):
        approved=graph('node-extension-example','rdg-explicit-context-example',
                       nodeTypeExtensions=['context'])
        approved['nodes'].append({'id':'CTX','kind':'context','title':'Real project-specific context'})
        M.validate(approved)
        self.assertIn('context',M.allowed_node_kinds(approved))
        for variant in (graph(nodeTypeExtensions=['context']),
                        graph('node-extension-example','wrong-identity',nodeTypeExtensions=['context']),
                        graph('wrong-graph-id','rdg-explicit-context-example',nodeTypeExtensions=['context'])):
            with self.assertRaisesRegex(ValueError,'NODE_KIND_EXTENSION_NOT_GRANTED'):
                M.validate(variant)
        missing_opt_in=graph('node-extension-example','rdg-explicit-context-example')
        missing_opt_in['nodes'].append(approved['nodes'][-1])
        with self.assertRaisesRegex(ValueError,'INVALID_OR_UNAPPROVED_NODE_KIND'):
            M.validate(missing_opt_in)

    def test_real_graph_edit_creates_optional_context_only_for_enabled_owner(self):
        template=graph('node-extension-example','rdg-explicit-context-example',
                       nodeTypeExtensions=['context'])
        event={'id':'EV-1','type':'graph_changed','operation':'create_context',
               'by':'assistant','authorityPrincipal':'bearer:tester',
               'note':'Optional Context has been intentionally activated for this owner'}
        patch={'schemaVersion':1,'expectedRevision':1,'operations':[{'op':'graph_edit',
                'action':'create_context','node':{'id':'CTX','kind':'context',
                   'title':'Project-specific additional node'},'event':event}]}
        result,changed=M.apply(template,patch,trusted_verified=True)
        self.assertTrue(changed)
        self.assertEqual(result['revision'],2)
        self.assertEqual(result['nodes'][-1]['kind'],'context')
        self.assertEqual(result['events'][-1]['operation'],'create_context')
        without_opt=copy.deepcopy(template)
        del without_opt['nodeTypeExtensions']
        with self.assertRaisesRegex(ValueError,'CREATE_CONTEXT_NOT_ENABLED_FOR_THIS_GRAPH'):
            M.apply(without_opt,patch,trusted_verified=True)
        wrong_owner=graph()
        with self.assertRaisesRegex(ValueError,'CREATE_CONTEXT_NOT_ENABLED_FOR_THIS_GRAPH'):
            M.apply(wrong_owner,patch,trusted_verified=True)

    def test_disallow_duplicate_extensions_and_base_kind_override(self):
        for values in (['context','context'],['requirement'],['action'],['context',5]):
            g=graph('node-extension-example','rdg-explicit-context-example',nodeTypeExtensions=values)
            with self.subTest(values=values),self.assertRaisesRegex(ValueError,'NODE_TYPE_EXTENSIONS_INVALID'):
                M.validate(g)

    def test_existing_legacy_sources_do_not_enable_legacy_kinds_in_new_graph(self):
        legacy=graph()
        legacy.pop('actionModel')
        legacy['nodes'].append({'id':'D','kind':'decision','title':'Archived only','status':'committed'})
        M.validate(legacy)
        new=copy.deepcopy(legacy)
        new['actionModel']='candidate-v6'
        with self.assertRaisesRegex(ValueError,'INVALID_OR_UNAPPROVED_NODE_KIND'):
            M.validate(new)

if __name__=='__main__':unittest.main()
