# Field review -- `xae_edit.ps1`, editing through the open XAE

This round ran `field-test-xae-edit.md` on the TwinCAT PC on 2026-10-29: TwinCAT 3.1.4024.55
(TcXaeShell, `TcXaeShell.DTE.15.0`), Windows 10 22H2 (19045), Python 3.12.10, Windows PowerShell
5.1.19041.7548. The skill was at commit `a736eef`, the head of `worktree-xae-edit` (PR #49), in its
own clone. `<scratch>` was a fresh clone of the scratch TcUnit solution at `8f3eaab`, plus the
CFC probe POU from round 5, committed before E1. XAE was started from the Start menu and the
solution opened by hand, not elevated except in E1d. `PYTHONUTF8` and `PYTHONIOENCODING` were
cleared in every shell that ran a check. Project_A was open in a second XAE during part of the
round. That one was never attached to, and it shows in two `list` outputs below as "Project_A".

**Stopped at E9 as the runbook says, then finished on the maintainer's word.** E9's own steps (b)
and (c) pass. But one more case was tried, with the POU saved and the person typing in a method,
and there `set` overwrote the typing (E9f). The maintainer chose to finish the round on the
unchanged tool and fix afterwards. So E10 to E15 and E18 ran too. E16 (controller) and E17
(optional) did not run.

Four defects came out, F1 to F4 below. F3 is the one the runbook warns about: **the tool can
overwrite and save what the person typed in a method, property accessor or interface member.**
F2 is its cause. The rest of the round passes: list and attach, dialog detection, the guard for
the POU's own body, graphical refusal, every object kind (the alias after a vInfo change), the
lock guard in `tcpou.py`, and its release.

| # | Result | Evidence |
|---|---|---|
| E0 | pass | `run_tests.py`: last line `all checks passed`, exit 0. `xae_edit_tests.ps1`: 83 `ok`, `all checks passed`, exit 0. A first run with Project_A's XAE open failed one check, `list with no XAE: exit 0 and says so`, which printed that XAE's line. The test assumes no XAE is running. With every XAE closed it passed |
| E1a | pass | `no XAE in the Running Object Table`, exit 0 |
| E1b | pass | `PID 11828  TcXaeShell.DTE.15.0  <scratch>\TcUnitScratch.sln`, exit 0. Earlier the tester had opened the round-5 copy from the recent list. `show -Solution <scratch>\…` then exited 2 with `no XAE holds <scratch>\TcUnitScratch.sln. Ask the user to open it in XAE, or, with XAE closed, use tcpou.py and xae_build.ps1.` That is correct: it attaches by path, not by name |
| E1c | pass | `PID 11828 … <scratch>\TcUnitScratch.sln` and `PID 11424  TcXaeShell.DTE.15.0  (no solution open)`. `show` printed `TIPC` / `type 14` / `^PLC1  type 56`, exit 0 |
| E1d | pass | `list`: `no XAE in the Running Object Table` and `XAE process 5424 is not in this shell's Running Object Table: it runs as administrator and this shell does not, or the other way round, or it is still starting. Run both at the same level.`, exit 0. `show` exits 2 with `no XAE holds …` and the same line |
| E2 | pass | `type 604`, `language 1 (ST)`, `file <scratch>\TcUnitScratch\PLC1\POUs\FB_Sequence.TcPOU`, `saved True`, `^M_Fail  type 609` |
| E3 | pass | `set the impl of TIPC^PLC1^PLC1 Project^POUs^FB_Sequence in XAE (unsaved; the file changes on: xae_edit.ps1 save)`, exit 0. Hash and mtime unchanged. `show`: `saved False, edited by this tool`. `Compare-Object` printed nothing. No dialog. In the editor, `// E3` was there and the tab had `*` |
| E4 | **fail (F1)** | `set -Part decl` exit 0, prints `(unsaved; …)`, but the file was written during the call and `show` says `saved True`. Reproduced with no one touching XAE: mtime before the set 13:22:35.331, after it 13:26:27.117. It happens with the editor closed too, and the save takes pending body edits with it. See *F1* |
| E5 | partial | Both exit 0: `added fb …^FB_XeSt as <scratch>\…\FB_XeSt.TcPOU (saved). XAE registers it in the .plcproj itself`, the same for `FB_XeLd`. Both files exist; `show` gives 604 with language 1 and 6. **The `.plcproj` on disk did not change** (mtime from before E1, no `Compile` entries) until the E10 build saved it. That build added exactly the two entries. The probes' "registered in the .plcproj at once" does not hold: the registration is in XAE's memory until the project is saved |
| E6 | **fail (F1, F2)** | `added method …^FB_XeSt^M_Check in XAE (unsaved; …)`, exit 0. The declaration write saved the POU, so the method's declaration was on disk at once. The body was set after it and stayed in memory only (`get` returns `M_Check := nIn > 0;`, the file has an empty body), yet `show` gave `saved True (its file object …^FB_XeSt)`, not `False, edited by this tool`. `save` then printed `nothing to save: … is up to date` |
| E7 | pass | `refused: the body of …^FB_XeLd is not Structured Text (language 6), and this tool sets Structured Text only. Edit it in XAE.`, exit 1. `show`: `language 6 (LD)`. `get`: `(a graphical body: XML, which set refuses)`, and `ld.xml` starts `<NWL><XmlArchive><Data>`. **CFC is language 5**: `show …^FB_CfcProbe` gives `language  5`, and `set` refuses it the same way |
| E8 | **fail (F2)** | `save "…^FB_Sequence^M_Fail"` printed `nothing to save: … is up to date`, exit 0, while a body set on `M_Fail` was pending in memory. The save format itself, from E4's diff, holds only the edited lines, `ProductVersion="3.1.4024.0"` becoming `"3.1.4024.12"`, and the final line break dropped. No other line changed |
| E9 | pass for (a) to (d), **fail for E9e/E9f (F3)** | (a) `saved False, edited by this tool`. (c) The tester's space landed in the body: `show` gave `saved False, edited by someone else`, `set` exited 1 with `refused: …^FB_Sequence holds unsaved edits this tool did not make, probably typed in XAE. …`, and the space stayed. (b) A space in `M_Fail`'s own editor, with the POU still unsaved from (a): the same refusal, and the space stayed. (d) `save` refused; `set … -Force` printed `warning: … holds unsaved edits this tool did not make; going ahead (-Force)` and exit 0, and the body read back as `b.st`; the next `save` was refused again. The `M_Fail` tab already showed `*` before the typing, from this tool's own method set. **E9e**, added: the tester saved `FB_Sequence` (Ctrl+S), then typed a space in `M_Fail`. `show` gave `saved True`; a body `set` went through; `show` then gave `edited by this tool`; `save` wrote the typed space to disk. **E9f**, added: POU saved, tester typed `//xyz` in `M_Fail`. `show "…^M_Fail"` gave `saved True (its file object …)`; `set "…^M_Fail" -Part impl` exited 0, and `//xyz` was gone. See *F3* |
| E10 | **fail (F4)**, (b) not reached | (a) With a space typed in the body: `found no 'TIPC^<PLC>^<PLC> Project' node, so cannot check what the build would save. Pass -SaveUserEdits to build anyway.`, exit 2, after 0.8 s. It refuses, but for the wrong reason: the walk finds no PLC project at all. `-SaveUserEdits`: Build pane `Build complete -- 0 errors, 0 warnings : ready for download!`, `Build: 2 succeeded or up-to-date, 0 failed`, `Projects failed: 0`, exit 0, 8.2 s, **no `.xti` prompt**. It printed no `saved …` lines, since the walk found nothing. `show` gives `saved True` for every POU. The build saved the `.plcproj` too. (b) The unsaved cycle-time change showed in DTE as document `<scratch>\TcUnitScratch\PLC1\PlcTask.TcTTO`, `Saved=False`: a PLC-project file, not the `.tsproj`. `build` exited 2 with the F4 line, 0.7 s, so the guard was not tested. `Test-ObjectFileName` matches `.TcTTO`, so `Get-UnsavedDocuments` would leave this one to the tree walk |
| E11 | pass | `refused: XAE has this project open (<scratch>\TcUnitScratch.project.~u: rewritten 0 s ago). A write on disk makes it ask to reload, and edits it holds unsaved can be lost. Edit through that XAE with scripts/xae_edit.ps1, or ask the user to close the solution. --allow-open writes anyway.`, exit 1, file unchanged, no prompt. **The lock file is `TcUnitScratch.project.~u` in the `.sln` folder itself**, next to the `.sln`, rewritten on every edit. It holds four lines: user, machine name, XAE PID, a tick count |
| E12 | pass | `tcpou.py set … --allow-open` raised the prompt. `list`: `PID 5496  TcXaeShell.DTE.15.0  dialog: [#32770] 'TcXaeShell' \| &Yes \| &No \| Cancel \| <scratch>\…\FB_Sequence.TcPOU  File has been changed outside the environment. Reload the new file?` `show`, `get`, `set`, `save` and `build` each exited 2 in 0.5-0.6 s with `could not tell which XAE holds <scratch>\TcUnitScratch.sln. Ask the user to answer what XAE shows, then run this again:` and the dialog line. None advises `tcpou.py`; the file was unchanged and `x.st` was not written. The tester then answered Yes |
| E13 | pass | Error List floating: `list` shows the solution, no `dialog:`; `show` exit 0 |
| E14 | recorded | Editor open, `set` with `// E14`, the tester pressed Ctrl+Z once in the body: **nothing changed**. `b4.st` equals `b3.st`, `// E14` included; `show` still `saved False, edited by this tool` |
| E18a | pass | `PRG_Xe`: type **602**, language 1. `F_XeAdd`: `created with vInfo form 1 of 2: String[] [1, INT]`, type **603**, language 1. Both `saved False, edited by this tool` (the body set after the declaration's save makes them unsaved again) |
| E18b | pass after E18g for the alias | `ST_Xe` **606**, `E_Xe` **605**, `U_Xe` **607**, `GVL_Xe` **615** (`.TcGVL`): exit 0, `(saved)` (F1), files read back with the declarations given. `T_XeMm` failed: `XAE did not create T_XeMm (type 623) in TIPC^PLC1^PLC1 Project^DUTs: vInfo null: TwinCAT PLC automation call (ITcSmTreeItem:CreateChild) failed: Base class not specified! Parameter name: baseClass`, exit 1. See E18g |
| E18c | pass | `I_Xe` is `.TcIO`, type **618**. `add-method`: `created with vInfo form 1 of 2: String BOOL`, the method type **610**. `add-property -NoSet`: `created with vInfo form 1 of 2: String LREAL` and `added the Get accessor`, property type **612**, `Get` type **654**. No `removed the Set accessor` line: XAE adds no accessor itself here, so there was no Set to remove, and `DeleteChild('Set')` was not exercised |
| E18d | pass, F2 again | `FB_XeChild` saved at creation (F1); its declaration reads back `FUNCTION_BLOCK FB_XeChild EXTENDS FB_XeSt IMPLEMENTS I_Xe`. `add-method M_Probe -FromImpl`: exit 0, one vInfo form, no line. `add-property Level -NoSet`: `created with vInfo form 1 of 2: String[] [1, LREAL]`, `added the Get accessor`. `set "…^Level^Get"` exit 0. `show "…^FB_XeChild^Level^Get"`: type **613**, `language 1 (ST)`, file `FB_XeChild.TcPOU`, but `saved True (its file object …)`, not `False, edited by this tool` (F2) |
| E18e | pass, F2 again | `add-property Speed`: `created with vInfo form 1 of 2: String[] [1, LREAL]`, `added the Get accessor`, `added the Set accessor`; property **611**, `Get` **613**, `Set` **614**. Both accessor sets exit 0. `sd.st` holds `PUBLIC` / `VAR` / `END_VAR`. `show` gives `saved True` throughout (F2) |
| E18f | pass with F2/F4 | `save` exits 0 for every object. PRG and FUN print `saved …`; every other one prints `nothing to save: … is up to date`, rightly for DUT/GVL/ITF (F1 had saved them), wrongly for `FB_XeChild` and `FB_XeSt`, whose accessor and method bodies were in memory only (F2). A plain `build` hits F4 (exit 2). `-SaveUserEdits`: `Build complete -- 0 errors, 0 warnings`, exit 0, 6.5 s; it wrote the accessor bodies to disk. `tcpou.py check` printed `ok` for all 11 new files, exit 0. The `.plcproj` diff adds exactly the 9 new files' `Compile` entries, nothing else |
| E18g | alias form found | `CreateChild('T_XeMm', 623, '', 'LREAL')` worked: type 623, `<scratch>\…\DUTs\T_XeMm.TcDUT`. XAE's skeleton is the declaration `LREAL` alone, not a `TYPE` block. `set -Part decl` with `t_d.st` then made it `TYPE T_XeMm : LREAL;` / `END_TYPE`, and it builds. The other forms were not needed |
| E15 | pass | After *Close Solution*: no `*.~u` left anywhere under `<scratch>`, at once. `list`: `PID 5496 … (no solution open)`. The E11 command ran at once: exit 0. The guard does not linger |
| E16 | not run | No test controller in this session |
| E17 | not run | Optional |

## F1 -- `set -Part decl` saves the object at once

Setting `DeclarationText` on a POU, a method or an alias wrote the whole file during the call, and
`VSProjectItem.Saved` went back to True. That happened with the editor open or closed. Body edits
pending in memory went to disk with it: `// E4i`, set into the body before a declaration set, was
on disk afterwards. `ImplementationText` does not do this (E3, and E4 with the body: mtime
unchanged, `saved False`). Every command that writes a declaration does it: `set -Part decl`,
`new -FromDecl`, `add-method` (its declaration is always written). The tool still prints
`(unsaved; the file changes on: xae_edit.ps1 save)`.

The probes' *A set raises no dialog and leaves the file alone* (`references/twincat/xae-automation.md`)
holds for bodies only. What follows from F1:

- the message is wrong, and the user cannot discard a declaration change by closing without saving;
- the user's own unsaved edits in that object get saved too, if the guard lets the write through
  (it does after `-Force`, and in F3's case);
- the README's and the runbook's "file untouched until save" needs a declaration exception.

## F2 -- a member's edits do not mark its POU unsaved

A body set on a method or a property accessor, by this tool or by typing, leaves the POU's
`VSProjectItem.Saved` at True. XAE records the change in a DTE document of its own, named
`<file>;<POU>.<member>`, for example `…\FB_XeSt.TcPOU;FB_XeSt.M_Check` and
`…\FB_XeSt.TcPOU;FB_XeSt.Speed.Get`, with `Saved=False`. That document exists although no editor
window was opened for it. A probe read them all (kind `{CFF47BB1-5559-4BDE-A2AF-06B30BC64F6C}`).
`Document.Save()` on such a document returned 1 (`vsSaveSucceeded`), wrote the file, and set
`Saved` to True. The POU's own `Saved` stayed True throughout.

The tool reads only the POU's `Saved`, so:

- `show` reports a member edit as `saved True`;
- `save` says `nothing to save` and leaves it in memory (E6, E8, E18f);
- `Assert-OwnerClean` returns at once when the POU reads saved, so it never compares fingerprints
  (F3);
- `Get-UnsavedDocuments` drops every document whose name before `;` is a PLC object file, which is
  exactly these, so `build`'s guard cannot see them either (once F4 is fixed).

## F3 -- `set` overwrites typing in a method (the one the runbook stops on)

Precondition: the POU itself is saved, and the person has typed in one of its methods (or
accessors). That is the ordinary case: save, then go on typing. Then:

- `show "…^FB_Sequence"` and `show "…^FB_Sequence^M_Fail"` both say `saved True`;
- `set "…^M_Fail" -Part impl` exits 0, and what was typed there is gone (E9f: `//xyz`);
- `set "…^FB_Sequence" -Part impl` exits 0 and records a fingerprint that holds the person's typing
  as this tool's own. A `save` then writes that typing to disk with no question (E9e).

Runbook E9 (b) passed only because step (a) had left the POU unsaved, so the fingerprint was
compared.

## F4 -- `build` finds no PLC project

`Get-UnsavedObjects` walks `TIPC` → each PLC → each child named `* Project`. But `TIPC^PLC1`'s
`Child(i)` list holds only `PLC1 Instance` (type 57). `show "TIPC^PLC1"` prints just that.
`LookupTreeItem('TIPC^PLC1^PLC1 Project')` finds the project (type 600) anyway. So
`$roots` stays 0, and every plain `build` exits 2 with `found no 'TIPC^<PLC>^<PLC> Project' node`.
It fails closed, so nothing is lost. But the guard never runs, and `-SaveUserEdits` is the only
way to build, which saves everything with no check.

## Suggested fixes (not made on the PC)

1. Owner dirty = the POU's `VSProjectItem.Saved` is False **or** any `Dte.Documents` entry whose
   `FullName` starts with `<owner file>;` has `Saved` False. Use that in `Assert-OwnerClean`,
   `show`, `Update-OwnerState`, `Remove-SavedState` and the build guard (F2, F3).
2. `save`: after `VSProjectItem.Save()`, also `Save()` each unsaved `<owner file>;…` document, then
   check both again (F2).
3. Build guard: find the PLC project by `LookupTreeItem("TIPC^$plc^$plc Project")`, or by the
   child whose `ItemType` is 600 through `LookupChild`, not by `Child(i)` (F4). Map unsaved
   `<file>;…` documents to their owner and compare fingerprints rather than dropping them (F2).
4. Declarations: report what XAE did (read `Saved` after the write) instead of always "unsaved".
   Document that a declaration write saves the object. Keep the guard in front of it, so it never
   saves typing it did not make (F1).
5. Alias: pass the base type as `vInfo` (`'LREAL'` for `TYPE T_XeMm : LREAL;`, taken from the
   declaration) and then set the declaration (E18g).
6. `xae_edit_tests.ps1`'s `list with no XAE` should skip, not fail, when an XAE is running (E0).

## Re-run after the fix

Fixes 1 to 6 were made on the branch after the round, in this clone, and the failed checks re-run
on the same XAE with the same `<scratch>`, solution reopened by hand. `xae_edit_tests.ps1`: 88 `ok`,
the no-XAE check skipped while an XAE ran, `all checks passed`; `run_tests.py`: `all checks passed`.

| # | Result | Evidence |
|---|---|---|
| R4 | pass | `set -Part decl` adding `nR4`: `set the decl of …^FB_Sequence in XAE (saved: XAE writes the file when a declaration is set)`, and `nR4` is on disk |
| R8 | pass | `set "…^FB_Sequence^M_Fail" -Part impl`: `(unsaved; the file changes on: xae_edit.ps1 save)`; `show` then `saved False, edited by this tool`; `save "…^M_Fail"`: `saved …^FB_Sequence to …`, the line on disk, `show` `saved True` |
| R10 | pass | With only this tool's method edit pending, a plain `build` printed `saved TIPC^PLC1^PLC1 Project^POUs^FB_Sequence`, then `Build complete -- 0 errors, 0 warnings`, `Projects failed: 0`, exit 0, 4.9 s: the walk now finds the PLC project |
| R18 | pass | `new $duts -Type alias -Name T_XeAl -FromDecl` (`TYPE T_XeAl : UDINT;`): exit 0, type 623, the file holds `TYPE T_XeAl : UDINT;` / `END_TYPE` |
| R9f | pass | `FB_Sequence` saved, the tester typed `xyz` in `M_Fail`. `show` on the POU and on `^M_Fail`: `saved False, edited by someone else`. `set "…^M_Fail"`, `set "…^FB_Sequence"` and `save` each exit 1 with `refused: …^FB_Sequence holds unsaved edits this tool did not make, probably typed in XAE. …`. `build`: `refused: a build saves every unsaved object, and these hold edits this tool did not make:` / `TIPC^PLC1^PLC1 Project^POUs^FB_Sequence`, exit 1, 1.1 s. `xyz` stayed in the editor and is not on disk |

E9 (b) to (d) and E10 (b) were not repeated by hand. The unit tests cover the method case on fake
items.

## Facts recorded

- Type numbers: TIPC 14, PLC 56, PLC instance 57, PLC project 600, folder 601, program 602,
  function 603, function block 604, enum 605, struct 606, union 607, method 609, interface method
  610, property 611, interface property 612, property Get 613, property Set 614, GVL 615,
  References 617, interface 618, task (PLC) 621, alias 623, External Types 652, tmc 653, interface
  property Get 654.
- CFC POU: `Language` 5.
- The tab and `*`: the `M_Fail` tab already showed `*` before the typing in E9, from this tool's
  own method set. A script edit marks the member's tab, as F2's documents say.
- `build`'s refusal took 0.7-0.8 s, but it is F4's early exit, not the walk. Its cost on a real
  project is still unmeasured (E17).
- XAE's skeletons: the alias created with `vInfo 'LREAL'` has the declaration `LREAL` alone. The
  others could not be read before the tool's declaration replaced them, since that write saves
  (F1). On disk each file holds exactly the declaration given.
- vInfo forms that worked, as PowerShell expressions:
  - function (603): `[string[]] @('1', 'INT')`, form 1 of 2
  - program (602), function block (604): `1` (ST), `6` (LD), the only form
  - struct (606), enum (605), union (607), GVL (615), interface (618): `$null`, the only form
  - alias (623): `'LREAL'`, the base type, found in E18g; `$null` fails
  - interface method (610): `'BOOL'`, form 1 of 2
  - interface property (612): `'LREAL'`, form 1 of 2
  - property (611): `[string[]] @('1', 'LREAL')`, form 1 of 2 (the tool prints `String[] [1, LREAL]`)
  - accessors: the tool added `Get` (and `Set`) itself each time; XAE added none
  - method (609): one form, as measured before
- The lock: `<scratch>\TcUnitScratch.project.~u`, next to the `.sln`. It is gone the moment the
  solution closes.
- The XAE save format writes `ProductVersion="3.1.4024.12"` on this project, drops the final line
  break, and in `PlcTask.TcTTO` drops `<ObjectProperties />`.

## Beads

`bd` is not installed on this PC, so the failures are listed here: F1, F2, F3, F4 above, each
with its command and output in the table, and the E0 test assumption (fix 6).

## Clean-up

The tester removes:

- `<scratch>`, or keeps it: it is its own git
  repository, with the round's state committed step by step;
- in the skill clone: `b.st`, `b2.st`, `b3.st`, `b4.st`, `b9e.st`, `d.st`, `i.st`, `i2.st`,
  `ld.xml`, `x.st`, `x2.st`, `sd.st`, `mf*.st`, `cur_*.st`, `child_back.st`, `e15.st` and E18's
  input files (`prg_*.st`, `fun_*.st`, `st_d.st`, `e_d.st`, `u_d.st`, `t_d.st`, `gvl_d.st`,
  `child_d.st`, `true_i.st`, `get_i.st`, `speed_*.st`);
- `%TEMP%\twincat-st-xae_edit-*.txt`, the tool's state files.

No controller was touched, so nothing needs re-activating.

## After hand-back

The fixes landed on PR #49 with these changes on top, made without an XAE and covered by the unit
tests only:

- `build` matches an unsaved document to the objects its walk reported, by file name, instead of
  dropping every `.Tc*` document. An unsaved `PlcTask.TcTTO` is listed whether or not the walk
  reaches the task, which E10 (b) never got to show.
- The member documents are read once per walk, not once per POU: E17's 453 POUs would otherwise
  cost 453 enumerations of `Dte.Documents`.
- `new -Type alias -Returns <type>` with no `-FromDecl` writes `TYPE <Name> : <type>;` /
  `END_TYPE` itself, since XAE's skeleton is the bare type.
- The `created with vInfo form N of M` line appears only when a form other than the measured one
  was needed; the saved-state note names object creation as well as a declaration.

`field-test-xae-edit.md` lists what a second round runs.
