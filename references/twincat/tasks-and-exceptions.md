# Tasks, Shared Data and Runtime Exceptions

Two ways a PLC program fails that no single POU shows: two tasks touching the same data, and
a runtime exception that stops the PLC. The rules in the first half are vendor-neutral (PLCopen
CP10, CP11, CP15, CP26); the library names, Static Analysis rules and core-dump handling are
**TwinCAT-specific**, checked against Beckhoff InfoSys for 4024 and 4026.

## Data shared between tasks

### Find out which task runs what, first

Every question below starts from "which tasks touch this variable?". The task objects of the
PLC project (`.TcTTO` files) list the programs each task calls, and the cycle times and
priorities live in the `.tsproj` (see the orient block in `../twincat.md`). Follow each program
down to the FBs and globals it reaches. A function block instance declared in a GVL and called
from two programs in two tasks is the case people miss: the instance's internal state is shared
data too.

### What goes wrong

A task of higher priority can interrupt a lower one between any two instructions, and on a
multi-core controller two tasks run truly at the same time. Two failure shapes follow, and
neither shows up in a test on one task:

```pascal
// Lost update: both tasks run this. Each reads 41, each writes 42; one count is gone.
GVL.nPartsTotal := GVL.nPartsTotal + 1;

// Torn read: the fast task sees the position and the velocity from two different scans
// of the slow task, a pair that never existed.
fX := GVL.stAxisSnapshot.fPosition;   // mm   - written by the slow task
fV := GVL.stAxisSnapshot.fVelocity;   // mm/s - may already be the next scan's value
```

Do not reason about which accesses are atomic. Beckhoff's guidance is to treat every access
as non-atomic, because whether one is atomic depends on the processor.

### The rules

1. **One writer per variable** (CP10, CP26). Decide which task owns each shared variable; every
   other task only reads it. Two writers is a design to undo, not a race to lock around, unless
   it truly cannot be avoided.
2. **Read a foreign variable once per cycle** (CP15). Copy it into a local at the top of the
   task and use the copy, so every line of this scan sees the same value.
3. **Move multi-word data as one unit** (CP11). With a single writer, either exchange it through
   the process image between tasks or hand over a whole structure under a flag the reader
   acknowledges; both work only while one task writes.
4. **Lock only when there are several writers**, and keep the locked section short. Tc2_System
   has two mechanisms:

| Mechanism | Use it for | Shape |
|---|---|---|
| `FB_IecCriticalSection` | Short sections. One global instance per protected resource. | `Enter()`, access, `Leave()` — `Enter()` waits until it gets the lock, so a long section stalls the other task |
| `TestAndSet(flag)` | Longer sections. Returns TRUE when it took the flag. | Must have an `ELSE` path: when it returns FALSE, skip the access and try again next cycle |

```pascal
// Several writers, so a lock. The lock flag is owned by nobody and released by whoever took it.
IF TestAndSet(GVL.bRecipeLock) THEN
    GVL.stRecipe := stNewRecipe;      // the whole structure, inside the lock
    GVL.bRecipeLock := FALSE;         // release on every path out
ELSE
    bRecipePending := TRUE;           // not this cycle; retry next scan
END_IF
```

Never wait for a lock in a loop: that is `X1` under another name, and a lower-priority task
holding it cannot run to release it while you spin.

### Two TwinCAT specifics

- **An FB instance that does ADS must stay in one task.** Calling it from two tasks fails with
  `ADSERR_DEVICE_INVALIDCONTEXT` (`0x709`, 1801). The same holds for any communication or
  file block: give each task its own instance.
- **Static Analysis (TE1200) has rules for concurrent access**, SA0006 and SA0103. If the
  project has a Static Analysis licence, run them; they point at candidates, they do not prove
  the absence of a race. `st_review.py` does not check any of this: it reads one file at a time
  and does not know the task configuration.

## Runtime exceptions

### What one does

An exception stops the PLC project: its tasks stop executing, and TwinCAT itself stays in Run
mode. Nothing restarts it until someone does. On a machine this is the "PLC stopped, page fault"
or "access violation" call, and the first question is always which line.

The usual causes, with the reviewer rule that looks for each:

