Keep this file minimal: entry points and non-obvious rules only. Study assumptions and decisions go in `project/README.md`; reusable API lessons in ANSYS_API_NOTES.md.

# Layout

- `tools/`: `fea.ps1` (lists and runs every maintained command), `fea.py` (connection, script transport, commands), `fea_post.py` (local deck and result helpers), `fea_checks.py` (expectations), `scripts/` (code that runs inside ANSYS; `mechanical_lib.py` is prepended to every Mechanical script).
- `project/`: this study. `README.md` (assumptions, acceptance criteria), `expectations.json` and `checks.py` (what `validate` and `audit-deck` enforce), `stages/` (study steps run with `stage`), the `.wbpj` with its `_files` folder, and source geometry.
- `examples/`: tested patterns to copy into `project/` (materials, import, setup, inertia relief, relative deformation).
- `reports/` (ignored): command output (JSON, input decks, result tables, images).

Before API work, read [ANSYS_API_NOTES.md](ANSYS_API_NOTES.md) and [docs/SETUP.md](docs/SETUP.md).

# Working in ANSYS

- Attach to the Workbench and Mechanical sessions that are already open; never launch a second instance, clear or reset a project, or close a session. If the user is working in ANSYS, ask before running anything that changes it.
- Run commands through `tools\fea.ps1`; with no arguments it lists them as read, view, session, changes, solves or saves. Use `inspect` before changes instead of writing a probe, and `validate` after.
- A timed-out or interrupted command may still be running inside ANSYS. Inspect the outcome before retrying a change.
- Extend a maintained command rather than writing a near-duplicate. Throwaway scripts go in `scratch/` (ignored) and run with `run`. When you need the same script a second time, make it a command: in `tools/` if it works on any model, as a `project/stages/<name>_<backend>.py` stage if it depends on this study's names or geometry.
- `run` and `stage` have no transaction or rollback. Make scripts refuse to run twice (check for what they create), keep changes small and inspect after each.
- Server scripts are Python 2.7-compatible (Workbench is IronPython). They get `fea_args`, `study_root` and `reports_dir`; Mechanical scripts also get the `fea_*` helpers. Set `wb_script_result` / `fea_script_result` to a JSON-serializable value.
- When an API call behaves unexpectedly and you find what works, add the lesson to ANSYS_API_NOTES.md.
- No personal install paths, credentials, license settings or `.env`. Session ports go only in the ignored `fea.local.json`.

# Engineering rules

- Never infer supports, loads, contact behavior, material orientation, symmetry or masses from CAD appearance. Ask the user and record each decision in `project/README.md`. CAD mates are not FE connections.
- Give every dimensional value a unit. Pin solver units in analysis settings.
- Use named selections and stable ids after checking names and types; map imported bodies by centroid and volume, never by order.
- Don't change CAD as a side effect of an FEA task.

# Mesh, solve and report

- `mesh` writes the input deck and audits it. Review the deck summary, masses, loads and connections before `solve`; add lasting rules to `project/expectations.json`.
- `solve` fails unless the solution state is Solved. Solver completion is not engineering acceptance: check messages, equilibrium, mesh convergence and that results are plausible.
- After a model or result change, run `report` and show the user a result image. Say which figures are true scale and which are exaggerated.
- Save only when the user asks (`save --expect <system>`). Git LFS keeps history: no snapshot copies.

# Project rules

Add this study's own rules here and link `project/README.md`. Examples: coordinate convention, units, which bodies are flexible, approved simplifications, what must not change.
