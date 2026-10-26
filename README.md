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

Syntax is not where model-written PLC code fails. **Execution model is.** All but one of the
recurring defects compile, and the one that does not, `PT := 500`, needs a compiler the agent
almost never has:

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

- **`st_review.py`** — 30 rules. PLCopen Coding Guidelines rules (`CP`/`N`/`C`/`L`/`E`) carry
  that document's own severity; `X` rules are this skill's own: blocking loops, timer presets
  typed as integers, unchecked pointer dereferences, state machines with no reachable error
  state, timers and motion blocks called only inside a branch, `FB_init` without an
  online-change guard, and FBs that pair `Enable` with `Done`.
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
git -C .claude/skills/twincat-st checkout v0.4.1
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
│   ├── st_review.py                    the reviewer — 30 rules, PLCopen-keyed
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
│   ├── tools.md                        every reviewer flag and tcpou.py subcommand in full
│   ├── testing-tcunit.md               the test lane
│   ├── safety-boundary.md              the TwinSAFE/FSoE hard stop
│   ├── twincat.md                      VENDOR — libraries, FB_init, online change, 4024
│   ├── twincat/project-files.md        VENDOR — .TcPOU/.plcproj editing, git hygiene
│   ├── twincat/ads-and-diagnostics.md  VENDOR — ADS, EtherCAT triage
│   ├── twincat/xae-automation.md       VENDOR — headless builds, what a build rewrites
│   └── twincat/tasks-and-exceptions.md VENDOR — shared data between tasks, PLC exceptions
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

There is no TwinCAT toolchain where this skill is developed, so the line between verified and
not verified is the most important fact on this page. Five field rounds on TwinCAT 3.1.4024.55
drew it, and the evidence for each line below is in their records:
[`field-review-v0.3.0.md`](evals/field-review-v0.3.0.md),
[`field-review-round3.md`](evals/field-review-round3.md),
[`field-review-round4.md`](evals/field-review-round4.md),
[`field-test-round4.md`](evals/field-test-round4.md) and
[`field-review-round5.md`](evals/field-review-round5.md).

Whatever is verified here, **code an agent writes for you is still not compiled** unless you build
it, and `SKILL.md` rule 3 makes the agent say so every time.

**Verified**

- **The templates compile** in XAE 4024.55, the TcUnit suite against TcUnit 1.3.2, and the suite
  passed 2 of 2 on a test controller with its watchdog failing a hung test after 10 s. It passes
  2 of 2 against 0.4.0's `FB_Sequence` too, and on a controller that block's `bDone` stays TRUE
  while `bExecute` is held and falls on the first scan that sees `bExecute` FALSE.
- **`tcpou.py` round-trips a real project:** `new`, `register`, `set`, `reguid`, `add-method` and
  `add-property` produce files XAE opens without a repair prompt and builds.
- **Agent-written code built as delivered** in two field-test tasks, in two rounds.
- **The reviewer on a production project:** no high-severity false positive left; the one
  high finding is a real CP8. X12, CP7 and CP12 report nothing there, correctly: the project
  has no code in their scope, so that shows no false positives, not that they catch defects.
- **`PT := 500` is a compile error**, as the skill says: `Cannot convert type 'INT' to type 'TIME'`.
- **All 30 reviewer rules fire** on a defective fixture, and the reviewer stays silent on every shape that was
  once a false positive, swept across about 1,670 real files from public TwinCAT projects.
- **The test suite passes on Windows and Linux**, from a clone and from an installed copy.
- **`code-equal` holds on a real project:** about 1,350 unmodified files under
  `core.autocrlf=true`, all IDENTICAL.
- **`tcpou.py` moves a part losslessly from Windows PowerShell 5.1 and cmd.exe.**
- **`tcpou.py pins` matches XAE's own PLCopen export** on LD and FBD networks, 0 mismatches.
- **`xae_build.ps1`** builds with or without XAE open, and fails cleanly on a wrong path.
- **`references/twincat/tasks-and-exceptions.md` on a 4024 x64 controller:** the core-dump steps
  work as written. An integer division by zero stopped the PLC, the dump was in the folder the
  reference names, and XAE loaded it logged out, with the faulting line, the variable values and
  the call stack. The `TestAndSet` example builds; `__TRY` is refused at build time, as the
  reference says.
- **The restart table** (`cyclic-execution-rules.md` Rule 9) on a 4024 controller: the `VAR` and
  `PERSISTENT` rows as printed, and `RETAIN` without a retain handler, which keeps its value only
  through an online change.
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

**Not yet verified on a TwinCAT install** (no field round had the hardware)

- **`VAR RETAIN` with a retain handler.** Rule 9's *kept* cells for `RETAIN` restate InfoSys; no
  controller with NOVRAM and a retain handler has been tried.
- **`__TRY` on a 32-bit runtime.** Only an x64 runtime was available, and it refuses `__TRY`.

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
