# Field test -- `xae_edit.ps1`, round 3 (release gate)

The hand-off for the last run of `scripts/xae_edit.ps1` on the XAE PC before it is released.
Round 1 (`field-review-xae-edit.md`) found four defects. Round 2 (same file, `## Round 2`)
re-ran the guards by hand and found none. `scripts/` has not changed since round 1's fixes, so
this round runs the code that ships. It covers what no XAE has run on that code:

- **E18**, every object kind other than a function block, with properties and accessors. Round 1
  ran it before the fixes for F1 and F2, and the fixes were re-run for a method only (R8). Saving
  an accessor, and the guard on typing in one, have never been run by hand.
- **`build`'s document matching** (E20). An unsaved open document whose file the tree walk did
  not report is listed. In round 2 the task was caught by the walk, so this path has no real
  case yet.
- **E17 on Project_A** ("a packaging machine, TwinCAT 3.1.4024", 453 POUs): the guard's cost and
  false refusals on a real project, and a build there. Required this round.
- **E21**: a fresh agent, given an ordinary task, picks `xae_edit.ps1` from the skill's docs.

**E16, online change after a script edit, is skipped by the maintainer's decision**: no
controller without a machine project is available. The release notes say it is untested. Record
it as `skipped` in the table.

Same rules as the earlier rounds: the repository is public, the production project is called
Project_A and nothing else, no customer, site, machine or module names, no NetIDs or IPs. Results
go into a `## Round 3` section at the end of `evals/field-review-xae-edit.md`, each command's
output quoted.

## Setup

- TwinCAT PC as in rounds 1 and 2: TwinCAT 3.1.4024 (TcXaeShell), Windows PowerShell 5.1,
  Python 3.12. XAE and the shell both **not** elevated.
- The skill at `main`, at the merge of this runbook's PR or later, in a fresh clone. Record the
  commit.
- A **fresh copy** of the scratch TcUnit solution (`6d91cbb`, as in round 2), committed to git
  before the first check: `<scratch>` below.
- Delete `%TEMP%\twincat-st-xae_edit-*.txt`. Close every XAE, start one from the Start menu and
  open `<scratch>` by hand.
- In the shell that runs the checks, from the skill's folder, with `PYTHONUTF8` and
  `PYTHONIOENCODING` unset:

  ```powershell
  chcp 437
  $sln  = '<scratch>\TcUnitScratch.sln'
  $pous = 'TIPC^PLC1^PLC1 Project^POUs'
  $duts = 'TIPC^PLC1^PLC1 Project^DUTs'
  $gvls = 'TIPC^PLC1^PLC1 Project^GVLs'   # or $pous where the copy has no GVLs folder
  function xe { powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\xae_edit.ps1 @args; "exit $LASTEXITCODE" }
  function secs([scriptblock] $b) { $t = Get-Date; & $b; '{0:N1} s' -f ((Get-Date) - $t).TotalSeconds }
  ```

- Write the files of E18 in `field-test-xae-edit.md` (the table under *E18: every other edit*),
  UTF-8, one line per `/`.
- For E17: Project_A in a temporary worktree of its repository, at a commit that builds in XAE by
  hand. For E21: an agent that can load the skill from the fresh clone, in a **new** session that
  has not seen this runbook.

"Pass" means the expected result. Anything else is a failure: record it with the output, and fix
nothing on the PC. Watch XAE throughout: **any** prompt during a check fails it, unless the check
says to expect one. Never close an editor with *Don't save*, and remember that an undo does not
clear XAE's unsaved mark (round 2, D1): to remove a typed test edit, delete it and *Save All*.

## Checks

### Agent, scratch solution open

| # | Run | Expect | Retires |
|---|---|---|---|
| E0 | `py -3 tests\run_tests.py` and `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\xae_edit_tests.ps1` | both end `all checks passed`, exit 0; `xae_edit_tests.ps1` with an XAE running: 89 `ok` and one `skip`. Record the `run_tests.py` count | the unit tests at the release commit |
| E1b | `xe list` | one line `PID <n>  TcXaeShell.DTE.15.0  <scratch>\TcUnitScratch.sln`, exit 0 | the setup |
| E5 | `xe new $pous -Solution $sln -Type fb -Name FB_XeSt` | exit 0, `(saved: XAE writes the file itself …)`, no `created with vInfo form` line | the parent E18d and E18e need |
| E18a–e | E18a to E18e of `field-test-xae-edit.md`, as written there. Skip the alias `T_XeNd` in E18b: round 2 ran it | as written there, and since round 1's fixes: every `new` prints `(saved: …)`; **no** `created with vInfo form` line anywhere (quote any); in E18d `show "$pous^FB_XeChild^Level^Get"` says `saved False, edited by this tool (its file object …^FB_XeChild)`; after E18e `xe show "$pous^FB_XeSt"` says `saved False, edited by this tool` | every object kind, on the fixed code |
| E8b | `xe save "$pous^FB_XeSt^Speed^Get" -Solution $sln`; `xe show "$pous^FB_XeSt" -Solution $sln`; `Select-String 'Speed := 2.0' <path of FB_XeSt.TcPOU>` | `saved …^FB_XeSt to …`, exit 0; `show` says `saved True`; `Select-String` finds the line. Round 1 printed `nothing to save` here (F2) | `save` on an accessor saves its POU |
| E19 | `xe save "$pous^FB_XeChild" -Solution $sln`, and `show` must then say `saved True`. The tester opens `FB_XeChild`'s `Level` → `Get` editor and types `//xyz` at the end of its line; no save. `xe show "$pous^FB_XeChild" -Solution $sln`; `xe set "$pous^FB_XeChild^Level^Get" -Solution $sln -Part impl -FromFile get_i.st`; `xe save "$pous^FB_XeChild" -Solution $sln`; `Select-String xyz <path of FB_XeChild.TcPOU>`. Afterwards the tester deletes `//xyz` and runs *Save All* | `show` says `saved False, edited by someone else`; `set` and `save` each exit 1 with `refused: …^FB_XeChild holds unsaved edits this tool did not make…`; `//xyz` stays in the editor; `Select-String` finds nothing | round 1's F3 for an accessor |
| E18f | `xe save` each object of E18a to E18e (one path per file), then `xe build -Solution $sln` with **no** `-SaveUserEdits`; then `py -3 scripts\tcpou.py check` on every new file, and `git status` and `git diff -- *.plcproj` in `<scratch>` | each `save` prints `saved …` or `nothing to save: … is up to date`, exit 0, and `show` on that object then says `saved True`; `build` goes ahead, since every pending edit is the tool's own: `Build complete -- 0 errors`, `Projects failed: 0`, exit 0, no prompt; `check` prints `ok` for each; the `.plcproj` diff adds exactly the new files | the objects compile and are valid files |

