# twincat-st

An agent skill for writing, reviewing and debugging IEC 61131-3 **Structured Text** in the
CODESYS V3 dialect family — **Beckhoff TwinCAT 3** primary (build 4024.x), **CODESYS**
secondary. Works with Claude Code and with GitHub Copilot in VS Code, from the same files.

Companion skill: **[twincat-scope](https://github.com/SionVerhoef/twincat-scope)** records and
triages TwinCAT 3 Scope measurements — what the code written here actually does on the machine.
They are independent; install either alone.

> **Not affiliated with or endorsed by Beckhoff Automation GmbH & Co. KG.**
> "TwinCAT" and "Beckhoff" are trademarks of Beckhoff Automation GmbH & Co. KG, used here
> nominatively to describe what this skill works with. "EtherCAT" is a registered trademark and
> patented technology, licensed by Beckhoff Automation GmbH, Germany. "CODESYS" is a trademark of
> CODESYS GmbH. "PLCopen" is a trademark of PLCopen.

## Install

```bash
# Claude Code
git submodule add https://github.com/SionVerhoef/twincat-st .claude/skills/twincat-st

# GitHub Copilot in VS Code
git submodule add https://github.com/SionVerhoef/twincat-st .github/skills/twincat-st
```

Or just clone it anywhere and point your agent at `SKILL.md`.

### Python

Both scripts need **Python 3** and nothing else — standard library only, no `pip install`.

On **Windows**, which is where TwinCAT runs:

```powershell
winget install -e --id Python.Python.3.12
```

Then invoke the scripts with **`py -3`**, never `python3`:

```powershell
py -3 scripts\st_review.py src\
```

Windows has no `python3.exe`. The python.org installer — which is what winget fetches —
creates `python.exe` and the `py` launcher, so a bare `python3` falls through to the
Microsoft Store alias stub, which prints *"Python was not found"* and exits 1 **even when
Python is installed correctly**. The scripts cannot warn you about this, because the stub
answers before Python ever starts. `SKILL.md` and the commands below are written `py -3` for
that reason; on Linux or macOS read them as `python3`.

## The claim

Syntax is not where model-written PLC code fails. **Execution model is.** A capable model will write a blocking `WHILE` loop into a cyclically-scanned real-time task, or set `PT := 500` where the type is `TIME`, or freeze a PLCopen motion block by guarding its call behind an `IF`. None of these are syntax errors and a compiler accepts all of them.

So this skill leads with the execution model, and it makes the review step **a program rather than a checklist**.

## What is here

```
twincat-st/
├── SKILL.md                            entry point — rules, workflow, routing
├── scripts/
│   ├── st_review.py                    the reviewer — 20 rules, PLCopen-keyed
│   └── tcpou.py                        surgical .TcPOU editing, reguid, .plcproj registration
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
│   └── codesys.md                      VENDOR — untested, flagged as such
├── templates/                          known-good FB / enum / TcUnit skeletons
├── examples/                           real MIT/BSD-2 code to pattern-match against
├── tests/                              every rule must fire; fixed false positives must stay fixed
├── evals/                              A/B prompts, a fixture project, and a self-graded grader
└── ATTRIBUTIONS.md                     what this was built from, and what each source gave it
```

## The reviewer

```bash
py -3 scripts/st_review.py src/                 # defect rules
py -3 scripts/st_review.py src/ --pedantic      # + contested style rules
py -3 scripts/st_review.py src/ --json          # machine-readable
py -3 scripts/st_review.py --list-rules         # what it checks
```

Python 3 and nothing else — both scripts use only the standard library.

Reads `.TcPOU`/`.TcDUT`/`.TcGVL`/`.TcIO` and plain `.st`, walking **every** declaration/implementation pair — POU body, methods, property getters and setters. A top-level-only parse misses roughly 84% of the code in an OOP project.

Findings carry a citable id. `CP`/`N`/`C`/`L`/`E` are PLCopen Coding Guidelines rules carrying that document's own severity; `X` ids are this skill's own, for what no general-purpose linter looks for — blocking loops, timer presets typed as integers, pointers dereferenced without a null check, state machines with no reachable error state, `FB_init` without an online-change guard, and an FB that mixes the two PLCopen behaviour models by pairing `Enable` with `Done`.

Exit status is 1 when anything at or above `--fail-on` (default `high`) is found, so it can gate CI.

### How it was validated

- **Detection:** `tests/run_tests.py` asserts every one of the 20 rules still fires on a
  deliberately defective fixture, and that the reviewer stays silent on a second fixture
  collecting every shape that was once a false positive. Both run in CI. Checking only that
  good code stays clean cannot catch a rule that has quietly stopped detecting anything —
  which is how `CP8` came to miss `bAtTarget := (fA = fB);`, the assignment form of the very
  defect this skill leads with.
- **The two tools check each other.** The tests scaffold an FB with `tcpou.py` and review it
  with `st_review.py`. Nothing did that before, which is how `new --type fb` came to emit
  `bEnable` alongside `bDone` — the PLCopen pairing violation `references/behaviour-model.md`
  names explicitly — into every function block created with this skill.
- **False positives:** swept across **440 real `.TcPOU` files** from Beckhoff's own samples, TcUnit, TcMatrix, the PackML example and Stefan Henneken's corpus. Four genuine false-positive classes were found and fixed during tuning — member access via `THIS^.` being read as an unused variable, type names leaking between methods of the same file, `POINTER TO LREAL` being treated as a float, and the mandatory `FB_init` parameters being reported as dead. Two contested rules (line length, early `RETURN`) were moved behind `--pedantic` because they fire hundreds of times on well-regarded code and drown the real findings.
- **Self-consistency:** the skill's own templates pass its own reviewer.

It is a pattern checker, not a compiler. A clean run means nothing it knows about matched — the tool says so on every run, and so should you.

## Scope, and why it is drawn there

- **Named for TwinCAT, targeted at the CODESYS V3 family.** TwinCAT 3's PLC layer is CODESYS-V3-derived and shares its OOP extensions, so this is one core plus a vendor seam. Roughly three quarters of "how to write good ST" transfers unchanged.
- **Not `iec61131-st`** — that name implicitly claims Siemens SCL and Rockwell ST, which are genuinely different dialects this skill cannot back.
- **Not OpenPLC.** OpenPLC compiles through matiec, which implements IEC 61131-3 **2nd Edition** — no `METHOD`, `PROPERTY`, `EXTENDS` or `INTERFACE`. On the language axis it is the narrowest target available, not the broadest.

## What it will not do

**Author safety logic.** No TwinSAFE, no FSoE, no E-stop implemented in standard PLC code and presented as a safety function. That work needs a certified toolchain, a documented risk assessment and a competent person's sign-off. The skill reads and explains existing safety configuration, works the standard-PLC side of the boundary, and says plainly where the line is. See `references/safety-boundary.md`.

**Touch a live machine.** ADS is read-only; activating a configuration or writing a variable on a real controller is proposed, never executed.

## Status

**Unverified against a compiler.** No TwinCAT toolchain exists in the environment this was built in, so no Structured Text here has been compiled and no template has been loaded into XAE. `scripts/st_review.py` is tested — against a fixture and 440 real files — but it checks patterns, not semantics.

`SKILL.md` rule 3 makes the skill declare that gap rather than paper over it. The same honesty applies to the skill itself.

The highest-value next step is filling `examples/` with real house code; see `examples/README.md`. House style outranks every convention written here.

## Sources

`ATTRIBUTIONS.md` lists what this was built from and what each source contributed.

## Licence

MIT — see `LICENSE`.

The ten files under `examples/` are redistributed from three upstream projects and keep their
own licences (MIT, MIT, BSD-2-Clause); each folder carries a verbatim `LICENSE` copy, as those
licences require. `ATTRIBUTIONS.md` has the full inventory, and the rule for adding more.
