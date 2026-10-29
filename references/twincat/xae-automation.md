# XAE Automation: builds, and edits through the open XAE

How to get real compiler output from a TwinCAT 3 (4024) project without the IDE in front of you
(rung 2 of the verification ladder in `SKILL.md`), and how to edit a project the user has open in
XAE without XAE asking to reload it. **TwinCAT-specific and Windows-only**: both need a PC with
TwinCAT XAE installed. On any other machine, the rung is unreachable; say "not compiled".

## Which tool

**First ask whether the user has the solution open in XAE.** `xae_edit.ps1 list` answers it, and
so does a fresh `<project>.project.~u` lock file (below).

| The solution is | Edit with | Build with |
|---|---|---|
| **open in the user's XAE** | `scripts/xae_edit.ps1`, through that XAE | `xae_edit.ps1 build`, in that XAE |
| closed | `scripts/tcpou.py`, on disk | `scripts/xae_build.ps1`, in a hidden XAE |

Mixing them is what makes XAE ask to reload. A write on disk to a file XAE holds raises `<file>
File has been changed outside the environment. Reload the new file?`: one `tcpou.py set` raised
two such prompts in a row. Worse, measured once: with an unsaved edit held in XAE for the same POU,
**Yes** led to *Save changes to the following items?*, and **Yes** there still left XAE holding the
disk version. The unsaved edit was gone. So while an XAE holds the solution, every edit goes
through it, and `tcpou.py` refuses to write (`--allow-open` overrides).

## Headless builds

`scripts/xae_build.ps1` drives XAE through its Automation Interface (COM/DTE). It opens the solution
in a **new, hidden** XAE process, builds it, prints the Build pane and the compiler entries of the
Error List, and quits. It never activates.

