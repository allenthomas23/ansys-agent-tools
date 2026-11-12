"""Example local post-processing: deformation relative to a reference region.

After inertia relief (or any free body), absolute displacement depends on the
solver's reference. This removes a rigid motion fitted to reference nodes, then
reports relative displacement at sample points.

Needs `report` output with Directional Deformation X/Y/Z results named
"Displacement X/Y/Z", and the deck written by `mesh`. Adapt the selections.
  .venv/Scripts/python.exe examples/relative_deformation.py <report folder> <deck>
"""
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from fea_post import fit_rigid_motion, read_nodes, read_result_table, relative_displacement, table_unit

folder, deck = Path(sys.argv[1]), Path(sys.argv[2])
tables = [folder / f"Displacement_{axis}.txt" for axis in "XYZ"]
displacements = [read_result_table(t) for t in tables]
coords = read_nodes(deck)  # Solver units (MKS here: metres).

# Example selections: reference = nodes within 20 mm of the origin;
# samples = nodes within 5 mm of each point. Replace with the study's regions.
REFERENCE_RADIUS, SAMPLE_RADIUS = 0.020, 0.005
SAMPLES = {"tip": (0.15, 0.0, 0.0)}

near = lambda p, c, r: sum((p[k] - c[k]) ** 2 for k in range(3)) < r * r
reference = [n for n, p in coords.items() if n in displacements[0] and near(p, (0, 0, 0), REFERENCE_RADIUS)]
fit = fit_rigid_motion(coords, displacements, reference)
out = {"unit": table_unit(tables[0]), "reference_nodes": len(reference), "rigid_motion": fit, "samples": {}}
for name, point in SAMPLES.items():
    nodes = [n for n, p in coords.items() if n in displacements[0] and near(p, point, SAMPLE_RADIUS)]
    if not nodes:
        raise SystemExit("No nodes near sample " + name)
    values = [relative_displacement(n, coords, displacements, fit) for n in nodes]
    mean = [sum(v[k] for v in values) / len(values) for k in range(3)]
    out["samples"][name] = {"nodes": len(nodes), "mean_relative": mean, "magnitude": math.sqrt(sum(v * v for v in mean))}
print(json.dumps(out, indent=2))
