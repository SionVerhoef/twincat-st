# TwinCAT 3 — vendor specifics

Everything that does **not** transfer to other CODESYS V3 tools. Target build **4024.x**: engineering via Visual Studio integration or TcXaeShell, monolithic installer, no package manager (that is 4026 — if the user is on 4026, say so, because install and tooling paths differ).

The core rules in `cyclic-execution-rules.md`, `st-language.md` and `naming-conventions.md` apply unchanged. This file is the seam.

Deeper material: [`twincat/project-files.md`](twincat/project-files.md) for editing project files and surviving git; [`twincat/ads-and-diagnostics.md`](twincat/ads-and-diagnostics.md) for ADS, EtherCAT triage and TcUnit.

## Orienting in an unfamiliar project

```bash
# Is this a TwinCAT project, and what shape?
find . -maxdepth 4 \( -name "*.tsproj" -o -name "*.plcproj" \) 2>/dev/null

# Build version the project was last saved with (also the XML schema version)
grep -ho 'ProductVersion="[^"]*"' $(find . -name "*.TcPOU" | head -1) 2>/dev/null

# What POUs exist, and what is the entry program?
find . -name "*.TcPOU" | sed 's#.*/##' | sort
grep -rl "PROGRAM MAIN" --include="*.TcPOU" .

# Global variables and I/O-mapped symbols
find . -name "*.TcGVL" -exec echo "--- {}" \; -exec cat {} \;

# Library references and pinned versions - do NOT use a library absent from this list
grep -A2 -E "PlaceholderReference|LibraryReference" $(find . -name "*.plcproj" | head -1)

# Task config: cycle times and priorities drive what work is legal in one scan
grep -rhoE '<(Task|CycleTime|Priority)[^>]*>' $(find . -name "*.tsproj" -o -name "*.xti" | head -20) 2>/dev/null | head -30
```

## Standard libraries

Only reference a library actually listed in the project's `.plcproj`. A missing library is a build failure, not a warning.

**`Tc2_Standard`** — the IEC blocks: `TON` `TOF` `TP` (timers) · `CTU` `CTD` `CTUD` (counters) · `R_TRIG` `F_TRIG` (edges) · `RS` `SR` (latches) · `SEL` `MUX` `LIMIT` `MIN` `MAX` · string functions `LEN` `LEFT` `RIGHT` `MID` `CONCAT` `FIND` `INSERT` `DELETE` `REPLACE`.

**`Tc2_System`** — runtime services: `ADSREAD` / `ADSWRITE` / `ADSRDWRT` function blocks, `MEMCPY` / `MEMSET` / `MEMCMP`, GUID and system-time helpers, task and system info.

**`Tc2_Utilities`** — conversions and helpers: time/date structure conversion (`SYSTEMTIME_TO_DT` and friends), `T_PLC_MS` (millisecond tick, useful for coarse timing), file access blocks, random numbers.

**`Tc2_MC2`** — PLCopen Motion Control: `MC_Power` `MC_Home` `MC_MoveAbsolute` `MC_MoveRelative` `MC_MoveVelocity` `MC_Stop` `MC_Halt` `MC_Reset` `MC_ReadStatus` `MC_ReadAxisError`, and the `AXIS_REF` type. Requires the NC PTP runtime (TF5000). The **block contracts** are PLCopen and portable — see `st-language.md`; only the library name and axis configuration are TwinCAT-specific.

**`Tc2_EtherCAT`** — CoE access (`FB_EcCoESdoRead` / `FB_EcCoESdoWrite`), master/slave state control and diagnostics.

**`Tc3_Module`** — TcCOM module base types, for module-oriented and Simulink-integrated projects.

**`Tc3_EventLogger`** — structured alarms and messages to the TwinCAT event logger. Strongly preferred over ad-hoc string logging for anything an operator must see.

## `FB_init` — construction, and the online-change trap

`FB_init` is TwinCAT's constructor: it runs before the first cycle and lets an instance receive configuration once, at instantiation, instead of on every call. It is the standard answer to PLCopen CP23 (too many pins) — 180 uses across the reference corpus, so it is mainstream rather than exotic.

The signature is fixed. The first two parameters are supplied by the runtime; anything after them is yours:

```pascal
METHOD FB_init : BOOL
VAR_INPUT
    bInitRetains : BOOL;   // TRUE on a cold start — retains are being initialised
    bInCopyCode  : BOOL;   // TRUE when the instance is being moved by an online change
    nBufferSize  : UDINT;  // your own configuration
END_VAR
```

```pascal
// Called at declaration:
VAR
    fbBuffer : FB_RingBuffer(nBufferSize := 256);
END_VAR
```

**The trap:** `FB_init` runs **again on every online change**, with `bInCopyCode := TRUE`, while the machine is running. Work that is not idempotent — allocating, resetting a counter, re-homing a state machine — is then repeated against live state. The idiom is to bail out early:

