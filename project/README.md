# Study

Fill this in when starting a study. No study is configured yet.

## Definition

Record each decision with its source (user decision, datasheet, test, assumption). The agent asks for anything missing instead of reading it from CAD.

- **Objective and acceptance criteria:** what decision the analysis supports; allowable values and where they come from.
- **Geometry:** source CAD and revision, export format and location (`source/`), simplifications and excluded parts.
- **Materials:** properties with sources and units, material axes for orthotropic materials.
- **Masses:** which parts are flexible bodies and which are point masses; mass, CG and inertia sources; how masses are grouped.
- **Connections:** joint behavior between bodies (bonded, frictional, bolted), which CAD contacts are suppressed.
- **Loads and supports:** magnitudes, directions, units, combinations; physical supports, or a free body with inertia relief.
- **Mesh and solver:** element order and size, convergence study, linear or nonlinear.
- **Result checks:** equilibrium, mass totals, plausibility, which results are reported and against what limits.

## Workflow

Native project: `<Study>.wbpj` with its `_files` folder, here in `project/`. Stages in `stages/` run in this order:

1. (list stages, e.g. `materials`, `import`, `setup`)
2. `mesh`, review the deck audit
3. `solve`
4. `report`

## Expectations

`expectations.json` tells `validate` and `audit-deck` what this study must contain. Every key is optional:

```json
{
  "systems": ["Bracket - Static"],
  "analysis": "Static Structural",
  "counts": {"Body": 3, "ContactRegion": 4, "Force": 1, "FixedSupport": 1},
  "forbid_categories": ["Displacement"],
  "materials": {"Plate": "Aluminum alloy", "*": "Structural Steel"},
  "require_solved": true,
  "deck": {
    "units": "MKS",
    "require": ["^\\s*airl\\s*,\\s*6"],
    "forbid": ["^\\s*d\\s*,"]
  }
}
```

- `systems`: Workbench system display names that must exist.
- `counts`: exact numbers of unsuppressed Mechanical objects by `DataModelObjectCategory` (as `inspect --backend mechanical` shows them).
- `materials`: material per body name; `"*"` for all other bodies.
- `deck`: regular expressions matched per line, case-insensitive, against the input deck written by `mesh`.

Rules that this format can't express go in `checks.py`.
