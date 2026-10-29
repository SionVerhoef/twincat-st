# Field test -- `xae_edit.ps1`, editing through the open XAE

The hand-off for the first run of `scripts/xae_edit.ps1` on a PC with XAE. A field agent measured
every Automation Interface call it makes with probe scripts (TwinCAT 3.1.4024.55, 2026-10-29):
editing through the open XAE raised no prompt, left the file alone until saved, and showed the
edit live in the open editor. The tool was then written without an XAE, so this round runs the
tool itself. It also closes what the probes could not reach: a person typing in the same POU,
Ctrl+Z, an online change, and a dialog left open. `references/twincat/xae-automation.md` →
*Editing through the open XAE* has the measured facts.

Same rules as the earlier rounds: the repository is public, the production project is called
Project_A ("a packaging machine, TwinCAT 3.1.4024") and nothing else, no customer, site, machine
or module names, no NetIDs or IPs. Results go into `evals/field-review-xae-edit.md` in that form,
with each command's output quoted.

## Setup

- TwinCAT PC: TwinCAT 3.1.4024.55 (TcXaeShell), Windows PowerShell 5.1, Python 3.12. XAE and the
  shell both **not** elevated, except in E1d.
- The skill at the head of branch `worktree-xae-edit`. Record the commit.
- A **fresh copy** of the scratch TcUnit solution, committed to git before E1, called
  `<scratch>` below. Not the probe copy: that one still holds the probes' objects. Every object
  this round adds goes at the end (*Clean-up*).
- **Start XAE from the Start menu and open the solution by hand**, as a user would. The probes
  used an XAE started through COM, so this is also the first run against one a person started.
- In the shell that runs the checks, from the skill's folder:

  ```powershell
  chcp 437
  $sln = '<scratch>\TcUnitScratch.sln'
  $pous = 'TIPC^PLC1^PLC1 Project^POUs'
  function xe { powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\xae_edit.ps1 @args; "exit $LASTEXITCODE" }
  ```

  Adjust `$pous` if the scratch PLC is not called `PLC1`; `xe show -Solution $sln` lists `TIPC`.

"Pass" means the expected result. Anything else is a failure: file it as its own bead with the
output, and do not fix it on the PC. Watch XAE throughout: **any** prompt that appears during a
check fails it, unless the check says to expect one.

## Checks

### Without XAE's solution

| # | Run | Expect | Retires |
|---|---|---|---|
| E0 | `py -3 tests\run_tests.py` and `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\xae_edit_tests.ps1`, env clean as in round 5 | both end `all checks passed`, exit 0 | the unit tests on the PC, not only in CI |
| E1a | Close every XAE. `xe list` | `no XAE in the Running Object Table`, exit 0 | `list` with no XAE |

### With the scratch solution open in XAE