```pascal
IF bInCopyCode THEN RETURN; END_IF     // online change: leave the live instance alone

THIS^.pBuffer := __NEW(BYTE, nBufferSize);
```

`scripts/st_review.py` reports this as `X8`, and deliberately only when `FB_init` does something non-idempotent — a plain assignment is harmless to repeat.

Related: **`FB_exit`** runs on shutdown and before an online change replaces an instance (free anything `FB_init` allocated), and **`FB_reinit`** runs after the instance has been copied.

## `VAR_INST` — state inside a method

Declares storage with instance lifetime inside a *method*, so it persists across calls without appearing on the function block:

```pascal
METHOD PUBLIC CountPulses : DINT
VAR_INPUT
    bSignal : BOOL;
END_VAR
VAR_INST
    fbEdge : R_TRIG;        // survives between calls; invisible from outside
    nCount : DINT;
END_VAR

fbEdge(CLK := bSignal);
IF fbEdge.Q THEN
    nCount := nCount + 1;
END_IF
CountPulses := nCount;
```

132 occurrences in the corpus. Useful when a method owns an edge detector or a small counter that no one else should see. Note the usual caveat: the method must actually be called every cycle for the edge detector to work, so this belongs in a method the FB body invokes, not one a caller might skip.

## Pragmas worth knowing

```pascal
{attribute 'qualified_only'}                    // enums and GVLs - always use
{attribute 'hide'}                              // hide from the library browser
{attribute 'no_init'}                           // skip zero-init (large arrays, startup time)
{attribute 'TcCallAfterOutputUpdate'}           // run this POU after the output image is written
{attribute 'analysis' := '-33'}                 // suppress one static-analysis rule, with a reason
{region 'Error handling'} ... {endregion}       // folding
```

`{attribute 'qualified_only'}` is CODESYS-family, not TwinCAT-only. `TcCallAfterOutputUpdate` is TwinCAT.

## Tooling

| Tool | What it does |
|---|---|
| **XAE** (TE1000) | Engineering environment — Visual Studio integration, or the standalone TcXaeShell |
| **XAR** | The runtime |
| **Automation Interface** | COM/DTE scripting of XAE — the route to headless builds and CI. `TcUnit-Runner` uses it. |
| **Static Analysis** (TE1200) | Rule-based linting. If the project has a ruleset, treat it as the house standard — the skill and the linter must agree. |
| **Scope View** (TE1300 for the professional version) | Signal tracing; the right tool for timing questions |
| **TcUnit** | Open-source unit testing — see `twincat/ads-and-diagnostics.md` |

## 4024 gotchas

- **7-day trial licence** must be regenerated on the target roughly weekly (captcha in the licence device, then restart TwinCAT into Run). A "worked Monday, dead the following week" report is usually this.
- **A new file not registered in `.plcproj` is not compiled** and produces no error. Silent and very confusing. `scripts/tcpou.py register` fixes it.
- **`.TcPOU` files carry a UTF-8 BOM; line endings vary.** XAE writes CRLF, but most published code is LF, because git normalisation rewrites it and TwinCAT reads it back happily. Measured across 2,839 object files from the reference corpus: **97% have a BOM, but only 19% use CRLF** — and the split runs per repository, not per file. So do not "fix" line endings: **preserve whatever the file already uses**, or a one-line edit becomes a whole-file diff. `scripts/tcpou.py` detects both and restores them, reporting the style as a note rather than an error.
- **Activating a configuration stops the machine.** Never propose it casually.
- **Online change has limits** — changing an FB's interface or adding `PERSISTENT` data typically forces a full download, which resets state. This is why a small, stable FB interface is worth designing for.
- **`.library` files are compiled** — no readable source. A repository full of them is worthless as reference material regardless of file count.

## Project layout that ages well

```
MySolution/
├── MySolution.sln
├── MyProject/
│   ├── MyProject.tsproj
│   ├── _Config/IO/            <- .xti externalized I/O devices
│   ├── PLC/
│   │   ├── PLC.plcproj
│   │   ├── POUs/
│   │   │   ├── MAIN.TcPOU
│   │   │   ├── Devices/       <- FB per physical device
│   │   │   └── Sequences/     <- FB per process sequence
│   │   ├── DUTs/
│   │   ├── GVLs/
│   │   └── Tests/             <- TcUnit suites, excluded from the release build
└── .gitattributes
```

Beckhoff's own OOP Extended Sample uses a five-layer variant — `01_Submodules` → `02_Subsystems` → `03_Machine` → `04_Application` → `05_Visu` — with PackML state machines and unit modes (`Auto` / `SemiAuto` / `Manual` / `Maintenance`). See [`patterns.md`](patterns.md) for how those layers work and why dependencies must point downward; read it before designing a large machine structure.
