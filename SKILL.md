---
name: twincat-st
description: "Use for any Structured Text question or task on Beckhoff TwinCAT 3 or CODESYS V3, even a one-liner: a timer, counter or trigger that never fires, a hung state machine, OOP (EXTENDS, ABSTRACT, SUPER^, interfaces, FB_init, online change), writing or reviewing function blocks, ladder-to-ST conversion, PackML, PLCopen motion and Execute/Done, ADS, TcUnit, .TcPOU/.plcproj files, or a folder that contains them. Easy-looking questions hide the dialect traps (PT := 500, level-driven Execute, blocking loops, float equality); it knows them and ships a reviewer, so use it rather than answering from memory. Not for Siemens SCL/TIA Portal, Rockwell Studio 5000, OpenPLC/matiec, EtherCAT wiring or hardware selection, Scope traces, or drawing ladder diagrams. Never write TwinSAFE/FSoE safety logic."
---

# Structured Text that survives contact with a machine

> **Reference material only. Not for safety functions.** All code you generate must be reviewed and validated by a qualified engineer against the drive and platform documentation before it runs on a machine. Every hand-over ends with the fixed line in step 5.

**Target: the CODESYS V3 dialect family.** TwinCAT 3 (build 4024.x) is the verified platform. Its PLC layer is CODESYS-V3-derived and shares the OOP extensions, so the vendor-neutral core here applies to CODESYS and the tools built on it; their library names, `.project` container and test tooling are **not covered**, and nothing in this skill was checked on a CODESYS install. On a CODESYS question, answer from the core and say that the vendor specifics are unverified rather than guess at them.

**Out of scope:** Siemens SCL, Rockwell Studio 5000 ST, OpenPLC/matiec. Those are different dialects — matiec implements IEC 61131-3 **2nd Edition** and has no `METHOD`, `PROPERTY`, `EXTENDS` or `INTERFACE` at all. Guidance from here would be fluent and wrong. Say so and stop.

## Why a skill, rather than just writing the code

A capable model writes Structured Text that *reads* correctly and *behaves* wrongly, because it imports a sequential mental model into a cyclically-scanned real-time system. The recurring failures are specific and predictable:

- `WHILE NOT bDone DO` where the answer was a state machine — the task overruns, the watchdog fires, the machine stops
- a `TON` preset written `PT := 500` instead of `PT := T#500MS`
- an `Execute` input driven from a level instead of an edge, so the block runs once and never again (reviewer rule `X11`)

**Asked to add "another one like this", check the existing line first.** If it carries one of these traps, name that line as the problem before writing anything next to it. Copying its style copies the defect: in a field test an agent kept `Execute := bAutoMode AND bAtHome` unremarked and delivered a second level-driven move beside it.
- a wait with no timeout, so a failed sensor hangs the sequence with no diagnostic
- `IF fActual = fTarget` on an `LREAL`, which is essentially never true
- `SEL(bOption, 0, fWidth)` read as "0 when set": `SEL(G, IN0, IN1)` returns its **first** value when `G` is FALSE. `references/st-language.md` has `MUX` and `LIMIT` too

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

**Read `examples/` when style is the question** — new code going into an existing codebase, an unfamiliar convention, or "make this look like ours". It holds real working code from two published projects, and pattern-matching against working code beats following a written convention. It is also the most expensive thing here to read, so skip it for a contained change to code you can already see. If the team has added their own house code there, that outranks everything, including this skill.

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

**A request to review is not a request to repair.** Asked to review, check, or "tell me what you find", report each finding with its location, rule id and the fix you would make — and leave the files as they are. Edit only when the user asks for fixes, or after asking whether they want them. A PLC project is often about to go onto a machine; changes nobody asked for are changes nobody re-tested.

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
| 2. **Headless build** via the Automation Interface on a Windows PC with XAE — `scripts/xae_build.ps1` | Full compiler errors |
| 3. **`scripts/st_review.py` + a human read** | Known defect patterns absent — **always do this** |
| 4. Nothing | Then say "unverified, not compiled" plainly |

There is deliberately no Linux syntax-check rung. `matiec` and `rusty` cannot parse the OOP constructs this dialect is built on, so a clean run there would prove almost nothing while looking like a pass.

Close with: what you wrote and which shape it uses · what was verified and what was not · the assumptions you made about I/O, cycle time and fault behaviour · what the human must do next.

**End every hand-over that contains code with this line, word for word, even for a one-line change:**

> Not compiled. A qualified engineer must review and validate this code against the drive and platform documentation before it runs on a machine.

"Not compiled" alone is not enough, and neither is "review it before it goes on the machine". In a field test, 8 of 8 hand-overs said the first and only 1 of 8 said the second in full.

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
| `references/twincat/xae-automation.md` | Asked for a build or compile check, and XAE is installed. What a build rewrites, and why activation stays manual. |

**Routing rule of thumb:** if the answer names a `Tc2_`/`Tc3_` library, a `.TcPOU` file, ADS or XAE, it is TwinCAT-specific and belongs behind `references/twincat.md`, not in a general answer.

## Tools

