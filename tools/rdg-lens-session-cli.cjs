#!/usr/bin/env node
'use strict';
// Human/AI entry point: pure read-only semantic session, optional candidate
// capture, and optional metadata-only lookup. It NEVER writes graphs.
const fs=require('node:fs');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const {createSession,hash}=require('./rdg-lens-session.cjs');
const {capture,lastRelevant}=require('./rdg-lens-research.cjs');
const flags=process.argv.slice(2);
function arg(name,required=false){const idx=flags.indexOf(name);
 if(idx<0){if(required)throw Error(name+' required');return null;}
 if(!flags[idx+1]||flags[idx+1].startsWith('--'))throw Error(name+' must have a filename');
 return flags[idx+1];}
function load(name,required=false){const filename=arg(name,required);
 return filename?JSON.parse(fs.readFileSync(filename,'utf8')):null;}
function githubResearch(cmd,meta){
 const py=path.join(__dirname,'rdg-github-research-cli.py');
 const r=spawnSync('python3',[py,cmd],{encoding:'utf8',
  input:meta?JSON.stringify(meta):undefined,maxBuffer:8*1024*1024});
 if(r.status!==0)throw Error('GITHUB_LOOKUP_FAILED: '+(r.stderr||r.stdout).slice(-500));
 return JSON.parse(r.stdout);
}
function main(){
 if(flags.includes('--saved-metadata')&&flags.includes('--github-metadata'))
  throw Error('Choose either local metadata or GitHub lookup');
 if(flags.includes('--open-previous')&&!flags.includes('--github-metadata'))
  throw Error('--open-previous requires --github-metadata');
 const lens=load('--lens',true),bindings=load('--bindings',true);
 const assessment=load('--assessments')||{};
 const session=createSession(lens,bindings,assessment);
 const requested=load('--persistence');
 const recording=requested?capture(session,requested,new Date().toISOString()):{saved:false};
 const remote=flags.includes('--github-metadata');
 const metadata=remote?githubResearch('--list'):load('--saved-metadata');
 const previous=metadata?lastRelevant(metadata,{
  lensId:session.lensId,definitionDigest:session.definitionDigest,
  ...bindings,evidenceStillValid:!remote&&assessment.evidenceStillValid===true}):{found:false};
 const previousResearch=(remote&&flags.includes('--open-previous')&&previous.found)?
  githubResearch('--open',previous.metadata):null;
 process.stdout.write(JSON.stringify({session,persistence:recording,previous,
  ...(previousResearch?{previousResearch}:{})},null,2)+'\n');
}
try{main();}catch(e){process.stderr.write('LENS_CLI_ERROR: '+e.message+'\n');process.exitCode=2;}