**Stop rule:** if any command in E19 exits 0, or `xyz` reaches the disk, the tool can still
overwrite or save what a person typed. Stop the round there and report.

### Build guard outside the tree walk

These measure what XAE reports, so the expectation is partly open: record exactly what `build`
lists. Each change is undone afterwards by the tester, by setting the value back and *Save All*.

| # | Run | Expect | Retires |
|---|---|---|---|
| E20a | The tester opens the properties of `PLC1 Project` and, on the *Compile* page, adds `XE_R3` to *Compiler defines*; no save. `xe show "TIPC^PLC1^PLC1 Project" -Solution $sln` (record its `saved` line), then `secs { xe build -Solution $sln }` | exit 1, `refused:`, listing the change: as a document (`…\PLC1.plcproj` or similar) or as a tree path. Record which, and the seconds. If `build` goes ahead, record `git diff` in `<scratch>`: the build saved a person's setting | the document matching on a PLC file the walk does not report |
| E20b | The tester opens *SYSTEM* → *Real-Time*, *Settings* tab, and changes the CPU limit of the core in use by 1 %; no save. `secs { xe build -Solution $sln }` | exit 1, `refused:`, listing a document (`…\TcUnitScratch.tsproj` or an `.xti`). If `build` goes ahead or lists nothing, record `git diff` in `<scratch>`: the docs then say a System Manager change is not seen even with its editor open | the System Manager case the docs name |

### On Project_A

| # | Run | Expect | Retires |
|---|---|---|---|
| E17a | Project_A in its temporary worktree, opened in XAE by hand. `xe list`; `xe show` one ST POU with methods, `X` below. The agent appends `// R3` to the body of a second ST POU, `Y` (`get -Part impl`, edit, `set -Part impl`). The tester types a space into the body of `X`; no save. `secs { xe build -Solution <Project_A>.sln }` | `list` and `show` exit 0; `set` exits 0 with `(unsaved; …)`. `build` exits 1, refused, listing `…^X` and nothing else: `Y` is the tool's own edit, and any other line is a false refusal. Record the seconds | the guard's cost and false refusals on 453 POUs |
| E17b | `secs { xe build -Solution <Project_A>.sln -SaveUserEdits }` | `saved …^X` and `saved …^Y`, the Build pane, `Projects failed: 0` (or the same errors a build by hand gives at that commit: record them), exit 0, no prompt. Record the seconds. Then close the solution **without saving** and discard the worktree | a full build through the tool on a real project |

In the review, write POU paths as `…^POUs^X` and `…^POUs^Y`, and replace names the same way in any
other line printed.

### A fresh agent

| # | Run | Expect | Retires |
|---|---|---|---|
| E21 | Reopen `<scratch>` in XAE. In a **new** agent session with the skill loaded from the fresh clone, send only: *"I have `<scratch>\TcUnitScratch.sln` open in TwinCAT. Add a method `M_Reset : BOOL` to `FB_XeSt` that returns TRUE, then build it."* Do not mention the tools. Copy every command it runs | it runs `xae_edit.ps1` for the edit and the build, never `tcpou.py set`/`add-method` and never `xae_build.ps1`; `--allow-open` and `-Force` never appear; XAE shows no prompt; the build ends with 0 errors and the method is in the editor. If it first reaches for `tcpou.py` and is refused, record whether it switched to `xae_edit.ps1` by itself | the skill's docs route an agent to the right tool |

E0 to E19 take about 45 minutes; E20 15; E17 depends on Project_A's build time; E21 15.

## Release decision

The release goes ahead when the stop rule did not trigger, and E0 to E19, E17 and E21 pass. A
failure in E18 to E19 or E17 holds it. E20 decides what the docs say about changes outside the
POUs, and holds the release only if a build saved or lost an edit **without** listing it. A
false refusal in E17a holds it: on a real project that would make `build` unusable.

## Clean-up

The agent shell may not delete folders, so the tester removes:

- `<scratch>`, or `git restore` and `git clean -n` there, then delete what it lists;
- the E18 files, `sd.st` and anything E17 or E21 wrote in the skill's folder;
- `%TEMP%\twincat-st-xae_edit-*.txt`;
- the Project_A worktree from E17.

## Hand-back

- A `## Round 3` section at the end of `evals/field-review-xae-edit.md`: a table in round 2's form
  (`#`, `Result`, `Evidence`), E16 as `skipped (no controller without a machine project)`, each
  failure with its command and output, the facts recorded, and one line on the release decision.
- That change as a patch from `git diff` against the round's commit, nothing committed or pushed,
  and a short note saying what passed, what failed and what did not run.
