# Export statistics, node tables and PNGs for every evaluated result of one solved
# analysis. Changes only graphics/view settings, restored afterwards; the camera is
# left at the last exported view. No model data is changed and nothing is saved.
analysis = fea_analysis()
fea_require_solved(analysis)
out = fea_folder(reports_dir, fea_safe_name(analysis.Name))
images = fea_folder(out, "images")
graphics_enums = Ansys.Mechanical.DataModel.MechanicalEnums.Graphics
view = ExtAPI.Graphics.ViewOptions
pref = view.ResultPreference
notes = view.AnnotationPreferences
saved = {
    "units": ExtAPI.Application.ActiveUnitSystem, "mesh": view.ShowMesh,
    "extra": pref.ExtraModelDisplay, "contour": pref.ContourView,
    "scoping": pref.ScopingDisplay, "scaling": pref.DeformationScaling,
    "masses": notes.ShowPointMasses, "forces": notes.ShowForceArrows,
    "body_scopings": notes.ShowBodyScopings,
}
settings = Ansys.Mechanical.Graphics.GraphicsImageExportSettings()
settings.CurrentGraphicsDisplay = False  # Render at the requested size, not the window's.
settings.Width = int(fea_args["width"])
settings.Height = int(fea_args["height"])
settings.Background = GraphicsBackgroundType.White
settings.Capture = GraphicsCaptureType.ImageAndLegend
rows, image_rows, skipped = [], [], []

def _export(result, stem, orientation_name, exaggerated):
    pref.DeformationScaling = (graphics_enums.DeformationScaling.Auto if exaggerated
                               else getattr(graphics_enums.DeformationScaling, "True"))
    ExtAPI.Graphics.Camera.SetSpecificViewOrientation(getattr(ViewOrientationType, orientation_name))
    ExtAPI.Graphics.Camera.SetFit()
    height = ExtAPI.Graphics.Camera.SceneHeight  # Margin for titles and extrema labels.
    ExtAPI.Graphics.Camera.SceneHeight = Quantity(str(height.Value * 1.25) + " [" + str(height.Unit) + "]")
    ExtAPI.Graphics.Redraw()
    name = stem + "-" + orientation_name.lower() + ("-scaled" if exaggerated else "") + ".png"
    path = _fea_os.path.join(images, name)
    ExtAPI.Graphics.ExportImage(path, GraphicsImageExportFormat.PNG, settings)
    image_rows.append({"file": path, "result": str(result.Name), "view": orientation_name,
                       "deformation_display": "automatic exaggeration" if exaggerated else "true scale"})

try:
    if fea_args.get("units"):
        ExtAPI.Application.ActiveUnitSystem = getattr(MechanicalUnitSystem, fea_args["units"])
    view.ShowMesh = False
    pref.ExtraModelDisplay = graphics_enums.ExtraModelDisplay.NoWireframe
    pref.ContourView = graphics_enums.ContourView.SmoothContours
    pref.ScopingDisplay = (graphics_enums.ScopingDisplay.AllBodies if fea_args.get("context")
                           else graphics_enums.ScopingDisplay.ResultOnly)
    notes.ShowPointMasses = False
    notes.ShowForceArrows = False
    notes.ShowBodyScopings = False
    for result in analysis.Solution.Children:
        if not hasattr(result, "Maximum") or str(result.ObjectState) != "Solved":
            if hasattr(result, "Maximum"):
                skipped.append({"name": str(result.Name), "state": str(result.ObjectState)})
            continue
        stem = fea_safe_name(result.Name)
        table = _fea_os.path.join(out, stem + ".txt")
        result.ExportToTextFile(table)
        rows.append({"name": str(result.Name), "category": str(result.DataModelObjectCategory),
                     "maximum": str(result.Maximum), "minimum": str(result.Minimum),
                     "maximum_value": result.Maximum.Value, "minimum_value": result.Minimum.Value,
                     "unit": str(result.Maximum.Unit), "table": table})
        result.Activate()
        for orientation_name in fea_args["views"]:
            _export(result, stem, orientation_name, False)
            if fea_args.get("scaled") and "Deformation" in str(result.DataModelObjectCategory):
                _export(result, stem, orientation_name, True)
finally:
    ExtAPI.Application.ActiveUnitSystem = saved["units"]
    view.ShowMesh = saved["mesh"]
    pref.ExtraModelDisplay = saved["extra"]
    pref.ContourView = saved["contour"]
    pref.ScopingDisplay = saved["scoping"]
    pref.DeformationScaling = saved["scaling"]
    notes.ShowPointMasses = saved["masses"]
    notes.ShowForceArrows = saved["forces"]
    notes.ShowBodyScopings = saved["body_scopings"]

fea_script_result = dict(fea_mesh_counts(), analysis=str(analysis.Name), output=out,
                         solution_state=str(analysis.Solution.ObjectState),
                         results=rows, images=image_rows, skipped=skipped,
                         working_directory=str(analysis.WorkingDir), messages=fea_messages())
