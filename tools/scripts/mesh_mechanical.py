# Mesh (only if needed) and write the solver input deck for review. No solve.
analysis = fea_analysis()
if str(Model.Mesh.ObjectState) != "Solved":
    Model.Mesh.GenerateMesh()
deck = _fea_os.path.join(fea_folder(reports_dir), fea_safe_name(analysis.Name) + "-input.dat")
analysis.WriteInputFile(deck)
fea_script_result = dict(fea_mesh_counts(), analysis=str(analysis.Name), input_file=deck,
                         mesh_state=str(Model.Mesh.ObjectState),
                         analysis_state=str(analysis.ObjectState), messages=fea_messages())
