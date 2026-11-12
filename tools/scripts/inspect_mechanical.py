# Executed inside Mechanical. Observational only: no meshing, solving,
# selection change or save.
def _fea_node(obj):
    node = {"name": str(obj.Name), "id": int(obj.ObjectId)}
    for prop in ("DataModelObjectCategory", "ObjectState", "Suppressed", "Material"):
        if hasattr(obj, prop):
            node[prop] = str(getattr(obj, prop))
    node["children"] = [_fea_node(child) for child in obj.Children]
    return node

fea_script_result = {
    "project": _fea_node(ExtAPI.DataModel.Project),
    "geometry_unit": str(ExtAPI.DataModel.GeoData.Unit),
    "unit_system": str(ExtAPI.Application.ActiveUnitSystem),
    "mesh": dict(fea_mesh_counts(), state=str(Model.Mesh.ObjectState)),
    "analyses": [{"index": i, "name": str(a.Name), "id": int(a.ObjectId),
                  "state": str(a.ObjectState),
                  "solution_state": str(a.Solution.ObjectState),
                  "working_directory": str(a.WorkingDir)}
                 for i, a in enumerate(Model.Analyses)],
    "messages": fea_messages(),
}
