const {test}=require('node:test'),assert=require('node:assert/strict');
const {simulate}=require('./viewer-test-helper.cjs');
const rows=u=>u.ids['graph-list'].children;