| Cause | Typical shape | Reviewer |
|---|---|---|
| Access violation | Dereferencing a null or stale `POINTER TO`, an unassigned `REFERENCE TO`, an interface variable that was never assigned | `X5`, `X6` |
| Integer division by zero | `nTotal / nCount` with `nCount` from a recipe or an HMI | `X4` |
| Array index out of range | A computed index past the array bounds. Without a check it is **not** an exception: the write lands in whatever memory follows | — (Rule 7) |
| Stack overflow | Recursion, or very large arrays declared as locals of a method or function | `CP13` |
| Exception in `FB_init` | Work in `FB_init` that touches something not yet there, often after an online change | `X8` |

A `REAL`/`LREAL` division by zero is a different case: whether it raises an exception or quietly
produces infinity or NaN depends on the floating-point exception setting of the task. Find out
which, rather than assuming either.

### Finding the line

- **XAE logged in when it happens:** the debugger stops on the faulting line and the call stack
  window shows how it got there. Read the call stack before anything else; the faulting line is
  often a library or helper and the cause is its caller.
- **Nobody logged in:** the runtime writes a core dump on the target by itself, into the boot
  folder (`C:\TwinCAT\3.1\Boot\Plc` before 4026, `C:\ProgramData\Beckhoff\TwinCAT\3.1\Boot\Plc\CoreDump`
  from 4026). Copy it to the engineering PC and open it with *PLC → Core Dump → Load*: XAE shows
  the project as it was at the exception, with the call tree and variable values.
- **A core dump only opens against the exact build that produced it** — the same project and its
  `.compileinfo` from `_CompileInfo`. Archive them together, or the dump is unreadable later.
- From 4026.14, `CreateCallstackCoreDump()` writes a call-stack-only dump from code, without
  stopping anything: useful to find out who calls a block with a bad argument.

The fix is almost never in the exception handler. It is the missing guard on the line the dump
points at.

### Implicit checks, for commissioning

TwinCAT and CODESYS let a project add special functions that the compiler calls around every
risky operation (*Add → POU for implicit checks*):

| Function | Checks |
|---|---|
| `CheckBounds` | Every array access with a variable index |
| `CheckDivDInt`, `CheckDivLInt`, `CheckDivReal`, `CheckDivLReal` | The divisor of every division |
| `CheckRangeSigned`, `CheckRangeUnsigned` (and the `L` forms for 64-bit) | Assignments to subrange types |
| `CheckPointer` | Every pointer dereference — the body is empty, you write the check yourself |

Know what they cost and what they hide:

- **They run on every access**, so they cost cycle time across the whole project. Measure the
  task's execution time with them in before deciding to ship them.
- **They do not apply inside libraries** by default, so a library's own out-of-range access is
  still unchecked.
- **The default `CheckBounds` clamps the index to the nearest bound and carries on.** That stops
  the memory corruption but turns it into a silent wrong value. Add a flag or a log entry in
  the function, so the clamp is seen; otherwise the check hides the defect it found.

They are a diagnostic. The defect is still the unguarded index or divisor in the code.

### `__TRY` / `__CATCH`

Structured exception handling exists from 4024 on targets that support it. Where it is not
supported the compiler says so.

```pascal
VAR
    eExc     : __SYSTEM.ExceptionCode;
    eLastExc : __SYSTEM.ExceptionCode;   // kept for the diagnosis
END_VAR

__TRY
    fRatio := fbScale.GetRatio();            // a call that can fault
__CATCH(eExc)
    fRatio := 0.0;
    eLastExc := eExc;                        // e.g. RTSEXCPT_DIVIDEBYZERO
    bError := TRUE;
__FINALLY
    nCalls := nCalls + 1;
__ENDTRY
```

- **What ran inside `__TRY` stopped at the fault**, half-done. Any state it was updating may now
  be inconsistent: treat the catch as an error path that puts the block into its error state,
  not as "carry on".
- **It is not flow control.** Catching a division by zero is no substitute for the `X4` guard; it
  only turns a stopped PLC into a running one with a wrong value, which can be worse on a
  machine.
- `F_RaiseException` (Tc2_System) throws a chosen code. Outside a `__TRY` it stops the PLC like
  any other exception.

Use it at the boundary to code you do not control — a third-party library, a formula from a
recipe — and log what it caught.
