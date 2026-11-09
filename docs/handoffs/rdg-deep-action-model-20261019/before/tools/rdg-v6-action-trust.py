#!/usr/bin/env python3
"""Candidate-v6 trusted-boundary verification for material Action review.

Proofs require an out-of-band secret, not a claim embedded in a graph. A valid
MAC authenticates *the trusted issuer who held that secret*, not the human user.
Local graph hashes verify source integrity, not the real-world truth of canons.
No builtin proof issuer or default secret is provided.
"""
import hashlib
import hmac
import json
import os
import re
import time


def check(cond, text):
    if not cond:
        raise ValueError(text)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def proof_payload(package):
    claim = package.get('trustedApproval', {})
    return {'transactionId': package.get('transactionId'),
            'changes': package.get('changes'),
            'principal': claim.get('principal'),
            'expiresAt': claim.get('expiresAt'),
            'purpose': claim.get('purpose')}


MATERIAL_OPS = {'select_action', 'link_action_requirement', 'reconsider_action', 'transition_qrpe', 'graph_edit'}


def need_trust(package):
    return any(op.get('op') in MATERIAL_OPS
               for change in package.get('changes', [])
               for op in (change.get('patch') or {}).get('operations', [])) or any(
        (change.get('create') or {}).get('actionModel') == 'candidate-v6' and
        (any(n.get('kind') == 'action' and n.get('status') in ('selected', 'superseded')
             for n in (change.get('create') or {}).get('nodes', [])) or
         bool((change.get('create') or {}).get('events')))
        for change in package.get('changes', []))


def verify_transaction(package, now=None):
    """Fail closed for material reconsideration; no bypass via event.approvalRef."""
    if not need_trust(package):
        return False
    claim = package.get('trustedApproval')
    check(isinstance(claim, dict), 'TRUST_REQUIRED: missing trustedApproval')
    purposes = {'rdg-v6-material-action-v1'}
    # Historical pilot fixtures may still replay a single pure reconsideration.
    if all(op.get('op') == 'reconsider_action' for change in package['changes']
           for op in (change.get('patch') or {}).get('operations', [])) and all(
           'create' not in c for c in package['changes']):
        purposes.add('rdg-v6-action-reconsider-v1')
    check(claim.get('purpose') in purposes, 'TRUST_WRONG_PURPOSE')
    check(isinstance(claim.get('principal'), str) and claim['principal'].strip(),
          'TRUST_PRINCIPAL_REQUIRED')
    check(type(claim.get('expiresAt')) is int and
          (now if now is not None else time.time()) < claim['expiresAt'] <=
          (now if now is not None else time.time()) + 900,
          'TRUST_APPROVAL_EXPIRED_OR_TOO_LONG')
    key = os.environ.get('RDG_V6_TRUST_KEY', '')
    check(len(key.encode('utf-8')) >= 32, 'TRUST_UNAVAILABLE: no trusted issuer key')
    check(isinstance(claim.get('signature'), str) and
          re.fullmatch('[0-9a-f]{64}', claim['signature']), 'TRUST_SIGNATURE_REQUIRED')
    expected = hmac.new(key.encode('utf-8'), canonical(proof_payload(package)),
                        hashlib.sha256).hexdigest()
    check(hmac.compare_digest(expected, claim['signature']), 'TRUST_SIGNATURE_INVALID')
    for change in package['changes']:
        for op in (change.get('patch') or {}).get('operations', []):
            if op.get('op') in MATERIAL_OPS:
                ev = op.get('event', {})
                if op.get('op') != 'transition_qrpe':
                    check(ev.get('authorityPrincipal') == claim['principal'],
                          'TRUST_ACTOR_NOT_BOUND_TO_RECEIPT')
                if op.get('op') == 'transition_qrpe':
                    check(op.get('authorityPrincipal') == claim['principal'],
                          'TRUST_QRPE_ACTOR_NOT_BOUND_TO_RECEIPT')
                if op.get('op') == 'reconsider_action':
                    check(ev.get('by') == 'user', 'TRUST_REVIEW_REQUIRES_USER_ATTRIBUTION')
    return True


def verify_local_evidence(original, op):
    """Verify every evidence ref against the actual previous graph state."""
    old = {n['id']: n for n in original['nodes']}
    reviewer = old.get(op.get('reviewActionId'), {})
    ev = op.get('event', {})
    refs = [ref for check_record in ev.get('canonChecks', [])
            for ref in check_record.get('evidenceRefs', [])]
    refs.extend(ref for q in reviewer.get('qrpe', [])
                for ref in q.get('resolutionEvidenceRefs', []))
    lens_effect = ev.get('lensApplication', {}).get('effectQrpe', {})
    refs.extend(lens_effect.get('evidenceRefs', []))
    check(refs, 'EVIDENCE_MISSING')
    for ref in refs:
        check(isinstance(ref, str), 'EVIDENCE_UNSUPPORTED_REFERENCE')
        m = re.fullmatch(r'graph-node:([A-Za-z0-9_-]+)@([0-9a-f]{64})', ref)
        check(m is not None, 'EVIDENCE_UNSUPPORTED_REFERENCE: ' + str(ref))
        nid, digest = m.groups()
        check(nid in old, 'EVIDENCE_NODE_NOT_FOUND')
        check(hmac.compare_digest(fingerprint(old[nid]), digest),
              'EVIDENCE_STALE_OR_FORGED')
    return True
