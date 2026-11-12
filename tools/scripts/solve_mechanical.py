# Solve one analysis and evaluate its results. Can take as long as ANSYS needs.
analysis = fea_analysis()
analysis.Solution.Solve(True)
state = str(analysis.Solution.ObjectState)
if state == "Solved":
    analysis.Solution.EvaluateAllResults()
fea_script_result = dict(fea_mesh_counts(), analysis=str(analysis.Name), solution_state=state,
                         working_directory=str(analysis.WorkingDir),
                         results=[{"name": str(r.Name), "state": str(r.ObjectState)}
                                  for r in analysis.Solution.Children],
                         messages=fea_messages())
