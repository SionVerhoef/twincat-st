# Naming and conventions

**The project you are editing wins.** If the existing code uses a different scheme, follow it. A consistently "wrong" codebase is far better than a half-converted one — flag the divergence, don't fix it unasked. Everything below is the default for new code with no precedent.

## The convention question is genuinely contested

Worth knowing before you assert anything, because a senior controls engineer will have an opinion and may well have a different one.

- **PLCopen's own documents** use `x` for booleans — `xExecute`, `xDone`, `xBusy`, `iErrorID`. That is what the function-block library spec is written in.
- **PLCopen rule N2 is deliberately neutral.** It says: *if* you use type prefixes, define them and be consistent. It does not mandate prefixes at all.
- **Some respected TwinCAT practitioners drop prefixes entirely**, arguing that the IDE shows the type and a name should describe intent.
- **The TwinCAT community in practice uses `b`.** Measured across 1,378 `.TcPOU` files from the Beckhoff samples, Beckhoff-USA-Community, Stefan Henneken's corpus and other well-regarded libraries — 2,217 `BOOL` declarations:

  | Form | Count | Share |
  |---|---|---|
  | `bName` | 1,701 | 76.7% |
  | `Name` (no prefix) | 353 | 15.9% |
  | other | 150 | 6.8% |
  | `xName` | 13 | 0.6% |

So: **`b` is the TwinCAT default and this skill uses it**, but say "convention" rather than "the rule", and switch without complaint when the project or the vendor spec you are implementing against uses `x`.

## Variable prefixes

| Prefix | Type | Example |
|---|---|---|
| `b` | `BOOL` | `bValveOpen` |
| `n` | any integer (`SINT`…`ULINT`) | `nCycleCount` |
| `f` | `REAL` / `LREAL` | `fActualPosition` |
| `s` | `STRING` / `WSTRING` | `sRecipeName` |
| `t` | `TIME` / `LTIME` | `tTimeout` |
| `dt` | `DATE` / `DT` / `TOD` | `dtLastRun` |
| `by` `w` `dw` `lw` | `BYTE` `WORD` `DWORD` `LWORD` | `wStatusBits` |
| `a` | array, then the element prefix | `aStations`, `afTemperatures` |
| `st` | struct instance | `stRecipe` |
| `e` | enum instance | `eState` |
| `fb` | function block instance | `fbMoveAbsolute` |
| `i` | interface reference | `iDevice` |
| `p` | pointer | `pBuffer` |
| `ref` | reference | `refAxis` |
| `c` | constant | `cMaxStations` |

## Type and object prefixes

| Prefix | For |
|---|---|
| `FB_` | Function block — `FB_Pump` |
| `F_` | Function — `F_ScaleAnalogInput` |
| `I_` | Interface — `I_Device` |
| `E_` | Enum — `E_StationState` |
| `ST_` | Struct — `ST_Recipe` |
| `T_` | Alias / subrange — `T_StationIndex` |
| `P_` | Property — `P_ActualValue` |
| `GVL_` | Global variable list — `GVL_Machine` |
| `PRG_` | Program, except the conventional `MAIN` |

## Rules worth the ink

- **English throughout** — identifiers, comments, enum members, error text. A mixed-language codebase is a tax on every future handover.
- **`PascalCase` after the prefix.** `bEmergencyStopActive`, not `b_emergency_stop_active`.
- **Case is not significant to the compiler** but is to the reader and to search (PLCopen N4). `Motor` and `motor` are the same variable; pick one spelling and hold it.
- **Length in the useful band** (N6): roughly 8–25 characters, averaging ~15. `nTmpCnt2` is too short to mean anything; a 40-character name is too long to compare at a glance.
- **No abbreviations** unless domain-standard — `PID`, `SDO`, `PDO`, `HMI`, `NC`, `PLC` are fine.
- **Never shadow a global with a local** (N5). The compiler will not warn and the reader cannot tell which one is live.
- **Booleans state a positive condition.** `bReady`, not `bNotReady` — negated names produce double negatives at every call site.
- **Units in the declaration comment for every physical value.** `fSetpoint : LREAL; // degC` prevents an entire class of bug no compiler catches, and it is the highest-value comment in PLC code.
- **Constants, never magic numbers.** Array bounds, timeouts, error ids and scaling factors go in `VAR CONSTANT` or a GVL.
- **`{attribute 'qualified_only'}` on every enum and GVL**, so references read `E_State.Idle` and `GVL_Machine.cMaxStations` and cannot collide.
- **Error ids are namespaced hex constants** with documented meanings — `16#8101`, collected in one place so the HMI, the logs and the operator share a single list.

## Comments

Comment the **why**. The what is already in the code (PLCopen C1).

```pascal
// WRONG — restates the code
nCount := nCount + 1;   // increment count

// RIGHT — explains a decision that is not derivable from the code
// Filter runs on the 10 ms task: this sensor has ~30 ms of mechanical bounce,
// so anything faster reports phantom transitions.
fbDebounce(IN := bSensorRaw, PT := T#50MS);
```

Declaration comments carry the unit, the valid range, and the provenance of any magic value — "from datasheet section 4.2", "measured on machine #3". That last one is worth more than it looks: it tells the next person whether the number is a specification or an observation.

## Structure

- **One responsibility per function block** (PLCopen CP5). An FB that moves an axis *and* parses a recipe *and* drives the HMI is three FBs.
- **Devices get an FB; sequences get an FB.** The device FB knows how to actuate; the sequence FB knows the order. Mixing them makes both untestable.
- **The interface is the contract**: inputs, outputs, `bError`, `nErrorID`, and a `Reset()`. Keep it small and stable — every change to an FB interface forces a full download, which on a production machine is a scheduled event, not a keystroke.
- **Cap the pin count at about 10** (CP23). Past that, group related parameters into a `STRUCT`, or move configuration into `FB_init` so it is supplied once at instantiation rather than every cycle.
- **No logic in `MAIN`** beyond calling the top-level FBs in a defined order. `MAIN` is a wiring diagram, not a program.
