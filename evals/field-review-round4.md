# Field review -- round 4 (release round)

Round 4 ran `field-test-round4.md` on the TwinCAT PC: TwinCAT 3.1.4024.55, Windows 10 22H2, Python
3.12.10, Windows PowerShell 5.1.19041 and cmd.exe. The skill was at commit `f69dd5b` (PR #35), both
as the clone and as the installed copy (the clone without `.git` and `.github`, byte-identical
otherwise). Project_A, a packaging machine on TwinCAT 3.1.4024, ran in a temporary worktree at its
current `HEAD`. The worktree was restored after every check and removed at the end. The scratch
TcUnit solution came from round 3. Project names are replaced by stand-ins.

`PYTHONUTF8` and `PYTHONIOENCODING` were cleared in every shell that ran a check. cmd's `set PYTHON`
listed only `PYTHONDONTWRITEBYTECODE`, and PowerShell echoed `[][]`. The console code page was set
to 437 **before** PowerShell 5.1 started (`[Console]::OutputEncoding` = IBM437). A first R2 to R4
pass ran `chcp 437` inside the script instead. That PowerShell had already taken code page 65001
from the agent's host app, so `>` kept `²` intact and R3 had nothing to warn about. That pass is
discarded. A tester who runs these checks from an agent shell should set the code page first.

**13 of 15 pass. R1 and R14 fail**, one bead each (see *Beads*).

| # | Result | Evidence |
|---|---|---|
| R1 | **fail** | Clone and installed copy alike: 114 `ok`, `2 failed`, exit 1, no `skip` line. Failing: `get --out writes UTF-8 with no BOM, byte-identical to what get prints` and `two trailing line breaks are kept: an empty last line stays possible` (`b'a := 1;\r\nb := 2;\r\n\r\n'`). Bead 1 |
| R2 | pass | PS 5.1, a POU with `²` in a decl comment: `get --part decl --out d.st` writes UTF-8, no BOM, `²` intact. `set --part decl --from-file d.st`: exit 0, `git diff` empty |
| R3 | pass | `get --part decl > d16.st` writes UTF-16LE (`FF FE`). `set --from-file d16.st`: exit 0, no traceback, and exactly one stderr line: `warning: the new text contains ┬▓ and the current part does not: UTF-8 read through cp1252 or an OEM code page on the way here? ('get --out' and 'set --from-file' avoid that)`. `git diff --numstat` gives `1 1`: the unit comment's `[mm/s²]` became `[mm/s┬▓]`. Restored afterwards |
| R4 | pass | An ASCII-only POU's `impl` from `get --out` (12,812 bytes, ending `);` with no line break). `Get-Content d.st \| py -3 tcpou.py set X --part impl`: exit 0, `git diff` empty |
| R5 | pass (stand-in) | `d.st` from R2 ends in `END_VAR` with no line break. Saved with one LF appended, which is exactly what an editor's final-newline save adds to an LF file, then `set --from-file`: exit 0, `git diff` empty. No editor GUI was driven |
| R6 | pass | cmd.exe, `d.st` re-encoded as cp1252 (one `0xB2` byte). `set --from-file bad.st`: exit 1, one stderr line, `refused: <scratch>\bad.st: not UTF-8 or UTF-16 with a BOM`. The target's SHA-256 was unchanged |
| R7 | pass | `code-equal --ref HEAD`, `core.autocrlf=true`, untouched worktree: **1,353 IDENTICAL, 0 DIFFERENT, 0 CANNOT COMPARE**, exit 0 for every batch. 1,353 is round 3's 1,352 (`.TcPOU`/`.TcDUT`/`.TcGVL`) plus one DUT committed since. The set includes the file that came back falsely DIFFERENT in round 3. It took 102 s in 14 batches, because 1,353 paths do not fit on one command line |
| R8 | pass | Fresh PLCopen export of the six LD callers at `HEAD`: 56 boxes, 1,076 pins, **0 mismatches**, 0 order differences. 48 `(rung: left rail, TRUE)`, 6 `NOT x`, 1 `(coil) ... [<method>]` and 18 `(return) <- NOT x   [<method>]`, each in the method the export puts it in. `--pin <coil variable>` prints the coil line, exit 0. `--box <instance>` prints that box and no rung line. On round 3's own exports and the POUs at round 3's commit, the same comparison gives 1,066 pins and 0 mismatches: 10 pins were wired in since |
| R9 | pass | `CFC body: pins reads FBD/LD networks only`, exit 2, on round 3's XAE-made CFC POU (it now holds two drawn boxes) and on `FB_CfcEmpty` |
| R10 | pass | The user drew one FBD POU in XAE 4024.55: a `CTU` box with CU unwired, RESET fed by an AND of two variables, PV from a variable and one output assigned. `pins` matches the export on all five pins. Input 0 is a `BoxTreeOperand` with `Operand ""`, not a `BoxTreeTerminator`, so `(unwired)` is right there. See *R10* |
| R11 | pass | No XAE running: exit 0, `Build complete -- 0 errors, 0 warnings : ready for download!`, no `WARNING:` line, stderr empty, 32 s |
| R12 | pass | The user's XAE held the scratch solution. The first stdout line was `WARNING: the solution is open in XAE (PID n): it will ask to reload the .xti; answer Yes`. The build exited 0 with `Build complete -- 0 errors, 0 warnings`, 29 s. That XAE showed `<scratch>\_Config\PLC\PLC1.xti` / `This file was modified outside of TwinCAT XAE.` / `Do you want to reload it?`. **Yes** reloaded it, and a window watcher on that process logged no further dialog over the next four minutes |
| R13 | pass | Exit 1 after 1 s, stdout empty. stderr is exactly `envdte.dll not found in 'C:\nowhere'. Pass -PublicAssemblies for this XAE install.`, with no error record. No XAE process before or after |
| R14 | **fail** | 158 files, Project_A's own code with the framework libraries excluded, as in round 2: **132 findings** (3 high, 101 medium, 28 low). Two of the three high findings are false positives (E3). Bead 2 |
| R15 | pass | PS 5.1, `get <POU> \| Select-Object -First 3`, on a POU body (33,360 chars) and on the largest ST part in Project_A (a method, 114,436 chars): three lines each, then nothing. No `Broken pipe`, no traceback; `$LASTEXITCODE` -1 is PowerShell stopping the pipeline. cmd.exe, **stand-in** for `\| more` then `q`: a reader that takes one line and closes the pipe (`\| (set /p FIRST= & ...)`) printed the first line, exit 0, nothing from `tcpou.py` |

R5 and R15's cmd half use stand-ins for the human gesture. They feed `set` the same bytes, and close
the pipe at the same point. The editor and `more` were not driven.

## R1 -- the two failing tests

On Windows `sys.stdout` is a text stream, so `get` prints each `\n` as `\r\n`. `get --out` writes LF
bytes. The first test compares the `--out` bytes with the printed bytes, and the second compares the
printed bytes with an LF literal. Both fail on Windows only. The behaviour each test is about still
holds. `--out` is UTF-8 with no BOM and keeps `²`, and both trailing line breaks are kept: they
print as `\r\n\r\n`. CI runs on `ubuntu-latest` only, where stdout writes LF. Round 3's 90 `ok` came
before these tests were added.

## R8 -- method

Round 3's comparison script, extended for the fixes. It adds the rail input, `NOT`, the owning
method, and coil and RETURN rungs, compared entry by entry in order and pin by pin by name. One
detail of the export: a single negated operand at a box pin is exported twice, once on the contact
and again as `negated="true"` on the pin. The native storage holds one operand with `Flags` 1. It is
counted once. A first pass counted it twice and showed two `NOT NOT x` mismatches. Both traced to
this, and the native storage settles it.

## R10 -- an FBD network as XAE stores it

Drawn in the editor and saved, not imported. New shapes, next to round 3's LD list:

- The body is `<Implementation><NWL>` with `<v n="DefaultViewMode">"Fbd"</v>`, the same container
  as LD.
- An unwired input, input 0 included, is a `BoxTreeOperand` whose `Operand` is `""`. No
  `BoxTreeTerminator` occurs anywhere in the network.
- An operator box sits inline in the FB box's `InputItems` as a `BoxTreeBox` with `CallType`
  `Operator` (`And`). Its own inputs are `BoxTreeOperand`s, and its one output is a bare `<n />`.
- The FB box (`CallType` `FunctionBlock`) lists its output operands by position against
  `OutputParam`. An unwired output is a bare `<n />`, as in LD.
- The export writes an unwired input as an `inVariable` with an empty `<expression />`. The
  operator becomes `block typeName="AND"` with `In1`, `In2` and `Out1`.

`pins` printed `CU <- (unwired)`, `RESET <- AND(bA, bB)`, `PV <- nPreset` and `CV -> bDone`. The
export says the same, and leaves Q unwired. The drawing put the assignment on CV, not Q, but storage,
export and `pins` agree. The test comment "in an Fbd network a terminator stays '(unwired)': no FBD
example has been checked" can now point here: none occurred.

## R14 -- findings by rule

| Rule | Sev | Count | Verdict |
|---|---|---|---|
| CP8 | high | 1 | **Real.** An actual position, latched once in one step, compared with `=` against its target. It is the finding v0.3.0 A4 already judged real |
| E3 | high | 2 | **False positive.** `ist_Zone.fEnd <= ist_Zone.fStart`, two LREAL members read through a `REFERENCE TO` a struct. The code is new since round 2 (bead 2) |
| CP24 | medium | 59 | Same count as round 2's real dead-code findings |
| CP23 | medium | 22 | Same as round 2 |
| X3 | medium | 17 | Same as round 2 |
| X6 | medium | 3 | Same as round 2 |
| X6 | low | 28 | Same as round 2 |

Round 2's 130 plus the two E3 findings make 132. As R14 asks, only the high findings were read one
by one. The medium and low counts match round 2 rule by rule.

## What the release can move

From README *Awaiting the release round*:

- **The round-3 `tcpou.py` fixes**: R2 to R7 pass. Whether the tests pass on Windows waits on
  bead 1.
- **`tcpou.py pins` on LD**: R8 passes. *No FBD network has been checked* is retired by R10: one
  drawn FBD network matched the export.
- **`xae_build.ps1`**: R11 to R13 pass.
- **The reviewer's severity classification** waits on bead 2.

After the two fixes, re-run R1 (clone and installed copy) and R14. If the R1 fix changes `tcpou.py`
rather than the tests, re-run R3 and R15 too, because they read `get`'s stdout.

## Beads

To file under `twincat-st-1hr` (the field-test bead); `bd` is not installed on the TwinCAT PC:

1. **R1: `run_tests.py` fails on Windows.** Two tests compare `get`'s stdout with LF bytes, and
   Windows prints CRLF. The fix goes either in the tests (compare after normalising line endings)
   or in `get` (print LF, as `--out` writes). Also add a `windows-latest` job to CI: this ran green
   there on `ubuntu-latest` only. Output: the R1 row above.
2. **R14: E3 reports an ordering comparison of members read through a `REFERENCE TO`.** The rule
   takes its pointer names from `is_pointerish`, which counts `REFERENCE TO`. Its regex keeps the
   identifier in front of `.member`. A reference is dereferenced implicitly, so neither
   `ref.a <= ref.b` nor `ref1 < ref2` compares addresses. Repro, no project code:

   ```
   FUNCTION_BLOCK FB_RefOrder
   VAR_INPUT
       ist_Zone : REFERENCE TO ST_Zone;    // fStart, fEnd : LREAL [mm]
   END_VAR
   VAR
       bEmpty : BOOL;
   END_VAR
   IF __ISVALIDREF(ist_Zone) THEN
       bEmpty := ist_Zone.fEnd <= ist_Zone.fStart;
   END_IF
   END_FUNCTION_BLOCK
   ```

   `st_review.py FB_RefOrder.st --rules E3` reports `high   E3    FB_RefOrder:9  only = and <>
   are defined on pointers; ordering relies on undocumented memory layout`, exit 1.

## Re-run after the fixes

R1 and R14 ran again on the same PC, as `field-test-round4.md` *Re-run after the fixes* lists them.
The skill was at `0dc4194` (PR #36), as the clone and as the installed copy: reinstalled from the
clone, 116 files, byte-identical, no `.git` or `.github`. Python 3.12.10, cmd.exe. `PYTHONUTF8` and
`PYTHONIOENCODING` were cleared, and `set PYTHON` listed only `PYTHONDONTWRITEBYTECODE`. `tcpou.py`
is byte-identical to `f69dd5b`, so R3 and R15 stand.

**Both pass.** Beads `twincat-st-ajl` (R1) and `twincat-st-gqw` (R14) can close, and nothing is left
under README *Awaiting the re-run*.

| # | Result | Evidence |
|---|---|---|
| R1 | pass | Clone and installed copy alike: exit 0, 116 `ok`, no `skip` line, last line `all checks passed`. The two logs are byte-identical. Round 4's two failures are `ok` under their new names: `get --out writes UTF-8 with no BOM, the text get prints, as LF bytes` and `two trailing line breaks are kept: an empty last line stays possible` |
| R14 | pass | At round 4's Project_A commit: 158 files, **130 findings**, `{'high': 1, 'medium': 101, 'low': 28}`, no E3. Finding for finding, that is round 4's 132 without its two E3. At Project_A's current `HEAD`: 158 files, 129 findings, `{'high': 1, 'medium': 100, 'low': 28}`, no E3 (see below). `--min-severity high` lists one finding at both: round 4's CP8, same line, still real |

### R14 -- Project_A's HEAD moved

Round 4's worktree was made before Project_A's last commits, so R14 ran at both commits. In between,
Project_A added an `__ISVALIDREF` check on a `REFERENCE TO` input, one line in one POU. At `HEAD`
the X6 on that input is gone: it was real, and the project fixed it. One CP24 and one X3 in the
same POU moved down a line. No other finding changed.

| Rule | Sev | Round 4's commit | `HEAD` |
|---|---|---|---|
| CP8 | high | 1 | 1 |
| E3 | high | 0 | 0 |
| CP24 | medium | 59 | 59 |
| CP23 | medium | 22 | 22 |
| X3 | medium | 17 | 17 |
| X6 | medium | 3 | 2 |
| X6 | low | 28 | 28 |

### Method notes

- The PC's system disk had about 150 MB free, and a full Project_A worktree no longer fits there.
  Each worktree was made with `--no-checkout` and then checked out only the eight folders of
  Project_A's own code, the 158 files. The reviewer ran from the PLC project folder with those
  eight folders as its paths, as round 4 did, so the framework libraries stay out. Both worktrees
  were removed afterwards.
- The scratch solution no longer held `FB_FbdProbe`: it was removed at the end of round 4.
