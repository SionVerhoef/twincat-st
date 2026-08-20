---
name: twincat-st
description: "Structured Text for Beckhoff TwinCAT 3 and CODESYS V3 — write it, review it, and catch the scan-cycle bugs a general-purpose model reliably introduces. Covers IEC 61131-3 ST syntax, the POU model, OOP (METHOD/PROPERTY/INTERFACE/EXTENDS/IMPLEMENTS/ABSTRACT/THIS/SUPER), state machines, PackML, the PLCopen behaviour model (Execute/Done and Enable/Valid), error handling, FB_init and online change, TcUnit tests, .TcPOU/.TcDUT/.TcGVL/.TcIO/.plcproj files, ADS, EtherCAT and PLCopen motion (MC_Power, MC_MoveAbsolute, MC_Home). Use this skill whenever the user writes, reviews, refactors, debugs or asks about PLC code, Structured Text, TwinCAT, Beckhoff, CODESYS, XAE/TcXaeShell, a ladder-to-ST conversion, a machine sequence or an axis — and also when a directory simply contains .tsproj, .plcproj or .TcPOU files, even if nobody says 'TwinCAT'. It ships an executable reviewer (scripts/st_review.py) that finds blocking loops, unguarded pointers, float equality and missing timeouts, so prefer it over reviewing PLC code unaided. Do NOT use for Siemens SCL/TIA Portal, Rockwell Studio 5000 or OpenPLC/matiec — genuinely different dialects. Never authors TwinSAFE/FSoE safety logic."
---

# Structured Text that survives contact with a machine

**Target: the CODESYS V3 dialect family.** TwinCAT 3 primary (build 4024.x), CODESYS secondary. TwinCAT 3's PLC layer is CODESYS-V3-derived and shares its OOP extensions, so this is one core plus a vendor seam, not two products.

**Out of scope:** Siemens SCL, Rockwell Studio 5000 ST, OpenPLC/matiec. Those are different dialects — matiec implements IEC 61131-3 **2nd Edition** and has no `METHOD`, `PROPERTY`, `EXTENDS` or `INTERFACE` at all. Guidance from here would be fluent and wrong. Say so and stop.

## Why a skill, rather than just writing the code

A capable model writes Structured Text that *reads* correctly and *behaves* wrongly, because it imports a sequential mental model into a cyclically-scanned real-time system. The recurring failures are specific and predictable:

- `WHILE NOT bDone DO` where the answer was a state machine — the task overruns, the watchdog fires, the machine stops
- a `TON` preset written `PT := 500` instead of `PT := T#500MS`
- an `Execute` input driven from a level instead of an edge, so the block runs once and never again
- a wait with no timeout, so a failed sensor hangs the sequence with no diagnostic
- `IF fActual = fTarget` on an `LREAL`, which is essentially never true

None of these are syntax errors. A compiler accepts all of them. So the priority order here is deliberate: **execution model first, syntax second, vendor trivia last** — and the review step is a program, not a vibe.

## Three rules that override everything else

1. **Never author safety logic.** No TwinSAFE, no FSoE, no safety-PLC projects, and no emergency-stop handling written as standard PLC code and presented as a safety function. Functional safety needs a certified toolchain, a documented risk assessment and a competent person's sign-off, none of which an agent can supply. You may *read and explain* existing safety configuration. See `references/safety-boundary.md`.
2. **Never write to or activate a live machine.** Treat ADS as read-only. Writing a variable, activating a configuration or switching Run/Config on a real controller is a human gesture — propose the command, don't run it.
3. **Never claim code compiles when you have not compiled it.** There is almost certainly no PLC compiler here. `scripts/st_review.py` finds defect *patterns*; it is not a compiler, and a clean run proves only that nothing it knows about matched.

## Workflow

### 1. Orient before writing

PLC code is written against a *specific* machine. Guessing the I/O, the axis names or the library versions produces code that compiles and then does the wrong thing to real hardware.

Establish, and state what you assumed if you could not:

- vendor and version; which **task** this runs in and its **cycle time**
- the fault behaviour required — stop, hold, or continue degraded
- whether any part of this is a safety function (if yes → rule 1)
- what must survive a restart (→ `RETAIN` / `PERSISTENT`, see `references/cyclic-execution-rules.md`)

**Read `examples/` when style is the question** — new code going into an existing codebase, an unfamiliar convention, or "make this look like ours". It holds real working code from three published projects, and pattern-matching against working code beats following a written convention. It is also the most expensive thing here to read, so skip it for a contained change to code you can already see. If the team has added their own house code there, that outranks everything, including this skill.

### 2. Choose the shape before the syntax

Naming the shape first is what prevents the sequential-code failure. Almost every task is one of five:

| Shape | Use when | Pattern |
|---|---|---|
| **Cyclic logic** | Continuous evaluation — interlocks, scaling, alarms | Straight-line, no state |
| **State machine** | Anything with steps, waiting or a sequence | `CASE eState OF` + per-state timeout |
| **Command FB** | An action a caller triggers and awaits | PLCopen `Execute`/`Busy`/`Done`/`Error` |
| **Manager** | One instance per device, all driven together | Array of instances + bounded `FOR` |
| **Edge/latch** | React once to a change | `R_TRIG`/`F_TRIG` |

