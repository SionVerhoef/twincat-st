# Field review -- round 5 (0.4.0 release round)

Round 5 ran `field-test-round5.md` on the TwinCAT PC: TwinCAT 3.1.4024.55, Windows 10 22H2 (19045),
Python 3.12.10, Windows PowerShell 5.1.19041 and cmd.exe. The skill was at commit `b0cc562` (head of
`worktree-release-0.4.0-cleanup`, PR #38), both as the clone and as the installed copy. The
installed copy was reinstalled from the clone: 121 files, byte-identical, no `.git` or `.github`.
Project_A, a packaging machine on TwinCAT 3.1.4024, ran in a temporary worktree, read only, holding
just its own code folders. The scratch TcUnit solution came from rounds 3 and 4 (target Local,
TcUnit 1.3.2). It was copied first, and restored afterwards. Project names are replaced by
stand-ins.

`PYTHONUTF8` and `PYTHONIOENCODING` were cleared in every shell that ran a check. An echo printed
`[][]`, and the only `PYTHON*` variable left was `PYTHONDONTWRITEBYTECODE`. PowerShell 5.1 was
started with code page 437 already set (`[Console]::OutputEncoding` = IBM437).

**W1 to W6 pass. W7 to W10 were skipped**: no test controller was available. Since W7 gates the
release, the gate is still open. No check failed, so no bead was filed.

| # | Result | Evidence |
|---|---|---|
| W1 | pass | Clone and installed copy alike: exit 0, 122 `ok`, last line `all checks passed`. The two logs are byte-identical |
| W2 | pass | cmd.exe. `get --out` and then `set --from-file` for `decl`, `impl`, `M_Fail:decl` and `M_Fail:impl`: every `get` and `set` exited 0. `code-equal <scratch>\FB_Sequence.TcPOU --against templates\FB_Sequence.TcPOU` printed `IDENTICAL code: ... (4 parts)`, exit 0. `git diff` in the scratch repo: 6 insertions(+), 1 deletion(-). That is the `bDone` declaration comment (`(until next Execute edge)` became `(latched until bExecute falls)`) plus the `IF NOT bExecute THEN bDone := FALSE; END_IF` block in `Idle`, with its two comment lines. No `Id` line changed |
| W3 | pass | PS 5.1. The *Using them* block, with `MyProject/PLC` replaced by the scratch PLC folder, run from the clone. `new`, `add-method`, the four `get`/`set` pairs, `register`, `check` and `st_review.py` each exited 0. `check` printed `ok   <scratch>/POUs/FB_Filling.TcPOU`. `st_review.py` printed `1 file(s) scanned -- no findings.` The `.plcproj` gained `<Compile Include="POUs\FB_Filling.TcPOU">`. `FB_Filling`'s POU and method GUIDs differ from the template's. See *W3* |
| W4 | pass | The `TestAndSet` example compiles as written. It needed only declarations: a GVL with `bRecipeLock : BOOL` and `stRecipe : ST_Recipe`, a two-member `ST_Recipe`, and the locals `stNewRecipe` and `bRecipePending`. The target refuses `__TRY`. For TwinCAT RT (x64) on 4024.55 the compiler reports `The codegenerator for the current device does not support structured exception handling.` on the `__TRY` line. W4 expects that kind of refusal, and the doc's *Where it is not supported the compiler says so* holds. See *W4* |
| W5 | pass (second build) | No XAE running. First build, with W2, W3 and both W4 POUs: exit 1, `Compile complete -- 1 errors, 0 warnings`. The one error is W4's `__TRY` refusal. Second build, with only the `__TRY` POU unregistered and its call removed: exit 0, `Build complete -- 0 errors, 0 warnings : ready for download!`, stderr empty, 44 s. This build covers W2, W3 and W4's `TestAndSet` example. Afterwards no `TcXaeShell.exe` was left running |
| W6 | pass | 158 files, Project_A's own code, framework libraries excluded, run as in round 4. At round 4's Project_A commit: 130 findings, `{'high': 1, 'medium': 101, 'low': 28}`, rule for rule the same as round 4's re-run (CP24 59, CP23 22, X6 31, X3 17, CP8 1). At Project_A's current `HEAD`: 129, `{'high': 1, 'medium': 100, 'low': 28}`. The difference is the one X6 that the project fixed, as reported in round 4's re-run. `--rules X12,CP7,CP12` returns 0 findings at both commits, so there was nothing to judge false and no false CP7. See *W6* |
| W7 | skipped | No test controller available. This check gates the release, so the gate is open |
| W8 | skipped | Its own condition does not hold. The scratch project has `FB_Sequence` instances only inside the TcUnit suite FB, and no program calls one. It would have needed a controller anyway |
| W9 | skipped | No test controller. The README line stays under *Not yet verified* |
| W10 | skipped | No test controller. The README line stays under *Not yet verified* |

## W3 -- what was not verbatim

- The edit step. `# edit decl.st: FUNCTION_BLOCK FB_Sequence -> FUNCTION_BLOCK FB_Filling` is a
  manual edit. A byte-for-byte replacement of that string stood in for the editor. The part is
  ASCII-only, so the edit exercised no encoding path.
- The `register` line names `E_SeqState.TcDUT` too. Since the enum step was skipped, as the
  checklist says, only `FB_Filling.TcPOU` was registered.
- The block passes the same `decl.st` file for each of the four parts. That was kept.

## W4 -- the `__TRY` example

The example was pasted exactly as written. Its two `VAR` lines stayed in their own `VAR` block. A
second block declared `fbScale : FB_Scale`, `fRatio : LREAL`, `bError : BOOL` and `nCalls : UDINT`.
`fbScale.GetRatio()` needs a type that provides it, so a minimal `FB_Scale` with a method
`GetRatio : LREAL` (body `GetRatio := 1.0;`) was added. That is the one object beyond plain
declarations, and the example cannot compile without one. Both W4 POUs were called from `MAIN`, so
code generation could not skip them. No statement of either example was changed.

The compiler's refusal names the device, not the version. On this PC, 4024.55 with the TwinCAT RT
(x64) target, `__TRY` is not available. The doc's *exists from 4024 on targets that support it* is
true, but a 4024 user on an x64 runtime cannot tell from it that `__TRY` is unavailable to them.
Which targets and builds do support it was not checked here. A sentence naming the x64 refusal,
with InfoSys's support matrix, would close the gap. This is not a failure of W4.

## W6 -- why zero is right

A zero is only a pass if there was nothing to find, so each rule's candidates in the 158 files were
checked independently of the reviewer:

- **X12.** The files declare 66 standard stateful instances (27 `TON`, 12 `TOF`, 3 `TP`, 21
  `R_TRIG`, 3 `F_TRIG`, no `MC_*`). ST calls 63 of them, and every one of those has at least one
  call outside any `IF`/`CASE`. The other 3 are never called, which is CP24's business. No X12
  candidate exists.
- **CP7.** No `MC_*`, `ADS*` or `FB_File*` instance is in the scanned code. Its axes run through
  framework FBs outside the scan. One FB in the tree declares an error output, `obError`. Its six
  instances are all called from LD networks only, and no ST line reads their `obError`. CP7 judges
  ST call sites only (uncalled instances are CP24's business), so it stays silent there. That is
  the rule's documented scope, not a false positive. A human reviewer would note that the six error
  outputs are not read. Whether that is a gap depends on the project's alarm handling, which
  reports through another path.
- **CP12.** 41 outputs are mapped `AT %Q`. Each is written from one unit only, counting ST
  assignments, `=>` bindings and LD/FBD operands. No candidate exists.

The rules were exercised on a project where they have nothing to say. The run shows they add no
false positives to a real 158-file project, and that CP7, the high rule, raises nothing false. The
run does not show them catching a real defect in the field. The unit tests in W1 cover that.

## What this round verifies

- `FB_Sequence`'s `bDone` latch ships as the scratch copy: W2 IDENTICAL, W5 compiles it. Its runtime
  behaviour (W8) was not observed.
- The template recipe in `templates/README.md` works in Windows PowerShell 5.1 (W3) and the result
  compiles (W5).
- `tasks-and-exceptions.md`'s examples: the `TestAndSet` lock compiles as written. The `__TRY`
  example is refused by the x64 target on 4024.55, as the doc allows.
- Reviewer rules X12, CP7 and CP12: no false positives on Project_A (W6).

**Not verified:** W7 (the TcUnit run, which gates the release), W8, W9 (the core-dump steps) and
W10 (the Rule 9 restart table). README *Not yet verified* keeps the core-dump and restart-table
lines, and the TcUnit run still needs a controller.

## Beads

None filed: no check failed.

## Still to do

W7, when a test controller is free. W9 and W10 can run on the same activation. Their scratch POUs
are written and built, but they are not in the restored scratch solution.

## Maintainer decision (2026-10-25)

0.4.0 ships with W7 not run. The maintainer waived the gate. The one change W7 would test at runtime
is `FB_Sequence`'s `bDone` latch, and both suite tests hold `bExecute` TRUE throughout, so the new
`IF NOT bExecute` branch is not reached inside them. W2 and W5 show the shipped code compiles.
W7 runs with W9 and W10 when a controller is free.
