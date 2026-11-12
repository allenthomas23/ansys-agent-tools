"""Declarative checks from project/expectations.json. Read-only; see project/README.md."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTATIONS = ROOT / "project" / "expectations.json"


def load_expectations(path=EXPECTATIONS):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}


def walk(node):
    yield node
    for child in node.get("children", []):
        yield from walk(child)


def active_nodes(snapshot):
    """Mechanical tree objects that are not suppressed."""
    return [n for n in walk(snapshot.get("project", {})) if n.get("Suppressed") != "True"]


def expectation_issues(backend, snapshot, expected):
    if backend == "workbench":
        names = [s.get("display_text") for s in snapshot.get("systems", [])]
        for name in expected.get("systems", []):
            if name not in names:
                yield "Workbench has no system named " + name
        return
    analyses = snapshot.get("analyses", [])
    wanted = expected.get("analysis")
    if wanted is not None:
        analyses = [a for a in analyses if a["name"] == wanted]
        if not analyses:
            yield "Mechanical has no analysis named " + wanted
            return
    active = active_nodes(snapshot)
    for category, count in expected.get("counts", {}).items():
        found = sum(n.get("DataModelObjectCategory") == category for n in active)
        if found != count:
            yield f"Expected {count} active {category} objects; found {found}."
    for node in active:
        if node.get("DataModelObjectCategory") in expected.get("forbid_categories", []):
            yield f"{node['DataModelObjectCategory']} is not permitted in this study: {node['name']}"
    materials = expected.get("materials", {})
    if materials:
        for node in active:
            if node.get("DataModelObjectCategory") != "Body":
                continue
            want = materials.get(node["name"], materials.get("*"))
            if want is not None and node.get("Material") != want:
                yield f"Body {node['name']} has material {node.get('Material')!r}; expected {want!r}"
    if expected.get("require_solved"):
        for analysis in analyses:
            if analysis["solution_state"] != "Solved":
                yield f"Analysis {analysis['name']} is not solved: {analysis['solution_state']}"
