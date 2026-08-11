# Cyclic execution rules

**Read this before writing or reviewing any Structured Text.** These are the rules that separate PLC code from ordinary programs. Breaking them produces code that compiles cleanly, reads correctly, and misbehaves on the machine — which is the failure mode a language reference cannot help with.

Each rule maps to an `X` id in `scripts/st_review.py`, so the mechanical part is checkable. The judgement part is not, and that is what the rubric at the end is for.

## The mental model

A PLC task is a function called forever, on a fixed period:

```
every cycle (say every 10 ms, forever):
    1. copy physical inputs  -> input process image
    2. run the whole program ONCE, top to bottom
    3. copy output process image -> physical outputs
```

Four consequences, from which everything below follows:

- **The program must return before the cycle time expires.** Overrun trips the watchdog and stops the PLC. There is no wait, no sleep, no retry-until.
- **State lives in variables between cycles, never in execution position.** A local `VAR` in a function block persists; where you were in the code does not. You cannot pause mid-routine.
- **Inputs are sampled once per cycle.** A pulse shorter than the cycle time can be invisible. Reading an input twice in one scan gives the same value twice.
- **Outputs are applied once per cycle, at the end.** Writing an output and reading it back in the same scan reads your own write, not the physical world.

---

## Rule 1 — Never block. Use a state machine. `X1`

The single most common failure in model-written PLC code.

**Wrong** — halts the task, trips the watchdog, stops the machine:

```pascal
bValveOpen := TRUE;
WHILE NOT bValveConfirmed DO       // cannot terminate within this scan
    ;
END_WHILE
bPumpStart := TRUE;
```

**Right** — one step per scan, and every wait has a timeout:

```pascal
CASE eState OF

    E_Seq.Idle:
        IF bStart THEN
            bValveOpen := TRUE;
            fbStateTimer(IN := FALSE);          // reset before entering the wait
            eState     := E_Seq.WaitValve;
        END_IF

    E_Seq.WaitValve:
        fbStateTimer(IN := TRUE, PT := T#3S);
        IF bValveConfirmed THEN
            bPumpStart := TRUE;
            eState     := E_Seq.Running;
        ELSIF fbStateTimer.Q THEN               // every wait needs this branch
            nErrorID := 16#8001;                // valve confirm timeout
            eState   := E_Seq.Error;
        END_IF

    E_Seq.Running:
        IF NOT bStart THEN
            eState := E_Seq.Stopping;
        END_IF

    E_Seq.Error:
        bValveOpen := FALSE;                    // define the safe output state
        bPumpStart := FALSE;
        IF bReset THEN
            nErrorID := 0;
            eState   := E_Seq.Idle;             // Error must be escapable
        END_IF

ELSE
    eState := E_Seq.Error;                      // unknown state is a fault
END_CASE
```

**Rule of thumb:** the words *wait*, *until*, *retry*, *poll* or *sleep* in a requirement mean state machine, never loop.

A bounded `WHILE` over data you control can be legitimate. Prove the bound, then record the proof where the next reader will see it:

```pascal
WHILE pNode <> 0 DO   // lint:allow X1 list built at init, hard max 64 entries
```

## Rule 2 — Keep calling a block while its operation is in flight. `CP20`

A function block instance is a state machine that only advances when you call it. A PLCopen-style block — motion `MC_*`, communications, file access — that stops being called mid-operation never finishes, never times out and never reports an error. The machine simply stops, with no diagnostic.

**Wrong** — `Busy` never clears, `Done` never arrives:

```pascal
IF bStartMove THEN
    fbMoveAbs(Axis := stAxis, Execute := TRUE, Position := 100.0, Velocity := 50.0);
END_IF
```

**Right** — the call site is unconditional; `Execute` is the control:

```pascal
fbMoveAbs(
    Axis     := stAxis,
    Execute  := bStartMove,      // the input is the control, not the call site
    Position := fTargetPos,      // mm
    Velocity := fSpeed,          // mm/s
    Done     => bMoveDone,
    Busy     => bMoveBusy,
    Error    => bMoveError,
    ErrorID  => nMoveErrorID);

IF bMoveError THEN
    eState := E_Seq.Error;
END_IF
```

