# Examples

Patterns from a completed study (a bonded multi-body frame with point masses, solved free-flying under inertia relief). Copy what fits into `project/`, then adapt names, values and checks. The API calls are verified on ANSYS 2025 R2; the example values are placeholders, not engineering data.

| File | Use |
|---|---|
| `stages/materials_workbench.py` | Orthotropic and isotropic materials in Engineering Data |
| `stages/import_mechanical.py` | Geometry import and a body list for mapping |
| `stages/setup_mechanical.py` | Materials, bonded joints, point masses, forces, supports, gravity, solver settings and results from `case.json` |
| `case.example.json` | The case file `setup` reads; every value needs the user's approval |
| `inertia_relief.apdl` | Command snippet for a free body |
| `relative_deformation.py` | Local post-processing: deformation relative to a reference region |

Typical sequence once copied:

```powershell
powershell.exe -NoProfile -File tools/fea.ps1 new-system --name "Bracket - Static"
powershell.exe -NoProfile -File tools/fea.ps1 stage materials --arg system=SYS
powershell.exe -NoProfile -File tools/fea.ps1 start-mechanical --system SYS --open-editor
powershell.exe -NoProfile -File tools/fea.ps1 stage import --arg geometry=source/Bracket.x_t
# create the named selections case.json uses (in Mechanical, or in a stage)
powershell.exe -NoProfile -File tools/fea.ps1 stage setup
powershell.exe -NoProfile -File tools/fea.ps1 mesh
powershell.exe -NoProfile -File tools/fea.ps1 solve
powershell.exe -NoProfile -File tools/fea.ps1 report --scaled
```