If you are reaching for a `WHILE` loop or the words "wait until", you have picked the wrong shape. Go back to the state machine row.

Choosing between a `Execute`-style and an `Enable`-style interface is a real decision with a non-obvious rule behind it — see `references/behaviour-model.md`.

### 3. Write

1. **Declarations first, fully typed**, with a unit in the comment for every physical value (`// mm/s`). Units in declarations prevent a class of bug no compiler catches.
2. **Interface before body** — inputs, outputs and the error path (`bError`, `nErrorID`) before any logic.
3. **All states in an `E_` enum**, including `Idle` and `Error`.
4. **Body state by state**, each with an explicit exit condition *and* a timeout.
5. **A reset path.** If there is no way out of `Error`, the block is not finished.

Match the surrounding project's conventions even where they differ from `references/naming-conventions.md`. A consistently different codebase beats a half-converted one; flag the divergence, don't silently "fix" it.

### 4. Review — with the tool, not by eye

Run the reviewer on anything you wrote or were asked to review:

```bash
py -3 scripts/st_review.py <file-or-dir>...             # defect rules
py -3 scripts/st_review.py src/ --pedantic              # + style rules
py -3 scripts/st_review.py src/ --json                  # machine-readable
py -3 scripts/st_review.py src/ --fail-on high          # CI gate (already the default)
py -3 scripts/st_review.py src/ --min-severity medium   # hide the low findings
py -3 scripts/st_review.py src/ --rules X1,X5,CP8       # only these rules
py -3 scripts/st_review.py --list-rules                 # what it checks
```

**Every command in this file is written `py -3`, because TwinCAT runs on Windows and Windows has no `python3`.** A bare `python3` there reaches the Microsoft Store alias stub, which prints *"Python was not found"* and exits 1 **even when Python is installed correctly** — so read the error as a wrong command, not a missing interpreter. On Linux or macOS use `python3` instead. The README has the detail.

**Point it at the code you own, not at the whole `.plcproj`.** A project pulls in vendor and framework libraries nobody on the team can change, and their findings bury yours: on one real 1352-file project, scanning everything gave 835 findings where the 111 application files gave 68. Scan the application folder.

**Exit status is 1 only at `--fail-on` or above, and that defaults to `high`.** A run reporting hundreds of `medium` findings still exits 0 — that is the gate working, not the tool ignoring them. `--min-severity` filters *before* the gate, so hiding a severity also stops it ever failing a build.

**Exit status 2 means a file could not be parsed, and it overrides `--fail-on never`.** An unreadable file produces no findings for the same reason an empty one does, so letting it pass would report a green check on code the reviewer never looked at. Unparsed files are listed on stderr and in the JSON under `files_unreadable`, and `files_scanned` counts only what was actually read.

It parses `.TcPOU`/`.TcDUT`/`.TcGVL`/`.TcIO` and plain `.st`, walking **every** declaration/implementation pair — POU body, methods, property getters and setters. That matters: a top-level-only parse misses about 84% of the code in an OOP project.

Findings carry a rule id you can cite in a review — `CP8`, `X1`, `E3`. The `CP`/`N`/`C`/`L`/`E` ids are PLCopen Coding Guidelines rules and carry that document's own severity; the `X` ids are this skill's own, for what that catalogue does not cover — the failure modes specific to a scanned task, plus `X9` for the PLCopen *behaviour model* contract, which is standardised in a different document. `references/plcopen-rules.md` is the full catalogue.

The tool is a floor, not a ceiling. It cannot see intent, so **you still read the code** for the things it cannot check: is the shape right, is the error path meaningful, does the timeout value make physical sense, is this secretly a safety function. `references/cyclic-execution-rules.md` carries the review rubric for that pass.

When the tool reports something you have judged acceptable, record the judgement in the code rather than ignoring the line:

```pascal
WHILE pNode <> 0 DO   // lint:allow X1 list is built at init, max 64 nodes
```

An unexplained suppression is itself reported, because a bare silencer and an unreviewed defect look identical six months later.

### 5. Say what you actually verified

Name the rung you reached. Never imply a higher one.

| Rung | What it proves |
|---|---|
| 1. **TcUnit on a real target**, results read back over ADS | Real semantics, real timing |
| 2. **Headless build** via the Automation Interface on a Windows runner | Full compiler errors |
| 3. **`scripts/st_review.py` + a human read** | Known defect patterns absent — **always do this** |
| 4. Nothing | Then say "unverified, not compiled" plainly |

There is deliberately no Linux syntax-check rung. `matiec` and `rusty` cannot parse the OOP constructs this dialect is built on, so a clean run there would prove almost nothing while looking like a pass.

Close with: what you wrote and which shape it uses · what was verified and what was not · the assumptions you made about I/O, cycle time and fault behaviour · what the human must do next.

