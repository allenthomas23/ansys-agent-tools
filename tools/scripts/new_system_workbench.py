# Executed inside Workbench (IronPython 2.7). Adds one analysis system; no save.
name = fea_args["name"]
if [s for s in GetAllSystems() if s.DisplayText == name]:
    raise Exception("A system named " + name + " already exists; inspect it instead")
system = GetTemplate(TemplateName=fea_args["template"], Solver=fea_args["solver"]).CreateSystem()
system.DisplayText = name
wb_script_result = {"name": system.Name, "display_text": system.DisplayText}
