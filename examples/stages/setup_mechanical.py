# Example stage: build a linear static case from named selections and a case file.
# Shows API patterns verified on Mechanical 2025 R2; the physics choices are the
# case file's, and every one of them needs the user's approval.
# Copy to project/stages/, copy examples/case.example.json to project/case.json,
# create the named selections it lists, then: fea.ps1 stage setup
import json
case = json.load(open(_fea_os.path.join(study_root, "case.json")))
analysis = fea_analysis(case.get("analysis", 0))
if [c for c in analysis.Children if str(c.Name) == case["marker"]]:
    raise Exception("This case is already set up; inspect instead of building twice")

def named(name):
    groups = Model.NamedSelections  # None until the model has a named selection.
    found = [n for n in (groups.Children if groups else []) if str(n.Name) == name]
    if len(found) != 1:
        raise Exception("Named selection not found uniquely: " + name)
    return found[0]

def quantity(value, unit):
    return Quantity(str(value) + " [" + unit + "]")

for body_name, material in case.get("materials", {}).items():
    bodies = [b for b in fea_bodies() if str(b.Name) == body_name]
    if len(bodies) != 1:
        raise Exception("Body not found uniquely: " + body_name)
    bodies[0].Material = material

# CAD contacts are not engineering joints: suppress them and add explicit ones.
if case.get("suppress_imported_contacts"):
    for contact in Model.Connections.GetChildren(DataModelObjectCategory.ContactRegion, True):
        contact.Suppressed = True
for joint in case.get("bonded_joints", []):
    contact = Model.Connections.AddContactRegion()
    contact.Name = joint["name"]
    contact.SourceLocation = named(joint["source"])
    contact.TargetLocation = named(joint["target"])
    contact.ContactType = ContactType.Bonded
    # Pure penalty avoids MPC equations competing with remote-point couplings.
    contact.ContactFormulation = ContactFormulation.PurePenalty
    contact.SmallSliding = ContactSmallSlidingType.On
    if joint.get("trim_mm"):
        contact.TrimContact = ContactTrimType.On
        contact.TrimTolerance = quantity(joint["trim_mm"], "mm")

for mass in case.get("point_masses", []):
    obj = Model.Geometry.AddPointMass()
    obj.Name = mass["name"]
    obj.Location = named(mass["faces"])
    obj.Mass = quantity(mass["kg"], "kg")
    obj.XCoordinate, obj.YCoordinate, obj.ZCoordinate = [quantity(v, "m") for v in mass["cg_m"]]
    obj.Behavior = LoadBehavior.Deformable
    obj.RemotePoint.RelaxationMethod = False
    inertia = mass.get("inertia_kg_m2", [0, 0, 0])  # Diagonal terms about the CG.
    obj.MassMomentOfInertiaX = quantity(inertia[0], "kg m^2")
    obj.MassMomentOfInertiaY = quantity(inertia[1], "kg m^2")
    obj.MassMomentOfInertiaZ = quantity(inertia[2], "kg m^2")

for load in case.get("forces", []):
    force = analysis.AddForce()
    force.Name = load["name"]
    force.Location = named(load["faces"])
    force.DefineBy = LoadDefineBy.Components
    force.XComponent.Output.DiscreteValues = [quantity(load["N"][0], "N")]
    force.YComponent.Output.DiscreteValues = [quantity(load["N"][1], "N")]
    force.ZComponent.Output.DiscreteValues = [quantity(load["N"][2], "N")]

for support in case.get("fixed_supports", []):
    fixed = analysis.AddFixedSupport()
    fixed.Location = named(support)

if case.get("gravity"):
    gravity = analysis.AddEarthGravity()
    gravity.Direction = getattr(GravityOrientationType, case["gravity"])

settings = analysis.AnalysisSettings
settings.LargeDeflection = bool(case.get("large_deflection", False))
settings.WeakSprings = WeakSpringsType.Off
settings.SolverType = SolverType.Direct
# Pin solver units so changing display units for figures cannot change the deck.
settings.SolverUnits = SolverUnitsControlType.Manual
settings.SolverUnitSystem = WBUnitSystemType.ConsistentMKS

if case.get("apdl"):
    # Inertia relief (AIRL) needs shared-memory solving.
    analysis.SolveConfiguration.SolveProcessSettings.DistributeSolution = False

snippet = analysis.AddCommandSnippet()  # Also marks the case as built.
snippet.Name = case["marker"]
snippet.Input = (open(_fea_os.path.join(study_root, case["apdl"])).read() if case.get("apdl")
                 else "! " + case["marker"])

Model.Mesh.ElementOrder = ElementOrder.Quadratic
Model.Mesh.ElementSize = quantity(case["element_size_mm"], "mm")
analysis.Solution.AddTotalDeformation().Name = "Total deformation"
analysis.Solution.AddEquivalentStress().Name = "Equivalent stress"
fea_script_result = {"analysis": str(analysis.Name), "messages": fea_messages(),
                     "contacts": [j["name"] for j in case.get("bonded_joints", [])],
                     "point_mass_kg": sum(m["kg"] for m in case.get("point_masses", [])),
                     "structural_mass_kg": sum(b.Mass.Value for b in fea_bodies() if not b.Suppressed)}
