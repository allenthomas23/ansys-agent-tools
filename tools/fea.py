"""Attach-only command line tools for the user's open ANSYS sessions.

Kinds: [read] observes only; [view] changes only graphics settings and writes
files under reports/; [session] enables an API server in the open session;
[changes] edits the model; [solves] runs the solver; [saves] writes the project.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
SCRIPTS = TOOLS / "scripts"
STUDY = ROOT / "project"
REPORTS = ROOT / "reports"
LOCAL_CONFIG = ROOT / "fea.local.json"
sys.path.insert(0, str(TOOLS))
import fea_post  # noqa: E402
from fea_checks import load_expectations  # noqa: E402


def configuration(backend, port=None):
    config = json.loads((ROOT / "fea.config.json").read_text(encoding="utf-8-sig"))
    if LOCAL_CONFIG.exists():
        for key, value in json.loads(LOCAL_CONFIG.read_text(encoding="utf-8-sig")).items():
            if isinstance(value, dict) and isinstance(config.get(key), dict):
                config[key].update(value)
            else:
                config[key] = value
    endpoint = dict(config[backend])
    if port is not None:
        endpoint["port"] = port
    if endpoint["host"] not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("This kit attaches only to local sessions; use a loopback host.")
    p = endpoint.get("port")
    if type(p) is not int or not 1 <= p <= 65535:
        raise ValueError(f"No valid {backend} port configured. See docs/SETUP.md; use --port or fea.local.json.")
    if endpoint["security"] not in ("wnua", "mtls", "insecure"):
        raise ValueError("Unsupported transport security mode.")
    timeout = float(config.get("connect_timeout", 10))
    if timeout <= 0:
        raise ValueError("connect_timeout must be positive.")
    return endpoint, timeout


def remember_port(backend, port):
    """Record a session port in the ignored fea.local.json, keeping other entries."""
    local = json.loads(LOCAL_CONFIG.read_text(encoding="utf-8-sig")) if LOCAL_CONFIG.exists() else {}
    local.setdefault(backend, {})["port"] = int(port)
    LOCAL_CONFIG.write_text(json.dumps(local, indent=2) + "\n", encoding="utf-8")


def decode_result(value):
    # Workbench versions can return JSON as a string; Mechanical returns text.
    for _ in range(3):
        if not isinstance(value, str):
            break
        value = json.loads(value)
    if not isinstance(value, dict) or value.get("ok") is not True:
        raise RuntimeError("ANSYS script failed: " + str(value))
    return value["result"]


def envelope(source, backend):
    result_name = "wb_script_result" if backend == "workbench" else "fea_script_result"
    # Both server interpreters support Python 2.7 syntax. Keep exec at global scope
    # so normal Workbench and Mechanical scripting globals remain available.
    code = ("import json as _fea_json\nimport traceback as _fea_traceback\n"
            + result_name + " = None\ntry:\n"
            + "    exec(compile(" + ascii(source) + ", '<fea-script>', 'exec'))\n"
            + "    _fea_response = {'ok': True, 'result': " + result_name + "}\n"
            + "except Exception:\n"
            + "    _fea_response = {'ok': False, 'error': _fea_traceback.format_exc()}\n")
    if backend == "workbench":
        return code + "wb_script_result = _fea_json.dumps(_fea_response)\n"
    return code + "_fea_json.dumps(_fea_response)"


def prelude(backend, args=None):
    """Globals for server scripts: fea_args, study_root, reports_dir (+ helpers)."""
    values = dict(args or {}, study_root=str(STUDY), reports_dir=str(REPORTS))
    # json.dumps escapes non-ASCII, so the literal is safe in Python 2 and 3.
    code = ("import json as _fea_args_json\n"
            "fea_args = _fea_args_json.loads(" + ascii(json.dumps(values)) + ")\n"
            "study_root = fea_args['study_root']\nreports_dir = fea_args['reports_dir']\n")
    if backend == "mechanical":
        code += (SCRIPTS / "mechanical_lib.py").read_text(encoding="utf-8") + "\n"
    return code


def server_script(path, backend, args=None):
    return prelude(backend, args) + Path(path).read_text(encoding="utf-8-sig")


class Session:
    def __init__(self, backend, endpoint, timeout):
        self.backend = backend
        self.endpoint = endpoint
        self.timeout = timeout
        self.client = None

    def __enter__(self):
        e = self.endpoint
        # Fail quickly on a closed port; never fall back to launching an app.
        with socket.create_connection((e["host"], e["port"]), timeout=self.timeout):
            pass
        if self.backend == "workbench":
            import grpc
            from ansys.workbench.core import connect_workbench
            self.client = connect_workbench(host=e["host"], port=e["port"],
                                            security=e["security"], client_workdir=str(ROOT))
            try:
                grpc.channel_ready_future(self.client.channel).result(timeout=self.timeout)
            except Exception:
                self.client.exit()  # Attached ClientWrapper: disconnect only.
                raise
        else:
            from ansys.mechanical.core import connect_to_mechanical
            self.client = connect_to_mechanical(
                ip=e["host"], port=e["port"], connect_timeout=self.timeout,
                transport_mode=e["security"], clear_on_connect=False,
                cleanup_on_exit=False, keep_connection_alive=False)
        return self

    def run(self, source):
        script = envelope(source, self.backend)
        if self.backend == "workbench":
            result = self.client.run_script_string(script)
        else:
            result = self.client.run_python_script(script)
        return decode_result(result)

    def __exit__(self, *exc):
        if self.backend == "workbench":
            self.client.exit()  # Never use launch_workbench here.
        # Mechanical cleanup_on_exit=False preserves the application. Do not call
        # Mechanical.exit(): it terminates the user's Mechanical session.


def run_on_server(backend, source, port=None):
    # Callers build the script first, so path failures cannot touch a session.
    endpoint, timeout = configuration(backend, port)
    with Session(backend, endpoint, timeout) as session:
        return session.run(source)


def validate(backend, snapshot):
    spec = importlib.util.spec_from_file_location("fea_project_checks", STUDY / "checks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    issues = list(module.check(backend, snapshot))
    return {"ok": not issues, "scope": "project preflight; not engineering approval or convergence verification",
            "issues": issues, "snapshot": snapshot}


def audit_deck(path):
    summary = fea_post.deck_summary(path)
    issues = fea_post.check_deck(path, load_expectations().get("deck", {}))
    return {"ok": not issues, "issues": issues, "summary": summary,
            "scope": "deck review aid; check loads, supports and masses yourself"}


def stages():
    found = {}
    for path in sorted((STUDY / "stages").glob("*_*.py")):
        name, _, backend = path.stem.rpartition("_")
        if backend in ("workbench", "mechanical"):
            found[name] = (path, backend)
    return found


def save_json(name, value):
    REPORTS.mkdir(exist_ok=True)
    path = REPORTS / (name + ".json")
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")
    return path


def summarize(result, report_path):
    summary = {k: v for k, v in result.items() if not isinstance(v, (dict, list))}
    summary.update({k + "_count": len(v) for k, v in result.items() if isinstance(v, list)})
    if result.get("messages"):
        summary["messages"] = result["messages"]
    summary["report"] = str(report_path)
    return summary


def write_image_index(result, folder):
    lines = ["# " + result["analysis"] + " result figures", "",
             "Native ANSYS renders. `-scaled` files exaggerate the displayed shape; legends give computed values.", "",
             "| Figure | Result | View | Deformation display |", "|---|---|---|---|"]
    for row in result["images"]:
        name = Path(row["file"]).name
        lines.append(f"| [{name}](images/{name}) | {row['result']} | {row['view']} | {row['deformation_display']} |")
    lines += ["", "| Result | Minimum | Maximum |", "|---|---:|---:|"]
    lines += [f"| {r['name']} | {r['minimum']} | {r['maximum']} |" for r in result["results"]]
    (Path(folder) / "IMAGES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def key_values(pairs):
    out = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise ValueError("--arg expects KEY=VALUE: " + pair)
        out[key] = value
    return out


def build_parser():
    p = argparse.ArgumentParser(prog="fea.ps1", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = p.add_subparsers(dest="command", metavar="command")

    def add(name, help_text, backend=None):
        sub = commands.add_parser(name, help=help_text, description=help_text)
        if backend == "choice":
            sub.add_argument("--backend", choices=("workbench", "mechanical"), default="workbench")
        if backend:
            sub.add_argument("--port", type=int, help="override the configured port for this call")
        return sub

    add("check-env", "[read] Python client versions; no ANSYS connection")
    add("inspect", "[read] Workbench systems, or Mechanical tree, mesh, analyses and messages", "choice")
    add("validate", "[read] inspect, then run project/checks.py and expectations.json", "choice")
    audit = add("audit-deck", "[read] summarize a solver input deck and apply expectations.json deck rules")
    audit.add_argument("deck", type=Path)
    new = add("new-system", "[changes] add an analysis system to the Workbench project", "workbench")
    new.add_argument("--name", required=True, help="display text for the new system")
    new.add_argument("--template", default="Static Structural")
    new.add_argument("--solver", default="ANSYS")
    start = add("start-mechanical", "[session] enable a system's Mechanical API server; records its port", "workbench")
    start.add_argument("--system", default="SYS", help="Workbench system name (inspect lists them)")
    start.add_argument("--open-editor", action="store_true", help="open the system's Model editor first")
    for name, help_text in (("mesh", "[changes] mesh if needed and write the input deck to reports/ for review"),
                            ("solve", "[solves] solve one analysis; nonzero exit unless Solved")):
        sub = add(name, help_text, "mechanical")
        sub.add_argument("--analysis", default="0", help="analysis index or name (default 0)")
    report = add("report", "[view] export result statistics, node tables and PNGs of a solved analysis", "mechanical")
    report.add_argument("--analysis", default="0", help="analysis index or name (default 0)")
    report.add_argument("--views", default="Iso,Top", help="comma list of ViewOrientationType names")
    report.add_argument("--width", type=int, default=3200)
    report.add_argument("--height", type=int, default=1800)
    report.add_argument("--scaled", action="store_true", help="also export exaggerated deformation shapes")
    report.add_argument("--context", action="store_true", help="show unscoped bodies around scoped results")
    report.add_argument("--units", help="MechanicalUnitSystem for tables and legends, e.g. StandardNMM (restored after)")
    stage = add("stage", "[changes] run project/stages/<name>_<backend>.py; result to reports/<name>.json")
    stage.add_argument("name", nargs="?", help="stage name; omit to list stages")
    stage.add_argument("--port", type=int, help="override the configured port for this call")
    stage.add_argument("--arg", action="append", default=[], metavar="KEY=VALUE", help="passed in fea_args")
    run = add("run", "[changes] execute a reviewed native script; may modify, solve or save", "choice")
    run.add_argument("script", type=Path)
    run.add_argument("--arg", action="append", default=[], metavar="KEY=VALUE", help="passed in fea_args")
    save = add("save", "[saves] save the Workbench project (and its open Mechanical model)", "workbench")
    save.add_argument("--expect", required=True, help="display text of a system the project must contain")
    save.add_argument("--as", dest="path", type=Path, help="first save to this new .wbpj path (never overwrites)")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "check-env":
        versions = {}
        for name in ("ansys-workbench-core", "ansys-mechanical-core"):
            try:
                versions[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                versions[name] = None
        print(json.dumps({"python": sys.version, "clients": versions}, indent=2))
        return 0 if all(versions.values()) else 1
    if args.command == "audit-deck":
        result = audit_deck(args.deck)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    if args.command in ("inspect", "validate"):
        source = server_script(SCRIPTS / ("inspect_" + args.backend + ".py"), args.backend)
        result = run_on_server(args.backend, source, args.port)
        if args.command == "validate":
            result = validate(args.backend, result)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 1 if args.command == "validate" and not result["ok"] else 0
    if args.command == "new-system":
        source = server_script(SCRIPTS / "new_system_workbench.py", "workbench",
                               {"name": args.name, "template": args.template, "solver": args.solver})
        print(json.dumps(run_on_server("workbench", source, args.port), indent=2))
        return 0
    if args.command == "start-mechanical":
        source = server_script(SCRIPTS / "start_mechanical_workbench.py", "workbench",
                               {"system": args.system, "open_editor": args.open_editor})
        result = run_on_server("workbench", source, args.port)
        remember_port("mechanical", result["port"])
        result["recorded_in"] = str(LOCAL_CONFIG)
        print(json.dumps(result, indent=2))
        return 0
    if args.command in ("mesh", "solve"):
        source = server_script(SCRIPTS / (args.command + "_mechanical.py"), "mechanical", {"analysis": args.analysis})
        result = run_on_server("mechanical", source, args.port)
        if args.command == "mesh":
            result["deck"] = audit_deck(result["input_file"])
        path = save_json(args.command, result)
        print(json.dumps(summarize(result, path), indent=2))
        if args.command == "mesh":
            print(json.dumps(result["deck"], indent=2))
            return 0 if result["deck"]["ok"] else 1
        return 0 if result["solution_state"] == "Solved" else 1
    if args.command == "report":
        options = {"analysis": args.analysis, "views": [v.strip() for v in args.views.split(",") if v.strip()],
                   "width": args.width, "height": args.height, "scaled": args.scaled,
                   "context": args.context, "units": args.units}
        source = server_script(SCRIPTS / "report_mechanical.py", "mechanical", options)
        result = run_on_server("mechanical", source, args.port)
        result["image_size_issues"] = [row["file"] for row in result["images"]
                                       if fea_post.png_size(row["file"]) != (args.width, args.height)]
        folder = Path(result["output"])
        (folder / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        write_image_index(result, folder)
        print(json.dumps(summarize(result, folder / "report.json"), indent=2))
        return 1 if result["image_size_issues"] else 0
    if args.command == "stage":
        found = stages()
        if not args.name:
            print(json.dumps({name: {"backend": b, "file": str(p)} for name, (p, b) in found.items()}, indent=2))
            return 0
        if args.name not in found:
            raise ValueError(f"No stage {args.name}; add project/stages/{args.name}_mechanical.py "
                             "or _workbench.py. Known: " + (", ".join(found) or "none"))
        path, backend = found[args.name]
        source = server_script(path, backend, key_values(args.arg))
        result = run_on_server(backend, source, args.port)
        if not isinstance(result, dict):
            result = {"result": result}
        report_path = save_json(args.name, result)
        print(json.dumps(summarize(result, report_path), indent=2))
        state = result.get("solution_state")
        return 1 if state is not None and state != "Solved" else 0
    if args.command == "run":
        source = server_script(args.script, args.backend, key_values(args.arg))
        print(json.dumps(run_on_server(args.backend, source, args.port), indent=2, ensure_ascii=True))
        return 0
    if args.command == "save":
        options = {"expect": args.expect, "path": str(args.path.resolve()) if args.path else None}
        source = server_script(SCRIPTS / "save_workbench.py", "workbench", options)
        print(json.dumps(run_on_server("workbench", source, args.port), indent=2))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        sys.exit(1)
