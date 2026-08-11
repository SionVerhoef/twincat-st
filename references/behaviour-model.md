# The PLCopen behaviour model — designing a function block interface

Before writing an FB that *does something over time*, decide which of two interface families it belongs to. PLCopen standardised both in *Creating PLCopen Compliant Function Block Libraries* (v1.0, 2017), and every `MC_*` motion block, every communication block and most vendor library blocks follow one of them.

Getting this right is why a block composes with the rest of the system instead of needing a wrapper.

## The two families

|  | **Edge-triggered** | **Level-controlled** |
|---|---|---|
| Start input | `Execute` — acts on the **rising edge** | `Enable` — acts while **held true** |
| Completion output | `Done` | `Valid` |
| Means | "Do this once, tell me when it's finished" | "Keep doing this for as long as I ask" |
| Typical use | Move to position, write a file, send a message | Power on a drive, run a controller, publish a reading |

**The pairing is part of the contract**: `Execute` pairs with `Done`, `Enable` pairs with `Valid`. An FB with `Execute` and `Valid` will confuse every reader who knows the convention, and they are your colleagues.

## The rule that decides it

There is one hard constraint, and it is not obvious:

> **Detecting a rising edge inside a function block costs two PLC cycles.** So if the requirement is to accept a new value *every* cycle, an edge-triggered interface cannot do it. Use a level-controlled one.

That single fact settles most of the design arguments. A block that processes a stream of samples, runs a control loop, or must react within one scan is level-controlled. A block that performs a discrete operation with a beginning and an end is edge-triggered.

## Edge-triggered: the state set

PLCopen names the states, and using their names makes your block legible to anyone who has read a motion manual:

```
Dormant  ──Execute↑──▶  Executing  ──▶  Done  ──▶  Resetting  ──▶  Dormant
                             │
                             └──────────▶  Error  ──▶  Resetting
```

The minimal interface:

```pascal
FUNCTION_BLOCK FB_DoSomething
VAR_INPUT
    bExecute    : BOOL;         // rising edge starts the operation
END_VAR
VAR_OUTPUT
    bDone       : BOOL;         // completed successfully
    bBusy       : BOOL;         // accepted and in progress
    bError      : BOOL;
    nErrorID    : UDINT;
END_VAR
```

Behaviour the caller is entitled to assume:

- `bBusy` goes true on the accepted rising edge and stays true until `bDone` or `bError`.
- `bDone` and `bError` are mutually exclusive, and both are **latched until `bExecute` goes false** — that is what lets a caller see a result it would otherwise miss between scans.
- Dropping `bExecute` while busy does **not** abort the operation; it only arranges for the outputs to clear when it finishes.

### Adding abort

If an operation can be cancelled, the standard extension adds `Aborting` and `Aborted` states and a `CommandAborted` output. In motion this is the one people forget: a second move on the same axis supersedes the first, and the first block reports `CommandAborted`, not `Error`. **An unhandled `CommandAborted` looks exactly like "the machine randomly stopped mid-move".**

### Adding timers

Two distinct timeout concepts, both from the spec, and they solve different problems:

| Input | Meaning |
|---|---|
| `udiTimeOut` | Total time the operation may stay busy. Exceeded → `Error`. This is the one that stops a dead sensor hanging a sequence forever. |
| `udiTimeLimit` | Time this block may consume **per invocation**. Lets a long job be spread over several cycles without overrunning the task. |

`TimeLimit` is the sanctioned answer to "this work does not fit in one scan": do a slice, return, continue next cycle. It is a much better answer than a loop, and it is the part of the spec people miss.

## Level-controlled: the state set

```
Disabled  ──Enable──▶  Enabling  ──▶  Enabled/Valid  ──Enable false──▶  Disabling
                            │
                            └────────▶  Error
```

```pascal
FUNCTION_BLOCK FB_Measure
VAR_INPUT
    bEnable     : BOOL;         // run while true
END_VAR
VAR_OUTPUT
    bValid      : BOOL;         // output data is currently meaningful
    bBusy       : BOOL;
    bError      : BOOL;
    nErrorID    : UDINT;
    fValue      : LREAL;        // degC
END_VAR
```

`bValid` is a statement about the *data*, not the operation: it says "the value you are reading right now is good". A caller that reads `fValue` without checking `bValid` is reading a stale or meaningless number, which is the level-controlled equivalent of ignoring an error.

The spec also defines **continuous** variants (`LConC`) for behaviour that never completes — a controller that simply runs while enabled and has no `Done` state at all.

## Error handling is part of the contract

PLCopen coding rule **CP7** requires that error information a block returns is actually tested. In this interface family that means:

```pascal
fbMove(Axis := stAxis, Execute := bStart,
       Done => bDone, Busy => bBusy,
       CommandAborted => bAborted,
       Error => bErr, ErrorID => nErrID);

IF bErr THEN
    nErrorID := nErrID;          // propagate, don't swallow
    eState   := E_Seq.Error;
ELSIF bAborted THEN
    eState   := E_Seq.Aborted;   // NOT the same as an error
END_IF
```

Two habits worth keeping:

- **Propagate the underlying `ErrorID`** rather than replacing it with your own generic code. The person debugging at 03:00 needs the drive's number, not yours.
- **Namespace your own error ids** as hex constants with documented meanings (`16#8101`), collected in one enum or GVL so the HMI and the operator share one list.

## Applying it

When you write an FB that acts over time, work through this:

1. Does it need to accept new data every cycle? → level-controlled. Otherwise edge-triggered.
2. Can it be cancelled or superseded? → add abort, and make callers handle `CommandAborted` separately from `Error`.
3. Can it hang waiting on the physical world? → add `TimeOut`. Nearly always yes.
4. Can its work exceed one scan? → add `TimeLimit` and slice it, rather than looping.
5. Does it report `Error` **and** `ErrorID`, and does the caller read both? (CP7)

`templates/FB_Sequence.TcPOU` implements the edge-triggered shape with a timeout and a reachable, resettable error state — start there rather than from a blank file.