| # | Run | Expect | Retires |
|---|---|---|---|
| E1b | Open `<scratch>` in XAE by hand. `xe list` | one line `PID <n>  TcXaeShell.DTE.15.0  <scratch>\TcUnitScratch.sln`, exit 0 | `list` with one XAE, started by hand |
| E1c | Start a second XAE with no solution. `xe list`, then `xe show -Solution $sln` | two lines, the second `(no solution open)`; `show` prints `TIPC` and its children, exit 0. Close the second XAE | attach by solution, with two XAEs running |
| E1d | *Optional.* Close XAE, start it **as administrator**, open `<scratch>`. In the non-elevated shell: `xe list`, then `xe show -Solution $sln`. Then back to a non-elevated XAE | `list` says `XAE process <n> is not in this shell's Running Object Table: it runs as administrator…`; `show` exits 2 with the same line | the elevation case, untested so far |
| E2 | `xe show "$pous^FB_Sequence" -Solution $sln` | `type 604`, `language 1 (ST)`, `file <scratch>\…\FB_Sequence.TcPOU`, `saved True`, its methods as children with `type 609`. Quote the output | `show` |
| E3 | Editor for `FB_Sequence` **closed**. `xe get "$pous^FB_Sequence" -Solution $sln -Part impl -Out b.st`; append the line `// E3`; note `Get-FileHash` and `LastWriteTime` of `FB_Sequence.TcPOU`; `xe set "$pous^FB_Sequence" -Solution $sln -Part impl -FromFile b.st`; `xe show "$pous^FB_Sequence" -Solution $sln`; `xe get … -Out b2.st` | `set` exits 0 and prints `set the impl … in XAE (unsaved…`; no dialog; hash and mtime unchanged; `show` says `saved False, edited by this tool`; `(Get-Content b.st -Raw) -ceq (Get-Content b2.st -Raw)` is True. Opening the editor now shows `// E3` and the tab has `*` | get/set impl, editor closed |
| E4 | Open `FB_Sequence` in its editor. `get -Part decl -Out d.st`, add a line `    nE4 : INT;` before the first `END_VAR`, `set -Part decl -FromFile d.st` | exit 0, no dialog, the declaration in the open editor shows `nE4` at once, file unchanged on disk | get/set decl, editor open |
| E5 | `xe add-pou $pous -Solution $sln -Name FB_XeSt`, then `xe add-pou $pous -Solution $sln -Name FB_XeLd -Lang ld`. Then `git status` and `git diff -- *.plcproj` in `<scratch>` | both exit 0 and print the file XAE wrote; both appear in Solution Explorer; both `.TcPOU` files exist; the `.plcproj` diff adds exactly their two `Compile` entries | `add-pou`, ST and LD, with XAE registering them |
| E6 | `d.st` = `METHOD M_Check : BOOL` / `VAR_INPUT` / `    nIn : INT;` / `END_VAR`, `i.st` = `M_Check := nIn > 0;`. `xe add-method "$pous^FB_XeSt" -Solution $sln -Name M_Check -FromDecl d.st -FromImpl i.st`, then `xe show "$pous^FB_XeSt^M_Check" -Solution $sln` | exit 0; `M_Check` under `FB_XeSt` in Solution Explorer; `show` gives `type 609` and `saved False, edited by this tool (its file object …^FB_XeSt)` | `add-method` with texts |
| E7 | `xe set "$pous^FB_XeLd" -Solution $sln -Part impl -FromFile b.st`; `xe show "$pous^FB_XeLd" -Solution $sln`; `xe get "$pous^FB_XeLd" -Solution $sln -Out ld.xml`. If the scratch copy holds a CFC POU, `show` it too | `set` exits 1 with `refused: the body … is graphical`; `show` gives `language 6 (LD)`; `get` notes `a graphical body: XML` and `ld.xml` starts with `<NWL>` or similar. **Record the CFC POU's language number**: the tool refuses 2 to 6 and treats an XML body as graphical; CFC's number has not been seen | `set` refuses graphical bodies |
| E8 | `xe save "$pous^FB_Sequence^<one of its methods>" -Solution $sln`, then `git diff -- *FB_Sequence.TcPOU` | prints `saved …^FB_Sequence to …`, exit 0; `show` says `saved True`. The diff holds the `// E3` line and `nE4`, and otherwise only what an XAE save writes on this project (the scratch project writes `ProductVersion`; record any other line) | `save` on a method saves its POU |
| E9 | In the editor, type a space at the end of a line of `FB_Sequence`'s **body**; do not save. `xe show "$pous^FB_Sequence" -Solution $sln`, then `xe set … -Part impl -FromFile b.st`, then `xe save "$pous^FB_Sequence" -Solution $sln`, then `xe set … -Part impl -FromFile b.st -Force` | `show`: `saved False, edited by someone else`. `set` and `save` exit 1, `refused: … unsaved edits this tool did not make`, and change nothing (the typed space is still in the editor). `-Force` exits 0 with a `warning:` line; the body is now `b.st`, so the typed space is gone. Record whether the tab kept `*` after the typing, which is the signal the tool reads | the user's unsaved typing, untested so far |
| E10 | Type a space at the end of a body line of `FB_Sequence` again. `xe build -Solution $sln`. Then `xe build -Solution $sln -SaveUserEdits` | the first exits 1 with `refused: a build saves every unsaved PLC object…` and lists `…^FB_Sequence`; nothing is saved. The second: `the build saves:` lines, the Build pane with `Build complete -- 0 errors`, `Projects failed: 0`, exit 0, **no `.xti` reload prompt**, and `show` gives `saved True` for every POU touched above. Record the seconds `build` took before it refused (`Measure-Command`) | the build guard; a build in the user's XAE |
| E11 | `py -3 scripts\tcpou.py set <scratch>\…\FB_Sequence.TcPOU --part impl --from-file b.st`. Record where XAE's `*.project.~u` lock file is | exit 1 `refused: XAE has this project open (…)`, no prompt in XAE, file unchanged | `tcpou.py` finds the lock and refuses |
| E12 | Raise a prompt: the same `tcpou.py set` with `--allow-open`. Leave the reload prompt open. Then `xe list`, and time each of `xe show`, `xe get … -Out x.st`, `xe set … -FromFile b.st`, `xe save …`, `xe build -Solution $sln` with `Measure-Command` | `list` prints `dialog: [#32770] '…' \| …File has been changed outside the environment…`. Every other command exits 2 within about 2 s, naming the dialog, and changes nothing. Afterwards the tester answers **Yes** | dialog pre-flight; no hang |
| E13 | Drag the Error List out of XAE so it floats. `xe list`, `xe show -Solution $sln`. Dock it again | no `dialog:` in `list`; `show` exits 0. A floating tool window must not read as a dialog | dialog detection has no false positive |
| E14 | With `FB_Sequence` open in the editor: `xe set "$pous^FB_Sequence" -Solution $sln -Part impl -FromFile b3.st` (b.st plus `// E14`), then the tester clicks into the editor and presses **Ctrl+Z** once. `xe get … -Out b4.st` | record whether Ctrl+Z removed `// E14`, what `b4.st` holds, and whether the tab still shows `*` | undo of a script edit, untested so far |
| E15 | Close the solution in XAE. Does `*.project.~u` disappear? Run the E11 command again at once, and once more after 2 minutes if it refused | record both. If the lock stays behind, `tcpou.py` refuses for up to 2 minutes after closing | how long the `tcpou.py` guard lingers |

