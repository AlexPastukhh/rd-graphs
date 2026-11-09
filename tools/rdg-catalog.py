"""Source discovery and presentation metadata; no R/D semantics or write permission."""
import json
import os
import re
from pathlib import Path
from importlib.machinery import SourceFileLoader
IO=SourceFileLoader('catalog_current_routes',str(Path(__file__).with_name('rdg-transaction-io.py'))).load_module()

SLUG = re.compile(r"[a-z0-9][a-z0-9_-]*")
SKIP = {"node_modules", "__pycache__", "source-versions", "snapshots", "generated"}

def read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise ValueError(f"cannot read catalog source {path}: {exc}") from exc

def safe_file(root, path):
    path = Path(path)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"catalog path outside root: {path}")
    if any(part.is_symlink() for part in [path, *path.parents] if part != root.parent):
        raise ValueError(f"symlink catalog source: {path}")
    return path

def presentation(value, where):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"invalid presentation: {where}")
    allowed = {"title", "description", "usage", "exampleOnly", "archived"}
    if set(value) - allowed:
        raise ValueError(f"unknown presentation field: {where}")
    for k in ["title", "description"]:
        if k in value and (not isinstance(value[k], str) or not value[k].strip()):
            raise ValueError(f"invalid {k}: {where}")
    if "usage" in value and value["usage"] not in {"ready", "working"}:
        raise ValueError(f"invalid usage: {where}")
    for k in ["exampleOnly", "archived"]:
        if k in value and type(value[k]) is not bool:
            raise ValueError(f"invalid {k}: {where}")
    return value.copy()

def discover(root, overrides=None):
    root = Path(root)
    overrides = overrides or {}
    registry = read(root / "catalog.json") if (root / "catalog.json").exists() else {"schemaVersion": 1, "entries": {}}
    if registry.get("schemaVersion") != 1 or not isinstance(registry.get("entries"), dict):
        raise ValueError("invalid graphs/catalog.json")
    paths, directories = set(), {root}
    for base, dirs, names in os.walk(root, followlinks=False):
        base = Path(base)
        manifest=base/'package.json'
        packaged=(base/'.rdg/package.json').is_file()
        if manifest.is_file():
            metadata=read(manifest);packaged=packaged or isinstance(metadata,dict) and metadata.get('kind')=='rdgGraphPackage'
        if packaged:dirs[:]=[];continue
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIP and not (base/d).is_symlink())
        directories.add(base)
        for name in ["graph.json", "folder.json"]:
            if name in names:
                paths.add(safe_file(root, base/name))
    for key in overrides:
        if not isinstance(key, str) or "\\" in key or ".." in Path(key).parts or Path(key).is_absolute():
            raise ValueError("invalid override path")
        path = safe_file(root, root/key)
        if path.name != "graph.json":
            raise ValueError("override must address graph.json")
        paths.add(path)
        directories.update(path.parents)
    # Folders and source owners replace legacy graph-set membership.
    # A full graph is a projection from one authoritative root Requirement.
    graphs, seen = [], set()
    graph_dirs = set()
    for path in sorted(p for p in paths if p.name == "graph.json"):
        safe_file(root, path)
        key = path.relative_to(root).as_posix()
        if IO.legacy_owner_route(path):continue
        graph = overrides[key] if key in overrides else read(path)
        old = registry["entries"].get(key, {})
        if not isinstance(old, dict):
            raise ValueError(f"invalid catalog registry entry: {key}")
        slug = graph.get("catalogSlug") or old.get("slug") or path.parent.name
        if not isinstance(slug, str) or not SLUG.fullmatch(slug) or slug in seen:
            raise ValueError(f"invalid/duplicate graph slug: {key}")
        seen.add(slug)
        meta = presentation({**(old.get("presentation") or {}), **(graph.get("presentation") or {})}, key)
        if "exampleOnly" not in meta and graph.get("exampleOnly") is True:
            meta["exampleOnly"] = True
        folder = path.parent.parent.relative_to(root).as_posix()
        folder = old.get("folder", "" if folder == "." else folder)
        if folder and (Path(folder).is_absolute() or ".." in Path(folder).parts or "\\" in folder):
            raise ValueError(f"invalid presentation folder: {key}")
        item = {"slug":slug, "title":meta.get("title") or graph.get("title") or graph.get("id") or slug,
                "file":key, "group":key.split("/")[0] if "/" in key else "legacy", "folder":folder,
                "kind":"graph", "presentation":meta, "catalogLegacy":meta.get("archived",False),
                "catalogHidden":graph.get("catalogHidden") is True or graph.get("actionModel") != "candidate-v6" or any(graph.get(k) is True for k in ("readOnly","templateOnly","exampleOnly")),
                "planningScale":graph.get("planningScale","module"), "graph":graph}
        graphs.append(item)
        graph_dirs.add(path.parent)
    folders = []
    # Keep an ordinary navigation route to every root graph without
    # exposing physical child graph directories as duplicate catalog entries.
    required_folders = set()
    for item in graphs:
        folder = root / item["folder"]
        while folder != root and folder.is_relative_to(root):
            required_folders.add(folder)
            folder = folder.parent
    for path in sorted(directories):
        if not path.is_relative_to(root) or path == root:
            continue
        internal = path in graph_dirs or any(d in path.parents for d in graph_dirs)
        if internal and path not in required_folders:
            continue
        relative = path.relative_to(root).as_posix()
        parent = path.parent.relative_to(root).as_posix()
        info = read(path/"folder.json") if (path/"folder.json").exists() else {}
        if info and info.get("schemaVersion") != 1:
            raise ValueError(f"invalid folder.json: {relative}")
        meta = presentation(info.get("presentation"), relative)
        folders.append({"id":relative, "kind":"folder", "folder":"" if parent=="." else parent,
                        "title":meta.get("title",path.name), "presentation":meta})
    return graphs, folders
