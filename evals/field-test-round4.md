# Field test -- round 4, the release round

This is the hand-off for the last test round before the skill is released. Its job is to empty
the *Awaiting the release round* list in README *Status*: after it, every item there is either
verified and moved up, or taken out of the skill. Nothing stays "not yet verified" in a release.

Same rules as the earlier rounds: the repository is public, the production project is called
Project_A ("a packaging machine, TwinCAT 3.1.4024") and nothing else, no customer, site, machine
or module names, no NetIDs or IPs. Results go into `evals/field-review-round4.md` in that form.

## Setup

- TwinCAT PC: TwinCAT 3.1.4024.55, Windows 10, Python 3.12, Windows PowerShell 5.1 and cmd.exe.
- The skill at the release-candidate commit (this PR merged into `main`), both as the clone and
  as the installed copy under `~/.claude/skills/twincat-st`.
- `PYTHONUTF8` and `PYTHONIOENCODING` unset in every shell that runs a check. The agent's own
  shell inherits `PYTHONIOENCODING=utf-8:surrogateescape` from its host app; clear it there and
  confirm with an echo, as round 3 did.
- Project_A in a temporary worktree of its repository, restored after every check; the scratch
  TcUnit solution from round 3.

Each check names the README line it retires. "Pass" means the expected result, verbatim where one
is given; anything else is a failure, filed as its own bead with the output.

## Checks

| # | Run | Expect | Retires |
|---|---|---|---|
| R1 | `py -3 tests/run_tests.py` from the clone and from the installed copy, env clean | exit 0, `all checks passed`, 116 ok, no `skip` line | round-3 fixes (tests pass on Windows) |
| R2 | PowerShell 5.1, a Project_A POU with `²` in a comment: `get X --part decl --out d.st`, then `set X --part decl --from-file d.st` | `git diff` empty | `get --out` |
| R3 | PowerShell 5.1, same POU: `get X --part decl > d16.st` (Out-File, UTF-16), then `set --from-file d16.st` | exit 0, no traceback, one `warning:` line on stderr naming `┬▓`; the file now holds `┬▓` where `²` was -- `git restore` it | UTF-16 decoding, mojibake warning |
| R4 | PowerShell 5.1, a POU without non-ASCII: `Get-Content d.st \| py -3 tcpou.py set X --part impl` where `d.st` came from `get --out` | `git diff` empty: no extra line before `]]>` | trailing line break from a pipe |
| R5 | Open `d.st` from R2 in an editor that adds a final newline (VS Code, Notepad++), save without other changes, `set --from-file d.st` | `git diff` empty | trailing line break from an editor |
| R6 | cmd.exe: a file holding only bytes that are neither UTF-8 nor UTF-16-with-BOM (e.g. `²` saved as cp1252), `set --from-file bad.st` | exit 1, exactly one stderr line ending `not UTF-8 or UTF-16 with a BOM`, naming the file, target unchanged | refusal path |
| R7 | `py -3 tcpou.py code-equal <all 1,352 Project_A source files> --ref HEAD` on the untouched checkout, `core.autocrlf=true` | 1,352 IDENTICAL, 0 DIFFERENT, 0 CANNOT COMPARE, exit 0 | `code-equal` under autocrlf |
| R8 | `pins` on the same six LD callers as round 3, against XAE's PLCopen export (`ITcPlcIECProject.PlcOpenExport`) | 0 mismatches over the 1,066 pins; 48 rung inputs print `(rung: left rail, TRUE)`; the 6 negations print `NOT x`; the coil rung and the 18 RETURN rungs appear as `(coil) ... [Method]` and `(return) <- ... [Method]`; `--pin <coil variable>` finds the coil; `--box <instance>` lists no rung lines | `pins` on LD |
| R9 | `pins` on the XAE-made empty CFC POU from round 3 | `CFC body: pins reads FBD/LD networks only`, exit 2 | CFC refusal (then listed under *Not supported*, nothing to retire) |
| R10 | In the scratch project, draw one FBD POU: an FB box with a wired input, an operator (AND/OR) input, one unwired input and one wired output. Save, `pins`, and compare with the PLCopen export | pins match the export. Note what XAE stores at input 0 of an FBD box; if it is a `BoxTreeTerminator`, report it, because `pins` prints `(unwired)` there and the README must say so or the code must change | "No FBD network has been checked" |
| R11 | `xae_build.ps1` on the scratch solution with no XAE open | exit 0, `Build complete -- 0 errors, 0 warnings`, no `WARNING:` line | `xae_build.ps1` (normal path) |
| R12 | `xae_build.ps1` on the scratch solution while the same solution is open in XAE | a `WARNING: the solution is open in XAE (PID n)` line before the build; the open XAE shows the `.xti` reload prompt; **Yes** reloads with no further prompt; build exit 0 | same-solution warning and the doc's advice |
| R13 | `xae_build.ps1 -PublicAssemblies C:\nowhere` | exit 1, one line on stderr (`envdte.dll not found in 'C:\nowhere'. Pass -PublicAssemblies for this XAE install.`), no error record with script position, no XAE left running | `[Console]::Error.WriteLine` fix |
| R14 | `py -3 scripts/st_review.py <Project_A PLC folder>` at the release commit; read every **high**-severity finding | the total (round 2: 130) and, per rule, how many; 0 high-severity false positives. A real high finding is fine and should be listed with its rule | reviewer severity classification |
| R15 | `py -3 tcpou.py get <big POU> \| Select-Object -First 3` (PowerShell) and `\| more` then `q` (cmd) | the first lines, then nothing: no `! None: Broken pipe`, no traceback | broken-pipe exit |

R1 to R7, R11, R13 and R15 are mechanical and take minutes. R8 and R14 take the export and a read
through the findings; round 3 did R8 in about an hour. R10 needs a human at the editor for a few
minutes. R12 needs XAE open at the same time.

## Not in this round

- Agent-behaviour cells (B1 to B5). Both earlier rounds recorded them and the skill text they
  grade has not changed since; the release notes cite those runs.
- CFC parsing. Out of scope: README lists it under *Not supported*; R9 only confirms the refusal.
- CODESYS. `references/codesys.md` is removed; nothing CODESYS-specific is left to verify.
- The candidate eval `labeler-recipe-offset` (`evals/candidates.json`). Scouting it is useful but
  does not gate the release.

## Reporting and release

1. Write `evals/field-review-round4.md`: one row per check, pass or fail, the verbatim line or
   count that proves it, redacted as above.
2. Every failure is a bead and a fix; re-run that one check after the fix. R10 may end as a
   documented limitation instead of a fix if FBD stores something `pins` cannot read yet; then the
   README says exactly that under *Not supported*, not under *Awaiting*.
3. The release PR moves each passed item from *Awaiting the release round* to *Verified*, deletes
   that heading, and bumps `CHANGELOG.md` from *Unreleased* to the release version with the date.
   The version is the maintainer's call; the field-test gate bead (`twincat-st-1hr`) names 1.0.0.
4. Tag and publish through `/release`, per the maintainer's release flow.
