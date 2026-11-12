# Running ANSYS FEA with an AI agent

This kit lets an AI coding agent (Claude Code, Codex, or similar) set up, solve and report an ANSYS Mechanical analysis in the Workbench session you already have open. It works through the official PyAnsys clients, with no clicking and no screen control, using a set of tested commands that attach to your session, never launch or close ANSYS, and only save when you ask.

You describe the study ("import the bracket, bond the ribs to the plate, apply 200 N at the hole and fix the base", "mesh it and show me what the deck contains", "solve and show the stress"). The agent asks you for the engineering choices it can't see in the CAD, builds the model in small checked stages, audits the solver input, solves, and shows you result images.

## How it works

```
You  ->  AI agent (reads AGENTS.md)  ->  tools\fea.ps1 <command>  ->  Python + PyAnsys  ->  your open Workbench / Mechanical
```

- **AGENTS.md** holds the rules the agent follows: attach to the open session, ask before changing it while you work, never guess supports or loads from CAD, audit the deck before solving, show an image after every result change. Claude Code reads it through `CLAUDE.md`.
- **tools\fea.ps1** is the single entry point. Run it with no arguments to see every command and what it may change.
- **Workbench and Mechanical are separate servers.** Workbench handles the project, systems and Engineering Data; Mechanical handles geometry, connections, mesh, loads, solving and results. `start-mechanical` enables Mechanical's server from Workbench.
- **project\\** is your study: its assumptions (`README.md`), what `validate` must find (`expectations.json`, `checks.py`), and study steps (`stages\`) the agent writes as the study grows.
- **ANSYS_API_NOTES.md** collects API lessons learned the hard way: lifecycle calls that close your session, solves that report success after failing, contact settings inertia relief needs. The agent reads it before API work and adds to it.
- **Git + Git LFS** keep the history of native ANSYS files.

## Commands

| Command | Kind | What it does |
|---|---|---|
| `inspect` | read | Workbench systems, or (`--backend mechanical`) the model tree with materials and suppression, mesh size, analyses and their states, units and Mechanical's messages |
| `validate` | read | Inspects, then checks `project/expectations.json` (object counts, forbidden supports, materials per body, solved state) and `project/checks.py` |
| `audit-deck <file>` | read | Summarizes an input deck without ANSYS: units, nodes, elements, element types, constraints, loads, inertia relief; applies the deck rules in `expectations.json` |
| `new-system` | changes | Adds an analysis system (`--template "Static Structural" --name ...`) |
| `start-mechanical` | session | Enables a system's Mechanical API server and records its port |
| `mesh` | changes | Meshes if needed, writes the solver input deck to `reports\` and audits it |
| `solve` | solves | Solves one analysis and evaluates results; fails unless the state is Solved |
| `report` | view | For a solved analysis: min/max of every result, node tables, PNGs per view (true scale; `--scaled` adds exaggerated shapes) and an `IMAGES.md` index. Restores your view settings |
| `stage <name>` | changes | Runs `project/stages/<name>_<backend>.py`; result in `reports\<name>.json` |
| `run <script>` | changes | Runs any reviewed native script; the escape hatch for probes |
| `save` | saves | Saves the project only if it contains the expected system (`--expect`); `--as` for a first save, never overwriting |
| `check-env` | read | Client versions, no connection |

Connected commands take `--port` to override the configured one, and `--analysis <index or name>` where it applies. All print JSON and exit nonzero on failure. Scripts and solves take as long as ANSYS needs; interrupting the client doesn't stop the work inside ANSYS.

## Set up a project

1. Install Git, Git LFS, Python 3.10+ and an AI coding agent. Run `git lfs install` once.
2. Start a repository from this one. In it:
   ```powershell
   python -m venv .venv
   .venv/Scripts/python.exe -m pip install -r requirements.txt
   powershell.exe -NoProfile -File tools/fea.ps1 check-env
   ```
3. Open Workbench, run `StartServer()` in **File > Scripting > Open Command Window**, and put the port in `fea.local.json` ([docs/SETUP.md](docs/SETUP.md)). Check with `tools/fea.ps1 inspect`.
4. Fill in `project/README.md`: objective, acceptance criteria, geometry source, materials, loads, supports, contacts. Put the source geometry in `project/source/`.
5. Start your agent in the repository and ask for the study. It creates the system, opens Mechanical with `start-mechanical --open-editor`, and builds the model in stages (start from `examples/`).

## Working with the agent

- **Answer its questions about physics.** Supports, load paths, joint behavior, material directions and masses can't be read from CAD; the agent asks, and records your answers in `project/README.md`.
- **Let it make commands and stages.** Repeated steps become `project/stages/` scripts that refuse to run twice and report what they made. Generic ones belong in `tools/`.
- **Read the audit before the solve.** `mesh` prints the deck summary (masses, constraints, loads, element types). Rules you always want, such as "no displacement constraints" or "inertia relief on", go in `expectations.json`.
- **Look at the picture.** "Solved" and a passing `validate` don't mean the answer is right. Check deformed shapes, reaction balance and a mesh refinement before trusting numbers.
- **Coordinate on the session.** If you're working in ANSYS at the same time, the agent should ask before running changes. Git can't merge two people's edits to a `.wbpj`.

## Limits

- Windows, ANSYS Workbench/Mechanical with the PyAnsys server features. Built and used with ANSYS 2025 R2 (`ansys-workbench-core` 0.14, `ansys-mechanical-core` 0.13); check other releases with `inspect` first.
- Attaches only to sessions on this computer (loopback) with Windows authentication (`wnua`) by default.
- Validation checks setup and states. It doesn't qualify strength, convergence or the physical validity of a model.

Offline tests: `.venv/Scripts/python.exe -m unittest discover -s tests -v`.
