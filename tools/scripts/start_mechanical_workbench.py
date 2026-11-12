# Executed inside Workbench (IronPython 2.7). Enables the API server of the
# system's Mechanical editor in this session; never starts another Workbench.
system = GetSystem(Name=fea_args["system"])
if fea_args.get("open_editor"):
    system.GetContainer(ComponentName="Model").Edit()
port = LaunchMechanicalServerOnSystem(SystemName=fea_args["system"])
wb_script_result = {"system": system.Name, "display_text": system.DisplayText, "port": int(port)}
