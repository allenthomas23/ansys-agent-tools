# Setup and session attachment

The defaults in `fea.config.json` use Windows Named User Authentication (`wnua`) on a loopback host. Run the tools as the same Windows user as ANSYS. There are no hardcoded installation paths and no ANSYS launcher in this kit: it attaches to servers you enable in your open session.

## Workbench

In the open Workbench window, choose **File > Scripting > Open Command Window** and run:

```python
StartServer()
```

It returns the port ([PyWorkbench connection docs](https://workbench.docs.pyansys.com/version/stable/getting-started/connection.html)). Put it in `fea.local.json` in the repository root (ignored by Git):

```json
{
  "workbench": {"port": 50001}
}
```

Or pass `--port 50001` to a command. Ports change every time ANSYS starts; run `StartServer()` again then, but not while an existing connection still works.

## Mechanical

With the Workbench port configured, let the tools enable Mechanical for an existing system (`inspect` lists system names such as `SYS`):

```powershell
powershell.exe -NoProfile -File tools/fea.ps1 start-mechanical --system SYS --open-editor
```

This opens the system's Model editor (if `--open-editor`), starts its API server and records the port in `fea.local.json`. Repeat after Mechanical is closed and reopened.

Manual alternative: in Mechanical's Scripting pane run `Ansys.ACT.Mechanical.MechanicalAPI.Instance.ApplicationAPI.StartGrpcServer(10000)` with a free port ([example](https://github.com/ansys/pymechanical/discussions/996)) and add `"mechanical": {"port": 10000}` to `fea.local.json`.

Check with `tools/fea.ps1 inspect --backend mechanical`.

## Security modes

Each endpoint's `security` must match its server (`wnua`, `mtls` or `insecure`). Never downgrade it to get past a failed connection. Older releases can need a different transport; check that release's documentation. This kit doesn't change firewall or license settings.

## Git LFS

`.gitattributes` stores native ANSYS binaries (`.mechdb`, `.wbpz`, `.agdb`, `.scdoc`, `.pmdb`, `.mechdat`) and common CAD exchange formats in Git LFS. Run `git lfs install --local` in each checkout. Commit a `.wbpj` together with its `_files` folder; `.gitignore` leaves out locks, backups and regenerable solver files (`.rst` and friends). Add patterns when a study needs other formats.

## Troubleshooting

- **Connection refused / closed port:** the server isn't running or the port is stale. Enable it in the intended window and update `fea.local.json`. The tools never start a replacement session.
- **Socket permission errors inside an agent sandbox:** run the same command with the sandbox's approved local network access.
- **Authentication errors:** the transport or Windows user doesn't match. Don't switch modes blindly.
- **A command hangs:** a modal dialog or a running solve blocks scripts. Look at the ANSYS window before retrying; a stopped client can leave work running in ANSYS.
- **Static Structural missing from the Workbench toolbox:** check installed products and license. A Workbench connection doesn't prove a Mechanical license is available.