## Where to read next

Load a reference when the task reaches it — don't read them all up front.

| File | Read it when |
|---|---|
| **`references/cyclic-execution-rules.md`** | **Writing or reviewing any ST.** The execution model and the review rubric. Highest-value file here. |
| `references/plcopen-rules.md` | Citing a rule, or doing a formal review. The 64-rule catalogue with severities. |
| `references/st-language.md` | Syntax, data types, the POU model, OOP constructs. Vendor-neutral. |
| `references/behaviour-model.md` | Designing an FB interface — `Execute`/`Done` vs `Enable`/`Valid`, abort and timeout. |
| `references/patterns.md` | State machines, sequences, PackML, and how to lay out a machine project. |
| `references/oop.md` | Inheritance vs composition vs interface; SOLID applied to function blocks. |
| `references/naming-conventions.md` | Naming anything. Measured against a real corpus, not asserted. |
| `references/testing-tcunit.md` | Writing tests, or asked whether the code is testable. |
| `references/safety-boundary.md` | **Anything** touching TwinSAFE, FSoE, E-stop, guards, or a SIL/PL claim. |
| `references/twincat.md` | TwinCAT specifics — libraries, `FB_init`, online change, 4024 gotchas. |
| `references/twincat/project-files.md` | Editing `.TcPOU`/`.plcproj`, or a git merge conflict in one. |
| `references/twincat/ads-and-diagnostics.md` | ADS access, EtherCAT triage, reading a running machine. |
| `references/codesys.md` | CODESYS rather than TwinCAT. **Marked untested** — say so. |

**Routing rule of thumb:** if the answer names a `Tc2_`/`Tc3_` library, a `.TcPOU` file, ADS or XAE, it is TwinCAT-specific and belongs behind `references/twincat.md`, not in a general answer.

## Tools

| Path | For |
|---|---|
| `scripts/st_review.py` | The reviewer. Run it on every change. |
| `scripts/tcpou.py` | Read and edit real `.TcPOU` files without disturbing GUIDs, `<LineIds>`, the BOM or CRLF. `new` scaffolds an object, `reguid` re-stamps Ids after copying a file, `register` adds it to the `.plcproj`. |
| `templates/` | Known-good skeletons — sequence FB, state enum, TcUnit suite. |
| `examples/` | Real working code from three published projects, each with its `LICENSE` and a `NOTES.md` on what to take from it. Read these before writing. House code added here outranks every convention in this skill. |

Both scripts need Python 3 and nothing else — standard library, no `pip install`. Commands are written `py -3` for Windows; on Linux or macOS use `python3`.

### `tcpou.py`

Editing a `.TcPOU` as plain text is how you corrupt a project. Every subcommand:

```bash
py -3 scripts/tcpou.py show     <file>                                   # parts + encoding
py -3 scripts/tcpou.py get      <file> --part impl                       # print one part
py -3 scripts/tcpou.py set      <file> --part impl --from-file body.st   # replace one part
py -3 scripts/tcpou.py new      --type fb --name FB_Filling --dir POUs/  # scaffold
py -3 scripts/tcpou.py register <PLC.plcproj> <file>...                  # make it compile
py -3 scripts/tcpou.py reguid   <file>...                                # re-stamp Ids
py -3 scripts/tcpou.py check    <file>...                                # validate
```

- `new` takes a **`--name`, not a path**, and picks the extension itself (`.TcPOU`/`.TcDUT`/`.TcGVL`). `--type` is one of `fb`, `prg`, `fun`, `dut`, `gvl`; `fb` also takes `--extends`, `--implements` and `--shape`.
- **`--shape` picks which interface family the FB gets:** `execute` (the default) declares `bExecute`/`bBusy`/`bDone`, `enable` declares `bEnable`/`bValid`, and `cyclic` declares no command interface at all. Choose the one the block actually is — `Execute` pairs with `Done`, `Enable` pairs with `Valid`, and mixing the two is what rule `X9` reports. `references/behaviour-model.md` is the decision.
- `set` reads stdin when `--from-file` is omitted.
- Part keys come from `show`: `decl`, `impl`, `Reset:impl`, `ActualValue.Get:impl`.

**Run `show` before `get`/`set` rather than guessing a part key.** A wrong key exits 1 and prints the real ones — but if you then verify your own edit by hashing the file, a `set` that never ran looks exactly like a `set` that changed nothing. Check the exit status, not just the bytes.

**A new file that is not registered in the `.plcproj` silently does not compile.** `tcpou.py register` is not optional; it is idempotent, so running it twice is safe.

## Adding material to this skill

Files from permissively-licensed sources (MIT, 0BSD, BSD-2, Apache-2) can be copied in — record them in `ATTRIBUTIONS.md` in the same commit. Anything else, including vendor documentation and standards, gets read and restated rather than pasted; vendoring a GPL file would relicense the whole skill.

`ATTRIBUTIONS.md` lists what this was built from and what each source contributed.