An XAE with a **different** solution open is left alone (seven builds, same PID, same title). An XAE
with the **same** solution open is not: it keeps running and responding, but within a second of the
build it raises a modal prompt, `<PLC>.xti … was modified outside of TwinCAT XAE. Do you want to
reload it?`. **Yes** reloads it with no further prompt. **No** keeps the old `.xti` in memory and
writes it back on the next save. The hidden XAE also rewrites the shared `.vs\<sln>\v15\.suo` when it
quits. **So when the solution is open, build with `xae_edit.ps1 build` instead**, which builds in
that XAE and raises no prompt. While a solution is open, XAE keeps a lock file beside it,
`<project>.project.~u` (three lines: user, machine, PID; rewritten about every 35 s); when it names a
live process `xae_build.ps1` prints a warning before building.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\xae_build.ps1 -Solution C:\src\Line1\Line1.sln
```

| Option | Effect |
|---|---|
| `-Rebuild` | Clean first. Lays out PLC memory anew, so `.tmc`/`.xti` differ from an incremental build |
| `-TreePath 'TIPC^PLC1^PLC1 Project^POUs^FB_X'` | Print that tree item and its children — confirms XAE sees a method or property `tcpou.py` added |
| `-SaveAll` | Save All after the build. Then `git status` shows what XAE would rewrite on save |
| `-ProgId` | Default `TcXaeShell.DTE.15.0`. An XAE integrated in Visual Studio is `VisualStudio.DTE.<ver>` |
| `-PublicAssemblies` | Folder holding that XAE's `envdte.dll`. Default is TcXaeShell's `Common7\IDE\PublicAssemblies` |

**Exit code:** 0 = every project built; 1 = a project failed (`SolutionBuild.LastBuildInfo` counts
them) or the script could not run. Quote the `Build complete -- N errors, M warnings` line when you
report the result — that line, not the exit code alone, is the evidence.

### Before you run it in someone's project

A build is not read-only. Exactly like a build in XAE, it writes:

- the PLC's `.tmc` and the `TmcHash` line in the PLC's `.xti`. With no compile state yet (a fresh
  clone or worktree) far more of the `.xti` changes: 208 lines on a production project,
- `_CompileInfo`. `-Rebuild` adds a new `<guid>.compileinfo` and leaves the old one,
- `_Boot/` (when not git-ignored) and `<PLC>.xti.bak`,
- the `.plcproj`, on the first build of a fresh project: it adds `<None Include="PLC1.tmc">` and
  re-indents `PlcProjectOptions`,
- a Measurement project's `.vsm`, if the solution has one. It is rewritten as soon as XAE opens the
  solution, with no build at all.

An incremental build with no source change still rewrites `_CompileInfo`, the `_Boot` files and the
`.xti`, but not the `.tmc`.

So: the agent runs a build **only when the user asked for a build or a compile check**, and says
first that these files will be rewritten. Run it while they are unmodified in git, and afterwards
restore them (`git restore <those paths>`) unless the user wants the build output kept. A build
changes no controller.

It builds **the files on disk**. Edits unsaved in an open XAE are not included — ask the user to
save first, or the build checks an older version than the one on their screen.

### Field notes

Verified on TwinCAT 3.1.4024.55, Windows 10, against a production project and a scratch TcUnit
project.

- **Use Windows PowerShell 5.1** (`powershell.exe`). PowerShell 7's COM and `Add-Type` support is
  not enough for this script.
- **Late-bound DTE reads the Error List as empty** from PowerShell. The script loads `envdte.dll`
  from the XAE's own `PublicAssemblies` and reads the panes early-bound. `LastBuildInfo` works
  either way, so a pass/fail without messages is the symptom of a wrong `-PublicAssemblies`.
- XAE rejects COM calls while busy (`RPC_E_CALL_REJECTED`); the script registers a message filter
  that retries them.
- `SuppressUI` hides modal dialogs. A project-repair prompt would be suppressed, not shown — so an
  empty Error List after opening is the check that none was raised.
- "Unknown TMC file version found - ignoring the file" on opening is harmless; the `.tmc` is
  regenerated by the build.
- Of two compiler errors on one broken line, one had no file name in the Error List. The Build pane
  printed above it carries `FB_X.TcPOU(65) : error: …` for both, so read both sections.

## Editing through the open XAE

`scripts/xae_edit.ps1` attaches to the XAE the user already has open and edits through its
Automation Interface. The edit lands in XAE's memory, so XAE never sees a file change behind its
back and asks nothing. An open editor shows the edit at once, and its tab gets the unsaved `*`. The
file changes only when XAE saves it, in XAE's own format: the same bytes the user's Ctrl+S would
write. Every command and option is in `../tools.md`.

The workflow, after `list` has shown the solution open:

1. `show` the tree path, then `get -Out` the part you will change. Tree paths look like
   `TIPC^PLC1^PLC1 Project^POUs^FB_X^M_Reset`.
2. Edit the file, then `set -FromFile` it, or `add-method` / `add-pou`.
3. `save` the POU, then run `st_review.py` on its `.TcPOU`: the reviewer reads the disk, which
   holds the edit only after the save.
4. `build`, if the user asked for one. It saves every unsaved PLC object first.
5. Logging in and the online change stay the user's gesture (`SKILL.md` rule 2). The tool never
   logs in.

What the tool does to keep the user's XAE safe, and why:

- **It attaches; it never starts an XAE.** Each XAE registers itself in the Running Object Table
  as `!TcXaeShell.DTE.15.0:<pid>`. With two running, asking COM for "the" XAE returns whichever
  registered first, so the tool lists them all and takes the one whose solution is the path
  given. None or several: it refuses. The ROT is separate per integrity level, so an XAE run as
  administrator is invisible to a shell that is not, and the tool says so.
- **It stops at an open dialog.** While any modal dialog is open in XAE, XAE rejects every COM
  call. Retrying, as `xae_build.ps1`'s message filter does, hung for good (killed after 180 s). A
  filter with a deadline gave up after 10 s, but the call it gave up on came back empty, not as an
  error. So the tool looks for dialogs through Win32 before the first call and before every write,
  and treats a call given up on (after 30 s) as a failure. Exit 2 names the dialog.
- **It leaves the user's unsaved edits alone.** `set`, `add-method` and `save` refuse a POU that
  holds unsaved edits the tool did not make, unless `-Force`. It tells them apart by a fingerprint
  of the POU's whole text taken after its own last write, kept per solution in `%TEMP%` and void
  once XAE restarts.
- **`build` checks first.** A build saves every unsaved PLC object, so it would save the user's
  half-typed edits too. Measured: two edits pending in memory were on disk afterwards, with the
  build's time. The tool lists unsaved objects and refuses when any is not its own, unless
  `-SaveUserEdits`.
- **It reads back every write**, and a difference other than line endings is exit 1.
- **It sets Structured Text only.** On an LD or CFC body, `ImplementationText` returns the same
  XmlArchive XML as the file (`<NWL>…`, `<CFC>…`). Writing back modified CFC XML worked once, which
  is too little to offer: `get` reads graphical bodies, `set` refuses them.
- **It never runs Save All**, which would also save the user's own work. `save` saves one object.

### Field notes

Measured on TwinCAT 3.1.4024.55 (TcXaeShell), Windows 10, Windows PowerShell 5.1, non-elevated,
against a copy of the scratch TcUnit solution open in a visible XAE and driven from a separate
`powershell.exe`, the way the tool runs. These were measured with probe scripts. The tool itself
has not yet run on an XAE PC: `evals/field-test-xae-edit.md` is the runbook for that.

- **No interop assembly is needed.** The tree item's IDispatch exposes the members of every
  interface: `DeclarationText`, `ImplementationText`, `ImplementationXml`, `Language`,
  `CreateChild`, `LookupChild`, `Child(i)`, `ChildCount`, `PathName`, `VSProjectItem` and more.
  The project's `.Object` is the `ITcSysManager`; `LookupTreeItem(<path>)` finds the item.
- **A set raises no dialog and leaves the file alone**, hash and mtime unchanged; `VSProjectItem.Saved`
  goes from True to False, and the readback equals what was set. That held with the POU open in an
  editor too. XAE's files are CRLF; the tool writes in the line endings of the text it replaces.
- **`CreateChild(name, 609, '', $null)` adds a method; `CreateChild(name, 604, '', 1)` a function
  block in ST, and language `6` one in LD** (an empty `<NWL>` network). A new POU's file is written
  and registered in the `.plcproj` at once, before any save, so `tcpou.py register` is not needed on
  this path. XAE generates the GUIDs. Other kinds (program, function, property, DUT, GVL, action)
  take other codes from Beckhoff's `ITcSmTreeItem::CreateChild` documentation; none is verified
  here, so the tool does not offer them.
- **`VSProjectItem.Save()` on a POU saves that POU and its methods**, with no dialog. A method's own
  `Save()` throws `NotImplementedException`, and its file name reads `<path>\FB_X.TcPOU;FB_X.M_Reset`;
  the tool saves the POU instead.
- **An XAE save writes the project's own format.** On a project with *Write ProductVersion* on, it
  changed `ProductVersion="3.1.4024.0"` to `"3.1.4024.12"` and dropped the final line break. On a
  production project with the option off, 452 of 453 POUs carry no `ProductVersion` and no final
  line break, so a save there should change only the edited lines (expected from the format; not
  yet saved on that project).
- **A build in the attached XAE raises no prompt**, `.xti` included: the XAE that rewrites it is the
  one holding it. `SolutionBuild.LastBuildInfo` counts failed projects.
- `$dte.ExecuteCommand('Edit.Undo')` from a script reports the command unavailable. Whether the
  user's Ctrl+Z undoes a script edit is not yet known.
- Not yet tested: unsaved typing by the user in the same POU (the PLC editor exposes no text
  buffer through DTE, so it could not be simulated; the runbook has a person type), an online
  change after a script edit, XAE and the shell at different elevations, and XAE's *Auto-load
  changes, if saved* option, which might silence the prompt for disk edits. Leave that option
  alone: the tool does not need it.

## Activation is not scripted here

There is deliberately no activation script. `SKILL.md` rule 2 stands: activating a configuration
replaces what runs on the controller, and that is a human gesture. Hand the user the steps; do not
perform them. That covers running TcUnit on a target too — the user activates, then the results
can be read back over ADS (`testing-tcunit.md`; the client side is in `ads-and-diagnostics.md`). TcUnit 1.3.2 shows its summary lines (`Tests:`,
`Successful tests:`, `Failed tests:`, `TESTS FINISHED RUNNING`) as **Errors** in the XAE Error
List, not on a Messages tab: read the counts, not the icon (`testing-tcunit.md`).

What to tell the user when the test controller also holds a machine project, learnt the hard way:

1. **Back up `C:\TwinCAT\3.1\Boot\Plc\` on the controller first.** Activating a scratch project
   there made persistent values of the machine project fail to restore, twice.
2. **Re-activating the machine project afterwards is part of the test**, not an optional clean-up.
   In field round 2 its persistent values came back through that re-activation. In round 5,
   which also restarted TwinCAT with the scratch project active, they stayed reset. Do not count
   on re-activation to restore them: the backup is the only copy.
3. Keep scratch test configurations free of axes and I/O.
4. If no free controller is available, the honest report is "built, not run".
