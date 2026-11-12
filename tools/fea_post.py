"""Local (Python 3) helpers for ANSYS input decks and exported results.

None of these connect to ANSYS. Use them from project post-processing scripts:

    sys.path.insert(0, str(ROOT / "tools"))
    from fea_post import read_nodes, read_result_table, fit_rigid_motion
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import struct

# MAPDL commands that matter when reviewing a deck before a solve.
# MAPDL accepts 4-character abbreviations (Mechanical writes "keyop"), so commands
# are counted by their first four characters.
REVIEW_COMMANDS = ("d", "f", "sfe", "cp", "ce", "acel", "omega", "airl", "irlf",
                   "antype", "nlgeom", "solve", "/units", "outres", "keyopt")


def _head(line):
    return line.split("!")[0].split(",")[0].strip().lower()[:4]


def _fortran_widths(fmt):
    """Field widths from a deck format line such as (1i9,3e20.9e3) or (19i9)."""
    widths = []
    for count, kind, width in re.findall(r"(\d*)([ie])(\d+)", fmt.lower()):
        widths.extend([int(width)] * int(count or 1))
    return widths


def _fields(line, widths):
    # Fixed-width fields can touch when values are negative, so prefer widths.
    if widths and len(line.rstrip("\r\n")) >= sum(widths[:2]):
        out, pos = [], 0
        for width in widths:
            text = line[pos:pos + width].strip()
            pos += width
            if text:
                out.append(text)
        return out
    return line.split()


def read_nodes(deck):
    """Return {node_id: (x, y, z)} from every NBLOCK in a written input deck.

    Coordinates are in the deck's solver units (see `/units`), not display units.
    """
    nodes = {}
    with Path(deck).open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if not line.lower().startswith("nblock"):
                continue
            widths = _fortran_widths(next(stream))
            for row in stream:
                cells = _fields(row, widths)
                if not cells or cells[0] == "-1" or row.lower().startswith(("n,", "eblock", "et,")):
                    break
                if len(cells) >= 4:
                    # (1i9,3e..) is id,x,y,z; (3i9,6e..) is id,solid,line,x,y,z,...
                    ints = 3 if len(cells) >= 6 and "." not in cells[1] else 1
                    nodes[int(cells[0])] = tuple(float(v) for v in cells[ints:ints + 3])
    return nodes


def deck_summary(deck):
    """Counts and settings to review before solving. Reads only the deck."""
    commands = Counter()
    element_types = {}
    units = None
    nodes = elements = 0
    with Path(deck).open(encoding="utf-8", errors="replace") as stream:
        block = None
        for line in stream:
            low = line.strip().lower()
            if block:
                if low.startswith("-1") or (block == "n" and low.startswith(("n,", "eblock", "et,"))):
                    block = None
                elif low and not low.startswith("("):
                    if block == "n":
                        nodes += 1
                continue
            if not low or low.startswith("!"):
                continue
            head = _head(low)
            commands[head] += 1
            parts = [p.strip() for p in low.split("!")[0].split(",")]
            if head == "nblo":
                block = "n"
            elif head == "eblo":
                block = "e"
                if len(parts) > 4 and parts[4].isdigit():
                    elements += int(parts[4])
            elif head == "et" and len(parts) > 2:
                element_types[parts[1]] = parts[2]
            elif head == "/uni" and len(parts) > 1:
                units = parts[1].upper()
    review = {name: commands[name[:4]] for name in REVIEW_COMMANDS if commands[name[:4]]}
    return {"file": str(deck), "units": units, "nodes": nodes, "elements": elements,
            "element_types": dict(Counter(element_types.values())), "review_commands": review,
            "displacement_constraints": commands["d"], "inertia_relief": bool(commands["airl"] or commands["irlf"])}


def check_deck(deck, rules):
    """Apply `deck` rules from project/expectations.json; return failure messages.

    rules: {"require": [regex, ...], "forbid": [regex, ...], "units": "MKS"}
    Regexes are matched case-insensitively per line (multiline).
    """
    text = Path(deck).read_text(encoding="utf-8", errors="replace")
    issues = []
    for pattern in rules.get("require", []):
        if not re.search(pattern, text, re.I | re.M):
            issues.append("Deck is missing required pattern: " + pattern)
    for pattern in rules.get("forbid", []):
        match = re.search(pattern, text, re.I | re.M)
        if match:
            issues.append("Deck contains forbidden pattern " + pattern + ": " + match.group(0).strip())
    units = rules.get("units")
    if units and not re.search(r"^\s*/units\s*,\s*" + re.escape(units) + r"\b", text, re.I | re.M):
        issues.append("Deck solver units are not " + units)
    return issues


def read_result_table(path):
    """Return {node_or_element_id: value} from Mechanical's ExportToTextFile output.

    The header names the quantity and its unit, e.g. "Directional Deformation (mm)";
    values use the unit system active when the file was exported.
    """
    rows = {}
    with Path(path).open(encoding="utf-8-sig", errors="replace") as stream:
        header = next(stream)
        for line in stream:
            cells = line.split()
            if len(cells) >= 2:
                try:
                    rows[int(cells[0])] = float(cells[1])
                except ValueError:
                    continue
    return rows


def table_unit(path):
    with Path(path).open(encoding="utf-8-sig", errors="replace") as stream:
        match = re.search(r"\(([^)]*)\)\s*$", next(stream).strip())
    return match.group(1) if match else None


def _solve(matrix, rhs):
    n = len(rhs)
    aug = [list(matrix[i]) + [rhs[i]] for i in range(n)]
    for k in range(n):
        pivot = max(range(k, n), key=lambda i: abs(aug[i][k]))
        aug[k], aug[pivot] = aug[pivot], aug[k]
        if abs(aug[k][k]) < 1e-30:
            raise ValueError("Singular rigid-motion fit: reference nodes do not span 3D")
        scale = aug[k][k]
        aug[k] = [v / scale for v in aug[k]]
        for i in range(n):
            if i != k and aug[i][k]:
                factor = aug[i][k]
                aug[i] = [aug[i][j] - factor * aug[k][j] for j in range(n + 1)]
    return [aug[i][n] for i in range(n)]


def fit_rigid_motion(coords, displacements, reference_nodes):
    """Least-squares small rigid motion [tx, ty, tz, rx, ry, rz] of reference nodes.

    coords: {id: (x, y, z)}; displacements: three {id: value} dicts (X, Y, Z), in
    consistent length units. Use it to report deformation relative to a chosen part
    of the structure, e.g. after inertia relief, where absolute displacement depends
    on the solver's reference. Pick reference nodes that do not lie on one line.
    """
    normal = [[0.0] * 6 for _ in range(6)]
    rhs = [0.0] * 6
    used = 0
    for node in reference_nodes:
        if node not in coords or any(node not in d for d in displacements):
            continue
        used += 1
        x, y, z = coords[node]
        rows = ([1, 0, 0, 0, z, -y], [0, 1, 0, -z, 0, x], [0, 0, 1, y, -x, 0])
        for k, row in enumerate(rows):
            for i in range(6):
                rhs[i] += row[i] * displacements[k][node]
                for j in range(6):
                    normal[i][j] += row[i] * row[j]
    if used < 3:
        raise ValueError("Rigid-motion fit needs at least three reference nodes with results")
    return _solve(normal, rhs)


def relative_displacement(node, coords, displacements, fit):
    """Displacement of `node` with the fitted rigid motion removed."""
    x, y, z = coords[node]
    tx, ty, tz, rx, ry, rz = fit
    rigid = (tx + ry * z - rz * y, ty + rz * x - rx * z, tz + rx * y - ry * x)
    return [displacements[k][node] - rigid[k] for k in range(3)]


def png_size(path):
    """(width, height) of a PNG, or raise if the file is not a PNG."""
    header = Path(path).read_bytes()[:24]
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Not a PNG: " + str(path))
    return struct.unpack(">II", header[16:24])
