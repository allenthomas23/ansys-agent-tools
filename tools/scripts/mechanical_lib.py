# Prepended to every script fea.py sends to Mechanical (stage, run and built-in
# commands). Executed inside Mechanical: keep Python 2.7-compatible syntax.
# Provided globals: fea_args (dict), study_root, reports_dir.
import os as _fea_os


def fea_messages():
    # Message objects have no Summary property; str() holds severity and text.
    return [{"severity": str(m.Severity), "text": str(m)} for m in ExtAPI.Application.Messages]


def fea_analysis(selector=None):
    """Analysis by index or name; default is fea_args["analysis"] or the first."""
    if selector is None:
        selector = fea_args.get("analysis", 0)
    analyses = list(Model.Analyses)
    if not analyses:
        raise Exception("Mechanical has no analyses")
    try:
        return analyses[int(selector)]
    except ValueError:
        named = [a for a in analyses if str(a.Name) == str(selector)]
        if len(named) != 1:
            raise Exception("Analysis not found uniquely: " + str(selector))
        return named[0]


def fea_bodies(node=None):
    node = Model.Geometry if node is None else node
    if str(node.DataModelObjectCategory) == "Body":
        return [node]
    found = []
    for child in node.Children:
        found.extend(fea_bodies(child))
    return found


def fea_selection(ids):
    if not ids:
        raise Exception("Empty geometry selection")
    value = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    value.Ids = list(ids)
    return value


def fea_named_selection(name, ids):
    obj = Model.AddNamedSelection()
    obj.Name = name
    obj.Location = fea_selection(ids)
    return obj


def fea_mesh_counts():
    try:
        mesh = ExtAPI.DataModel.MeshDataByName("Global")
        return {"nodes": mesh.NodeCount, "elements": mesh.ElementCount}
    except Exception:
        return {"nodes": 0, "elements": 0}


def fea_safe_name(text):
    keep = [c if c.isalnum() or c in "-_" else "_" for c in str(text)]
    return "".join(keep).strip("_") or "unnamed"


def fea_folder(*parts):
    path = _fea_os.path.join(*parts)
    if not _fea_os.path.isdir(path):
        _fea_os.makedirs(path)
    return path


def fea_require_solved(analysis):
    # Solve(True) can return normally while the solution is SolveFailed.
    state = str(analysis.Solution.ObjectState)
    if state != "Solved":
        raise Exception("Solution is not solved: " + state)
