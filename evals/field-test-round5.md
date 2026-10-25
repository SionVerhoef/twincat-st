# Field test -- round 5, the 0.4.0 template check

The hand-off for one short round before 0.4.0 is tagged. Round 4 verified everything else in
README *Status*; since then the pre-release cleanup (PR #38) changed one piece of PLC code:
`templates/FB_Sequence.TcPOU` now keeps `bDone` latched until `bExecute` falls, as PLCopen and
`references/behaviour-model.md` say, instead of until the next rising edge. The README and
CHANGELOG say that change has not been rebuilt. This round either verifies it or finds it broken.
It also runs the rewritten recipe in `templates/README.md` once from PowerShell 5.1, because it was
only tested on Linux.

Same rules as the earlier rounds: the repository is public. Only the scratch TcUnit solution is
used, so no production project is involved. Write no customer, site or machine names, NetIDs or IPs
into the results.

## Setup

- TwinCAT PC: TwinCAT 3.1.4024.55, Python 3.12, Windows PowerShell 5.1.
- The skill at the head of branch `worktree-release-0.4.0-cleanup` (PR #38), both as the clone and
  as the installed copy under `~/.claude/skills/twincat-st`. Record the commit.
- `PYTHONUTF8` and `PYTHONIOENCODING` unset in every shell that runs a check, confirmed with an
  echo, as in rounds 3 and 4.
- The scratch TcUnit solution from rounds 3 and 4, with XAE closed. Commit or copy it first so it
  can be restored.

"Pass" means the expected result, verbatim where one is given. Anything else is a failure: file it
as its own bead with the output, and do not fix it on the PC.

## Checks

| # | Run | Expect | Retires |
|---|---|---|---|
| W1 | `py -3 tests/run_tests.py` from the clone and from the installed copy, env clean | exit 0, `all checks passed`, 119 `ok` lines | the new SKILL.md guards run on Windows |
| W2 | Bring the scratch project's `FB_Sequence` up to the branch: for each part `decl`, `impl`, `M_Fail:decl`, `M_Fail:impl`, run `get templates\FB_Sequence.TcPOU --part <p> --out p.st`, then `set <scratch>\FB_Sequence.TcPOU --part <p> --from-file p.st`. Then `py -3 scripts\tcpou.py code-equal <scratch>\FB_Sequence.TcPOU --against templates\FB_Sequence.TcPOU` | every `set` exits 0; `code-equal` prints IDENTICAL, exit 0; `git diff` in the scratch repo shows only the `bDone` lines and their comments, Ids unchanged | the scratch copy is the template being shipped |
| W3 | PowerShell 5.1: the *Using them* block of `templates\README.md`, verbatim, into the scratch project with `FB_Filling`. Skip the enum step: the scratch project already has `E_SeqState` | every command exits 0; `check` prints `ok`; `st_review.py` reports no findings; `FB_Filling` appears in the `.plcproj` | the template recipe on Windows |
| W4 | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\xae_build.ps1 -Solution <scratch>.sln`, no XAE open | exit 0, `Build complete -- 0 errors, 0 warnings`; this build covers W2 and W3 | "The templates compile" |
| W5 | **Human step.** Activate the scratch solution on the test controller (never one that holds a machine project) and let TcUnit run | `Tests: 2`, `Successful tests: 2`, `Failed tests: 0` (TcUnit 1.3.2 shows these as Errors; read the counts) | "the suite passed 2 of 2" |
| W6 | **Human step, optional.** Only if the scratch project already calls an `FB_Sequence` instance from a program: online, drive it to Done (`bExecute`, `bStep1Done`, `bStep2Done` TRUE), then write `bExecute := FALSE` | `bDone` stays TRUE while `bExecute` is TRUE and goes FALSE on the scan after it falls | the new latch behaves as documented |

W1 to W4 are mechanical and take minutes. W5 needs a human for the activation, because the skill
never activates (rule 2). W6 is a nice-to-have; W4 and W5 are the gate.

## Reporting

1. Write `evals/field-review-round5.md`: the commit tested, then one row per check, pass or fail,
   with the verbatim line or count it rests on. Keep the redaction rules above.
2. Commit it to `worktree-release-0.4.0-cleanup` and push. A failure gets its own bead with the
   output, and the PR stays unmerged.
3. If W4 and W5 pass, the README caveat on `FB_Sequence` and the CHANGELOG's "not rebuilt" line
   come out in a follow-up commit on the same branch, citing this round. Then merge and
   `/release publish`.
