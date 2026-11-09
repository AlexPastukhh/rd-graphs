#!/usr/bin/env python3
"""Opt-in, read-only GitHub Lens archive discovery, without implicit graph load.

Caller must configure RDG_GITHUB_REPOSITORY and GITHUB_TOKEN explicitly.
Listing reads only small metadata sidecars. Full research is fetched only when
--open is requested, bound to the selected metadata + expected Git blob SHA.
"""
import argparse
import json
import os
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

mod = SourceFileLoader('rdg_github_research_store', str(Path(__file__).with_name('rdg-github-store.py'))).load_module()


def main():
    parser = argparse.ArgumentParser()
    mutually = parser.add_mutually_exclusive_group(required=True)
    mutually.add_argument('--list', action='store_true')
    mutually.add_argument('--open', action='store_true')
    args = parser.parse_args()
    repo = os.environ.get('RDG_GITHUB_REPOSITORY')
    if not repo:
        raise ValueError('RDG_GITHUB_REPOSITORY is required for opt-in read')
    branch = os.environ.get('RDG_GITHUB_BRANCH', 'main')
    storage = mod.GithubGraphStore(mod.GithubContentsTransport(repo, branch))
    if args.list:
        print(json.dumps(storage.list_research_metadata(), ensure_ascii=False))
    else:
        metadata = json.load(sys.stdin)
        print(json.dumps(storage.load_research(metadata), ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('RDG_GITHUB_RESEARCH_ERROR: ' + str(exc), file=sys.stderr)
        sys.exit(2)
