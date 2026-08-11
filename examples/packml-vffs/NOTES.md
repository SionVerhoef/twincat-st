# PackML VFFS demo — Beckhoff USA Community

**Source:** [Beckhoff-USA-Community/PackML_PLC_Example](https://github.com/Beckhoff-USA-Community/PackML_PLC_Example) · MIT · Copyright (c) 2023 Beckhoff Automation LLC · see `LICENSE`
**What it is:** a vertical form-fill-seal packaging machine, structured with PackML state machines. Real applied industrial code, not a teaching toy.

Five files, chosen because together they show one complete vertical slice: how a machine is wired at the top, how a reusable module base is defined, and how one physical device implements a contract.

## What to take from each

### `MAIN.TcPOU` — a wiring diagram, not a program

The entire implementation body is:

```pascal
CyclicLogic();
```

Everything else is declarations. This is the strongest available evidence for the rule in `references/naming-conventions.md` → *Structure*: **no logic in `MAIN`.** Note also `VFFSDemo : FB_Machine := (Name := 'VFFS Demo');` — an FB instance configured at declaration rather than in an init step.

### `FB_EquipmentModuleTemplate.TcPOU` — an abstract base for reusable modules

`FUNCTION_BLOCK ABSTRACT FB_EquipmentModuleTemplate EXTENDS FB_PackML_Base`. Worth reading for:

- **The method contract a module must fill in** — `Initialize`, `CyclicLogic`, `CreateEvents`, `Monitoring`. Concrete modules override these; the base drives them.
- **`Initialize` is a real init state machine** (2,256 chars), not a constructor. There is no constructor in ST — this is what initialisation actually looks like, and `CyclicLogic` gates on `_InitComplete` until it finishes.
- **Alarms via a helper** — `RaiseAlarm2Args` wraps `F_RaiseAlarmWithStringParameters`. This is the house error-reporting seam: one place that knows how alarms are raised, so modules do not each invent one.

### `FB_Cylinder.TcPOU` + `I_Cylinder.TcIO` — a device FB and its contract

The pair is the point. Read the interface first, then the implementation.

`I_Cylinder.TcIO` declares only `Extend`, `Retract`, `Extended`, `Retracted`, `ExtendTime`, `RetractTime` — methods and properties with **no bodies**. That is the whole vocabulary a caller gets.

`FB_Cylinder` then `EXTENDS FB_ComponentBase IMPLEMENTS I_Cylinder`, and demonstrates:

- **Direct I/O mapping in a declaration** — `Output AT %Q* : BOOL;`
- **Timer and edge instances as members** — `Extend_TON : TON;`, `Extend_RTRIG : R_TRIG;` — declared once, driven from `CyclicLogic`, exactly as `cyclic-execution-rules.md` Rules 2 and 5 require
- **Properties backed by private fields** — `Extended` reads `_Extended`; the caller cannot write it
- **A simulated device** — extension is modelled by elapsed time, not a real sensor, so the demo runs without hardware. Real cylinders have reed switches; do not copy the timing model into production without feedback.

### `ST_Cylinder_Config.TcDUT` — the config/status/command split

Trivially small on its own (`ExtendTime`, `RetractTime`), and that is the lesson. The upstream project splits a device's data into four structs — `_Config`, `_Status`, `_Command`, `_HMI` — so each has one direction and one audience. Copying that split costs nothing and makes the HMI seam obvious.

## Where this diverges from `references/naming-conventions.md`

Read honestly, because you will hit this on any real codebase:

| This code | Our convention |
|---|---|
| `Output`, `_Extended`, `_ExtendTime` | `bOutput`, `bExtended`, `fExtendTime` |
| `Extend_TON`, `Extend_RTRIG` (type as suffix) | `fbExtendTimer` (type as prefix) |
| `_ExtendTime : LREAL := 1000; // ms` | `tExtendTime : TIME := T#1S` |

None of this is wrong — it is a coherent internal convention, consistently applied, with a `_` backing-field idiom that reads well. It is a live demonstration of the rule at the top of `naming-conventions.md`: **the project you are editing wins.**

The `LREAL`-milliseconds choice is a genuine trade-off rather than a mistake: a `TIME` literal cannot be set from an HMI faceplate, an `LREAL` can. Note the cost — you lose the type safety that stops someone passing a millisecond count where a `TIME` was expected.

## Caveat

This is a **demo** machine. The simulated cylinder feedback above is the clearest example: production code reads real sensors and needs the timeout-to-error path that `cyclic-execution-rules.md` Rule 1 describes. Take the structure; do not take the simulation.
