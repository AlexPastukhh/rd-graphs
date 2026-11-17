#!/usr/bin/env python3
"""Validate author-owned chat commands and publish one complete read-only manifest.

Authoring file: work-kit/helper-commands/commands.json.
The source RDG lens catalog is used for identity checks only: command text is
not synthesized on fetch/build and is independent of Markdown/source-map.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work-kit/helper-commands/commands.json"
OUTPUT = ROOT / "work-kit/helper-commands/catalog.json"
LENSES = ROOT / "tools/rdg-agent-lenses/catalog.json"
PROFILE = "rdg-decision-v1"
KEY = re.compile(r"^[a-z][a-z0-9-]{0,79}$")
SECRET = re.compile(r"(?i)(?:ghp_[A-Za-z0-9]{20}|Bearer\s+[A-Za-z0-9._~+/-]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)")


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def lens_keys():
    data = json.loads(LENSES.read_bytes())
    require(data.get("schemaVersion") == 1 and isinstance(data.get("entries"), list), "RDG_LENS_CATALOG_SCHEMA")
    keys = set()
    for e in data["entries"]:
        key = e.get("key")
        require(isinstance(key, str) and KEY.fullmatch(key) and key not in keys, "RDG_LENS_IDENTITY")
        require(PROFILE in e.get("profileDefinitions", {}), f"RDG_LENS_PROFILE:{key}")
        keys.add(key)
    require(bool(keys), "RDG_LENS_EMPTY")
    return keys


def initial_text(key, title):
    # Used exactly once by --init; persisted source remains independently editable.
    return (
        f"Примени существующую линзу RDG «{title}» (lensKey: {key}) к текущей задаче.\n\n"
        "Сначала через доступный авторизованный RDG Agent/API прочитай её АКТУАЛЬНОЕ полное "
        "структурированное определение. Из корня rd-graphs доступна команда:\n"
        f"python3 -B tools/rdg-agent.py lens --lens {key} --model-profile {PROFILE} "
        "--context <подготовленный-RDG-context>\n"
        "Сначала проверь doctor/capabilities/catalog при необходимости; через RDG lenses "
        "подтверди role=lens, lensKey, identity и текущую revision. Используй реальные "
        "связи, Canon/Info, правила, ограничения и необходимые источники из прочитанного "
        "определения; не считай текст кнопки полным содержанием линзы. "
        "Примени методику соразмерно задаче и полномочиям пользователя. "
        "Если определение или API недоступны, скажи об ограничении, не придумывай смысл. "
        "Не создавай Graph, Action или процесс лишь из-за вызова этой команды."
    )


def initialize():
    require(not SOURCE.exists(), "RDG_COMMAND_SOURCE_ALREADY_EXISTS")
    definitions = json.loads(LENSES.read_bytes())["entries"]
    commands = []
    for e in definitions:
        key = e["key"]
        title = e["title"]
        commands.append({
            "id": f"rdg.lens.{key}", "kind": "lens-launcher",
            "title": title, "description": e["purpose"][:300],
            "lensRef": {"role": "lens", "lensKey": key, "modelProfile": PROFILE},
            "insertText": initial_text(key, title),
        })
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    SOURCE.write_bytes(encode({"schemaVersion": 1, "commands": commands}))
    print(f"Initialized author-owned RDG commands: {len(commands)}")


def validate():
    data = json.loads(SOURCE.read_bytes())
    require(isinstance(data, dict) and set(data) == {"schemaVersion", "commands"} and data["schemaVersion"] == 1,
            "RDG_COMMAND_SOURCE_SCHEMA")
    commands = data["commands"]
    require(isinstance(commands, list) and bool(commands) and len(commands) <= 250, "RDG_COMMAND_SOURCE_COUNT")
    keys, seen = lens_keys(), set()
    normalized = []
    for c in commands:
        require(isinstance(c, dict) and set(c) == {"id", "kind", "title", "description", "lensRef", "insertText"},
                "RDG_COMMAND_FIELDS")
        ref = c["lensRef"]
        require(isinstance(ref, dict) and set(ref) == {"role", "lensKey", "modelProfile"}, "RDG_COMMAND_REF")
        key = ref["lensKey"]
        require(isinstance(key, str) and KEY.fullmatch(key) and key in keys, f"RDG_COMMAND_UNKNOWN_LENS:{key}")
        require(ref["role"] == "lens" and ref["modelProfile"] == PROFILE, f"RDG_COMMAND_PROFILE:{key}")
        require(c["id"] == f"rdg.lens.{key}" and c["id"] not in seen and c["kind"] == "lens-launcher",
                f"RDG_COMMAND_ID:{key}")
        seen.add(c["id"])
        for field, max_len in (("title", 300), ("description", 1200), ("insertText", 5000)):
            value = c[field]
            require(isinstance(value, str) and value.strip() and len(value) <= max_len and
                    not SECRET.search(value), f"RDG_COMMAND_TEXT:{key}:{field}")
        require(key in c["insertText"] and "rdg-agent.py lens --lens " + key in c["insertText"],
                f"RDG_COMMAND_BAD_INVOCATION:{key}")
        normalized.append(c)
    require({c["lensRef"]["lensKey"] for c in normalized} == keys,
            "RDG_COMMAND_COVERAGE: expected all published source lens keys")
    normalized.sort(key=lambda c: c["id"])
    revision = hashlib.sha256(encode(normalized)).hexdigest()
    return {"schemaVersion": 1, "kind": "rdg-chat-launcher-commands",
            "complete": True, "catalogRevision": revision, "commands": normalized}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true", help="Create editable command source once")
    ap.add_argument("--check", action="store_true", help="Verify committed catalog is byte-current")
    args = ap.parse_args()
    if args.init:
        initialize()
    manifest = encode(validate())
    if args.check:
        require(OUTPUT.exists() and OUTPUT.read_bytes() == manifest, "RDG_COMMAND_CATALOG_STALE")
        print("RDG helper command catalog verified")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_bytes(manifest)
        print(f"Built {OUTPUT.relative_to(ROOT)} with {len(json.loads(manifest)['commands'])} commands")


if __name__ == "__main__":
    main()
