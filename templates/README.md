# Templates

Known-good TwinCAT 3 (4024) object files. All are UTF-8 with BOM and CRLF, carry valid GUIDs, and pass `scripts/tcpou.py check`.

| File | What it is |
|---|---|
| `FB_Sequence.TcPOU` | **The workhorse.** PLCopen-style command interface (`bExecute` / `bBusy` / `bDone` / `bError` / `nErrorID`) over a `CASE` state machine, with a per-step timeout and a resettable error state. The edge detector and the step timer are called **once, unconditionally, above the `CASE`** — the state machine picks the timer's inputs, never whether it runs, and the timer re-arms on the scan the state changes. Calling a timer inside the branch that reads it is the shape `references/cyclic-execution-rules.md` Rule 5 prints as wrong. Each step's done-condition is an **input** (`bStep1Done`, `bStep2Done`) rather than a hardwired expression — that is what lets a test hold a step open and watch it fault. Copy this shape for anything with steps or waiting. |
| `E_SeqState.TcDUT` | The state enum `FB_Sequence` uses — qualified-only, explicit values, gaps left for inserting states. |
| `FB_ExampleTestSuite.TcPOU` | TcUnit suite skeleton showing how to drive an FB across multiple cycles in a test. Two fixtures, driven with different step conditions, so the completion path and the timeout path are both actually reachable. Requires the TcUnit library. |

## Using them

Scaffold a new object with `tcpou.py new`, which gives it a fresh GUID, then move the template's
parts into it. Never copy the file: a copy keeps the template's GUIDs, and TwinCAT identifies
objects by GUID. Use `get --out` and `set --from-file` rather than `>` or a pipe, which corrupt
non-ASCII characters in Windows PowerShell 5.1.

```bash
py -3 scripts/tcpou.py new --type fb --name FB_Filling --dir MyProject/PLC/POUs/
py -3 scripts/tcpou.py add-method MyProject/PLC/POUs/FB_Filling.TcPOU --name M_Fail --access PRIVATE

# for each part - decl, impl, M_Fail:decl, M_Fail:impl
py -3 scripts/tcpou.py get templates/FB_Sequence.TcPOU --part decl --out decl.st
#   edit decl.st: FUNCTION_BLOCK FB_Sequence -> FUNCTION_BLOCK FB_Filling, then fill in the steps
py -3 scripts/tcpou.py set MyProject/PLC/POUs/FB_Filling.TcPOU --part decl --from-file decl.st

# the state enum the same way, if the project does not have it yet
py -3 scripts/tcpou.py new --type dut --name E_SeqState --dir MyProject/PLC/DUTs/
py -3 scripts/tcpou.py get templates/E_SeqState.TcDUT --part decl --out enum.st
py -3 scripts/tcpou.py set MyProject/PLC/DUTs/E_SeqState.TcDUT --part decl --from-file enum.st

# REQUIRED - a file not in the .plcproj is silently not compiled
py -3 scripts/tcpou.py register MyProject/PLC/PLC.plcproj MyProject/PLC/POUs/FB_Filling.TcPOU MyProject/PLC/DUTs/E_SeqState.TcDUT

# validate, then review what you wrote
py -3 scripts/tcpou.py check MyProject/PLC/POUs/FB_Filling.TcPOU
py -3 scripts/st_review.py MyProject/PLC/POUs/FB_Filling.TcPOU
```

If a file was copied anyway, `tcpou.py reguid <file>` gives every object in it a fresh GUID.

## What the templates deliberately show

Every one of these is a worked example of the rules in `references/cyclic-execution-rules.md`:

- FB instances (`R_TRIG`, `TON`) declared once and called every cycle — Rule 2, Rule 5
- Timer reset on state entry, not in the waiting state — Rule 5
- A timeout and an error path on every wait — Rule 1
- An `ELSE` on the `CASE` catching impossible states
- Error IDs as named hex constants, not magic numbers
- An escape from `Error` via `bReset`, handled outside the `CASE` so it works from any state

The step conditions are inputs, `bStep1Done` and `bStep2Done`, marked `// wire this input to the real step-N signal`. Left unwired they stay `FALSE`, so the step never completes and the sequence faults on its timeout instead of running on.

All three templates pass `scripts/st_review.py` with no findings. CI fails the build if one ever reports a high-severity finding.
