#!/usr/bin/env python3
"""Explicit profile selector for the shared RDG Application.

The legacy kernel remains the owner of rdg-core-v1. Decision v1 has its own
pure kernel; shared Application paths dispatch here before model-specific
validation or effects. Unknown profiles fail closed.
"""
from importlib.machinery import SourceFileLoader
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_CACHE = {}


def for_profile(profile):
    if profile not in ("rdg-core-v1", "rdg-decision-v1"):
        raise ValueError("UNSUPPORTED_PROFILE_CAPABILITY")
    if profile not in _CACHE:
        filename = "rdg-core-model.py" if profile == "rdg-core-v1" else "rdg-decision-model.py"
        module_name = "rdg_profile_" + profile.replace("-", "_")
        _CACHE[profile] = SourceFileLoader(module_name, str(_ROOT / filename)).load_module()
    return _CACHE[profile]


def for_graph(graph):
    if not isinstance(graph, dict):
        raise ValueError("UNSUPPORTED_PROFILE_CAPABILITY")
    return for_profile(graph.get("coreModel"))


PROFILE = "rdg-core-v1"
COMMANDS = for_profile(PROFILE).COMMANDS
DEPENDENCY_TYPES = for_profile(PROFILE).DEPENDENCY_TYPES
PAIRS = for_profile(PROFILE).PAIRS
def commands_for(graph):
    return for_graph(graph).COMMANDS


def dependency_types_for(graph):
    return for_graph(graph).DEPENDENCY_TYPES


def entities(graph):
    return for_graph(graph).entities(graph)


def active_edges(graph):
    return for_graph(graph).active_edges(graph)


def validate(graph):
    return for_graph(graph).validate(graph)


def validate_role(graph, role, plan=None):
    return for_graph(graph).validate_role(graph, role, plan)


def detached_components(graph, work_graph_id=None):
    return for_graph(graph).detached_components(graph, work_graph_id)


def native_dependency_edges(graph):
    return for_graph(graph).native_dependency_edges(graph)


def semantic_projection(graph, node_id, level="L1"):
    return for_graph(graph).semantic_projection(graph, node_id, level)


def completion_state(graph, actual_roots=None):
    profile = for_graph(graph)
    if graph.get("coreModel") == "rdg-decision-v1":
        return profile.completion_state(graph)
    return profile.completion_state(graph, actual_roots)


def pins(graph, node_id):
    return for_graph(graph).pins(graph, node_id)


def focused_view(graph, node_id):
    return for_graph(graph).focused_view(graph, node_id)
def apply(original, patch, trusted_verified=False, *, coordinated=False, paper=False):
    profile = for_graph(original)
    if original['coreModel'] == 'rdg-decision-v1':
        return profile.apply(original, patch, trusted_verified,
                             coordinated=coordinated, paper=paper)
    return profile.apply(original, patch, trusted_verified, coordinated=coordinated)


def blank(ident, title, space, root, root_title, scope="Specified working scope",
          core_model=None, root_reason=None):
    profile = core_model or PROFILE
    if profile == "rdg-core-v1":
        # The shared create-schema can carry a Decision-only rootReason field.
        # It is irrelevant to the immutable legacy core profile.
        return for_profile(profile).blank(ident, title, space, root, root_title, scope)
    return for_profile(profile).blank(ident, title, space, root, root_title, scope,
                                      root_reason or "Explicit primary reason for this process")


def affected(before, after, changed, *, cosmetic_ids=()):
    left, right = for_graph(before), for_graph(after)
    if left is not right:
        raise ValueError("UNSUPPORTED_PROFILE_CAPABILITY")
    return left.affected(before, after, changed, cosmetic_ids=cosmetic_ids)


def support_state(graph):
    return for_graph(graph).support_state(graph)


def group_visibility(graph, show_excluded=False):
    profile = for_graph(graph)
    if not hasattr(profile, "group_visibility"):
        return []
    return profile.group_visibility(graph, show_excluded)


def guard(node, event, operation="edit"):
    # This node-only legacy helper cannot infer a Decision Requirement/Action.
    # Decision callers must select for_graph(graph) before calling guard.
    return for_profile(PROFILE).guard(node, event, operation)


def external_pin_key(ref):
    return for_profile(PROFILE).external_pin_key(ref)


def fact_record(source, owner, event_id, relation):
    return for_graph(source).fact_record(source, owner, event_id, relation)


def argument_leaves(condition):
    return for_profile(PROFILE).argument_leaves(condition)


def validate_lens_recommendations(graph):
    profile = for_graph(graph)
    validator = getattr(profile, "validate_lens_recommendations", None)
    if validator is None:
        raise ValueError("UNSUPPORTED_PROFILE_CAPABILITY")
    return validator(graph)
