# Example stage: import geometry into the analysis' existing Geometry Import and
# list bodies with ids, volumes and centroids for mapping. Copy to project/stages/.
# Run: fea.ps1 stage import --arg geometry=source/Part.x_t
# (path relative to project/). Materials are refreshed so Engineering Data shows up.
if Model.Geometry.Children.Count:
    raise Exception("Geometry already exists; inspect before importing again")
path = _fea_os.path.join(study_root, fea_args["geometry"])
if not _fea_os.path.isfile(path):
    raise Exception("Geometry file not found: " + path)
# A Workbench-owned primary import rejects explicit preferences; pass None.
Model.GeometryImportGroup.Children[0].Import(
    path, Ansys.Mechanical.DataModel.Enums.GeometryImportPreference.Format.Automatic, None)
Model.Materials.RefreshMaterials()
rows = []
for body in fea_bodies():
    geo = body.GetGeoBody()
    # Body names may not survive import (Parasolid did not keep them): map bodies
    # to the source by centroid/volume, never by order.
    rows.append({"name": str(body.Name), "id": int(body.ObjectId), "geometry_id": geo.Id,
                 "volume": str(body.Volume), "centroid": list(geo.Centroid),
                 "faces": len(geo.Faces)})
ExtAPI.Graphics.Camera.SetFit()
fea_script_result = {"bodies": rows, "geometry_unit": str(ExtAPI.DataModel.GeoData.Unit),
                     "imported_contacts": [str(c.Name) for c in
                                           Model.Connections.GetChildren(DataModelObjectCategory.ContactRegion, True)],
                     "messages": fea_messages()}
