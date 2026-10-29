# Field test -- `xae_edit.ps1`, round 2

The hand-off for the second run of `scripts/xae_edit.ps1` on the XAE PC. Round 1
(`field-review-xae-edit.md`, 2026-10-29) found four defects. The worst: with a POU saved, `set`
overwrote what the person had typed in one of its methods, because XAE marks a method's edit on a
document of its own (`<file>;<POU>.<member>`), not on the POU. The fixes were re-run on that XAE
for the cases that failed, and PR #49 merged them into `main` together with three changes no XAE
has run yet:

- `build` matches an unsaved document to the objects its walk reported, by file name, so an
  unsaved file the walk does not reach, such as the task's `.TcTTO`, is listed instead of dropped.
  On a real XAE that could also list something it should not: a false refusal.
- The member documents are read once per walk, not once per POU.
- `new -Type alias -Returns <type>` with no `-FromDecl` writes the `TYPE` block itself.

This round repeats by hand the guard checks round 1 covered only in unit tests after the fix
(E9, E10), runs the three changes above, and reaches what round 1 could not: an online change
after a script edit (E16) and the build guard on Project_A (E17). Everything else passed in
round 1 and is not repeated. Check numbers follow round 1's, so the two tables line up.

Same rules as the earlier rounds: the repository is public, the production project is called
Project_A ("a packaging machine, TwinCAT 3.1.4024") and nothing else, no customer, site, machine
or module names, no NetIDs or IPs. Results go into a `## Round 2` section at the end of
`evals/field-review-xae-edit.md`, with each command's output quoted.

## Setup

- TwinCAT PC as in round 1: TwinCAT 3.1.4024.55 (TcXaeShell), Windows PowerShell 5.1, Python 3.12.
  XAE and the shell both **not** elevated.
