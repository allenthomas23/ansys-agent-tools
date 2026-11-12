# ANSYS API notes

Lessons verified with ANSYS 2025 R2 (`v252`), `ansys-workbench-core` 0.14.0 and `ansys-mechanical-core` 0.13.5 while running a complete static study (import, materials, contacts, point masses, inertia relief, solve, report). Add to this file when an API call surprises you.

## Session lifecycle

- Use `connect_workbench`, not `launch_workbench`. On an attached `ClientWrapper`, `exit()` only disconnects; on a launched one it resets and terminates Workbench. The two are not interchangeable.
- Use `connect_to_mechanical(clear_on_connect=False, cleanup_on_exit=False)`. Never call `Mechanical.exit()` on a borrowed session: it closes the user's Mechanical. The runner disables keepalive threads and lets its short-lived process release the connection.
- `StartServer()` in the Workbench Command Window enables the open session; `wnua` works on Windows.
- `LaunchMechanicalServerOnSystem(SystemName="SYS")`, run in Workbench, enables the API server of that system's open Mechanical editor and returns its port. `GetSystem(Name="SYS").GetContainer(ComponentName="Model").Edit()` opens the editor.

## Script transport and errors

- Workbench's interpreter is IronPython 2.7. Keep server scripts Python 2.7-compatible: no f-strings, annotations or other Python 3-only syntax.
- `run_script_string` logs some script errors and returns `None` instead of raising. The runner wraps every script in a success/error envelope and treats a missing or malformed response as a failure. A failure can happen after earlier changes; there is no rollback.
- Workbench returns `wb_script_result`; Mechanical returns the value of the script's last expression (the runner uses `fea_script_result`). These are globals in a shared interpreter: don't run two commands on one session at once.
- `ExtAPI.Application.Messages` entries have no `Summary` property; `str(message)` gives severity and text.

## Workbench project

- `GetTemplate(TemplateName="Static Structural", Solver="ANSYS").CreateSystem()` creates a system; set `DisplayText` to name it.
- Engineering Data: `GetSystem(...).GetContainer(ComponentName="Engineering Data")`, then `CreateMaterial`, `CreateProperty(Name="Elasticity", Behavior="Orthotropic"|"Isotropic")` and `SetData(SheetName="", Index=0, Variables=[...], Values=[["55 [GPa]"], ...])`. `GetMaterials()` lists them (`DisplayName`). In Mechanical, call `Model.Materials.RefreshMaterials()` before assigning new ones.
- `Save()` saves an already-saved project, including the open Mechanical model; `Save(FilePath=...)` for the first save. Check that the session holds the intended project before saving.

## Geometry

- A Workbench-owned Geometry Import rejects explicit import preferences: `Import(path, GeometryImportPreference.Format.Automatic, None)` works; the preferences belong to Workbench.
- Parasolid body names were not kept on import. Map imported bodies to the source by centroid and volume (`body.GetGeoBody().Centroid`, `body.Volume`) and check the count; import order doesn't match assembly order.
- `ExtAPI.DataModel.GeoData.Unit` gives geometry coordinate units (`m` for SI). Face/body `Centroid` values are in those units.
- Selections: `ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)` with `.Ids = [...]`; a named selection object can be assigned to `Location` directly.

## Connections, masses and loads

- Imported contacts reflect CAD touching, not joints. Suppress them and add explicit `AddContactRegion()` objects with the approved behavior.
- Bonded `ContactFormulation.PurePenalty` avoided MPC overconstraint where joints met remote-mass couplings. `TrimContact = On` with a tolerance greatly reduced contact data when many small faces targeted large plates; check every joint still finds target elements.
- Separate remote forces and remote masses on the same faces cause an overlap warning. Surface forces avoid duplicate coupling; combine masses that share attachment faces (keep total mass, CG and inertia, and record the grouping).
- Point mass: `Behavior = LoadBehavior.Deformable`, `RemotePoint.RelaxationMethod = False`, diagonal inertia via `MassMomentOfInertiaX/Y/Z` (no products of inertia).
- Force by components: `DefineBy = LoadDefineBy.Components`, then `XComponent.Output.DiscreteValues = [Quantity("10 [N]")]`.
- Pin solver units: `SolverUnits = SolverUnitsControlType.Manual`, `SolverUnitSystem = WBUnitSystemType.ConsistentMKS`. Changing display units for figures must not change the solver input.

## Inertia relief (free body)

- Automatic inertia relief (`AIRL,6`) needs bonded contact with small sliding and `NEQIT,1,FORCE`, plus shared-memory solving (`SolveProcessSettings.DistributeSolution = False`).
- Mechanical's generated remote-mass attachments are CONTA174 elements without small sliding, so setting it on explicit contacts isn't enough: the solver rejects the model. `examples/inertia_relief.apdl` sets `KEYOPT(18)=1` on every CONTA174 type.
- Use an explicit six modes: automatic mode counting conflicted with remote-point DOF handling. The AIRL printout's accelerations come from an eigensolve and aren't physical axis accelerations when its reference point lacks six DOFs; report applied forces and masses instead.
- Displacements are relative to the solver's reference. Report deformation relative to a region of the structure (`fea_post.fit_rigid_motion`).

## Mesh, solve and results

- `analysis.WriteInputFile(path)` writes the deck without solving; review it first (`audit-deck`). Nodes are in solver units; `nblock` uses fixed-width fields.
- `Solution.Solve(True)` can return normally with `Solution.ObjectState == SolveFailed`. Check the state before evaluating or exporting results.
- `ExtAPI.DataModel.MeshDataByName("Global")` gives `NodeCount` and `ElementCount`.
- `result.ExportToTextFile(path)` writes "Node Number / value" rows in the active display unit system, named in the header.

## Images

- `GraphicsImageExportSettings` with `CurrentGraphicsDisplay = False`, custom `Width`/`Height`, white background and `GraphicsCaptureType.ImageAndLegend` gives sharp PNGs independent of the window size.
- Hide mesh, point-mass and force annotations (`ViewOptions.ShowMesh`, `AnnotationPreferences.ShowPointMasses/ShowForceArrows/ShowBodyScopings`) and enlarge `Camera.SceneHeight` about 25% after `SetFit()` to leave room for titles and extrema. Restore the user's settings afterwards.
- True-scale deformation is `getattr(DeformationScaling, "True")`; the stub's `True_` alias doesn't exist at runtime.
- Call `ExtAPI.Graphics.Redraw()` after moving the camera (`FocalPoint`, `SceneWidth`, `ViewVector`) for a close-up, before exporting.

## References

- [Workbench attachment](https://workbench.docs.pyansys.com/version/stable/getting-started/connection.html)
- [PyWorkbench public API](https://workbench.docs.pyansys.com/version/stable/api/ansys/workbench/core/public_api/index.html)
- [Mechanical existing-GUI attachment](https://github.com/ansys/pymechanical/discussions/996)
- [PyMechanical session API](https://mechanical.docs.pyansys.com/version/stable/api/ansys/mechanical/core/mechanical/Mechanical.html)