| Path | For |
|---|---|
| `scripts/st_review.py` | The reviewer. Run it on every change. |
| `scripts/tcpou.py` | Read and edit real `.TcPOU` files without disturbing GUIDs, `<LineIds>`, the BOM or CRLF. `new` scaffolds an object, `add-method`/`add-property` append an empty member to fill in with `set`, `reguid` re-stamps Ids after copying a file, `register` adds it to the `.plcproj`. `pins` lists FBD/LD wiring, `code-equal` proves an edit touched only comments. |
| `scripts/xae_build.ps1` | Windows with XAE only: build the solution in a hidden XAE and print the real compiler output. Run it only when the user asked for a build; it rewrites `.tmc`/`.xti`/`_CompileInfo`. It never activates — rule 2 still holds. See `references/twincat/xae-automation.md`. |
| `templates/` | Known-good skeletons — sequence FB, state enum, TcUnit suite. |
| `examples/` | Real working code from two published projects, each with its `LICENSE` and a `NOTES.md` on what to take from it. Read these before writing. House code added here outranks every convention in this skill. |

The two Python scripts need Python 3 and nothing else — standard library, no `pip install`. Commands are written `py -3` for Windows; on Linux or macOS use `python3`.

### `tcpou.py`

Editing a `.TcPOU` as plain text is how you corrupt a project. Every subcommand:

```bash
py -3 scripts/tcpou.py show     <file>                                   # parts + encoding
py -3 scripts/tcpou.py get      <file> --part impl [--out body.st]       # print or write one part
py -3 scripts/tcpou.py pins     <file> [--pin REGEX] [--box REGEX]       # FBD/LD box wiring
py -3 scripts/tcpou.py set      <file> --part impl --from-file body.st   # replace one part
py -3 scripts/tcpou.py new      --type fb --name FB_Filling --dir POUs/  # scaffold
py -3 scripts/tcpou.py register <PLC.plcproj> <file>...                  # make it compile
py -3 scripts/tcpou.py reguid   <file>...                                # re-stamp Ids
py -3 scripts/tcpou.py check    <file>...                                # validate
py -3 scripts/tcpou.py code-equal <file>... [--ref REV | --against FILE] # comments-only?
```

- `new` takes a **`--name`, not a path**, and picks the extension itself (`.TcPOU`/`.TcDUT`/`.TcGVL`). `--type` is one of `fb`, `prg`, `fun`, `dut`, `gvl`; `fb` also takes `--extends`, `--implements` and `--shape`.
- **`--shape` picks which interface family the FB gets:** `execute` (the default) declares `bExecute`/`bBusy`/`bDone`, `enable` declares `bEnable`/`bValid`, and `cyclic` declares no command interface at all. Choose the one the block actually is — `Execute` pairs with `Done`, `Enable` pairs with `Valid`, and mixing the two is what rule `X9` reports. `references/behaviour-model.md` is the decision. An FB that **inherits** its command interface from a framework base — the common case in a module-based project — fits none of the three on its own: use `--shape cyclic --extends FB_YourBase`, which gives the `EXTENDS` and adds no pins of its own to clash with the base's.
- `set` reads stdin when `--from-file` is omitted. **From Windows PowerShell 5.1, move a part with `get --out body.st` and `set --from-file body.st`, never with `>` or a pipe.** `>` is `Out-File`: it decodes the script's UTF-8 through the console code page before writing UTF-16, so `²` lands in the file as `┬▓` and no reader can repair it. A pipe (`Get-Content body.st | set`) re-encodes each character to the console code page: a BOM-less file arrives with `²` as `??`, with `-Encoding UTF8` as `?`; lost either way. (cmd.exe's `>` and `type |` are fine.) `--from-file` and stdin take UTF-8 with or without a BOM and UTF-16 with one; anything else is refused in one line. One trailing line break more than the part already has, which a pipe or an editor appends, is dropped so a round trip leaves no diff. Files and output are UTF-8 whatever the console's code page.
- Part keys come from `show`: `decl`, `impl`, `Reset:impl`, `ActualValue.Get:impl`.
- **`pins` before concluding a signal is unused or unwired in an FBD or LD caller.** Which variable feeds which pin of a box is stored in the network XML, so a text search for `ibEmpty :=` finds nothing there. `pins` prints every box's inputs (`<-`, with operators as `OR(a, b)`, a negated operand as `NOT x`, an empty pin as `(unwired)` and, in LD, the rung input as `(rung: left rail, TRUE)`) and its wired outputs (`->`), each box tagged with the method its network lives in, `[MotionCycle]`. Coil rungs and conditional RETURN rungs have no box and are listed as `(coil) var <- AND(a, NOT b)` and `(return) <- NOT x`; `--pin var` finds the coil. It is read-only; the layout it reads was checked on 4024 LD networks and one FBD network drawn in XAE, against XAE's PLCopen export and in the editor. CFC is not supported: on a `<CFC>` body `pins` refuses with exit 2 rather than print an empty list, and nothing here reads a CFC box.
- **Claim "comments only" with `code-equal`, not by eye.** It compares every source part with the same part at `--ref` (default `HEAD`) or in `--against` another file, after dropping comments and insignificant whitespace; string literals count as code. Exit 0 = IDENTICAL, 1 = the code changed (it prints the first difference per part), 2 = nothing to compare with. It reads the CDATA source only, not the XML around it.

**Run `show` before `get`/`set` rather than guessing a part key.** A wrong key exits 1 and prints the real ones — but if you then verify your own edit by hashing the file, a `set` that never ran looks exactly like a `set` that changed nothing. Check the exit status, not just the bytes.

**A new file that is not registered in the `.plcproj` silently does not compile.** `tcpou.py register` is not optional; it is idempotent, so running it twice is safe.

## Adding material to this skill

Files from permissively-licensed sources (MIT, 0BSD, BSD-2, Apache-2) can be copied in — record them in `ATTRIBUTIONS.md` in the same commit. Anything else, including vendor documentation and standards, gets read and restated rather than pasted; vendoring a GPL file would relicense the whole skill.

`ATTRIBUTIONS.md` lists what this was built from and what each source contributed.