**`Execute` is edge-triggered.** It must go `FALSE` before the block will start again:

```pascal
IF bMoveDone OR bMoveError THEN
    bStartMove := FALSE;
END_IF
```

**Be precise about what this rule is not.** PLCopen CP20 says an instance should be invoked *at most once per cycle*, and explicitly allows a conditional call. So "call every function block unconditionally, always" is too strong — a stateless helper invoked in one branch of a `CASE` is fine. The rule is narrower and sharper: **while an operation is pending, the block must keep being called.** Practically, put such calls outside the `CASE`, drive them with their inputs, and read their outputs inside it.

**Never share one instance between two concurrent operations** — the second call overwrites the first's inputs in the same scan. One instance per concurrent operation; for N devices use an array of instances and a bounded `FOR`.

Choosing between an `Execute` interface and an `Enable` interface is a design decision with a non-obvious constraint behind it — see `behaviour-model.md`.

## Rule 3 — Every loop needs a compile-time bound. `X1`

`FOR` over a fixed array is fine. `WHILE`/`REPEAT` whose exit depends on process data is not.

```pascal
// WRONG — nIdx can run past the array, and the loop may never exit
WHILE aBuffer[nIdx] <> 0 DO
    nIdx := nIdx + 1;
END_WHILE

// RIGHT — constant bound, always terminates
FOR nIdx := 0 TO GVL.cBufferMax DO
    IF aBuffer[nIdx] = 0 THEN
        EXIT;
    END_IF
END_FOR
```

Watch total work as well as termination: 10,000 iterations of floating-point maths will not fit a 1 ms task. Heavy work belongs in a slower task, or spread across cycles — process N items per scan.

## Rule 4 — Detect edges explicitly. `X-`

A signal is observed once per cycle. If it can change faster than the cycle time the PLC will miss it — a task-design problem, not something code can fix.

```pascal
VAR
    fbStartTrig : R_TRIG;
END_VAR

fbStartTrig(CLK := bStartButton);      // called cyclically, like any FB
IF fbStartTrig.Q THEN                  // TRUE for exactly one cycle
    nCycleCount := nCycleCount + 1;
END_IF
```

Using a level where you meant an edge re-triggers every scan the button is held — hundreds of times.

## Rule 5 — Timers are instances: called cyclically, reset explicitly. `X2`

`TON` accumulates only while called with `IN := TRUE`. Two traps.

```pascal
// WRONG — only called inside the state, so it never resets between entries;
// on re-entry it can already be elapsed and fire immediately.
E_Seq.WaitValve:
    fbTimer(IN := TRUE, PT := T#3S);
```

Reset on the transition *into* the wait (`fbTimer(IN := FALSE);`), as in Rule 1. Sharing one timer instance across several states is a bug — give each wait its own, or reset on every state change.

**`PT` takes a `TIME` literal, not a number.** `T#500MS`, `T#3S`, `T#1M30S`. `PT := 500` does not compile; `PT := DINT_TO_TIME(nMillis)` is how you make it configurable.

## Rule 6 — Guard arithmetic; never compare floats for equality. `CP8`, `CP28`, `X4`

```pascal
// WRONG
IF fActualPos = fTargetPos THEN ...         // essentially never TRUE
fRatio := fNumerator / fDenominator;         // divide-by-zero faults the runtime

// RIGHT
IF ABS(fActualPos - fTargetPos) <= cPosTolerance THEN ...   // tolerance in mm
IF fDenominator <> 0.0 THEN
    fRatio := fNumerator / fDenominator;
ELSE
    eState := E_Seq.Error;
END_IF
```

The same applies to `TIME` (CP28): a scan steps over an exact value rather than landing on it, so use `>=`.

Pick integer widths for the real range — `DINT`, not `INT`, for anything that can pass 32,767, because counters overflow silently — and convert explicitly rather than relying on promotion.

