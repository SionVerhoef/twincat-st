# Field test -- round 5, the 0.4.0 release round

The hand-off for the last round before 0.4.0 is tagged. Round 4 verified everything README
*Status* lists as verified at the time. Since then PR #38 merged two bodies of work that have not
been near a TwinCAT install:

- **The pre-release cleanup.** `templates/FB_Sequence.TcPOU` now keeps `bDone` latched until
  `bExecute` falls, as PLCopen and `references/behaviour-model.md` say; the recipe in
  `templates/README.md` was rewritten and only tested on Linux.
- **Skill review batch 1 (PR #39, merged into #38).** Reviewer rules X12, CP7 and CP12; the new
  `references/twincat/tasks-and-exceptions.md`; the rewritten restart table in
  `references/cyclic-execution-rules.md` Rule 9. README *Status* lists all three under *Not yet
  verified on a TwinCAT install*.

This round either verifies each of them or finds it broken.

Same rules as the earlier rounds: the repository is public, the production project is called
Project_A ("a packaging machine, TwinCAT 3.1.4024") and nothing else, no customer, site, machine
or module names, no NetIDs or IPs. Results go into `evals/field-review-round5.md` in that form.

## Setup

- TwinCAT PC: TwinCAT 3.1.4024.55, Python 3.12, Windows PowerShell 5.1.
- The skill at the head of branch `worktree-release-0.4.0-cleanup` (PR #38), both as the clone and
  as the installed copy under `~/.claude/skills/twincat-st`. Record the commit.
- `PYTHONUTF8` and `PYTHONIOENCODING` unset in every shell that runs a check, confirmed with an
  echo, as in rounds 3 and 4.
- The scratch TcUnit solution from rounds 3 and 4, with XAE closed. Commit or copy it first so it
  can be restored. Every POU this round adds to it goes again at the end.
- Project_A in a temporary worktree of its repository, read only: W6 scans it and changes nothing.
- The test controller, never one that holds a machine project. Every activation, online write and
  reset on it is a human step: the skill never activates or writes (rule 2), and the agent only
  proposes the command.

"Pass" means the expected result, verbatim where one is given. Anything else is a failure: file it
as its own bead with the output, and do not fix it on the PC.

## Checks

### Agent, no controller

| # | Run | Expect | Retires |
|---|---|---|---|
| W1 | `py -3 tests/run_tests.py` from the clone and from the installed copy, env clean | exit 0, `all checks passed`, 122 `ok` lines | tests on Windows, with the new rules and guards |
| W2 | Bring the scratch project's `FB_Sequence` up to the branch: for each part `decl`, `impl`, `M_Fail:decl`, `M_Fail:impl`, run `get templates\FB_Sequence.TcPOU --part <p> --out p.st`, then `set <scratch>\FB_Sequence.TcPOU --part <p> --from-file p.st`. Then `py -3 scripts\tcpou.py code-equal <scratch>\FB_Sequence.TcPOU --against templates\FB_Sequence.TcPOU` | every `set` exits 0; `code-equal` prints IDENTICAL, exit 0; `git diff` in the scratch repo shows only the `bDone` lines and their comments, Ids unchanged | the scratch copy is the template being shipped |
| W3 | PowerShell 5.1: the *Using them* block of `templates\README.md`, verbatim, into the scratch project with `FB_Filling`. Skip the enum step: the scratch project already has `E_SeqState` | every command exits 0; `check` prints `ok`; `st_review.py` reports no findings; `FB_Filling` appears in the `.plcproj` | the template recipe on Windows |
| W4 | In the scratch project, one POU per example in `references/twincat/tasks-and-exceptions.md`: the `TestAndSet` lock (with a `GVL` holding `bRecipeLock` and a small `stRecipe` structure), and the `__TRY`/`__CATCH` example. Paste each example as written and add only the declarations it needs; record every other edit the compiler forces | no edit beyond declarations. If the target refuses `__TRY`, the compiler says so; record its exact message | "none of its examples has been built" |
| W5 | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\xae_build.ps1 -Solution <scratch>.sln`, no XAE open | exit 0, `Build complete -- 0 errors, 0 warnings`; this build covers W2, W3 and W4 | "The templates compile", and W4's examples |
| W6 | `py -3 scripts\st_review.py <Project_A PLC application folder> --json` at the round's commit, then the same with `--rules X12,CP7,CP12` | the total against round 4's 130, and per rule how many; every X12, CP7 and CP12 finding read and judged real or false, with the reason. CP7 is high, so a false CP7 is a high-severity false positive and a failure | "Reviewer rules X12, CP7 and CP12" |

### Human steps on the test controller

| # | Run | Expect | Retires |
|---|---|---|---|
| W7 | Activate the scratch solution and let TcUnit run | `Tests: 2`, `Successful tests: 2`, `Failed tests: 0` (TcUnit 1.3.2 shows these as Errors; read the counts) | "the suite passed 2 of 2" |
| W8 | *Optional.* Only if the scratch project already calls an `FB_Sequence` instance from a program: online, drive it to Done (`bExecute`, `bStep1Done`, `bStep2Done` TRUE), then write `bExecute := FALSE` | `bDone` stays TRUE while `bExecute` is TRUE and goes FALSE on the scan after it falls | the new latch behaves as documented |
| W9 | Add a scratch POU that divides a `DINT` by a variable holding 0 when a BOOL is set; activate, log out, set the BOOL (the human writes it). Then follow *Finding the line* in `tasks-and-exceptions.md`: copy the core dump from `C:\TwinCAT\3.1\Boot\Plc` (4024), open it with *PLC → Core Dump → Load* against the same build | the PLC stops on the exception; the dump is where the doc says; XAE shows the faulting line, the call tree and variable values. Record anything the doc got wrong. Remove the POU afterwards | "the core-dump steps have not been walked through" |
| W10 | A scratch POU with `nPlain : DINT := 5` in `VAR`, `nRetain : DINT` in `VAR RETAIN` and `nPers : DINT` in `VAR PERSISTENT`. Write each to 7, then in turn: online change, download, *Reset cold*, *Reset origin*. Read all three after each step. Note whether the controller has NOVRAM mapped to the retain area | matches the Rule 9 table: online change keeps all three; download and *Reset cold* put `nPlain` back to 5 and keep the other two; *Reset origin* resets all three. A restart or power cycle is optional; if done, `nRetain` keeps its value only with NOVRAM mapped. Remove the POU afterwards | "The rewritten restart table" |

W1 to W6 are mechanical and take under an hour; W6 is the longest, because every new finding gets
read. W7 to W10 need a human at the controller, about half an hour.

## What gates the release

- **W1, W5, W6 and W7 must pass.** They cover the code that ships and the one high-severity rule.
- **W9 and W10 retire README lines; they do not gate.** If either is skipped or fails, the matching
  line stays under *Not yet verified on a TwinCAT install*, and a failure gets a bead. The
  release can ship with those lines listed, as long as they are true.

## Not in this round

- Agent-behaviour cells. The A/B evals compared this branch with `main` on Haiku 4.5 before #39
  was merged in: outcome checks 114 of 117 in both. `homed-survives-restart` failing with the
  skill is a known gap with its own bead, not a release blocker.
- Everything round 4 verified and nothing since has touched: `pins`, `code-equal`, the
  PowerShell encoding paths, `xae_build.ps1`'s warning and error paths.

## Reporting

1. Write `evals/field-review-round5.md`: the commit tested, then one row per check, pass, fail or
   skipped, with the verbatim line or count it rests on. Keep the redaction rules above.
2. Commit it to `worktree-release-0.4.0-cleanup` and push. A failure gets its own bead with the
   output, and the PR stays unmerged.
3. Restore the scratch solution and remove the Project_A worktree.
4. Back on the development side: lines W5–W10 verified come out of *Not yet verified* and the
   `FB_Sequence` caveat, citing this round; then merge and `/release publish`.
