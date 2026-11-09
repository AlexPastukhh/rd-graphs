#!/usr/bin/env python3
"""Reproduce the OPEN semantic dependency gap in real Gendocen.

Exit 0 = BUG REPRODUCED, not product acceptance.
Exit 2 = different behavior (might be fixed; inspect).
Uses the existing co-located owner smoke runner and only tempfile fixtures.
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / "tools/rdg-gendocen-t1-history-smoke.py"
ANCHOR = '''        status_expect({"A1": "valid", "A2": "valid"}, "INITIAL_BASELINE")
        confirm_t1()
'''
INJECT = '''        status_expect({"A1": "valid", "A2": "valid"}, "INITIAL_BASELINE")
        confirm_t1()
        # Meaningful Plan reassignment: which Action belongs to which outcome
        # changes; time constraints and actionRefs do not change.
        original_branches = snapshot(pproj)["data"]["branchesById"]
        cases = plan["branches"][0]["cases"]
        cases[0]["stepIds"], cases[1]["stepIds"] = (
            cases[1]["stepIds"], cases[0]["stepIds"])
        plan["revision"] += 1
        project_plan()
        changed_branches = snapshot(pproj)["data"]["branchesById"]
        require(original_branches != changed_branches, "BRANCH_FIXTURE_NOT_CHANGED")
        _, checked = cli("check")
        review_status = {
            i["target"].rsplit("/", 1)[-1][:-3]: i["status"]
            for i in checked["data"]["results"]
        }
        print("OBSERVED_AFTER_BRANCH_SWAP=" +
              json.dumps(review_status, sort_keys=True), flush=True)
        if review_status == {"A1": "valid", "A2": "valid"}:
            print("GAP_REPRODUCED: actual branch membership changed; "
                  "Gendocen semantic reviews stayed valid.", flush=True)
            raise SystemExit(0)
        print("GAP_NOT_REPRODUCED: inspect whether conditional dependencies "
              "now correctly invalidate affected reviews.", flush=True)
        raise SystemExit(2)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-source", type=Path, required=True)
    args = parser.parse_args()
    if not (args.engine_source / "src/docengine/cli.py").is_file():
        parser.error("Gendocen source checkout not found")
    source = SOURCE.read_text(encoding="utf8")
    if source.count(ANCHOR) != 1:
        parser.error("Existing smoke runner changed; inspect source before reproducing")
    injected = source.replace(ANCHOR, INJECT)
    scope = {"__name__": "rdg_stage4_branch_audit", "__file__": str(SOURCE)}
    exec(compile(injected, str(SOURCE), "exec"), scope)
    scope["run"](args.engine_source)


if __name__ == "__main__":
    main()
