# Executed inside Workbench (IronPython 2.7). Saves the whole project, including
# an open Mechanical model. Refuses to save a project that lacks the expected system.
import os
names = [s.DisplayText for s in GetAllSystems()]
if fea_args["expect"] not in names:
    raise Exception("Refusing to save: no system named " + fea_args["expect"] + "; found " + repr(names))
target = fea_args.get("path")
if target:
    if os.path.exists(target):
        raise Exception("Project path already exists; refusing to overwrite " + target)
    Save(FilePath=target)
else:
    Save()
wb_script_result = {"saved": True, "path": target, "systems": names}
