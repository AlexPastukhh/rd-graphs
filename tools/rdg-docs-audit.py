#!/usr/bin/env python3
"""Read-only documentation consistency gate for the active RDG project.

No Markdown rewriting, no Graph mutations. Historical handoff snapshots and the
original v0.2 user-authored example are intentionally immutable and treated as
archive sources even without per-file banners. Docs status is closed by policy.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'docs/DOCS-POLICY.json'
REQUIREMENT_EXAMPLE='requirements-dependencies-demo'
LINK=re.compile(r'\[[^\]]+\]\(([^)]+)\)')

def read(path):return path.read_text(encoding='utf8')
def json_read(path):return json.loads(read(path))
def archived_status(rel,text,patterns):
    banner='> **СТАТУС: АРХИВ'
    if text.startswith(banner):return True
    # Registered reports may keep a title before their explicit archive banner.
    if not any(Path(rel).match(pattern) for pattern in patterns):return False
    lines=text.splitlines()
    return (len(lines)>2 and lines[0].startswith('# ') and lines[1]=='' and
            lines[2].startswith(banner))

def doc_anchors(text):
    """GitHub-style heading anchors and explicit IDs, excluding fenced code."""
    anchors=set();generated=set();fence=None
    for line in text.splitlines():
        marker=re.match(r'^\s{0,3}(`{3,}|~{3,})',line)
        if marker:
            token=marker.group(1)
            if fence is None:fence=(token[0],len(token))
            elif token[0]==fence[0] and len(token)>=fence[1]:fence=None
            continue
        if fence:continue
        anchors.update(re.findall(r'<(?:a|h[1-6])\b[^>]*\b(?:id|name)=["\']([^"\']+)["\']',line,re.I))
        match=re.match(r'^\s{0,3}#{1,6}\s+(.+?)\s*$',line)
        if not match:continue
        title=re.sub(r'\s+#+\s*$','',match.group(1))
        title=re.sub(r'\[([^\]]+)\]\([^)]+\)',r'\1',title)
        title=re.sub(r'<[^>]+>','',title).lower()
        base=re.sub(r'[^\w\- ]','',title).replace(' ','-')
        anchor=base;count=0
        while anchor in generated:count+=1;anchor=base+'-'+str(count)
        generated.add(anchor);anchors.add(anchor)
    return anchors


def link_problem(source,destination,*,check_fragment=True,cache=None):
    destination=destination.strip()
    if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',destination):return None
    file,sep,fragment=destination.partition('#')
    file=unquote(file.strip().strip('<>'));target=(source.parent/file) if file else source
    if not target.exists():return 'BROKEN_DOC_LINK: '+str(source)+' -> '+destination
    if check_fragment and sep and fragment and target.suffix.lower()=='.md':
        key=target.resolve();cache={} if cache is None else cache
        if key not in cache:cache[key]=doc_anchors(read(target))
        if unquote(fragment) not in cache[key]:return 'BROKEN_DOC_ANCHOR: '+str(source)+' -> '+destination
    return None


def ci_python_files(root):
    tree=ast.parse(read(root/'tools/rdg-ci.py'))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PYTHON_TESTS' for t in node.targets):
            return {'tests/'+name for name in ast.literal_eval(node.value)}
    raise ValueError('DOCS_CI_TEST_LIST_MISSING')


def trace_problem(root,path,case,*,mandatory=False,ci_files=()):
    target=root/path
    if not target.is_file():return 'DOC_TEST_FILE_MISSING: '+path
    try:tree=ast.parse(read(target))
    except SyntaxError:return 'DOC_TEST_PARSE_FAILED: '+path
    names={n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    if case not in names:return 'DOC_TEST_CASE_MISSING: '+path+'::'+case
    if mandatory and path not in ci_files:return 'DOC_TEST_NOT_IN_CI: '+path+'::'+case
    return None


def validate():
    problems=[];statistics={'markdownFiles':0,'normativeFiles':0,
                             'archivedFiles':0,'immutableSnapshots':0,'checkedLinks':0,'checkedAnchors':0,'checkedTestCases':0}
    def check(predicate,detail):
        if not predicate:problems.append(detail)
    policy=json_read(P)
    check(policy.get('schemaVersion')==1,'DOC_POLICY_SCHEMA_INVALID')
    normative=set(policy['normative'])
    anchors_cache={}
    try:ci_files=ci_python_files(ROOT)
    except (ValueError,SyntaxError) as exc:problems.append(str(exc));ci_files=set()
    check(len(normative)==len(policy['normative']),'DUPLICATE_NORMATIVE_DOC')
    for file in normative:
        check((ROOT/file).is_file(),'NORMATIVE_DOC_MISSING: '+file)
    # Preserve executable prompt import payloads and generated engine receipts:
    # they are source data, not documents for the current model. Directory
    # READMEs classify them as archived or engine-owned.
    check('work-kit/modules/**' in policy['immutableArchives'] and
          'kit/modules/**' in policy['immutableArchives'] and
          'docs/handoffs/**' in policy['immutableArchives'],
          'UNDECLARED_LEGACY_DOCUMENT_SOURCES')
    check('AGENTS.md' in normative,'DEVELOPER_ENTRY_NOT_NORMATIVE')
    check('docs/guides/RDG-CURRENT-STATE.md' in normative,'CURRENT_MAP_NOT_NORMATIVE')
    check('docs/guides/RDG-ACTIVE-CONTRACT.md' in normative,'SEMANTIC_CONTRACT_NOT_NORMATIVE')
    check('docs/guides/RDG-OPERATIONS.md' in normative,'OPERATIONS_RUNBOOK_NOT_NORMATIVE')
    # No unclassified doc may masquerade as part of the current model.
    sources=[ROOT/x for x in normative]
    # Existing archives are classified; retired files are not required to remain.
    for pattern in ('README-HISTORY.md','graphs/*.md','tests/visual/*.md',
                    'tests/legacy-set-contract/README.md','work-kit/*.md','kit/*.md'):
        sources+=list(ROOT.glob(pattern))
    sources+=list((ROOT/'docs').rglob('*.md'))
    sources=sorted(set(sources))
    for path in sources:
        check(path.is_file(),'REGISTERED_SOURCE_MISSING: '+str(path))
        if not path.is_file():continue
        rel=path.relative_to(ROOT).as_posix();text=read(path)
        statistics['markdownFiles']+=1
        immutable=((rel.startswith('docs/handoffs/') and rel!='docs/handoffs/README.md') or
                   rel=='docs/examples/requirements-decisions-graph-examples-v0.2.source.md')
        if immutable:
            statistics['immutableSnapshots']+=1
            # Genuine snapshot evidence: do not require modifying original bytes.
            continue
        is_normative=rel in normative
        if is_normative:
            statistics['normativeFiles']+=1
            check('СТАТУС:' in text[:430] and ('ДЕЙСТВУЮЩ' in text[:430] or 'АКТУАЛЬН' in text[:430]),
                  'NORMATIVE_STATUS_MISSING: '+rel)
        else:
            statistics['archivedFiles']+=1
            check(archived_status(rel,text,policy.get('archiveSources',[])),
                  'UNCLASSIFIED_OR_NOT_ARCHIVED: '+rel)
        # Relative links from all editable docs and labelled archives must work;
        # immutable snapshots had their own historical filesystem layouts.
        for found in LINK.finditer(text):
            destination=found.group(1).strip()
            if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',destination):continue
            statistics['checkedLinks']+=1
            if is_normative and '#' in destination:statistics['checkedAnchors']+=1
            problem=link_problem(path,destination,check_fragment=is_normative,cache=anchors_cache)
            if problem:problems.append(problem)
        if is_normative:
            for match in re.finditer(r'<!--\s*rdg-test(-ci)?:\s+(\S+)::(test_[A-Za-z0-9_]+)\s*-->',text):
                statistics['checkedTestCases']+=1
                problem=trace_problem(ROOT,match.group(2),match.group(3),mandatory=bool(match.group(1)),ci_files=ci_files)
                if problem:problems.append(problem)
    check(statistics['normativeFiles']==len(normative),'NORMATIVE_DOC_COUNT_INCORRECT')
    # Read primary sources, not copied counts from a previous README/version.
    viewer=read(ROOT/'tools/rd-graph-viewer.user.js')
    match=re.search(r'^// @version\s+(\d+\.\d+\.\d+)',viewer,re.M)
    check(bool(match),'SOURCE_VIEWER_VERSION_MISSING')
    if match:
        version=match.group(1)
        for rel in ('README.md','docs/guides/RDG-CURRENT-STATE.md'):
            check(version in read(ROOT/rel).splitlines()[2],
                  'DOCUMENTED_VIEWER_VERSION_STALE: '+rel+' source='+version)
    graph_path=ROOT/'graphs/workspaces'/REQUIREMENT_EXAMPLE/'graph.json'
    plan_path=ROOT/'plans'/REQUIREMENT_EXAMPLE/'plan.json'
    if graph_path.is_file() and plan_path.is_file():
        graph=json_read(graph_path);plan=json_read(plan_path)
        policy_kinds=json_read(ROOT/'tools/rdg-node-type-registry.json')['baseKinds']
        module_base=json_read(ROOT/'tools/rdg-module-registry.json')['base']
        check(module_base['nodeKinds']==policy_kinds and module_base['id']=='rdg-base' and module_base['version']==1,'MODULE_BASE_POLICY_DRIFT')
        publisher=json_read(ROOT/'tools/rdg-published-owners.json')['owners'][REQUIREMENT_EXAMPLE]
        catalog=json_read(ROOT/'graphs/catalog.json')
        reset=json_read(ROOT/'tools/rdg-resettable-examples.json')
        valid_kinds=set(graph.get('nodeTypeExtensions',[]))|set(policy_kinds)
        check(graph.get('actionModel')=='candidate-v6','TEACHING_GRAPH_OLD_MODEL')
        check(set(n['kind'] for n in graph['nodes'])<=valid_kinds,'UNREGISTERED_NODE_KIND_IN_EXAMPLE')
        check(not any(n['id']=='C-ASSURANCE' for n in graph['nodes']),'STALE_CONTEXT_NODE_REINTRODUCED')
        check(not any(e.get('type')=='CONTEXT_FOR' for e in graph['edges']),'STALE_CONTEXT_EDGE_REINTRODUCED')
        check(not graph.get('nodeTypeExtensions'),'TEACHING_EXAMPLE_MUST_USE_BASE_NODE_KINDS')
        check(catalog['entries'].get('workspaces/'+REQUIREMENT_EXAMPLE+'/graph.json',{}).get('folder')=='examples',
              'TEACHING_EXAMPLE_NOT_IN_EXAMPLES_FOLDER')
        check(set(reset.get('examples',{}))=={REQUIREMENT_EXAMPLE},'UNEXPECTED_RESETTABLE_EXAMPLE')
        check(publisher['graphRevision']==graph['revision'] and publisher['planRevision']==plan['revision'],
              'PUBLISHED_REVISIONS_DO_NOT_MATCH_OWNER')
        check(publisher['graphSha256']==hashlib.sha256(graph_path.read_bytes()).hexdigest(),
              'PUBLISHED_GRAPH_SHA_STALE')
        check(publisher['planSha256']==hashlib.sha256(plan_path.read_bytes()).hexdigest(),
              'PUBLISHED_PLAN_SHA_STALE')
        live=read(ROOT/'docs/guides/RDG-LIVE-TEACHING-WORKSPACE.md')
        for fragment in (f'Graph revision {graph["revision"]}',
                         f'Plan revision {plan["revision"]}',
                         f'{len(graph["nodes"])} R/A узлов',
                         f'{len(publisher["history"])} первичных provenance-записей',
                         f'{len(publisher["dependencies"]["rows"])} dependency targets'):
            check(fragment in live,'EXAMPLE_DOC_FACT_STALE: '+fragment)
    else:problems.append('CANONICAL_EXAMPLE_OWNER_MISSING')
    # DRY: rapidly changing example rev counts must stay in example page only,
    # not in generic contracts, README or reset runbook.
    for rel in ('README.md','docs/README.md','docs/guides/RDG-CURRENT-STATE.md',
                'docs/guides/RDG-ACTIVE-CONTRACT.md','docs/guides/RDG-OPERATIONS.md',
                'docs/guides/RDG-TEACHING-EXAMPLE-RESET.md'):
        check(not re.search(r'\b(?:Graph|Plan)\s+(?:revision\s+)?r\d+\b',read(ROOT/rel)),
              'DUPLICATED_MUTABLE_EXAMPLE_REVISION: '+rel)
    for rel in normative:
        text=read(ROOT/rel)
        check('Все связи и контекст (+1)' not in text and 'Graph r14' not in text,
              'HISTORICAL_UI_OR_CONTEXT_TREATED_AS_CURRENT: '+rel)
    return problems,statistics

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Validate docs and source invariants without writing')
    parser.add_argument('--json',action='store_true',help='Print machine-readable summary')
    parser.add_argument('--list-active',action='store_true',help='List active document paths from DOCS-POLICY without archive scanning')
    args=parser.parse_args()
    if args.list_active:
        if args.check or args.json:parser.error('--list-active cannot be combined with --check or --json')
        for file in sorted(json_read(P)['normative']):print(file)
        return 0
    problems,statistics=validate()
    if args.json:print(json.dumps({'ok':not problems,**statistics,'errors':problems},ensure_ascii=False,indent=2))
    else:
        print('RDG_DOCS_AUDIT', 'PASS' if not problems else 'FAIL',json.dumps(statistics,ensure_ascii=False))
        for detail in problems:print('DOCS_ERROR',detail)
    return 0 if not problems else 2
if __name__=='__main__':sys.exit(main())
