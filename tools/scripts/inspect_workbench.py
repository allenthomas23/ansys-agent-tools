# Executed inside Workbench (IronPython 2.7). No rebuild, update or save.
wb_script_result = {
    "systems": [{"name": s.Name, "display_text": s.DisplayText} for s in GetAllSystems()]
}
