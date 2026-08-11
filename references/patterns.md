# Patterns — state machines, sequences and project structure

How to shape a machine program above the level of individual statements.

## The state machine, done properly

`CASE` on an enum is the workhorse of PLC code. What separates a good one from a fragile one is not the `CASE` — it is the five things around it.

```pascal
{attribute 'qualified_only'}
TYPE E_SeqState :
(
    Idle      := 0,
    Starting  := 10,
    Running   := 20,
    Stopping  := 30,
    Error     := 90         // leave gaps: inserting a step later shouldn't renumber
) DINT;
END_TYPE
```

Numbering in tens is a small thing that pays off: states show up as numbers on an HMI and in logs, and you will want to insert `Homing := 15` without shifting everything below it.

The five requirements:

1. **Every state has an exit condition.** A state you can enter and not leave is a hung machine.
2. **Every wait has a timeout**, and the timeout leads to `Error` with a distinct `nErrorID`. This is the difference between "the machine stopped" and "valve 3 did not confirm within 3 s".
3. **The timer is reset on the transition in**, not inside the waiting state — see `cyclic-execution-rules.md` Rule 5.
4. **`Error` defines safe outputs and is resettable.** An error state with no way out is an unplanned power cycle.
5. **`ELSE` is present** and treats an unknown value as a fault. Memory corruption and a newly-added enum member both land here.

### Entry and exit actions

Once a state needs setup, the flat form starts to hide bugs. Detect the transition explicitly:

```pascal
VAR
    eState     : E_SeqState;
    eStatePrev : E_SeqState;
    bEntry     : BOOL;
END_VAR

bEntry     := (eState <> eStatePrev);
eStatePrev := eState;

CASE eState OF
    E_SeqState.Starting:
        IF bEntry THEN
            fbTimer(IN := FALSE);        // one-shot setup, guaranteed once
            bDriveEnable := TRUE;
        END_IF
        fbTimer(IN := TRUE, PT := cStartTimeout);
        ...
END_CASE
```

This makes "reset the timer on entry" structural rather than something you have to remember at every transition site.

### Where the FB calls go

Blocks with pending operations are called **outside** the `CASE`, unconditionally, and the `CASE` only reads their outputs and sets their inputs. That satisfies both PLCopen CP20 (one invocation per cycle) and the requirement that a busy block keeps being serviced:

```pascal
// --- call the machinery once, every scan --------------------------
fbMoveAbs(Axis := stAxis, Execute := bReqMove,
          Position := fReqPos, Velocity := fReqVel,
          Done => bMoveDone, Busy => bMoveBusy,
          CommandAborted => bMoveAborted,
          Error => bMoveError, ErrorID => nMoveErrorID);

// --- decide what it should be doing -------------------------------
CASE eState OF
    E_SeqState.Running:
        bReqMove := TRUE;
        IF bMoveDone THEN
            bReqMove := FALSE;
            eState   := E_SeqState.Stopping;
        ELSIF bMoveError OR bMoveAborted THEN
            nErrorID := nMoveErrorID;
            eState   := E_SeqState.Error;
        END_IF
END_CASE
```

This layout is worth adopting as a habit. It is very hard to write the classic "block frozen mid-operation" bug when the calls physically sit outside the branch structure.

## Sub-sequences

When a sequence outgrows one `CASE`, do not nest `CASE` inside `CASE` — it becomes unreadable and untestable fast. Give the sub-sequence its own function block with an `Execute`/`Done` interface (see `behaviour-model.md`) and call it from a single parent state. The parent then reads as a list of steps, and each step is independently testable.

## PackML / ISA-88 for whole machines

For a machine rather than a single sequence, don't invent a state model — use PackML (OMAC), which PLCopen maps to IEC 61131-3 and which Beckhoff's own reference architecture implements.

The state set divides into three kinds:

| Kind | States | Behaviour |
|---|---|---|
| **Acting** (transient) | `Resetting`, `Starting`, `Completing`, `Suspending`, `Unsuspending`, `Holding`, `Unholding`, `Aborting`, `Clearing`, `Stopping` | Run to completion, then advance automatically on *state complete* |
| **Wait** (stable) | `Stopped`, `Idle`, `Complete`, `Held`, `Suspended`, `Aborted` | Hold until something commands a change |
| **Dual** | `Execute` | The producing state |

The normal path: power on lands in `Stopped`; `Reset` → `Resetting` → `Idle`; `Start` → `Starting` → `Execute`; when the order finishes, `Completing` → `Complete`.

Two loops hang off `Execute` — `Held` (the operator holds production) and `Suspended` (waiting for material) — and both return to it. Every state can leave via **Stop** (operator) or **Abort** (error). That last point is the one worth copying even if you never adopt PackML wholesale: *error handling is a transition available from every state*, not something bolted onto a few of them.

PLCopen documents both **centralised** error handling (all states route to one error step) and **de-centralised** (each step has its own error path). Centralised is simpler and usually right; de-centralised earns its cost when different steps need genuinely different recovery.

Machines also carry a **unit mode** — `Auto`, `SemiAuto`, `Manual`, `Maintenance` — orthogonal to the state. Beckhoff's sample models this with a mode manager owning the state machine, which keeps mode-specific behaviour out of the state logic itself.

## Structuring a machine project

Beckhoff's OOP Extended sample organises a real machine into layers, and it generalises well:

```
01_Submodules     individual devices — cylinder, sensor, drive
02_Subsystems     assemblies of devices that act together — a station
03_Machine        the machine: mode manager, PackML state, orchestration
04_Application    the specific installation, recipes, plant-specific glue
05_Visu           HMI
```

The rule that makes it work is **dependencies point downward only.** A submodule never knows about the machine. That is what lets you test a station without the plant, and reuse a cylinder FB on the next project.

Two habits that follow:

- **Devices get an FB; sequences get an FB.** The device knows how to actuate; the sequence knows the order. Mixed together, neither can be tested.
- **`MAIN` is a wiring diagram**, calling top-level FBs in a defined order and containing no logic of its own.

## Managing N devices

```pascal
VAR CONSTANT
    cMaxStations : DINT := 8;
END_VAR
VAR
    aStations : ARRAY[1..cMaxStations] OF FB_Station;
    nIdx      : DINT;
END_VAR

FOR nIdx := 1 TO cMaxStations DO        // compile-time bound
    aStations[nIdx](bEnable := bSystemReady);
END_FOR
```

Each instance carries its own state, the loop bound is constant, and adding a station is a constant change rather than a code change. Bounds-check any index that does not come from the loop itself.

## Errors and diagnostics

- **Namespace error ids** as hex constants with documented meanings (`16#8101`), collected in one enum or GVL so code, HMI and operators share one list.
- **Propagate the underlying id** from a failing block rather than replacing it with a generic one. The person debugging needs the drive's error number.
- **Record what failed and when**, not just that something did. A latched `sLastError` with a timestamp costs almost nothing and saves a site visit.
- **Distinguish `Error` from `CommandAborted`.** Different causes, different recovery.
