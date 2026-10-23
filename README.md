# twincat-st

An agent skill for writing, reviewing and debugging IEC 61131-3 **Structured Text** in the
CODESYS V3 dialect family, verified on **Beckhoff TwinCAT 3** (build 4024.x). Tested with Claude
Code and with GitHub Copilot in VS Code, from the same files.

Companion skill: **[twincat-scope](https://github.com/SionVerhoef/twincat-scope)** records and
triages TwinCAT 3 Scope measurements — what the code written here actually does on the machine.
They are independent; install either alone.

> **Reference material only. Not for safety functions.** All generated code must be reviewed
> and validated by a qualified engineer against the drive and platform documentation before
> it runs on a machine.

> **Not affiliated with or endorsed by Beckhoff Automation GmbH & Co. KG.**
> "TwinCAT" and "Beckhoff" are trademarks of Beckhoff Automation GmbH & Co. KG, used here
> nominatively to describe what this skill works with. "EtherCAT" is a registered trademark and
> patented technology, licensed by Beckhoff Automation GmbH, Germany. "CODESYS" is a trademark of
> CODESYS GmbH. "PLCopen" is a trademark of PLCopen.

## Why

Syntax is not where model-written PLC code fails. **Execution model is.** The recurring
defects all compile:

- `WHILE NOT bDone DO` inside a cyclic task, where the answer was a state machine — the task
  overruns, the watchdog fires, the machine stops.
- `PT := 500` on a `TON`, where the preset is a `TIME` and needed `T#500MS`.
- A PLCopen `Execute` driven from a level instead of an edge, or its call guarded behind an
  `IF`, so the block runs once and never again.
- A wait with no timeout, so a failed sensor hangs the sequence with no diagnostic.
- `IF fActual = fTarget` on an `LREAL`, which is essentially never true.

There is a second problem too. A `.TcPOU` is XML holding GUIDs, a BOM and CRLF line endings,
and a generic edit corrupts it. A new file that is not registered in the `.plcproj` never
compiles at all.

This skill gives the agent the execution model first, syntax second and vendor detail last,
plus two scripts: a reviewer that finds these patterns whether or not the model would have,
and a tool that edits TwinCAT project files without breaking them.

**What it has shown so far.** In A/B evals on a real project folder (three runs per task,
graded on the files the agent left behind), a strong model — Claude Opus 5.5 — avoided most of
these defects without the skill. With it, the code was barely better, but the answers were: they
stated that nothing was compiled, cited rule ids and declined out-of-scope dialects (98% against
88%, at about 2.4× the cost). On a smaller model the skill changes the code itself. Without it,
Claude Haiku 4.5 designed an E-stop as ordinary PLC logic and left sensor waits with no
timeout. With it, every run declined to write the E-stop as a safety function, and the
engineering checks on its failed tasks rose from 10.3 to 15.7 of 18, at about 5× the tokens.
Details, including where the grader flatters either arm: [`evals/results-iteration-2.md`](evals/results-iteration-2.md),
[`evals/results-scouting.md`](evals/results-scouting.md), [`evals/results-haiku.md`](evals/results-haiku.md).

## Features

**Write and review Structured Text**

- **`st_review.py`** — 27 rules. PLCopen Coding Guidelines rules (`CP`/`N`/`C`/`L`/`E`) carry
  that document's own severity; `X` rules are this skill's own: blocking loops, timer presets
  typed as integers, unchecked pointer dereferences, state machines with no reachable error
  state, `FB_init` without an online-change guard, and FBs that pair `Enable` with `Done`.
- **Reads real projects** — `.TcPOU`/`.TcDUT`/`.TcGVL`/`.TcIO` and plain `.st`, walking every
  method and property, not only the POU body. A top-level-only parse misses about 84% of the
  code in an OOP project.
- **CI-ready** — exits 1 at or above `--fail-on` (default `high`); `--json` for machines;
  contested style rules sit behind `--pedantic`.
- **Known-good templates** — FB, enum and TcUnit test-suite skeletons that pass the skill's own
  reviewer.

**Edit TwinCAT project files safely**

- **`tcpou.py`** — `show`, `get` and `set` one method or property of a `.TcPOU` without
  touching its GUIDs, BOM or line endings; `new` scaffolds an object with a fresh GUID;
  `register` adds it to the `.plcproj`; `reguid` and `check` repair and validate; `pins` lists
  the wiring of FBD/LD boxes; `code-equal` proves an edit changed only comments.
- **`xae_build.ps1`** — on a Windows PC with XAE, builds the solution in a hidden XAE and prints
  the real compiler output. It never activates.

**Guidance for the agent**

- The cyclic execution model and a review rubric built on it.
- The PLCopen behaviour models (`Execute`/`Done` against `Enable`/`Valid`), state machines,
  PackML, OOP and TcUnit testing.
- TwinCAT specifics: libraries, `FB_init`, online change, ADS and EtherCAT triage. CODESYS
  vendor specifics are not covered, and the skill says so when asked.
- Naming conventions measured against a real corpus — and the rule that **the project you are
  editing wins** over any of them.
- Three hard rules: no safety logic, no writes to a live machine, and no claim that code
  compiles when it has not been compiled.

## Install

```bash
# Claude Code
git submodule add https://github.com/SionVerhoef/twincat-st .claude/skills/twincat-st

# GitHub Copilot in VS Code
git submodule add https://github.com/SionVerhoef/twincat-st .github/skills/twincat-st
```

Pin a release rather than following `main`, and commit the pin:

```bash
git -C .claude/skills/twincat-st checkout v0.3.0
git add .claude/skills/twincat-st
```

A plain `git clone` of your repository leaves a submodule folder **empty**. Everyone who clones
afterwards needs `git clone --recurse-submodules <your-repo>`, or `git submodule update --init`
in an existing clone.

If you would rather not use submodules, download a release zip from
[Releases](https://github.com/SionVerhoef/twincat-st/releases) and unpack it into the same folder.

### Requirements

**Python 3**, standard library only — no `pip install`. On Windows, where TwinCAT runs:

```powershell
winget install -e --id Python.Python.3.12
py -3 scripts\st_review.py src\
```

Use **`py -3`**, never `python3`. Windows has no `python3.exe`, so a bare `python3` reaches the
Microsoft Store alias stub, which prints *"Python was not found"* **even when Python is
installed correctly** — and it answers before Python starts, so the scripts cannot warn you.
On Linux or macOS, read `py -3` as `python3`.

## Usage

You mostly don't call anything: ask the agent about your ST and the skill loads. The scripts
also run on their own:

```bash
py -3 scripts/st_review.py src/                 # defect rules
py -3 scripts/st_review.py src/ --pedantic      # + contested style rules
py -3 scripts/st_review.py src/ --json          # machine-readable
py -3 scripts/st_review.py --list-rules         # what it checks

py -3 scripts/tcpou.py show POUs/FB_Axis.TcPOU  # every editable part of one file
py -3 scripts/tcpou.py --help                   # all subcommands
```

The reviewer is a pattern checker, not a compiler. A clean run means nothing it knows about
matched — the tool says so on every run, and so should you.

## Layout

```
twincat-st/
├── SKILL.md                            entry point — rules, workflow, routing
├── scripts/
│   ├── st_review.py                    the reviewer — 27 rules, PLCopen-keyed
│   ├── tcpou.py                        surgical .TcPOU editing, FBD/LD pins, comments-only proof
│   └── xae_build.ps1                   headless XAE build (Windows + XAE only, never activates)
├── references/
│   ├── cyclic-execution-rules.md       CORE — the execution model + review rubric
│   ├── plcopen-rules.md                the 64-rule PLCopen catalogue, with severities
│   ├── st-language.md                  syntax, types, POU model, OOP constructs
│   ├── behaviour-model.md              FB interface contract — Execute/Done vs Enable/Valid
│   ├── patterns.md                     state machines, PackML, project structure
│   ├── oop.md                          inheritance vs composition, SOLID for FBs
│   ├── naming-conventions.md           conventions, measured against a real corpus
│   ├── testing-tcunit.md               the test lane
│   ├── safety-boundary.md              the TwinSAFE/FSoE hard stop
│   ├── twincat.md                      VENDOR — libraries, FB_init, online change, 4024
│   ├── twincat/project-files.md        VENDOR — .TcPOU/.plcproj editing, git hygiene
│   ├── twincat/ads-and-diagnostics.md  VENDOR — ADS, EtherCAT triage
│   └── twincat/xae-automation.md       VENDOR — headless builds, what a build rewrites
├── templates/                          known-good FB / enum / TcUnit skeletons
├── examples/                           real MIT/BSD-2 code to pattern-match against
├── tests/                              every rule must fire; fixed false positives must stay fixed
├── evals/                              A/B prompts, fixture projects, grader and runner
└── ATTRIBUTIONS.md                     what this was built from, and what each source gave it
```

## Scope

- **TwinCAT and the CODESYS V3 family.** TwinCAT 3's PLC layer is CODESYS-V3-derived and
  shares its OOP extensions, so the core applies across the family. Only the TwinCAT seam is
  covered and verified; CODESYS library names, project format and tooling are not.
- **Not Siemens SCL or Rockwell Studio 5000 ST.** They are genuinely different dialects;
  guidance from here would be fluent and wrong, so the skill says so and stops.
- **Not OpenPLC.** It compiles through matiec, which implements IEC 61131-3 **2nd Edition** —
  no `METHOD`, `PROPERTY`, `EXTENDS` or `INTERFACE`.
- **No safety logic.** No TwinSAFE, no FSoE, no E-stop written as standard PLC code and
  presented as a safety function. The skill reads and explains existing safety configuration
  and works the standard-PLC side of the boundary. See `references/safety-boundary.md`.
- **No writes to a live machine.** ADS is read-only; activating a configuration or writing a
  variable is proposed, never executed.

## Status

There is no TwinCAT toolchain where this skill is developed. That makes the line between
verified and not verified the most important fact on this page. Four field rounds on TwinCAT
3.1.4024.55 drew it ([`evals/field-review-v0.3.0.md`](evals/field-review-v0.3.0.md),
[`evals/field-review-round3.md`](evals/field-review-round3.md),
[`evals/field-review-round4.md`](evals/field-review-round4.md)). The fourth was the release
round ([`evals/field-test-round4.md`](evals/field-test-round4.md)): 13 of its 15 checks passed,
the two that failed are fixed here, and the list under *Awaiting the re-run* is what the re-run
of those two checks has to clear before the release.

Whatever is verified here, **code an agent writes for you is still not compiled** unless you build
it. The field tests built a handful of answers; they say nothing about the next one, and `SKILL.md`
rule 3 makes the agent say so every time.

**Verified**

- **The templates compile.** `E_SeqState`, `FB_Sequence` and `FB_ExampleTestSuite` build in XAE
  4024.55 with no errors, the suite against TcUnit 1.3.2.
- **The TcUnit suite fails loudly.** On a test controller it passed 2 of 2, and a test whose
  condition never arrives failed through its watchdog after 10 s instead of hanging the suite.
- **`tcpou.py` round-trips a real project.** A file made with `new`, `register`, `set` and
  `reguid` opened in XAE with no repair prompt and built. Opening and building rewrote none of
  the files `tcpou.py` wrote. A file written by `add-method` and `add-property` built clean too,
  and `xae_build.ps1 -TreePath` lists the method it added.
- **Agent-written code built as delivered** in two field-test tasks, twice: a new valve FB, and a
  step added to `FB_Sequence` by editing the `.TcPOU` in place, in the first round and again in
  the re-run on the fixed skill.
- **The fixed reviewer, re-run on the production project it was tuned on,** reports 130
  findings against 270 before the four false-positive fixes; 59 of them are CP24 and real. The
  release round read every high-severity finding on that project: one is real (CP8, a measured
  position compared exactly with its target) and two were E3 false positives on code added since
  round 2, fixed here (see *Awaiting the re-run*).
- **`PT := 500` is a compile error**, as the skill says: `Cannot convert type 'INT' to type 'TIME'`.
- Every one of the 27 reviewer rules fires on a deliberately defective fixture, and the reviewer
  stays silent on a second fixture collecting every shape that was once a false positive.
- False positives swept across 440 real `.TcPOU` files while tuning the rules — Beckhoff's
  samples, TcUnit, TcMatrix, a PackML example and Stefan Henneken's corpus — and across 1,230
  files from ten public TwinCAT projects since 0.2.0.
- The two scripts check each other: tests scaffold an FB with `tcpou.py` and review it with
  `st_review.py`. The shipped templates pass the reviewer.
- **`code-equal` holds on a real project.** Over the 1,353 unmodified source files of a
  production project against `HEAD` under `core.autocrlf=true`: 1,353 IDENTICAL, 0 DIFFERENT,
  0 CANNOT COMPARE. Round 3's one false DIFFERENT, a CR kept inside a multi-line string literal,
  was among them.
- **`tcpou.py` moves a part safely from Windows PowerShell 5.1 and cmd.exe.** `get --out` then
  `set --from-file` round-trips a part with `²` with no diff; a UTF-16 file from `>` is decoded,
  and the `┬▓` it carries is named in one warning line; one trailing line break from a pipe or an
  editor leaves no diff; a file that is neither UTF-8 nor UTF-16 with a BOM is refused in one
  line with the target unchanged; `get` into a reader that stops early exits quietly.
- **`tcpou.py pins` matches XAE's own PLCopen export.** Six LD callers of a 4024 production
  project, 56 boxes and 1,076 pins, 0 mismatches: the rung input, negations, the owning method,
  and the coil and RETURN rungs print as the export has them. One FBD network drawn in XAE
  matched its export on every pin; XAE stores an unwired FBD input, input 0 included, as an
  empty `BoxTreeOperand`, so `(unwired)` is right there.
- **`xae_build.ps1`** built the scratch TcUnit solution with no XAE open (`Build complete -- 0
  errors, 0 warnings`, exit 0). With the same solution open in XAE it warned first, that XAE
  asked once to reload the `.xti`, and Yes was the end of it. A wrong `-PublicAssemblies` printed
  one line and left no XAE running.
- Agent behaviour in A/B evals on Opus and Haiku, as summarised under *Why*.

**Not supported**

- **CFC bodies.** `tcpou.py pins` refuses a `<CFC>` body with exit 2 instead of listing nothing.
  CFC is a separate editor with its own storage (`CFCImplementationObject`); the projects this
  skill was tested on use LD for every graphical POU, and how a CFC box is stored has never been
  observed. `st_review.py` still counts a CFC body's operands as uses.
- **CODESYS specifics.** The vendor-neutral core applies to any CODESYS V3 tool, since TwinCAT's
  PLC layer is CODESYS-V3-derived, but library names, the `.project` container, SoftMotion, OPC
  UA and the CODESYS test tooling are not covered. Nothing here was checked on a CODESYS
  install, so the skill says so rather than guess.

**Awaiting the re-run** (`evals/field-test-round4.md`, *Re-run after the fixes*)

The release round failed two of its fifteen checks. Both are fixed here with a test, and neither
fix has been run on the TwinCAT PC:

- **The test suite on Windows** (R1). Two checks compared `get`'s stdout with LF bytes, and on
  Windows a text stream prints CRLF: 114 ok, 2 failed, from the clone and the installed copy
  alike. They now compare with line endings normalised, `tcpou.py` is unchanged, and CI runs the
  suite on `windows-latest` as well as `ubuntu-latest`. The re-run expects 116 ok.
- **No high-severity false positive** (R14). The round found 132 findings on the production
  project, 3 high: one real (CP8) and two E3 on `ist_Zone.fEnd <= ist_Zone.fStart`, two LREAL
  members read through a `REFERENCE TO`. E3 now takes only `POINTER TO` names and only a whole
  identifier as an operand. The re-run expects 130 findings and one high.

After the re-run, both items move to *Verified*, this heading goes, and the release is tagged.

The most useful contributions are a run of `st_review.py` on your own project with each finding
judged real or false, and real house code for `examples/` — see `examples/README.md`.

## Tests

```bash
py -3 tests/run_tests.py          # every rule fires; known false positives stay silent
py -3 evals/selftest.py           # the eval grader: gold scores full, null scores zero
```

Both run in CI, the test suite on Linux and on Windows. These are plain scripts, not pytest suites. `evals/README.md` explains how the
skill itself is evaluated against a no-skill baseline.

## Licence

MIT — see `LICENSE`.

The eight files under `examples/` are redistributed from two upstream projects and keep their
own licences (MIT, BSD-2-Clause); each folder carries a verbatim `LICENSE` copy, as those
licences require. `ATTRIBUTIONS.md` lists what this was built from, what each source
contributed, and the rule for adding more.
