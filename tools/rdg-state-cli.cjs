#!/usr/bin/env node
'use strict';
const fs=require('node:fs'),core=require('./rdg-state.js');
try{
 const input=JSON.parse(fs.readFileSync(0,'utf8'));
 const result=input.action==='validate'?core.validate(input.items,input.options):core.collect(input);
 process.stdout.write(JSON.stringify(result));
}catch(error){process.stderr.write(error.message+'\n');process.exitCode=2;}
