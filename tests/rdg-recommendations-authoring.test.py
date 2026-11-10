#!/usr/bin/env python3
"""B02B authoring on disposable Application owners, no live catalog."""
import copy,json,uuid,unittest
from pathlib import Path
from importlib.machinery import SourceFileLoader
ROOT=Path(__file__).resolve().parents[1]
T=SourceFileLoader('recommendation_fixture',str(ROOT/'tests/rdg-decision-integration.test.py')).load_module()
class Recommendations(unittest.TestCase):
 setUp=T.DecisionIntegration.setUp
 config=T.DecisionIntegration.config
 app=T.DecisionIntegration.app
 req=T.DecisionIntegration.req
 current=T.DecisionIntegration.current
 sources=T.DecisionIntegration.sources
 command=T.DecisionIntegration.command
 command_request=T.DecisionIntegration.command_request
 decision=T.DecisionIntegration.decision
 work_lens=T.DecisionIntegration.work_lens
 graph=T.DecisionIntegration.graph
 def definition(self,pid,targets):
  app=self.app();g=app.read(pid)['graph'];lens=self.work_lens()
  return {'id':str(uuid.uuid4()),'revision':1,'key':'test-'+uuid.uuid4().hex,'title':'Authored advice','supplied':False,'authored':True,'rules':[{'id':'rule-'+str(i),'nodeKinds':[kind],'scope':'identity','state':'any','anchor':{'packageId':pid,'identitySpace':g['identitySpace'],'nodeId':nid,'kind':kind if kind in ('process','workGraph') else 'entity'},'whenText':'When useful','usageText':'Read or follow the method; decide what is useful','lensRefs':[{k:lens[k] for k in ('packageId','identitySpace','lensKey')}]} for i,(nid,kind) in enumerate(targets)]}
 def publish(self,pid,d):
  app=self.app();row=app.read(pid);req=self.req('recommendation_edit',expectedRegistryRevision=app.recommendation_catalog()['registryRevision'],action='create',definition=d,note='Explicit isolated advice',attachTo={'packageId':pid,'expectedPackageRevision':row['package']['revision'],'expectedGraphRevision':row['graph']['revision']});before=self.sources();pre=app.call({'method':'preflight','request':req});self.assertEqual(before,self.sources());result=app.call({'method':'apply','request':req,'expectedInputBinding':pre['inputBinding']});self.assertTrue(app.call({'method':'apply','request':req})['idempotent']);return result
 def test_all_targets_full_compact_text_and_no_default(self):
  pid=self.decision();app=self.app();self.assertEqual(app.read(pid)['recommendations']['matches'],[])
  for nid,kind,fields in [('CTX','context',{'value':'Fact'}),('CAN','canon',{'guidance':'Theory'}),('INFO','info',{'value':'Reference'}),('F','finding',{'subjectId':'D1','findingType':'risk','rationale':'A mechanism','evidenceIds':[]}),('Q','question',{'relatedRefs':[],'impact':'May matter','answerCondition':'Enough data'}),('EXT','action',{'actionType':'task','lowLevel':False,'targetIds':[],'groupIds':[]})]:self.command(pid,'add',entity={'id':nid,'kind':kind,'title':nid,'description':'',**fields},**({'location':'external'} if nid=='EXT' else {}))
  g=app.read(pid)['graph'];targets=[('R1','requirement'),('D1','decision'),('A1','action'),('CTX','context'),('CAN','canon'),('INFO','info'),('F','finding'),('Q','question'),('EXT','action'),(g['id'],'process'),('WG1','workGraph')];d=self.definition(pid,targets);self.publish(pid,d)
  full=app.read(pid);self.assertEqual({m['nodeId'] for m in full['recommendations']['matches']},{i for i,k in targets});before=self.sources()
  for nid,kind in targets:
   rec=app.call({'method':'read','packageId':pid,'detail':'item','nodeId':nid,'include':['recommendations']})['data']['recommendations']['items'];self.assertEqual(len(rec),1);self.assertEqual(rec[0]['whenText'],'When useful');self.assertTrue(rec[0]['target']['available'])
  self.assertEqual(before,self.sources());self.assertEqual(next(n for n in full['graph']['nodes'] if n['id']=='D1')['selectionState'],'discovered');self.assertFalse(any(e['type']=='lens_application_recorded' for e in full['graph']['events']))
 def test_separate_intents_cursor_and_atomic_bad_target(self):
  pid=self.decision();app=self.app();d=self.definition(pid,[('R1','requirement'),('R1','requirement')]);d['rules'][1]['usageText']='Different intent';self.publish(pid,d);matches=app.read(pid)['recommendations']['matches'];self.assertEqual(len(matches),2);self.assertNotEqual(matches[0]['recommendationId'],matches[1]['recommendationId'])
  page=app.call({'method':'read','packageId':pid,'detail':'item','nodeId':'R1','include':['recommendations'],'limit':1});cursor=page['data']['recommendations']['page']['nextCursor'];changed=copy.deepcopy(d);changed['revision']=2;changed['rules'][0]['usageText']='Edited';req=self.req('recommendation_edit',expectedRegistryRevision=app.recommendation_catalog()['registryRevision'],action='edit',packageId=d['id'],definition=changed,note='Explicit change');app.request(req)
  with self.assertRaisesRegex(ValueError,'CURSOR_STALE'):app.call({'method':'read','packageId':pid,'detail':'item','nodeId':'R1','include':['recommendations'],'limit':1,'cursor':cursor})
  bad=self.definition(pid,[('R1','requirement')]);bad['rules'][0]['lensRefs'][0]['packageId']=str(uuid.uuid4());before=self.sources()
  with self.assertRaises(ValueError):self.publish(pid,bad)
  self.assertEqual(before,self.sources())
 def test_copy_remaps_advice_and_keeps_original_unchanged(self):
  pid=self.decision();app=self.app();d=self.definition(pid,[('D1','decision'),('WG1','workGraph'),(app.read(pid)['graph']['id'],'process')]);self.publish(pid,d);original=app.read(pid)['graph'];req=app.schema('copy',pid)['request'];req.update(path='copy/recommendations',note='Independent authored advice');copied=app.request(req)['packages'][0]['packageId'];row=app.read(copied);self.assertEqual(len(row['recommendations']['matches']),3);self.assertNotEqual(row['graph']['recommendationPackageIds'],original['recommendationPackageIds']);self.assertEqual(app.read(pid)['graph'],original)
 def test_template_process_advice_does_not_expand_to_receiving_owner(self):
  pid=self.decision();app=self.app();d=self.definition(pid,[(app.read(pid)['graph']['id'],'process'),('D1','decision')]);self.publish(pid,d)
  req=app.schema('capture_ready',pid)['request'];req.update(path='ready/advice',recommendationIds=[d['id']],note='Reusable scoped advice');ready=app.request(req)['packages'][0]['packageId']
  req=app.schema('apply_ready',pid,source_id=ready)['request'];req.update(mode='ADD_ROOT',note='Explicit template insertion');app.request(req);row=app.read(pid);process_hits=[m for m in row['recommendations']['matches'] if m['nodeId']==row['graph']['id']];self.assertEqual(len(process_hits),1);self.assertTrue(any(x['reason']=='instance-process-scope-not-transferable' for x in row['recommendations']['diagnostics']))
 def test_wrong_anchor_kind_is_rejected_without_writes(self):
  pid=self.decision();bad=self.definition(pid,[('R1','requirement')]);bad['rules'][0]['anchor']['kind']='workGraph';before=self.sources()
  with self.assertRaisesRegex(ValueError,'ANCHOR_KIND'):self.publish(pid,bad)
  self.assertEqual(before,self.sources())
 def test_wrong_profile_and_text_are_rejected_without_writes(self):
  pid=self.decision();app=self.app();d=self.definition(pid,[('R1','requirement')]);bad=copy.deepcopy(d);bad['rules'][0]['whenText']=None;before=self.sources()
  with self.assertRaises(ValueError):self.publish(pid,bad)
  self.assertEqual(before,self.sources());old=app.request(self.req('create',path='lens/old',role='lens',lensKey='old',graph=self.graph('legacy',paper=True)))['packages'][0]['packageId'];g=app.read(old)['graph'];bad['rules'][0]['whenText']='';bad['rules'][0]['lensRefs']=[{'packageId':old,'identitySpace':g['identitySpace'],'lensKey':'old'}];before=self.sources()
  with self.assertRaisesRegex(ValueError,'REFERENCE_MISSING:lens'):self.publish(pid,bad)
  self.assertEqual(before,self.sources())
if __name__=='__main__':unittest.main()