## Rule 7 — Bounds-check every computed index.

An out-of-range index is an unchecked memory access. Depending on configuration it either faults the runtime or silently corrupts adjacent variables. The second is far worse, and is the one you get by default in many builds.

```pascal
IF nIdx >= 0 AND nIdx <= GVL.cMaxStations THEN
    aStations[nIdx].bActive := TRUE;
ELSE
    eState := E_Seq.Error;
END_IF
```

## Rule 8 — No allocation, no recursion, validate every pointer. `E1`, `E3`, `X5`, `X6`

Deterministic execution means everything is allocated at download. No `__NEW`/`__DELETE` in cyclic code, no recursive function blocks, no unbounded string building. Fixed arrays and `STRING(n)` are the idiom — and `STRING` defaults to 80 characters plus terminator, so declare the length you need.

Pointers and references are valid and are the main source of runtime crashes:

```pascal
IF pData <> 0 THEN
    pData^.nValue := 42;
END_IF

IF __ISVALIDREF(refAxis) THEN
    refAxis.bEnable := TRUE;
END_IF
```

**A pointer stored across cycles can dangle after an online change.** Re-take it; do not cache it. Only `=` and `<>` are defined on pointers — ordering comparisons rely on undocumented memory layout (E3).

## Rule 9 — Know what survives a restart.

| Declaration | Warm reset | Power cycle | New download |
|---|---|---|---|
| `VAR` | no | no | no |
| `VAR RETAIN` | yes | yes | no |
| `VAR PERSISTENT` | yes | yes | yes, if written to the persistent file on shutdown |

Initial values (`nCount : DINT := 5;`) apply on download and cold reset — **not** every cycle, and **not** on a warm start. Code relying on a variable "starting at zero" after a restart is wrong; initialise it in an init state.

`PERSISTENT` data is written on controlled shutdown. An unexpected power loss can lose it: treat it as best-effort, and never let machine behaviour that matters depend on it silently.

## Rule 10 — Respect the process image and task boundaries. `CP12`, `CP15`

- Reading back an output you just wrote gives your own value, not the field state. To confirm an actuator moved, read its **input** feedback, and allow a cycle plus the device's physical response time.
- Variables shared between tasks of different priority can be read mid-update. Transfer multi-word data across a task boundary as one structure under a handshake flag, not field by field.
- Write each physical output once per cycle, in one place (CP12).
- Work must fit the cycle. File I/O, string parsing and large maths belong in a slower task.

---

## Review rubric

`scripts/st_review.py` covers the mechanical rows. These are the ones that need you.

```
[ ]  1. Sequences are state machines, not loops; every wait has a timeout
        and a path to Error                                             (X1, X3)
[ ]  2. Blocks with pending operations keep being called while Busy;
        Execute edges are dropped on Done/Error; no instance shared
        between two concurrent operations                               (CP20)
[ ]  3. Every loop is bounded, and the total work fits the cycle time    (X1)
[ ]  4. Edges via R_TRIG/F_TRIG wherever a one-shot was intended
[ ]  5. Timers are per-wait instances, reset on entry, PT a TIME literal (X2)
[ ]  6. No float or TIME equality; division guarded; integer widths fit  (CP8, CP28, X4)
[ ]  7. Every computed array index is bounds-checked
[ ]  8. No allocation or recursion; pointers and references validated    (E1, E3, X5, X6)
[ ]  9. RETAIN/PERSISTENT chosen deliberately; no reliance on implicit
        initialisation after a warm start
[ ] 10. Outputs written once per cycle; cross-task data transferred
        coherently; no output read-back used as feedback                (CP12, CP15)
[ ] 11. Error state is reachable, reports an id, defines safe outputs,
        and can be reset                                                (X7)
[ ] 12. Error/status outputs of called blocks are actually read          (CP7)
[ ] 13. The cycle time and fault behaviour were stated, not assumed
[ ] 14. Nothing here is a safety function                     (-> safety-boundary.md)
```

The last two rows are the ones a tool will never reach, and they are where the expensive mistakes live.
