#!/usr/bin/env python3
"""Validate author-owned general chat commands and publish one bulk read-only manifest.

The RDG lens catalog is checked for typed identity only. No command text is
inferred from lens Markdown and no Graph/runtime mutation occurs during build.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "kit/helper-commands/commands.json"
# V1 remains public for installed v0.40.9 helpers.
LEGACY_OUTPUT = ROOT / "kit/helper-commands/catalog.json"
# V2 is a distinct public endpoint so old cache refresh never breaks.
OUTPUT = ROOT / "kit/helper-commands/catalog-v2.json"
LENSES = ROOT / "tools/rdg-agent-lenses/catalog.json"
PROFILE = "rdg-decision-v1"
KEY = re.compile(r"^[a-z][a-z0-9-]{0,79}$")
COMMAND_ID = re.compile(r"^rdg\.command\.[a-z][a-z0-9-]{0,79}$")
SECRET = re.compile(r"(?i)(?:ghp_[A-Za-z0-9]{20}|Bearer\s+[A-Za-z0-9._~+/-]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)")
KINDS = {"lens-launcher", "workflow", "instruction"}


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def check_text(value, limit, label):
    require(isinstance(value, str) and value.strip() and len(value) <= limit
            and not SECRET.search(value), "RDG_COMMAND_TEXT:" + label)


def lens_keys():
    data = json.loads(LENSES.read_bytes())
    require(data.get("schemaVersion") == 1 and isinstance(data.get("entries"), list),
            "RDG_LENS_CATALOG_SCHEMA")
    keys = set()
    for item in data["entries"]:
        key = item.get("key")
        require(isinstance(key, str) and KEY.fullmatch(key) and key not in keys,
                "RDG_LENS_IDENTITY")
        require(PROFILE in item.get("profileDefinitions", {}), f"RDG_LENS_PROFILE:{key}")
        keys.add(key)
    require(bool(keys), "RDG_LENS_EMPTY")
    return keys


def initial_text(key, title):
    # Used only with --init, which never overwrites an existing owner source.
    return (
        f"Примени существующую линзу RDG «{title}» (lensKey: {key}) к текущей задаче.\n\n"
        "Сначала через доступный авторизованный RDG Agent/API прочитай её АКТУАЛЬНОЕ полное "
        "структурированное определение. Из корня rd-graphs доступна команда:\n"
        f"python3 -B tools/rdg-agent.py lens --lens {key} --model-profile {PROFILE} "
        "--context <подготовленный-RDG-context>\n"
        "Через RDG lenses подтверди role=lens, lensKey, identity и revision. Используй реальные "
        "связи, Canon/Info и применимые источники. Если API недоступен, сообщи об ограничении. "
        "Не создавай Graph или Action лишь из-за этой команды."
    )


def initialize():
    require(not SOURCE.exists(), "RDG_COMMAND_SOURCE_ALREADY_EXISTS")
    definitions = json.loads(LENSES.read_bytes())["entries"]
    commands = []
    for item in definitions:
        key = item["key"]
        commands.append({
            "id": f"rdg.lens.{key}", "kind": "lens-launcher",
            "title": item["title"], "description": item["purpose"][:300],
            "groupId": "lenses",
            "lensRefs": [{"role": "lens", "lensKey": key, "modelProfile": PROFILE}],
            "insertText": initial_text(key, item["title"]),
        })
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    SOURCE.write_bytes(encode({
        "schemaVersion": 2,
        "groups": [{"id": "lenses", "title": "Линзы", "description": "Адресные команды линз RDG"}],
        "commands": commands,
    }))
    print(f"Initialized author-owned RDG commands: {len(commands)}")


def validate():
    data = json.loads(SOURCE.read_bytes())
    require(isinstance(data, dict) and set(data) == {"schemaVersion", "groups", "commands"}
            and data["schemaVersion"] == 2, "RDG_COMMAND_SOURCE_SCHEMA")
    groups = data["groups"]
    require(isinstance(groups, list) and 1 <= len(groups) <= 30, "RDG_COMMAND_GROUP_COUNT")
    group_ids = set()
    for group in groups:
        require(isinstance(group, dict) and set(group) == {"id", "title", "description"},
                "RDG_COMMAND_GROUP_FIELDS")
        gid = group["id"]
        require(isinstance(gid, str) and KEY.fullmatch(gid) and gid not in group_ids,
                "RDG_COMMAND_GROUP_ID")
        check_text(group["title"], 160, f"group:{gid}:title")
        check_text(group["description"], 500, f"group:{gid}:description")
        group_ids.add(gid)

    commands = data["commands"]
    require(isinstance(commands, list) and 1 <= len(commands) <= 250, "RDG_COMMAND_SOURCE_COUNT")
    known_lenses = lens_keys()
    seen_ids, covered_lenses, normalized = set(), set(), []
    for command in commands:
        require(isinstance(command, dict) and set(command) ==
                {"id", "kind", "title", "description", "groupId", "lensRefs", "insertText"},
                "RDG_COMMAND_FIELDS")
        cid, kind = command["id"], command["kind"]
        require(isinstance(cid, str) and cid not in seen_ids and kind in KINDS,
                "RDG_COMMAND_ID")
        require(command["groupId"] in group_ids, f"RDG_COMMAND_UNKNOWN_GROUP:{cid}")
        check_text(command["title"], 300, f"{cid}:title")
        check_text(command["description"], 1200, f"{cid}:description")
        check_text(command["insertText"], 8000, f"{cid}:insertText")
        refs = command["lensRefs"]
        require(isinstance(refs, list) and len(refs) <= 12, f"RDG_COMMAND_REFS:{cid}")
        if kind in {"lens-launcher", "workflow"}:
            require(len(refs) >= 1, f"RDG_COMMAND_REFS:{cid}")
        if kind == "lens-launcher":
            require(len(refs) == 1, f"RDG_COMMAND_REFS:{cid}")
        else:
            require(bool(COMMAND_ID.fullmatch(cid)), f"RDG_COMMAND_ID:{cid}")
        unique_refs = set()
        for ref in refs:
            require(isinstance(ref, dict) and set(ref) == {"role", "lensKey", "modelProfile"},
                    f"RDG_COMMAND_REF:{cid}")
            key = ref["lensKey"]
            require(isinstance(key, str) and KEY.fullmatch(key) and key in known_lenses,
                    f"RDG_COMMAND_UNKNOWN_LENS:{cid}:{key}")
            require(ref["role"] == "lens" and ref["modelProfile"] == PROFILE,
                    f"RDG_COMMAND_PROFILE:{cid}:{key}")
            require(key not in unique_refs, f"RDG_COMMAND_DUPLICATE_LENS:{cid}:{key}")
            require("rdg-agent.py lens --lens " + key in command["insertText"],
                    f"RDG_COMMAND_BAD_INVOCATION:{cid}:{key}")
            unique_refs.add(key)
        if kind == "lens-launcher":
            key = refs[0]["lensKey"]
            require(cid == f"rdg.lens.{key}", f"RDG_COMMAND_ID:{cid}")
            require(key not in covered_lenses, f"RDG_COMMAND_ID:{cid}")
            covered_lenses.add(key)
        seen_ids.add(cid)
        normalized.append(command)
    require(covered_lenses == known_lenses,
            "RDG_COMMAND_COVERAGE: expected one lens-launcher for each published lens key")
    normalized.sort(key=lambda item: item["id"])
    revision = hashlib.sha256(encode({"groups": groups, "commands": normalized})).hexdigest()
    return {"schemaVersion": 2, "kind": "rdg-chat-commands", "complete": True,
            "catalogRevision": revision, "groups": groups, "commands": normalized}



def legacy_projection(manifest):
    """Keep existing V1 consumer online while V2 adds groups and composition."""
    commands = []
    for command in manifest["commands"]:
        if command["kind"] != "lens-launcher":
            continue
        commands.append({
            "id": command["id"],
            "kind": "lens-launcher",
            "title": command["title"],
            "description": command["description"],
            "lensRef": command["lensRefs"][0],
            "insertText": command["insertText"],
        })
    revision = hashlib.sha256(encode(commands)).hexdigest()
    return {"schemaVersion": 1, "kind": "rdg-chat-launcher-commands",
            "complete": True, "catalogRevision": revision, "commands": commands}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true", help="Create author-owned source once")
    parser.add_argument("--check", action="store_true", help="Verify committed manifest bytes")
    args = parser.parse_args()
    if args.init:
        initialize()
    current = validate()
    manifest = encode(current)
    legacy = encode(legacy_projection(current))
    if args.check:
        require(OUTPUT.exists() and OUTPUT.read_bytes() == manifest, "RDG_COMMAND_CATALOG_V2_STALE")
        require(LEGACY_OUTPUT.exists() and LEGACY_OUTPUT.read_bytes() == legacy,
                "RDG_COMMAND_CATALOG_V1_STALE")
        print("RDG v1+v2 command catalogs verified")
    else:
        OUTPUT.write_bytes(manifest)
        LEGACY_OUTPUT.write_bytes(legacy)
        print(f"Built {OUTPUT.relative_to(ROOT)} with {len(current['commands'])} commands and "
              f"{LEGACY_OUTPUT.relative_to(ROOT)} with {len(legacy_projection(current)['commands'])} launchers")


if __name__ == "__main__":
    main()