- The skill at `main`, at `dd0da0f` (the merge of PR #49) or later, in a fresh clone. Record the
  commit. The round-1 clone still holds the fixes as an uncommitted patch; `main` has them now, so
  leave that clone alone.
- A **fresh copy** of the scratch TcUnit solution, as in round 1 (`8f3eaab` plus the CFC probe
  POU), committed to git before the first check: `<scratch>` below. Not round 1's copy, which
  holds that round's objects and the `xyz` typed into `M_Fail`.
- Delete `%TEMP%\twincat-st-xae_edit-*.txt`, round 1's state files.
- Close every XAE, start one from the Start menu and open `<scratch>` by hand.
- In the shell that runs the checks, from the skill's folder, with `PYTHONUTF8` and
  `PYTHONIOENCODING` unset:

  ```powershell
  chcp 437
  $sln  = '<scratch>\TcUnitScratch.sln'
  $pous = 'TIPC^PLC1^PLC1 Project^POUs'
  $duts = 'TIPC^PLC1^PLC1 Project^DUTs'
  function xe { powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\xae_edit.ps1 @args; "exit $LASTEXITCODE" }
  function secs([scriptblock] $b) { $t = Get-Date; & $b; '{0:N1} s' -f ((Get-Date) - $t).TotalSeconds }
  ```

- For E16: the test controller, never one that holds a machine project, with the scratch solution
  activated on it. Back up `C:\TwinCAT\3.1\Boot\Plc\` on it first
  (`references/twincat/xae-automation.md` → *Activation is not scripted here*). Activating and
  logging in are the tester's steps.
- For E17, optional: Project_A in a temporary worktree of its repository.

"Pass" means the expected result. Anything else is a failure: record it with the output, and fix
nothing on the PC. If the maintainer asks for a fix there, hand it back as a patch against the
round's commit, as round 1 did. Watch XAE throughout: **any** prompt that appears during a check
fails it, unless the check says to expect one.

## Checks

### Agent, scratch solution open

| # | Run | Expect | Retires |
|---|---|---|---|
| E0 | `py -3 tests\run_tests.py` and `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\xae_edit_tests.ps1` | both end `all checks passed`, exit 0. CI's Windows runner prints 144 `ok` lines for `run_tests.py` (record the PC's count) and 90 for `xae_edit_tests.ps1`; with an XAE running, 89 and one `skip` line | the unit tests at the merged commit, on the PC |
| E1b | `xe list` | one line `PID <n>  TcXaeShell.DTE.15.0  <scratch>\TcUnitScratch.sln`, exit 0 | the setup |
| E9a | `xe get "$pous^FB_Sequence" -Solution $sln -Part impl -Out b.st`; add a last line `// R2` to `b.st`; `xe set "$pous^FB_Sequence" -Solution $sln -Part impl -FromFile b.st`; `xe show "$pous^FB_Sequence" -Solution $sln` | `set` exits 0 with `(unsaved; the file changes on: xae_edit.ps1 save)`; `show` says `saved False, edited by this tool` | the tool's own edit is recorded |
| E9b | The tester opens `M_Fail`'s editor and types a space at the end of a line; no save. `xe show "$pous^FB_Sequence" -Solution $sln`, then `xe set "$pous^FB_Sequence" -Solution $sln -Part impl -FromFile b.st` | `show` says `edited by someone else`; `set` exits 1 with `refused: …^FB_Sequence holds unsaved edits this tool did not make…`; the space is still in the editor | typing in a method while the POU is unsaved |
| E9c | The tester undoes the space. The `set` of E9a again. Then the tester types a space at the end of a line of `FB_Sequence`'s own body; `show` and `set` as in E9b | the first `set` exits 0; after the typing, `show` says `edited by someone else` and `set` exits 1 the same way; the space stays | typing in the POU's body |
| E9d | `xe save "$pous^FB_Sequence" -Solution $sln`; `xe set "$pous^FB_Sequence" -Solution $sln -Part impl -FromFile b.st -Force`; `xe save "$pous^FB_Sequence" -Solution $sln` | the first `save` exits 1, refused; `-Force` exits 0 with a `warning:` line, and the body reads back as `b.st`; the second `save` is refused again, because `-Force` counts for one command | `-Force` |
| E9e | `xe get "$pous^FB_Sequence^M_Fail" -Solution $sln -Part impl -Out mf.st`. The tester saves everything in XAE (*File → Save All*); `xe show "$pous^FB_Sequence" -Solution $sln` must now say `saved True`. Then the tester types `//xyz` at the end of a line of `M_Fail`; no save. `xe show "$pous^FB_Sequence^M_Fail" -Solution $sln`, then `xe set "$pous^FB_Sequence^M_Fail" -Solution $sln -Part impl -FromFile mf.st` | `show` says `saved False, edited by someone else (its file object …^FB_Sequence)`; `set` exits 1, refused; `//xyz` is still in the editor. If `show` did not say `saved True` before the typing, record what it said and which tabs kept `*` | **round 1's F3**: typing in a method of a saved POU |
| E9f | With `//xyz` still there: `xe set "$pous^FB_Sequence" -Solution $sln -Part impl -FromFile b.st`, `xe save "$pous^FB_Sequence" -Solution $sln`, `xe build -Solution $sln`; then `Select-String xyz <path of FB_Sequence.TcPOU>`. Afterwards the tester removes `//xyz` and saves all | each of the three exits 1 with `refused:`, `build` listing `…^FB_Sequence` and nothing else; `Select-String` finds nothing | round 1's E9e: the POU's own `set` no longer takes the typing for the tool's |
| E6 | Write `d.st` = `METHOD M_Check : BOOL` / `VAR_INPUT` / `    nIn : INT;` / `END_VAR` and `i.st` = `M_Check := nIn > 0;`. `xe new $pous -Solution $sln -Type fb -Name FB_XeR2`; `xe add-method "$pous^FB_XeR2" -Solution $sln -Name M_Check -FromDecl d.st -FromImpl i.st`; `xe show "$pous^FB_XeR2^M_Check" -Solution $sln`; `xe save "$pous^FB_XeR2^M_Check" -Solution $sln`; `Select-String 'nIn > 0' <path of FB_XeR2.TcPOU>` | `new` exits 0 with `(saved: XAE writes the file itself …)` and no `created with vInfo form` line; `add-method` exits 0 with `(unsaved; …)`; `show` says `saved False, edited by this tool (its file object …^FB_XeR2)`; `save` prints `saved …^FB_XeR2 to …`; `Select-String` finds the line. In round 1, `show` said `saved True` and `save` had nothing to save | a new method's body reads unsaved and is saved through its document |
| E18h | `xe new $duts -Solution $sln -Type alias -Name T_XeNd -Returns UDINT`; `xe get "$duts^T_XeNd" -Solution $sln -Part decl -Out t_nd.st` | exit 0, no `created with vInfo form` line; `t_nd.st` holds `TYPE T_XeNd : UDINT;` / `END_TYPE`, and so does the file on disk | an alias from `-Returns` alone |
| E10a | The tester types a space at the end of a line of `FB_Sequence`'s body; no save. `secs { xe build -Solution $sln }`. Then `xe build -Solution $sln -SaveUserEdits` | the first exits 1 with `refused: a build saves every unsaved object…`, listing `…^FB_Sequence` and nothing else: any other line is a false refusal, so quote it. Record the seconds. The second prints `saved …^FB_Sequence`, the Build pane with `Build complete -- 0 errors`, `Projects failed: 0`, exit 0, no prompt; it compiles E6's and E18h's objects too | the build guard reaching the PLC project, with no false refusal |
| E10b | `xe show "TIPC^PLC1^PLC1 Project" -Solution $sln` to find the task (type 621), then `xe show` the task. The tester opens the task's settings in XAE and changes its cycle time; no save. `xe show` the task again, then `xe build -Solution $sln`. Afterwards the tester sets the cycle time back and saves it | `build` exits 1, refused, listing the task: as the document `…\PlcTask.TcTTO` or as the tree path `…^PlcTask`. Record which, and the task's `saved` line before and after the change: if it stays `True`, only the document matching catches the change. If `build` goes ahead instead, record what `git diff` in `<scratch>` shows it saved | the guard outside the POUs; round 1 never got past F4 here |

**Stop rule:** if any command in E9e or E9f exits 0, or `xyz` reaches the disk, the tool can still
overwrite or save what a person typed. Stop the round there and report.

### Human steps on the test controller

| # | Run | Expect | Retires |
|---|---|---|---|
| E16 | With the scratch solution active on the test controller and the tester logged in once, the tester logs out. Then, on `MAIN` or whichever program the PLC task calls: `get -Part decl`, add `nE16 : INT;` to its `VAR` block, `set -Part decl`; `get -Part impl`, add a comment line and `nE16 := nE16 + 1;`, `set -Part impl`; `xe save` it; `xe build -Solution $sln`. The **tester** logs in | the declaration `set` prints `(saved: …)`, the body `set` `(unsaved; …)`; `build` exits 0. XAE offers **Login with online change**, not only a download; the online change applies and `nE16` counts up. Quote the dialog's text | online change after a script edit |

### Optional, on Project_A

| # | Run | Expect | Retires |
|---|---|---|---|
| E17 | Project_A in a temporary worktree, opened in XAE by hand. The tester types a space into the body of any one POU; no save. `secs { xe build -Solution <Project_A>.sln }`. Close the solution **without saving**, then discard the worktree | exit 1, refused, listing that one POU and nothing else. Record the seconds. In the review, write the POU's path as `…^POUs^<POU>`, and replace names the same way in any other line it printed | the guard's cost, and false refusals, on a project of 453 POUs |

E0 to E10 take about 45 minutes; E16 needs the controller; E17 is optional.

## Clean-up

The agent shell may not delete folders, so the tester removes:

- `<scratch>`, or `git restore` and `git clean -n` there, then delete what it lists: `FB_XeR2`,
  `T_XeNd` and the build output;
- `b.st`, `mf.st`, `d.st`, `i.st`, `t_nd.st` and E16's files in the skill's folder;
- `%TEMP%\twincat-st-xae_edit-*.txt`, the tool's state files;
- the Project_A worktree from E17, if made.

Re-activate the machine project on the test controller if E16 replaced it.

## Hand-back

- A `## Round 2` section at the end of `evals/field-review-xae-edit.md`: a table in round 1's form
  (`#`, `Result`, `Evidence`), each failure with its command and output, and the facts recorded.
- As in round 1: that change as a patch from `git diff` against the round's commit, nothing
  committed or pushed, and a short note saying what passed, what failed and what did not run.
  `bd` is not on the PC, so failures are listed in the review.
