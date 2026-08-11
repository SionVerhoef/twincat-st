# Structured Text — the CODESYS V3 dialect

IEC 61131-3 ST as implemented across the CODESYS V3 family (TwinCAT 3, CODESYS, and the vendor tools built on it). Read `cyclic-execution-rules.md` first — it governs *how* code is shaped; this covers *what* the language offers.

Everything here is vendor-neutral. For concrete library names, file formats and tooling see `twincat.md` or `codesys.md`.

## Data types

| Type | Width | Range / notes |
|---|---|---|
| `BOOL` | 8 bit | `TRUE` / `FALSE` |
| `BYTE` `WORD` `DWORD` `LWORD` | 8/16/32/64 | Bit strings — no arithmetic meaning |
| `SINT` `USINT` | 8 | −128…127 / 0…255 |
| `INT` `UINT` | 16 | −32768…32767 / 0…65535 |
| `DINT` `UDINT` | 32 | **Default for counters and ids** |
| `LINT` `ULINT` | 64 | |
| `REAL` | 32 | ~7 significant digits |
| `LREAL` | 64 | ~15 digits — **default for process values and positions** |
| `STRING(n)` | n+1 bytes | Single-byte; defaults to `STRING(80)` if `n` omitted |
| `WSTRING(n)` | | UTF-16 |
| `TIME` | 32 bit ms | `T#1M30S500MS`; wraps at ~49.7 days |
| `LTIME` | 64 bit ns | |
| `DATE` `TOD` `DT` | | `D#2026-08-07`, `TOD#14:30:00`, `DT#2026-08-07-14:30:00` |

Literals: `16#FF`, `2#1010_1100` (underscores allowed), `8#777`, `1.0E-3`, `T#500MS`. Typed literals where it matters: `LREAL#1.0`, `DINT#5`.

**Choose the type for the range and the operations** (PLCopen CP22): smallest type that fits, unsigned for unsigned data, enums and subranges where they apply. Don't use one wide type everywhere to avoid writing conversions.

Two defaults worth internalising: **`LREAL` for anything physical** — a 32-bit `REAL` runs out of resolution surprisingly early, and cannot hold millimetre precision past a few hundred metres of accumulated travel — and **`DINT` for counts**, because `INT` overflows silently at 32,767.

## POU types

| Keyword | State? | Use for |
|---|---|---|
| `PROGRAM` | yes, one global instance | Task entry points (`MAIN`) |
| `FUNCTION_BLOCK` | yes, per instance | Everything reusable — devices, sequences, controllers |
| `FUNCTION` | **no** | Pure computation; one return value; no memory between calls |
| `METHOD` | uses the FB's state | An operation on an FB, called explicitly |
| `PROPERTY` | uses the FB's state | Validated get/set access |
| `ACTION` | uses the FB's state | Named code block; legacy — prefer `METHOD` |

A `FUNCTION` cannot contain an FB instance and cannot remember anything. If you need a timer or an edge, it must be a `FUNCTION_BLOCK`.

Note PLCopen **CP16**: a task calls `PROGRAM` POUs, never a function block directly. Binding a task straight to an FB instance makes execution control ambiguous and is not portable.

## Variable sections

```pascal
FUNCTION_BLOCK FB_Station
VAR_INPUT
    bEnable     : BOOL;
    fSetpoint   : LREAL;            // mm
END_VAR
VAR_OUTPUT
    bDone       : BOOL;
    bError      : BOOL;
    nErrorID    : UDINT;
END_VAR
VAR_IN_OUT                          // by reference; caller MUST supply it
    stAxis      : AXIS_REF;
END_VAR
VAR                                 // instance state, persists between cycles
    eState      : E_StationState := E_StationState.Idle;
    fbTimer     : TON;
END_VAR
VAR CONSTANT
    cTimeout    : TIME := T#5S;
END_VAR
VAR_STAT                            // shared by ALL instances of this FB
    nInstances  : DINT;
END_VAR
VAR_TEMP                            // re-initialised every call — scratch only
    nLocalIdx   : DINT;
END_VAR
```

- Qualifiers: `RETAIN`, `PERSISTENT`, `CONSTANT` — see `cyclic-execution-rules.md` Rule 9 for what each survives.
- **`VAR_IN_OUT` is a reference.** No copy is made, the caller's variable is modified directly, and it must be assigned at every call site. This is how `AXIS_REF` and large structures are passed.
- **`VAR_TEMP` for genuine scratch** (PLCopen CP21) — loop counters especially. It is re-initialised each call, so a value cannot leak between cycles by accident. In practice it is rare in the wild (4 occurrences across the 1,378-file reference corpus, against widespread plain `VAR`), so you will mostly see `VAR` used for scratch. Prefer `VAR_TEMP` in new code; don't churn existing code over it.
- **`VAR_INST`** (TwinCAT) declares instance-lifetime storage inside a *method* — state that persists across calls without being visible on the FB. Useful for a method that owns an edge detector. 132 occurrences in the corpus, so it is a real idiom rather than a curiosity.

## Control flow

```pascal
IF a > b THEN ... ELSIF a = b THEN ... ELSE ... END_IF

CASE eState OF
    E_State.Idle:        ...
    E_State.Run,
    E_State.Hold:        ...            // multiple labels
    E_State.A..E_State.C: ...           // range
ELSE
    eState := E_State.Error;            // ALWAYS include — catches corrupted state
END_CASE

FOR i := 0 TO 9 BY 1 DO ... END_FOR     // BY optional
WHILE cond DO ... END_WHILE             // only with a provable bound
REPEAT ... UNTIL cond END_REPEAT
EXIT;  CONTINUE;  RETURN;
```