### Human steps on the test controller

| # | Run | Expect | Retires |
|---|---|---|---|
| E16 | With the scratch solution activated on the test controller (never one holding a machine project) and the tester logged in once, log out. Then: `set` a harmless change in an ST body (a new comment and `nE16 := nE16 + 1;` with `nE16` added by `set -Part decl`), `save`, `build`. The **tester** logs in | XAE offers **Login with online change**, not only a download; the online change applies and `nE16` counts. Record the exact dialog text | online change after a script edit, untested so far |

### Optional, on Project_A

| # | Run | Expect | Retires |
|---|---|---|---|
| E17 | Project_A in a temporary worktree, opened in XAE. Type a space into any POU. `Measure-Command { xe build -Solution <Project_A>.sln }`. Close the solution **without saving** and discard the worktree | refused, listing that POU only; record the seconds. The guard walks every folder of the PLC project, 453 POUs there | the build guard's cost on a real project |

E0 to E15 take about an hour; E16 needs the controller; E17 is optional.

## Clean-up

The agent shell may not delete folders, so the tester removes:

- the `<scratch>` copy, or, if it is to be kept, `git restore` and `git clean -n` there, then delete
  what `git clean -n` lists: `FB_XeSt.TcPOU`, `FB_XeLd.TcPOU`, and the build output;
- `b.st`, `b2.st`, `b3.st`, `b4.st`, `d.st`, `i.st`, `ld.xml`, `x.st` in the skill's folder;
- `%TEMP%\twincat-st-xae_edit-*.txt`, the tool's state files;
- the Project_A worktree from E17, if made.

Re-activate the machine project on the test controller if E16 replaced it
(`references/twincat/xae-automation.md` → *Activation is not scripted here*).
