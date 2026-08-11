# The State pattern in ST — PLC-Design-Patterns

**Source:** [0w8States/PLC-Design-Patterns](https://github.com/0w8States/PLC-Design-Patterns) · BSD 2-Clause · Copyright (c) 2021, John Helfrich · see `LICENSE`
**What it is:** the GoF design patterns implemented in Structured Text. These three files are the State pattern, plus one global variable list from the Observer sample in the same repository.

This is here as the **object-oriented alternative to `CASE eState OF`**, so you can judge when each is right. `references/cyclic-execution-rules.md` Rule 1 teaches the `CASE` form because it is the correct default. This shows the other option honestly.

## `I_State.TcIO` — one method per event

```
INTERFACE I_State
  METHOD Turn_On : BOOL          METHOD Card_Inserted : BOOL
  METHOD Turn_Off : BOOL         METHOD Card_Ejected : BOOL
  METHOD Service : BOOL          METHOD Cancel : BOOL
  METHOD Op : BOOL               METHOD Failure : BOOL
  METHOD SystemTest_OK : BOOL
  PROPERTY Description : E_StateDescription
```

The inversion is the whole idea. A `CASE` state machine is organised **by state**, with every event handled inside each branch. This is organised **by event**: the interface lists what can happen, and each state FB decides what *it* does about each one. Adding a state means adding a file that implements this interface — no existing `CASE` block is touched.

## `FB_ATM_Machine.TcPOU` — the context

```pascal
VAR_OUTPUT
    ipState : I_State := fbOff;          // current state IS an interface reference
END_VAR
VAR
    fbOff             : FB_Off(THIS);    // FB_init passes the machine back to the state
    fbIdle            : FB_Idle(THIS);
    fbServingCustomer : FB_ServingCustomer(THIS);
    rtrigOnButton     : R_TRIG;          // one edge detector per input
```

Three things to notice:

1. **`ipState : I_State := fbOff`** — the "current state" variable is an interface reference, not an enum. Transitioning is reassigning it. Every state object is a persistent FB instance, allocated once at download — no runtime allocation, so this stays legal under `cyclic-execution-rules.md` Rule 8.
2. **`FB_Off(THIS)`** — the `FB_init` mechanism, passing the machine into each state so a state can command the transition. This is the ST equivalent of constructor injection.
3. **An `R_TRIG` per input**, so each button press is one event rather than a level held across scans — Rule 4, applied consistently.

## When to use which

| | `CASE eState OF` | State pattern |
|---|---|---|
| States are few and stable | **Better** — all logic visible in one file | Overkill |
| Debugging on a live machine | **Better** — one place to breakpoint, state is a readable enum | Harder: behaviour is spread across files, and the debugger shows you an interface |
| Adding states often | Every addition edits the same `CASE` | **Better** — add a file, touch nothing existing |
| States share complex per-state data | Cramped | **Better** — each state FB owns its own `VAR` |
| Reviewer is a controls engineer, not a software engineer | **Better** — universally read | Needs the pattern explained |

**Default to `CASE`.** Reach for this when a machine genuinely has many states with substantial per-state behaviour, and when the team is comfortable with interfaces. The debugging cost is real and is paid at commissioning, at night, under time pressure.

## `Param.TcGVL` — a parameter list

From the Observer sample in the same repository, included because it is a clean minimal GVL:

```pascal
{attribute 'qualified_only'}
VAR_GLOBAL CONSTANT
    MaxSubscribers : INT := 5;
END_VAR
```

Exactly the form `references/naming-conventions.md` recommends: `qualified_only` so it must be referenced as `Param.MaxSubscribers`, and `CONSTANT` so an array bound cannot be changed at runtime. Note it is declared with `ParameterList="True"` in the XML, which is what makes it settable per-instance in the project tree.

## Caveats

- **Built on TwinCAT 3.1.4022**, not 4024 — `tcpou.py check` flags this. Nothing here is version-sensitive, but do not assume the whole repository loads cleanly on a current build.
- **An ATM, not a machine.** The domain is deliberately generic so the pattern is the only thing on show. Read it for shape, not for process control.
- **`x` prefix for BOOL** (`xOnButton`) — a third naming convention, different again from both `naming-conventions.md` and the PackML sample. Further evidence that the house convention is a choice, not a standard.
