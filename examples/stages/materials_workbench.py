# Example stage: define materials in a system's Engineering Data (Workbench,
# IronPython 2.7). Copy to project/stages/ and replace the names and values with
# sourced properties. Values below are placeholders, not recommendations.
# Run: fea.ps1 stage materials --arg system=SYS
eng = GetSystem(Name=fea_args.get("system", "SYS")).GetContainer(ComponentName="Engineering Data")
existing = [m.DisplayName for m in eng.GetMaterials()]

def create(name):
    if name in existing:
        raise Exception("Material already exists; inspect before creating it again: " + name)
    return eng.CreateMaterial(Name=name)

# Orthotropic: material axes follow the body's coordinate system (global unless set).
composite = create("Composite laminate - EXAMPLE")
composite.CreateProperty(Name="Density").SetData(
    SheetName="", Index=0, Variables=["Density"], Values=[["1600 [kg m^-3]"]])
composite.CreateProperty(Name="Elasticity", Behavior="Orthotropic").SetData(
    SheetName="", Index=0,
    Variables=["Young's Modulus X direction", "Young's Modulus Y direction", "Young's Modulus Z direction",
               "Poisson's Ratio XY", "Poisson's Ratio YZ", "Poisson's Ratio XZ",
               "Shear Modulus XY", "Shear Modulus YZ", "Shear Modulus XZ"],
    Values=[["50 [GPa]"], ["8 [GPa]"], ["50 [GPa]"], ["0.3"], ["0.05"], ["0.08"],
            ["3.5 [GPa]"], ["3.5 [GPa]"], ["4 [GPa]"]])

metal = create("Aluminum alloy - EXAMPLE")
metal.CreateProperty(Name="Density").SetData(
    SheetName="", Index=0, Variables=["Density"], Values=[["2700 [kg m^-3]"]])
metal.CreateProperty(Name="Elasticity", Behavior="Isotropic").SetData(
    SheetName="", Index=0, Variables=["Young's Modulus", "Poisson's Ratio"], Values=[["69 [GPa]"], ["0.33"]])

wb_script_result = {"created": [composite.DisplayName, metal.DisplayName],
                    "valid": [bool(composite.IsValid()), bool(metal.IsValid())]}