Assignment is `:=`. Comparison is `=`, not `==`. Output binding in a call is `=>`.
Operators: `AND OR XOR NOT`, `+ - * / MOD`, `**`, `<> < <= > >=`.
Comments: `// line`, `(* block *)`, `/* block */`.

Two PLCopen notes: don't modify the `FOR` variable inside the loop and don't rely on its value afterwards (L22, L13); parenthesise to make precedence explicit rather than trusting the reader to know the table (L15).

## Calling function blocks

```pascal
// All inputs in one call — the common form
fbStation(bEnable := TRUE, fSetpoint := 120.0, stAxis := stAxis1,
          bDone => bStationDone, bError => bStationError);

// Or set members and call bare (still one call per cycle)
fbStation.bEnable := TRUE;
fbStation(stAxis := stAxis1);           // VAR_IN_OUT must still be supplied
bStationDone := fbStation.bDone;

// Methods and properties
fbStation.Reset();
fbStation.Setpoint := 120.0;            // PROPERTY set
fCurrent := fbStation.ActualValue;      // PROPERTY get
```

Name parameters at the call site rather than relying on position (L14) — it survives someone adding a pin.

## User-defined types

```pascal
{attribute 'qualified_only'}            // forces E_State.Idle; prevents collisions
TYPE E_State :
(
    Idle    := 0,
    Running := 10,
    Done    := 20,
    Error   := 90
) DINT;                                 // explicit base type
END_TYPE

TYPE ST_Recipe :
STRUCT
    sName       : STRING(40);
    fTemp       : LREAL;                // degC
    nCycles     : DINT;
END_STRUCT
END_TYPE

TYPE T_StationIndex : DINT (0..15); END_TYPE      // subrange
```

Always put `{attribute 'qualified_only'}` on enums — unqualified members leak into the global namespace and collide with each other across libraries.

## Object orientation (3rd Edition)

> These constructs entered the standard in the **3rd Edition**. Runtimes on the 2nd Edition — OpenPLC and anything else compiling through matiec — support none of them. That is why this skill targets the CODESYS V3 family and not "IEC 61131-3" in general.

```pascal
INTERFACE I_Device
METHOD Reset : BOOL
END_METHOD

FUNCTION_BLOCK FB_DeviceBase IMPLEMENTS I_Device
FUNCTION_BLOCK FB_Pump EXTENDS FB_DeviceBase

// Inside FB_Pump
METHOD PUBLIC Reset : BOOL
    SUPER^.Reset();                     // call the parent implementation
    THIS^.eState := E_State.Idle;       // explicit self-reference
    Reset := TRUE;                      // assigning the method name returns it
```

- Access modifiers `PUBLIC`, `PRIVATE`, `PROTECTED`, `INTERNAL`. Default is public — be explicit.
- `ABSTRACT` and `FINAL` apply to both FBs and methods.
- **The FB body still runs on every instance call**, in addition to any methods. Put cyclic logic in the body and discrete operations in methods.
- Interface variables are references. Validate with `__QUERYINTERFACE()` before use and never assume one is assigned.

For *when* to use each of these rather than how to spell them, see `oop.md`. Keep hierarchies shallow: deep inheritance makes online change and live debugging considerably harder, and the debugger will show you the base implementation rather than the override you expected.

## Useful pragmas

```pascal
{attribute 'qualified_only'}                    // enums and GVLs — always
{attribute 'hide'}                              // hide from the library browser
{attribute 'no_init'}                           // skip zero-init (large arrays, boot time)
{region 'Error handling'} ... {endregion}       // folding
{attribute 'analysis' := '-33'}                 // suppress one static-analysis rule
{warning 'refactor before release'}             // deliberate compiler warning
```

Suppressing an analysis rule without a comment saying why is the same anti-pattern as a bare `lint:allow` — the next reader cannot distinguish a considered decision from an unreviewed one.

## Standard blocks

Available on every runtime in this family, though the supplying library is named differently per vendor:

`TON` `TOF` `TP` · `CTU` `CTD` `CTUD` · `R_TRIG` `F_TRIG` · `RS` `SR` · `SEL` `MUX` `LIMIT` `MIN` `MAX` · string functions `LEN` `LEFT` `RIGHT` `MID` `CONCAT` `FIND` `INSERT` `DELETE` `REPLACE`.

**Never reference a library that is not listed in the project file** — a missing library is a build failure, not a warning.

## Motion: the PLCopen contract

`MC_*` is a cross-vendor specification; TwinCAT's `Tc2_MC2` and CODESYS SoftMotion both implement it, so the contract is portable even where the library names are not.

| Signal | Meaning |
|---|---|
| `Execute` | Rising edge starts the command |
| `Busy` | Accepted and in progress |
| `Active` | This block currently controls the axis |
| `Done` / `InVelocity` / `InPosition` | Completed successfully |
| `CommandAborted` | Superseded by another block on the same axis |
| `Error` + `ErrorID` | Failed — handle both |

Minimum viable axis sequence: `MC_Reset` → `MC_Power` (hold `Enable` true for as long as the drive should stay on) → `MC_Home` → motion commands → `MC_Stop`.

Read `Error` **and** `CommandAborted` on every block. They are different events with different causes, and an unhandled `CommandAborted` presents to the operator as "the machine randomly stopped mid-move".
