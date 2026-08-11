# Object orientation in Structured Text

`st-language.md` covers how to spell `EXTENDS`, `IMPLEMENTS` and `THIS^`. This is about when to reach for them — and when not to.

The temptation with OOP in ST is to import habits from C# or Java wholesale. Some transfer; some are actively harmful on a controller that must survive an online change while a machine is running.

## Start from composition

**Default to composition. Reach for inheritance only when you can name the substitutability you need.**

```pascal
// Composition — FB_Station HAS a cylinder and a timer
FUNCTION_BLOCK FB_Station
VAR
    fbClamp : FB_Cylinder;
    fbTimer : TON;
END_VAR
```

Composition survives change: swapping the clamp for a different actuator is a declaration edit. Inheritance is a permanent commitment to a shape, and in ST it carries costs a desktop language does not have — deep hierarchies make online change harder, and the live debugger will show you the base implementation rather than the override you expected.

The reference corpus bears this out: across 1,378 `.TcPOU` files there are 236 `EXTENDS` against 226 `IMPLEMENTS` and 2,237 `METHOD` — inheritance is used, but it is not the dominant structuring tool. `ABSTRACT` appears 45 times. This is a codebase style that leans on interfaces and methods far more than on class hierarchies.

## When each one is right

| Use | When | Signal you chose wrong |
|---|---|---|
| **Composition** | One thing *has* another; you want to swap the part | You are reaching into the inner object's internals from outside |
| **Interface** | Several unrelated things must be *usable the same way* | The interface has one implementer and always will |
| **Inheritance** | Genuine specialisation, shared implementation you would otherwise copy | The child overrides nearly everything, or you cannot substitute it for the parent |

Interfaces are the workhorse for machine code: a `I_Device` with `Reset()` and a `Status` property lets a diagnostics module iterate over every device without knowing what any of them are. That is the case where OOP genuinely pays in a PLC.

## The feature-combination trap

Beckhoff's own OOP Extended sample ships this hierarchy, and it is worth studying precisely because it shows the failure mode:

```
FB_Cylinder IMPLEMENTS I_Cylinder
  ├── FB_CylinderDiag      EXTENDS FB_Cylinder
  └── FB_CylinderTemp      EXTENDS FB_Cylinder
        └── FB_CylinderTempDiag EXTENDS FB_CylinderTemp
```

Two independent features — diagnostics and temperature — and already four types. Add a third and you need eight. Inheritance multiplies rather than adds, and `FB_CylinderTempDiag` has to duplicate whatever `FB_CylinderDiag` did because ST has no multiple inheritance.

This is the motivating example for **Decorator**: wrap the base object in a diagnostics object that implements the same interface and forwards to it. Features then compose in any combination without a type explosion. If you find yourself writing `FB_ThingAWithB`, stop and consider wrapping instead.

## SOLID, translated to function blocks

PLCopen's OOP guidelines adopt SOLID explicitly. What each one means here:

- **Single responsibility** — an FB that moves an axis, parses a recipe and drives the HMI is three FBs. Also PLCopen CP5.
- **Open/closed** — add a device type by writing a new FB that implements the existing interface, not by adding a branch to a `CASE` in the manager.
- **Liskov substitution** — if `FB_PumpB EXTENDS FB_Pump`, anywhere accepting `FB_Pump` must work with `FB_PumpB`. An override that throws an error for an operation the parent supports breaks this, and the caller has no way to know.
- **Interface segregation** — several small interfaces beat one large one. An FB forced to implement six methods it does not need is a design smell, and stub methods are where bugs hide.
- **Dependency inversion** — a sequence should depend on `I_Cylinder`, not on `FB_FestoCylinderType47`. This is what makes the sequence testable without hardware.

That last one is the practical payoff: dependency inversion is what turns "we can only test this on the machine" into "we can test this at a desk with a simulated device". See `testing-tcunit.md`.

## Patterns that earn their place

From the corpus and PLCopen's guidance, the ones that recur in real machine code:

| Pattern | Use |
|---|---|
| **State** | A device whose behaviour differs per state, where the `CASE` has grown unmanageable. One FB per state implementing a common interface. |
| **Decorator** | Optional features — diagnostics, logging, simulation — without a type explosion (see above). |
| **Command** | An operation as an object: queue it, undo it, log it. PLCopen's OOP guidelines formalise this as `ICommand`, paired with `IModule` for the things commands act on. |
| **Observer** | Several consumers need to hear about an event without the producer knowing them. |
| **Factory** | Selecting an implementation at startup — real device vs simulation. |

**Modules and commands** is PLCopen's own framing and is worth knowing: a *module* is a part of the machine (actuator, sensor, assembly) implementing `IModule`; a *command* is a discrete action against one, implementing `ICommand` and following the edge-triggered behaviour model. It reconciles classic PLCopen motion blocks with an object-oriented application, since a block can be used both ways.

Don't apply a pattern because it has a name. A `CASE` statement with four states is better than four FBs and an interface. Reach for State when the `CASE` is genuinely unmanageable, not before.

## Things that bite in ST specifically

- **`FB_init` runs again on an online change.** Guard non-idempotent work with `IF bInCopyCode THEN RETURN; END_IF`. See `twincat.md`.
- **A pointer or interface reference cached across cycles can dangle** after an online change. Re-take it; validate with `__ISVALIDREF` / `__QUERYINTERFACE` before use.
- **The FB body runs on every call, in addition to methods.** Cyclic logic goes in the body; discrete operations go in methods. Putting cyclic logic in a method that the caller might not call is a common source of "it stopped working".
- **Interface method calls are dynamically dispatched**, which costs a little time and prevents some compiler optimisation. Almost never a problem — but on a 1 ms task with hundreds of instances, measure rather than assume.
- **Changing an FB interface forces a full download**, which on a production machine is a scheduled event. Design the interface to be stable; add rather than reshape.
- **Keep hierarchies shallow** — two levels is usually plenty. Every level is another place the debugger shows you the wrong implementation.
