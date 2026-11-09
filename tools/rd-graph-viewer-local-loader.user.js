// ==UserScript==
// @name         R-D Graph Viewer Local Loader
// @namespace    local.rdg.viewer/loader
// @version      2.5.2
// @description  Load local graph data and viewer via @require without file:// XHR.
//
// @match        https://chatgpt.com/*
// @match        https://chat.openai.com/*
//
// @run-at       document-idle
// @noframes
//
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_xmlhttpRequest
//
// @require      file:///C:/Users/alexa/Repos/rd-graphs/tools/rd-graph-data.js
// @require      file:///C:/Users/alexa/Repos/rd-graphs/tools/rd-graph-viewer.user.js
//
// @updateURL    none
// @downloadURL  none
// ==/UserScript==

(() => {
  'use strict';
  const host = document.getElementById('rdg-viewer-root');
  if (!host || typeof host.rdgStart !== 'function') {
    console.error('[RDG Loader v2.5.2] Viewer not initialized from local @require.');
    return;
  }
  const request = typeof GM_xmlhttpRequest === 'function' ? GM_xmlhttpRequest : null;
  const bundle = typeof globalThis !== 'undefined' ? globalThis.RDG_EMBEDDED_GRAPHS : null;
  console.info('[RDG Loader v2.5.2] Viewer:', host.dataset.rdgVersion,
    '; bundled graphs:', Array.isArray(bundle?.graphs) ? bundle.graphs.length : 0,
    '; GM request:', request ? 'available' : 'not available');
  // Bundled data work even if an independent file:// XMLHttpRequest is forbidden.
  void host.rdgStart(request);
})();
