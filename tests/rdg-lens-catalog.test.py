#!/usr/bin/env python3
"""Catalog is readable without owners; definitions stay ordinary, potential R/A."""
import copy
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
A=SourceFileLoader('lens_catalog_agent',str(ROOT/'tools/rdg-agent.py')).load_module()


class Catalog(unittest.TestCase):
    def test_guidance_is_readable_without_owner_or_credentials(self):
        env={k:v for k,v in os.environ.items() if k not in
             ('RDG_AUTH_STORE','RDG_AUTH_TOKEN','RDG_AGENT_CONTEXT')}
        for command in [('lenses',),('lens','--lens','explore')]:
            result=subprocess.run(['python3','-B',str(ROOT/'tools/rdg-agent.py'),*command],
                capture_output=True,text=True,env=env,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            data=json.loads(result.stdout)
            self.assertEqual(data['graphWrites'],0)
            self.assertEqual(data['planWrites'],0)
            if command[0]=='lenses':
                self.assertFalse(data['requiresOwnerContext'])
                self.assertTrue(any(x['key']=='clarify' for x in data['lenses']))
                self.assertTrue(any(x['key']=='preserve' for x in data['lenses']))
                self.assertFalse(any(x['id']=='three-block-criteria' for x in data['limitations']))
            else:
                self.assertFalse(data['bound'])
                self.assertTrue(data['validated'])

    def test_every_active_document_has_a_resolvable_instruction_route(self):
        catalog=A.read_lens_catalog()
        policy=json.loads((ROOT/'docs/DOCS-POLICY.json').read_text())
        routes=catalog['instructionCoverage']
        self.assertEqual(set(policy['normative']),{r['source'] for r in routes})
        for route in routes:
            self.assertTrue((ROOT/route['source']).is_file())
            graph=A.lens_definition(route['lens'])[2]
            self.assertIn(route['nodeId'],{n['id'] for n in graph['nodes']})
        shape=A.lens_definition('shape')[2]
        self.assertFalse(any(q['id']=='Q-THREE-CRITERIA'
            for n in shape['nodes'] for q in n.get('qrpe',[])))
        self.assertIn('preserve',next(e for e in catalog['entries'] if e['key']=='shape')['companions'])
        preserve=A.lens_definition('preserve')[2]
        self.assertFalse({'R-PRESERVE-C1','R-PRESERVE-C2','R-PRESERVE-C3'} & {n['id'] for n in preserve['nodes']})
        canon=next(n for n in preserve['objects'] if n['kind']=='canon')
        condition=canon['arguments'][0]['condition']
        self.assertEqual({'C1','C2'},{x['id'] for x in condition['all'][0]['any']})
        self.assertEqual(condition['all'][1]['id'],'C3')

    def test_all_definitions_use_existing_base_types_and_potential_branches(self):
        catalog=A.read_lens_catalog()
        definitions=[]
        for entry in catalog['entries']:
            if 'definition' not in entry:continue  # Decision-only fundamentals have no fake legacy variant.
            graph=A.lens_definition(entry['key'])[2]
            self.assertEqual(graph['events'],[])
            self.assertEqual({n['kind'] for n in graph['nodes']},{'requirement','action'})
            self.assertTrue(all(n['status']=='candidate' for n in graph['nodes'] if n['kind']=='action'))
            self.assertTrue(all(n['status']=='potential' for n in graph['nodes']
                if n['kind']=='requirement' and n['id']!=graph['rootRequirementId']))
            self.assertEqual(graph['coreModel'],'rdg-core-v1')
            self.assertFalse(any(e['type']=='OUTCOME_OF' for e in graph['edges']))
            self.assertTrue(any(e['type']=='CANON_FOR' for e in graph['edges']))
            if entry['key'] not in ('preserve','checkpoint'):self.assertTrue(any(e['type']=='INTRODUCES' for e in graph['edges']))
            definitions.append(graph)
        code="""const fs=require('node:fs'),m=require(process.argv[1]);
const graphs=JSON.parse(fs.readFileSync(0,'utf8'));
for(const g of graphs)m.parsePreparedLens(g);
console.log(graphs.length);
"""
        result=subprocess.run(['node','-e',code,str(ROOT/'tools/rdg-lens-session.cjs')],
            input=json.dumps(definitions),capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(int(result.stdout),len(definitions))

    def test_all_decision_definitions_are_readonly_profile_specific_graphs(self):
        definitions=[]
        for entry in A.read_lens_catalog()['entries']:
            graph=A.lens_definition(entry['key'],'rdg-decision-v1')[2]
            A.PORTABLE.module('rdg-model-profiles').validate_role(graph,'lens')
            self.assertEqual(graph['events'],[]);self.assertTrue(all(n['selectionState']=='discovered' for n in graph['nodes'] if n['kind']=='decision'))
            self.assertTrue(any(e['type']=='CANON_FOR' for e in graph['edges']));definitions.append(graph)
            out=subprocess.run(['python3','-B',str(ROOT/'tools/rdg-agent.py'),'lens','--lens',entry['key'],'--model-profile','rdg-decision-v1'],capture_output=True,text=True,timeout=30,env={k:v for k,v in os.environ.items() if k not in ('RDG_AUTH_STORE','RDG_AUTH_TOKEN','RDG_AGENT_CONTEXT')})
            self.assertEqual(out.returncode,0,out.stderr);self.assertEqual(json.loads(out.stdout)['graph']['coreModel'],'rdg-decision-v1')
        code="const fs=require('node:fs'),m=require(process.argv[1]);for(const g of JSON.parse(fs.readFileSync(0,'utf8')))m.parsePreparedLens(g);"
        out=subprocess.run(['node','-e',code,str(ROOT/'tools/rdg-lens-session.cjs')],input=json.dumps(definitions),capture_output=True,text=True,timeout=30);self.assertEqual(out.returncode,0,out.stderr);self.assertEqual(len(definitions),15)

    def with_copy(self):
        temp=tempfile.TemporaryDirectory(prefix='rdg-lens-catalog-')
        self.addCleanup(temp.cleanup)
        tools=Path(temp.name)/'tools'
        shutil.copytree(ROOT/'tools/rdg-agent-lenses',tools/'rdg-agent-lenses')
        return tools,tools/'rdg-agent-lenses/catalog.json'

    def test_registered_extension_needs_no_new_python_whitelist(self):
        tools,path=self.with_copy()
        catalog=json.loads(path.read_text())
        entry=copy.deepcopy(catalog['entries'][0])
        entry.update(key='custom',definition='custom.json',companions=[])
        graph=A.lens_definition('orient')[2]
        graph.update(id='custom-lens',identitySpace='custom-lens-space')
        (path.parent/'custom.json').write_text(json.dumps(graph))
        catalog['entries'].append(entry);path.write_text(json.dumps(catalog))
        with patch.object(A,'TOOLS',tools):
            self.assertEqual(A.lens_definition('custom')[2]['id'],'custom-lens')
            self.assertIn('custom',{r['key'] for r in A.lens_catalog()['lenses']})

    def test_unregistered_paths_duplicates_and_symlinks_are_rejected(self):
        tools,path=self.with_copy()
        good=json.loads(path.read_text())
        with patch.object(A,'TOOLS',tools):
            for name in ('../private','/etc/passwd','not-registered'):
                with self.assertRaisesRegex(ValueError,'LENS_NOT_AVAILABLE'):
                    A.lens_definition(name)
            bad=copy.deepcopy(good);bad['entries'][0]['definition']='../outside.json'
            path.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,'UNSAFE_LENS_DEFINITION'):A.read_lens_catalog()
            bad=copy.deepcopy(good);bad['entries'].append(bad['entries'][0])
            path.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,'LENS_CATALOG_KEY'):A.read_lens_catalog()
            path.write_text(json.dumps(good))
            definition=path.parent/good['entries'][0]['definition']
            outside=path.parent.parent/'outside.json';definition.rename(outside)
            definition.symlink_to(outside)
            with self.assertRaisesRegex(ValueError,'UNSAFE_LENS_DEFINITION'):A.read_lens_catalog()


if __name__=='__main__':unittest.main()
