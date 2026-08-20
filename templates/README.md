# Templates

Known-good TwinCAT 3 (4024) object files. All are UTF-8 with BOM and CRLF, carry valid GUIDs, and pass `scripts/tcpou.py check`.

| File | What it is |
|---|---|
| `FB_Sequence.TcPOU` | **The workhorse.** PLCopen-style command interface (`bExecute` / `bBusy` / `bDone` / `bError` / `nErrorID`) over a `CASE` state machine, with a per-step timeout, a private transition method that resets the timer, and a resettable error state. Each step's done-condition is an **input** (`bStep1Done`, `bStep2Done`) rather than a hardwired expression — that is what lets a test hold a step open and watch it fault. Copy this shape for anything with steps or waiting. |
| `E_SeqState.TcDUT` | The state enum `FB_Sequence` uses — qualified-only, explicit values, gaps left for inserting states. |
| `FB_ExampleTestSuite.TcPOU` | TcUnit suite skeleton showing how to drive an FB across multiple cycles in a test. Two fixtures, driven with different step conditions, so the completion path and the timeout path are both actually reachable. Requires the TcUnit library. |

## Using them

Copy, rename, then edit through the script so the XML stays intact:

```bash
cp templates/FB_Sequence.TcPOU MyProject/PLC/POUs/FB_Filling.TcPOU

# rename the object inside the file (the POU Name attribute and the declaration)
sed -i 's/FB_Sequence/FB_Filling/g' MyProject/PLC/POUs/FB_Filling.TcPOU

# REQUIRED - the copy still carries the template's Id GUIDs, and TwinCAT
# identifies objects by Id. Two objects sharing one is a real conflict and
# nothing warns you.
python3 scripts/tcpou.py reguid MyProject/PLC/POUs/FB_Filling.TcPOU

# validate structure and encoding
python3 scripts/tcpou.py check MyProject/PLC/POUs/FB_Filling.TcPOU

# edit the implementation
python3 scripts/tcpou.py get MyProject/PLC/POUs/FB_Filling.TcPOU --part impl > /tmp/body.st
$EDITOR /tmp/body.st
python3 scripts/tcpou.py set MyProject/PLC/POUs/FB_Filling.TcPOU --part impl --from-file /tmp/body.st

# REQUIRED - a file not in the .plcproj is silently not compiled
python3 scripts/tcpou.py register MyProject/PLC/PLC.plcproj MyProject/PLC/POUs/FB_Filling.TcPOU

# then review what you wrote
python3 scripts/st_review.py MyProject/PLC/POUs/FB_Filling.TcPOU
```

**Copying a template duplicates its GUID.** For a new object, prefer `tcpou.py new` (which generates a fresh one) and paste the template body in, or replace the `Id="{...}"` value by hand before adding the file to a project that already contains the original.

## What the templates deliberately show

Every one of these is a worked example of the rules in `references/cyclic-execution-rules.md`:

- FB instances (`R_TRIG`, `TON`) declared once and called every cycle — Rule 2, Rule 5
- Timer reset on state entry, not in the waiting state — Rule 5
- A timeout and an error path on every wait — Rule 1
- An `ELSE` on the `CASE` catching impossible states
- Error IDs as named hex constants, not magic numbers
- An escape from `Error` via `bReset`, handled outside the `CASE` so it works from any state

The `IF TRUE THEN // <- replace with the real condition` markers are intentional: they are the two places a real step condition must go, and they will not compile into anything meaningful if left alone.

All three templates pass `scripts/st_review.py` with no high or medium findings. The two `low` CP20 notes it does report — a timer called from more than one branch — are the documented mutually-exclusive-branch case: the branches cannot both run in one scan. That is exactly the judgement CP20 asks a reader to make, which is why the reviewer reports it rather than staying silent, and why it reports it at low severity rather than as a defect.
